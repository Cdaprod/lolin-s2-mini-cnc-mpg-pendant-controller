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
    def test_orbit_marker_sheet_has_all_supersampled_subpixel_tiles(self):
        packed = generate_hud_bezels.orbit_phase_data()
        self.assertEqual(len(packed), 36 * 36 // 2)
        pixels = []
        for value in packed:
            pixels.extend((value & 0x0F, value >> 4))
        tiles = []
        for ty in range(4):
            for tx in range(4):
                tile = tuple(
                    pixels[(ty*9+y)*36 + tx*9+x]
                    for y in range(9) for x in range(9))
                self.assertTrue(any(tile))
                self.assertLessEqual(max(tile), 15)
                tiles.append(tile)
        self.assertEqual(len(set(tiles)), 16)
        self.assertEqual((ASSETS / "runtime" / "orbit_phases.4bpp").read_bytes(),
                         packed)

    def test_rotor_segments_have_orientation_and_subpixel_atlas(self):
        packed = generate_hud_bezels.rotor_segment_data()
        self.assertEqual(len(packed), 36 * 576 // 2)
        bitmap = (ASSETS / "runtime" / "rotor_segment_phases.4bpp")
        self.assertEqual(bitmap.read_bytes(), packed)
        # Read two 9x9 tiles at the same fractional position. Orientation
        # changes the capsule while retaining a shared indexed palette.
        pixels = []
        for value in packed:
            pixels.extend((value & 0x0F, value >> 4))

        def tile(orientation, phase_x=0, phase_y=0):
            tile_x = phase_x
            tile_y = orientation * 4 + phase_y
            return tuple(pixels[(tile_y * 9 + y) * 36 + tile_x * 9 + x]
                         for y in range(9) for x in range(9))

        self.assertTrue(any(tile(0)))
        self.assertNotEqual(tile(0), tile(4))
        self.assertNotEqual(tile(0), tile(0, 1, 0))

    def test_precomputed_orb_sheet_loads_without_runtime_geometry_sampling(self):
        calls = []

        class Bitmap:
            def __init__(self, width, height, colors):
                calls.append((width, height, colors))

        fake_displayio = type("DisplayIO", (), {"Bitmap": Bitmap})
        fake_bitmaptools = type("BitmapTools", (), {
            "readinto": staticmethod(lambda bitmap, source, bits_per_pixel:
                                      calls.append((bits_per_pixel,
                                                    len(source.read()))) )
        })
        with patch.dict("sys.modules", {"bitmaptools": fake_bitmaptools}), \
                patch("builtins.open", mock_open(read_data=b"x" * 648)):
            bitmap, frames = display._load_orb_sprite_sheet(fake_displayio)
        self.assertIsNotNone(bitmap)
        self.assertEqual(frames, 16)
        self.assertEqual(calls, [(36, 36, 16), (4, 648)])

    def test_precomputed_rotor_sheet_loads_without_runtime_geometry(self):
        calls = []

        class Bitmap:
            def __init__(self, width, height, colors):
                calls.append((width, height, colors))

        fake_displayio = type("DisplayIO", (), {"Bitmap": Bitmap})
        fake_bitmaptools = type("BitmapTools", (), {
            "readinto": staticmethod(lambda bitmap, source, bits_per_pixel:
                                      calls.append((bits_per_pixel,
                                                    len(source.read()))) )
        })
        with patch.dict("sys.modules", {"bitmaptools": fake_bitmaptools}), \
                patch("builtins.open", mock_open(read_data=b"x" * 10368)):
            bitmap, frames = display._load_rotor_sprite_sheet(fake_displayio)
        self.assertIsNotNone(bitmap)
        self.assertEqual(frames, 256)
        self.assertEqual(calls, [(36, 576, 16), (4, 10368)])

    def test_all_production_bezels_are_240px_4bpp_and_transparent(self):
        manifest = json.loads((ASSETS / "manifest.json").read_text())
        self.assertEqual(len(manifest["themes"]), 12)
        self.assertEqual(manifest["sprite_assets"][0]["bytes"], 648)
        self.assertEqual(manifest["sprite_assets"][1]["bytes"], 10368)
        self.assertEqual((ASSETS / "runtime" / "orbit_phases.4bpp").stat().st_size,
                         648)
        self.assertEqual((ASSETS / "runtime" / "rotor_segment_phases.4bpp").stat().st_size,
                         10368)
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

    def test_segmented_bezel_keeps_its_arc_gaps_dark(self):
        """Glow must not merge precision strokes into a solid annulus."""
        from PIL import Image
        import math
        image = Image.open(ASSETS / "development" / "cyan_reactor.png")
        alpha = image.getchannel("A")
        # At the 22.5 degree midpoint between the first two major arcs,
        # nothing should fill the gap at the outer ring radius.
        x = round(120 + 113 * math.cos(math.radians(-67.5)))
        y = round(120 + 113 * math.sin(math.radians(-67.5)))
        self.assertLessEqual(alpha.getpixel((x, y)), 8)
        # A corresponding arc core remains bright, proving the test catches
        # over-broad illumination without accepting a blank asset.
        self.assertGreaterEqual(alpha.getpixel((120, 7)), 180)

    def test_firmware_bitmap_palette_matches_the_generated_bezel_core(self):
        """Catch host arithmetic that corrupts the indexed device bitmap."""
        _, packed, palette = generate_hud_bezels.render(
            generate_hud_bezels.THEMES[0], supersample=8)
        self.assertEqual(
            packed,
            (ASSETS / "runtime" / "cyan_reactor.4bpp").read_bytes())
        # The segment centered at 12 o'clock must quantize to luminous cyan,
        # not an unrelated color caused by overflow in squared RGB distances.
        byte = packed[7 * 120 + 120 // 2]
        index = byte & 0x0F
        core = palette[index]
        primary = tuple(round(channel * 0.78 *
                              generate_hud_bezels.BEZEL_LUMINANCE)
                        for channel in generate_hud_bezels.THEMES[0][2])
        distance = sum(
            (channel - expected) ** 2
            for channel, expected in zip(
                ((core >> 16) & 255, (core >> 8) & 255, core & 255), primary))
        self.assertLess(distance, 22 ** 2)

    def test_decorative_palettes_stay_below_status_text_luminance(self):
        for name, palette in bezel_palette.PALETTES.items():
            with self.subTest(theme=name):
                self.assertLessEqual(
                    max(max((color >> 16) & 0xFF,
                            (color >> 8) & 0xFF, color & 0xFF)
                        for color in palette[1:]), 80)

    def test_default_bezel_keeps_negative_space_inside_the_ring(self):
        """The close-view default must not fill its center with dot noise."""
        _, packed, _ = generate_hud_bezels.render(
            generate_hud_bezels.THEMES[0], supersample=8)
        # A top-center sample on the old dense inner dot track is now clear.
        offset = 26 * 120 + 120 // 2
        self.assertEqual(packed[offset] & 0x0F, 0)

    def test_development_png_matches_indexed_firmware_colors(self):
        rgba, packed, palette = generate_hud_bezels.render(
            generate_hud_bezels.THEMES[0], supersample=4)
        pixels = rgba.load()
        for y, x in ((0, 0), (7, 120), (120, 120), (120, 8), (232, 120)):
            byte = packed[y * 120 + x // 2]
            index = (byte & 0x0F) if x % 2 == 0 else (byte >> 4)
            color = palette[index]
            expected = ((color >> 16) & 0xFF, (color >> 8) & 0xFF,
                        color & 0xFF, 0 if index == 0 else 255)
            self.assertEqual(pixels[x, y], expected)

    def test_runtime_deployment_includes_only_generated_bitmap_assets(self):
        files = deploy.runtime_files()
        bezels = [path for path in files
                  if path.startswith("assets/round_hud/")]
        self.assertEqual(len(bezels), 14)
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
