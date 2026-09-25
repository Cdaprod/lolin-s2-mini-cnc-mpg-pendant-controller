import unittest

from src.display.displayio_backend import DisplayIOBackend
from src.display.ui import UIManager
from src.state import PendantState


class Node:
    def __init__(self):
        self.y = 0


class Group(list):
    pass


class Line:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.node = Node()
        self.text = ""
        self.updates = 0

    def set_text(self, text):
        text = str(text)
        if text == self.text:
            return False
        self.text = text
        self.updates += 1
        return True


class Display:
    width = 128
    height = 64

    def __init__(self):
        self.root_group = None
        self.refreshes = 0

    def refresh(self, minimum_frames_per_second=0):
        self.refreshes += 1


class DisplayIOBackendTests(unittest.TestCase):
    def make_renderer(self):
        state = PendantState()
        state.connection_state = "connected"
        state.machine_state = "idle"
        ui = UIManager(state)
        ui.complete_boot()
        ui.refresh_context()
        display = Display()
        renderer = DisplayIOBackend(
            display, line_factory=Line, group_factory=Group
        )
        renderer.bind_ui(ui)
        return state, ui, display, renderer

    def test_retained_dirty_render_skips_unchanged_frame(self):
        state, _, display, renderer = self.make_renderer()
        self.assertTrue(renderer.render(state))
        first_updates = sum(line.updates for line in renderer.body)
        self.assertFalse(renderer.render(state))
        self.assertEqual(renderer.render_count, 1)
        self.assertEqual(renderer.skipped_count, 1)
        self.assertEqual(sum(line.updates for line in renderer.body), first_updates)
        self.assertEqual(display.refreshes, 1)

    def test_overlay_precedence_and_missing_long_coordinates(self):
        state, ui, _, renderer = self.make_renderer()
        state.work_position["X"] = 12345678901234567890.0
        state.work_position["Y"] = None
        state.connection_state = "disconnected"
        ui.refresh_context()
        renderer.render(state)
        self.assertEqual(renderer.overlay.text, "")
        state.alarm = "2"
        state.set_estop(True)
        ui.refresh_context()
        renderer.render(state)
        self.assertIn("MOTION INHIBITED", renderer.overlay.text)


if __name__ == "__main__":
    unittest.main()
