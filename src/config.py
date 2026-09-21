"""Configuration loader for CircuitPython ``settings.toml``."""

import os


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


def load_config():
    return {
        "wifi_ssid": _get("CIRCUITPY_WIFI_SSID"),
        "wifi_password": _get("CIRCUITPY_WIFI_PASSWORD"),
        "hostname": _get("MPG_HOSTNAME", "cda-lolin-s2-mpg"),
        "controller_mode": _get("MPG_CONTROLLER_MODE", "disabled").lower(),
        "controller_host": _get("MPG_CONTROLLER_HOST", ""),
        "controller_port": _get_int("MPG_CONTROLLER_PORT", 8080),
        "uart_tx_pin": _get("MPG_UART_TX_PIN", ""),
        "uart_rx_pin": _get("MPG_UART_RX_PIN", ""),
        "uart_baudrate": _get_int("MPG_UART_BAUDRATE", 115200),
        "base_increment": float(_get("MPG_BASE_INCREMENT", "0.001")),
        "jog_feed": float(_get("MPG_JOG_FEED", "500")),
        "status_interval": float(_get("MPG_STATUS_INTERVAL", "0.2")),
        "jobs_path": _get("MPG_JOBS_PATH", "/jobs"),
        "macros_path": _get("MPG_MACROS_PATH", "/macros"),
        "probe_z": _get("MPG_PROBE_Z", "G91 G38.2 Z-10 F100"),
        "safe_z": _get("MPG_SAFE_Z", "G53 G0 Z0"),
        "park": _get("MPG_PARK", "G53 G0 X0 Y0"),
    }
