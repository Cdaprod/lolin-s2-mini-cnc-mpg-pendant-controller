"""GC9A01 display construction and the concrete DisplayIO round scene."""

from . import theme
from .geometry import radial_points, RoundLayout
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


def _line(displayio, terminalio, width, height, x, y, color=theme.TEXT):
    from src.display.displayio_backend import _DisplayIOTextLine
    line = _DisplayIOTextLine(width, height, terminalio.FONT, displayio, color)
    line.node.x, line.node.y = x, y
    return line


class _RingNode:
    def __init__(self, palette):
        self.palette = palette

    @property
    def color(self):
        return self.palette[1]

    @color.setter
    def color(self, value):
        self.palette[1] = value


def displayio_scene(display):
    """Create the persistent scene once; renderer updates its properties."""
    import displayio
    import terminalio
    root = displayio.Group()
    bitmap = displayio.Bitmap(240, 240, 2)
    palette = displayio.Palette(2)
    palette[0], palette[1] = theme.BACKGROUND, theme.MUTED
    center = RoundLayout.CENTER[0]
    for y in range(240):
        for x in range(240):
            radius2 = (x - center) ** 2 + (y - center) ** 2
            if ((RoundLayout.OUTER_RING_RADIUS - 3) ** 2 <= radius2 <=
                    (RoundLayout.OUTER_RING_RADIUS + 3) ** 2):
                bitmap[x, y] = 1
    root.append(displayio.TileGrid(bitmap, pixel_shader=palette))
    content = displayio.Group()
    root.append(content)
    title = _line(displayio, terminalio, 156, 12, 42, 22, theme.CYAN)
    axis = _line(displayio, terminalio, 30, 12, 105, 56, theme.CYAN)
    value = _line(displayio, terminalio, 150, 18, 45, 78)
    secondary = _line(displayio, terminalio, 190, 10, 25, 110, theme.MUTED)
    multiplier = _line(displayio, terminalio, 170, 12, 35, 140, theme.CYAN)
    indicators = _line(displayio, terminalio, 170, 10, 35, 170, theme.GREEN)
    menu = [_line(displayio, terminalio, 170, 12, 35, 52 + index * 20)
            for index in range(6)]
    tabs = []
    for (x, y) in radial_points(5, 94):
        tabs.append(_line(displayio, terminalio, 55, 10,
                          max(0, x - 25), max(0, y - 5), theme.CYAN))
    for line in [title, axis, value, secondary, multiplier, indicators] + tabs:
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
