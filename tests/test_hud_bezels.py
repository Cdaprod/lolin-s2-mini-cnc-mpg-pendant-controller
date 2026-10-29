import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import mock_open, patch

from tools import deploy, generate_hud_bezels
from src.display.round_ui import bezel_palette, display


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "round_hud"


class AssetPipelineTests(unittest.TestCase):
    def test_all_production_bezels_are_240px_4bpp_and_transparent(self):
        manifest = json.loads((ASSETS / "manifest.json").read_text())
        self.assertEqual(len(manifest["themes"]), 12)
        self.assertEqual(manifest["target"], [240, 240])
        names = set()
        for item in manifest["themes"]:
            name = item["name"]
            names.add(name)
            self.assertEqual(item["width"], 240)
            self.assertEqual(item["height"], 240)
            self.assertEqual(item["palette_entries"], 16)
            self.assertEqual(item["transparent_index"], 0)
            self.assertEqual(item["bytes"], 240 * 240 // 2)
            data = (ROOT / item["file"]).read_bytes()
            self.assertEqual(len(data), 28800)
            png = ROOT / item["development_png"]
            from PIL import Image
            image = Image.open(png).convert("RGBA")
            self.assertEqual(image.size, (240, 240))
            import numpy as np
            alpha = np.asarray(image.getchannel("A"))
            y, x = np.indices(alpha.shape)
            radius = np.hypot(x-120, y-120)
            self.assertEqual(int(alpha[radius < 87].max()), 0)
            self.assertEqual(int(alpha[radius > 119].max()), 0)
            self.assertEqual(len(bezel_palette.PALETTES[name]), 16)
        self.assertEqual(len(names), 12)

    def test_runtime_deployment_includes_only_generated_bitmap_assets(self):
        files = deploy.runtime_files()
        bezels = [path for path in files
                  if path.startswith("assets/round_hud/")]
        self.assertEqual(len(bezels), 12)
        self.assertTrue(all(path.endswith(".4bpp") for path in bezels))
        self.assertFalse(deploy.managed_path(
            "assets/round_hud/development/cyan_reactor.png"))
        self.assertTrue(deploy.managed_path(
            "assets/round_hud/runtime/cyan_reactor.4bpp"))
        self.assertFalse(deploy.managed_path(
            "assets/round_hud/runtime/../../settings.toml"))

    def test_selected_bezel_loads_with_four_bit_decoder_and_transparent_zero(self):
        calls = []

        class Bitmap:
            def __init__(self, width, height, colors):
                calls.append(("bitmap", width, height, colors))

        class Palette:
            def __init__(self, count):
                self.values = [0] * count

            def __setitem__(self, index, value):
                self.values[index] = value

            def make_transparent(self, index):
                calls.append(("transparent", index))

        fake_displayio = type("DisplayIO", (), {
            "Bitmap": Bitmap, "Palette": Palette,
        })
        fake_bitmaptools = type("BitmapTools", (), {
            "readinto": staticmethod(
                lambda bitmap, source, bits_per_pixel: calls.append(
                    ("readinto", bits_per_pixel, source.read())))
        })
        with patch.dict("sys.modules", {"bitmaptools": fake_bitmaptools}), \
                patch("builtins.open", mock_open(read_data=b"asset")):
            bitmap, palette = display._load_bezel(
                fake_displayio, "cyan_reactor")
        self.assertIsNotNone(bitmap)
        self.assertEqual(calls[0], ("bitmap", 240, 240, 16))
        self.assertEqual(calls[1], ("readinto", 4, b"asset"))
        self.assertEqual(calls[-1], ("transparent", 0))
        self.assertEqual(len(palette.values), 16)

    def test_unknown_or_missing_asset_uses_legacy_scene_fallback(self):
        self.assertEqual(display._load_bezel(object(), "untrusted-name"),
                         (None, None))
        with patch.dict("sys.modules", {"bitmaptools": object()}), \
                patch("builtins.open", side_effect=OSError("missing")):
            class DisplayIO:
                Bitmap = lambda self, *args: object()
            self.assertEqual(display._load_bezel(DisplayIO(), "cyan_reactor"),
                             (None, None))

    def test_generator_is_deterministic_at_four_times_supersampling(self):
        theme = generate_hud_bezels.THEMES[0]
        first = generate_hud_bezels.render(theme, supersample=4)
        second = generate_hud_bezels.render(theme, supersample=4)
        self.assertEqual(first[1], second[1])
        self.assertEqual(first[0].tobytes(), second[0].tobytes())
        self.assertEqual(first[0].size, (240, 240))


if __name__ == "__main__":
    unittest.main()
