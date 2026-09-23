"""Independent board and display profiles; profiles never enable hardware."""

LOLIN_S2_MINI_V1 = "lolin_s2_mini_v1"
XIAO_ESP32S3 = "xiao_esp32s3"
SEEED_ROUND_240 = "seeed_round_240"

# Board profiles own resources.  Display wiring is deliberately absent here.
BOARD_PROFILES = {
    LOLIN_S2_MINI_V1: {
        "uart_tx_pin": "IO17", "uart_rx_pin": "IO18",
        "mpg_a_pin": "IO1", "mpg_b_pin": "IO2",
        "estop_observe_pin": "IO3",
        "button_pins": {
            "SELECT": "IO4", "BACK": "", "FN": "IO6", "CANCEL": "IO5",
        },
        "selector_backend": "mcp23017",
        "i2c_sda_pin": "IO33", "i2c_scl_pin": "IO35",
        "mcp23017_address": 0x20,
        "mcp23017_axis_bits": {
            "X": 0, "Y": 1, "Z": 2, "4": 3, "5": 4, "6": 5,
        },
        "mcp23017_multiplier_bits": {"X1": 6, "X10": 7, "X100": 8},
        "spi_sck_pin": "IO7", "spi_mosi_pin": "IO11",
        "spi_miso_pin": "IO9",
        "sd_sck_pin": "IO7", "sd_mosi_pin": "IO11",
        "sd_miso_pin": "IO9", "sd_cs_pin": "IO10",
        # Legacy proposed LCD binding retained for existing installations.
        "display_sck_pin": "IO7", "display_mosi_pin": "IO11",
        "display_cs_pin": "IO12", "display_dc_pin": "IO13",
        "display_reset_pin": "IO14",
    },
    XIAO_ESP32S3: {
        # Logical XIAO headers keep this profile useful across CircuitPython
        # board revisions; an attached peripheral supplies its own wiring.
        "uart_tx_pin": "TX", "uart_rx_pin": "RX",
        "spi_sck_pin": "D8", "spi_mosi_pin": "D10",
        "spi_miso_pin": "D9",
    },
}

# Display profiles own controller/capabilities and their convenient default
# binding.  These defaults can always be overridden in settings.toml.
DISPLAY_PROFILES = {
    SEEED_ROUND_240: {
        "display_driver": "gc9a01",
        "display_renderer": "round",
        "display_width": 240, "display_height": 240,
        "display_rotation": 0,
        "display_sck_pin": "D8", "display_mosi_pin": "D10",
        "display_cs_pin": "D1", "display_dc_pin": "D3",
        "display_reset_pin": "", "display_backlight_pin": "D6",
        "display_touch_sda_pin": "D4", "display_touch_scl_pin": "D5",
    },
}

# Compatibility alias for callers that enumerate the original mapping.
PROFILES = BOARD_PROFILES


def _merge_mapping(current, proposed):
    result = dict(current or {})
    for key, value in proposed.items():
        if not result.get(key):
            result[key] = value
    return result


def _apply(result, profile, kind):
    if not profile:
        return result
    profiles = BOARD_PROFILES if kind == "board" else DISPLAY_PROFILES
    if profile not in profiles:
        raise ValueError("unknown {} profile: {}".format(kind, profile))
    for key, value in profiles[profile].items():
        if isinstance(value, dict):
            result[key] = _merge_mapping(result.get(key), value)
        elif result.get(key) in (None, "", 0):
            result[key] = value
    return result


def apply_hardware_profile(config):
    """Return a copy with blank assignments filled by independent profiles."""
    result = dict(config)
    # hardware_profile remains a supported name for existing installations.
    board_profile = result.get("board_profile") or result.get(
        "hardware_profile", ""
    )
    result = _apply(result, board_profile, "board")
    result = _apply(result, result.get("display_profile", ""), "display")
    validate_profile_binding(result)
    return result


def validate_profile_binding(config):
    """Fail early when an enabled display lacks required bus/control pins."""
    if not config.get("display_enabled") or config.get("display_use_board_display"):
        return
    if config.get("display_driver") == "gc9a01":
        required = ("display_sck_pin", "display_mosi_pin",
                    "display_cs_pin", "display_dc_pin")
        missing = [name for name in required if not config.get(name)]
        if missing:
            raise ValueError("display profile missing resources: " +
                             ", ".join(missing))
