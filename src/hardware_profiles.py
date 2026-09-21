"""Named reference pin profiles; profiles assign pins but never enable hardware."""

LOLIN_S2_MINI_V1 = "lolin_s2_mini_v1"

# CircuitPython board aliases are IO<n>. LCD signals are proposed routing only:
# no LCD controller, module, voltage, backlight, or physical wiring is verified.
PROFILES = {
    LOLIN_S2_MINI_V1: {
        "uart_tx_pin": "IO17",
        "uart_rx_pin": "IO18",
        "mpg_a_pin": "IO1",
        "mpg_b_pin": "IO2",
        "estop_observe_pin": "IO3",
        "button_pins": {
            "SELECT": "IO4", "BACK": "", "FN": "IO6", "CANCEL": "IO5",
        },
        "selector_backend": "mcp23017",
        "i2c_sda_pin": "IO33",
        "i2c_scl_pin": "IO35",
        "mcp23017_address": 0x20,
        "mcp23017_axis_bits": {
            "X": 0, "Y": 1, "Z": 2, "4": 3, "5": 4, "6": 5,
        },
        "mcp23017_multiplier_bits": {"X1": 6, "X10": 7, "X100": 8},
        "spi_sck_pin": "IO7",
        "spi_mosi_pin": "IO11",
        "spi_miso_pin": "IO9",
        "sd_sck_pin": "IO7",
        "sd_mosi_pin": "IO11",
        "sd_miso_pin": "IO9",
        "sd_cs_pin": "IO10",
        "display_sck_pin": "IO7",
        "display_mosi_pin": "IO11",
        "display_cs_pin": "IO12",
        "display_dc_pin": "IO13",
        "display_reset_pin": "IO14",
    },
}


def _merge_mapping(current, proposed):
    result = dict(current or {})
    for key, value in proposed.items():
        if not result.get(key):
            result[key] = value
    return result


def apply_hardware_profile(config):
    """Return a copy with blank assignments filled by the selected profile."""
    name = config.get("hardware_profile", "")
    if not name:
        return config
    if name not in PROFILES:
        raise ValueError("unknown hardware profile: " + name)
    result = dict(config)
    for key, value in PROFILES[name].items():
        if isinstance(value, dict):
            result[key] = _merge_mapping(result.get(key), value)
        elif result.get(key) in (None, "", 0):
            result[key] = value
    return result
