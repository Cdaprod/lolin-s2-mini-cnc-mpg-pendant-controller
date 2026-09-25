import os
import tempfile
import unittest

from src.app import PendantApplication
from src.hardware import scan_i2c
from src.display.console import ConsoleDisplay
from src.display.indicator import DigitalIndicatorOutput
from src.display.ui import ROTATE_CW
from src.input.buttons import DebouncedButton
from src.input.manager import InputManager, SyntheticInputAdapter
from src.network import MockWiFiService
from src.state import PendantState
from src.storage.circuitpython_sd import mount_from_config
from src.storage.sdcard import SDStorage
from src.transport.mock import MockTransport


class MutableClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class FakeI2C:
    def __init__(self, addresses):
        self.addresses = addresses
        self.locked = False

    def try_lock(self):
        self.locked = True
        return True

    def scan(self):
        return self.addresses

    def unlock(self):
        self.locked = False


class DiagnosticScanTests(unittest.TestCase):
    def test_scan_is_read_only_and_reports_addresses(self):
        bus = FakeI2C((0x3C, 0x20))
        self.assertEqual(scan_i2c(bus), ((0x20, 0x3C), None))
        self.assertFalse(bus.locked)


class PhysicalInputTests(unittest.TestCase):
    def test_selectors_wheel_and_invalid_transition(self):
        state = PendantState()
        adapter = SyntheticInputAdapter()
        manager = InputManager(state, adapter, counts_per_detent=4)
        adapter.set(axes=("4",), multipliers=("X100",))
        manager.poll(0)
        self.assertEqual(state.selected_axis, "A")
        self.assertAlmostEqual(state.jog_increment, 0.1)
        events = []
        for now, pins in enumerate(((0, 0), (0, 1), (1, 1), (1, 0), (0, 0))):
            adapter.set(mpg_a=pins[0], mpg_b=pins[1])
            events.extend(manager.poll(now + 1).events)
        self.assertEqual(events, [ROTATE_CW])
        adapter.set(mpg_a=1, mpg_b=1)
        self.assertEqual(manager.poll(10).events, [])
        self.assertGreater(manager.decoder.invalid_transitions, 0)

    def test_all_axes_off_and_multipliers(self):
        state = PendantState()
        adapter = SyntheticInputAdapter()
        manager = InputManager(state, adapter)
        for physical, logical in (("X", "X"), ("Y", "Y"), ("Z", "Z"),
                                  ("4", "A"), ("5", "B"), ("6", "C")):
            adapter.set(axes=(physical,), multipliers=("X1",))
            manager.poll(1)
            self.assertEqual(state.selected_axis, logical)
        for label, increment in (("X1", 0.001), ("X10", 0.01),
                                 ("X100", 0.1)):
            adapter.set(axes=("X",), multipliers=(label,))
            manager.poll(2)
            self.assertAlmostEqual(state.jog_increment, increment)
        adapter.set(axes=())
        manager.poll(3)
        self.assertIsNone(state.selected_axis)

    def test_background_encoder_delta_is_bounded_and_semantic(self):
        state = PendantState()
        adapter = SyntheticInputAdapter()
        manager = InputManager(state, adapter, counts_per_detent=4)
        adapter.set(mpg_delta=8)
        self.assertEqual(manager.poll(0).events, [ROTATE_CW, ROTATE_CW])
        adapter.set(mpg_delta=-4)
        self.assertEqual(manager.poll(1).events, ["ROTATE_CCW"])

    def test_button_debounce_short_and_long(self):
        button = DebouncedButton(debounce=0.03, long_press=0.5)
        self.assertEqual(button.update(True, 0), [])
        self.assertIn("press", button.update(True, 0.04))
        self.assertIn("long", button.update(True, 0.55))
        button.update(False, 0.56)
        released = button.update(False, 0.60)
        self.assertIn("release", released)
        self.assertNotIn("short", released)
        button.update(True, 1.0)
        button.update(True, 1.04)
        button.update(False, 1.1)
        released = button.update(False, 1.14)
        self.assertIn("short", released)


