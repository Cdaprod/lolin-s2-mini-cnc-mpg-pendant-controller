import unittest

from src.input.buttons import ButtonMapper
from src.input.mpg import MPGDecoder
from src.input.manager import InputManager, SyntheticInputAdapter
from src.input.selectors import SelectorError, SelectorModel
from src.state import PendantState
from src.input.touch import TouchInput
from src.display.ui import ROTATE_CW, TouchEvent


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

    def test_selector_change_discards_encoder_delta_from_same_poll(self):
        state = PendantState()
        adapter = SyntheticInputAdapter()
        manager = InputManager(state, adapter, counts_per_detent=4)
        adapter.set(axes=("X",), multipliers=("X1",), mpg_delta=0)
        manager.poll(0)

        adapter.set(axes=("4",), multipliers=("X10",), deadman=True,
                    mpg_delta=4)
        result = manager.poll(1)

        self.assertEqual(state.selected_axis, "A")
        self.assertEqual(state.jog_increment, 0.01)
        self.assertEqual(result.events, [])
        self.assertEqual(result.mpg_activity, 0)

    def test_selector_change_clears_partial_encoder_counts(self):
        state = PendantState()
        adapter = SyntheticInputAdapter()
        manager = InputManager(state, adapter, counts_per_detent=4)
        adapter.set(axes=("X",), multipliers=("X1",), mpg_delta=0)
        manager.poll(0)
        adapter.set(mpg_delta=2)
        self.assertEqual(manager.poll(1).events, [])
        self.assertEqual(manager.hardware_accumulator, 2)

        adapter.set(axes=("4",), mpg_delta=0)
        transition = manager.poll(2)
        self.assertEqual(transition.events, [])
        self.assertEqual(manager.hardware_accumulator, 0)
        adapter.set(mpg_delta=2)
        self.assertEqual(manager.poll(3).events, [])

    def test_transport_reset_discards_partial_and_first_recovery_sample(self):
        state = PendantState()
        adapter = SyntheticInputAdapter()
        manager = InputManager(state, adapter, counts_per_detent=4)
        adapter.set(axes=("X",), multipliers=("X1",), mpg_delta=0)
        manager.poll(0)
        adapter.set(mpg_delta=2)
        self.assertEqual(manager.poll(1).events, [])
        manager.reset_encoder()
        self.assertEqual(manager.hardware_accumulator, 0)

        adapter.set(mpg_delta=2)
        self.assertEqual(manager.poll(2).events, [])
        self.assertEqual(manager.hardware_accumulator, 0)
        adapter.set(mpg_delta=2)
        self.assertEqual(manager.poll(3).events, [])
        adapter.set(mpg_delta=2)
        self.assertEqual(manager.poll(4).events, [ROTATE_CW])

    def test_selector_transition_resets_partial_quadrature_detent(self):
        state = PendantState()
        adapter = SyntheticInputAdapter()
        manager = InputManager(state, adapter, counts_per_detent=4)
        adapter.set(axes=("X",), multipliers=("X1",), mpg_a=0, mpg_b=0)
        manager.poll(0)
        adapter.set(mpg_a=0, mpg_b=1)
        self.assertEqual(manager.poll(1).events, [])
        self.assertEqual(manager.decoder.accumulator, 1)

        adapter.set(axes=("4",), mpg_a=1, mpg_b=1)
        self.assertEqual(manager.poll(2).events, [])
        self.assertEqual(manager.decoder.accumulator, 0)
        for now, pins in enumerate(((1, 0), (0, 0), (0, 1)), 3):
            adapter.set(mpg_a=pins[0], mpg_b=pins[1])
            self.assertEqual(manager.poll(now).events, [])
        adapter.set(mpg_a=1, mpg_b=1)
        self.assertEqual(manager.poll(6).events, [ROTATE_CW])


class SelectorTests(unittest.TestCase):
    def setUp(self):
        self.state = PendantState()
        self.selectors = SelectorModel(self.state)

    def test_fourth_axis_selector_maps_to_a_axis(self):
        self.assertEqual(self.selectors.select_axis("4"), "AXIS_A")
        self.assertEqual(self.state.selected_axis, "A")
        self.assertEqual(self.state.active_page, "OPERATIONAL")

    def test_five_and_six_selector_positions_remain_safe_pages(self):
        self.assertEqual(self.selectors.select_axis("5"), "CONFIG")
        self.assertEqual(self.state.active_page, "CONFIGURATION")
        self.assertEqual(self.selectors.select_axis("6"), "PREVIEW")
        self.assertEqual(self.state.active_page, "PREVIEW")

    def test_six_axis_profile_can_restore_abc_without_rewiring(self):
        selectors = SelectorModel(
            self.state, {"4": "AXIS_A", "5": "AXIS_B", "6": "AXIS_C"})
        for physical, logical in (("4", "A"), ("5", "B"), ("6", "C")):
            self.assertEqual(selectors.select_axis(physical), "AXIS_" + logical)
            self.assertEqual(self.state.selected_axis, logical)

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


class FakeTouch:
    def __init__(self, points):
        self.points = list(points)
        self.last = None

    def point(self):
        point = self.points.pop(0) if self.points else None
        if point is not None:
            self.last = point
        return point

    def last_point(self):
        return self.last


class TouchTests(unittest.TestCase):
    def test_tap_is_normalized_without_semantic_action(self):
        now = [0.0]
        touch = TouchInput(FakeTouch(((100, 80), None)), lambda: now[0])
        self.assertEqual(touch.poll(), ())
        now[0] = 0.1
        self.assertEqual(touch.poll(), ())
        now[0] = 0.2
        event = touch.poll()[0]
        self.assertIsInstance(event, TouchEvent)
        self.assertEqual((event.kind, event.x, event.y), ("release_select", 100, 80))

    def test_vertical_motion_is_normalized_as_navigation(self):
        now = [0.0]
        source = FakeTouch(((100, 160), (100, 80), None))
        touch = TouchInput(source, lambda: now[0])
        touch.poll()
        now[0] = 0.1
        touch.poll()
        self.assertEqual(touch.poll(), ())
        now[0] = 0.2
        event = touch.poll()[0]
        self.assertIsInstance(event, TouchEvent)
        self.assertEqual(event.kind, "swipe_up")
