"""Cooperative physical-control polling and normalized UI event generation."""

from src.display.ui import (
    BACK, CANCEL, FN, LONG_FN, LONG_SELECT, ROTATE_CCW, ROTATE_CW, SELECT,
)
from .buttons import DebouncedButton
from .mpg import MPGDecoder
from .selectors import SelectorError, SelectorModel

BUTTON_EVENTS = {
    "SELECT": (SELECT, LONG_SELECT),
    "BACK": (BACK, None),
    "FN": (FN, LONG_FN),
    "CANCEL": (CANCEL, None),
}


class InputSnapshot:
    """Normalized sample supplied by hardware or a host-side fake adapter."""

    def __init__(self, mpg_a=False, mpg_b=False, axes=None, multipliers=None,
                 buttons=None, estop=False, deadman=False, mpg_delta=None):
        self.mpg_a = bool(mpg_a)
        self.mpg_b = bool(mpg_b)
        self.axes = tuple(axes or ())
        self.multipliers = tuple(multipliers or ())
        self.buttons = buttons or {}
        self.estop = bool(estop)
        self.deadman = bool(deadman)
        self.mpg_delta = mpg_delta


class NullInputAdapter:
    configured = False

    def read(self):
        return InputSnapshot()


class InputPollResult:
    def __init__(self, events, estop, estop_changed, deadman_changed,
                 selector_changed, multiplier_changed=False, mpg_activity=0,
                 selector_direction=0, multiplier_direction=0):
        self.events = events
        self.estop = estop
        self.estop_changed = estop_changed
        self.deadman_changed = deadman_changed
        self.selector_changed = selector_changed
        self.multiplier_changed = multiplier_changed
        self.mpg_activity = int(mpg_activity)
        self.selector_direction = int(selector_direction)
        self.multiplier_direction = int(multiplier_direction)


class InputManager:
    """One MPG stream plus selectors/buttons; never communicates with GRBL."""

    MAX_EVENTS = 16

    def __init__(self, state, adapter=None, counts_per_detent=4, direction=1,
                 debounce=0.03, long_press=0.8, axis_map=None):
        self.state = state
        self.adapter = adapter or NullInputAdapter()
        self.decoder = MPGDecoder(counts_per_detent, direction)
        self.selectors = SelectorModel(state, axis_map)
        self.buttons = dict((name, DebouncedButton(debounce, long_press))
                            for name in BUTTON_EVENTS)
        self.events = []
        self.last_estop = None
        self.last_deadman = None
        self.last_axes = None
        self.last_multipliers = None
        self.dropped_events = 0
        self.hardware_accumulator = 0

    def _emit(self, event):
        if event is None:
            return
        if len(self.events) >= self.MAX_EVENTS:
            self.dropped_events += 1
            return
        self.events.append(event)

    def _update_selectors(self, sample):
        if not getattr(self.adapter, "configured", True):
            return
        axes = sample.axes
        multipliers = sample.multipliers
        if axes != self.last_axes:
            self.last_axes = axes
            if len(axes) == 0:
                self.selectors.select_axis("OFF")
            elif len(axes) == 1:
                try:
                    self.selectors.select_axis(axes[0])
                except SelectorError:
                    self.selectors.select_axis("OFF")
            else:
                self.selectors.select_axis("OFF")
                self.state.error = "axis selector is not one-hot"
        if multipliers != self.last_multipliers:
            self.last_multipliers = multipliers
            if len(multipliers) == 1:
                try:
                    self.selectors.select_multiplier(multipliers[0])
                except SelectorError as exc:
                    self.state.error = str(exc)
            elif len(multipliers) > 1:
                self.state.error = "multiplier selector is not one-hot"

    def poll(self, now):
        sample = self.adapter.read()
        estop_changed = (self.last_estop is None or
                         sample.estop != self.last_estop)
        self.last_estop = sample.estop
        deadman_changed = (self.last_deadman is None or
                           sample.deadman != self.last_deadman)
        self.last_deadman = sample.deadman
        previous_axis = self.state.selected_axis
        previous_multiplier = self.state.selected_multiplier
        self._update_selectors(sample)
        if getattr(self.adapter, "configured", True):
            self.state.deadman_enabled = sample.deadman
        activity = 0
        if sample.mpg_delta is None:
            direction = self.decoder.update(sample.mpg_a, sample.mpg_b, now)
            if direction > 0:
                self._emit(ROTATE_CW)
                activity += 1
            elif direction < 0:
                self._emit(ROTATE_CCW)
                activity -= 1
        else:
            signed_delta = sample.mpg_delta * self.decoder.direction
            activity += signed_delta
            self.hardware_accumulator += signed_delta
            threshold = self.decoder.counts_per_detent
            while abs(self.hardware_accumulator) >= threshold:
                direction = 1 if self.hardware_accumulator > 0 else -1
                self._emit(ROTATE_CW if direction > 0 else ROTATE_CCW)
                self.hardware_accumulator -= direction * threshold
                if len(self.events) >= self.MAX_EVENTS:
                    break
        for name, button in self.buttons.items():
            generated = button.update(bool(sample.buttons.get(name, False)), now)
            if ((name in ("BACK", "CANCEL") and "press" in generated) or
                    (name in ("SELECT", "FN") and "short" in generated)):
                self._emit(BUTTON_EVENTS[name][0])
            if "long" in generated:
                self._emit(BUTTON_EVENTS[name][1])
        events = self.events
        self.events = []
        axis_order = (None, "X", "Y", "Z", "A", "B", "C")
        multiplier_order = ("X1", "X10", "X100")
        axis_direction = self._direction(
            axis_order, previous_axis, self.state.selected_axis)
        multiplier_direction = self._direction(
            multiplier_order, previous_multiplier, self.state.selected_multiplier)
        return InputPollResult(
            events, sample.estop, estop_changed, deadman_changed,
            previous_axis != self.state.selected_axis,
            previous_multiplier != self.state.selected_multiplier, activity,
            axis_direction, multiplier_direction
        )

    @staticmethod
    def _direction(order, previous, current):
        if previous not in order or current not in order:
            return 0
        delta = order.index(current) - order.index(previous)
        return 1 if delta > 0 else -1 if delta < 0 else 0


class SyntheticInputAdapter:
    """Mutable host adapter for deterministic full-pipeline simulation."""

    def __init__(self):
        self.configured = True
        self.snapshot = InputSnapshot()

    def read(self):
        return self.snapshot

    def set(self, **values):
        current = self.snapshot
        data = {
            "mpg_a": current.mpg_a, "mpg_b": current.mpg_b,
            "axes": current.axes, "multipliers": current.multipliers,
            "buttons": current.buttons, "estop": current.estop,
            "deadman": current.deadman,
            "mpg_delta": current.mpg_delta,
        }
        data.update(values)
        self.snapshot = InputSnapshot(**data)
