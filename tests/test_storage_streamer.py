import os
import tempfile
import unittest

from src.controller.grbl import GRBLController
from src.gcode.macros import MacroLibrary
from src.gcode.streamer import GCodeStreamer
from src.safety.state_machine import SafetyStateMachine
from src.state import PendantState
from src.storage.sdcard import SDStorage
from src.transport.mock import MockTransport


class StorageTests(unittest.TestCase):
    def test_filter_and_incremental_read(self):
        with tempfile.TemporaryDirectory() as root:
            for name in ("one.nc", "two.GCODE", "three.tap", "bad.txt"):
                with open(os.path.join(root, name), "w") as out:
                    out.write("; comment\nG0 X0\nG1 X1 (move)\n")
            storage = SDStorage(root)
            self.assertEqual(storage.list_jobs(),
                             ["one.nc", "three.tap", "two.GCODE"])
            job = storage.select_job("one.nc").open()
            self.assertEqual(job.next_command(), "G0 X0")
            self.assertEqual(job.next_command(), "G1 X1")
            self.assertIsNone(job.next_command())
            self.assertEqual(job.line_number, 3)
            job.close()


class StreamerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp.name, "job.nc")
        with open(self.path, "w") as out:
            out.write("G0 X0\nG1 X1\n")
        self.state = PendantState()
        self.state.machine_state = "idle"
        self.state.connection_state = "connected"
        self.transport = MockTransport()
        self.controller = GRBLController(
            self.state, self.transport, status_interval=1000
        )
        self.streamer = GCodeStreamer(self.state, self.controller, timeout=2)
        self.job = SDStorage(self.temp.name).select_job("job.nc")

    def tearDown(self):
        self.temp.cleanup()

    def send_one_and_respond(self, response, now):
        self.streamer.poll(now)
        self.controller.poll(now)
        self.transport.inject(response)
        self.controller.poll(now + 0.1)

    def test_ok_progression_and_completion(self):
        self.streamer.start(self.job, 0)
        self.send_one_and_respond("ok", 0)
        self.assertEqual(self.state.streaming_line, 1)
        self.send_one_and_respond("ok", 1)
        self.streamer.poll(2)
        self.assertEqual(self.state.sd_job_state, "complete")
        self.assertEqual(self.state.streaming_progress, 1.0)

    def test_error_and_alarm_stop(self):
        self.streamer.start(self.job, 0)
        self.send_one_and_respond("error:2", 0)
        self.assertEqual(self.state.sd_job_state, "error")
        self.streamer.start(self.job, 1)
        self.send_one_and_respond("ALARM:1", 1)
        self.assertEqual(self.state.sd_job_state, "alarm")

    def test_hold_resume_cancel_and_timeout(self):
        self.streamer.start(self.job, 0)
        self.streamer.pause()
        self.assertEqual(self.transport.writes[-1], b"!")
        self.streamer.resume()
        self.assertEqual(self.transport.writes[-1], b"~")
        self.streamer.poll(1)
        self.streamer.poll(4)
        self.assertEqual(self.state.sd_job_state, "error")
        self.state.machine_state = "idle"
        self.streamer.start(self.job, 5)
        self.streamer.cancel()
        self.assertEqual(self.state.sd_job_state, "cancelled")


class MacroTests(unittest.TestCase):
    def test_macro_load_and_queue(self):
        with tempfile.TemporaryDirectory() as root:
            with open(os.path.join(root, "park.gcode"), "w") as out:
                out.write("G53 G0 Z0\nG53 G0 X0 Y0 ; park\n")
            state = PendantState()
            state.connection_state = "connected"
            state.machine_state = "idle"
            state.deadman_enabled = True
            controller = GRBLController(state, MockTransport())
            count = MacroLibrary(root).queue(
                "park", controller, SafetyStateMachine(state)
            )
            self.assertEqual(count, 2)
            self.assertEqual(controller.queue[1][0], "G53 G0 X0 Y0")
