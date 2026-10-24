"""Controller-side jog lease and replay guard for the ESP32-C3 adapter.

Only admitted commands may be passed to GRBL. Caller MUST run tick() regularly
and wire cancellation to the actual UART realtime jog-cancel/hold path.
"""
from src.controller.jog_command import build_jog


class JogLease:
    def __init__(self, emit, cancel, now, max_age=0.25):
        self.emit, self.cancel, self.now = emit, cancel, now
        self.max_age = float(max_age)
        if not 0 < self.max_age <= 0.5:
            raise ValueError("unsafe motion lease duration")
        self.owner = None
        self.session = None
        self.last_sequence = None
        self.deadline = None
        self.active = False

    def admit(self, owner, session, sequence, axis, distance, feed,
              deadman=False, controller_idle=False):
        if (not deadman or not controller_idle or
                not isinstance(owner, bytes) or len(owner) != 6 or
                not isinstance(session, int) or not 0 < session <= 0xffffffff or
                not isinstance(sequence, int) or not 0 <= sequence <= 65535):
            return False
        if self.active and self.now() >= self.deadline:
            self.revoke()
            return False
        if self.owner is not None and (self.owner != owner or
                                      self.session != session):
            return False
        if self.last_sequence is not None:
            delta = (sequence - self.last_sequence) & 65535
            if not 0 < delta < 32768:
                return False
        try:
            command = build_jog(axis, distance, feed)
        except (ValueError, TypeError):
            return False
        if self.emit(command) is not True:
            return False
        self.owner, self.session = owner, session
        self.last_sequence = sequence
        self.deadline = self.now() + self.max_age
        self.active = True
        return True

    def tick(self):
        if self.active and self.now() >= self.deadline:
            self.revoke()

    def revoke(self):
        previous = self.active
        self.owner = self.session = self.last_sequence = self.deadline = None
        self.active = False
        if previous:
            self.cancel()
        return previous
