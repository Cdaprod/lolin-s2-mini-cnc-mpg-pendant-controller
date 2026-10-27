import os
import sys
import tempfile
import unittest
import types
from types import SimpleNamespace
from unittest.mock import patch

from src.app import PendantApplication
from src.hardware import build_storage, scan_i2c
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


class FailingI2C(FakeI2C):
    def scan(self):
        raise OSError("bus fault")


class CountingWiFiService(MockWiFiService):
    def __init__(self):
        super().__init__()
        self.poll_count = 0
        self.connect_count = 0

    def poll(self):
        self.poll_count += 1

    def connect(self, ssid, password, persist=True):
        self.connect_count += 1
        return super().connect(ssid, password, persist)


class DiagnosticScanTests(unittest.TestCase):
    def test_round_display_release_deinitializes_backlight_pin_owner(self):
        import src.display.round_ui.display as round_display
        events = []
        output = SimpleNamespace(deinit=lambda: events.append("backlight"))
        with patch.dict(sys.modules, {"displayio": SimpleNamespace(
                release_displays=lambda: events.append("displayio whole"))}), \
             patch.object(round_display, "_BACKLIGHT_OUTPUT", output):
            round_display.release_existing_displays()
            self.assertIsNone(round_display._BACKLIGHT_OUTPUT)
        self.assertEqual(events, ["displayio whole", "backlight"])

    def test_disabled_sd_does_not_report_absent_optional_jobs_directory_as_error(self):
        with tempfile.TemporaryDirectory() as root:
            missing_jobs = os.path.join(root, "jobs")
            storage, mount = build_storage({
                "sd_enabled": False, "jobs_path": missing_jobs,
                "macros_path": os.path.join(root, "macros"),
            })
            self.assertIsNone(mount)
            self.assertEqual(storage.status, "unconfigured")
            self.assertIsNone(storage.error)
            self.assertEqual(storage.list_jobs(), [])
            self.assertEqual(storage.status, "unconfigured")

    def test_application_deinit_releases_owned_optional_resources_once(self):
        class Resource:
            def __init__(self):
                self.closed = 0
            def deinit(self):
                self.closed += 1
        app = object.__new__(PendantApplication)
        app.mirror = Resource()
        app.network_service = Resource()
        app.sd_mount = Resource()
        app.touch_manager = Resource()
        app.spi_bus = Resource()
        app.i2c_bus = Resource()
        app.display = SimpleNamespace(display=object())
        resources = {name: getattr(app, name) for name in
                     ("mirror", "network_service", "sd_mount",
                      "touch_manager", "spi_bus", "i2c_bus")}
        with patch("src.display.round_ui.display.release_existing_displays") as release:
            app.deinit()
            app.deinit()
        release.assert_called_once()
        for name, resource in resources.items():
            self.assertEqual(resource.closed, 1)
            if name != "network_service":
                self.assertIsNone(getattr(app, name))

    def test_sd_failure_is_reported_and_retry_recovers_with_shared_spi(self):
        from src.storage import circuitpython_sd
        with tempfile.TemporaryDirectory() as root:
            board = types.ModuleType("board")
            for name in ("D8", "D10", "D9", "D2"):
                setattr(board, name, name)
            busio = types.ModuleType("busio")
            busio.SPI = lambda *args, **kwargs: object()
            sdcardio = types.ModuleType("sdcardio")
            storage = types.ModuleType("storage")
            state = {"fail": True, "mounts": 0, "unmounts": 0,
                     "card_deinits": 0}
            class Card:
                def __init__(self, spi, chip_select):
                    self.spi, self.chip_select = spi, chip_select
                    if state["fail"]:
                        raise OSError("card absent")
                def deinit(self):
                    state["card_deinits"] += 1
            sdcardio.SDCard = Card
            storage.VfsFat = lambda card: ("vfs", card)
            def mount(vfs, path):
                state["mounts"] += 1
                os.makedirs(os.path.join(path, "jobs"), exist_ok=True)
            storage.mount = mount
            storage.umount = lambda path: state.__setitem__(
                "unmounts", state["unmounts"] + 1)
            shared = object()
            config = {"sd_enabled": True, "sd_sck_pin": "D8",
                      "sd_mosi_pin": "D10", "sd_miso_pin": "D9",
                      "sd_cs_pin": "D2", "sd_mount_path": os.path.join(root, "sd")}
            with patch.dict(sys.modules, {"board": board, "busio": busio,
                                          "sdcardio": sdcardio, "storage": storage}):
                result = circuitpython_sd.mount_from_config(config, shared)
                self.assertEqual(result[1], "mount_error")
                self.assertIn("initialize SD card", result[2])
                state["fail"] = False
                recovered = circuitpython_sd.mount_from_config(config, shared)
                recovered[0].deinit()
                recovered[0].deinit()
            self.assertEqual(recovered[1], "available")
            self.assertIs(recovered[0].spi, shared)
            self.assertEqual(state["mounts"], 1)
            self.assertEqual(state["unmounts"], 1)
            self.assertEqual(state["card_deinits"], 1)

    def test_round_display_releases_before_spi_and_mounts_sd_after_lcd(self):
        import src.app as app_module
        from src.storage.sdcard import SDStorage
        with tempfile.TemporaryDirectory() as root:
            jobs, macros = os.path.join(root, "jobs"), os.path.join(root, "macros")
            os.mkdir(jobs)
            os.mkdir(macros)
            events = []
            shared = object()
            def display_factory(config, shared_spi=None):
                events.append(("display", shared_spi))
                return ConsoleDisplay(lambda value: None)
            def storage_factory(config, shared_spi=None):
                events.append(("sd", shared_spi))
                return SDStorage(jobs, macros), object()
            with patch("src.app.sys", SimpleNamespace(
                    implementation=SimpleNamespace(name="circuitpython"),
                    modules={})), \
                 patch("src.display.round_ui.display.release_existing_displays",
                       side_effect=lambda: events.append(("release", None))), \
                 patch("src.hardware.build_shared_spi",
                       side_effect=lambda config: events.append(("spi", None)) or shared), \
                 patch("src.app.build_display", side_effect=display_factory), \
                 patch("src.app.build_storage", side_effect=storage_factory):
                app = PendantApplication.from_config(
                    {"controller_mode": "disabled", "display_enabled": True,
                     "display_renderer": "round", "sd_enabled": True,
                     "jobs_path": jobs, "macros_path": macros},
                    network_service=MockWiFiService())
            self.assertEqual([item[0] for item in events],
                             ["release", "spi", "display", "sd"])
            self.assertIs(events[2][1], shared)
            self.assertIs(events[3][1], shared)
            self.assertIs(app.spi_bus, shared)

    def test_circuitpython_composition_rejects_same_session_reinitialization(self):
        import src.app as app_module
        modules = {app_module._CIRCUITPY_COMPOSITION_KEY:
                   {"deinitialized": False}}
        circuitpython = SimpleNamespace(
            implementation=SimpleNamespace(name="circuitpython"),
            modules=modules)
        with patch("src.app.sys", circuitpython):
            with self.assertRaisesRegex(RuntimeError, "deinit the current"):
                PendantApplication.from_config({"controller_mode": "disabled"})

    def test_circuitpython_composition_can_restart_after_clean_deinit(self):
        import src.app as app_module
        circuitpython = SimpleNamespace(
            implementation=SimpleNamespace(name="circuitpython"), modules={})
        config = {"controller_mode": "disabled", "display_enabled": False,
                  "inputs_enabled": False}
        with patch("src.app.sys", circuitpython):
            first = PendantApplication.from_config(
                config, display=ConsoleDisplay(lambda value: None),
                network_service=MockWiFiService(), shared_i2c=FakeI2C(()))
            first.deinit()
            self.assertTrue(first._circuitpython_lifecycle["deinitialized"])
            second = PendantApplication.from_config(
                config, display=ConsoleDisplay(lambda value: None),
                network_service=MockWiFiService(), shared_i2c=FakeI2C(()))
            second.deinit()

    def test_scan_is_read_only_and_reports_addresses(self):
        bus = FakeI2C((0x3C, 0x20))
        self.assertEqual(scan_i2c(bus), ((0x20, 0x3C), None))
        self.assertFalse(bus.locked)

    def test_i2c_failure_does_not_pollute_storage_diagnostics(self):
        with tempfile.TemporaryDirectory() as root:
            jobs = os.path.join(root, "jobs")
            macros = os.path.join(root, "macros")
            os.mkdir(jobs)
            os.mkdir(macros)
            app = PendantApplication.from_config(
                {"controller_mode": "disabled", "jobs_path": jobs,
                 "macros_path": macros, "mcp23017_address": 0x20},
                display=ConsoleDisplay(lambda value: None),
                network_service=MockWiFiService(),
                shared_i2c=FailingI2C(()),
            )
            self.assertEqual(app.state.storage_state, "available")
            self.assertIsNone(app.state.storage_error)
            self.assertEqual(app.state.subsystems["storage"], "OK")
            self.assertEqual(app.state.subsystems["sd"], "DISABLED")
            self.assertEqual(app.state.subsystems["i2c"], "ERROR")
            self.assertIn("OSError", app.state.i2c_error)


