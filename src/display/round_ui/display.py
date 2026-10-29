"""GC9A01 construction and the production retained round-instrument scene."""

import math

from . import bezel_palette, theme
from .rotor import BEZEL_SEGMENT_COUNT, BEZEL_SEGMENT_OFFSET_RAD
from .effects import TOUCH_BITMAP_CENTER, TOUCH_BITMAP_SIZE, touch_zone
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


def _instrument_bitmap(displayio, colors, legacy_bezel=True):
    """Build one indexed backdrop with directional arcs and subtle dial ticks."""
    bitmap = displayio.Bitmap(240, 240, 6)
    palette = displayio.Palette(6)
    palette[0] = colors["background"]
    palette[1] = colors["panel"]
    palette[2] = colors["highlight"]
    palette[3] = colors["panel"]
    palette[4] = colors["panel"]
    palette[5] = colors["panel"]
    if not legacy_bezel:
        bitmap.fill(0)
        return bitmap, palette
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


def _load_bezel(displayio, name):
    """Load one compact indexed bezel once; return None for safe fallback."""
    if name not in bezel_palette.PALETTES:
        return None, None
    try:
        import bitmaptools
        bitmap = displayio.Bitmap(240, 240, 16)
        with open("/assets/round_hud/runtime/{}.4bpp".format(name), "rb") as source:
            bitmaptools.readinto(bitmap, source, bits_per_pixel=4)
        palette = displayio.Palette(16)
        for index, color in enumerate(bezel_palette.PALETTES[name]):
            palette[index] = color
        palette.make_transparent(0)
        return bitmap, palette
    except (ImportError, OSError, RuntimeError, ValueError, AttributeError,
            MemoryError):
        return None, None


def _load_orb_sprite_sheet(displayio):
    """Load precomputed subpixel phases or create a cheap legacy marker."""
    try:
        import bitmaptools
        bitmap = displayio.Bitmap(36, 36, 16)
        with open("/assets/round_hud/runtime/orbit_phases.4bpp", "rb") as source:
            bitmaptools.readinto(bitmap, source, bits_per_pixel=4)
        return bitmap, 16
    except (ImportError, OSError, RuntimeError, ValueError, AttributeError,
            MemoryError):
        bitmap = displayio.Bitmap(9, 9, 4)
        for yy in range(9):
            for xx in range(9):
                distance2 = (xx-4)**2 + (yy-4)**2
                if distance2 <= 4:
                    bitmap[xx, yy] = 1
                elif distance2 <= 9:
                    bitmap[xx, yy] = 2
                elif distance2 <= 16:
                    bitmap[xx, yy] = 3
        return bitmap, 0


def _load_rotor_sprite_sheet(displayio):
    """Load precomputed curved-arc orientation and subpixel phases."""
    try:
        import bitmaptools
        bitmap = displayio.Bitmap(132, 3168, 16)
        with open("/assets/round_hud/runtime/rotor_segment_phases.4bpp",
                  "rb") as source:
            bitmaptools.readinto(bitmap, source, bits_per_pixel=4)
        return bitmap, 384
    except (ImportError, OSError, RuntimeError, ValueError, AttributeError,
            MemoryError):
        return None, 0


