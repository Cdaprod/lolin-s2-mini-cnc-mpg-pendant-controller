"""Non-invasive CircuitPython USB API capability probe.

Copy to CIRCUITPY and execute from REPL using:
    exec(open("/tools/probe_usb_capabilities.py").read())
No USB role changes, VBUS switching, or motor commands occur.
"""
import sys

MODULES = ("usb_host", "usb", "usb_cdc", "microcontroller", "board")

def probe():
    print("runtime:", sys.implementation.name)
    print("version:", sys.version)
    for name in MODULES:
        try:
            module = __import__(name)
            print(name, "available", tuple(
                item for item in dir(module)
                if not item.startswith("_")
            ))
        except (ImportError, NotImplementedError) as exc:
            print(name, "unavailable", str(exc))
    print("No USB enumeration or GRBL motion attempted.")

if __name__ == "__main__":
    probe()
