"""Thin CircuitPython GPIO adapter; all pin names come from configuration."""

from .manager import InputSnapshot


class CircuitPythonInputAdapter:
    """Read conditioned logic only; A/A-/B/B- require external interfacing."""

    configured = True

    def __init__(self, inputs, axis_inputs, multiplier_inputs, button_inputs,
                 estop_input=None, mpg_active_low=False,
                 selector_active_low=True, button_active_low=True,
                 estop_active_low=True, deadman_input=None,
                 deadman_active_low=True, encoder=None, selector_refresh=None,
                 resources=None):
        self.inputs = inputs
        self.axis_inputs = axis_inputs
        self.multiplier_inputs = multiplier_inputs
        self.button_inputs = button_inputs
        self.estop_input = estop_input
        self.mpg_active_low = bool(mpg_active_low)
        self.selector_active_low = bool(selector_active_low)
        self.button_active_low = bool(button_active_low)
        self.estop_active_low = bool(estop_active_low)
        self.deadman_input = deadman_input
        self.deadman_active_low = bool(deadman_active_low)
        self.encoder = encoder
        self.encoder_position = encoder.position if encoder is not None else 0
        self.selector_refresh = selector_refresh
        self.resources = resources or ()

    def _active(self, pin, active_low):
        value = bool(pin.value)
        return not value if active_low else value

    def read(self):
        if self.selector_refresh is not None:
            self.selector_refresh()
        axes = tuple(name for name, pin in self.axis_inputs.items()
                     if self._active(pin, self.selector_active_low))
        multipliers = tuple(name for name, pin in self.multiplier_inputs.items()
                            if self._active(pin, self.selector_active_low))
        buttons = dict((name, self._active(pin, self.button_active_low))
                       for name, pin in self.button_inputs.items())
        estop = False
        if self.estop_input is not None:
            raw = bool(self.estop_input.value)
            estop = not raw if self.estop_active_low else raw
        deadman = False
        if self.deadman_input is not None:
            deadman = self._active(self.deadman_input, self.deadman_active_low)
        delta = None
        a = False
        b = False
        if self.encoder is not None:
            position = self.encoder.position
            delta = position - self.encoder_position
            self.encoder_position = position
        else:
            a = self._active(self.inputs["A"], self.mpg_active_low)
            b = self._active(self.inputs["B"], self.mpg_active_low)
        return InputSnapshot(a, b, axes, multipliers, buttons, estop,
                             deadman, delta)


def _input_pin(board, digitalio, name, pull_up=True):
    pin = digitalio.DigitalInOut(getattr(board, name))
    pin.direction = digitalio.Direction.INPUT
    pin.pull = digitalio.Pull.UP if pull_up else digitalio.Pull.DOWN
    return pin


def from_config(config, shared_i2c=None):
    """Build configured inputs or return `None`; never supplies default pins."""
    if not config.get("inputs_enabled"):
        return None
    required = (config.get("mpg_a_pin"), config.get("mpg_b_pin"))
    if not all(required):
        raise ValueError("enabled physical inputs require MPG_PIN_A and MPG_PIN_B")
    import board
    import digitalio
    mpg_active_low = config.get("mpg_active_low", False)
    selector_active_low = config.get("selector_active_low", True)
    button_active_low = config.get("button_active_low", True)
    encoder = None
    pins = {}
    if config.get("mpg_use_rotaryio", True):
        import rotaryio
        encoder = rotaryio.IncrementalEncoder(
            getattr(board, required[0]), getattr(board, required[1]), divisor=1
        )
    else:
        pins = {
            "A": _input_pin(board, digitalio, required[0], mpg_active_low),
            "B": _input_pin(board, digitalio, required[1], mpg_active_low),
        }
    selector_refresh = None
    resources = []
    if (config.get("selector_backend") == "mcp23017" and
            config.get("selector_interface_verified")):
        from .mcp23017 import MCP23017InputBank
        sda_name = config.get("i2c_sda_pin")
        scl_name = config.get("i2c_scl_pin")
        if not sda_name or not scl_name:
            raise ValueError("MCP23017 selector backend requires I2C pins")
        if shared_i2c is None:
            raise ValueError("MCP23017 selector backend requires shared I2C bus")
        i2c = shared_i2c
        bank = MCP23017InputBank(
            i2c, config.get("mcp23017_address", 0x20), 0x01FF
        )
        axes = dict((name, bank.pin(bit)) for name, bit in
                    config.get("mcp23017_axis_bits", {}).items())
        multipliers = dict((name, bank.pin(bit)) for name, bit in
                           config.get("mcp23017_multiplier_bits", {}).items())
        selector_refresh = bank.refresh
        resources.append(bank)
    else:
        axes = dict((name, _input_pin(board, digitalio, pin, selector_active_low))
                    for name, pin in config.get("axis_pins", {}).items() if pin)
        multipliers = dict(
            (name, _input_pin(board, digitalio, pin, selector_active_low))
            for name, pin in config.get("multiplier_pins", {}).items() if pin
        )
    buttons = dict((name, _input_pin(board, digitalio, pin, button_active_low))
                   for name, pin in config.get("button_pins", {}).items() if pin)
    estop = None
    if config.get("estop_observe_pin"):
        estop = _input_pin(board, digitalio,
                           config["estop_observe_pin"],
                           config.get("estop_active_low", True))
    deadman = None
    if config.get("deadman_pin"):
        deadman = _input_pin(board, digitalio, config["deadman_pin"],
                             config.get("deadman_active_low", True))
    return CircuitPythonInputAdapter(
        pins, axes, multipliers, buttons, estop, mpg_active_low,
        selector_active_low, button_active_low,
        config.get("estop_active_low", True), deadman,
        config.get("deadman_active_low", True), encoder, selector_refresh,
        resources
    )
