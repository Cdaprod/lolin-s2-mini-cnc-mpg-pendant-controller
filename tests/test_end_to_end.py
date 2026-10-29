import unittest
from unittest.mock import patch
from types import SimpleNamespace

from src.app import PendantApplication
from src.display.console import ConsoleDisplay
from src.input.mpg import MPGDecoder
from src.input.selectors import SelectorModel
from src.transport.mock import MockGRBLTransport, MockTransport
from src.display.ui import TouchEvent


class EndToEndTests(unittest.TestCase):
    def test_home_menu_opens_on_contact_and_release_does_not_select_a_row(self):
        class TouchManager:
            last_contact_transition = ("down", 130, 102)
            last_feedback = (130, 102, "contact")
            feedback_until = 1.2
            consecutive_errors = 0
            last_error = None
            gestures = SimpleNamespace(axis_lock=None)
            events = ()

            def poll(self):
                return self.events

        touch = TouchManager()
        app = PendantApplication.from_config(
            {"controller_mode": "disabled"},
            display=ConsoleDisplay(lambda frame: None),
            touch_manager=touch, clock=lambda: 1.0)

        app.poll()
        self.assertEqual(app.ui.current_screen, "MAIN_MENU")
        self.assertTrue(app._touch_menu_preview_active)

        touch.last_contact_transition = ("up", 130, 102)
        touch.events = (TouchEvent("release_select", 130, 102),)
        app.poll()
        self.assertEqual(app.ui.current_screen, "MAIN_MENU")
        self.assertFalse(app._touch_menu_preview_active)
        self.assertFalse(app.state.controller_enabled)

    def test_home_menu_contact_preview_cancels_before_horizontal_page_swipe(self):
        class TouchManager:
            last_contact_transition = ("down", 130, 102)
            last_feedback = (130, 102, "contact")
            feedback_until = 1.2
            consecutive_errors = 0
            last_error = None
            gestures = SimpleNamespace(axis_lock=None)
            events = ()

            def poll(self):
                return self.events

        touch = TouchManager()
        app = PendantApplication.from_config(
            {"controller_mode": "disabled"},
            display=ConsoleDisplay(lambda frame: None),
            touch_manager=touch, clock=lambda: 1.0)
        app.poll()
        self.assertEqual(app.ui.current_screen, "MAIN_MENU")

        touch.last_contact_transition = None
        touch.gestures.axis_lock = "horizontal"
        touch.events = (TouchEvent("swipe_left", 130, 205),)
        app.poll()

        self.assertEqual(app.ui.current_screen, "EXPLORER")
        self.assertEqual(app.state.active_page, "EXPLORER")
        self.assertFalse(app._touch_menu_preview_active)

    def test_home_menu_contact_preview_cancels_on_long_press(self):
        class TouchManager:
            last_contact_transition = ("down", 130, 102)
            last_feedback = (130, 102, "contact")
            feedback_until = 1.2
            consecutive_errors = 0
            last_error = None
            gestures = SimpleNamespace(axis_lock=None)
            events = ()

            def poll(self):
                return self.events

        touch = TouchManager()
        app = PendantApplication.from_config(
            {"controller_mode": "disabled"},
            display=ConsoleDisplay(lambda frame: None),
            touch_manager=touch, clock=lambda: 1.0)
        app.poll()
        self.assertEqual(app.ui.current_screen, "MAIN_MENU")

        touch.last_contact_transition = None
        touch.events = (TouchEvent("long_press", 130, 102),)
        app.poll()

        self.assertEqual(app.ui.current_screen, "HOME")
        self.assertFalse(app._touch_menu_preview_active)
        self.assertFalse(app.state.controller_enabled)

    def test_touch_preview_renders_before_wifi_service(self):
        order = []

        class TouchManager:
            last_contact_transition = ("down", 95, 87)
            last_feedback = None
            feedback_until = 0
            consecutive_errors = 0
            last_error = None

            def poll(self):
                return ()

        class Display(ConsoleDisplay):
            def render(self, state):
                order.append("render")
                return super().render(state)

        app = PendantApplication.from_config(
            {"controller_mode": "disabled"}, display=Display(lambda frame: None),
            touch_manager=TouchManager(), clock=lambda: 1.0)
        app.ui.enter("MAIN_MENU")
        app.network_service.poll = lambda: order.append("wifi")

        app.poll()

        self.assertEqual(app.ui.focus["MAIN_MENU"], 1)
        self.assertLess(order.index("render"), order.index("wifi"))

    def test_home_contact_opens_safe_menu_and_shows_touch_feedback(self):
        feedback = []

        class TouchManager:
            last_contact_transition = ("down", 90, 65)
            last_feedback = (90, 65, "contact")
            feedback_until = 1.2
            consecutive_errors = 0
            last_error = None

            def poll(self):
                return ()

        class Display(ConsoleDisplay):
            def touch_feedback(self, point, until):
                feedback.append((point, until))

        app = PendantApplication.from_config(
            {"controller_mode": "disabled"},
            display=Display(lambda frame: None),
            touch_manager=TouchManager(), clock=lambda: 1.0)

        app.poll()

        self.assertEqual(feedback, [((90, 65), 1.2)])
        self.assertEqual(app.ui.current_screen, "MAIN_MENU")
        self.assertFalse(app.state.controller_enabled)

    def test_touch_contact_precedes_released_gesture_in_diagnostics(self):
        class TouchManager:
            last_contact_transition = ("up", 90, 65)
            last_feedback = None
            consecutive_errors = 0
            last_error = None
            feedback_until = 0

            def poll(self):
                return (TouchEvent("release_select", 90, 65),)

        app = PendantApplication.from_config(
            {"controller_mode": "disabled"},
            display=ConsoleDisplay(lambda frame: None),
            touch_manager=TouchManager(), clock=lambda: 1.0)
        events = []
        with patch("src.app.emit",
                   side_effect=lambda event, **fields: events.append(event)):
            app.poll()
        self.assertLess(events.index("touch_contact"),
                        events.index("touch_gesture"))

    def test_touch_diagnostics_do_not_precede_contact_redraw(self):
        order = []

        class TouchManager:
            last_contact_transition = ("down", 90, 65)
            last_feedback = (90, 65, "contact")
            feedback_until = 1.2
            consecutive_errors = 0
            last_error = None

            def poll(self):
                return ()

        class Display(ConsoleDisplay):
            def render(self, state):
                order.append("render")
                return super().render(state)

        app = PendantApplication.from_config(
            {"controller_mode": "disabled"},
            display=Display(lambda frame: None),
            touch_manager=TouchManager(), clock=lambda: 1.0)
        with patch("src.app.emit",
                   side_effect=lambda event, **fields:
                   order.append("event:" + event)):
            app.poll()

        self.assertLess(order.index("render"),
                        order.index("event:touch_contact"))

    def test_estop_immediately_discards_jog_and_inhibits_stream(self):
        transport = MockTransport()
        app = PendantApplication.from_config(
            {"controller_mode": "mock"}, transport=transport,
            display=ConsoleDisplay(lambda frame: None), clock=lambda: 1.0
        )
        app.controller.queue_command("G0 X1", "jog")
        app.observe_estop(True)
        self.assertTrue(app.state.estop_observed)
        self.assertEqual(app.state.machine_state, "estop")
        self.assertFalse(any(kind == "jog" for _, kind in app.controller.queue))
        self.assertIn(b"!", transport.writes)
        self.assertIn(b"\x85", transport.writes)

    def test_mpg_to_grbl_status_state_and_display(self):
        frames = []
        transport = MockTransport()
        app = PendantApplication.from_config(
            {"controller_mode": "mock", "base_increment": 0.001,
             "jog_feed": 500, "status_interval": 100},
            transport=transport,
            display=ConsoleDisplay(frames.append),
            clock=lambda: 1.0,
        )
        app.state.connection_state = "connected"
        app.state.machine_state = "idle"
        app.state.deadman_enabled = True
        app.state.input_valid = True
        app.ui.refresh_context()
        selectors = SelectorModel(app.state)
        selectors.select_axis("X")
        selectors.select_multiplier("X10")
        decoder = MPGDecoder(4)
        event = 0
        for pins in ((0, 0), (0, 1), (1, 1), (1, 0), (0, 0)):
            event = decoder.update(*pins) or event
        self.assertEqual(event, 1)
        self.assertTrue(app.actions.jog(event))
        app.controller.poll(1)
        self.assertIn(b"$J=G91 G21 X0.010000 F500.000\n", transport.writes)
        transport.inject("ok")
        transport.inject("<Idle|MPos:125.4,42.15,-8,0|WCO:0,0,0,0|FS:0,0|Ov:100,100,100>")
        app.poll()
        frame = frames[-1]
        self.assertIn("X >    +125.400", frame)
        self.assertIn("X10 / 0.010mm", frame)
        self.assertIn("open-loop controller", frame)

    def test_default_mock_mode_simulates_grbl(self):
        app = PendantApplication.from_config(
            {"controller_mode": "mock", "status_interval": 0},
            display=ConsoleDisplay(lambda frame: None), clock=lambda: 1.0
        )
        self.assertIsInstance(app.transport, MockGRBLTransport)
        app.poll()
        app.poll()
        self.assertEqual(app.state.controller_identity, "Grbl 1.1h")
        self.assertEqual(app.state.machine_state, "idle")


if __name__ == "__main__":
    unittest.main()
