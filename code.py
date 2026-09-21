"""CircuitPython entry point; composes the pendant and runs its event loop."""

import time

from src.config import load_config
from src.app import PendantApplication


def main():
    print()
    print("[boot] LOLIN S2 Mini CNC MPG Pendant")

    config = load_config()

    app = PendantApplication.from_config(config)
    print("[ready] pendant runtime started")

    while True:
        app.poll()
        time.sleep(0.01)


try:
    main()
except Exception as exc:
    print("[fatal]", repr(exc))
    while True:
        time.sleep(1)
