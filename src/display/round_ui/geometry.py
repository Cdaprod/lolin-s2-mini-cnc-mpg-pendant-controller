"""Small precomputed radial-layout helpers."""

import math


class RoundLayout:
    """Reusable safe-area metrics for a 240px circular display."""

    SIZE = 240
    CENTER = (120, 120)
    OUTER_RING_RADIUS = 111
    SAFE_RADIUS = 101
    MARGIN = 8
    BASELINE = 18
    HEADER = (42, 18, 156, 22)
    CONTENT = (25, 48, 190, 112)
    FOOTER = (35, 166, 170, 28)
    MODAL = (25, 82, 190, 72)

    @classmethod
    def safe_width(cls, y, margin=0):
        """Chord width inside the safe circle at display coordinate ``y``."""
        offset = min(cls.SAFE_RADIUS, abs(int(y) - cls.CENTER[1]))
        half = int(math.sqrt(cls.SAFE_RADIUS ** 2 - offset ** 2))
        return max(0, 2 * half - 2 * (cls.MARGIN + int(margin)))


def radial_points(count, radius, center=(120, 120), start_degrees=-90):
    """Return integer points evenly distributed around a circle."""
    points = []
    for index in range(count):
        angle = math.radians(start_degrees + (360.0 * index / count))
        points.append((int(center[0] + math.cos(angle) * radius),
                       int(center[1] + math.sin(angle) * radius)))
    return tuple(points)
