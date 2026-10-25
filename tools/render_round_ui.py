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
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 17)
for skin in ("industrial", "ice", "amber", "spectrum"):
    c = theme.select(skin)
    for name in names:
        screen = screens[name]
        im = Image.new("RGB", (240, 240), c["background"])
        d = ImageDraw.Draw(im)
        d.ellipse((9, 9, 231, 231), outline=c["panel"], width=4)
        # Four physical top-level page positions; no pager at idle in firmware.
        page = {"EXPLORER": 1, "CONFIGURATION": 2, "PREVIEW": 3}.get(name, 0)
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
            title = screen.title[:20]
            if d.textbbox((0, 0), title, font=font)[2] > 165:
                title = title[:17]
            d.text((120, 43), title, anchor="mm", font=font, fill=c["text"])
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
                                        fill=c["panel"], outline=c["accent"], width=1)
                    d.rounded_rectangle((30, y-4, 34, y+17), radius=2, fill=c["accent"])
                elif row:
                    d.line((37, y-7, 203, y-7), fill=c.get("separator", c["muted"]), width=1)
                available = 150
                label = str(label)
                while label and d.textbbox((0, 0), label, font=font)[2] > available:
                    label = label[:-2]
                    if not label.endswith("…"):
                        label += "…"
                d.text((43, y), label, font=font,
                       fill=c["text"] if enabled else c["muted"])
            d.text((120, 211), "BACK  ·  HOME", anchor="mm", font=small, fill=c["muted"])
        im.save(OUT / f"{skin}-{name.lower()}.png")
print(f"Generated {len(names)*4} navigation-aware round UI design previews in {OUT}")
