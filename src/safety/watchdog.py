"""Communication and jog watchdog checks using an injected clock."""


class Watchdog:
    def __init__(self, state, communication_timeout=2.0, jog_timeout=0.5):
        self.state = state
        self.communication_timeout = float(communication_timeout)
        self.jog_timeout = float(jog_timeout)
        self.last_jog_event = None

    def note_jog(self, now):
        self.last_jog_event = now

    def poll(self, now):
        events = []
        last = self.state.last_controller_response
        reference = last
        if reference is None and self.state.connection_state == "connecting":
            reference = self.state.connection_started_timestamp
        if (self.state.connection_state in ("connected", "connecting") and
                reference is not None and
                now - reference > self.communication_timeout):
            self.state.connection_state = "disconnected"
            self.state.machine_state = "error"
            self.state.error = "controller response timeout"
            self.state.jog_active = False
            events.append("communication_timeout")
        if (self.state.jog_active and self.last_jog_event is not None and
                now - self.last_jog_event > self.jog_timeout):
            self.state.jog_active = False
            events.append("jog_timeout")
        return events
