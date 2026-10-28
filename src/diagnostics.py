"""Compact structured diagnostics for the passive USB CDC monitor."""


def _token(value):
    value = str(value)
    # Keep each key/value pair machine-readable and bounded on CircuitPython.
    return value.replace("%", "_25").replace("=", "_").replace(" ", "_")[:80]


def emit(event, **fields):
    """Write one low-allocation event line to CircuitPython's USB console."""
    parts = ["event=" + _token(event)]
    for key in sorted(fields):
        value = fields[key]
        if value is not None:
            parts.append("{}={}".format(_token(key), _token(value)))
    print("[event] " + " ".join(parts))