class ApplicationInputPipelineTests(unittest.TestCase):
    def make_app(self, root):
        jobs = os.path.join(root, "jobs")
        macros = os.path.join(root, "macros")
        os.mkdir(jobs)
        os.mkdir(macros)
        clock = MutableClock()
        adapter = SyntheticInputAdapter()
        transport = MockTransport()
        app = PendantApplication.from_config(
            {"controller_mode": "mock", "jobs_path": jobs,
             "macros_path": macros, "status_interval": 100,
             "base_increment": 0.001, "jog_feed": 500,
             "mpg_counts_per_detent": 4, "button_debounce": 0.01,
             "button_long_press": 0.2},
            transport=transport, display=ConsoleDisplay(lambda value: None),
            network_service=MockWiFiService([("Lab", -20)]),
            input_adapter=adapter, clock=clock,
        )
        app.state.connection_state = "connected"
        app.state.machine_state = "idle"
        app.state.deadman_enabled = True
        adapter.set(axes=("X",), multipliers=("X10",), deadman=True)
        app.poll()
        return app, adapter, clock

    def rotate_cw(self, app, adapter, clock):
        for a, b in ((0, 0), (0, 1), (1, 1), (1, 0), (0, 0)):
            adapter.set(mpg_a=a, mpg_b=b)
            clock.advance(0.01)
            app.poll()

    def tap(self, app, adapter, clock, name):
        adapter.set(buttons={name: True})
        app.poll()
        clock.advance(0.02)
        app.poll()
        adapter.set(buttons={name: False})
        app.poll()
        clock.advance(0.02)
        app.poll()

    def test_input_manager_is_polled_and_wheel_is_contextual(self):
        with tempfile.TemporaryDirectory() as root:
            app, adapter, clock = self.make_app(root)
            self.rotate_cw(app, adapter, clock)
            self.assertTrue(any(b"$J=" in data for data in app.transport.writes))
            jog_count = sum(b"$J=" in data for data in app.transport.writes)
            self.tap(app, adapter, clock, "SELECT")
            self.assertEqual(app.ui.current_screen, "MAIN_MENU")
            self.rotate_cw(app, adapter, clock)
            self.assertEqual(app.ui.focus["MAIN_MENU"], 1)
            self.assertEqual(sum(b"$J=" in d for d in app.transport.writes),
                             jog_count)
            self.assertGreater(app.state.loop_count, 0)

    def test_estop_preempts_jog_stream_and_requires_long_recovery(self):
        with tempfile.TemporaryDirectory() as root:
            app, adapter, clock = self.make_app(root)
            job_path = os.path.join(root, "jobs", "job.nc")
            with open(job_path, "w") as output:
                output.write("G0 X1\n")
            app.streamer.start(app.storage.select_job("job.nc"), clock())
            adapter.set(estop=True)
            clock.advance(0.01)
            app.poll()
            self.assertTrue(app.state.estop_latched)
            self.assertEqual(app.state.sd_job_state, "inhibited")
            self.assertEqual(app.ui.active_overlay()[0], "ESTOP")
            self.assertIn(b"\x85", app.transport.writes)
            adapter.set(estop=False)
            clock.advance(0.01)
            app.poll()
            self.assertTrue(app.state.estop_latched)
            adapter.set(buttons={"SELECT": True})
            clock.advance(0.02)
            app.poll()
            clock.advance(0.25)
            app.poll()
            clock.advance(0.25)
            app.poll()
            self.assertFalse(app.state.estop_latched)


class StorageHardwareTests(unittest.TestCase):
    def test_missing_and_empty_storage_are_safe(self):
        with tempfile.TemporaryDirectory() as root:
            missing = SDStorage(os.path.join(root, "missing"))
            self.assertEqual(missing.status, "missing")
            self.assertEqual(missing.list_jobs(), [])
            empty = os.path.join(root, "empty")
            os.mkdir(empty)
            present = SDStorage(empty)
            self.assertEqual(present.status, "available")
            self.assertEqual(present.list_jobs(), [])

    def test_unconfigured_and_incomplete_mount_do_not_import_hardware(self):
        self.assertEqual(mount_from_config({})[1], "unconfigured")
        result = mount_from_config({"sd_enabled": True})
        self.assertEqual(result[1], "mount_error")


class Output:
    value = False


class IndicatorHardwareTests(unittest.TestCase):
    def test_verified_output_adapter_tracks_logical_states(self):
        output = Output()
        indicator = DigitalIndicatorOutput(output)
        self.assertTrue(indicator.update("READY"))
        self.assertTrue(output.value)
        self.assertFalse(indicator.update("READY"))
        self.assertTrue(indicator.update("DISCONNECTED"))
        self.assertFalse(output.value)
