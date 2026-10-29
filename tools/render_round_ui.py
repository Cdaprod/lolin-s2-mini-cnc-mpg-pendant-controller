"""240px UI design snapshots, sourced from the production screen registry.

Preview approximations for design review, not pixel-identical DisplayIO captures.
The dots here depict the transient 1.6s state immediately after navigation.
"""
from pathlib import Path
import argparse
import math
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageDraw, ImageFont
from src.display.round_ui import bezel_palette, theme
from src.display.round_ui.renderer import HUD_ORBIT_RATES
from src.display.ui import build_screens
from src.display.navigation import menu_window_start

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, default=Path("reports/round-ui"),
                    help="snapshot directory (default: reports/round-ui)")
parser.add_argument("--bezel", default="cyan_reactor",
                    help="generated bezel name to composite into previews")
ARGS = parser.parse_args()
OUT = ARGS.output
OUT.mkdir(parents=True, exist_ok=True)
ASSET_ROOT = Path(__file__).resolve().parents[1] / "assets" / "round_hud"
BEZEL_PATH = ASSET_ROOT / "runtime" / (ARGS.bezel + ".4bpp")
if ARGS.bezel not in bezel_palette.PALETTES or not BEZEL_PATH.is_file():
    raise SystemExit("generated runtime bezel not found: {}".format(BEZEL_PATH))


def load_runtime_bezel(name, palette_name=None):
    """Decode the exact LSB-first 4bpp asset and palette used by firmware."""
    path = ASSET_ROOT / "runtime" / (name + ".4bpp")
    if name not in bezel_palette.PALETTES or not path.is_file():
        raise SystemExit("generated runtime bezel not found: {}".format(path))
    data = path.read_bytes()
    if len(data) != 240 * 240 // 2:
        raise SystemExit("invalid runtime bezel size: {}".format(path))
    indices = bytearray(240 * 240)
    for offset, value in enumerate(data):
        indices[offset * 2] = value & 0x0F
        indices[offset * 2 + 1] = value >> 4
    colors = bezel_palette.PALETTES[palette_name or name]
    # Approximate the panel's RGB565 color conversion in the preview. Keep
    # index zero transparent, matching Palette.make_transparent(0).
    rgba_palette = []
    for color in colors:
        red = (color >> 16) & 0xFF
        green = (color >> 8) & 0xFF
        blue = color & 0xFF
        red = (red >> 3) * 255 // 31
        green = (green >> 2) * 255 // 63
        blue = (blue >> 3) * 255 // 31
        rgba_palette.extend((red, green, blue, 0 if color == colors[0] else 255))
    image = Image.new("RGBA", (240, 240))
    image.putdata([tuple(rgba_palette[index * 4:index * 4 + 4])
                   for index in indices])
    return image


bezel_asset = load_runtime_bezel(ARGS.bezel)
ROTOR_ASSET = ASSET_ROOT / "runtime" / "rotor_segment_phases.4bpp"
rotor_asset = ROTOR_ASSET.read_bytes() if ROTOR_ASSET.is_file() else b""
screens = build_screens()
names = ["HOME", "MAIN_MENU", "MACHINE", "JOBS", "JOB_BROWSER",
         "ACTIVE_JOB", "EXPLORER", "CONFIGURATION", "CONTROLLER",
         "NETWORK", "SETTINGS", "SYSTEM", "SYSTEM_INFO", "PREVIEW"]
runtime_fonts = Path(__file__).resolve().parents[1] / "fonts-source"
regular_candidates = (
    runtime_fonts / "DejaVuSans.ttf",
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
)
bold_candidates = (
    runtime_fonts / "DejaVuSans-Bold.ttf",
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
)
regular_source = next(path for path in regular_candidates if path.is_file())
bold_source = next(path for path in bold_candidates if path.is_file())
# Use the same family and pixel sizes as the device BDF strikes. The TTF
# source is optional and only used for host previews.
font = ImageFont.truetype(str(regular_source), 12)
small = ImageFont.truetype(str(regular_source), 10)
large = ImageFont.truetype(str(bold_source), 24)
title_font = ImageFont.truetype(str(bold_source), 14)


