"""Deterministic 240x240 UI snapshots using production screen registry.

Host rasterizer is a visual approximation of the displayio scene, not a
hardware framebuffer capture. Screen labels/items are read from build_screens.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageDraw, ImageFont
from src.display.round_ui import theme
from src.display.ui import build_screens

OUT = Path("reports/round-ui")
OUT.mkdir(parents=True, exist_ok=True)
screens = build_screens()
names = ["HOME", "MAIN_MENU", "MACHINE", "JOBS", "JOB_BROWSER",
         "ACTIVE_JOB", "EXPLORER", "CONFIGURATION", "CONTROLLER",
         "NETWORK", "SETTINGS", "SYSTEM", "SYSTEM_INFO", "PREVIEW"]
font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 17)
for skin in ("industrial", "ice", "amber", "spectrum"):
    c = theme.select(skin)
    for name in names:
        screen = screens[name]
        im = Image.new("RGB", (240, 240), c["background"])
        d = ImageDraw.Draw(im)
        d.ellipse((9, 9, 231, 231), outline=c["panel"], width=5)
        d.arc((19, 19, 221, 221), 198, 255, fill=c["accent"], width=3)
        d.arc((19, 19, 221, 221), 285, 340, fill=c["warning"], width=3)
        if name == "HOME":
            d.text((120, 36), "READY", anchor="mm", font=large, fill=c["success"])
            d.text((120, 70), "X", anchor="mm", font=large, fill=c["accent"])
            d.text((120, 112), "+124.520", anchor="mm", font=large, fill=c["text"])
            d.text((120, 143), "WPOS  mm", anchor="mm", font=font, fill=c["muted"])
            d.text((120, 167), "X10", anchor="mm", font=large, fill=c["warning"])
            d.text((120, 194), "HOLD TO JOG", anchor="mm", font=font, fill=c["accent"])
        else:
            d.text((120, 39), screen.title[:20], anchor="mm", font=large, fill=c["accent"])
            items = screen.items
            if not items:
                items = []
                if screen.dynamic == "jobs":
                    items = ["demo.nc", "calibration.nc", "examples/"]
                elif name == "SYSTEM_INFO":
                    items = ["Board: XIAO S3", "Display: 240x240", "Touch: CST8XX", "I2C: enabled", "SD: available"]
                elif name == "PREVIEW":
                    items = ["DEMO / PREVIEW", "No machine action"]
                else:
                    items = ["No items"]
            for i, item in enumerate(items[:6]):
                label = item.label if hasattr(item, "label") else item
                y = 62 + 22 * i
                if i == 0:
                    d.rounded_rectangle((31, y - 3, 209, y + 16), 5, fill=c["highlight"])
                d.text((39, y), str(label)[:25], font=font,
                       fill=c["text"] if getattr(item, "enabled", True) else c["muted"])
            d.text((120, 208), "BACK  |  HOME", anchor="mm", font=font, fill=c["muted"])
        im.save(OUT / f"{skin}-{name.lower()}.png")
print(f"Generated {len(names)*4} UI snapshot PNGs in {OUT}")
