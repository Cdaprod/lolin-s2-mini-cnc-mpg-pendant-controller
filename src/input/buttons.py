"""Semantic button events and configurable FN chord mapping."""

ACTIONS = (
    "HOME", "ZERO_AXIS", "ZERO_XYZ", "START_RESUME", "FEED_HOLD",
    "JOG_CANCEL", "UNLOCK", "SOFT_RESET", "PROBE_Z", "SAFE_Z",
    "PARK", "SPINDLE_TOGGLE", "FN",
)

DEFAULT_BUTTONS = {
    "HOME": "HOME", "ZERO": "ZERO_AXIS", "START": "START_RESUME",
    "HOLD": "FEED_HOLD", "PROBE": "PROBE_Z", "CANCEL": "JOG_CANCEL",
}
DEFAULT_FN = {
    "HOME": "SAFE_Z", "ZERO": "ZERO_XYZ", "START": "SPINDLE_TOGGLE",
    "HOLD": "SOFT_RESET", "PROBE": "PARK",
}


class ButtonMapper:
    def __init__(self, primary=None, fn=None):
        self.primary = dict(DEFAULT_BUTTONS)
        self.fn = dict(DEFAULT_FN)
        if primary:
            self.primary.update(primary)
        if fn:
            self.fn.update(fn)

    def action_for(self, button, fn_active=False):
        action = (self.fn if fn_active else self.primary).get(button.upper())
        if action is not None and action not in ACTIONS:
            raise ValueError("unknown configured action: " + action)
        return action