def rgb(color):
    """Convert firmware RGB888 integers to Pillow's explicit RGB tuple."""
    if isinstance(color, int):
        return ((color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF)
    return color


def draw_hud_orbs(draw, colors, now=4.0, outer_angle=None):
    """Match production marker geometry and its retained dim motion ghost."""
    for index, (radius, rate) in enumerate(zip((109, 99), HUD_ORBIT_RATES)):
        color = colors["accent"] if index == 0 else colors["highlight"]
        angle = (outer_angle if index == 0 and outer_angle is not None
                 else now * rate)
        cx = 120 + round(radius * math.cos(angle))
        cy = 120 + round(radius * math.sin(angle))
        for yy in range(9):
            for xx in range(9):
                distance2 = (xx - 4) ** 2 + (yy - 4) ** 2
                if distance2 <= 4:
                    fill = color
                elif distance2 <= 9:
                    fill = theme.shade_color(color, 72)
                elif distance2 <= 16:
                    fill = theme.shade_color(color, 38)
                else:
                    continue
                draw.point((cx + xx - 4, cy + yy - 4), fill=rgb(fill))
        trail_angle = angle - rate * 0.20
        trail_x = 118 + round(radius * math.cos(trail_angle))
        trail_y = 118 + round(radius * math.sin(trail_angle))
        ghost = theme.shade_color(color, 22)
        for yy in range(5):
            for xx in range(5):
                if (xx - 2) ** 2 + (yy - 2) ** 2 <= 2:
                    draw.point((trail_x + xx - 2, trail_y + yy - 2),
                               fill=rgb(ghost))


def draw_rotor_segments(image, colors, angle):
    """Composite the same compact phase tiles used by the firmware renderer."""
    if len(rotor_asset) != 36 * 576 // 2:
        return
    pixels = image.load()
    for segment in range(3):
        theta = angle + segment * (2.0 * math.pi / 3.0)
        center_x = 120 + 113.0 * math.cos(theta)
        center_y = 120 + 113.0 * math.sin(theta)
        base_x, base_y = math.floor(center_x), math.floor(center_y)
        phase_x = int((center_x - base_x) * 4)
        phase_y = int((center_y - base_y) * 4)
        tangent = (theta + math.pi / 2.0) % (2.0 * math.pi)
        orientation = int(round(tangent * 16.0 / (2.0 * math.pi))) % 16
        tile_x, tile_y = phase_x, orientation * 4 + phase_y
        for y in range(9):
            for x in range(9):
                atlas_x, atlas_y = tile_x * 9 + x, tile_y * 9 + y
                byte = rotor_asset[atlas_y * 18 + atlas_x // 2]
                value = (byte & 0x0F) if atlas_x % 2 == 0 else byte >> 4
                if value:
                    color = theme.shade_color(colors["accent"], value * 100 // 15)
                    pixels[int(base_x) + x - 4, int(base_y) + y - 4] = rgb(color)


for skin in ("industrial", "ice", "amber", "spectrum"):
    # Retain per-theme previews for color regression; also publish a page-
    # accurate composite showing the palette chosen by physical selector.
    c = theme.select(skin)
    for name in names:
        screen = screens[name]
        base = Image.new("RGBA", (240, 240), rgb(c["background"]) + (255,))
        im = Image.alpha_composite(base, bezel_asset).convert("RGB")
        d = ImageDraw.Draw(im)
        # Four physical top-level page positions; no pager at idle in firmware.
        page = {"EXPLORER": 1, "CONFIGURATION": 2, "PREVIEW": 3}.get(name, 0)
        # Snapshot at t=4 s to make both counter-rotating HUD markers visible.
        draw_hud_orbs(d, c)
        draw_rotor_segments(im, c, 0.0)
        d = ImageDraw.Draw(im)
        for i in range(4):
            x = 67 + (106 * i) // 3
            y = 120 - int(math.sqrt(108 * 108 - (x - 120) ** 2))
            fill = 0xFFFFFF if i == page else 0x667176
            d.ellipse((x-3, y-3, x+3, y+3), fill=rgb(fill))
        if name == "HOME":
            d.text((120, 43), "READY", anchor="mm", font=large, fill=rgb(c["success"]))
            d.text((120, 72), "X", anchor="mm", font=large, fill=rgb(c["accent"]))
            d.text((120, 111), "+124.520", anchor="mm", font=large, fill=rgb(c["text"]))
            d.text((120, 143), "WPOS  mm", anchor="mm", font=font, fill=rgb(c["muted"]))
            d.text((120, 168), "X10", anchor="mm", font=large, fill=rgb(c["warning"]))
            d.text((120, 194), "HOLD TO JOG", anchor="mm", font=small, fill=rgb(c["text"]))
        else:
            title = screen.title
            while title and d.textbbox((0, 0), title, font=title_font)[2] > 166:
                title = title[:-1]
            d.text((120, 43), title, anchor="mm", font=title_font, fill=rgb(c["text"]))
            d.line((44, 55, 196, 55), fill=rgb(c.get("separator", c["muted"])), width=1)
            items = screen.items
            if not items:
                if screen.dynamic == "jobs":
                    items = ["demo.nc", "calibration.nc", "examples/"]
                elif name == "SYSTEM_INFO":
                    items = ["Board: XIAO S3", "Display: 240x240", "Touch: CST8XX", "I2C: enabled", "SD: available"]
                elif name == "PREVIEW":
                    items = ["Mode: SAFE SIM", "Wheel steps: 0", "Increment: 0.001", "Simulated X: 0.0"]
                else:
                    items = ["No items available"]
            focus = min(2, len(items)-1)
            start = menu_window_start(focus, len(items), 6)
            for row, item in enumerate(items[start:start+6]):
                label = item.label if hasattr(item, "label") else item
                enabled = getattr(item, "enabled", True)
                y = 62 + row * 22
                if row == focus - start:
                    d.rounded_rectangle((30, y-4, 210, y+17), radius=5,
                                        fill=rgb(c["panel"]), outline=rgb(c.get("focus_border", c["muted"])), width=1)
                    d.rounded_rectangle((30, y-4, 34, y+17), radius=2, fill=rgb(c["accent"]))
                elif row:
                    d.line((37, y-7, 203, y-7), fill=rgb(c.get("separator", c["muted"])), width=1)
                available = 156
                label = str(label)
                while label and d.textbbox((0, 0), label, font=font)[2] > available:
                    label = label[:-2]
                    if not label.endswith("…"):
                        label += "…"
                d.text((43, y), label, font=font,
                       fill=rgb(c["text"] if enabled else c["muted"]))
            d.text((120, 211), "BACK  ·  HOME", anchor="mm", font=small, fill=rgb(c["muted"]))
        im.save(OUT / f"{skin}-{name.lower()}.png")
        if name == "HOME":
            angle = 4.0 * HUD_ORBIT_RATES[0]
            marker = (120 + round(109 * math.cos(angle)),
                      120 + round(109 * math.sin(angle)))
            assert im.getpixel(marker) == rgb(c["accent"]), (
                "Pillow color conversion changed the firmware HUD color",
                im.getpixel(marker), rgb(c["accent"]))

# Match the user's photographed, disarmed HOME state as a separate visual
# target. Connection state and motion admission are shown as distinct signals.
c = theme.select("industrial")
base = Image.new("RGBA", (240, 240), rgb(c["background"]) + (255,))
im = Image.alpha_composite(base, bezel_asset).convert("RGB")
d = ImageDraw.Draw(im)
draw_hud_orbs(d, c)
draw_rotor_segments(im, c, 0.0)
d = ImageDraw.Draw(im)
for i in range(4):
    x = 67 + (106 * i) // 3
    y = 120 - int(math.sqrt(108 * 108 - (x - 120) ** 2))
    d.ellipse((x-3, y-3, x+3, y+3),
              fill=rgb(0xFFFFFF if i == 0 else 0x667176))
d.text((120, 38), "DISCONNECTED", anchor="mm", font=font,
       fill=rgb(c["muted"]))
d.text((79, 55), "AXIS OFF", anchor="mm", font=small,
       fill=rgb(c["accent"]))
d.text((161, 55), "STEP X1", anchor="mm", font=small,
       fill=rgb(c["warning"]))
d.text((120, 78), "OFF", anchor="mm", font=large,
       fill=rgb(c["accent"]))
d.text((120, 112), "---", anchor="mm", font=large,
       fill=rgb(c["text"]))
d.text((120, 137), "WPOS  mm", anchor="mm", font=font,
       fill=rgb(c["muted"]))
d.text((120, 157), "X1", anchor="mm", font=large,
       fill=rgb(c["warning"]))
d.text((120, 187), "MOTION DISARMED", anchor="mm", font=small,
       fill=rgb(c["warning"]))
d.text((120, 211), "NET-  SD-  MENU", anchor="mm", font=small,
       fill=rgb(c["muted"]))
im.save(OUT / "home-disconnected.png")

# Dedicated preview of each physical page in its assigned theme.
assigned = (("HOME", "industrial"), ("EXPLORER", "amber"),
            ("CONFIGURATION", "ice"), ("PREVIEW", "spectrum"))
page_sheet = Image.new("RGB", (1120, 310), "#15191D")
page_draw = ImageDraw.Draw(page_sheet)
heading = ImageFont.truetype(str(regular_source), 18)
for i, (screen, palette) in enumerate(assigned):
    x = 20 + i * 280
    preview_path = (OUT / "home-disconnected.png" if screen == "HOME" else
                    OUT / f"{palette}-{screen.lower()}.png")
    preview = Image.open(preview_path)
    page_sheet.paste(preview, (x, 12))
    page_draw.text((x, 260), f"{screen} · {palette.upper()}",
                   font=heading, fill="#E5E7EB")
page_sheet.save(OUT / "physical-pages-themed.png")
# Readable contact sheets accompany every CI artifact for visual regression review.
for skin in ("industrial", "ice", "amber", "spectrum"):
    sheet = Image.new("RGB", (1120, 1160), "#15191D")
    draw = ImageDraw.Draw(sheet)
    heading = ImageFont.truetype(str(regular_source), 18)
    for index, name in enumerate(names):
        x = index % 4 * 280 + 20
        y = index // 4 * 290 + 16
        panel = Image.open(OUT / f"{skin}-{name.lower()}.png")
        sheet.paste(panel, (x, y))
        draw.text((x, y + 245), name.replace("_", " "),
                  font=heading, fill="#E5E7EB")
    sheet.save(OUT / f"{skin}-contact-sheet.png")
print(f"Generated {len(names)*4} previews + 4 contact sheets in {OUT}")

# The user-provided photo showed the browser's no-files page. Keep both
# storage outcomes visible in snapshots so that blank-row regressions are
# immediately apparent.
for storage, primary, secondary in (
        ("disabled", "SD CARD DISABLED", "ENABLE IN SETTINGS"),
        ("available", "NO FILES FOUND", "SD CARD READY")):
    c = theme.select("amber")
    base = Image.new("RGBA", (240, 240), rgb(c["background"]) + (255,))
    im = Image.alpha_composite(base, bezel_asset).convert("RGB")
    d = ImageDraw.Draw(im)
    draw_hud_orbs(d, c)
    draw_rotor_segments(im, c, 0.0)
    d = ImageDraw.Draw(im)
    d.text((120, 43), "FILE EXPLORER", anchor="mm", font=title_font,
           fill=rgb(c["text"]))
    d.line((44, 55, 196, 55), fill=rgb(c["separator"]), width=1)
    d.text((120, 129), primary, anchor="mm", font=font, fill=rgb(c["text"]))
    d.text((120, 151), secondary, anchor="mm", font=small, fill=rgb(c["muted"]))
    d.text((120, 211), "-  BACK  |  HOME", anchor="mm", font=small,
           fill=rgb(c["muted"]))
    im.save(OUT / f"explorer-empty-{storage}.png")


def state_canvas(palette_name="industrial", bezel_name=None, rotor_angle=0.0,
                 outer_angle=None, alarm=False):
    colors = theme.select(palette_name)
    selected = bezel_name or ARGS.bezel
    art = load_runtime_bezel(selected,
                             "red_alarm" if alarm else selected)
    base = Image.new("RGBA", (240, 240), rgb(colors["background"])+(255,))
    image = Image.alpha_composite(base, art).convert("RGB")
    draw = ImageDraw.Draw(image)
    if not alarm:
        draw_hud_orbs(draw, colors, outer_angle=outer_angle)
        draw_rotor_segments(image, colors, rotor_angle)
    draw = ImageDraw.Draw(image)
    return image, draw, colors


def preview_home(filename, status, axis, step, position, safety, *,
                 palette_name="industrial", bezel_name=None):
    image, draw, colors = state_canvas(palette_name, bezel_name)
    draw.text((120, 38), status, anchor="mm", font=font,
              fill=rgb(colors["success"] if status == "CONNECTED" else colors["muted"]))
    draw.text((79, 55), "AXIS " + axis, anchor="mm", font=small,
              fill=rgb(colors["accent"]))
    draw.text((161, 55), "STEP " + step, anchor="mm", font=small,
              fill=rgb(colors["warning"]))
    draw.text((120, 82), position, anchor="mm", font=large,
              fill=rgb(colors["accent"]))
    draw.text((120, 118), "WPOS  mm", anchor="mm", font=font,
              fill=rgb(colors["muted"]))
    draw.text((120, 151), step, anchor="mm", font=large,
              fill=rgb(colors["warning"]))
    draw.text((120, 187), safety, anchor="mm", font=small,
              fill=rgb(colors["text"] if status == "CONNECTED" else colors["warning"]))
    draw.text((120, 211), "NET+  SD-  MENU", anchor="mm", font=small,
              fill=rgb(colors["muted"]))
    image.save(OUT / filename)


# These compositions reuse the photographed home layout and the actual
# retained status text placement; effects are previews, not device captures.
preview_home("home-connected.png", "CONNECTED", "X", "X10",
             "+124.520", "HOLD TO JOG")
preview_home("axis-selection.png", "CONNECTED", "Y", "X1",
             "+002.750", "AXIS SELECTED")
preview_home("encoder-motion.png", "CONNECTED", "X", "X10",
             "+124.520", "MPG INPUT +1")
encoder_preview = Image.open(OUT / "encoder-motion.png").convert("RGBA")
encoder_draw = ImageDraw.Draw(encoder_preview)
encoder_color = rgb(theme.select("industrial")["accent"])
encoder_draw.ellipse((149, 14, 162, 27), fill=encoder_color+(45,))
encoder_draw.ellipse((153, 18, 160, 25), fill=encoder_color+(230,))
encoder_draw.ellipse((140, 10, 146, 16), fill=encoder_color+(80,))
encoder_preview.convert("RGB").save(OUT / "encoder-motion.png")

touch_preview = Image.open(OUT / "amber-configuration.png").convert("RGBA")
touch_layer = Image.new("RGBA", (240, 240), (0, 0, 0, 0))
touch_draw = ImageDraw.Draw(touch_layer)
touch_color = rgb(theme.select("ice")["accent"])
for radius, alpha in ((5, 190), (12, 120), (21, 60)):
    touch_draw.ellipse((79-radius, 94-radius, 79+radius, 94+radius),
                       outline=touch_color+(alpha,), width=1)
touch_preview = Image.alpha_composite(touch_preview, touch_layer)
touch_preview.convert("RGB").save(OUT / "touch-ripple.png")

alarm_image, alarm_draw, alarm_colors = state_canvas(
    "industrial", alarm=True)
alarm_draw.rounded_rectangle((34, 76, 206, 164), radius=12,
                             fill=(20, 5, 12), outline=(255, 73, 85), width=1)
alarm_draw.text((120, 101), "ALARM", anchor="mm", font=large,
                fill=(255, 69, 82))
alarm_draw.text((120, 132), "MOTION INHIBITED", anchor="mm", font=small,
                fill=(245, 239, 242))
alarm_image.save(OUT / "alarm-critical.png")

print("Generated interactive-state previews (connected, axis, touch, encoder, alarm)")

# Angle sweep isolates the retained outer rotor bead over identical HUD content.
# It demonstrates spatial continuity; the physical renderer interpolates
# between these positions at its configured frame ceiling.
for degrees in (0, 90, 180, 270):
    image, draw, colors = state_canvas(
        rotor_angle=math.radians(degrees), outer_angle=math.radians(degrees))
    draw.text((120, 211), "BEZEL {:03d} DEG".format(degrees), anchor="mm",
              font=small, fill=rgb(colors["muted"]))
    image.save(OUT / "bezel-angle-{:03d}.png".format(degrees))
