"""Host-side tests for release-triggered safe round-screen touch gestures."""

import unittest
from src.input.touch_gestures import TouchGestures
from src.input.touch import TouchInput
from src.display.ui import TouchEvent, UIManager
from src.state import PendantState


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class Source:
    def __init__(self):
        self.current = None

    def point(self):
        return self.current


class GestureTests(unittest.TestCase):
    def test_tap_and_hold(self):
        clock = Clock()
        gestures = TouchGestures(clock)
        self.assertEqual(gestures.poll((120, 120)), ())
        clock.t = .10
        self.assertEqual(gestures.poll(None), (("tap", 120, 120),))
        gestures.poll((125, 110))
        clock.t = 1.0
        self.assertEqual(gestures.poll(None), (("long_press", 125, 110),))

    def test_directional_swipes(self):
        for end, expected in [((120, 20), "swipe_up"),
                              ((120, 200), "swipe_down"),
                              ((30, 120), "swipe_left"),
                              ((205, 120), "swipe_right")]:
            gestures = TouchGestures(Clock())
            self.assertEqual(gestures.poll((120, 120)), ())
            self.assertEqual(gestures.poll(end), ())
            self.assertEqual(gestures.poll(None)[0][0], expected)

    def test_no_unexpected_release_or_movement_action(self):
        gestures = TouchGestures(Clock())
        self.assertEqual(gestures.poll(None), ())
        gestures.poll((120, 120))
        gestures.poll((140, 136))
        self.assertEqual(gestures.poll(None), ())
        self.assertEqual(gestures.poll((-5, 20)), ())

    def test_touch_transform_and_counting(self):
        clock, source = Clock(), Source()
        touch = TouchInput(source, clock, rotation=90, invert_y=True)
        source.current = (10, 20)
        self.assertEqual(touch.poll(), ())
        source.current = None
        events = touch.poll()
        self.assertEqual((events[0].kind, events[0].x, events[0].y),
                         ("tap", 219, 229))
        self.assertEqual(touch.event_count, 1)
        self.assertEqual(touch.sample_count, 1)

    def test_touch_poll_failure_is_recorded_and_recovery_clears_error(self):
        clock = Clock()
        class FailingSource:
            broken = True
            def point(self):
                if self.broken:
                    raise OSError("I2C unavailable")
                return None
        source = FailingSource()
        touch = TouchInput(source, clock)
        for _ in range(3):
            self.assertEqual(touch.poll(), ())
        self.assertEqual(touch.consecutive_errors, 3)
        self.assertEqual(touch.last_error, "OSError")
        source.broken = False
        self.assertEqual(touch.poll(), ())
        self.assertEqual(touch.consecutive_errors, 0)
        self.assertIsNone(touch.last_error)

    def test_touch_never_recovers_estop(self):
        state = PendantState()
        ui = UIManager(state)
        ui.complete_boot()
        state.estop_latched = True
        state.estop_observed = False
        self.assertIsNone(ui.handle(TouchEvent("long_press", 120, 120)))
        self.assertTrue(state.estop_latched)


if __name__ == "__main__":
    unittest.main()
