import unittest

from src.display.round_ui.renderer import RoundRenderer
from src.display.round_ui.bootstrap import apply_mock_state
from src.display.round_ui.geometry import RoundLayout
from src.display.ui import ROTATE_CCW, ROTATE_CW, SELECT, UIManager
from src.state import PendantState


class Node:
    def __init__(self):
        self.color = 0
        self.hidden = False


class Line:
    def __init__(self):
        self.text = ""
        self.updates = 0

    def set_text(self, value):
        value = str(value)
        if self.text == value:
            return False
        self.text = value
        self.updates += 1
        return True


class Display:
    def __init__(self):
        self.root_group = None
        self.refreshes = 0

    def refresh(self, minimum_frames_per_second=0):
        self.refreshes += 1


def scene_factory(display):
    return {
        "root": Node(), "ring": Node(), "title": Line(), "axis": Line(),
        "value": Line(), "secondary": Line(), "multiplier": Line(),
        "activity": Line(), "indicators": Line(), "tabs": [Line()],
        "menu": [Line() for _ in range(6)], "overlay_group": Node(),
        "overlay_title": Line(), "overlay_detail": Line(),
    }


class RoundRendererTests(unittest.TestCase):
    def test_bootstrap_populates_representative_state(self):
        state = PendantState()
        apply_mock_state(state)
        self.assertEqual(state.work_position["X"], 124.520)
        self.assertEqual(state.selected_multiplier, "X10")
        self.assertEqual(state.wifi_state, "DISABLED")
        self.assertEqual(state.connection_state, "disconnected")

    def make_renderer(self):
        state = PendantState()
        state.connection_state = "connected"
        state.machine_state = "idle"
        state.storage_state = "available"
        state.selected_axis = "X"
        state.work_position.update({"X": 124.520, "Y": 2.0, "Z": -3.0,
                                    "A": 0.0})
        ui = UIManager(state)
        ui.complete_boot()
        display = Display()
        renderer = RoundRenderer(display, scene_factory)
        renderer.bind_ui(ui)
        return state, ui, display, renderer

    def test_maps_home_state_and_updates_only_changed_component(self):
        state, _, display, renderer = self.make_renderer()
        self.assertTrue(renderer.render(state))
        self.assertEqual(renderer.axis.axis.value, "X")
        self.assertEqual(renderer.axis.value.value, "+124.520")
        self.assertEqual(renderer.title.value, "IDLE / MOTION OFF")
        self.assertEqual(renderer.activity.text.value, "HOLD:OFF  MPG:---")
        self.assertEqual(renderer.tabs.lines[0].text, "> TAP: MENU")
        axis_updates = renderer.axis.axis.line.updates
        value_updates = renderer.axis.value.line.updates
        self.assertFalse(renderer.render(state))
        self.assertEqual(display.refreshes, 1)
        state.work_position["X"] = 125.0
        self.assertTrue(renderer.render(state))
        self.assertEqual(renderer.axis.axis.line.updates, axis_updates)
        self.assertEqual(renderer.axis.value.line.updates, value_updates + 1)

    def test_home_prioritizes_armed_hold_and_signed_relative_activity(self):
        state, _, _, renderer = self.make_renderer()
        state.deadman_enabled = True
        state.mpg_activity = -4
        renderer.render(state)
        self.assertEqual(renderer.title.value, "IDLE / JOG ARMED")
        self.assertEqual(renderer.activity.text.value, "HOLD:ON  MPG:CCW <<<")
        state.mpg_activity = 2
        renderer.render(state)
        self.assertEqual(renderer.activity.text.value, "HOLD:ON  MPG:CW >>")

    def test_existing_ui_navigation_and_overlay_drive_round_components(self):
        state, ui, _, renderer = self.make_renderer()
        renderer.render(state)
        ui.handle(SELECT)
        renderer.render(state)
        self.assertEqual(ui.current_screen, "MAIN_MENU")
        self.assertTrue(renderer.menu[0].value.startswith("› "))
        state.alarm = "2"
        ui.refresh_context()
        renderer.render(state)
        self.assertFalse(renderer.overlay.group.hidden)
        self.assertEqual(renderer.overlay.title.value, "ALARM")

    def test_long_diagnostics_scroll_both_directions(self):
        _, ui, _, renderer = self.make_renderer()
        ui.enter("MAIN_MENU")
        ui.enter("SYSTEM")
        ui.detail_title = "Diagnostics"
        ui.enter("SYSTEM_INFO")
        self.assertEqual(len(ui.items()), 18)
        renderer.render(ui.state)
        first = [line.value for line in renderer.menu]
        self.assertIn("CircuitPython", first[0])
        for _ in range(17):
            ui.handle(ROTATE_CW)
        renderer.render(ui.state)
        self.assertEqual(ui.focus["SYSTEM_INFO"], 17)
        self.assertTrue(any("Last error" in line.value for line in renderer.menu))
        ui.handle(ROTATE_CCW)
        renderer.render(ui.state)
        self.assertEqual(ui.focus["SYSTEM_INFO"], 16)
        for _ in range(16):
            ui.handle(ROTATE_CCW)
        renderer.render(ui.state)
        self.assertEqual([line.value for line in renderer.menu], first)

    def test_six_row_network_details_need_no_window_shift(self):
        _, ui, _, renderer = self.make_renderer()
        ui.enter("MAIN_MENU")
        ui.enter("NETWORK")
        ui.enter("NETWORK_INFO")
        renderer.render(ui.state)
        self.assertEqual(len(ui.items()), 6)
        self.assertTrue(renderer.menu[0].value.startswith("› Wi-Fi"))
        self.assertIn("Reason", renderer.menu[5].value)

    def test_layout_regions_are_inside_round_safe_area(self):
        for region in RoundLayout.content_rows().values():
            self.assertTrue(RoundLayout.region_within_safe_circle(region))
        self.assertTrue(RoundLayout.region_within_safe_circle(RoundLayout.MODAL))


if __name__ == "__main__":
    unittest.main()
