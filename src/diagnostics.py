"""Compact structured diagnostics for the passive USB CDC monitor."""


def _token(value):
    value = str(value)
    # Keep each key/value pair machine-readable and bounded on CircuitPython.
    return value.replace("%", "_25").replace("=", "_").replace(" ", "_")[:80]


def emit(event, **fields):
    """Write one low-allocation event line to CircuitPython's USB console."""
    parts = ["event=" + _token(event)]
    for key in sorted(fields):
        value = fields[key]
        if value is not None:
            parts.append("{}={}".format(_token(key), _token(value)))
    print("[event] " + " ".join(parts))


def input_configuration_fields(config, adapter_configured,
                               mcp23017_detected, mcp23017_address):
    """Return the resolved, non-secret physical input map for startup logs."""
    def pin_map(values):
        if not values:
            return "none"
        return ",".join("{}:{}".format(name, pin)
                        for name, pin in values.items() if pin) or "none"

    encoder = "A:{},B:{}".format(config.get("mpg_a_pin") or "none",
                                 config.get("mpg_b_pin") or "none")
    return {
        "selector_backend": config.get("selector_backend") or "disabled",
        "inputs_enabled": config.get("inputs_enabled", False),
        "adapter_configured": bool(adapter_configured),
        "selector_interface_verified": config.get(
            "selector_interface_verified", False),
        "encoder_pins": encoder,
        "encoder_mode": "rotaryio" if config.get("mpg_use_rotaryio", True)
                       else "gpio",
        "encoder_counts_per_detent": config.get("mpg_counts_per_detent", 4),
        "encoder_direction": config.get("mpg_direction", 1),
        "axis_pins": pin_map(config.get("axis_pins", {})),
        "axis_map": pin_map(config.get("axis_map", {})),
        "increment_pins": pin_map(config.get("multiplier_pins", {})),
        "button_pins": pin_map(config.get("button_pins", {})),
        "estop_pin": config.get("estop_observe_pin") or "unassigned",
        "deadman_pin": config.get("deadman_pin") or "unassigned",
        "selector_active_low": config.get("selector_active_low", True),
        "button_active_low": config.get("button_active_low", True),
        "estop_active_low": config.get("estop_active_low", True),
        "deadman_active_low": config.get("deadman_active_low", True),
        "mcp23017_detected": bool(mcp23017_detected),
        "mcp23017_address": ("0x{:02x}".format(mcp23017_address)
                             if mcp23017_address is not None else "none"),
    }
