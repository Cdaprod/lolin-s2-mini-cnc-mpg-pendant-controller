"""Compact mathematical effects shared by the runtime and host previews."""

TOUCH_BITMAP_SIZE = 35
TOUCH_BITMAP_CENTER = TOUCH_BITMAP_SIZE // 2

# Palette indices are ordered from the widest ring inward. Zero remains the
# transparent background used by the retained DisplayIO bitmap.
TOUCH_OUTER = 1
TOUCH_MIDDLE = 2
TOUCH_INNER = 3
TOUCH_CORE = 4


def touch_zone(x, y):
    """Return the 4bpp ring index for one pixel in the touch sprite."""
    dx = int(x) - TOUCH_BITMAP_CENTER
    dy = int(y) - TOUCH_BITMAP_CENTER
    radius2 = dx * dx + dy * dy
    if radius2 <= 2:
        return TOUCH_CORE
    if 16 <= radius2 <= 25:
        return TOUCH_INNER
    if 81 <= radius2 <= 100:
        return TOUCH_MIDDLE
    if 196 <= radius2 <= 225:
        return TOUCH_OUTER
    return 0


def touch_level(index, progress):
    """Brightness percentage for a touch ripple palette index."""
    progress = max(0.0, min(1.0, float(progress)))
    if index == TOUCH_CORE:
        return int(100 * max(0.0, 1.0 - progress / 0.34))
    if index == TOUCH_INNER:
        return int(96 * max(0.0, 1.0 - abs(progress - 0.08) / 0.34))
    if index == TOUCH_MIDDLE:
        return 30 + int(70 * max(
            0.0, 1.0 - abs(progress - 0.42) / 0.43))
    if index == TOUCH_OUTER:
        return 38 + int(62 * max(
            0.0, 1.0 - abs(progress - 0.72) / 0.72))
    return 0
