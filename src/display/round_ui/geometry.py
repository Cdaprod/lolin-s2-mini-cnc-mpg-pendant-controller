"""Small precomputed radial-layout helpers."""

import math


def radial_points(count, radius, center=(120, 120), start_degrees=-90):
    """Return integer points evenly distributed around a circle."""
    points = []
    for index in range(count):
        angle = math.radians(start_degrees + (360.0 * index / count))
        points.append((int(center[0] + math.cos(angle) * radius),
                       int(center[1] + math.sin(angle) * radius)))
    return tuple(points)
