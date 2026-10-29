"""GC9A01 construction and the production retained round-instrument scene."""

import math

from . import theme
from .renderer import RoundRenderer

_BACKLIGHT_OUTPUT = None
_BITMAP_FONT_CACHE = {}
_BITMAP_FONT_FILES = {(1, 10): "DejaVuSans-10.bdf",
                      (1, 12): "DejaVuSans-12.bdf",
                      (1, 14): "DejaVuSans-12.bdf",
                      (2, 20): "DejaVuSans-Bold-14.bdf",
                      (2, 28): "DejaVuSans-Bold-14.bdf",
                      (3, 30): "DejaVuSans-Bold-24.bdf"}
_ASCII_GLYPHS = tuple(range(32, 127))
_COMMON_GLYPHS = _ASCII_GLYPHS + (0x2014, 0x2026, 0x00B0)
_BITMAP_FONT_GLYPHS = {
    (1, 10): _ASCII_GLYPHS,
    (1, 12): _COMMON_GLYPHS,
    (1, 14): _COMMON_GLYPHS,
    (2, 20): _ASCII_GLYPHS,
    (2, 28): _ASCII_GLYPHS,
    (3, 30): tuple(ord(character) for character in " 0123456789+-.XYZABCOFF"),
}


def release_existing_displays():
    """Release resources owned by the prior round display composition.

    Call once during composition, before constructing the SPI bus. Releasing
    after another peripheral has retained that bus can invalidate ownership.
    """
    global _BACKLIGHT_OUTPUT
    import displayio
    try:
        displayio.release_displays()
    finally:
        # DisplayIO does not own this DigitalInOut. Keep its lifecycle beside
        # the display release or D6 remains claimed across app teardown.
        if _BACKLIGHT_OUTPUT is not None:
            output, _BACKLIGHT_OUTPUT = _BACKLIGHT_OUTPUT, None
            output.deinit()


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
    # Render fonts at their actual pixel sizes. Scaling the tiny terminal font
    # makes headings jagged and can clip long labels such as CONFIGURATION.
    font = terminalio.FONT
    font_key = ((1, 10) if scale == 1 and height <= 10 else
                (scale, height))
    font_path = _BITMAP_FONT_FILES.get(font_key)
    if font_path:
        # Several text boxes use the same BDF strike with different bounds.
        # Share the loaded font and its glyph cache by asset path.
        if font_path not in _BITMAP_FONT_CACHE:
            try:
                from adafruit_bitmap_font import bitmap_font
                loaded_font = bitmap_font.load_font("/fonts/" + font_path)
                # The BDF reader lazily scans the complete file for each
                # uncached character. Prime the small UI alphabet once so
                # live input and first-frame timing never pay per-glyph file
                # scans in the application loop.
                loaded_font.load_glyphs(_BITMAP_FONT_GLYPHS[font_key])
                _BITMAP_FONT_CACHE[font_path] = loaded_font
            except (ImportError, OSError, ValueError):
                _BITMAP_FONT_CACHE[font_path] = None
        if _BITMAP_FONT_CACHE[font_path] is not None:
            font = _BITMAP_FONT_CACHE[font_path]
            scale = 1
            source_width = width
            source_height = height
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
    # Small retained 9x9 multi-tone discs soften pixel stair-steps while
    # keeping the orbit indicators distinct at native 240x240 resolution.
    # Only sprite positions change per frame; no bitmap rebuilds.
    hud_markers = []
    hud_trails = []
    for radius, color in ((109, colors["accent"]), (99, colors["highlight"])):
        pixels = displayio.Bitmap(9, 9, 4)
        marker_palette = displayio.Palette(4)
        marker_palette[0] = 0
        marker_palette.make_transparent(0)
        marker_palette[1] = color
        marker_palette[2] = theme.shade_color(color, 72)
        marker_palette[3] = theme.shade_color(color, 38)
        for yy in range(9):
            for xx in range(9):
                distance2 = (xx - 4) ** 2 + (yy - 4) ** 2
                if distance2 <= 4:
                    pixels[xx, yy] = 1
                elif distance2 <= 9:
                    pixels[xx, yy] = 2
                elif distance2 <= 16:
                    pixels[xx, yy] = 3
        sprite = displayio.TileGrid(pixels, pixel_shader=marker_palette)
        sprite.x, sprite.y = 116 + radius, 116
        root.append(sprite)
        hud_markers.append((sprite, radius, marker_palette))
        # One faint, smaller retained ghost sits just behind each orbiting
        # disc. This gives a restrained sense of motion without a framebuffer,
        # alpha blending, or per-frame allocation.
        trail_bitmap = displayio.Bitmap(5, 5, 2)
        trail_palette = displayio.Palette(2)
        trail_palette[0] = 0
        trail_palette.make_transparent(0)
        trail_palette[1] = theme.shade_color(color, 22)
        for ty in range(5):
            for tx in range(5):
                if (tx - 2) ** 2 + (ty - 2) ** 2 <= 2:
                    trail_bitmap[tx, ty] = 1
        trail = displayio.TileGrid(trail_bitmap, pixel_shader=trail_palette)
        trail.x, trail.y = sprite.x, sprite.y
        root.append(trail)
        hud_trails.append((trail, radius, trail_palette))
    palettes["hud_markers"] = tuple(item[2] for item in hud_markers)
    palettes["hud_trails"] = tuple(item[2] for item in hud_trails)


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
        line = _line(displayio, terminalio, 150, 12, 33, 63 + index * 22,
                     colors["text"], True)
        menu.append(line)
        menu_group.append(line.node)
    # Subtle separators make adjacent main-menu entries recognizable.
    separator_bitmap = displayio.Bitmap(170, 1, 1)
    separator_palette = displayio.Palette(1)
    separator_palette[0] = colors.get("separator", colors["muted"])
    palettes["separator"] = separator_palette
    menu_separators = []
    for index in range(5):
        separator = displayio.TileGrid(
            separator_bitmap, pixel_shader=separator_palette,
            x=35, y=79 + index * 22
        )
        separator.hidden = True
        menu_separators.append(separator)
        menu_group.append(separator)
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

    # Tiny retained touch ripple. Its four concentric palette zones animate
    # with a short glow/fade; the bitmap is built once and never rewritten.
    # Critical alarm overlay stays above this feedback layer.
    halo = displayio.Bitmap(13, 13, 4)
    halo_palette = displayio.Palette(4)
    halo_palette[0] = 0x000000
    halo_palette.make_transparent(0)
    halo_palette[1] = theme.shade_color(colors["accent"], 0)
    halo_palette[2] = theme.shade_color(colors["accent"], 0)
    halo_palette[3] = theme.shade_color(colors["accent"], 0)
    for hy in range(13):
        for hx in range(13):
            radius2 = (hx - 6) ** 2 + (hy - 6) ** 2
            if radius2 <= 1:
                halo[hx, hy] = 3
            elif 4 <= radius2 <= 8:
                halo[hx, hy] = 2
            elif 16 <= radius2 <= 36:
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
        "touch_halo": halo_node, "hud_markers": tuple(hud_markers),
        "hud_trails": tuple(hud_trails),
        "nav_group": nav_group,
        "nav_dots": nav_dots,
        "home_group": home, "state_label": state_label,
        "axis_feedback": axis_feedback, "step_feedback": step_feedback,
        "axis": axis,
        "value": value, "context": context, "increment": increment,
        "motion": motion, "connectivity": connectivity,
        "menu_group": menu_group, "menu_title": menu_title, "menu": menu,
        "menu_separators": tuple(menu_separators),
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
