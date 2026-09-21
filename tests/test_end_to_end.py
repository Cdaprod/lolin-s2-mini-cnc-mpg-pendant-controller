import unittest

from src.app import PendantApplication
from src.display.console import ConsoleDisplay
from src.input.mpg import MPGDecoder
from src.input.selectors import SelectorModel
from src.transport.mock import MockGRBLTransport, MockTransport


class EndToEndTests(unittest.TestCase):
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
