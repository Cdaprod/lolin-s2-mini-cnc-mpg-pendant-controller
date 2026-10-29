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


class FlakySource(Source):
    def __init__(self):
        super().__init__()
        self.fail = False

    def point(self):
        if self.fail:
            raise OSError("temporary I2C read failure")
        return self.current


class GestureTests(unittest.TestCase):
    def test_touch_contact_diagnostics_report_coordinates_and_ignore_read_errors(self):
        clock = Clock()
        source = FlakySource()
        touch = TouchInput(source, clock)

        source.current = (90, 65)
        self.assertEqual(touch.poll(), ())
        self.assertEqual(touch.last_contact_transition, ("down", 90, 65))

        clock.t = .04
        source.fail = True
        self.assertEqual(touch.poll(), ())
        self.assertIsNone(touch.last_contact_transition)
        self.assertTrue(touch.gestures.active)

        source.fail = False
        source.current = None
        clock.t = .05
        self.assertEqual(touch.poll(), ())
        self.assertIsNone(touch.last_contact_transition)
        clock.t = .13
        event = touch.poll()[0]
        self.assertEqual((event.kind, event.x, event.y),
                         ("release_select", 90, 65))
        self.assertEqual(touch.last_contact_transition, ("up", 90, 65))

    def test_tap_and_hold(self):
        clock = Clock()
        gestures = TouchGestures(clock)
        self.assertEqual(gestures.poll((120, 120)), ())
        clock.t = .10
        self.assertEqual(gestures.poll(None), ())
        clock.t = .20
        self.assertEqual(gestures.poll(None), (("release_select", 120, 120),))
        clock.t = .50
        gestures.poll((125, 110))
        clock.t = 1.0
        self.assertEqual(gestures.poll(None), ())
        clock.t = 1.10
        self.assertEqual(gestures.poll(None), (("release_select", 125, 110),))

    def test_drag_previews_then_releases_into_selection(self):
        clock = Clock()
        gestures = TouchGestures(clock)
        self.assertEqual(gestures.poll((90, 65)), ())
        self.assertEqual(gestures.poll((90, 66)), ())
        self.assertEqual(gestures.poll((90, 87)), (("drag", 90, 87),))
        self.assertEqual(gestures.poll(None), ())
        clock.t = .10
        self.assertEqual(gestures.poll(None), ())  # short contact is ignored

    def test_sensor_dropout_does_not_release_or_change_page(self):
        clock = Clock()
        gestures = TouchGestures(clock)
        gestures.poll((120, 120))
        clock.t = .08
        self.assertEqual(gestures.poll(None), ())
        clock.t = .11
        self.assertEqual(gestures.poll((115, 120)), ())
        clock.t = .20
        self.assertEqual(gestures.poll(None), ())
        clock.t = .30
        self.assertEqual(gestures.poll(None), (("release_select", 115, 120),))

    def test_tap_release_is_confirmed_within_40ms(self):
        clock = Clock()
        gestures = TouchGestures(clock)
        gestures.poll((120, 120))
        clock.t = .10
        gestures.poll(None)
        clock.t = .139
        self.assertEqual(gestures.poll(None), ())
        clock.t = .14
        self.assertEqual(gestures.poll(None),
                         (("release_select", 120, 120),))

    def test_short_contact_and_navigation_cooldown(self):
        clock = Clock()
        gestures = TouchGestures(clock)
        gestures.poll((120, 120))
        clock.t = .02
        gestures.poll(None)
        clock.t = .12
        self.assertEqual(gestures.poll(None), ())
        gestures.poll((120, 120))
        clock.t = .20
        self.assertEqual(gestures.poll(None), ())
        clock.t = .46
        gestures.poll((120, 120))
        clock.t = .55
        gestures.poll(None)
        clock.t = .65
        self.assertEqual(gestures.poll(None), (("release_select", 120, 120),))

    def test_jitter_and_diagonal_motion_never_select(self):
        clock = Clock()
        gestures = TouchGestures(clock)
        gestures.poll((100, 66))
        clock.t = .10
        self.assertEqual(gestures.poll((114, 79)), ())
        clock.t = .20
        gestures.poll(None)
        clock.t = .30
        self.assertEqual(gestures.poll(None), (("release_select", 114, 79),))
        clock.t = .60
        gestures.poll((100, 90))
        clock.t = .70
        gestures.poll((143, 135))
        clock.t = .80
        gestures.poll(None)
        clock.t = .90
        self.assertEqual(gestures.poll(None), ())

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

    def test_vertical_touch_swipe_only_moves_menu_focus_never_jogs(self):
        state = PendantState()
        ui = UIManager(state)
        ui.complete_boot()
        ui.enter("MAIN_MENU")
        ui.focus["MAIN_MENU"] = 0
        before = ui.focus["MAIN_MENU"]
        result = ui.handle(TouchEvent("swipe_down", 100, 130))
        self.assertIsNone(result)
        self.assertEqual(ui.focus["MAIN_MENU"], 3)
        self.assertNotEqual(ui.focus["MAIN_MENU"], before)
        ui.home()
        state.connection_state = "connected"
        ui.refresh_context()
        self.assertIsNone(ui.handle(TouchEvent("swipe_down", 100, 130)))
        self.assertEqual(ui.current_screen, "HOME")

    def test_physical_release_select_on_home_opens_menu_without_motion(self):
        state = PendantState()
        state.connection_state = "connected"
        ui = UIManager(state)
        ui.complete_boot()
        ui.refresh_context()
        clock, source = Clock(), Source()
        touch = TouchInput(source, clock)
        source.current = (120, 120)
        self.assertEqual(touch.poll(), ())
        clock.t = .10
        source.current = None
        self.assertEqual(touch.poll(), ())
        clock.t = .20
        event = touch.poll()[0]
        self.assertEqual(event.kind, "release_select")
        self.assertIsNone(ui.handle(event))
        self.assertEqual(ui.current_screen, "MAIN_MENU")

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
        result = ui.handle(TouchEvent("release_select", 95, 65))
        self.assertIsNone(result)
        self.assertEqual(ui.confirmation["command"], "ACTION")
        self.assertFalse(ui.confirmation["accept"])

    def test_touch_does_not_resume_active_job(self):
        state = PendantState()
        ui = UIManager(state)
        ui.complete_boot()
        ui.enter("ACTIVE_JOB")
        result = ui.handle(TouchEvent("release_select", 90, 87))
        self.assertIsNone(result)
        self.assertIsNone(ui.confirmation)
        self.assertEqual(ui.current_screen, "ACTIVE_JOB")

    def test_directional_swipes(self):
        for end, expected in [((120, 20), "swipe_up"),
                              ((120, 200), "swipe_down"),
                              ((30, 120), "swipe_left"),
                              ((205, 120), "swipe_right")]:
            clock = Clock()
            gestures = TouchGestures(clock)
            self.assertEqual(gestures.poll((120, 120)), ())
            clock.t = .10
            self.assertEqual(gestures.poll(end), ())
            self.assertEqual(gestures.poll(None), ())
            clock.t = .20
            self.assertEqual(gestures.poll(None)[0][0], expected)

    def test_vertical_swipes_remain_touch_events_not_handwheel_rotations(self):
        clock, source = Clock(), Source()
        touch = TouchInput(source, clock)
        source.current = (120, 120)
        self.assertEqual(touch.poll(), ())
        source.current = (120, 50)
        clock.t = .10
        self.assertEqual(touch.poll(), ())  # outside menu rows: no preview
        clock.t = .12
        source.current = None
        self.assertEqual(touch.poll(), ())
        clock.t = .22
        events = touch.poll()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].kind, "swipe_up")

    def test_no_unexpected_release_or_movement_action(self):
        gestures = TouchGestures(Clock())
        self.assertEqual(gestures.poll(None), ())
        gestures.poll((120, 120))
        gestures.poll((140, 136))
        self.assertEqual(gestures.poll(None), ())  # axis-locked diagonal is cancelled
        self.assertEqual(gestures.poll((-5, 20)), ())

    def test_touch_transform_and_counting(self):
        clock, source = Clock(), Source()
        touch = TouchInput(source, clock, rotation=90, invert_y=True)
        source.current = (10, 20)
        self.assertEqual(touch.poll(), ())
        clock.t = .10
        source.current = None
        self.assertEqual(touch.poll(), ())
        clock.t = .20
        events = touch.poll()
        self.assertEqual((events[0].kind, events[0].x, events[0].y),
                         ("tap", 219, 229))
        self.assertEqual(touch.event_count, 1)
        self.assertEqual(touch.poll_count, 3)
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
        self.assertEqual(touch.poll_count, 3)
        self.assertEqual(touch.consecutive_errors, 3)
        self.assertEqual(touch.last_error, "OSError")
        source.broken = False
        self.assertEqual(touch.poll(), ())
        self.assertEqual(touch.consecutive_errors, 0)
        self.assertIsNone(touch.last_error)
        self.assertEqual(touch.poll_count, 4)

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
        self.assertEqual(touch.irq_idle_count, 1)
        irq.value = False
        self.assertEqual(touch.point(), (101, 193))
        self.assertEqual(bus.address, 0x2E)
        bus.data = bytes((0, 0, 101, 0, 193))
        self.assertIsNone(touch.point())
        bus.data = bytes((1, 0, 250, 0, 100))
        self.assertIsNone(touch.point())
        bus.locked = True
        self.assertIsNone(touch.point())
        self.assertEqual(touch.read_count, 3)
        self.assertEqual(touch.bus_busy_count, 1)

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
