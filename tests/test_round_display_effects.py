import unittest

from src.display.round_ui.effects import (
    TOUCH_BITMAP_CENTER, TOUCH_BITMAP_SIZE, TOUCH_CORE, TOUCH_INNER,
    TOUCH_MIDDLE, TOUCH_OUTER, touch_level, touch_zone,
)


class TouchRippleGeometryTests(unittest.TestCase):
    def test_bitmap_size_and_ring_zones_are_centered(self):
        self.assertEqual(TOUCH_BITMAP_SIZE, 57)
        center = TOUCH_BITMAP_CENTER
        self.assertEqual(touch_zone(center, center), TOUCH_CORE)
        self.assertEqual(touch_zone(center + 2, center), TOUCH_CORE)
        self.assertEqual(touch_zone(center + 4, center), 0)
        self.assertEqual(touch_zone(center + 8, center), TOUCH_INNER)
        self.assertEqual(touch_zone(center + 16, center), TOUCH_MIDDLE)
        self.assertEqual(touch_zone(center + 26, center), TOUCH_OUTER)
        self.assertEqual(touch_zone(center + 12, center), 0)

    def test_contact_starts_visible_and_brightness_moves_outward(self):
        self.assertEqual(touch_level(TOUCH_CORE, 0.0), 100)
        self.assertGreater(touch_level(TOUCH_INNER, 0.0), 0)
        self.assertGreater(touch_level(TOUCH_MIDDLE, 0.0), 0)
        self.assertGreater(touch_level(TOUCH_OUTER, 0.0), 0)
        self.assertGreaterEqual(touch_level(TOUCH_OUTER, 0.0), 38)

        self.assertGreater(touch_level(TOUCH_INNER, 0.10),
                           touch_level(TOUCH_MIDDLE, 0.10))
        self.assertGreater(touch_level(TOUCH_MIDDLE, 0.48),
                           touch_level(TOUCH_INNER, 0.48))
        self.assertGreater(touch_level(TOUCH_OUTER, 0.78),
                           touch_level(TOUCH_MIDDLE, 0.78))

    def test_wave_brightness_clamps_progress(self):
        for index in range(1, 5):
            self.assertEqual(touch_level(index, -1.0),
                             touch_level(index, 0.0))
            self.assertEqual(touch_level(index, 2.0),
                             touch_level(index, 1.0))


if __name__ == "__main__":
    unittest.main()
