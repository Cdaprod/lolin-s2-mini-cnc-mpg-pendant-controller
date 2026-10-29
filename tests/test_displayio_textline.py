"""Host checks for the bounded text raster path used by the round display."""

import sys
import types
import unittest
from unittest.mock import patch

from src.display.displayio_backend import _DisplayIOTextLine


class Bitmap:
    def __init__(self, width, height, value_count):
        self.width, self.height = width, height
        self.pixels = [[0] * width for _ in range(height)]

    def fill(self, value):
        for row in self.pixels:
            row[:] = [value] * self.width

    def __getitem__(self, point):
        x, y = point
        return self.pixels[y][x]

    def __setitem__(self, point, value):
        x, y = point
        if 0 <= x < self.width and 0 <= y < self.height:
            self.pixels[y][x] = value


class Palette:
    def __init__(self, count):
        self.values = [None] * count

    def __setitem__(self, index, value):
        self.values[index] = value

    def make_transparent(self, index):
        pass


class TileGrid:
    def __init__(self, bitmap, pixel_shader):
        self.bitmap = bitmap
        self.pixel_shader = pixel_shader


class Glyph:
    width = 2
    height = 2
    shift_x = 2
    dx = 0
    dy = 0

    def __init__(self, bitmap, tile_index):
        self.bitmap = bitmap
        self.tile_index = tile_index


class Font:
    def __init__(self):
        self.atlas = Bitmap(4, 2, 2)
        # Two 2x2 glyph tiles in one atlas.
        self.atlas[0, 0] = 1
        self.atlas[1, 1] = 1
        self.atlas[3, 0] = 1
        self.atlas[2, 1] = 1

    def get_glyph(self, codepoint):
        if codepoint == ord(" "):
            return GlyphWithNoBitmap()
        return Glyph(self.atlas, 0 if codepoint == ord("A") else 1)


class GlyphWithNoBitmap:
    width = 3
    height = 0
    shift_x = 3
    tile_index = 0

    @property
    def bitmap(self):
        raise AssertionError("blank glyph bitmap must not be accessed")


class DisplayIO:
    Bitmap = Bitmap
    Palette = Palette
    TileGrid = TileGrid


def bitmaptools_blit(dest, source, x, y, *, x1=0, y1=0, x2=None, y2=None,
                     skip_source_index=None, skip_dest_index=None):
    x2 = source.width if x2 is None else x2
    y2 = source.height if y2 is None else y2
    for sy in range(y1, y2):
        for sx in range(x1, x2):
            value = source[sx, sy]
            if value == skip_source_index:
                continue
            dest[x + sx - x1, y + sy - y1] = value


class DisplayIOTextLineTests(unittest.TestCase):
    def render(self, use_native_blit, centered=False):
        module = types.SimpleNamespace(blit=bitmaptools_blit)
        modules = {"bitmaptools": module} if use_native_blit else {
            "bitmaptools": None
        }
        with patch.dict(sys.modules, modules):
            line = _DisplayIOTextLine(
                6, 2, Font(), DisplayIO, centered=centered)
        line.set_text("AB")
        return line.bitmap.pixels, line._bitmap_blit is not None

    def test_native_blit_matches_python_fallback_pixels(self):
        native, used_native = self.render(True)
        fallback, used_native_fallback = self.render(False)
        self.assertTrue(used_native)
        self.assertFalse(used_native_fallback)
        self.assertEqual(native, fallback)
        self.assertEqual(native, [[1, 0, 0, 1, 0, 0],
                                  [0, 1, 1, 0, 0, 0]])

    def test_centered_text_keeps_expected_centering(self):
        pixels, _ = self.render(True, centered=True)
        self.assertEqual(pixels, [[0, 1, 0, 0, 1, 0],
                                  [0, 0, 1, 1, 0, 0]])

    def test_native_blit_preserves_clear_and_skip_repeated_text(self):
        module = types.SimpleNamespace(blit=bitmaptools_blit)
        with patch.dict(sys.modules, {"bitmaptools": module}):
            line = _DisplayIOTextLine(6, 2, Font(), DisplayIO)
        line.set_text("AB")
        self.assertFalse(line.set_text("AB"))
        line.set_text("A")
        self.assertEqual(line.bitmap.pixels,
                         [[1, 0, 0, 0, 0, 0], [0, 1, 0, 0, 0, 0]])

    def test_zero_height_space_uses_advance_without_reading_bitmap(self):
        module = types.SimpleNamespace(blit=bitmaptools_blit)
        with patch.dict(sys.modules, {"bitmaptools": module}):
            line = _DisplayIOTextLine(8, 2, Font(), DisplayIO)
        line.set_text("A A")
        self.assertEqual(line.bitmap.pixels,
                         [[1, 0, 0, 0, 0, 1, 0, 0],
                          [0, 1, 0, 0, 0, 0, 1, 0]])

    def test_bitmap_font_side_bearings_and_baselines_are_respected(self):
        class OffsetGlyph:
            def __init__(self, height, dx, dy):
                self.bitmap = Bitmap(1, height, 2)
                for y in range(height):
                    self.bitmap[0, y] = 1
                self.width = 1
                self.height = height
                self.shift_x = 2
                self.dx = dx
                self.dy = dy
                self.tile_index = 0

        class OffsetFont:
            def get_bounding_box(self):
                return 3, 4, 0, -1

            def get_glyph(self, codepoint):
                if codepoint == ord("A"):
                    return OffsetGlyph(2, 0, 0)
                return OffsetGlyph(3, -1, -2)

        module = types.SimpleNamespace(blit=bitmaptools_blit)
        with patch.dict(sys.modules, {"bitmaptools": module}):
            line = _DisplayIOTextLine(4, 5, OffsetFont(), DisplayIO)
        line.set_text("Ag")
        self.assertEqual(line.bitmap.pixels, [
            [0, 0, 0, 0],
            [1, 0, 0, 0],
            [1, 1, 0, 0],
            [0, 1, 0, 0],
            [0, 1, 0, 0],
        ])


if __name__ == "__main__":
    unittest.main()
