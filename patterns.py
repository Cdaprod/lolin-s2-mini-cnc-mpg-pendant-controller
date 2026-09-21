"""
Small pattern helper retained for compatibility with the existing
LOLIN S2 Mini CircuitPython experiments.

This module intentionally has no hardware dependencies.
"""

_PATTERNS = (
    "steady",
    "pulse",
    "blink",
)

_pattern_index = 0


def current_pattern():
    return _PATTERNS[_pattern_index]


def next_pattern():
    """Advance to the next pattern name and return it."""
    global _pattern_index
    _pattern_index = (_pattern_index + 1) % len(_PATTERNS)
    return current_pattern()


def pattern_output(pattern, phase=0.0):
    """
    Return normalized output 0.0..1.0 for a named pattern.

    `phase` should normally be 0.0..1.0.
    """
    phase = float(phase) % 1.0

    if pattern == "steady":
        return 1.0

    if pattern == "pulse":
        # Triangle wave without math dependency.
        return 1.0 - abs((phase * 2.0) - 1.0)

    if pattern == "blink":
        return 1.0 if phase < 0.5 else 0.0

    return 0.0
