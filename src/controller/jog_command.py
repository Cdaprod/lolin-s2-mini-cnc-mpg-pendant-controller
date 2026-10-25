"""Strict, bounded per-detent GRBL 1.1 jog command builder.

This module only constructs commands. CNC transmission requires an independently
verified machine-side ESP-NOW jog lease and watchdog; never bypass admission.
"""
import math

AXES = ("X", "Y", "Z", "A", "B", "C")
MAX_DISTANCE_MM = 1.0
MAX_FEED_MM_MIN = 1000.0
MIN_DISTANCE_MM = 0.000001


def build_jog(axis, distance_mm, feed_mm_min):
    axis = str(axis).upper()
    if axis not in AXES:
        raise ValueError("invalid jog axis")
    if not isinstance(distance_mm, (float, int)):
        raise ValueError("jog distance is not numeric")
    if not isinstance(feed_mm_min, (float, int)):
        raise ValueError("jog feed is not numeric")
    distance = float(distance_mm)
    feed = float(feed_mm_min)
    if (not math.isfinite(distance) or
            abs(distance) < MIN_DISTANCE_MM or
            abs(distance) > MAX_DISTANCE_MM):
        raise ValueError("jog distance outside allowed increment")
    if not math.isfinite(feed) or feed <= 0 or feed > MAX_FEED_MM_MIN:
        raise ValueError("jog feed outside allowed range")
    # All arguments are validated numeric scalars; no arbitrary G-code allowed.
    command = "$J=G91 G21 {}{:.6f} F{:.3f}\n".format(axis, distance, feed)
    return command.encode("ascii")