class PhysicalInputTests(unittest.TestCase):
    def test_selectors_wheel_and_invalid_transition(self):
        state = PendantState()
        adapter = SyntheticInputAdapter()
        manager = InputManager(state, adapter, counts_per_detent=4)
        adapter.set(axes=("4",), multipliers=("X100",))
        manager.poll(0)
        self.assertIsNone(state.selected_axis)
        self.assertEqual(state.selector_function, "FILES")
        self.assertEqual(state.active_page, "EXPLORER")
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
        expected = (("X", "X", "OPERATIONAL"),
                    ("Y", "Y", "OPERATIONAL"),
                    ("Z", "Z", "OPERATIONAL"),
                    ("4", None, "EXPLORER"),
                    ("5", None, "CONFIGURATION"),
                    ("6", None, "PREVIEW"))
        for physical, logical, page in expected:
            adapter.set(axes=(physical,), multipliers=("X1",))
            manager.poll(1)
            self.assertEqual(state.selected_axis, logical)
            self.assertEqual(state.active_page, page)
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
    def test_wifi_association_poll_is_deferred_during_machine_activity(self):
        with tempfile.TemporaryDirectory() as root:
            jobs, macros = os.path.join(root, "jobs"), os.path.join(root, "macros")
            os.mkdir(jobs)
            os.mkdir(macros)
            network = CountingWiFiService()
            app = PendantApplication.from_config(
                {"controller_mode": "disabled", "jobs_path": jobs,
                 "macros_path": macros},
                display=ConsoleDisplay(lambda value: None),
                network_service=network)
            app.state.deadman_enabled = True
            app.poll()
            self.assertEqual(network.poll_count, 0)
            app.state.deadman_enabled = False
            app.state.machine_state = "idle"
            app.poll()
            self.assertEqual(network.poll_count, 1)

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

    def test_physical_selectors_and_relative_activity_reach_view_model(self):
        with tempfile.TemporaryDirectory() as root:
            app, adapter, clock = self.make_app(root)
            adapter.set(axes=("Y",), multipliers=("X100",), deadman=True,
                        mpg_delta=4)
            app.poll()
            model = app.ui.view_model()
            self.assertEqual(model["axis_selector"], "Y")
            self.assertEqual(model["resolution_selector"], "X100")
            self.assertTrue(model["jog_armed"])
            self.assertEqual(model["mpg_activity"], 4)
            self.assertEqual(model["axis_transition_direction"], 1)
            self.assertEqual(model["resolution_transition_direction"], 1)
            adapter.set(axes=("X",), multipliers=("X1",), deadman=True,
                        mpg_delta=-4)
            app.poll()
            reverse = app.ui.view_model()
            self.assertEqual(reverse["axis_transition_direction"], -1)
            self.assertEqual(reverse["resolution_transition_direction"], -1)
            self.assertEqual(reverse["mpg_activity"], -4)
            clock.advance(0.21)
            adapter.set(mpg_delta=0)
            app.poll()
            self.assertEqual(app.ui.view_model()["mpg_activity"], 0)
            self.assertFalse(hasattr(app.state, "mpg_position"))

    def test_off_and_released_jog_hold_immediately_inhibit_motion(self):
        with tempfile.TemporaryDirectory() as root:
            app, adapter, clock = self.make_app(root)
            writes = len(app.transport.writes)
            adapter.set(axes=(), multipliers=("X10",), deadman=False,
                        mpg_delta=4)
            app.poll()
            model = app.ui.view_model()
            self.assertEqual(model["axis_selector"], "OFF")
            self.assertFalse(model["jog_armed"])
            self.assertFalse(model["motion_available"])
            self.assertEqual(len(app.transport.writes), writes)

    def test_page_selectors_revoke_motion_before_contextual_wheel(self):
        with tempfile.TemporaryDirectory() as root:
            app, adapter, _ = self.make_app(root)
            app.controller.queue_jog("X", 0.01, 500)
            app.state.jog_active = True
            before = sum(b"$J=" in data for data in app.transport.writes)
            adapter.set(axes=("4",), multipliers=("X10",), deadman=True,
                        mpg_delta=4)
            app.poll()
            self.assertEqual(app.ui.current_screen, "EXPLORER")
            self.assertEqual(app.state.active_page, "EXPLORER")
            self.assertIsNone(app.state.selected_axis)
            self.assertFalse(app.state.jog_active)
            self.assertFalse(any(kind == "jog" for _, kind in app.controller.queue))
            self.assertEqual(
                sum(b"$J=" in data for data in app.transport.writes), before)

    def test_files_config_and_preview_wheels_are_non_motion(self):
        with tempfile.TemporaryDirectory() as root:
            app, adapter, _ = self.make_app(root)
            for name in ("a.nc", "b.nc"):
                with open(os.path.join(root, "jobs", name), "w") as output:
                    output.write("G0 X0\n")
            baseline = sum(b"$J=" in data for data in app.transport.writes)

            adapter.set(axes=("4",), multipliers=("X1",), deadman=True,
                        mpg_delta=4)
            app.poll()
            self.assertEqual(app.ui.current_screen, "EXPLORER")
            self.assertEqual(app.ui.selected_item().value, "b.nc")

            adapter.set(axes=("5",), multipliers=("X1",), deadman=True,
                        mpg_delta=4)
            app.poll()
            self.assertEqual(app.ui.current_screen, "CONFIGURATION")
            self.assertEqual(app.ui.focus["CONFIGURATION"], 1)

            adapter.set(axes=("6",), multipliers=("X100",), deadman=True,
                        mpg_delta=-4)
            app.poll()
            self.assertEqual(app.ui.current_screen, "PREVIEW")
            self.assertEqual(app.state.preview_wheel_steps, -1)
            self.assertAlmostEqual(app.state.preview_position["X"], -0.1)
            adapter.set(mpg_delta=0, estop=True)
            app.poll()
            details = dict(app.ui.view_model()["details"])
            self.assertEqual(details["Multiplier"], "X100")
            self.assertEqual(details["Remote stop"], "ACTIVE")
            self.assertEqual(
                sum(b"$J=" in data for data in app.transport.writes), baseline)

    def test_returning_to_xyz_restores_motion_only_after_safe_transition(self):
        with tempfile.TemporaryDirectory() as root:
            app, adapter, _ = self.make_app(root)
            adapter.set(axes=("4",), multipliers=("X1",), deadman=True,
                        mpg_delta=4)
            app.poll()
            self.assertEqual(app.ui.current_screen, "EXPLORER")
            adapter.set(axes=("Y",), multipliers=("X1",), deadman=True,
                        mpg_delta=0)
            app.poll()
            self.assertEqual(app.ui.current_screen, "HOME")
            self.assertEqual(app.state.selected_axis, "Y")
            self.assertTrue(app.ui.view_model()["motion_available"])

    def test_estop_view_model_requires_explicit_recovery(self):
        with tempfile.TemporaryDirectory() as root:
            app, _, _ = self.make_app(root)
            app.observe_estop(True)
            self.assertEqual(app.ui.view_model()["estop_state"], "ACTIVE")
            app.observe_estop(False)
            self.assertEqual(app.ui.view_model()["estop_state"],
                             "RECOVERY_REQUIRED")
            app.recover_estop()
            self.assertEqual(app.ui.view_model()["estop_state"], "CLEAR")

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
            self.assertEqual(app.ui.active_overlay()[0], "E-STOP")
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
    def test_sd_write_probe_round_trips_and_removes_its_marker(self):
        board = types.ModuleType("board")
        for name in ("D8", "D10", "D9", "D2"):
            setattr(board, name, name)
        busio = types.ModuleType("busio")
        busio.SPI = lambda *args, **kwargs: object()
        sdcardio = types.ModuleType("sdcardio")
        storage = types.ModuleType("storage")
        class Card:
            def __init__(self, spi, chip_select):
                self.spi = spi
            def deinit(self):
                pass
        sdcardio.SDCard = Card
        storage.VfsFat = lambda card: card
        storage.mount = lambda _vfs, path: os.makedirs(
            os.path.join(path, "jobs"), exist_ok=True)
        storage.umount = lambda _path: None
        with tempfile.TemporaryDirectory() as root:
            mount_path = os.path.join(root, "sd")
            config = {"sd_enabled": True, "sd_write_test": True,
                      "sd_sck_pin": "D8", "sd_mosi_pin": "D10",
                      "sd_miso_pin": "D9", "sd_cs_pin": "D2",
                      "sd_mount_path": mount_path}
            with patch.dict(sys.modules, {"board": board, "busio": busio,
                                          "sdcardio": sdcardio,
                                          "storage": storage}):
                mount, status, error = mount_from_config(config, object())
                mount.deinit()
            self.assertEqual(status, "available")
            self.assertIsNone(error)
            self.assertFalse(os.path.exists(os.path.join(
                mount_path, ".cdaprod-sd-self-test.tmp")))

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
