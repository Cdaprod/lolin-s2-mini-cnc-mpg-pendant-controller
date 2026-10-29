"""Small, allocation-free kinematic model for the decorative bezel rotor."""

import math


def bezel_segment_levels(angle, count=24, minimum=1, maximum=15):
    """Brightness envelope for fixed tangent arcs, sweeping clockwise.

    A single compact light wave travels around the ring. The arcs never rotate
    or change orientation; their broad, curved strokes remain attached to the
    bezel while their palette intensity changes. Positive angle follows
    increasing screen-space theta (clockwise).
    """
    count = max(1, int(count))
    period = 2.0 * math.pi
    levels = []
    for index in range(count):
        theta = 2.0 * math.pi * index / count
        delta = ((theta - float(angle) + period * 0.5) % period) - period * 0.5
        envelope = math.exp(-0.5 * (delta / 0.58) ** 2)
        levels.append(int(round(minimum + (maximum - minimum) * envelope)))
    return tuple(levels)


def update_bezel_segment_levels(angle, levels, minimum=1, maximum=15):
    """Update a retained level buffer without allocating animation state."""
    count = len(levels)
    if count < 1:
        return
    period = 2.0 * math.pi
    angle = float(angle)
    for index in range(count):
        theta = 2.0 * math.pi * index / count
        delta = ((theta - angle + period * 0.5) % period) - period * 0.5
        envelope = math.exp(-0.5 * (delta / 0.58) ** 2)
        levels[index] = int(round(minimum + (maximum - minimum) * envelope))


class BezelRotor:
    """Integrate ambient and MPG-follow rotation without touching machine state.

    Encoder timestamps and signed detent deltas are read-only inputs supplied
    by the existing application state. Position is integrated in monotonic
    time, so animation timing does not depend on the app loop's poll rate.
    """

    IDLE_AFTER_S = 0.18
    ACCELERATION_TAU_S = 0.12

    def __init__(self, ambient_period_s=54.0, encoder_gain=0.04,
                 max_speed_rad_s=0.35, inertia_s=0.9,
                 direction_change_min_s=20.0,
                 direction_change_max_s=40.0, frame_rate=24):
        self.ambient_period_s = _bounded(ambient_period_s, 1.0, 600.0, 54.0)
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
