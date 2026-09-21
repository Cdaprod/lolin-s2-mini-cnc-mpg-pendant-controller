"""Validated quadrature decoder with no transport or GPIO dependencies."""

# Clockwise for the sequence 00, 01, 11, 10, 00. Reverse wiring can be
# accommodated with ``direction=-1`` without changing application logic.
_TRANSITIONS = {
    0x1: 1, 0x7: 1, 0xE: 1, 0x8: 1,
    0x2: -1, 0xB: -1, 0xD: -1, 0x4: -1,
}


class MPGDecoder:
    def __init__(self, counts_per_detent=4, direction=1,
                 min_event_interval=0.0, clock=None):
        if counts_per_detent < 1:
            raise ValueError("counts_per_detent must be positive")
        self.counts_per_detent = int(counts_per_detent)
        self.direction = 1 if direction >= 0 else -1
        self.min_event_interval = float(min_event_interval)
        self.clock = clock
        self.previous = None
        self.accumulator = 0
        self.invalid_transitions = 0
        self.last_event_at = None

    def reset(self, a=None, b=None):
        self.previous = None if a is None else ((bool(a) << 1) | bool(b))
        self.accumulator = 0

    def update(self, a, b, now=None):
        """Return -1/1 per complete detent or zero for no event."""
        current = (int(bool(a)) << 1) | int(bool(b))
        if self.previous is None:
            self.previous = current
            return 0
        if current == self.previous:
            return 0
        key = (self.previous << 2) | current
        self.previous = current
        delta = _TRANSITIONS.get(key)
        if delta is None:
            self.invalid_transitions += 1
            self.accumulator = 0
            return 0
        self.accumulator += delta * self.direction
        if abs(self.accumulator) < self.counts_per_detent:
            return 0
        event = 1 if self.accumulator > 0 else -1
        self.accumulator -= event * self.counts_per_detent
        if now is None and self.clock is not None:
            now = self.clock()
        if (now is not None and self.last_event_at is not None and
                now - self.last_event_at < self.min_event_interval):
            return 0
        self.last_event_at = now
        return event
