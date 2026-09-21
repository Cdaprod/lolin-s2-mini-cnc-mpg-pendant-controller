"""
LOLIN S2 Mini CNC MPG Pendant Controller
CircuitPython entry point.
"""

import time

from src.config import load_config
from src.network import connect_wifi
from src.controller import Controller


def main():
    print()
    print("[boot] LOLIN S2 Mini CNC MPG Pendant")

    config = load_config()

    network = connect_wifi(
        ssid=config["wifi_ssid"],
        password=config["wifi_password"],
        hostname=config["hostname"],
    )

    controller = Controller(
        mode=config["controller_mode"],
        host=config["controller_host"],
        port=config["controller_port"],
        network=network,
    )

    controller.begin()

    print("[ready] pendant runtime started")

    while True:
        # Future:
        # - scan MPG inputs
        # - update display/pattern
        # - dispatch safe pendant actions
        # - maintain controller connection
        controller.poll()
        time.sleep(0.05)


try:
    main()
except Exception as exc:
    print("[fatal]", repr(exc))
    while True:
        time.sleep(1)
