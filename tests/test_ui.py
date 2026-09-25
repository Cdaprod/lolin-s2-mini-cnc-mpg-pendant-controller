import os
import tempfile
import unittest

from src.app import PendantApplication
from src.display.console import ConsoleDisplay
from src.display.text_entry import TextEntry
from src.display.ui import (
    BACK, CANCEL, FN, LONG_SELECT, MOTION, NAVIGATION, ROTATE_CCW, ROTATE_CW,
    SELECT, TEXT_ENTRY, UIManager,
)
from src.network import MockWiFiService
from src.state import PendantState
from src.transport.mock import MockTransport


def ready_ui():
    state = PendantState()
    state.connection_state = "connected"
    state.machine_state = "idle"
    state.deadman_enabled = True
    ui = UIManager(state)
    ui.complete_boot()
    ui.refresh_context()
    return state, ui


class UIStateMachineTests(unittest.TestCase):
    def test_boot_home_menu_and_back(self):
        state = PendantState()
        ui = UIManager(state)
        self.assertEqual(ui.current_screen, "BOOT")
        ui.complete_boot()
        state.connection_state = "connected"
        ui.refresh_context()
        self.assertEqual(ui.current_screen, "HOME")
        self.assertEqual(ui.handwheel_mode, MOTION)
        ui.handle(SELECT)
        self.assertEqual(ui.current_screen, "MAIN_MENU")
        self.assertEqual(ui.handwheel_mode, NAVIGATION)
        ui.handle(BACK)
        self.assertEqual(ui.current_screen, "HOME")

    def test_wheel_routes_by_context(self):
        _, ui = ready_ui()
        command = ui.handle(ROTATE_CW)
        self.assertEqual((command.name, command.value), ("JOG", 1))
        ui.handle(SELECT)
        self.assertIsNone(ui.handle(ROTATE_CW))
        self.assertEqual(ui.focus["MAIN_MENU"], 1)

    def test_navigation_stack_is_bounded_and_backtracks(self):
        _, ui = ready_ui()
        ui.handle(SELECT)
        ui.enter("NETWORK")
        ui.enter("NETWORK_INFO")
        self.assertEqual(ui.stack, ["HOME", "MAIN_MENU", "NETWORK",
                                    "NETWORK_INFO"])
        ui.handle(BACK)
        self.assertEqual(ui.current_screen, "NETWORK")
        ui.home()
        self.assertEqual(ui.stack, ["HOME"])

    def test_text_entry_groups_mask_backspace_and_cancel(self):
        _, ui = ready_ui()
        ui.enter("MAIN_MENU")
        ui.enter("NETWORK")
        ui._start_text("Password", "WIFI_PASSWORD", masked=True)
        self.assertEqual(ui.handwheel_mode, TEXT_ENTRY)
        ui.handle(SELECT)
        self.assertEqual(ui.view_model()["text"], "•")
        ui.handle(ROTATE_CW)
        ui.handle(SELECT)
        self.assertEqual(ui.text_entry.value, "ab")
        ui.handle(BACK)
        self.assertEqual(ui.text_entry.value, "a")
        ui.handle(FN)
        self.assertEqual(ui.text_entry.group_name, "ABC")
        ui.handle(CANCEL)
        self.assertEqual(ui.current_screen, "NETWORK")
        self.assertIsNone(ui.text_entry)

    def test_text_entry_repr_never_contains_secret(self):
        entry = TextEntry("Password", masked=True, initial="TopSecret")
        self.assertNotIn("TopSecret", repr(entry))
        self.assertEqual(entry.display_value(), "•" * 9)

    def test_confirmation_accept_and_reject(self):
        _, ui = ready_ui()
        ui.enter("MAIN_MENU")
        ui.enter("MACHINE")
        ui.handle(SELECT)
        self.assertEqual(ui.active_overlay()[0], "CONFIRMATION")
        rejected = ui.handle(SELECT)
        self.assertEqual(rejected.name, "CONFIRM_REJECTED")
        ui.handle(SELECT)
        ui.handle(ROTATE_CW)
        accepted = ui.handle(SELECT)
        self.assertEqual((accepted.name, accepted.value), ("ACTION", "HOME"))

    def test_safety_overlay_priority_and_no_motion_restore(self):
        state, ui = ready_ui()
        state.alarm = "2"
        state.connection_state = "disconnected"
        state.set_estop(True)
        ui.refresh_context()
        self.assertEqual(ui.active_overlay()[0], "ESTOP")
        self.assertIsNone(ui.handle(ROTATE_CW))
        state.set_estop(False)
        ui.refresh_context()
        self.assertEqual(ui.active_overlay()[0], "ESTOP")
        state.clear_estop_latch()
        ui.refresh_context()
        self.assertEqual(ui.active_overlay()[0], "ALARM")
        state.alarm = None
        ui.refresh_context()
        self.assertEqual(ui.active_overlay()[0], "CONTROLLER OFFLINE")
        self.assertIsNone(ui.handle(ROTATE_CW))

    def test_disabled_entry_cannot_emit_command(self):
        _, ui = ready_ui()
        ui.enter("MAIN_MENU")
        ui.enter("SETTINGS")
        self.assertIsNone(ui.handle(SELECT))
        self.assertIn("not implemented", ui.toast)


