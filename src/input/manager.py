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
                 buttons=None, estop=False, deadman=False, mpg_delta=None,
                 valid=True, valid_reason=None):
        self.mpg_a = bool(mpg_a)
        self.mpg_b = bool(mpg_b)
        self.axes = tuple(axes or ())
        self.multipliers = tuple(multipliers or ())
        self.buttons = buttons or {}
        self.estop = bool(estop)
        self.deadman = bool(deadman)
        self.mpg_delta = mpg_delta
        self.valid = bool(valid)
        self.valid_reason = valid_reason


class NullInputAdapter:
    configured = False

    def read(self):
        return InputSnapshot()


class InputPollResult:
    def __init__(self, events, estop, estop_changed, deadman_changed,
                 selector_changed, multiplier_changed=False, mpg_activity=0,
                 selector_direction=0, multiplier_direction=0,
                 button_states=None, selectors_valid_changed=False,
                 encoder_overrun=False, encoder_overrun_delta=0,
                 input_valid_changed=False):
        self.events = events
        self.estop = estop
        self.estop_changed = estop_changed
        self.deadman_changed = deadman_changed
        self.selector_changed = selector_changed
        self.multiplier_changed = multiplier_changed
        self.mpg_activity = int(mpg_activity)
        self.selector_direction = int(selector_direction)
        self.multiplier_direction = int(multiplier_direction)
        self.button_states = dict(button_states or {})
        self.selectors_valid_changed = bool(selectors_valid_changed)
        self.encoder_overrun = bool(encoder_overrun)
        self.encoder_overrun_delta = int(encoder_overrun_delta)
        self.input_valid_changed = bool(input_valid_changed)


