import unittest
import math
from unittest.mock import patch

from src.display.round_ui.renderer import RoundRenderer, _profile_ticks_diff
from src.display.round_ui.components import MenuHighlight
from src.display.round_ui.bootstrap import apply_mock_state
from src.display.round_ui.geometry import RoundLayout
from src.display.round_ui.effects import TOUCH_BITMAP_CENTER
from src.display.round_ui.effects import TOUCH_HOLD_PROGRESS
from src.display.round_ui import bezel_palette, theme
from src.display.round_ui.rotor import (bezel_segment_levels,
                                        update_bezel_segment_levels)
from src.display.ui import ROTATE_CCW, ROTATE_CW, SELECT, UIManager
from src.state import PendantState


class Node:
    def __init__(self):
        self.color = 0
        self.hidden = False
        self.y = 0
        self.x = 0
        self.tile_index = 0
        self.pixel_shader = None

    def __getitem__(self, index):
        return self.tile_index

    def __setitem__(self, index, value):
        self.tile_index = value

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
        self.color = None
        self.updates = 0

    def set_text(self, value):
        value = str(value)
        if self.text == value:
            return False
        self.text = value
        self.updates += 1
        return True

    def set_color(self, value):
        if self.color == value:
            return False
        self.color = value
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
        "menu_separators": [Node() for _ in range(5)],
        "menu_highlight": Node(), "menu_footer": Line(),
        "overlay_group": Node(),
        "overlay_title": Line(), "overlay_detail": Line(),
    }