def displayio_scene(display, colors=None, bezel_name=None):
    """Create a bounded retained scene optimized for a 240px circular panel."""
    import displayio
    import terminalio
    colors = colors or theme.select("industrial")

    root = displayio.Group()
    bezel_name = bezel_name or bezel_palette.DEFAULT_BEZEL
    bezel_bitmap, bezel_colors = _load_bezel(displayio, bezel_name)
    bitmap, palette = _instrument_bitmap(
        displayio, colors, legacy_bezel=bezel_bitmap is None)
    root.append(displayio.TileGrid(bitmap, pixel_shader=palette))
    if bezel_bitmap is not None:
        # Decorative light stays beneath all readouts, feedback, and alarms.
        root.append(displayio.TileGrid(bezel_bitmap, pixel_shader=bezel_colors))
    palettes = {"dial": palette}
    if bezel_colors is not None:
        palettes["bezel"] = bezel_colors
    # Keep all bezel geometry stationary during continuous animation. The old
    # orbiting marker and afterimage TileGrids were repositioned every frame,
    # adding moving sprite bounds on top of the ring. The retained curved arcs
    # below provide the travelling highlight through palette levels alone.
    hud_markers = []
    hud_trails = []
    hud_frame_count = 0

    # Fixed concentric arcs form the outer rotor. Their brightness wave turns
    # around the ring; the arcs themselves never spin or change orientation.
    rotor_segments = []
    rotor_palette_bank = []
    rotor_sheet, rotor_frame_count = _load_rotor_sprite_sheet(displayio)
    if rotor_sheet is not None:
        rotor_count = BEZEL_SEGMENT_COUNT
        # Palette entries for each intensity are built once. Animation swaps a
        # TileGrid's existing shader instead of writing up to 360 colors/frame.
        for level in range(16):
            rotor_palette = displayio.Palette(16)
            rotor_palette[0] = 0
            rotor_palette.make_transparent(0)
            percent = level * 100 // 15
            for shade in range(1, 16):
                rotor_palette[shade] = theme.shade_color(
                    colors["accent"], shade * percent // 15)
            rotor_palette_bank.append(rotor_palette)
        for index in range(rotor_count):
            segment = displayio.TileGrid(
                rotor_sheet, pixel_shader=rotor_palette_bank[1],
                width=1, height=1,
                tile_width=33, tile_height=33)
            angle = (BEZEL_SEGMENT_OFFSET_RAD +
                     2.0 * math.pi * index / rotor_count)
            center_x = 120 + 110.0 * math.cos(angle)
            center_y = 120 + 110.0 * math.sin(angle)
            base_x, base_y = math.floor(center_x), math.floor(center_y)
            phase_x = int((center_x - base_x) * 4)
            phase_y = int((center_y - base_y) * 4)
            tangent = (angle + math.pi / 2.0) % (2.0 * math.pi)
            orientation = int(round(tangent * 24.0 / (2.0 * math.pi))) % 24
            segment[0] = orientation * 16 + phase_y * 4 + phase_x
            segment.x, segment.y = int(base_x) - 16, int(base_y) - 16
            segment.hidden = False
            root.append(segment)
            rotor_segments.append(segment)

    # Encoder-only feedback uses one bead and two retained afterimages. These
    # visualize raw handwheel detents only, never accepted machine motion.
    encoder_bitmap = displayio.Bitmap(9, 9, 4)
    encoder_palette = displayio.Palette(4)
    encoder_palette[0] = 0
    encoder_palette.make_transparent(0)
    encoder_palette[1] = colors["accent"]
    encoder_palette[2] = theme.shade_color(colors["accent"], 64)
    encoder_palette[3] = theme.shade_color(colors["accent"], 28)
    for ey in range(9):
        for ex in range(9):
            distance = (ex-4)**2 + (ey-4)**2
            if distance <= 2:
                encoder_bitmap[ex, ey] = 1
            elif distance <= 8:
                encoder_bitmap[ex, ey] = 2
            elif distance <= 16:
                encoder_bitmap[ex, ey] = 3
    encoder_marker = displayio.TileGrid(encoder_bitmap,
                                        pixel_shader=encoder_palette)
    encoder_marker.hidden = True
    root.append(encoder_marker)
    encoder_trail_bitmap = displayio.Bitmap(5, 5, 2)
    encoder_trail_palette = displayio.Palette(2)
    encoder_trail_palette[0] = 0
    encoder_trail_palette.make_transparent(0)
    encoder_trail_palette[1] = theme.shade_color(colors["accent"], 36)
    for ey in range(5):
        for ex in range(5):
            if (ex-2)**2 + (ey-2)**2 <= 2:
                encoder_trail_bitmap[ex, ey] = 1
    encoder_trail = displayio.TileGrid(encoder_trail_bitmap,
                                       pixel_shader=encoder_trail_palette)
    encoder_trail.hidden = True
    root.append(encoder_trail)
    encoder_far_palette = displayio.Palette(2)
    encoder_far_palette[0] = 0
    encoder_far_palette.make_transparent(0)
    encoder_far_palette[1] = theme.shade_color(colors["accent"], 16)
    encoder_far_trail = displayio.TileGrid(
        encoder_trail_bitmap, pixel_shader=encoder_far_palette)
    encoder_far_trail.hidden = True
    root.append(encoder_far_trail)
    palettes["encoder"] = (encoder_palette, encoder_trail_palette,
                            encoder_far_palette)

    # Build the retained touch pulse once; its layer is moved above ordinary
    # labels below so the contact response remains visible on a direct tap.
    halo = displayio.Bitmap(TOUCH_BITMAP_SIZE, TOUCH_BITMAP_SIZE, 5)
    halo_palette = displayio.Palette(5)
    halo_palette[0] = 0x000000
    halo_palette.make_transparent(0)
    for index in range(1, 5):
        halo_palette[index] = theme.shade_color(colors["accent"], 0)
    for hy in range(TOUCH_BITMAP_SIZE):
        for hx in range(TOUCH_BITMAP_SIZE):
            halo[hx, hy] = touch_zone(hx, hy)
    palettes["halo"] = halo_palette
    halo_node = displayio.TileGrid(halo, pixel_shader=halo_palette)
    halo_node.hidden = True
    root.append(halo_node)

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

    # Keep contact feedback visible over ordinary UI text/highlights. The
    # critical modal is appended afterward and always remains highest priority.
    root.remove(halo_node)
    root.append(halo_node)

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

    # Critical modal/alarm rendering stays above the touch feedback layer.
    root.remove(overlay_group)
    root.append(overlay_group)

    return {
        "root": root, "ring": _InstrumentRingNode(palette, colors),
        "bezel_name": bezel_name if bezel_bitmap is not None else None,
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
        "hud_frame_count": hud_frame_count,
        "rotor_segments": tuple(rotor_segments),
        "rotor_palette_bank": tuple(rotor_palette_bank),
        "rotor_tile_count": rotor_frame_count,
        "rotor_color": colors["accent"],
        "encoder_marker": encoder_marker, "encoder_trail": encoder_trail,
        "encoder_far_trail": encoder_far_trail,
        "encoder_palettes": palettes["encoder"],
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
        display, lambda d: displayio_scene(
            d, colors, config.get("ui_bezel", bezel_palette.DEFAULT_BEZEL)),
        animations=config.get("ui_animations", True),
        bezel_rotation_enabled=config.get("bezel_rotation_enabled", True),
        bezel_ambient_period_s=config.get("bezel_ambient_period_s", 54.0),
        bezel_encoder_gain=config.get("bezel_encoder_gain", 0.04),
        bezel_max_speed_rad_s=config.get("bezel_max_speed_rad_s", 0.35),
        bezel_inertia_s=config.get("bezel_inertia_s", 0.9),
        bezel_direction_change_min_s=config.get(
            "bezel_direction_change_min_s", 20.0),
        bezel_direction_change_max_s=config.get(
            "bezel_direction_change_max_s", 40.0),
        bezel_frame_rate=config.get("bezel_frame_rate", 24))