class InputManager:
    """One MPG stream plus selectors/buttons; never communicates with GRBL."""

    MAX_EVENTS = 16
    MAX_ENCODER_DETENTS_PER_POLL = 4

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
        self._discard_next_encoder_sample = False
        self._suppress_buttons_until_release = False

    def reset_encoder(self):
        """Discard a partial detent at a transport or safety boundary."""
        self.decoder.reset()
        self.hardware_accumulator = 0
        self._discard_next_encoder_sample = True

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
        if not sample.valid:
            self.last_axes = axes
            self.last_multipliers = sample.multipliers
            if self.state.selected_physical_axis != "OFF":
                self.selectors.select_axis("OFF")
            reason = sample.valid_reason or "input_sample_unavailable"
            self.state.selectors_valid = False
            self.state.selector_error = reason
            self.state.error = reason
            return
        multipliers = sample.multipliers
        previous_selector_error = self.state.selector_error
        valid = True
        error = None
        axes_changed = axes != self.last_axes
        self.last_axes = axes
        if len(axes) == 0:
            if axes_changed:
                self.selectors.select_axis("OFF")
        elif len(axes) == 1:
            if axes[0] not in self.selectors.axis_map:
                if axes_changed:
                    self.selectors.select_axis("OFF")
                valid = False
                error = "axis selector value is invalid"
            elif axes_changed:
                try:
                    self.selectors.select_axis(axes[0])
                except SelectorError:
                    self.selectors.select_axis("OFF")
                    valid = False
                    error = "axis selector value is invalid"
        else:
            if axes_changed:
                self.selectors.select_axis("OFF")
            valid = False
            error = "axis selector is not one-hot"
        self.last_multipliers = multipliers
        if len(multipliers) == 1:
            try:
                self.selectors.select_multiplier(multipliers[0])
            except SelectorError as exc:
                valid = False
                error = str(exc)
        else:
            valid = False
            error = "multiplier selector is not one-hot"
        self.state.selectors_valid = valid
        self.state.selector_error = error
        if error:
            self.state.error = error
        elif (previous_selector_error is not None and
              self.state.error == previous_selector_error):
            self.state.error = None

    def poll(self, now):
        sample = self.adapter.read()
        estop_changed = (self.last_estop is None or
                         sample.estop != self.last_estop)
        self.last_estop = sample.estop
        deadman = bool(sample.deadman and sample.valid)
        deadman_changed = (self.last_deadman is None or
                           deadman != self.last_deadman)
        self.last_deadman = deadman
        previous_physical_axis = self.state.selected_physical_axis
        previous_multiplier = self.state.selected_multiplier
        previous_selectors_valid = self.state.selectors_valid
        previous_input_valid = getattr(self.state, "input_valid", True)
        self.state.input_valid = bool(sample.valid)
        self.state.input_error = (sample.valid_reason
                                  if not sample.valid else None)
        input_valid_changed = previous_input_valid != self.state.input_valid
        self._update_selectors(sample)
        selector_changed = previous_physical_axis != self.state.selected_physical_axis
        multiplier_changed = previous_multiplier != self.state.selected_multiplier
        selectors_valid_changed = previous_selectors_valid != self.state.selectors_valid
        if getattr(self.adapter, "configured", True):
            self.state.deadman_enabled = deadman
        activity = 0
        encoder_overrun = False
        encoder_overrun_delta = 0
        if (selector_changed or multiplier_changed or selectors_valid_changed or
                input_valid_changed or not sample.valid or
                self._discard_next_encoder_sample):
            # A detent sampled with a selector transition has ambiguous
            # ownership. Drop it and partial counts instead of applying it
            # to the newly selected axis or increment. A reset also discards
            # the first sample after a transport boundary.
            self.decoder.reset(sample.mpg_a, sample.mpg_b)
            self.hardware_accumulator = 0
            self._discard_next_encoder_sample = False
        else:
            if sample.mpg_delta is None:
                direction = self.decoder.update(sample.mpg_a, sample.mpg_b, now)
                if direction > 0:
                    self._emit(ROTATE_CW)
                    activity += 1
                elif direction < 0:
                    self._emit(ROTATE_CCW)
                    activity -= 1
            else:
                signed_delta = int(sample.mpg_delta) * self.decoder.direction
                threshold = self.decoder.counts_per_detent
                max_counts = threshold * self.MAX_ENCODER_DETENTS_PER_POLL
                if abs(signed_delta) > max_counts:
                    # A large position jump can follow a stalled polling loop.
                    # Discard the entire sample and partial detent so the
                    # backlog cannot become a burst of later jog requests.
                    encoder_overrun = True
                    encoder_overrun_delta = signed_delta
                    self.hardware_accumulator = 0
                    self.decoder.reset(sample.mpg_a, sample.mpg_b)
                else:
                    activity += signed_delta
                    self.hardware_accumulator += signed_delta
                    while abs(self.hardware_accumulator) >= threshold:
                        direction = 1 if self.hardware_accumulator > 0 else -1
                        self._emit(ROTATE_CW if direction > 0 else ROTATE_CCW)
                        self.hardware_accumulator -= direction * threshold
                        if len(self.events) >= self.MAX_EVENTS:
                            break
        button_states = sample.buttons if sample.valid else {}
        if not sample.valid:
            self._suppress_buttons_until_release = True
        button_released_for_rearm = (
            sample.valid and self._suppress_buttons_until_release and
            not any(bool(button_states.get(name, False))
                    for name in self.buttons))
        if button_released_for_rearm:
            self._suppress_buttons_until_release = False
        for name, button in self.buttons.items():
            if (not sample.valid or self._suppress_buttons_until_release or
                    button_released_for_rearm):
                button.reset(now)
                continue
            generated = button.update(bool(button_states.get(name, False)), now)
            if ((name in ("BACK", "CANCEL") and "press" in generated) or
                    (name in ("SELECT", "FN") and "short" in generated)):
                self._emit(BUTTON_EVENTS[name][0])
            if "long" in generated:
                self._emit(BUTTON_EVENTS[name][1])
        events = self.events
        self.events = []
        axis_order = ("OFF", "X", "Y", "Z", "4", "5", "6")
        multiplier_order = ("X1", "X10", "X100")
        axis_direction = self._direction(
            axis_order, previous_physical_axis,
            self.state.selected_physical_axis)
        multiplier_direction = self._direction(
            multiplier_order, previous_multiplier, self.state.selected_multiplier)
        return InputPollResult(
            events, sample.estop, estop_changed, deadman_changed,
            selector_changed, multiplier_changed, activity,
            axis_direction, multiplier_direction, button_states,
            selectors_valid_changed, encoder_overrun, encoder_overrun_delta,
            input_valid_changed
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
            "valid": current.valid, "valid_reason": current.valid_reason,
        }
        data.update(values)
        self.snapshot = InputSnapshot(**data)
