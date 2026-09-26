"""GC9A01 display construction and the concrete DisplayIO round scene."""

import math

from . import theme
from .geometry import RoundLayout
from .renderer import RoundRenderer

_BACKLIGHT_OUTPUT = None


def _pin(board, name):
    if not name or not hasattr(board, name):
        return None
    return getattr(board, name)


def build_gc9a01(config):
    """Construct a GC9A01 from profile-selected pins."""
    global _BACKLIGHT_OUTPUT
    import board
    import busio
    import displayio
    import adafruit_gc9a01a
    displayio.release_displays()
    spi = busio.SPI(_pin(board, config["display_sck_pin"]),
                    MOSI=_pin(board, config["display_mosi_pin"]))
    try:
        from fourwire import FourWire
    except ImportError:
        FourWire = displayio.FourWire
    bus = FourWire(spi, command=_pin(board, config["display_dc_pin"]),
                   chip_select=_pin(board, config["display_cs_pin"]),
                   reset=_pin(board, config.get("display_reset_pin")))
    display = adafruit_gc9a01a.GC9A01A(
        bus, width=config.get("display_width", 240),
        height=config.get("display_height", 240),
        rotation=config.get("display_rotation", 0)
    )
    backlight = _pin(board, config.get("display_backlight_pin"))
    if backlight is not None:
        import digitalio
        output = digitalio.DigitalInOut(backlight)
        output.switch_to_output(value=True)
        _BACKLIGHT_OUTPUT = output
    return display


def _line(displayio, terminalio, width, height, x, y, color=theme.TEXT,
          centered=False):
    from src.display.displayio_backend import _DisplayIOTextLine
    line = _DisplayIOTextLine(width, height, terminalio.FONT, displayio, color,
                              centered)
    line.node.x, line.node.y = x, y
    return line


class _RingNode:
    def __init__(self, palette):
        self.palette = palette
        self.activity_value = 0
        self.armed = False
        self.phase = 0

    @property
    def color(self):
        return self.palette[1]

    @color.setter
    def color(self, value):
        for index in (1, 2, 3):
            self.palette[index] = value

    def set_activity(self, value, armed):
        value, armed = int(value), bool(armed)
        changed = value != self.activity_value or armed != self.armed
        if not changed:
            return False
        self.activity_value, self.armed = value, armed
        if value:
            self.phase = (self.phase + (1 if value > 0 else -1)) % 3
        base = theme.GREEN if armed else theme.MUTED
        accent = theme.CYAN if value > 0 else theme.YELLOW
        for index in (1, 2, 3):
            self.palette[index] = base
        if value:
            self.palette[1 + self.phase] = accent
        return True


def displayio_scene(display):
    """Create the persistent scene once; renderer updates its properties."""
    import displayio
    import terminalio
    root = displayio.Group()
    bitmap = displayio.Bitmap(240, 240, 4)
    palette = displayio.Palette(4)
    palette[0] = theme.BACKGROUND
    palette[1] = palette[2] = palette[3] = theme.MUTED
    center = RoundLayout.CENTER[0]
    for y in range(240):
        for x in range(240):
            radius2 = (x - center) ** 2 + (y - center) ** 2
            if ((RoundLayout.OUTER_RING_RADIUS - 3) ** 2 <= radius2 <=
                    (RoundLayout.OUTER_RING_RADIUS + 3) ** 2):
                angle = int((math.atan2(y - center, x - center) + math.pi) *
                            12 / (2 * math.pi))
                bitmap[x, y] = 1 + angle % 3
    root.append(displayio.TileGrid(bitmap, pixel_shader=palette))
    content = displayio.Group()
    root.append(content)
    rows = RoundLayout.content_rows()
    def layout_line(name, color=theme.TEXT):
        x, y, width, height = rows[name]
        return _line(displayio, terminalio, width, height, x, y, color, True)
    title = layout_line("title", theme.CYAN)
    axis = layout_line("axis", theme.CYAN)
    value = layout_line("value")
    secondary = layout_line("secondary", theme.MUTED)
    activity = layout_line("activity", theme.YELLOW)
    multiplier = layout_line("multiplier", theme.CYAN)
    indicators = layout_line("indicators", theme.GREEN)
    menu_x, menu_y, menu_width, _ = RoundLayout.CONTENT
    menu = [_line(displayio, terminalio, menu_width, 12, menu_x,
                  menu_y + index * RoundLayout.BASELINE)
            for index in range(6)]
    hint_x, hint_y, hint_width, hint_height = rows["menu_hint"]
    tabs = [_line(displayio, terminalio, hint_width, hint_height,
                  hint_x, hint_y, theme.CYAN, True)]
    for line in [title, axis, value, secondary, activity, multiplier,
                 indicators] + tabs:
        content.append(line.node)
    menu_group = displayio.Group()
    root.append(menu_group)
    for line in menu:
        menu_group.append(line.node)
    overlay_group = displayio.Group()
    modal_x, modal_y, modal_width, modal_height = RoundLayout.MODAL
    overlay_bitmap = displayio.Bitmap(modal_width, modal_height, 1)
    overlay_palette = displayio.Palette(1)
    overlay_palette[0] = theme.PANEL
    overlay_group.append(displayio.TileGrid(
        overlay_bitmap, pixel_shader=overlay_palette, x=modal_x, y=modal_y
    ))
    overlay_title = _line(displayio, terminalio, 160, 14, 40, 96, theme.YELLOW)
    overlay_detail = _line(displayio, terminalio, 160, 14, 40, 120)
    overlay_group.append(overlay_title.node)
    overlay_group.append(overlay_detail.node)
    root.append(overlay_group)
    return {"root": root, "ring": _RingNode(palette), "title": title,
            "axis": axis, "value": value, "secondary": secondary,
            "activity": activity,
            "multiplier": multiplier, "indicators": indicators, "tabs": tabs,
            "menu": menu, "home_group": content, "menu_group": menu_group,
            "overlay_group": overlay_group,
            "overlay_title": overlay_title, "overlay_detail": overlay_detail}


def from_config(config):
    if config.get("display_use_board_display"):
        import board
        display = board.DISPLAY
    elif config.get("display_driver") == "gc9a01":
        display = build_gc9a01(config)
    else:
        raise ValueError("round renderer requires a supported display driver")
    return RoundRenderer(display, displayio_scene)
