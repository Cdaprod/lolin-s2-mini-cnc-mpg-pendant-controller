"""GC9A01 construction and the production retained round-instrument scene."""

import math

from . import theme
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
          centered=False, scale=1):
    from src.display.displayio_backend import _DisplayIOTextLine
    source_width = max(1, width // scale)
    source_height = max(1, height // scale)
    line = _DisplayIOTextLine(source_width, source_height, terminalio.FONT,
                              displayio, color, centered)
    if scale == 1:
        line.node.x, line.node.y = x, y
    else:
        group = displayio.Group(scale=scale, x=x, y=y)
        group.append(line.node)
        line.node = group
    return line


class _InstrumentRingNode:
    """Palette-driven ring: no per-frame bitmap writes or object allocation."""

    def __init__(self, palette):
        self.palette = palette
        self.color = theme.MUTED
        self.signature = None

    def update(self, state, activity, armed, axis_transition,
               increment_transition):
        self.signature = (state, activity, armed, axis_transition,
                          increment_transition)
        exceptional = state in ("alarm", "estop")
        base = theme.RED if exceptional else (theme.CYAN if armed else 0x24343A)
        self.color = base
        self.palette[1] = base
        self.palette[2] = theme.CYAN if axis_transition else 0x31545B
        self.palette[3] = theme.YELLOW if increment_transition else 0x544B2A
        self.palette[4] = (theme.RED if exceptional else
                           (theme.CYAN if activity > 0 else 0x18343A))
        self.palette[5] = (theme.RED if exceptional else
                           (theme.YELLOW if activity < 0 else 0x352F1B))


class _HighlightNode:
    def __init__(self, node):
        self.node = node

    @property
    def hidden(self):
        return self.node.hidden

    @hidden.setter
    def hidden(self, value):
        self.node.hidden = value

    @property
    def y(self):
        return self.node.y

    @y.setter
    def y(self, value):
        self.node.y = value


def _instrument_bitmap(displayio):
    """Build one indexed backdrop with directional arcs and subtle dial ticks."""
    bitmap = displayio.Bitmap(240, 240, 6)
    palette = displayio.Palette(6)
    palette[0] = theme.BACKGROUND
    palette[1] = 0x24343A
    palette[2] = 0x31545B
    palette[3] = 0x544B2A
    palette[4] = 0x18343A
    palette[5] = 0x352F1B
    for y in range(240):
        dy = y - 120
        for x in range(240):
            dx = x - 120
            radius2 = dx * dx + dy * dy
            angle = math.atan2(dy, dx)
            if 106 * 106 <= radius2 <= 111 * 111:
                bitmap[x, y] = 1
            elif 97 * 97 <= radius2 <= 102 * 102:
                if -2.72 <= angle <= -1.77:
                    bitmap[x, y] = 2
                elif -1.37 <= angle <= -0.42:
                    bitmap[x, y] = 3
                elif 0.48 <= angle <= 1.42:
                    bitmap[x, y] = 4
                elif 1.72 <= angle <= 2.66:
                    bitmap[x, y] = 5
    return bitmap, palette


def displayio_scene(display):
    """Create a bounded retained scene optimized for a 240px circular panel."""
    import displayio
    import terminalio

    root = displayio.Group()
    bitmap, palette = _instrument_bitmap(displayio)
    root.append(displayio.TileGrid(bitmap, pixel_shader=palette))

    home = displayio.Group()
    root.append(home)
    axis_feedback = _line(displayio, terminalio, 68, 10, 46, 48,
                          theme.CYAN, True)
    step_feedback = _line(displayio, terminalio, 68, 10, 126, 48,
                          theme.YELLOW, True)
    state_label = _line(displayio, terminalio, 96, 12, 72, 29,
                        theme.GREEN, True)
    axis = _line(displayio, terminalio, 72, 30, 84, 59,
                 theme.CYAN, True, 3)
    value = _line(displayio, terminalio, 174, 30, 33, 89,
                  theme.TEXT, True, 3)
    context = _line(displayio, terminalio, 100, 10, 70, 121,
                    theme.MUTED, True)
    increment = _line(displayio, terminalio, 88, 20, 76, 137,
                      theme.YELLOW, True, 2)
    motion = _line(displayio, terminalio, 152, 12, 44, 168,
                   theme.CYAN, True)
    connectivity = _line(displayio, terminalio, 106, 10, 67, 194,
                         theme.MUTED, True)
    for line in (state_label, axis_feedback, step_feedback, axis, value,
                 context, increment, motion, connectivity):
        home.append(line.node)

    menu_group = displayio.Group()
    root.append(menu_group)
    menu_title = _line(displayio, terminalio, 150, 20, 45, 30,
                       theme.CYAN, True, 2)
    menu_group.append(menu_title.node)
    highlight_bitmap = displayio.Bitmap(180, 18, 1)
    highlight_palette = displayio.Palette(1)
    highlight_palette[0] = 0x15333A
    highlight_grid = displayio.TileGrid(highlight_bitmap,
                                        pixel_shader=highlight_palette,
                                        x=30, y=58)
    menu_group.append(highlight_grid)
    menu = []
    for index in range(6):
        line = _line(displayio, terminalio, 164, 12, 38, 63 + index * 22,
                     theme.TEXT)
        menu.append(line)
        menu_group.append(line.node)
    menu_footer = _line(displayio, terminalio, 110, 10, 65, 202,
                        theme.MUTED, True)
    menu_group.append(menu_footer.node)

    overlay_group = displayio.Group()
    modal_bitmap = displayio.Bitmap(190, 94, 1)
    modal_palette = displayio.Palette(1)
    modal_palette[0] = 0x26090D
    overlay_group.append(displayio.TileGrid(
        modal_bitmap, pixel_shader=modal_palette, x=25, y=73
    ))
    overlay_title = _line(displayio, terminalio, 160, 28, 40, 89,
                          theme.RED, True, 2)
    overlay_detail = _line(displayio, terminalio, 166, 14, 37, 128,
                           theme.TEXT, True)
    overlay_group.append(overlay_title.node)
    overlay_group.append(overlay_detail.node)
    root.append(overlay_group)

    return {
        "root": root, "ring": _InstrumentRingNode(palette),
        "home_group": home, "state_label": state_label,
        "axis_feedback": axis_feedback, "step_feedback": step_feedback,
        "axis": axis,
        "value": value, "context": context, "increment": increment,
        "motion": motion, "connectivity": connectivity,
        "menu_group": menu_group, "menu_title": menu_title, "menu": menu,
        "menu_highlight": _HighlightNode(highlight_grid),
        "menu_footer": menu_footer, "overlay_group": overlay_group,
        "overlay_title": overlay_title, "overlay_detail": overlay_detail,
    }


def from_config(config):
    if config.get("display_use_board_display"):
        import board
        display = board.DISPLAY
    elif config.get("display_driver") == "gc9a01":
        display = build_gc9a01(config)
    else:
        raise ValueError("round renderer requires a supported display driver")
    return RoundRenderer(display, displayio_scene)
