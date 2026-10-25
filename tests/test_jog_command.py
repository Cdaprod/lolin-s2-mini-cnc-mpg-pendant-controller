"""Bounds and injection regression cases for CNC MPG jog builder."""
import unittest
from src.controller.jog_command import build_jog


class JogCommandTests(unittest.TestCase):
    def test_axis_distance_feed_and_direction(self):
        self.assertEqual(build_jog("x", 0.01, 250),
                         b"$J=G91 G21 X0.010000 F250.000\n")
        self.assertEqual(build_jog("Z", -0.1, 50),
                         b"$J=G91 G21 Z-0.100000 F50.000\n")

    def test_invalid_inputs_fail_closed(self):
        for axis, distance, feed in (
            ("X\nM3", 0.01, 100),
            ("?", 0.01, 100),
            ("X", 0, 100),
            ("X", 2.0, 100),
            ("X", -2.0, 100),
            ("X", float("nan"), 100),
            ("X", float("inf"), 100),
            ("X", 0.01, float("inf")),
            ("X", 0.01, float("nan")),
            ("X", 0.01, 1001),
            ("X", 0.01, -1),
            ("X", "1\nM3", 100),
        ):
            with self.subTest(axis=axis, distance=distance, feed=feed):
                with self.assertRaises(ValueError):
                    build_jog(axis, distance, feed)


if __name__ == "__main__":
    unittest.main()