class RoundRendererTests(unittest.TestCase):
    def test_menu_highlight_uses_short_friction_settle(self):
        node = Node()
        node.hidden = True
        highlight = MenuHighlight(node)
        highlight.set(0, visible=True)
        self.assertEqual(node.y, 58)

        highlight.set(1, visible=True)
        self.assertEqual(node.y, 58)
        positions = [node.y]
        for _ in range(12):
            highlight.animate()
            positions.append(node.y)

        self.assertTrue(all(a <= b <= 80 for a, b in zip(positions,
                                                           positions[1:])))
        self.assertEqual(node.y, 80)

    def test_menu_highlight_is_immediate_when_animation_disabled(self):
        node = Node()
        node.hidden = True
        highlight = MenuHighlight(node)
        highlight.set(0, visible=True, animate=False)
        highlight.set(2, visible=True, animate=False)
        self.assertEqual(node.y, 102)

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
        self.assertTrue(all(separator.hidden
                            for separator in renderer.menu_separators))

    def test_empty_job_browser_explanation_is_centered_and_not_selectable(self):
        state, ui, _, renderer = self.make_renderer()
        state.storage_state = "available"
        ui.enter("EXPLORER")

        renderer.render(state)

        self.assertEqual(renderer.menu[0].line.text, "")
        self.assertEqual(renderer.menu[3].line.text, "NO FILES FOUND")
        self.assertEqual(renderer.menu[4].line.text, "SD CARD READY")
        self.assertTrue(renderer.menu_highlight.node.hidden)

    def test_unverified_and_active_remote_stop_have_semantic_color(self):
        state, ui, _, renderer = self.make_renderer()
        state.active_page = "PREVIEW"
        ui.enter("PREVIEW")
        ui.refresh_context()
        renderer.render(state)
        self.assertEqual(renderer.menu[5].value, "Remote stop: UNKNOWN")
        self.assertEqual(renderer.menu[5].line.color,
                         theme.for_page("PREVIEW")["warning"])

        state.estop_input_configured = True
        state.input_valid = True
        ui.refresh_context()
        ui.dirty = True
        renderer.render(state)
        self.assertEqual(renderer.menu[5].value, "Remote stop: CLEAR")
        self.assertEqual(renderer.menu[5].line.color,
                         theme.for_page("PREVIEW")["success"])

        state.estop_observed = True
        ui.refresh_context()
        ui.dirty = True
        renderer.render(state)
        self.assertEqual(renderer.menu[5].value, "Remote stop: ACTIVE")
        self.assertEqual(renderer.menu[5].line.color,
                         theme.for_page("PREVIEW")["danger"])

    def test_menu_rules_only_separate_visible_rows(self):
        state, ui, _, renderer = self.make_renderer()
        ui.enter("CONFIGURATION")

        renderer.render(state)

        self.assertEqual([separator.hidden
                          for separator in renderer.menu_separators],
                         [False, False, False, True, True])

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

    def test_bezel_rotation_is_disabled_without_mutating_encoder_state(self):
        state, _, _, renderer = self.make_renderer()
        renderer.bezel_rotation_enabled = False
        marker, trail = Node(), Node()
        marker.hidden = trail.hidden = False
        renderer.hud_markers = ((marker, 109, None), (Node(), 99, None))
        renderer.hud_trails = ((trail, 109, None), (Node(), 99, None))
        state.mpg_activity = -2
        state.mpg_activity_timestamp = 1.0
        before = (state.mpg_activity, state.mpg_activity_timestamp)
        renderer.animate(1.0)
        self.assertTrue(marker.hidden)
        self.assertTrue(trail.hidden)
        self.assertEqual((state.mpg_activity, state.mpg_activity_timestamp), before)

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

    def test_hud_motion_ghosts_follow_orbits_without_extra_scene_objects(self):
        _, _, _, renderer = self.make_renderer()
        markers = []
        trails = []
        for radius in (109, 99):
            marker, trail = Node(), Node()
            marker.x = marker.y = trail.x = trail.y = 0
            markers.append(marker)
            trails.append(trail)
        renderer.hud_markers = tuple(
            (marker, radius, None)
            for marker, radius in zip(markers, (109, 99))
        )
        renderer.hud_trails = tuple(
            (trail, radius, None)
            for trail, radius in zip(trails, (109, 99))
        )
        renderer.animate(0.25)
        self.assertTrue(all(not trail.hidden for trail in trails))
        initial = tuple((trail.x, trail.y) for trail in trails)
        renderer.animate(0.50)
        self.assertNotEqual(tuple((trail.x, trail.y) for trail in trails), initial)
        renderer.ui.active_overlay = lambda: ("E-STOP", "test")
        renderer.animate(0.75)
        self.assertTrue(all(trail.hidden for trail in trails))

    def test_rotating_bezel_segments_follow_rotor_and_yield_to_alarm(self):
        state, _, _, renderer = self.make_renderer()
        renderer.hud_markers = ((Node(), 109, None), (Node(), 99, None))
        segments = [Node() for _ in range(24)]
        renderer.bezel_segments = segments
        renderer.bezel_segment_palettes = [[0] + [1] * 15
                                           for _ in segments]
        renderer.rotor_tile_count = 384
        renderer._rotor_brightness_levels = [-1] * len(segments)
        renderer._rotor_target_levels = [0] * len(segments)
        renderer._rotor_color = theme.CYAN
        geometry = tuple((item.x, item.y, item.tile_index) for item in segments)

        self.assertTrue(renderer.animate(0.0))
        initial_levels = tuple(renderer._rotor_brightness_levels)
        self.assertTrue(all(not item.hidden for item in segments))

        state.mpg_activity = 2
        state.mpg_activity_timestamp = 0.1
        self.assertTrue(renderer.animate(0.1))
        self.assertNotEqual(tuple(renderer._rotor_brightness_levels),
                            initial_levels)
        self.assertEqual(tuple((item.x, item.y, item.tile_index)
                               for item in segments), geometry)

        renderer.ui.active_overlay = lambda: ("E-STOP", "test")
        renderer.animate(0.2)
        self.assertTrue(all(item.hidden for item in segments))

    def test_rotor_palette_bank_avoids_per_frame_palette_rewrites(self):
        class Palette(list):
            def __init__(self):
                super().__init__([0] * 16)
                self.writes = 0

            def __setitem__(self, index, value):
                self.writes += 1
                super().__setitem__(index, value)

        _, _, _, renderer = self.make_renderer()
        renderer.bezel_segments = [Node() for _ in range(24)]
        renderer.bezel_palette_bank = [Palette() for _ in range(16)]
        renderer.rotor_tile_count = 384
        renderer._rotor_brightness_levels = [-1] * 24
        renderer._rotor_target_levels = [0] * 24

        renderer._apply_rotor_color(theme.CYAN)
        self.assertTrue(all(
            segment.pixel_shader is renderer.bezel_palette_bank[level]
            for segment, level in zip(
                renderer.bezel_segments, renderer._rotor_brightness_levels)))
        writes_after_theme_setup = tuple(
            palette.writes for palette in renderer.bezel_palette_bank)

        renderer.animate(0.0)
        renderer.animate(0.1)

        self.assertEqual(tuple(palette.writes
                               for palette in renderer.bezel_palette_bank),
                         writes_after_theme_setup)
        self.assertTrue(all(
            segment.pixel_shader is renderer.bezel_palette_bank[level]
            for segment, level in zip(
                renderer.bezel_segments, renderer._rotor_brightness_levels)))

    def test_alarm_hides_rotor_when_decorative_animation_is_disabled(self):
        _, _, _, renderer = self.make_renderer()
        renderer.animations = False
        marker, trail = Node(), Node()
        renderer.hud_markers = ((marker, 109, None),)
        renderer.hud_trails = ((trail, 109, None),)
        segment = Node()
        segment.hidden = False
        segment.x, segment.y = 109, 120
        renderer.bezel_segments = [segment]
        overlay = [None]
        renderer.ui.active_overlay = lambda: overlay[0]

        renderer.animate(0.1)
        self.assertFalse(segment.hidden)
        self.assertTrue(marker.hidden)
        self.assertTrue(trail.hidden)

        overlay[0] = ("ALARM", "test alarm")
        renderer.animate(0.2)
        self.assertTrue(segment.hidden)
        self.assertTrue(marker.hidden)
        self.assertTrue(trail.hidden)

        overlay[0] = None
        renderer.animate(0.3)
        self.assertFalse(segment.hidden)
        self.assertTrue(marker.hidden)
        self.assertTrue(trail.hidden)
        self.assertEqual((segment.x, segment.y), (109, 120))

    def test_rotor_brightness_wave_follows_clockwise_and_counterclockwise(self):
        still = bezel_segment_levels(0.0, 24)
        clockwise = bezel_segment_levels(0.30, 24)
        counterclockwise = bezel_segment_levels(-0.30, 24)
        self.assertEqual(max(still), 15)
        self.assertGreater(clockwise[1], clockwise[0])
        self.assertGreater(counterclockwise[23], counterclockwise[0])
        self.assertTrue(all(1 <= value <= 15 for value in clockwise))

    def test_rotor_highlight_is_one_connected_traveling_arc(self):
        levels = bezel_segment_levels(0.0)
        self.assertEqual(len(levels), 24)
        self.assertEqual(levels[0], 15)
        self.assertEqual(sum(value >= 8 for value in levels), 5)
        self.assertTrue(all(levels[index] >= 8 for index in (22, 23, 0, 1, 2)))
        self.assertEqual(sum(value >= 8 for value in levels[3:22]), 0)
        self.assertEqual(levels[1], levels[-1])

    def test_rotor_animation_updates_a_retained_brightness_buffer(self):
        levels = [0] * 24
        identity = id(levels)
        update_bezel_segment_levels(0.3, levels)
        expected = bezel_segment_levels(0.3, 24)
        self.assertEqual(tuple(levels), expected)
        self.assertEqual(id(levels), identity)

    def test_critical_alarm_tints_bezel_red_and_restores_selected_theme(self):
        _, _, _, renderer = self.make_renderer()
        renderer._bezel_palette = list(bezel_palette.PALETTES["cyan_reactor"])
        renderer._bezel_base_palette = bezel_palette.PALETTES["cyan_reactor"]
        renderer._bezel_alarm_active = False
        transparent = renderer._bezel_palette[0]

        self.assertTrue(renderer._set_bezel_alarm(("E-STOP", "LATCHED")))
        self.assertEqual(renderer._bezel_palette[0], transparent)
        self.assertEqual(renderer._bezel_palette[7],
                         bezel_palette.PALETTES["red_alarm"][7])
        self.assertFalse(renderer._set_bezel_alarm(("E-STOP", "LATCHED")))

        self.assertTrue(renderer._set_bezel_alarm(None))
        self.assertEqual(renderer._bezel_palette,
                         list(bezel_palette.PALETTES["cyan_reactor"]))

    def test_page_theme_tints_bezel_and_alarm_restores_current_page(self):
        _, _, _, renderer = self.make_renderer()
        renderer._bezel_palette = list(bezel_palette.PALETTES["cyan_reactor"])
        renderer._bezel_base_palette = bezel_palette.PALETTES["cyan_reactor"]
        renderer._bezel_alarm_active = False
        transparent = renderer._bezel_palette[0]

        renderer._apply_page_theme("EXPLORER")
        amber = bezel_palette.PALETTES["amber_precision"]
        self.assertEqual(renderer._bezel_base_palette, amber)
        self.assertEqual(renderer._bezel_palette[7], amber[7])
        self.assertEqual(renderer._bezel_palette[0], transparent)

        renderer._set_bezel_alarm(("ALARM", "9"))
        self.assertEqual(renderer._bezel_palette[7],
                         bezel_palette.PALETTES["red_alarm"][7])

        renderer._apply_page_theme("CONFIGURATION")
        self.assertEqual(renderer._bezel_palette[7],
                         bezel_palette.PALETTES["red_alarm"][7])
        renderer._set_bezel_alarm(None)
        self.assertEqual(renderer._bezel_palette,
                         list(bezel_palette.PALETTES["ice_optical"]))

    def test_encoder_feedback_tracks_detent_direction_and_fades(self):
        state, _, _, renderer = self.make_renderer()
        marker, trail, far_trail = Node(), Node(), Node()
        marker.hidden = trail.hidden = far_trail.hidden = True
        palettes = ([0, 0, 0, 0], [0, 0], [0, 0])
        renderer.encoder_marker = marker
        renderer.encoder_trail = trail
        renderer.encoder_far_trail = far_trail
        renderer.encoder_palettes = palettes
        state.mpg_activity = 1
        state.mpg_activity_timestamp = 1.0

        self.assertTrue(renderer.animate(1.0))
        self.assertFalse(marker.hidden)
        self.assertFalse(trail.hidden)
        self.assertFalse(far_trail.hidden)
        clockwise_angle = renderer._encoder_angle
        self.assertGreater(marker.x, 120)
        self.assertTrue(renderer.animate(1.12))
        self.assertNotEqual(palettes[0][1], 0)

        state.mpg_activity = -1
        state.mpg_activity_timestamp = 1.13
        self.assertTrue(renderer.animate(1.13))
        self.assertLess(renderer._encoder_angle, clockwise_angle)
        self.assertTrue(renderer.animate(1.38))
        self.assertTrue(marker.hidden)
        self.assertTrue(trail.hidden)
        self.assertTrue(far_trail.hidden)

    def test_encoder_afterimages_follow_the_actual_detent_delta(self):
        state, _, _, renderer = self.make_renderer()
        marker, trail, far_trail = Node(), Node(), Node()
        renderer.encoder_marker = marker
        renderer.encoder_trail = trail
        renderer.encoder_far_trail = far_trail
        state.mpg_activity = 3
        state.mpg_activity_timestamp = 1.0

        renderer.animate(1.0)

        self.assertEqual(renderer._encoder_angle, 337.5)
        self.assertAlmostEqual(marker.x, 120 + round(101 * math.cos(
            math.radians(-22.5))) - 4)
        self.assertAlmostEqual(trail.y, 120 + round(101 * math.sin(
            math.radians(335.5))) - 2)
        self.assertAlmostEqual(far_trail.y, 120 + round(101 * math.sin(
            math.radians(333.5))) - 2)
        self.assertGreater(trail.x, far_trail.x)

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

    def test_top_page_swipe_moves_retained_groups_together(self):
        state, ui, _, renderer = self.make_renderer()
        renderer.home_group = Node()
        renderer.menu_group = Node()
        renderer.menu_group.hidden = True
        renderer.render(state)
        ui.page_swipe_direction = 1
        state.active_page = "EXPLORER"
        ui.apply_selector_context()

        self.assertTrue(renderer.render(state))
        transition = renderer._page_transition
        start = transition["started"]
        self.assertEqual(transition["phase"], "slide")
        self.assertFalse(renderer.home_group.hidden)
        self.assertFalse(renderer.menu_group.hidden)
        self.assertEqual(renderer.home_group.x, 0)
        self.assertEqual(renderer.menu_group.x, 240)
        self.assertTrue(renderer.animate(start + 0.09))
        self.assertIn(renderer.home_group.x, (-37, -38))
        self.assertIn(renderer.menu_group.x, (202, 203))
        self.assertEqual(renderer.menu_group.x - renderer.home_group.x, 240)
        self.assertTrue(renderer.render(state))
        self.assertTrue(renderer.animate(start + 0.18))
        self.assertEqual(renderer.home_group.x, -120)
        self.assertEqual(renderer.menu_group.x, 120)
        self.assertTrue(renderer.render(state))
        self.assertEqual(renderer.menu_title.value, "FILE EXPLORER")
        self.assertTrue(renderer.animate(start + 0.37))
        self.assertEqual(renderer.menu_group.x, 0)
        self.assertEqual(renderer.home_group.x, 0)
        self.assertTrue(renderer.home_group.hidden)
        self.assertFalse(renderer.menu_group.hidden)
        renderer.render(state)
        self.assertIsNone(renderer._page_transition)

    def test_same_group_menu_page_swipe_keeps_safe_single_group_transition(self):
        state, ui, _, renderer = self.make_renderer()
        renderer.home_group = Node()
        renderer.menu_group = Node()
        renderer.menu_group.hidden = True
        state.active_page = "EXPLORER"
        ui.apply_selector_context()
        renderer.render(state)
        self.assertFalse(renderer.menu_group.hidden)
        ui.page_swipe_direction = 1
        state.active_page = "CONFIGURATION"
        ui.apply_selector_context()

        self.assertTrue(renderer.render(state))
        self.assertEqual(renderer._page_transition["phase"], "out")
        self.assertFalse(renderer.menu_group.hidden)
        self.assertEqual(renderer.menu_title.value, "FILE EXPLORER")
        start = renderer._page_transition["started"]
        self.assertTrue(renderer.animate(start + 0.09))
        self.assertEqual(renderer.menu_group.x, -60)
        self.assertEqual(renderer.menu_title.value, "FILE EXPLORER")
        renderer.render(state)

        self.assertTrue(renderer.animate(start + 0.181))
        self.assertEqual(renderer.menu_group.x, 240)
        renderer.render(state)
        self.assertEqual(renderer._page_transition["phase"], "in")
        self.assertEqual(renderer.menu_title.value, "CONFIGURATION")
        incoming = renderer._page_transition["started"]
        self.assertTrue(renderer.animate(incoming + 0.09))
        self.assertEqual(renderer.menu_group.x, 60)
        renderer.render(state)
        self.assertTrue(renderer.animate(incoming + 0.181))
        self.assertEqual(renderer.menu_group.x, 0)
        renderer.render(state)
        self.assertIsNone(renderer._page_transition)

    def test_alarm_interrupts_page_swipe_transition(self):
        state, ui, _, renderer = self.make_renderer()
        renderer.home_group = Node()
        renderer.menu_group = Node()
        renderer.menu_group.hidden = True
        renderer.render(state)
        ui.page_swipe_direction = 1
        state.active_page = "EXPLORER"
        ui.apply_selector_context()
        renderer.render(state)
        state.estop_latched = True

        renderer.render(state)

        self.assertIsNone(renderer._page_transition)
        self.assertEqual(renderer.home_group.x, 0)
        self.assertEqual(renderer.menu_group.x, 0)
        self.assertFalse(renderer.overlay.group.hidden)

    def test_maps_home_state_and_updates_only_changed_component(self):
        state, _, display, renderer = self.make_renderer()
        self.assertTrue(renderer.render(state))
        self.assertEqual(renderer.axis.axis.value, "X")
        self.assertEqual(renderer.axis.value.value, "+124.520")
        self.assertEqual(renderer.state_label.value, "IDLE")
        self.assertEqual(renderer.motion.text.value, "HOLD TO JOG")
        colors = theme.select("industrial")
        self.assertEqual(renderer.state_label.line.color, colors["success"])
        self.assertEqual(renderer.motion.text.line.color, colors["warning"])
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

    def test_home_separates_disconnect_status_from_motion_safety_state(self):
        state, _, _, renderer = self.make_renderer()
        state.connection_state = "disconnected"
        state.machine_state = "disconnected"
        renderer.render(state)
        self.assertEqual(renderer.state_label.value, "DISCONNECTED")
        self.assertEqual(renderer.state_label.line.color,
                         theme.select("industrial")["muted"])
        self.assertEqual(renderer.motion.text.value, "MOTION DISARMED")
        self.assertEqual(renderer.motion.text.line.color,
                         theme.select("industrial")["warning"])

        state.transport = "c3-espnow"
        state.link_state = "PAIRED_NO_GRBL"
        renderer.render(state)
        self.assertEqual(renderer.state_label.value, "ESP-NOW LINKED")
        self.assertEqual(renderer.motion.text.value, "GRBL OFFLINE")
        self.assertEqual(renderer.state_label.line.color,
                         theme.select("industrial")["success"])

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
        self.assertEqual(renderer.motion.text.value, "MOTION DISARMED")

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
        self.assertEqual(renderer._halo_duration, 0.10)
        self.assertFalse(renderer.touch_halo.hidden)
        self.assertEqual((renderer.touch_halo.x, renderer.touch_halo.y),
                         (120 - TOUCH_BITMAP_CENTER,
                          120 - TOUCH_BITMAP_CENTER))
        self.assertFalse(renderer.animate(1.1))
        self.assertTrue(renderer.render(state))
        self.assertEqual(display.refreshes, initial + 1)
        self.assertFalse(renderer.render(state))
        self.assertTrue(renderer.animate(1.2))
        self.assertTrue(renderer.touch_halo.hidden)
        self.assertTrue(renderer.render(state))

    def test_touch_glow_animates_reused_palette_without_new_bitmap(self):
        _, _, _, renderer = self.make_renderer()

        class Palette(list):
            pass

        palette = Palette([0, 0, 0, 0, 0])
        renderer._halo_palette = palette
        renderer.touch_halo = Node()
        renderer.touch_halo.hidden = True
        renderer.touch_feedback((120, 120), 1.2)
        initial = tuple(palette)
        self.assertEqual(palette[1], 0)  # Broad ring waits for the outward wave.
        self.assertEqual(palette[2], 0)
        self.assertGreater(palette[3], 0)  # Inner ring is visible immediately.
        self.assertGreater(palette[4], palette[3])  # Bright contact core.
        self.assertTrue(renderer.animate(1.1))
        self.assertNotEqual(tuple(palette), initial)
        self.assertTrue(renderer._update_halo_palette(0.82))
        self.assertGreater(palette[1], palette[2])  # Light travels outward.

    def test_touch_hold_keeps_compact_contact_glow_without_restarting_wave(self):
        _, _, _, renderer = self.make_renderer()
        palette = [0, 0, 0, 0, 0]
        renderer._halo_palette = palette
        renderer.touch_halo = Node()
        renderer.touch_halo.hidden = True
        renderer._last_animation_now = 1.0
        renderer.touch_feedback((120, 120), 1.50)
        started = renderer._halo_started

        renderer.touch_hold(1.10)
        self.assertTrue(renderer._halo_held)
        self.assertEqual(renderer._halo_started, started)
        self.assertEqual(renderer._halo_progress, TOUCH_HOLD_PROGRESS)
        self.assertTrue(renderer.animate(1.30) or
                        renderer._halo_progress == TOUCH_HOLD_PROGRESS)
        self.assertEqual(renderer._halo_progress, TOUCH_HOLD_PROGRESS)
        self.assertGreater(palette[2], 0)
        self.assertEqual(palette[4], 0)
        self.assertEqual(palette[1], 0)
        held_ring = palette[2]

        renderer.touch_release(1.30)
        self.assertFalse(renderer._halo_held)
        self.assertTrue(renderer._halo_releasing)
        self.assertEqual(renderer._halo_release_progress,
                         TOUCH_HOLD_PROGRESS)
        self.assertTrue(renderer.animate(1.31))
        self.assertEqual(palette[1], 0)  # Release fades the same inner halo.
        self.assertLess(palette[2], held_ring)
        self.assertGreater(palette[2], 0)
        self.assertTrue(renderer.animate(1.35))
        self.assertLess(palette[2], held_ring)
        renderer.animate(1.39)
        self.assertTrue(renderer.touch_halo.hidden)
        self.assertFalse(renderer._halo_releasing)
        self.assertTrue(renderer.touch_halo.hidden)

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
        palettes = ([0, 0, 0, 0], [0, 0], [0, 0])
        renderer.encoder_palettes = palettes
        renderer.palettes = {"dial": [0] * 6, "focus": [0] * 3,
                             "separator": [0], "hud_markers": (),
                             "hud_trails": ()}
        renderer.active_theme = None
        renderer._last_render_signature = None
        renderer.render(state)
        self.assertEqual(renderer.active_theme, "industrial")
        self.assertEqual(palettes[0][1], theme.select("industrial")["accent"])
        ui.enter("MAIN_MENU")
        renderer.render(state)
        self.assertEqual(renderer.active_theme, "industrial")
        state.active_page = "EXPLORER"
        ui.apply_selector_context()
        renderer.render(state)
        self.assertEqual(renderer.active_theme, "amber")
        self.assertEqual(palettes[0][1], theme.select("amber")["accent"])
        self.assertEqual(palettes[1][1], theme.shade_color(
            theme.select("amber")["accent"], 36))
        renderer._encoder_started = 1.0
        renderer._encoder_phase = -1
        pulse_time = 1.12
        renderer.animate(pulse_time)
        pulse_strength = int(100 * (1 - (pulse_time - 1.0) / 0.24))
        amber_pulse = theme.shade_color(
            theme.select("amber")["accent"], pulse_strength)
        self.assertEqual(palettes[0][1], amber_pulse)
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
        self.assertEqual(palettes[0][1], theme.select("spectrum")["accent"])

    def test_page_theme_recolors_retained_rotor_tiles(self):
        _, _, _, renderer = self.make_renderer()
        renderer.palettes = {"dial": [0] * 6, "focus": [0] * 3,
                             "separator": [0], "hud_markers": (),
                             "hud_trails": ()}
        renderer.bezel_segments = [Node() for _ in range(24)]
        renderer.bezel_segment_palettes = [[0] + [0] * 15
                                           for _ in renderer.bezel_segments]
        renderer._rotor_brightness_levels = [-1] * 24
        renderer._rotor_target_levels = [0] * 24
        renderer.active_theme = None

        renderer._apply_page_theme("EXPLORER")

        self.assertEqual(renderer._rotor_color,
                         theme.select("amber")["accent"])
        self.assertEqual(renderer._rotor_brightness_levels,
                         renderer._rotor_target_levels)
        expected_level = renderer._rotor_target_levels[0]
        self.assertEqual(renderer.bezel_segment_palettes[0][15],
                         theme.shade_color(theme.select("amber")["accent"],
                                           expected_level * 100 // 15))

if __name__ == "__main__":
    unittest.main()
