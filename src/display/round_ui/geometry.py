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
    HEADER = (45, 34, 150, 22)
    CONTENT = (25, 52, 190, 108)
    FOOTER = (35, 166, 170, 28)
    MODAL = (28, 82, 184, 72)

    @classmethod
    def centered_region(cls, y, height, maximum_width, margin=0):
        """Return a centered rectangle bounded by the safe circle chord."""
        width = min(int(maximum_width), cls.safe_width(y, margin),
                    cls.safe_width(y + height, margin))
        return ((cls.SIZE - width) // 2, int(y), width, int(height))

    @classmethod
    def content_rows(cls):
        """Return named text regions derived from the three layout zones."""
        header_y = cls.HEADER[1] + 4
        content_y = cls.CONTENT[1] + cls.MARGIN
        footer_y = cls.FOOTER[1] + 4
        return {
            "title": cls.centered_region(header_y, 12, cls.HEADER[2]),
            "axis": cls.centered_region(content_y, 12, 30),
            "value": cls.centered_region(content_y + cls.BASELINE + 4, 18, 150),
            "secondary": cls.centered_region(content_y + 3 * cls.BASELINE, 10, 190),
            "multiplier": cls.centered_region(content_y + 5 * cls.BASELINE, 12, 170),
            "indicators": cls.centered_region(footer_y, 10, cls.FOOTER[2]),
        }

    @classmethod
    def region_within_safe_circle(cls, region):
        """Check every rectangle corner against the circular safe radius."""
        x, y, width, height = region
        cx, cy = cls.CENTER
        return all((px - cx) ** 2 + (py - cy) ** 2 <= cls.SAFE_RADIUS ** 2
                   for px in (x, x + width) for py in (y, y + height))

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
