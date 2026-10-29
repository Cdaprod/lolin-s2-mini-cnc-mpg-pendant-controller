"""Compact structured diagnostics for the passive USB CDC monitor."""


def _token(value):
    value = str(value)
    # Keep each key/value pair machine-readable and bounded on CircuitPython.
    return value.replace("%", "_25").replace("=", "_").replace(" ", "_")[:80]


def is_runtime_reload(exc):
    """Return whether CircuitPython raised its normal VM-reload signal.

    ReloadException is a CircuitPython builtin, but is intentionally absent
    from CPython. Name-checking keeps the host test surface importable while
    distinguishing expected soft reloads from application failures.
    """
    return type(exc).__name__ == "ReloadException"


def _enum_token(value):
    """Format CircuitPython enum values compactly without assuming an API."""
    name = getattr(value, "name", None)
    if name:
        return str(name)
    return str(value).rsplit(".", 1)[-1]


def startup_context_fields(supervisor_module=None,
                           microcontroller_module=None):
    """Return non-secret reset/reload evidence when the runtime exposes it."""
    fields = {}
    runtime = getattr(supervisor_module, "runtime", None)
    if runtime is not None:
        for attribute, key in (("run_reason", "run_reason"),
                               ("safe_mode_reason", "safe_mode_reason")):
            try:
                value = getattr(runtime, attribute)
            except (AttributeError, NotImplementedError, RuntimeError):
                continue
            if value is not None:
                fields[key] = _enum_token(value)
        try:
            fields["serial_connected"] = bool(runtime.serial_connected)
        except (AttributeError, NotImplementedError, RuntimeError):
            pass

    cpu = getattr(microcontroller_module, "cpu", None)
    if cpu is not None:
        try:
            frequency = cpu.frequency
        except (AttributeError, NotImplementedError, RuntimeError):
            frequency = None
        if frequency is not None:
            fields["cpu_frequency_hz"] = int(frequency)
        try:
            value = cpu.reset_reason
        except (AttributeError, NotImplementedError, RuntimeError):
            value = None
        if value is not None:
            fields["reset_reason"] = _enum_token(value)
    return fields


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


def loop_timing_fields(loop_count, poll_duration_ms, window_ms,
                       profiled_phase_ms):
    """Summarize observed poll rate and execution time using integer fields."""
    count = max(0, int(loop_count))
    window = max(0, int(window_ms))
    duration_us = max(0, int(float(poll_duration_ms) * 1000 + 0.5))
    profiled_us = max(0, int(profiled_phase_ms)) * 1000
    if count == 0 or window == 0:
        return {"loop_hz": 0, "poll_avg_us": 0,
                "unprofiled_avg_us": 0, "loop_window_ms": window}
    return {
        "loop_hz": int((count * 1000 + window // 2) // window),
        "poll_avg_us": int((duration_us + count // 2) // count),
        "unprofiled_avg_us": int((max(0, duration_us - profiled_us) +
                                   count // 2) // count),
        "loop_window_ms": window,
    }
