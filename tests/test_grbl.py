import unittest

from src.controller.grbl import GRBLController
from src.state import PendantState
from src.transport.mock import MockTransport


class GRBLParserTests(unittest.TestCase):
    def setUp(self):
        self.state = PendantState()
        self.transport = MockTransport()
        self.controller = GRBLController(self.state, self.transport)

    def test_startup_ok_error_alarm_and_messages(self):
        self.assertEqual(self.controller.parse_line("Grbl 1.1h ['$' for help]", 1), "startup")
        self.assertEqual(self.state.controller_identity, "Grbl 1.1h")
        self.controller.awaiting_response = ("G0 X0", "normal")
        self.assertEqual(self.controller.parse_line("ok", 2), "ok")
        self.controller.awaiting_response = ("bad", "normal")
        self.controller.queue_command("G0 X2", "normal")
        self.assertEqual(self.controller.parse_line("error:2", 3), "error")
        self.assertEqual(self.state.error, "error:2")
        self.assertEqual(self.controller.queue, [])
        self.assertEqual(self.controller.parse_line("[MSG:hello]", 4), "message")
        self.assertEqual(self.state.message, "hello")
        self.assertEqual(self.controller.parse_line("[VER:1.1h.20200101:]", 5), "info")
        self.assertIn("VER:", self.state.controller_identity)
        self.controller.parse_line("[GC:G0 G54 G17 G21 G90 M3]", 5)
        self.assertEqual(self.state.active_coordinate_system, "G54")
        self.assertEqual(self.state.spindle_command, "CW")
        self.assertEqual(self.controller.parse_line("ALARM:1", 6), "alarm")
        self.assertEqual(self.state.machine_state, "alarm")
        self.assertEqual(self.state.alarm, "1")

    def test_status_fields_and_coordinate_derivation(self):
        report = "<Idle|MPos:10,20,30,40,50,60|WCO:1,2,3,4,5,6|FS:500,12000|Ov:90,50,110|Pn:XYZP|A:S|WCS:G55>"
        self.controller.parse_line(report, 10)
        self.assertEqual(self.state.machine_state, "idle")
        self.assertEqual(self.state.work_position["X"], 9.0)
        self.assertEqual(self.state.work_position["C"], 54.0)
        self.assertEqual(self.state.feed_rate, 500)
        self.assertEqual(self.state.spindle_speed, 12000)
        self.assertEqual((self.state.feed_override, self.state.rapid_override,
                          self.state.spindle_override), (90, 50, 110))
        self.assertEqual(self.state.pin_state, set("XYZP"))
        self.assertEqual(self.state.active_coordinate_system, "G55")
        self.assertEqual(self.state.spindle_command, "CW")

    def test_wpos_derives_mpos_and_f_only(self):
        self.controller.parse_line("<Idle|WPos:2,3,4|WCO:10,20,30|F:42>", 10)
        self.assertEqual(self.state.machine_position["X"], 12.0)
        self.assertEqual(self.state.feed_rate, 42)

    def test_realtime_commands(self):
        for name, expected in (("status", b"?"), ("start", b"~"),
                               ("hold", b"!"), ("jog_cancel", b"\x85"),
                               ("soft_reset", b"\x18")):
            self.controller.realtime(name)
            self.assertEqual(self.transport.writes[-1], expected)

    def test_jog_generation_coalescing_and_bound(self):
        self.assertTrue(self.controller.queue_jog("X", 0.01, 500))
        self.assertTrue(self.controller.queue_jog("X", 0.01, 500))
        self.assertEqual(len(self.controller.queue), 1)
        self.assertIn("X0.020000", self.controller.queue[0][0])
        small = GRBLController(self.state, self.transport, queue_limit=1)
        self.assertTrue(small.queue_command("G0 X0"))
        self.assertFalse(small.queue_command("G0 Y0"))

    def test_disconnect_and_reconnect(self):
        self.transport.disconnect()
        self.controller.poll(1)
        self.assertEqual(self.state.connection_state, "disconnected")
        self.transport.connect()
        self.controller.poll(2)
        self.assertEqual(self.state.connection_state, "connecting")
        self.transport.inject("<Idle|MPos:0,0,0>")
        self.controller.poll(3)
        self.assertEqual(self.state.connection_state, "connected")
