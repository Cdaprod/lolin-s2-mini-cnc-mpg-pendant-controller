"""GC9A01 construction and the production retained round-instrument scene."""

import math

from . import theme
from .renderer import RoundRenderer

_BACKLIGHT_OUTPUT = None


def _pin(board, name):
    if not name or not hasattr(board, name):
        return None
    return getattr(board, name)


def build_gc9a01(config, shared_spi=None):
    """Construct a GC9A01 from profile-selected pins."""
    global _BACKLIGHT_OUTPUT
    import board
    import busio
    import displayio
    import adafruit_gc9a01a
    displayio.release_displays()
    spi = shared_spi or busio.SPI(_pin(board, config["display_sck_pin"]),
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
    # Prefer a native-size bitmap font for enlarged text; scaling terminalio
    # pixels creates harsh 2x/3x square edges. Optional file, safe fallback.
    font = terminalio.FONT
    if scale > 1:
        try:
            from adafruit_bitmap_font import bitmap_font
            font = bitmap_font.load_font("/fonts/DejaVuSans-14.bdf")
            scale = 1
            source_width = width
            source_height = height
        except (ImportError, OSError, ValueError):
            pass
    line = _DisplayIOTextLine(source_width, source_height, font,
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

    def __init__(self, palette, colors):
        self.palette = palette
        self.colors = colors
        self.color = colors["muted"]
        self.signature = None

    def update(self, state, activity, armed, axis_transition,
               increment_transition):
        self.signature = (state, activity, armed, axis_transition,
                          increment_transition)
        exceptional = state in ("alarm", "estop")
        accent = self.colors["accent"]
        danger = self.colors["danger"]
        base = danger if exceptional else self.colors["panel"]
        self.color = base
        self.palette[1] = base
        self.palette[2] = accent if axis_transition else self.colors["panel"]
        self.palette[3] = self.colors["warning"] if increment_transition else self.colors["panel"]
        self.palette[4] = danger if exceptional else (accent if activity > 0 else self.colors["panel"])
        self.palette[5] = danger if exceptional else (self.colors["warning"] if activity < 0 else self.colors["panel"])


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


def _instrument_bitmap(displayio, colors):
    """Build one indexed backdrop with directional arcs and subtle dial ticks."""
    bitmap = displayio.Bitmap(240, 240, 6)
    palette = displayio.Palette(6)
    palette[0] = colors["background"]
    palette[1] = colors["panel"]
    palette[2] = colors["highlight"]
    palette[3] = colors["panel"]
    palette[4] = colors["panel"]
    palette[5] = colors["panel"]
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


def displayio_scene(display, colors=None):
    """Create a bounded retained scene optimized for a 240px circular panel."""
    import displayio
    import terminalio
    colors = colors or theme.select("industrial")

    root = displayio.Group()
    bitmap, palette = _instrument_bitmap(displayio, colors)
    root.append(displayio.TileGrid(bitmap, pixel_shader=palette))
    palettes = {"dial": palette}


    home = displayio.Group()
    root.append(home)
    axis_feedback = _line(displayio, terminalio, 68, 10, 46, 48,
                          colors["accent"], True)
    step_feedback = _line(displayio, terminalio, 68, 10, 126, 48,
                          colors["warning"], True)
    state_label = _line(displayio, terminalio, 96, 12, 72, 29,
                        colors["success"], True)
    axis = _line(displayio, terminalio, 72, 30, 84, 59,
                 colors["accent"], True, 3)
    value = _line(displayio, terminalio, 174, 30, 33, 89,
                  colors["text"], True, 3)
    context = _line(displayio, terminalio, 100, 10, 70, 121,
                    colors["muted"], True)
    increment = _line(displayio, terminalio, 88, 20, 76, 137,
                      colors["warning"], True, 2)
    motion = _line(displayio, terminalio, 152, 12, 44, 168,
                   colors["accent"], True)
    connectivity = _line(displayio, terminalio, 106, 10, 67, 194,
                         colors["muted"], True)
    for line in (state_label, axis_feedback, step_feedback, axis, value,
                 context, increment, motion, connectivity):
        home.append(line.node)

    # Retained, transient page indicators on the top edge of the circle.
    # The current page is white; all other dots are muted grey.
    nav_group = displayio.Group()
    nav_group.hidden = True
    root.append(nav_group)
    nav_dots = []
    for i in range(7):
        dot = displayio.Bitmap(7, 7, 2)
        dot_palette = displayio.Palette(2)
        dot_palette[0] = 0x000000
        dot_palette.make_transparent(0)
        dot_palette[1] = colors["muted"]
        for dy in range(7):
            for dx in range(7):
                if (dx - 3) ** 2 + (dy - 3) ** 2 <= 9:
                    dot[dx, dy] = 1
        node = displayio.TileGrid(dot, pixel_shader=dot_palette)
        node.hidden = True
        nav_group.append(node)
        nav_dots.append((node, dot_palette))

    menu_group = displayio.Group()
    # HOME is the initial screen; menu must not cover operational readouts
    # before the renderer's first scheduled refresh.
    menu_group.hidden = True
    root.append(menu_group)
    menu_title = _line(displayio, terminalio, 150, 20, 45, 30,
                       colors["accent"], True, 2)
    menu_group.append(menu_title.node)
    # High-contrast outline replaces the previous muddy solid highlight.
    highlight_bitmap = displayio.Bitmap(180, 18, 3)
    highlight_palette = displayio.Palette(3)
    highlight_palette[0] = colors["panel"]
    highlight_palette[1] = colors.get("focus_border", colors["muted"])
    highlight_palette[2] = colors["accent"]
    for x in range(180):
        highlight_bitmap[x, 0] = 1
        highlight_bitmap[x, 17] = 1
    for y in range(18):
        for x in range(4):
            highlight_bitmap[x, y] = 2
        highlight_bitmap[179, y] = 1
    palettes["focus"] = highlight_palette
    highlight_grid = displayio.TileGrid(highlight_bitmap,
                                        pixel_shader=highlight_palette,
                                        x=30, y=58)
    menu_group.append(highlight_grid)
    menu = []
    for index in range(6):
        line = _line(displayio, terminalio, 164, 12, 38, 63 + index * 22,
                     colors["text"])
        menu.append(line)
        menu_group.append(line.node)
    # Subtle separators make adjacent main-menu entries recognizable.
    separator_bitmap = displayio.Bitmap(170, 1, 1)
    separator_palette = displayio.Palette(1)
    separator_palette[0] = colors.get("separator", colors["muted"])
    palettes["separator"] = separator_palette
    for index in range(5):
        menu_group.append(displayio.TileGrid(
            separator_bitmap, pixel_shader=separator_palette,
            x=35, y=79 + index * 22
        ))
    menu_footer = _line(displayio, terminalio, 110, 10, 65, 202,
                        colors["muted"], True)
    menu_group.append(menu_footer.node)

    overlay_group = displayio.Group()
    # Keep the opaque modal from covering HOME before the first renderer poll.
    overlay_group.hidden = True
    modal_bitmap = displayio.Bitmap(190, 94, 1)
    modal_palette = displayio.Palette(1)
    modal_palette[0] = 0x26090D
    overlay_group.append(displayio.TileGrid(
        modal_bitmap, pixel_shader=modal_palette, x=25, y=73
    ))
    overlay_title = _line(displayio, terminalio, 160, 28, 40, 89,
                          colors["danger"], True, 2)
    overlay_detail = _line(displayio, terminalio, 166, 14, 37, 128,
                           colors["text"], True)
    overlay_group.append(overlay_title.node)
    overlay_group.append(overlay_detail.node)
    root.append(overlay_group)

    # Tiny, retained touch halo, invisible until the application observes a
    # physical release. A 13x13 indexed sprite costs 169 pixels and is never
    # rewritten during normal polling. Critical alarm overlay stays above it.
    halo = displayio.Bitmap(13, 13, 2)
    halo_palette = displayio.Palette(2)
    halo_palette[0] = 0x000000
    halo_palette.make_transparent(0)
    halo_palette[1] = colors["accent"]
    for hy in range(13):
        for hx in range(13):
            radius2 = (hx - 6) ** 2 + (hy - 6) ** 2
            if 22 <= radius2 <= 42:
                halo[hx, hy] = 1
    palettes["halo"] = halo_palette
    halo_node = displayio.TileGrid(halo, pixel_shader=halo_palette)
    halo_node.hidden = True
    root.append(halo_node)
    # Keep the high-priority overlay above the touch indicator.
    root.remove(overlay_group)
    root.append(overlay_group)

    return {
        "root": root, "ring": _InstrumentRingNode(palette, colors),
        "palettes": palettes,
        "themed_text": ((axis_feedback, "accent"), (step_feedback, "warning"),
                        (state_label, "success"), (axis, "accent"),
                        (value, "text"), (context, "muted"),
                        (increment, "warning"), (motion, "accent"),
                        (connectivity, "muted"), (menu_title, "accent"),
                        (menu_footer, "muted"), (overlay_title, "danger"),
                        (overlay_detail, "text")),
        "touch_halo": halo_node, "nav_group": nav_group,
        "nav_dots": nav_dots,
        "home_group": home, "state_label": state_label,
        "axis_feedback": axis_feedback, "step_feedback": step_feedback,
        "axis": axis,
        "value": value, "context": context, "increment": increment,
        "motion": motion, "connectivity": connectivity,
        "menu_group": menu_group, "menu_title": menu_title, "menu": menu,
        "menu_colors": (colors["text"], colors["muted"]),
        "menu_highlight": _HighlightNode(highlight_grid),
        "menu_footer": menu_footer, "overlay_group": overlay_group,
        "overlay_title": overlay_title, "overlay_detail": overlay_detail,
    }


def from_config(config, shared_spi=None):
    if config.get("display_use_board_display"):
        import board
        display = board.DISPLAY
    elif config.get("display_driver") == "gc9a01":
        display = build_gc9a01(config, shared_spi=shared_spi)
    else:
        raise ValueError("round renderer requires a supported display driver")
    colors = theme.select(config.get("ui_theme", "industrial"))
    return RoundRenderer(
        display, lambda d: displayio_scene(d, colors),
        animations=config.get("ui_animations", True))
