"""Semantic action dispatcher and safe MPG-to-GRBL translation."""

from src.safety.state_machine import SafetyError


class ActionDispatcher:
    def __init__(self, state, controller, safety, jog_feed=500.0,
                 commands=None, watchdog=None, clock=None):
        self.state = state
        self.controller = controller
        self.safety = safety
        self.jog_feed = float(jog_feed)
        self.watchdog = watchdog
        self.clock = clock
        self.commands = {
            "PROBE_Z": "G91 G38.2 Z-10 F100",
            "SAFE_Z": "G53 G0 Z0",
            "PARK": "G53 G0 X0 Y0",
        }
        if commands:
            self.commands.update(commands)

    def jog(self, direction):
        self.safety.require_jog()
        distance = self.state.jog_increment * (1 if direction > 0 else -1)
        if not self.controller.queue_jog(
                self.state.selected_axis, distance, self.jog_feed):
            self.state.error = "jog queue full"
            return False
        self.state.jog_active = True
        if self.watchdog is not None:
            self.watchdog.note_jog(self.clock() if self.clock else 0.0)
        return True

    def dispatch(self, action):
        if action == "FN":
            return True
        if action == "JOG_CANCEL":
            self.controller.cancel_jog()
            return True
        if action == "FEED_HOLD":
            self.controller.realtime("hold")
            return True
        if action == "START_RESUME":
            if self.safety.inhibit_reason():
                raise SafetyError(self.safety.inhibit_reason())
            if self.state.machine_state not in ("idle", "hold"):
                raise SafetyError("start disallowed in " + self.state.machine_state)
            self.controller.realtime("start")
            return True
        if action == "SOFT_RESET":
            self.controller.realtime("soft_reset")
            return True
        if action == "UNLOCK":
            self.safety.require_recovery()
            return self.controller.queue_command("$X", "action")
        self.safety.require_command(motion=True)
        if action == "HOME":
            return self.controller.queue_command("$H", "action")
        if action == "ZERO_AXIS":
            if self.state.selected_axis is None:
                raise SafetyError("axis selector is OFF")
            return self.controller.queue_command(
                "G10 L20 P0 {}0".format(self.state.selected_axis), "action"
            )
        if action == "ZERO_XYZ":
            return self.controller.queue_command(
                "G10 L20 P0 X0 Y0 Z0", "action"
            )
        if action == "SPINDLE_TOGGLE":
            command = "M5" if self.state.spindle_command in ("CW", "CCW") else "M3"
            return self.controller.queue_command(command, "action")
        if action in self.commands:
            return self.controller.queue_command(self.commands[action], "action")
        raise ValueError("unknown action: " + action)
