import unittest

from src.display.round_ui.renderer import RoundRenderer
from src.display.round_ui.bootstrap import apply_mock_state
from src.display.ui import SELECT, UIManager
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
        "indicators": Line(), "tabs": [Line() for _ in range(5)],
        "menu": [Line() for _ in range(6)], "overlay_group": Node(),
        "overlay_title": Line(), "overlay_detail": Line(),
    }


class RoundRendererTests(unittest.TestCase):
    def test_bootstrap_populates_representative_state(self):
        state = PendantState()
        apply_mock_state(state)
        self.assertEqual(state.work_position["X"], 124.520)
        self.assertEqual(state.selected_multiplier, "X10")
        self.assertEqual(state.wifi_state, "connected")

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
        axis_updates = renderer.axis.axis.line.updates
        value_updates = renderer.axis.value.line.updates
        self.assertFalse(renderer.render(state))
        self.assertEqual(display.refreshes, 1)
        state.work_position["X"] = 125.0
        self.assertTrue(renderer.render(state))
        self.assertEqual(renderer.axis.axis.line.updates, axis_updates)
        self.assertEqual(renderer.axis.value.line.updates, value_updates + 1)

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


if __name__ == "__main__":
    unittest.main()
