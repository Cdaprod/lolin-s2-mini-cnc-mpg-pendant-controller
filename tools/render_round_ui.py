"""240px UI design snapshots, sourced from the production screen registry.

Preview approximations for design review, not pixel-identical DisplayIO captures.
The dots here depict the transient 1.6s state immediately after navigation.
"""
from pathlib import Path
import math
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageDraw, ImageFont
from src.display.round_ui import theme
from src.display.ui import build_screens
from src.display.navigation import menu_window_start

OUT = Path("reports/round-ui")
OUT.mkdir(parents=True, exist_ok=True)
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
for skin in ("industrial", "ice", "amber", "spectrum"):
    # Retain per-theme previews for color regression; also publish a page-
    # accurate composite showing the palette chosen by physical selector.
    c = theme.select(skin)
    for name in names:
        screen = screens[name]
        im = Image.new("RGB", (240, 240), c["background"])
        d = ImageDraw.Draw(im)
        d.ellipse((9, 9, 231, 231), outline=c["panel"], width=4)
        # Four physical top-level page positions; no pager at idle in firmware.
        page = {"EXPLORER": 1, "CONFIGURATION": 2, "PREVIEW": 3}.get(name, 0)
        # Snapshot at t=4 s to make both counter-rotating HUD markers visible.
        for radius, rate, color in (
                (109, 0.22, c["accent"]),
                (99, -0.20, c["highlight"])):
            angle = 4.0 * rate
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
                    d.point((cx + xx - 4, cy + yy - 4), fill=fill)
        for i in range(4):
            x = 67 + (106 * i) // 3
            y = 120 - int(math.sqrt(108 * 108 - (x - 120) ** 2))
            fill = 0xFFFFFF if i == page else 0x667176
            d.ellipse((x-3, y-3, x+3, y+3), fill=fill)
        if name == "HOME":
            d.text((120, 43), "READY", anchor="mm", font=large, fill=c["success"])
            d.text((120, 72), "X", anchor="mm", font=large, fill=c["accent"])
            d.text((120, 111), "+124.520", anchor="mm", font=large, fill=c["text"])
            d.text((120, 143), "WPOS  mm", anchor="mm", font=font, fill=c["muted"])
            d.text((120, 168), "X10", anchor="mm", font=large, fill=c["warning"])
            d.text((120, 194), "HOLD TO JOG", anchor="mm", font=small, fill=c["text"])
        else:
            title = screen.title
            while title and d.textbbox((0, 0), title, font=title_font)[2] > 166:
                title = title[:-1]
            d.text((120, 43), title, anchor="mm", font=title_font, fill=c["text"])
            d.line((44, 55, 196, 55), fill=c.get("separator", c["muted"]), width=1)
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
                                        fill=c["panel"], outline=c.get("focus_border", c["muted"]), width=1)
                    d.rounded_rectangle((30, y-4, 34, y+17), radius=2, fill=c["accent"])
                elif row:
                    d.line((37, y-7, 203, y-7), fill=c.get("separator", c["muted"]), width=1)
                available = 156
                label = str(label)
                while label and d.textbbox((0, 0), label, font=font)[2] > available:
                    label = label[:-2]
                    if not label.endswith("…"):
                        label += "…"
                d.text((43, y), label, font=font,
                       fill=c["text"] if enabled else c["muted"])
            d.text((120, 211), "BACK  ·  HOME", anchor="mm", font=small, fill=c["muted"])
        im.save(OUT / f"{skin}-{name.lower()}.png")

# Dedicated preview of each physical page in its assigned theme.
assigned = (("HOME", "industrial"), ("EXPLORER", "amber"),
            ("CONFIGURATION", "ice"), ("PREVIEW", "spectrum"))
page_sheet = Image.new("RGB", (1120, 310), "#15191D")
page_draw = ImageDraw.Draw(page_sheet)
heading = ImageFont.truetype(str(regular_source), 18)
for i, (screen, palette) in enumerate(assigned):
    x = 20 + i * 280
    preview = Image.open(OUT / f"{palette}-{screen.lower()}.png")
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
    im = Image.new("RGB", (240, 240), c["background"])
    d = ImageDraw.Draw(im)
    d.ellipse((9, 9, 231, 231), outline=c["panel"], width=4)
    d.text((120, 43), "FILE EXPLORER", anchor="mm", font=title_font,
           fill=c["text"])
    d.line((44, 55, 196, 55), fill=c["separator"], width=1)
    d.text((120, 129), primary, anchor="mm", font=font, fill=c["text"])
    d.text((120, 151), secondary, anchor="mm", font=small, fill=c["muted"])
    d.text((120, 211), "-  BACK  |  HOME", anchor="mm", font=small,
           fill=c["muted"])
    im.save(OUT / f"explorer-empty-{storage}.png")
