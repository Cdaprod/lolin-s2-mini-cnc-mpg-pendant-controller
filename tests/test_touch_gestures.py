"""Host-side tests for release-triggered safe round-screen touch gestures."""

import unittest
from src.input.touch_gestures import TouchGestures
from src.input.touch import TouchInput, CHSC6XTouchSource
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
        self.assertEqual(gestures.poll(None), (("release_select", 120, 120),))
        gestures.poll((125, 110))
        clock.t = 1.0
        self.assertEqual(gestures.poll(None), (("release_select", 125, 110),))

    def test_drag_previews_then_releases_into_selection(self):
        clock = Clock()
        gestures = TouchGestures(clock)
        self.assertEqual(gestures.poll((90, 65)), ())
        self.assertEqual(gestures.poll((90, 66)), (("drag", 90, 66),))
        self.assertEqual(gestures.poll((90, 87)), (("drag", 90, 87),))
        self.assertEqual(gestures.poll(None), (("release_select", 90, 87),))

    def test_top_level_swipes_change_page_only(self):
        state = PendantState()
        ui = UIManager(state)
        ui.complete_boot()
        self.assertEqual(ui.current_screen, "HOME")
        ui.handle(TouchEvent("swipe_left", 120, 110))
        self.assertEqual(ui.current_screen, "EXPLORER")
        self.assertEqual(state.active_page, "EXPLORER")
        ui.handle(TouchEvent("swipe_left", 120, 110))
        self.assertEqual(ui.current_screen, "CONFIGURATION")
        ui.handle(TouchEvent("swipe_right", 120, 110))
        self.assertEqual(ui.current_screen, "EXPLORER")
        ui.handle(TouchEvent("swipe_right", 120, 110))
        self.assertEqual(ui.current_screen, "HOME")

    def test_released_static_row_selects_but_machine_action_does_not(self):
        state = PendantState()
        ui = UIManager(state)
        ui.complete_boot()
        ui.enter("MAIN_MENU")
        ui.handle(TouchEvent("drag", 95, 87))
        self.assertEqual(ui.focus["MAIN_MENU"], 1)
        ui.handle(TouchEvent("release_select", 95, 87))
        self.assertEqual(ui.current_screen, "JOBS")
        ui.back()
        ui.handle(TouchEvent("release_select", 95, 65))
        self.assertEqual(ui.current_screen, "MACHINE")
        ui.handle(TouchEvent("release_select", 95, 65))
        self.assertIsNone(ui.confirmation)

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
        self.assertEqual(gestures.poll(None), (("release_select", 140, 136),))
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

    def test_chsc6x_irq_and_five_byte_packet(self):
        class I2C:
            locked = False
            reads = 0
            data = bytes((1, 0, 101, 0, 193))
            def try_lock(self):
                if self.locked:
                    return False
                self.locked = True
                return True
            def readfrom_into(self, address, buffer):
                self.reads += 1
                self.address = address
                buffer[:] = self.data
            def unlock(self):
                self.locked = False
        class IRQ:
            value = True
        bus, irq = I2C(), IRQ()
        touch = CHSC6XTouchSource(bus, irq)
        self.assertIsNone(touch.point())
        self.assertEqual(bus.reads, 0)
        irq.value = False
        self.assertEqual(touch.point(), (101, 193))
        self.assertEqual(bus.address, 0x2E)
        bus.data = bytes((0, 0, 101, 0, 193))
        self.assertIsNone(touch.point())
        bus.data = bytes((1, 0, 250, 0, 100))
        self.assertIsNone(touch.point())
        bus.locked = True
        self.assertIsNone(touch.point())

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
