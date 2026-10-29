"""Compact mathematical effects shared by the runtime and host previews."""

TOUCH_BITMAP_SIZE = 25
TOUCH_BITMAP_CENTER = TOUCH_BITMAP_SIZE // 2

# Each radial contour has a dim edge index and a brighter core index. The
# paired colors soften the small 25px sprite without alpha blending or runtime
# bitmap writes. Index zero remains transparent.
TOUCH_OUTER_EDGE = 1
TOUCH_OUTER = 2
TOUCH_MIDDLE_EDGE = 3
TOUCH_MIDDLE = 4
TOUCH_INNER_EDGE = 5
TOUCH_INNER = 6
TOUCH_CORE_EDGE = 7
TOUCH_CORE = 8
TOUCH_PALETTE_SIZE = 9
# Hold a compact two-ring contact mark under the finger. The inner contour
# keeps the acknowledgment visible when the fingertip covers the center, while
# the 25px sprite stays clear of neighboring menu rows.
TOUCH_HOLD_PROGRESS = 0.34
TOUCH_HOLD_PULSE_PERIOD_S = 0.90
TOUCH_HOLD_PULSE_AMPLITUDE = 0.045


def touch_zone(x, y):
    """Return a paired-edge 4bpp contour index for one touch-sprite pixel."""
    dx = int(x) - TOUCH_BITMAP_CENTER
    dy = int(y) - TOUCH_BITMAP_CENTER
    radius2 = dx * dx + dy * dy
    if radius2 <= 2:
        return TOUCH_CORE
    if radius2 <= 4:
        return TOUCH_CORE_EDGE
    if 9 <= radius2 <= 20:
        return TOUCH_INNER
    if (5 <= radius2 <= 8) or (21 <= radius2 <= 28):
        return TOUCH_INNER_EDGE
    if 36 <= radius2 <= 56:
        return TOUCH_MIDDLE
    if (29 <= radius2 <= 35) or (57 <= radius2 <= 68):
        return TOUCH_MIDDLE_EDGE
    if 81 <= radius2 <= 110:
        return TOUCH_OUTER
    if (70 <= radius2 <= 80) or (111 <= radius2 <= 132):
        return TOUCH_OUTER_EDGE
    return 0


def touch_level(index, progress):
    """Brightness percentage for a touch ripple palette index."""
    progress = max(0.0, min(1.0, float(progress)))
    if index in (TOUCH_CORE, TOUCH_CORE_EDGE):
        # Let the one-pixel contact core disappear before the compact held
        # phase; otherwise the center point reads as a fixed cursor under the
        # two contour rings.
        level = int(100 * max(0.0, 1.0 - progress / 0.30))
    elif index in (TOUCH_INNER, TOUCH_INNER_EDGE):
        level = int(94 * max(0.0, 1.0 - abs(progress - 0.12) / 0.42))
    elif index in (TOUCH_MIDDLE, TOUCH_MIDDLE_EDGE):
        level = int(90 * max(0.0, 1.0 - abs(progress - 0.48) / 0.40))
    elif index in (TOUCH_OUTER, TOUCH_OUTER_EDGE):
        level = int(78 * max(0.0, 1.0 - abs(progress - 0.82) / 0.30))
    else:
        return 0
    if index in (TOUCH_CORE_EDGE, TOUCH_INNER_EDGE,
                 TOUCH_MIDDLE_EDGE, TOUCH_OUTER_EDGE):
        return level * 34 // 100
    return level
