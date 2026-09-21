"""Display and logical indicator contracts."""

INDICATOR_STATES = (
    "OFF", "READY", "JOG", "RUN", "HOLD", "ALARM", "DISCONNECTED",
)


class Display:
    def render(self, state):
        raise NotImplementedError


class Indicator:
    """Logical LED+ / LED- state; no electrical drive assumptions."""

    def __init__(self):
        self.state = "OFF"

    def set(self, value):
        value = value.upper()
        if value not in INDICATOR_STATES:
            raise ValueError("invalid indicator state: " + value)
        self.state = value
