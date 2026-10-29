"""Host checks for retained font setup and bounded BDF initialization."""

import sys
import types
import unittest
from unittest.mock import patch

from src.display.round_ui import display as round_display
from tests.test_displayio_textline import DisplayIO


class Font:
    def __init__(self):
        self.loaded = []

    def load_glyphs(self, codepoints):
        self.loaded.append(tuple(codepoints))


class RoundDisplayFontTests(unittest.TestCase):
    def tearDown(self):
        round_display._BITMAP_FONT_CACHE.clear()

    def test_font_glyphs_are_preloaded_once_per_cached_font(self):
        loaded = []

        def load_font(path):
            font = Font()
            loaded.append((path, font))
            return font

        package = types.SimpleNamespace(
            bitmap_font=types.SimpleNamespace(load_font=load_font))
        terminalio = types.SimpleNamespace(FONT=object())
        with patch.dict(sys.modules, {"adafruit_bitmap_font": package,
                                      "bitmaptools": None}):
            round_display._line(DisplayIO, terminalio, 68, 10, 0, 0)
            round_display._line(DisplayIO, terminalio, 68, 10, 0, 0)

        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0][0], "/fonts/DejaVuSans-10.bdf")
        self.assertEqual(len(loaded[0][1].loaded), 1)
        self.assertIn(ord(" "), loaded[0][1].loaded[0])

    def test_bdf_strike_is_shared_across_different_line_bounds(self):
        loaded = []

        def load_font(path):
            font = Font()
            loaded.append((path, font))
            return font

        package = types.SimpleNamespace(
            bitmap_font=types.SimpleNamespace(load_font=load_font))
        terminalio = types.SimpleNamespace(FONT=object())
        with patch.dict(sys.modules, {"adafruit_bitmap_font": package,
                                      "bitmaptools": None}):
            round_display._line(DisplayIO, terminalio, 150, 20, 0, 0,
                                scale=2)
            round_display._line(DisplayIO, terminalio, 160, 28, 0, 0,
                                scale=2)

        self.assertEqual([path for path, _ in loaded],
                         ["/fonts/DejaVuSans-Bold-14.bdf"])


if __name__ == "__main__":
    unittest.main()
