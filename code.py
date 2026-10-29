"""CircuitPython entry point; composes the pendant and runs its event loop."""

import time
import sys

from src.config import load_config
from src.app import PendantApplication
from src.diagnostics import emit, is_runtime_reload


def main():
    print()
    print("[boot] XIAO ESP32-S3 CNC MPG Pendant")

    config = load_config()

    app = PendantApplication.from_config(config)
    print("[ready] pendant runtime started")

    while True:
        app.poll()
        time.sleep(0)


if __name__ == "__main__":
    try:
        main()
    except BaseException as exc:
        if is_runtime_reload(exc):
            emit("application_reload", type=type(exc).__name__)
            raise
        emit("application_exception", type=type(exc).__name__)
        printer = getattr(sys, "print_exception", None)
        if printer is not None:
            printer(exc)
        raise
