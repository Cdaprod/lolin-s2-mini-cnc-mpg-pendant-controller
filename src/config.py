"""Configuration loader for CircuitPython ``settings.toml``."""

import os

from src.hardware_profiles import apply_hardware_profile


def _get(name, default=""):
    value = os.getenv(name)
    if value is None:
        return default
    return value


def _get_int(name, default):
    value = _get(name, str(default))
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _get_float(name, default):
    try:
        return float(_get(name, str(default)))
    except (TypeError, ValueError):
        return float(default)


def _get_bool(name, default=False):
    value = str(_get(name, "true" if default else "false")).lower()
    return value in ("1", "true", "yes", "on")


def _pin_map(prefix, names):
    return dict((name, _get(prefix + name, "")) for name in names)


def load_config():
    config = {
        "hardware_profile": _get("MPG_HARDWARE_PROFILE", ""),
        "board_profile": _get("MPG_BOARD_PROFILE", ""),
        "display_profile": _get("MPG_DISPLAY_PROFILE", ""),
        "wifi_ssid": _get("CIRCUITPY_WIFI_SSID"),
        "wifi_password": _get("CIRCUITPY_WIFI_PASSWORD"),
        "hostname": _get("MPG_HOSTNAME", "cda-lolin-s2-mpg"),
        "controller_mode": _get("MPG_CONTROLLER_MODE", "disabled").lower(),
        "controller_host": _get("MPG_CONTROLLER_HOST", ""),
        "controller_port": _get_int("MPG_CONTROLLER_PORT", 8080),
        "uart_tx_pin": _get("MPG_UART_TX_PIN", ""),
        "uart_rx_pin": _get("MPG_UART_RX_PIN", ""),
        "uart_baudrate": _get_int("MPG_UART_BAUDRATE", 115200),
        "base_increment": _get_float("MPG_BASE_INCREMENT", 0.001),
        "jog_feed": _get_float("MPG_JOG_FEED", 500),
        "status_interval": _get_float("MPG_STATUS_INTERVAL", 0.2),
        "jobs_path": _get("MPG_JOBS_PATH", "/jobs"),
        "macros_path": _get("MPG_MACROS_PATH", "/macros"),
        "probe_z": _get("MPG_PROBE_Z", "G91 G38.2 Z-10 F100"),
        "safe_z": _get("MPG_SAFE_Z", "G53 G0 Z0"),
        "park": _get("MPG_PARK", "G53 G0 X0 Y0"),
        "inputs_enabled": _get_bool("MPG_INPUTS_ENABLED"),
        "mpg_active_low": _get_bool("MPG_ENCODER_ACTIVE_LOW", False),
        "mpg_use_rotaryio": _get_bool("MPG_USE_ROTARYIO", True),
        "selector_active_low": _get_bool("MPG_SELECTOR_ACTIVE_LOW", True),
        "button_active_low": _get_bool("MPG_BUTTON_ACTIVE_LOW", True),
        "mpg_a_pin": _get("MPG_PIN_A", ""),
        "mpg_b_pin": _get("MPG_PIN_B", ""),
        "mpg_counts_per_detent": _get_int("MPG_COUNTS_PER_DETENT", 4),
        "mpg_direction": _get_int("MPG_DIRECTION", 1),
        "axis_map": dict((name, _get("MPG_AXIS_MAP_" + name, logical))
                         for name, logical in (("X", "X"), ("Y", "Y"),
                                               ("Z", "Z"), ("4", "A"),
                                               ("5", "B"), ("6", "C"))),
        "axis_pins": _pin_map("MPG_PIN_AXIS_", ("X", "Y", "Z", "4", "5", "6")),
        "multiplier_pins": _pin_map("MPG_PIN_MULTIPLIER_", ("X1", "X10", "X100")),
        "button_pins": _pin_map("MPG_PIN_BUTTON_", (
            "SELECT", "BACK", "FN", "CANCEL"
        )),
        "estop_observe_pin": _get("MPG_PIN_ESTOP_OBSERVE", ""),
        "estop_active_low": _get_bool("MPG_ESTOP_ACTIVE_LOW", True),
        "deadman_pin": _get("MPG_PIN_DEADMAN", ""),
        "deadman_active_low": _get_bool("MPG_DEADMAN_ACTIVE_LOW", True),
        "button_debounce": _get_float("MPG_BUTTON_DEBOUNCE", 0.03),
        "button_long_press": _get_float("MPG_BUTTON_LONG_PRESS", 0.8),
        "display_enabled": _get_bool("MPG_DISPLAY_ENABLED"),
        "display_use_board_display": _get_bool("MPG_DISPLAY_USE_BOARD_DISPLAY"),
        "display_width": _get_int("MPG_DISPLAY_WIDTH", 0),
        "display_height": _get_int("MPG_DISPLAY_HEIGHT", 0),
        "display_rotation": _get_int("MPG_DISPLAY_ROTATION", 0),
        "display_driver": _get("MPG_DISPLAY_DRIVER", "").lower(),
        "display_renderer": _get("MPG_DISPLAY_RENDERER", "").lower(),
        "round_ui_bootstrap": _get_bool("MPG_ROUND_UI_BOOTSTRAP"),
        "sd_enabled": _get_bool("MPG_SD_ENABLED"),
        "sd_sck_pin": _get("MPG_SD_SCK_PIN", ""),
        "sd_mosi_pin": _get("MPG_SD_MOSI_PIN", ""),
        "sd_miso_pin": _get("MPG_SD_MISO_PIN", ""),
        "sd_cs_pin": _get("MPG_SD_CS_PIN", ""),
        "sd_mount_path": _get("MPG_SD_MOUNT_PATH", "/sd"),
        "indicator_enabled": _get_bool("MPG_INDICATOR_ENABLED"),
        "indicator_verified": _get_bool("MPG_INDICATOR_ELECTRICALLY_VERIFIED"),
        "indicator_pin": _get("MPG_INDICATOR_PIN", ""),
        "indicator_active_high": _get_bool("MPG_INDICATOR_ACTIVE_HIGH", True),
        "selector_backend": _get("MPG_SELECTOR_BACKEND", "").lower(),
        "selector_interface_verified": _get_bool(
            "MPG_SELECTOR_INTERFACE_VERIFIED"
        ),
        "i2c_sda_pin": _get("MPG_I2C_SDA_PIN", ""),
        "i2c_scl_pin": _get("MPG_I2C_SCL_PIN", ""),
        "mcp23017_address": _get_int("MPG_MCP23017_ADDRESS", 0x20),
        "mcp23017_axis_bits": {
            "X": 0, "Y": 1, "Z": 2, "4": 3, "5": 4, "6": 5,
        },
        "mcp23017_multiplier_bits": {"X1": 6, "X10": 7, "X100": 8},
        "spi_sck_pin": _get("MPG_SPI_SCK_PIN", ""),
        "spi_mosi_pin": _get("MPG_SPI_MOSI_PIN", ""),
        "spi_miso_pin": _get("MPG_SPI_MISO_PIN", ""),
        "display_sck_pin": _get("MPG_DISPLAY_SCK_PIN", ""),
        "display_mosi_pin": _get("MPG_DISPLAY_MOSI_PIN", ""),
        "display_cs_pin": _get("MPG_DISPLAY_CS_PIN", ""),
        "display_dc_pin": _get("MPG_DISPLAY_DC_PIN", ""),
        "display_reset_pin": _get("MPG_DISPLAY_RESET_PIN", ""),
        "display_backlight_pin": _get("MPG_DISPLAY_BACKLIGHT_PIN", ""),
        "display_touch_sda_pin": _get("MPG_DISPLAY_TOUCH_SDA_PIN", ""),
        "display_touch_scl_pin": _get("MPG_DISPLAY_TOUCH_SCL_PIN", ""),
    }
    configured = apply_hardware_profile(config)
    if not configured.get("selector_backend"):
        configured["selector_backend"] = "direct"
    return configured
