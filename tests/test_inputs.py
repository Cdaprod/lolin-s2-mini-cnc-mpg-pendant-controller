import unittest

from src.input.buttons import ButtonMapper
from src.input.mpg import MPGDecoder
from src.input.selectors import SelectorError, SelectorModel
from src.state import PendantState


class MPGTests(unittest.TestCase):
    def decode(self, states):
        decoder = MPGDecoder(counts_per_detent=4)
        return [decoder.update(a, b) for a, b in states], decoder

    def test_clockwise_and_counterclockwise(self):
        events, _ = self.decode([(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)])
        self.assertEqual(events, [0, 0, 0, 0, 1])
        events, _ = self.decode([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
        self.assertEqual(events, [0, 0, 0, 0, -1])

    def test_malformed_transition_is_rejected(self):
        events, decoder = self.decode([(0, 0), (1, 1), (1, 0), (0, 0)])
        self.assertEqual(events, [0, 0, 0, 0])
        self.assertEqual(decoder.invalid_transitions, 1)

    def test_rate_limit_and_accumulation(self):
        decoder = MPGDecoder(2, min_event_interval=0.1)
        self.assertEqual(decoder.update(0, 0, 0.0), 0)
        self.assertEqual(decoder.update(0, 1, 0.01), 0)
        self.assertEqual(decoder.update(1, 1, 0.02), 1)
        self.assertEqual(decoder.update(1, 0, 0.03), 0)
        self.assertEqual(decoder.update(0, 0, 0.04), 0)


class SelectorTests(unittest.TestCase):
    def setUp(self):
        self.state = PendantState()
        self.selectors = SelectorModel(self.state)

    def test_axis_four_five_six_map_to_abc(self):
        self.assertEqual(self.selectors.select_axis("4"), "A")
        self.assertEqual(self.selectors.select_axis("5"), "B")
        self.assertEqual(self.selectors.select_axis("6"), "C")

    def test_multiplier_uses_ratio(self):
        self.assertAlmostEqual(self.selectors.select_multiplier("X1"), 0.001)
        self.assertAlmostEqual(self.selectors.select_multiplier("X10"), 0.010)
        self.assertAlmostEqual(self.selectors.select_multiplier("X100"), 0.100)

    def test_ambiguous_contacts_fail_axis_to_off(self):
        with self.assertRaises(SelectorError):
            self.selectors.update_contacts(["X", "Y"], ["X1"])
        self.assertIsNone(self.state.selected_axis)

    def test_contextual_button_mapping(self):
        buttons = ButtonMapper()
        self.assertEqual(buttons.action_for("ZERO"), "ZERO_AXIS")
        self.assertEqual(buttons.action_for("ZERO", True), "ZERO_XYZ")