class UIIntegrationTests(unittest.TestCase):
    def make_app(self, root, wifi=None):
        jobs = os.path.join(root, "jobs")
        macros = os.path.join(root, "macros")
        os.mkdir(jobs)
        os.mkdir(macros)
        transport = MockTransport()
        app = PendantApplication.from_config(
            {"controller_mode": "mock", "jobs_path": jobs,
             "macros_path": macros, "status_interval": 100,
             "base_increment": 0.001, "jog_feed": 500},
            transport=transport, display=ConsoleDisplay(lambda value: None),
            network_service=wifi or MockWiFiService(), clock=lambda: 1.0,
        )
        app.state.connection_state = "connected"
        app.state.machine_state = "idle"
        app.state.deadman_enabled = True
        app.state.selected_physical_axis = "X"
        app.state.selected_axis = "X"
        app.ui.refresh_context()
        return app, jobs, macros

    def test_same_wheel_jogs_navigates_ssids_and_edits_text(self):
        with tempfile.TemporaryDirectory() as root:
            wifi = MockWiFiService([("cda_Lab", -30), ("Shop", -50)])
            app, _, _ = self.make_app(root, wifi)
            app.handle_ui_event(ROTATE_CW)
            app.controller.poll(1)
            jog_count = sum(b"$J=" in write for write in app.transport.writes)
            self.assertEqual(jog_count, 1)

            app.handle_ui_event(SELECT)  # Main Menu
            app.handle_ui_event(ROTATE_CW)
            self.assertEqual(app.ui.focus["MAIN_MENU"], 1)
            self.assertEqual(sum(b"$J=" in w for w in app.transport.writes), 1)

            # Navigate directly to Network, then use its real scan command.
            app.ui.enter("NETWORK")
            app.handle_ui_event(ROTATE_CW)  # Scan Networks
            app.handle_ui_event(SELECT)
            self.assertEqual(app.ui.current_screen, "WIFI_SCAN")
            app.handle_ui_event(ROTATE_CW)
            self.assertEqual(app.ui.selected_item().value, "Shop")
            self.assertEqual(sum(b"$J=" in w for w in app.transport.writes), 1)

            app.handle_ui_event(SELECT)
            self.assertEqual(app.ui.current_screen, "TEXT_ENTRY")
            selected = app.ui.text_entry.selected_character
            app.handle_ui_event(ROTATE_CW)
            self.assertNotEqual(app.ui.text_entry.selected_character, selected)
            self.assertEqual(sum(b"$J=" in w for w in app.transport.writes), 1)

    def test_wifi_password_submission_is_masked_and_not_retained(self):
        with tempfile.TemporaryDirectory() as root:
            wifi = MockWiFiService([("cda_Lab", -30)])
            app, _, _ = self.make_app(root, wifi)
            app.ui.enter("MAIN_MENU")
            app.ui.enter("NETWORK")
            app.ui.set_dynamic_items("ssids", wifi.scan())
            app.ui.enter("WIFI_SCAN")
            app.handle_ui_event(SELECT)
            app.handle_ui_event(SELECT)  # 'a'
            self.assertEqual(app.ui.view_model()["text"], "•")
            app.handle_ui_event(LONG_SELECT)
            self.assertTrue(wifi.connected)
            self.assertEqual(wifi.password_length, 1)
            self.assertIsNone(app.ui.text_entry)

    def test_file_job_flow_hold_resume_and_cancel(self):
        with tempfile.TemporaryDirectory() as root:
            app, jobs, _ = self.make_app(root)
            with open(os.path.join(jobs, "part.nc"), "w") as output:
                output.write("G0 X0\n")
            with open(os.path.join(jobs, "second.tap"), "w") as output:
                output.write("G0 Y0\n")
            app.ui.enter("MAIN_MENU")
            app.ui.enter("JOBS")
            app.handle_ui_event(SELECT)  # Browse
            self.assertEqual(app.ui.current_screen, "JOB_BROWSER")
            writes_before = list(app.transport.writes)
            app.handle_ui_event(ROTATE_CW)
            self.assertEqual(app.ui.selected_item().value, "second.tap")
            self.assertEqual(app.transport.writes, writes_before)
            app.handle_ui_event(ROTATE_CCW)
            app.handle_ui_event(SELECT)
            self.assertEqual(app.ui.current_screen, "JOB_DETAILS")
            app.handle_ui_event(SELECT)
            app.handle_ui_event(ROTATE_CW)
            app.handle_ui_event(SELECT)
            self.assertEqual(app.ui.current_screen, "ACTIVE_JOB")
            self.assertEqual(app.state.current_filename, "part.nc")
            model = app.ui.view_model()
            self.assertEqual(model["filename"], "part.nc")
            self.assertIn("progress", model)
            app.handle_ui_event(SELECT)  # Hold
            self.assertEqual(app.state.sd_job_state, "paused")
            app.handle_ui_event(ROTATE_CW)
            app.handle_ui_event(SELECT)  # Resume
            self.assertEqual(app.state.sd_job_state, "streaming")
            app.handle_ui_event(ROTATE_CW)
            app.handle_ui_event(SELECT)  # Cancel confirmation
            app.handle_ui_event(ROTATE_CW)
            app.handle_ui_event(SELECT)
            self.assertEqual(app.state.sd_job_state, "cancelled")

    def test_macro_selection_requires_confirmation(self):
        with tempfile.TemporaryDirectory() as root:
            app, _, macros = self.make_app(root)
            with open(os.path.join(macros, "park.gcode"), "w") as output:
                output.write("G53 G0 Z0\n")
            app.ui.enter("MAIN_MENU")
            app.ui.enter("MACROS")
            app.handle_ui_event(SELECT)
            app.handle_ui_event(SELECT)
            self.assertEqual(app.ui.current_screen, "MACRO_DETAILS")
            app.handle_ui_event(SELECT)
            self.assertEqual(app.controller.queue, [])
            app.handle_ui_event(ROTATE_CW)
            app.handle_ui_event(SELECT)
            self.assertEqual(app.controller.queue[-1][1], "macro")


if __name__ == "__main__":
    unittest.main()
