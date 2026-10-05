"""Protocol-v1 host endpoint joining a pendant to a controller adapter."""

from src.transport.protocol import (COMMAND, MOTION, MOTION_START, MOTION_STOP,
                                    ReliableSession, STATUS)


class HostBridge:
    """Own the receiver-local lease and controller-neutral command boundary."""

    def __init__(self, transport, adapter, clock, session_id=None,
                 nonce_factory=None, status_interval_ms=200):
        self.adapter = adapter
        self.clock = clock
        self.status_interval_ms = int(status_interval_ms)
        self.last_status_ms = None
        options = {}
        if nonce_factory is not None:
            options["nonce_factory"] = nonce_factory
        self.session = ReliableSession(
            transport, self._dispatch, clock, role="responder",
            session_id=session_id, on_motion_stop=self.adapter.stop_jog,
            **options)

    @property
    def state(self):
        return self.adapter.state

    def poll(self):
        self.session.poll()
        state = self.adapter.poll()
        now = int(self.clock() * 1000)
        if (self.session.established and self.session.outstanding is None and
                (self.last_status_ms is None or
                 now - self.last_status_ms >= self.status_interval_ms)):
            if self.session.send(state.status_payload(), STATUS, reliable=False):
                self.last_status_ms = now
        return state

    def _dispatch(self, packet):
        if packet.message_class == MOTION:
            action = packet.flags & (MOTION_START | MOTION_STOP)
            if action == MOTION_START:
                return self._start_jog(packet.payload)
            # ReliableSession validates the intent ID and owns stop/expiry.
            if action == MOTION_STOP:
                return True
            return False
        if packet.message_class != COMMAND:
            return False
        try:
            name = packet.payload.decode("ascii")
        except UnicodeError:
            return False
        return self.adapter.command(name)

    def _start_jog(self, payload):
        try:
            name, axis, direction, feed = payload.decode("ascii").split("|")
            direction = int(direction)
            feed = float(feed)
        except (UnicodeError, ValueError):
            return False
        if name != "JOG":
            return False
        return self.adapter.start_jog(axis, direction, feed)

    def close(self):
        self.adapter.stop_jog()
        self.adapter.close()
