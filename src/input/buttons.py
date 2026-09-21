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


class DebouncedButton:
    """Nonblocking active-state debouncer with one-shot long-press events."""

    def __init__(self, debounce=0.03, long_press=0.8):
        self.debounce = float(debounce)
        self.long_press = float(long_press)
        self.raw = False
        self.stable = False
        self.changed_at = 0.0
        self.pressed_at = None
        self.long_sent = False

    def update(self, active, now):
        """Return `press`, `short`, `release`, or one-shot `long` events."""
        active = bool(active)
        events = []
        if active != self.raw:
            self.raw = active
            self.changed_at = now
        if self.raw != self.stable and now - self.changed_at >= self.debounce:
            self.stable = self.raw
            if self.stable:
                self.pressed_at = now
                self.long_sent = False
                events.append("press")
            else:
                if self.pressed_at is not None and not self.long_sent:
                    events.append("short")
                self.pressed_at = None
                self.long_sent = False
                events.append("release")
        if (self.stable and not self.long_sent and self.pressed_at is not None
                and now - self.pressed_at >= self.long_press):
            self.long_sent = True
            events.append("long")
        return events
