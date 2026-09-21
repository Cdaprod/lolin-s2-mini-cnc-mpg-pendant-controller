"""Application safety policy; not a substitute for a hardwired E-stop."""


class SafetyError(RuntimeError):
    pass


class SafetyStateMachine:
    JOG_STATES = ("idle", "jog")
    COMMAND_STATES = ("idle", "hold")

    def __init__(self, state):
        self.state = state

    def inhibit_reason(self, require_deadman=False):
        if self.state.estop_observed or self.state.estop_latched:
            return "E-stop inhibited"
        if self.state.connection_state != "connected":
            return "controller disconnected"
        if require_deadman and not self.state.deadman_enabled:
            return "dead-man not enabled"
        if self.state.alarm is not None:
            return "controller alarm"
        return None

    def require_jog(self):
        reason = self.inhibit_reason(require_deadman=True)
        if reason:
            raise SafetyError(reason)
        if self.state.machine_state not in self.JOG_STATES:
            raise SafetyError("jog disallowed in " + self.state.machine_state)
        if self.state.selected_axis is None:
            raise SafetyError("axis selector is OFF")

    def require_command(self, motion=True):
        reason = self.inhibit_reason(require_deadman=motion)
        if reason:
            raise SafetyError(reason)
        if self.state.machine_state not in self.COMMAND_STATES:
            raise SafetyError("command disallowed in " + self.state.machine_state)

    def require_recovery(self):
        if self.state.estop_observed or self.state.estop_latched:
            raise SafetyError("E-stop inhibited")
        if self.state.connection_state != "connected":
            raise SafetyError("controller disconnected")

    def observe_estop(self, active):
        self.state.set_estop(active)
