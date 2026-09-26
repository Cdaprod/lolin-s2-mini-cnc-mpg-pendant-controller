"""Design geometry and host-verifiable safe regions for the round instrument."""

import math


class RoundLayout:
    """Physical-pixel regions for the 240px GC9A01 and its bezel."""

    SIZE = 240
    CENTER = (120, 120)
    OUTER_RING_RADIUS = 111
    SAFE_RADIUS = 104
    MODAL = (25, 73, 190, 94)

    @classmethod
    def content_rows(cls):
        """Critical HOME regions, ordered by glance hierarchy."""
        return {
            "state": (72, 29, 96, 12),
            "axis_feedback": (46, 48, 68, 10),
            "step_feedback": (126, 48, 68, 10),
            "axis": (84, 59, 72, 30),
            "dro": (33, 89, 174, 30),
            "context": (70, 121, 100, 10),
            "increment": (76, 137, 88, 20),
            "motion": (44, 168, 152, 12),
            "connectivity": (67, 194, 106, 10),
        }

    @classmethod
    def region_within_safe_circle(cls, region):
        """Check every rectangle corner against the readable circle."""
        x, y, width, height = region
        cx, cy = cls.CENTER
        return all((px - cx) ** 2 + (py - cy) ** 2 <= cls.SAFE_RADIUS ** 2
                   for px in (x, x + width) for py in (y, y + height))

    @classmethod
    def safe_width(cls, y, margin=0):
        """Return available chord width at a physical display row."""
        offset = min(cls.SAFE_RADIUS, abs(int(y) - cls.CENTER[1]))
        half = int(math.sqrt(cls.SAFE_RADIUS ** 2 - offset ** 2))
        return max(0, 2 * half - 2 * int(margin))
