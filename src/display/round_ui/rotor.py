"""Small, allocation-free kinematic model for the decorative bezel rotor."""

import math

_WAVE_BINS = 2160  # 90 angular samples per 24-segment ring step.
_WAVE_HALF_BINS = _WAVE_BINS // 2
# Keep the moving highlight visually local. A wider wave lights most of the
# 12-arc ring at once, which reads as a persistent smear after extended use.
# At the 30-degree segment pitch this leaves a bright lead arc and a short,
# smooth falloff to its immediate neighbors.
_WAVE_SIGMA = 0.72
BEZEL_SEGMENT_COUNT = 4
# Four long, fixed curved accents sit at the cardinal points. A brightness
# wave travels clockwise among them; no arc pivots like a moving worm.
BEZEL_SEGMENT_OFFSET_RAD = -math.pi / 2.0
BEZEL_TRACK_RADIUS = 96.0
BEZEL_ARC_TILE_SIZE = 39
BEZEL_ARC_HALF_LENGTH = 16.5
_NORMALIZED_WAVE = bytes(
    int(round(255.0 * math.exp(-0.5 * (
        (math.pi * index / _WAVE_HALF_BINS) / _WAVE_SIGMA) ** 2)))
    for index in range(_WAVE_HALF_BINS + 1)
)


def bezel_segment_levels(angle, count=BEZEL_SEGMENT_COUNT, minimum=9,
                         maximum=15, phase_offset=0.0):
    """Brightness envelope for fixed tangent arcs, sweeping clockwise.

    A single compact light wave travels around the ring. The arcs never rotate
    or change orientation; their curved strokes remain attached to the bezel
    while their palette intensity changes. Positive angle follows increasing
    screen-space theta (clockwise). A precomputed angular lookup avoids repeated
    exponentials in the embedded animation loop.
    """
    count = max(1, int(count))
    levels = [0] * count
    update_bezel_segment_levels(angle, levels, minimum, maximum, phase_offset)
    return tuple(levels)


def update_bezel_segment_levels(angle, levels, minimum=9, maximum=15,
                                phase_offset=0.0):
    """Update a retained level buffer without allocating animation state."""
    count = len(levels)
    if count < 1:
        return
    phase = int((float(angle) % (2.0 * math.pi)) *
                (_WAVE_BINS / (2.0 * math.pi))) % _WAVE_BINS
    span = maximum - minimum
    center_offset = int(float(phase_offset) *
                        (_WAVE_BINS / (2.0 * math.pi)))
    for index in range(count):
        center = (index * _WAVE_BINS + count // 2) // count
        center = (center + center_offset) % _WAVE_BINS
        delta = (center - phase) % _WAVE_BINS
        if delta > _WAVE_HALF_BINS:
            delta = _WAVE_BINS - delta
        envelope = _NORMALIZED_WAVE[delta]
        levels[index] = minimum + (span * envelope + 127) // 255


class BezelRotor:
    """Integrate ambient and MPG-follow rotation without touching machine state.

    Encoder timestamps and signed detent deltas are read-only inputs supplied
    by the existing application state. Position is integrated in monotonic
    time, so animation timing does not depend on the app loop's poll rate.
    """

    IDLE_AFTER_S = 0.18
    ACCELERATION_TAU_S = 0.12

    def __init__(self, ambient_period_s=46.0, encoder_gain=0.04,
                 max_speed_rad_s=0.35, inertia_s=0.9,
                 direction_change_min_s=20.0,
                 direction_change_max_s=40.0, frame_rate=24):
        self.ambient_period_s = _bounded(ambient_period_s, 1.0, 600.0, 46.0)
        self.encoder_gain = _bounded(encoder_gain, 0.0, 10.0, 0.04)
        self.max_speed_rad_s = _bounded(max_speed_rad_s, 0.001, 4.0, 0.35)
        self.inertia_s = _bounded(inertia_s, 0.05, 10.0, 0.9)
        minimum = _bounded(direction_change_min_s, 5.0, 3600.0, 20.0)
        maximum = _bounded(direction_change_max_s, minimum, 3600.0, 40.0)
        self.direction_change_min_s = minimum
        self.direction_change_max_s = maximum
        self.frame_rate = int(_bounded(frame_rate, 1, 60, 24))

        self.angle = 0.0
        self.ambient_direction = 1
        self.velocity = self._ambient_velocity()
        self.mode = "AMBIENT"
        self._last_update = None
        self._last_encoder_timestamp = None
        self._last_encoder_time = None
        self._last_encoder_direction = 0
        self._next_direction_change = None
        self._change_count = 0
        self._frame = None

    @staticmethod
    def _sign(value):
        return 1 if value > 0 else (-1 if value < 0 else 0)

    def _ambient_velocity(self):
        return (self.ambient_direction * 2.0 * math.pi /
                self.ambient_period_s)

    def _next_interval(self):
        span = max(0, int(self.direction_change_max_s -
                          self.direction_change_min_s))
        # A deterministic 20-40 s schedule avoids an RNG dependency while
        # giving each reversal a slightly different dwell time.
        offset = ((self._change_count * 13 + 7) % (span + 1)) if span else 0
        self._change_count += 1
        return self.direction_change_min_s + offset

    def frame_due(self, now):
        """True no faster than the configured presentation frame ceiling."""
        frame = int(float(now) * self.frame_rate)
        if frame == self._frame:
            return False
        self._frame = frame
        return True

    def update(self, now, encoder_timestamp=None, encoder_delta=0):
        now = float(now)
        if self._last_update is None:
            self._last_update = now
            self._next_direction_change = now + self._next_interval()

        dt = max(0.0, now - self._last_update)
        self._last_update = now
        if (self._next_direction_change is not None and
                now >= self._next_direction_change):
            self.ambient_direction *= -1
            self._next_direction_change = now + self._next_interval()

        prior_velocity = self.velocity
        event = (encoder_timestamp is not None and
                 encoder_timestamp != self._last_encoder_timestamp)
        if event:
            direction = self._sign(int(encoder_delta))
            timestamp = float(encoder_timestamp)
            if direction:
                interval = (timestamp - self._last_encoder_timestamp
                            if self._last_encoder_timestamp is not None else 0.0)
                detents_per_second = (
                    abs(int(encoder_delta)) / interval if interval > 0.0 else 1.0
                )
                target_speed = min(
                    self.max_speed_rad_s,
                    max(0.015, detents_per_second * self.encoder_gain),
                )
                target = direction * target_speed
                # Direction reversals change sign promptly while angle remains
                # continuous. Same-direction speed changes ease in smoothly.
                if direction != self._last_encoder_direction:
                    self.velocity = target
                else:
                    alpha = 1.0 - math.exp(
                        -dt / self.ACCELERATION_TAU_S)
                    self.velocity += (target - self.velocity) * alpha
                self._last_encoder_direction = direction
                self._last_encoder_time = now
                self.mode = "FOLLOW"
            self._last_encoder_timestamp = timestamp
        elif (self._last_encoder_time is None or
              now - self._last_encoder_time >= self.IDLE_AFTER_S):
            target = self._ambient_velocity()
            alpha = 1.0 - math.exp(-dt / self.inertia_s)
            self.velocity += (target - self.velocity) * alpha
            self.mode = "AMBIENT" if abs(self.velocity-target) < 0.01 else "COAST"
        else:
            self.mode = "FOLLOW"

        self.angle = (self.angle + (prior_velocity + self.velocity) * 0.5 * dt) % (
            2.0 * math.pi)
        return self.angle, self.velocity


def _bounded(value, minimum, maximum, fallback):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return fallback
    return max(minimum, min(maximum, value))
