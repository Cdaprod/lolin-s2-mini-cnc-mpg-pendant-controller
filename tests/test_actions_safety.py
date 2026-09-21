import unittest

from src.controller.actions import ActionDispatcher
from src.controller.grbl import GRBLController
from src.input.selectors import SelectorModel
from src.safety.state_machine import SafetyError, SafetyStateMachine
from src.safety.watchdog import Watchdog
from src.state import PendantState
from src.transport.mock import MockTransport


class ActionSafetyTests(unittest.TestCase):
    def setUp(self):
        self.state = PendantState()
        self.state.connection_state = "connected"
        self.state.machine_state = "idle"
        self.state.deadman_enabled = True
        self.state.ui_handwheel_mode = "MOTION"
        SelectorModel(self.state).select_axis("X")
        self.transport = MockTransport()
        self.controller = GRBLController(self.state, self.transport)
        self.safety = SafetyStateMachine(self.state)
        self.actions = ActionDispatcher(self.state, self.controller, self.safety)

    def test_positive_and_negative_jog(self):
        self.assertTrue(self.actions.jog(1))
        self.assertIn("X0.001000", self.controller.queue[-1][0])
        self.controller.queue = []
        self.assertTrue(self.actions.jog(-1))
        self.assertIn("X-0.001000", self.controller.queue[-1][0])

    def test_unsafe_state_and_estop_reject_jog(self):
        self.state.machine_state = "run"
        with self.assertRaises(SafetyError):
            self.actions.jog(1)
        self.state.machine_state = "idle"
        self.safety.observe_estop(True)
        with self.assertRaises(SafetyError):
            self.actions.jog(1)
        self.safety.observe_estop(False)
        with self.assertRaises(SafetyError):
            self.actions.jog(1)
        self.state.clear_estop_latch()
        self.state.machine_state = "idle"
        self.assertTrue(self.actions.jog(1))

    def test_action_dispatch(self):
        self.assertTrue(self.actions.dispatch("ZERO_AXIS"))
        self.assertEqual(self.controller.queue[-1][0], "G10 L20 P0 X0")
        self.controller.queue = []
        self.assertTrue(self.actions.dispatch("HOME"))
        self.assertEqual(self.controller.queue[-1][0], "$H")
        self.actions.dispatch("FEED_HOLD")
        self.assertEqual(self.transport.writes[-1], b"!")

    def test_unlock_is_allowed_from_alarm_but_not_estop(self):
        self.state.machine_state = "alarm"
        self.state.alarm = "1"
        self.assertTrue(self.actions.dispatch("UNLOCK"))
        self.state.set_estop(True)
        with self.assertRaises(SafetyError):
            self.actions.dispatch("UNLOCK")

    def test_timeout_fails_closed(self):
        self.state.last_controller_response = 1.0
        events = Watchdog(self.state, communication_timeout=2).poll(4.0)
        self.assertEqual(events, ["communication_timeout"])
        self.assertEqual(self.state.machine_state, "error")
        self.assertEqual(self.state.connection_state, "disconnected")

    def test_connecting_timeout_fails_closed(self):
        self.state.connection_state = "connecting"
        self.state.connection_started_timestamp = 1.0
        events = Watchdog(self.state, communication_timeout=2).poll(4.0)
        self.assertEqual(events, ["communication_timeout"])
