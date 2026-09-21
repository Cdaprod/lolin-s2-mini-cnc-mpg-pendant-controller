"""Optional physical indicator sinks separated from unverified LED wiring."""


class NullIndicatorOutput:
    def update(self, logical_state):
        return None


class DigitalIndicatorOutput:
    """Drive verified external interface logic, never the pendant LED directly."""

    ACTIVE_STATES = ("READY", "JOG", "RUN", "HOLD", "ALARM")

    def __init__(self, output, active_high=True):
        self.output = output
        self.active_high = bool(active_high)
        self.last_state = None

    def update(self, logical_state):
        if logical_state == self.last_state:
            return False
        active = logical_state in self.ACTIVE_STATES
        self.output.value = active if self.active_high else not active
        self.last_state = logical_state
        return True


def from_config(config):
    if not config.get("indicator_enabled"):
        return NullIndicatorOutput()
    if not config.get("indicator_verified"):
        raise ValueError("indicator output requires explicit electrical verification")
    if not config.get("indicator_pin"):
        raise ValueError("enabled indicator requires MPG_INDICATOR_PIN")
    import board
    import digitalio
    output = digitalio.DigitalInOut(getattr(board, config["indicator_pin"]))
    output.direction = digitalio.Direction.OUTPUT
    output.value = not config.get("indicator_active_high", True)
    return DigitalIndicatorOutput(
        output, config.get("indicator_active_high", True)
    )
