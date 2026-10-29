import unittest

from src.display.round_ui.effects import (
    TOUCH_BITMAP_CENTER, TOUCH_BITMAP_SIZE, TOUCH_CORE, TOUCH_INNER,
    TOUCH_CORE_EDGE, TOUCH_HOLD_PROGRESS, TOUCH_INNER_EDGE,
    TOUCH_MIDDLE, TOUCH_MIDDLE_EDGE, TOUCH_OUTER,
    TOUCH_PALETTE_SIZE, touch_level, touch_zone,
)


class TouchRippleGeometryTests(unittest.TestCase):
    def test_bitmap_size_and_ring_zones_are_centered(self):
        self.assertEqual(TOUCH_BITMAP_SIZE, 25)
        center = TOUCH_BITMAP_CENTER
        self.assertEqual(touch_zone(center, center), TOUCH_CORE)
        self.assertEqual(touch_zone(center + 1, center), TOUCH_CORE)
        self.assertEqual(touch_zone(center + 2, center), TOUCH_CORE_EDGE)
        self.assertEqual(touch_zone(center + 3, center), TOUCH_INNER)
        self.assertEqual(touch_zone(center + 6, center), TOUCH_MIDDLE)
        self.assertEqual(touch_zone(center + 10, center), TOUCH_OUTER)
        self.assertEqual(touch_zone(center + 8, center), TOUCH_MIDDLE_EDGE)

    def test_contact_starts_visible_and_brightness_moves_outward(self):
        self.assertEqual(touch_level(TOUCH_CORE, 0.0), 100)
        self.assertGreater(touch_level(TOUCH_INNER, 0.0), 0)
        self.assertEqual(touch_level(TOUCH_MIDDLE, 0.0), 0)
        self.assertEqual(touch_level(TOUCH_OUTER, 0.0), 0)

        self.assertGreater(touch_level(TOUCH_INNER, 0.10),
                           touch_level(TOUCH_MIDDLE, 0.10))
        self.assertGreater(touch_level(TOUCH_MIDDLE, 0.48),
                           touch_level(TOUCH_INNER, 0.48))
        self.assertGreater(touch_level(TOUCH_OUTER, 0.78),
                           touch_level(TOUCH_MIDDLE, 0.78))

    def test_compact_release_phase_does_not_reach_outer_ring(self):
        held = TOUCH_HOLD_PROGRESS
        self.assertEqual(touch_level(TOUCH_CORE, held), 0)
        self.assertGreater(touch_level(TOUCH_INNER, held), 30)
        self.assertGreater(touch_level(TOUCH_MIDDLE, held), 40)
        self.assertEqual(touch_level(TOUCH_OUTER, held), 0)
        self.assertGreater(touch_level(TOUCH_INNER, held),
                           touch_level(TOUCH_INNER_EDGE, held))
        self.assertGreater(touch_level(TOUCH_MIDDLE, held),
                           touch_level(TOUCH_MIDDLE_EDGE, held))

    def test_wave_brightness_clamps_progress(self):
        for index in range(1, TOUCH_PALETTE_SIZE):
            self.assertEqual(touch_level(index, -1.0),
                             touch_level(index, 0.0))
            self.assertEqual(touch_level(index, 2.0),
                             touch_level(index, 1.0))


if __name__ == "__main__":
    unittest.main()
