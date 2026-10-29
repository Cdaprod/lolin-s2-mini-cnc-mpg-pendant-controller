import unittest
from unittest.mock import patch

from src.display.round_ui.renderer import RoundRenderer, _profile_ticks_diff
from src.display.round_ui.bootstrap import apply_mock_state
from src.display.round_ui.geometry import RoundLayout
from src.display.round_ui import theme
from src.display.ui import ROTATE_CCW, ROTATE_CW, SELECT, UIManager
from src.state import PendantState


class Node:
    def __init__(self):
        self.color = 0
        self.hidden = False
        self.y = 0

    def update(self, state, activity, armed, axis_transition,
               increment_transition):
        self.state = state
        self.activity = activity
        self.armed = armed
        self.axis_transition = axis_transition
        self.increment_transition = increment_transition


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
        "root": Node(), "ring": Node(), "state_label": Line(),
        "axis_feedback": Line(), "step_feedback": Line(),
        "axis": Line(), "value": Line(), "context": Line(),
        "increment": Line(), "motion": Line(), "connectivity": Line(),
        "menu_title": Line(), "menu": [Line() for _ in range(6)],
        "menu_highlight": Node(), "menu_footer": Line(),
        "overlay_group": Node(),
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

    def test_empty_job_browser_renders_storage_status_instead_of_blank_rows(self):
        state, ui, _, renderer = self.make_renderer()
        state.storage_state = "unconfigured"
        state.subsystems = {"sd": "DISABLED"}
        ui.enter("EXPLORER")

        renderer.render(state)

        self.assertEqual(renderer.menu[0].line.text, "")
        self.assertEqual(renderer.menu[3].line.text, "SD CARD DISABLED")
        self.assertEqual(renderer.menu[4].line.text, "ENABLE IN SETTINGS")
        self.assertTrue(renderer.menu_highlight.node.hidden)

    def test_empty_job_browser_explanation_is_centered_and_not_selectable(self):
        state, ui, _, renderer = self.make_renderer()
        state.storage_state = "available"
        ui.enter("EXPLORER")

        renderer.render(state)

        self.assertEqual(renderer.menu[0].line.text, "")
        self.assertEqual(renderer.menu[3].line.text, "NO FILES FOUND")
        self.assertEqual(renderer.menu[4].line.text, "SD CARD READY")
        self.assertTrue(renderer.menu_highlight.node.hidden)

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

    def test_hud_orbit_is_rate_limited_and_suppressed_on_estop(self):
        state, ui, display, renderer = self.make_renderer()
        first, second = Node(), Node()
        first.x = second.x = 0
        first.y = second.y = 0
        renderer.hud_markers = ((first, 109, None), (second, 99, None))
        self.assertTrue(renderer.animate(0.20))
        self.assertNotEqual((first.x, first.y), (0, 0))
        initial = (first.x, first.y)
        self.assertFalse(renderer.animate(0.205))  # same 24 Hz frame
        self.assertEqual((first.x, first.y), initial)
        self.assertTrue(renderer.animate(0.40))
        self.assertNotEqual((first.x, first.y), initial)
        state.estop_observed = True
        self.assertTrue(renderer.animate(0.55))
        self.assertTrue(first.hidden)
        self.assertTrue(second.hidden)
        state.estop_observed = False
        self.assertTrue(renderer.animate(0.70))
        self.assertFalse(first.hidden)

    def test_hud_markers_move_at_most_one_pixel_per_24hz_frame(self):
        _, _, _, renderer = self.make_renderer()
        markers = []
        for radius in (109, 99):
            marker = Node()
            marker.x = marker.y = 0
            markers.append(marker)
        renderer.hud_markers = tuple(
            (marker, radius, None)
            for marker, radius in zip(markers, (109, 99))
        )
        previous = None
        first_delta = second_delta = 0
        for frame in range(241):
            renderer.animate(frame / 24.0)
            current = tuple((marker.x, marker.y) for marker in markers)
            if previous is not None and current != previous:
                for before, after in zip(previous, current):
                    self.assertLessEqual(abs(after[0] - before[0]), 1)
                    self.assertLessEqual(abs(after[1] - before[1]), 1)
                # Signed tangent directions at t=0 verify counter-rotation.
                if frame < 30:
                    first_delta += current[0][1] - previous[0][1]
                    second_delta += current[1][1] - previous[1][1]
            previous = current
        self.assertGreater(first_delta, 0)
        self.assertLess(second_delta, 0)

    def test_home_and_menu_groups_are_mutually_exclusive(self):
        state, ui, _, renderer = self.make_renderer()
        renderer.home_group = Node()
        renderer.menu_group = Node()
        renderer.render(state)
        self.assertFalse(renderer.home_group.hidden)
        self.assertTrue(renderer.menu_group.hidden)
        self.assertIsNone(renderer.menu_title.value)
        ui.enter("MAIN_MENU")
        renderer.render(state)
        self.assertTrue(renderer.home_group.hidden)
        self.assertFalse(renderer.menu_group.hidden)
        self.assertEqual(renderer.menu_title.value,
                         ui.screens["MAIN_MENU"].title)
        ui.back()
        renderer.render(state)
        self.assertFalse(renderer.home_group.hidden)
        self.assertTrue(renderer.menu_group.hidden)

    def test_maps_home_state_and_updates_only_changed_component(self):
        state, _, display, renderer = self.make_renderer()
        self.assertTrue(renderer.render(state))
        self.assertEqual(renderer.axis.axis.value, "X")
        self.assertEqual(renderer.axis.value.value, "+124.520")
        self.assertEqual(renderer.state_label.value, "IDLE")
        self.assertEqual(renderer.motion.text.value, "HOLD TO JOG")
        axis_updates = renderer.axis.axis.line.updates
        value_updates = renderer.axis.value.line.updates
        with patch.object(renderer.ui, "view_model",
                          side_effect=AssertionError("idle home redraw")):
            self.assertFalse(renderer.render(state))
        self.assertGreaterEqual(renderer.last_model_ms, 0)
        self.assertGreaterEqual(renderer.last_update_ms, 0)
        self.assertGreaterEqual(renderer.last_refresh_ms, 0)
        self.assertEqual(display.refreshes, 1)
        renderer._hud_dirty = True
        with patch.object(renderer.ui, "view_model",
                          side_effect=AssertionError("transient full redraw")):
            self.assertTrue(renderer.render(state))
        self.assertFalse(renderer._hud_dirty)
        self.assertEqual(display.refreshes, 2)
        state.work_position["X"] = 125.0
        self.assertTrue(renderer.render(state))
        self.assertEqual(renderer.axis.axis.line.updates, axis_updates)
        self.assertEqual(renderer.axis.value.line.updates, value_updates + 1)

    def test_nonhome_view_model_is_bounded_but_dirty_actions_render_now(self):
        state, ui, _, renderer = self.make_renderer()
        ui.enter("NETWORK_INFO")
        ticks = [0]
        renderer._profile_ticks_ms = lambda: ticks[0]
        renderer.render(state)
        self.assertEqual(renderer.menu[0].line.text, "Wi-Fi: DISABLED")

        state.wifi_state = "CONNECTED"
        ticks[0] = 10
        with patch.object(ui, "view_model", wraps=ui.view_model) as view_model:
            self.assertFalse(renderer.render(state))
            self.assertEqual(view_model.call_count, 0)
            self.assertEqual(renderer.menu[0].line.text, "Wi-Fi: DISABLED")

            ticks[0] = 33
            self.assertTrue(renderer.render(state))
            self.assertEqual(view_model.call_count, 1)
            self.assertEqual(renderer.menu[0].line.text, "Wi-Fi: CONNECTED")

            ui._changed()
            ticks[0] = 34
            self.assertFalse(renderer.render(state))
            self.assertEqual(view_model.call_count, 2)

    def test_nonhome_transient_hud_refresh_skips_view_model(self):
        state, ui, display, renderer = self.make_renderer()
        ui.enter("MAIN_MENU")
        ticks = [0]
        renderer._profile_ticks_ms = lambda: ticks[0]
        renderer.render(state)
        ticks[0] = 5
        renderer._hud_dirty = True
        refreshes = display.refreshes
        with patch.object(ui, "view_model",
                          side_effect=AssertionError("transient full redraw")):
            self.assertTrue(renderer.render(state))
        self.assertFalse(renderer._hud_dirty)
        self.assertEqual(display.refreshes, refreshes + 1)

    def test_auto_refresh_display_uses_nonblocking_background_refresh(self):
        state, _, display, renderer = self.make_renderer()
        display.auto_refresh = True
        self.assertTrue(renderer.render(state))
        renderer._hud_dirty = True
        self.assertTrue(renderer.render(state))
        self.assertEqual(display.refreshes, 0)

    def test_renderer_timing_delta_handles_tick_wrap(self):
        period = 1 << 29
        self.assertEqual(_profile_ticks_diff(4, period - 3), 7)

    def test_home_prioritizes_armed_hold_and_signed_relative_activity(self):
        state, _, _, renderer = self.make_renderer()
        state.deadman_enabled = True
        state.input_valid = True
        state.mpg_activity = -4
        renderer.render(state)
        self.assertEqual(renderer.state_label.value, "READY")
        self.assertEqual(renderer.motion.text.value, "<<<<  CCW")
        self.assertEqual(renderer.ring.node.activity, -4)
        state.mpg_activity = 2
        renderer.render(state)
        self.assertEqual(renderer.motion.text.value, "CW  >>")
        self.assertEqual(renderer.ring.node.activity, 2)

    def test_existing_ui_navigation_and_overlay_drive_round_components(self):
        state, ui, _, renderer = self.make_renderer()
        self.assertTrue(renderer.overlay.group.hidden)
        renderer.render(state)
        self.assertTrue(renderer.overlay.group.hidden)
        ui.handle(SELECT)
        renderer.render(state)
        self.assertEqual(ui.current_screen, "MAIN_MENU")
        self.assertEqual(renderer.menu[0].value, "Machine")
        self.assertEqual(renderer.menu_highlight.node.y, 58)
        state.alarm = "2"
        ui.refresh_context()
        renderer.render(state)
        self.assertFalse(renderer.overlay.group.hidden)
        self.assertEqual(renderer.overlay.title.value, "ALARM")
        state.alarm = None
        ui.refresh_context()
        renderer.render(state)
        self.assertTrue(renderer.overlay.group.hidden)
        self.assertEqual(renderer.overlay.title.value, "")
        self.assertEqual(renderer.overlay.detail.value, "")

    def test_exceptional_and_selector_states_are_immediate(self):
        state, ui, _, renderer = self.make_renderer()
        renderer.render(state)
        state.selected_axis = "Z"
        state.axis_transition_direction = 1
        state.selected_multiplier = "X100"
        state.resolution_transition_direction = -1
        renderer.render(state)
        self.assertEqual(renderer.axis.axis.value, "Z")
        self.assertEqual(renderer.increment.text.value, "X100")
        self.assertEqual(renderer.axis_feedback.text.value, "AXIS >Z")
        self.assertEqual(renderer.step_feedback.text.value, "STEP <X100")
        self.assertEqual(renderer.ring.node.axis_transition, 1)
        self.assertEqual(renderer.ring.node.increment_transition, -1)

        state.connection_state = "disconnected"
        ui.refresh_context()
        renderer.render(state)
        self.assertEqual(renderer.motion.text.value, "CONTROLLER OFFLINE")

        state.set_estop(True)
        ui.refresh_context()
        renderer.render(state)
        self.assertEqual(renderer.overlay.title.value, "E-STOP")
        self.assertEqual(renderer.overlay.detail.value, "MOTION INHIBITED")
        self.assertEqual(renderer.ring.node.state, "estop")

        state.estop_observed = False
        ui.refresh_context()
        renderer.render(state)
        self.assertEqual(renderer.overlay.detail.value, "RECOVERY REQUIRED")

    def test_long_diagnostics_scroll_both_directions(self):
        _, ui, _, renderer = self.make_renderer()
        ui.enter("MAIN_MENU")
        ui.enter("SYSTEM")
        ui.detail_title = "Diagnostics"
        ui.enter("SYSTEM_INFO")
        self.assertEqual(len(ui.items()), 21)
        renderer.render(ui.state)
        first = [line.value for line in renderer.menu]
        self.assertIn("CircuitPython", first[0])
        for _ in range(20):
            ui.handle(ROTATE_CW)
        renderer.render(ui.state)
        self.assertEqual(ui.focus["SYSTEM_INFO"], 20)
        self.assertTrue(any("Last error" in line.value for line in renderer.menu))
        ui.handle(ROTATE_CCW)
        renderer.render(ui.state)
        self.assertEqual(ui.focus["SYSTEM_INFO"], 19)
        for _ in range(19):
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
        self.assertTrue(renderer.menu[0].value.startswith("Wi-Fi"))
        self.assertIn("Reason", renderer.menu[5].value)

    def test_palettes_supply_safe_named_tokens(self):
        required = {"background", "panel", "text", "muted", "accent",
                    "success", "warning", "danger", "highlight"}
        for name in ("industrial", "ice", "amber", "spectrum"):
            palette = theme.select(name)
            self.assertTrue(required.issubset(palette))
            self.assertNotEqual(palette["text"], palette["background"])
        self.assertEqual(theme.select("unknown"), theme.select("industrial"))

    def test_hud_shades_scale_each_rgb_channel(self):
        self.assertEqual(theme.shade_color(0x80C040, 50), 0x406020)
        self.assertEqual(theme.shade_color(0x80C040, 0), 0x000000)

    def test_touch_feedback_nonblocking_expiration(self):
        state, ui, display, renderer = self.make_renderer()
        class Halo(Node):
            def __init__(self):
                super().__init__()
                self.x = 0
                self.hidden = True
        renderer.touch_halo = Halo()
        renderer.render(state)
        initial = display.refreshes
        renderer.touch_feedback((120, 120), 1.2)
        self.assertFalse(renderer.touch_halo.hidden)
        self.assertFalse(renderer.animate(1.1))
        self.assertTrue(renderer.render(state))
        self.assertEqual(display.refreshes, initial + 1)
        self.assertFalse(renderer.render(state))
        self.assertTrue(renderer.animate(1.2))
        self.assertTrue(renderer.touch_halo.hidden)
        self.assertTrue(renderer.render(state))

    def test_layout_regions_are_inside_round_safe_area(self):
        for region in RoundLayout.content_rows().values():
            self.assertTrue(RoundLayout.region_within_safe_circle(region))



    def test_transient_top_page_dots_follow_physical_order(self):
        state, ui, _, renderer = self.make_renderer()
        nav = Node()
        nav.hidden = True
        renderer.nav_group = nav
        renderer.nav_dots = [(Node(), [0, 0]) for _ in range(4)]
        renderer.render(state)
        self.assertFalse(nav.hidden)
        self.assertEqual([palette[1] for _, palette in renderer.nav_dots],
                         [0xFFFFFF, 0x667176, 0x667176, 0x667176])
        positions = [node.x for node, _ in renderer.nav_dots]
        self.assertEqual(positions, sorted(positions))
        state.active_page = "PREVIEW"
        ui.apply_selector_context()
        renderer.render(state)
        self.assertEqual([palette[1] for _, palette in renderer.nav_dots],
                         [0x667176, 0x667176, 0x667176, 0xFFFFFF])
        self.assertFalse(nav.hidden)
        self.assertTrue(renderer.animate(renderer._nav_until + 0.01))
        self.assertTrue(nav.hidden)
        renderer.render(state)
        self.assertTrue(nav.hidden)
        state.alarm = "2"
        ui.refresh_context()
        ui.enter("SYSTEM")
        renderer.render(state)
        self.assertTrue(nav.hidden)

    def test_scrolling_focus_is_centered_after_initial_rows(self):
        from src.display.navigation import menu_window_start
        self.assertEqual(menu_window_start(0, 21, 6), 0)
        self.assertEqual(menu_window_start(5, 21, 6), 3)
        self.assertEqual(menu_window_start(20, 21, 6), 15)
        self.assertEqual(menu_window_start(0, 3, 6), 0)
        state, ui, _, renderer = self.make_renderer()
        ui.enter("MAIN_MENU")
        ui.enter("SYSTEM")
        ui.detail_title = "Diagnostics"
        ui.enter("SYSTEM_INFO")
        for _ in range(9):
            ui.handle(ROTATE_CW)
        renderer.render(state)
        self.assertEqual(renderer.menu_highlight.row, 2)
        self.assertIn("I2C", renderer.menu[0].value)


    def test_physical_pages_use_ordered_themes(self):
        self.assertEqual(theme.for_page("HOME"), theme.THEMES["industrial"])
        self.assertEqual(theme.for_page("EXPLORER"), theme.THEMES["amber"])
        self.assertEqual(theme.for_page("CONFIGURATION"), theme.THEMES["ice"])
        self.assertEqual(theme.for_page("PREVIEW"), theme.THEMES["spectrum"])

    def test_theme_changes_only_when_physical_page_changes(self):
        state, ui, display, renderer = self.make_renderer()
        renderer.render(state)
        self.assertEqual(renderer.active_theme, "industrial")
        ui.enter("MAIN_MENU")
        renderer.render(state)
        self.assertEqual(renderer.active_theme, "industrial")
        state.active_page = "EXPLORER"
        ui.apply_selector_context()
        renderer.render(state)
        self.assertEqual(renderer.active_theme, "amber")
        ui.enter("MAIN_MENU")
        renderer.render(state)
        self.assertEqual(renderer.active_theme, "amber")
        state.active_page = "CONFIGURATION"
        ui.apply_selector_context()
        renderer.render(state)
        self.assertEqual(renderer.active_theme, "ice")
        state.active_page = "PREVIEW"
        ui.apply_selector_context()
        renderer.render(state)
        self.assertEqual(renderer.active_theme, "spectrum")

if __name__ == "__main__":
    unittest.main()
