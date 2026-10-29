"""Compact mathematical effects shared by the runtime and host previews."""

TOUCH_BITMAP_SIZE = 25
TOUCH_BITMAP_CENTER = TOUCH_BITMAP_SIZE // 2

# Palette indices are ordered from the widest ring inward. Zero remains the
# transparent background used by the retained DisplayIO bitmap.
TOUCH_OUTER = 1
TOUCH_MIDDLE = 2
TOUCH_INNER = 3
TOUCH_CORE = 4
# Hold a compact two-ring contact mark under the finger. The inner contour
# keeps the acknowledgment visible when the fingertip covers the center, while
# the 25px sprite stays clear of neighboring menu rows.
TOUCH_HOLD_PROGRESS = 0.34
TOUCH_HOLD_PULSE_PERIOD_S = 0.90
TOUCH_HOLD_PULSE_AMPLITUDE = 0.045


def touch_zone(x, y):
    """Return the 4bpp ring index for one pixel in the touch sprite."""
    dx = int(x) - TOUCH_BITMAP_CENTER
    dy = int(y) - TOUCH_BITMAP_CENTER
    radius2 = dx * dx + dy * dy
    if radius2 <= 2:
        return TOUCH_CORE
    if 9 <= radius2 <= 20:
        return TOUCH_INNER
    if 36 <= radius2 <= 56:
        return TOUCH_MIDDLE
    if 81 <= radius2 <= 110:
        return TOUCH_OUTER
    return 0


def touch_level(index, progress):
    """Brightness percentage for a touch ripple palette index."""
    progress = max(0.0, min(1.0, float(progress)))
    if index == TOUCH_CORE:
        # Let the one-pixel contact core disappear before the compact held
        # phase; otherwise the center point reads as a fixed cursor under the
        # two contour rings.
        return int(100 * max(0.0, 1.0 - progress / 0.30))
    if index == TOUCH_INNER:
        return int(78 * max(0.0, 1.0 - abs(progress - 0.12) / 0.42))
    if index == TOUCH_MIDDLE:
        return int(74 * max(0.0, 1.0 - abs(progress - 0.48) / 0.40))
    if index == TOUCH_OUTER:
        return int(64 * max(0.0, 1.0 - abs(progress - 0.82) / 0.30))
    return 0
