"""Configuration loader for CircuitPython settings.toml."""

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
    ssid = _get("CIRCUITPY_WIFI_SSID")
    password = _get("CIRCUITPY_WIFI_PASSWORD")

    if not ssid:
        raise RuntimeError(
            "CIRCUITPY_WIFI_SSID is missing. "
            "Copy settings.toml.example to settings.toml."
        )

    return {
        "wifi_ssid": ssid,
        "wifi_password": password,
        "hostname": _get("MPG_HOSTNAME", "cda-lolin-s2-mpg"),
        "controller_mode": _get("MPG_CONTROLLER_MODE", "disabled").lower(),
        "controller_host": _get("MPG_CONTROLLER_HOST", ""),
        "controller_port": _get_int("MPG_CONTROLLER_PORT", 8080),
    }
