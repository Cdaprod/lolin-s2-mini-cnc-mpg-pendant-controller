"""Read-only CircuitPython USB capability diagnostics.

This module NEVER changes USB roles, enables VBUS, enumerates devices,
opens a serial port, or transmits machine commands.
"""
import sys

MODULES = ("usb_host", "usb", "usb_cdc", "microcontroller", "board")

def inspect_module(name, importer=__import__):
    """Return serializable module capability information without side effects."""
    try:
        module = importer(name)
    except (ImportError, NotImplementedError) as exc:
        return {"module": name, "available": False, "error": type(exc).__name__}
    return {
        "module": name,
        "available": True,
        "exports": sorted(item for item in dir(module) if not item.startswith("_")),
    }

def collect(importer=__import__):
    return {
        "runtime": sys.implementation.name,
        "version": sys.version.splitlines()[0],
        "modules": [inspect_module(name, importer) for name in MODULES],
        "host_verified": False,
        "ch34x_verified": False,
        "vbus_verified": False,
        "motion_enabled": False,
    }

def probe():
    report = collect()
    for key in ("runtime", "version", "host_verified", "ch34x_verified",
                "vbus_verified", "motion_enabled"):
        print("{}: {}".format(key, report[key]))
    for entry in report["modules"]:
        print("{}: {}".format(entry["module"], "available" if entry["available"] else "unavailable"))
        if entry["available"]:
            print("  exports:", ", ".join(entry["exports"]))
        else:
            print("  error:", entry["error"])
    print("Diagnostic only; no USB enumeration, VBUS switching or GRBL commands.")
    return report

if __name__ == "__main__":
    probe()
