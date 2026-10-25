"""Browser mirror authorization and motion-dispatch regression tests."""
import unittest
from src.network_mirror import PendantMirror
from src.display.ui import UIManager
from src.state import PendantState


class FakeApp:
    def __init__(self):
        self.state = PendantState()
        self.state.machine_state = "idle"
        self.state.connection_state = "connected"
        self.ui = UIManager(self.state)
        self.ui.complete_boot()
        self.ui.refresh_context()


def mirror(allow=True):
    # Bypass hardware socket init to test pure input authorization.
    obj = PendantMirror.__new__(PendantMirror)
    obj.app = FakeApp()
    obj.allow_navigation = allow
    return obj


class MirrorTests(unittest.TestCase):
    def test_opt_in_disabled(self):
        m = mirror(False)
        m.app.ui.enter("MAIN_MENU")
        self.assertFalse(m.navigate({"kind": "tap", "x": 100, "y": 60}))
        self.assertEqual(m.app.ui.current_screen, "MAIN_MENU")

    def test_submenu_entry_and_back(self):
        m = mirror()
        m.app.ui.enter("MAIN_MENU")
        self.assertTrue(m.navigate({"kind": "tap", "x": 100, "y": 60}))
        self.assertEqual(m.app.ui.current_screen, "MACHINE")
        self.assertTrue(m.navigate({"kind": "tap", "x": 20, "y": 210}))
        self.assertEqual(m.app.ui.current_screen, "MAIN_MENU")

    def test_motion_and_confirmation_not_accessible(self):
        m = mirror()
        self.assertFalse(m.navigate({"kind": "tap", "x": 120, "y": 120}))
        m.app.ui.enter("MAIN_MENU")
        m.app.ui.enter("MACHINE")
        self.assertFalse(m.navigate({"kind": "tap", "x": 120, "y": 60}))
        self.assertIsNone(m.app.ui.confirmation)

    def test_network_mutation_rejected(self):
        m = mirror()
        m.app.ui.enter("NETWORK")
        self.assertFalse(m.navigate({"kind": "tap", "x": 100, "y": 60}))

    def test_invalid_input_rejected(self):
        m = mirror()
        m.app.ui.enter("MAIN_MENU")
        for request in ({"kind": "swipe_left", "x": 20, "y": 20},
                        {"kind": "tap", "x": -1, "y": 60},
                        {"kind": "tap", "x": True, "y": 60},
                        {"kind": "tap", "x": 240, "y": 60}):
            self.assertFalse(m.navigate(request))

    def test_safety_overlay_blocks_browser_navigation(self):
        m = mirror()
        m.app.ui.enter("MAIN_MENU")
        m.app.state.set_estop(True)
        self.assertFalse(m.navigate({"kind": "tap", "x": 120, "y": 60}))

    def test_snapshot_omits_sensitive_details(self):
        m = mirror()
        m.app.ui.enter("NETWORK_INFO")
        result = m.snapshot()
        self.assertNotIn("details", result["ui"])
        self.assertNotIn("jog_armed", result["ui"])
        self.assertNotIn("motion_available", result["ui"])


if __name__ == "__main__":
    unittest.main()
