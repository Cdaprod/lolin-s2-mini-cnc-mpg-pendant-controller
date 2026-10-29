"""Map the authoritative UIManager view model onto a round CNC instrument."""

import math
import time

from ..navigation import menu_window_start
from . import bezel_palette, theme

from .components import (AxisReadout, ConnectivityGlyphs, IncrementBadge,
                         InstrumentRing, MenuHighlight, MotionPrompt, Overlay,
                         SelectorFeedback, TextComponent)
from .rotor import BezelRotor

# At 24 updates/s, keep tangential motion below one pixel per update at the
# retained marker radii. Integer DisplayIO coordinates then produce a regular
# one-pixel cadence instead of the visible multi-pixel jumps from faster rates.
HUD_ORBIT_RATES = (0.22, -0.20)
NONHOME_MODEL_INTERVAL_MS = 33
PAGE_SWIPE_DURATION = 0.48
_PROFILE_TICKS_MASK = (1 << 29) - 1
_PROFILE_TICKS_HALF = 1 << 28


def _profile_ticks_diff(newer, older):
    diff = (newer - older) & _PROFILE_TICKS_MASK
    return ((diff + _PROFILE_TICKS_HALF) & _PROFILE_TICKS_MASK) - \
        _PROFILE_TICKS_HALF


def _detail_status_color(label, value, colors):
    """Use restrained semantic colors for safety and hardware diagnostics."""
    key = str(label).strip().lower()
    state = str(value).strip().upper()
    if key == "remote stop":
        if state == "CLEAR":
            return colors["success"]
        if state == "ACTIVE":
            return colors["danger"]
        if state in ("UNKNOWN", "UNAVAILABLE", "RECOVERY_REQUIRED"):
            return colors["warning"]
    elif key == "hold-to-run":
        if state == "ACTIVE":
            return colors["accent"]
        if state in ("INACTIVE", "UNKNOWN", "UNAVAILABLE", "UNCONFIGURED"):
            return colors["warning"]
    elif key in ("input sample", "selector sample"):
        if state == "VALID":
            return colors["success"]
        if state in ("INVALID", "UNAVAILABLE"):
            return colors["danger"]
        if state in ("UNKNOWN", "UNCONFIGURED"):
            return colors["warning"]
    elif key in ("input error", "selector error"):
        if state in ("NONE", ""):
            return colors["success"]
        return colors["danger"]
    elif key == "mcp23017" and state in ("NOT DETECTED", "UNAVAILABLE"):
        return colors["warning"]
    return None


class RoundRenderer:
    """Mutate a small persistent scene; never issue controller operations."""

    def __init__(self, display, scene_factory, animations=True,
                 bezel_rotation_enabled=True, bezel_ambient_period_s=54.0,
                 bezel_encoder_gain=0.04, bezel_max_speed_rad_s=0.35,
                 bezel_inertia_s=0.9,
                 bezel_direction_change_min_s=20.0,
                 bezel_direction_change_max_s=40.0,
                 bezel_frame_rate=24):
        self.display = display
        self.ui = None
        self.render_count = 0
        self.skipped_count = 0
        self.animations = bool(animations)
        self.bezel_rotation_enabled = bool(bezel_rotation_enabled)
        self.bezel_rotor = BezelRotor(
            bezel_ambient_period_s, bezel_encoder_gain,
            bezel_max_speed_rad_s, bezel_inertia_s,
            bezel_direction_change_min_s, bezel_direction_change_max_s,
            bezel_frame_rate)
        try:
            import supervisor
            self._profile_ticks_ms = supervisor.ticks_ms
        except (ImportError, AttributeError):
            self._profile_ticks_ms = lambda: int(time.monotonic() * 1000)
        self.last_model_ms = 0
        self.last_update_ms = 0
        self.last_refresh_ms = 0
        self._last_render_signature = None
        self._last_home_signature = None
        self._halo_until = 0
        self._halo_started = 0
        self._halo_visible = False
        self._halo_dirty = False
        self._halo_palette = None
        self._halo_progress = 1.0
        self._halo_phase = -1
        self._halo_accent = theme.TEXT
        self._last_animation_now = None
        self._highlight_dirty = False
        self._highlight_phase = -1
        self._nav_until = 0.0
        self._nav_visible = False
        self._nav_dirty = False
        self._nav_signature = None
        self._displayed_page = None
        self._displayed_screen = None
        self._page_transition = None
        self._page_transition_dirty = False
        self._encoder_dirty = False
        scene = scene_factory(display)
        self.root = scene["root"]
        self.touch_halo = scene.get("touch_halo")
        self.nav_group = scene.get("nav_group")
        self.nav_dots = scene.get("nav_dots", ())
        self.hud_markers = scene.get("hud_markers", ())
        self.hud_trails = scene.get("hud_trails", ())
        self.hud_frame_count = scene.get("hud_frame_count", 0)
        self._hud_tile_indexes = [-1] * len(self.hud_markers)
        self.bezel_segments = scene.get("rotor_segments", ())
        self.rotor_frame_count = scene.get("rotor_frame_count", 0)
        self._rotor_tile_indexes = [-1] * len(self.bezel_segments)
        self._hud_phase = -1
        self._hud_dirty = False
        self._last_nonhome_model_ticks = None
        self._last_nonhome_safety_signature = None
        self.palettes = scene.get("palettes", {})
        self._bezel_palette = self.palettes.get("bezel")
        self._bezel_base_palette = bezel_palette.PALETTES.get(
            scene.get("bezel_name") or bezel_palette.DEFAULT_BEZEL)
        self._bezel_alarm_active = False
        self._halo_palette = self.palettes.get("halo")
        self.themed_text = scene.get("themed_text", ())
        self.active_theme = None
        self.home_group = scene.get("home_group")
        self.menu_group = scene.get("menu_group")
        self.encoder_marker = scene.get("encoder_marker")
        self.encoder_trail = scene.get("encoder_trail")
        self.encoder_palettes = scene.get("encoder_palettes", ())
        self._encoder_angle = -90.0
        self._encoder_seen_timestamp = None
        self._encoder_started = 0.0
        self._encoder_direction = 0
        self._encoder_phase = -1
        self.ring = InstrumentRing(scene["ring"])
        self.state_label = TextComponent(scene["state_label"])
        self.axis_feedback = SelectorFeedback(scene["axis_feedback"], "AXIS")
        self.step_feedback = SelectorFeedback(scene["step_feedback"], "STEP")
        self.axis = AxisReadout(scene["axis"], scene["value"], scene["context"])
        self.increment = IncrementBadge(scene["increment"])
        self.motion = MotionPrompt(scene["motion"])
        self.connectivity = ConnectivityGlyphs(scene["connectivity"])
        self.menu_title = TextComponent(scene["menu_title"])
        self.menu = [TextComponent(line) for line in scene["menu"]]
        self.menu_separators = scene.get("menu_separators", ())
        self.menu_colors = scene.get("menu_colors", (None, None))
        self.menu_highlight = MenuHighlight(scene["menu_highlight"])
        self.menu_footer = TextComponent(scene["menu_footer"])
        self.overlay = Overlay(scene["overlay_group"], scene["overlay_title"],
                               scene["overlay_detail"])
        self.display.root_group = self.root

    def _refresh_if_manual(self):
        """Avoid synchronous transfers when DisplayIO already auto-refreshes."""
        if getattr(self.display, "auto_refresh", None) is True:
            return
        self.display.refresh(minimum_frames_per_second=0)

    def _apply_page_theme(self, active_page):
        """Recolor retained DisplayIO objects without rebuilding the screen."""
        name = theme.PAGE_THEMES.get(str(active_page or "HOME").upper(),
                                     "industrial")
        if name == self.active_theme:
            return False
        colors = theme.select(name)
        self.active_theme = name
        if self.palettes:
            dial = self.palettes["dial"]
            dial[0] = colors["background"]
            for index in (1, 2, 3, 4, 5):
                dial[index] = colors["panel"]
            focus = self.palettes["focus"]
            focus[0] = colors["panel"]
            focus[1] = colors.get("focus_border", colors["muted"])
            focus[2] = colors["accent"]
            self.palettes["separator"][0] = colors["separator"]
            self._halo_accent = colors["accent"]
            self._update_halo_palette(self._halo_progress)
            for index, palette in enumerate(self.palettes.get("hud_markers", ())):
                color = colors["accent"] if index == 0 else colors["highlight"]
                for shade in range(1, 16):
                    palette[shade] = theme.shade_color(
                        color, shade * 100 // 15)
            for index, palette in enumerate(self.palettes.get("hud_trails", ())):
                color = colors["accent"] if index == 0 else colors["highlight"]
                palette[1] = theme.shade_color(color, 22)
            if self.encoder_palettes:
                self.encoder_palettes[0][1] = colors["accent"]
                self.encoder_palettes[0][2] = theme.shade_color(colors["accent"], 64)
                self.encoder_palettes[0][3] = theme.shade_color(colors["accent"], 28)
                self.encoder_palettes[1][1] = theme.shade_color(colors["accent"], 36)
        if hasattr(self.ring.node, "colors"):
            self.ring.node.colors = colors
            self.ring.signature = None
        for line, token in self.themed_text:
            if hasattr(line, "set_color"):
                line.set_color(colors[token])
        self.menu_colors = (colors["text"], colors["muted"])
        return True

    def bind_ui(self, ui):
        self.ui = ui

    def _set_bezel_alarm(self, overlay):
        """Retint only the retained bezel palette for a critical alarm."""
        active = bool(overlay and overlay[0] in ("E-STOP", "ALARM"))
        if active == self._bezel_alarm_active or self._bezel_palette is None:
            return False
        colors = (bezel_palette.PALETTES["red_alarm"] if active else
                  self._bezel_base_palette)
        if colors is None:
            return False
        changed = False
        for index in range(1, min(16, len(colors))):
            if self._bezel_palette[index] != colors[index]:
                self._bezel_palette[index] = colors[index]
                changed = True
        self._bezel_alarm_active = active
        return changed

    def touch_feedback(self, point, until):
        """Show a preallocated, temporary touch target; never dispatch actions."""
        if not self.animations or self.touch_halo is None:
            return
        if point is None:
            return
        x, y = int(point[0]), int(point[1])
        if not (7 <= x <= 232 and 7 <= y <= 232):
            return
        self.touch_halo.x = x - 6
        self.touch_halo.y = y - 6
        self.touch_halo.hidden = False
        self._halo_visible = True
        self._halo_until = float(until)
        self._halo_started = (
            self._last_animation_now if self._last_animation_now is not None
            else max(0.0, self._halo_until - 0.20)
        )
        self._halo_progress = 0.0
        self._halo_phase = -1
        self._update_halo_palette(0.0)
        self._halo_dirty = True

    def _update_halo_palette(self, progress):
        if self._halo_palette is None:
            return False
        progress = max(0.0, min(1.0, float(progress)))
        core = int(100 * (1.0 - progress))
        inner = int(70 * max(0.0, 1.0 - abs(progress - 0.25) / 0.25))
        outer = int(48 * max(0.0, 1.0 - abs(progress - 0.60) / 0.40))
        shades = (outer, inner, core)
        changed = False
        for index, strength in enumerate(shades, start=1):
            color = theme.shade_color(self._halo_accent, strength)
            if self._halo_palette[index] != color:
                self._halo_palette[index] = color
                changed = True
        return changed

    def animate(self, now):
        """Expire transient indicators without blocking or allocating bitmaps."""
        now = float(now)
        self._last_animation_now = now
        changed = False
        transition = self._page_transition
        if transition is not None:
            half = PAGE_SWIPE_DURATION / 2
            elapsed = max(0.0, now - transition["started"])
            if transition["phase"] == "slide":
                progress = min(1.0, elapsed / PAGE_SWIPE_DURATION)
                eased = progress * progress * (3.0 - 2.0 * progress)
                offset = round(-transition["delta"] * 240 * eased)
                old_group = transition["old_group"]
                new_group = transition["new_group"]
                new_offset = transition["delta"] * 240 + offset
                if old_group.x != offset or new_group.x != new_offset:
                    old_group.x, new_group.x = offset, new_offset
                    self._page_transition_dirty = True
                    changed = True
                if progress >= 1.0:
                    old_group.x = 0
                    new_group.x = 0
                    old_group.hidden = True
                    new_group.hidden = False
                    self._page_transition = None
                    self._page_transition_dirty = True
                    changed = True
            elif transition["phase"] == "out":
                progress = min(1.0, elapsed / half)
                # Ease in to the handoff; the matching incoming curve begins
                # at the same velocity, so the page swap never visibly stalls.
                offset = round(-transition["delta"] * 240 * progress * progress)
                if transition["old_group"].x != offset:
                    transition["old_group"].x = offset
                    self._page_transition_dirty = True
                    changed = True
                if progress >= 1.0:
                    old_group, new_group = (transition["old_group"],
                                            transition["new_group"])
                    if old_group is not new_group:
                        old_group.hidden = True
                        new_group.hidden = False
                    new_group.x = transition["delta"] * 240
                    transition["phase"] = "commit"
                    self._page_transition_dirty = True
                    changed = True
            elif transition["phase"] == "in":
                progress = min(1.0, elapsed / half)
                offset = round(transition["delta"] * 240 *
                               (1.0-progress) * (1.0-progress))
                if transition["new_group"].x != offset:
                    transition["new_group"].x = offset
                    self._page_transition_dirty = True
                    changed = True
                if progress >= 1.0:
                    transition["new_group"].x = 0
                    self._page_transition = None
                    self._page_transition_dirty = True
                    changed = True
        if self.animations and self.ui is not None:
            state = self.ui.state
            timestamp = getattr(state, "mpg_activity_timestamp", None)
            if timestamp is not None and timestamp != self._encoder_seen_timestamp:
                self._encoder_seen_timestamp = timestamp
                direction = 1 if state.mpg_activity > 0 else (
                    -1 if state.mpg_activity < 0 else 0)
                if direction:
                    self._encoder_direction = direction
                    self._encoder_angle = (self._encoder_angle +
                                           direction * 22.5) % 360
                    angle = math.radians(self._encoder_angle)
                    x = 120 + round(101 * math.cos(angle))
                    y = 120 + round(101 * math.sin(angle))
                    if self.encoder_marker is not None:
                        self.encoder_marker.x = x - 4
                        self.encoder_marker.y = y - 4
                        self.encoder_marker.hidden = False
                    trail_angle = math.radians(
                        self._encoder_angle - direction * 12)
                    tx = 120 + round(97 * math.cos(trail_angle))
                    ty = 120 + round(97 * math.sin(trail_angle))
                    if self.encoder_trail is not None:
                        self.encoder_trail.x = tx - 2
                        self.encoder_trail.y = ty - 2
                        self.encoder_trail.hidden = False
                    self._encoder_started = now
                    self._encoder_phase = -1
                    self._encoder_dirty = True
                    changed = True
            if self._encoder_started:
                elapsed = max(0.0, now-self._encoder_started)
                if elapsed >= 0.24:
                    if self.encoder_marker is not None:
                        self.encoder_marker.hidden = True
                    if self.encoder_trail is not None:
                        self.encoder_trail.hidden = True
                    self._encoder_started = 0.0
                    self._encoder_dirty = True
                    changed = True
                else:
                    phase = int(elapsed*24)
                    if phase != self._encoder_phase:
                        self._encoder_phase = phase
                        strength = max(0, int(100*(1-elapsed/0.24)))
                        if self.encoder_palettes:
                            accent = theme.select(self.active_theme or "industrial")["accent"]
                            self.encoder_palettes[0][1] = theme.shade_color(accent,strength)
                            self.encoder_palettes[0][2] = theme.shade_color(accent,strength*64//100)
                            self.encoder_palettes[0][3] = theme.shade_color(accent,strength*28//100)
                            self.encoder_palettes[1][1] = theme.shade_color(accent,strength*36//100)
                        self._encoder_dirty = True
                        changed = True
        if self.touch_halo is not None and self._halo_visible:
            if now >= self._halo_until:
                self.touch_halo.hidden = True
                self._halo_visible = False
                self._halo_dirty = True
                changed = True
                self._halo_progress = 1.0
                self._update_halo_palette(1.0)
            else:
                frame = int(now * 24)
                if frame != self._halo_phase:
                    self._halo_phase = frame
                    duration = max(0.001, self._halo_until -
                                   self._halo_started)
                    progress = (now - self._halo_started) / duration
                    self._halo_progress = max(0.0, min(1.0, progress))
                    if self._update_halo_palette(self._halo_progress):
                        self._halo_dirty = True
                        changed = True
        highlight_frame = int(now * 24)
        if highlight_frame != self._highlight_phase:
            self._highlight_phase = highlight_frame
            if self.menu_highlight.animate():
                self._highlight_dirty = True
                changed = True
        if self.nav_group is not None and self._nav_visible:
            if float(now) >= self._nav_until:
                self.nav_group.hidden = True
                self._nav_visible = False
                self._nav_dirty = True
                changed = True
        if self.animations and self.hud_markers:
            overlay = self.ui.active_overlay() if self.ui else None
            unsafe = bool(overlay and overlay[0] in ("E-STOP", "ALARM"))
            if unsafe:
                for sprite, _, _ in self.hud_markers:
                    if not sprite.hidden:
                        sprite.hidden = True
                        self._hud_dirty = True
                        changed = True
                for sprite, _, _ in self.hud_trails:
                    if not sprite.hidden:
                        sprite.hidden = True
                        self._hud_dirty = True
                        changed = True
                for sprite in self.bezel_segments:
                    if not sprite.hidden:
                        sprite.hidden = True
                        self._hud_dirty = True
                        changed = True
            else:
                state = self.ui.state if self.ui is not None else None
                encoder_timestamp = getattr(
                    state, "mpg_activity_timestamp", None) if state else None
                encoder_delta = getattr(state, "mpg_activity", 0) if state else 0
                rotor_angle, _ = self.bezel_rotor.update(
                    now, encoder_timestamp, encoder_delta)
                if self.bezel_rotation_enabled and self.bezel_rotor.frame_due(now):
                    self._hud_phase = int(float(now) * self.bezel_rotor.frame_rate)
                    for index, (sprite, radius, _) in enumerate(self.hud_markers):
                        if index == 0:
                            angle = rotor_angle
                        else:
                            angle = float(now) * HUD_ORBIT_RATES[index]
                        if self.hud_frame_count == 16:
                            center_x = 120 + radius * math.cos(angle)
                            center_y = 120 + radius * math.sin(angle)
                            base_x = math.floor(center_x)
                            base_y = math.floor(center_y)
                            phase_x = int((center_x-base_x) * 4)
                            phase_y = int((center_y-base_y) * 4)
                            tile_index = phase_y * 4 + phase_x
                            x, y = int(base_x) - 4, int(base_y) - 4
                            if self._hud_tile_indexes[index] != tile_index:
                                sprite[0] = tile_index
                                self._hud_tile_indexes[index] = tile_index
                                self._hud_dirty = True
                                changed = True
                        else:
                            x = 116 + round(radius * math.cos(angle))
                            y = 116 + round(radius * math.sin(angle))
                        if sprite.x != x or sprite.y != y or sprite.hidden:
                            sprite.x, sprite.y = x, y
                            sprite.hidden = False
                            self._hud_dirty = True
                            changed = True
                        if index < len(self.hud_trails):
                            trail, trail_radius, _ = self.hud_trails[index]
                            trail_rate = (self.bezel_rotor.velocity if index == 0
                                          else HUD_ORBIT_RATES[index])
                            trail_angle = angle - trail_rate * 0.20
                            trail_x = 118 + round(trail_radius * math.cos(trail_angle))
                            trail_y = 118 + round(trail_radius * math.sin(trail_angle))
                            if (trail.x != trail_x or trail.y != trail_y or
                                    trail.hidden):
                                trail.x, trail.y = trail_x, trail_y
                                trail.hidden = False
                                self._hud_dirty = True
                                changed = True
                    if self.rotor_frame_count == 256:
                        for index, sprite in enumerate(self.bezel_segments):
                            angle = rotor_angle + index * (2.0 * math.pi / 3.0)
                            center_x = 120 + 113.0 * math.cos(angle)
                            center_y = 120 + 113.0 * math.sin(angle)
                            base_x, base_y = math.floor(center_x), math.floor(center_y)
                            phase_x = int((center_x - base_x) * 4)
                            phase_y = int((center_y - base_y) * 4)
                            tangent = (angle + math.pi / 2.0) % (2.0 * math.pi)
                            orientation = int(round(
                                tangent * 16.0 / (2.0 * math.pi))) % 16
                            tile_index = (orientation * 16 + phase_y * 4 +
                                          phase_x)
                            if self._rotor_tile_indexes[index] != tile_index:
                                sprite[0] = tile_index
                                self._rotor_tile_indexes[index] = tile_index
                                self._hud_dirty = True
                                changed = True
                            x, y = int(base_x) - 4, int(base_y) - 4
                            if sprite.x != x or sprite.y != y or sprite.hidden:
                                sprite.x, sprite.y = x, y
                                sprite.hidden = False
                                self._hud_dirty = True
                                changed = True
                elif not self.bezel_rotation_enabled:
                    for sprite, _, _ in self.hud_markers[:1]:
                        if not sprite.hidden:
                            sprite.hidden = True
                            self._hud_dirty = True
                            changed = True
                    for sprite, _, _ in self.hud_trails[:1]:
                        if not sprite.hidden:
                            sprite.hidden = True
                            self._hud_dirty = True
                            changed = True
                    for sprite in self.bezel_segments:
                        if not sprite.hidden:
                            sprite.hidden = True
                            self._hud_dirty = True
                            changed = True
        return changed

    def _home_signature(self, state):
        axis = state.selected_axis
        position = state.displayed_position().get(axis)
        return (
            state.machine_state, state.connection_state, state.transport,
            state.link_state, axis, state.coordinate_mode, position,
            state.selected_multiplier, state.deadman_enabled,
            getattr(state, "input_valid", None),
            getattr(state, "selectors_valid", True),
            state.estop_observed, state.estop_latched, state.alarm,
            state.mpg_activity, state.axis_transition_direction,
            state.resolution_transition_direction, state.active_page,
            state.wifi_state, state.storage_state, self.ui.active_overlay(),
        )

    def _navigation(self, model):
        """Momentarily expose the physical page's position along the top rim."""
        if self.nav_group is None or not self.nav_dots:
            return False
        signature = (model["screen"], model.get("page_index", 0),
                     model.get("page_count", 4))
        if signature == self._nav_signature:
            return False
        self._nav_signature = signature
        if model.get("overlay"):
            if self._nav_visible:
                self.nav_group.hidden = True
                self._nav_visible = False
                return True
            return False
        count = max(1, min(len(self.nav_dots), int(signature[2])))
        current = max(0, min(count - 1, int(signature[1])))
        for i, (node, palette) in enumerate(self.nav_dots):
            node.hidden = i >= count
            if i < count:
                # Monotone left to right, all centers on the top circle.
                x = 67 + (106 * i) // max(1, count - 1)
                y = 120 - int(math.sqrt(max(0, 108 * 108 - (x - 120) ** 2)))
                node.x, node.y = x - 3, y - 3
                palette[1] = 0xFFFFFF if i == current else 0x667176
        self.nav_group.hidden = False
        self._nav_visible = True
        self._nav_until = time.monotonic() + 1.6
        self._nav_dirty = True
        return True

    @staticmethod
    def _empty_state(model, storage_state):
        """Explain empty browse pages instead of presenting blank rows."""
        screen = model.get("screen")
        if screen in ("JOBS", "JOB_BROWSER", "EXPLORER"):
            items = model.get("items", ())
            if len(items) == 1 and not items[0][1]:
                label = str(items[0][0])
                labels = {
                    "SD DISABLED": ("SD CARD DISABLED", "ENABLE IN SETTINGS"),
                    "SD CARD MISSING": ("SD CARD NOT FOUND", "INSERT SD CARD"),
                    "SD MOUNT ERROR": ("SD CARD ERROR", "CHECK SYSTEM STATUS"),
                    "NO FILES FOUND": ("NO FILES FOUND", "SD CARD READY"),
                }
                if label in labels:
                    return labels[label]
            messages = {
                "available": ("NO FILES FOUND", "SD CARD READY"),
                "disabled": ("SD CARD DISABLED", "ENABLE IN SETTINGS"),
                "missing": ("SD CARD NOT FOUND", "INSERT SD CARD"),
                "mount_error": ("SD CARD ERROR", "CHECK SYSTEM STATUS"),
            }
            return messages.get(
                str(storage_state).lower(),
                ("FILES UNAVAILABLE", "CHECK SYSTEM STATUS"))
        if screen in ("MACROS", "MACRO_BROWSER"):
            return "NO MACROS FOUND", ""
        return "NO ITEMS AVAILABLE", ""

    def render(self, state):
        if self.ui is None:
            raise RuntimeError("RoundRenderer must be bound to UIManager")
        transition = self._page_transition
        if transition is not None and self.ui.active_overlay():
            # Safety messages bypass decorative transitions immediately.
            old_group, new_group = transition["old_group"], transition["new_group"]
            old_group.x = new_group.x = 0
            if old_group is not new_group:
                old_group.hidden = True
            self._page_transition = None
            self._page_transition_dirty = False
            transition = None
        if transition is not None and transition["phase"] == "out":
            self.ui.dirty = True
            self.render_count += 1
            self._refresh_if_manual()
            return True
        if (transition is not None and transition["phase"] == "in" and
                self._page_transition_dirty and not self.ui.dirty):
            self._page_transition_dirty = False
            self._refresh_if_manual()
            return True
        if (self.ui.current_screen == "HOME" and not self.ui.dirty and
                not (self._halo_dirty or self._nav_dirty or self._hud_dirty
                     or self._highlight_dirty or self._page_transition_dirty
                     or self._encoder_dirty)):
            home_signature = self._home_signature(state)
            if home_signature == self._last_home_signature:
                self.skipped_count += 1
                self.last_model_ms = 0
                self.last_update_ms = 0
                self.last_refresh_ms = 0
                return False
        elif (self.ui.current_screen == "HOME" and not self.ui.dirty):
            home_signature = self._home_signature(state)
            if home_signature == self._last_home_signature:
                # Only preallocated transient sprites changed. Refresh them
                # without rebuilding the unchanged view model/components.
                refresh_started = self._profile_ticks_ms()
                self.render_count += 1
                try:
                    self._refresh_if_manual()
                except (AttributeError, RuntimeError):
                    pass
                self._halo_dirty = False
                self._nav_dirty = False
                self._hud_dirty = False
                self._highlight_dirty = False
                self._page_transition_dirty = False
                self._encoder_dirty = False
                self.last_model_ms = 0
                self.last_update_ms = 0
                self.last_refresh_ms = max(
                    0, _profile_ticks_diff(
                        self._profile_ticks_ms(), refresh_started))
                return True
        if self.ui.current_screen != "HOME":
            now_ticks = self._profile_ticks_ms()
            last_ticks = self._last_nonhome_model_ticks
            safety_signature = (
                state.estop_observed, state.estop_latched, state.alarm,
                state.sd_job_state, self.ui.active_overlay())
            safety_changed = (
                safety_signature != self._last_nonhome_safety_signature)
            if (not self.ui.dirty and not safety_changed and
                    last_ticks is not None and
                    _profile_ticks_diff(now_ticks, last_ticks) <
                    NONHOME_MODEL_INTERVAL_MS):
                # Input, touch, and safety processing stay at the app's full
                # poll rate. Only menu/detail view-model work is capped;
                # event-driven UI dirtiness above this branch renders now.
                transient_dirty = (self._halo_dirty or self._nav_dirty or
                                   self._hud_dirty or self._highlight_dirty or
                                   self._page_transition_dirty or self._encoder_dirty)
                if transient_dirty:
                    refresh_started = self._profile_ticks_ms()
                    self.render_count += 1
                    try:
                        self._refresh_if_manual()
                    except (AttributeError, RuntimeError):
                        pass
                    self._halo_dirty = False
                    self._nav_dirty = False
                    self._hud_dirty = False
                    self._highlight_dirty = False
                    self._page_transition_dirty = False
                    self._encoder_dirty = False
                    self.last_model_ms = 0
                    self.last_update_ms = 0
                    self.last_refresh_ms = max(
                        0, _profile_ticks_diff(
                            self._profile_ticks_ms(), refresh_started))
                    return True
                self.skipped_count += 1
                self.last_model_ms = 0
                self.last_update_ms = 0
                self.last_refresh_ms = 0
                return False
            self._last_nonhome_model_ticks = now_ticks
            self._last_nonhome_safety_signature = safety_signature
        model_started = self._profile_ticks_ms()
        model = self.ui.view_model()
        self._set_bezel_alarm(model.get("overlay"))
        if self._page_transition is not None and \
                self._page_transition["phase"] == "commit":
            self._page_transition["phase"] = "in"
            self._page_transition["started"] = time.monotonic()
            self._page_transition_dirty = False
        else:
            direction = self.ui.consume_page_swipe_direction()
            page = model.get("active_page", "HOME")
            if (direction and self._displayed_page is not None and
                    page != self._displayed_page and not model.get("overlay") and
                    self.home_group is not None and self.menu_group is not None):
                old_group = (self.home_group if self._displayed_screen == "HOME"
                             else self.menu_group)
                new_group = (self.home_group if model["screen"] == "HOME"
                             else self.menu_group)
                old_group.x = 0
                new_group.x = 0
                old_group.hidden = False
                if old_group is not new_group:
                    new_group.hidden = False
                    new_group.x = int(direction) * 240
                self._page_transition = {
                    "phase": ("slide" if old_group is not new_group else "out"),
                    "delta": int(direction),
                    "started": time.monotonic(), "old_group": old_group,
                    "new_group": new_group,
                }
                self._page_transition_dirty = True
                if old_group is new_group:
                    self.ui.dirty = True
                    self.render_count += 1
                    self._refresh_if_manual()
                    return True
        update_started = self._profile_ticks_ms()
        self.last_model_ms = max(
            0, _profile_ticks_diff(update_started, model_started))
        coordinates = state.displayed_position()
        selected_axis = state.selected_axis
        signature = (
            model, state.machine_state, state.coordinate_mode, selected_axis,
            coordinates.get(selected_axis), state.wifi_state,
            state.storage_state,
        )
        if (signature == self._last_render_signature and
                not (self._halo_dirty or self._nav_dirty or self._hud_dirty
                     or self._highlight_dirty or self._page_transition_dirty
                     or self._encoder_dirty)):
            self.skipped_count += 1
            self.last_update_ms = max(
                0, _profile_ticks_diff(self._profile_ticks_ms(), update_started))
            self.last_refresh_ms = 0
            return False
        self._last_render_signature = signature
        self._last_home_signature = (
            self._home_signature(state)
            if model["screen"] == "HOME" else None)
        theme_changed = self._apply_page_theme(model.get("active_page", "HOME"))
        nav_changed = self._navigation(model)
        if model.get("overlay") and self._nav_visible:
            self.nav_group.hidden = True
            self._nav_visible = False
            nav_changed = True
        is_home = model["screen"] == "HOME"
        transition = self._page_transition
        if (transition is not None and transition["phase"] == "slide" and
                transition["old_group"] is not transition["new_group"]):
            transition["old_group"].hidden = False
            transition["new_group"].hidden = False
        else:
            if self.home_group is not None:
                self.home_group.hidden = not is_home
            if self.menu_group is not None:
                self.menu_group.hidden = is_home
        self._displayed_page = model.get("active_page", "HOME")
        self._displayed_screen = model["screen"]

        changed = self.ring.update(
            state.machine_state,
            model["mpg_activity"] if model["jog_armed"] else 0,
            model["jog_armed"],
            model["axis_transition_direction"],
            model["resolution_transition_direction"],
        )
        changed = self.axis_feedback.update(
            model["axis_selector"], model["axis_transition_direction"]
        ) or changed
        changed = self.step_feedback.update(
            model["resolution_selector"],
            model["resolution_transition_direction"],
        ) or changed
        link = getattr(state, "link_state", "DISCONNECTED")
        wireless = getattr(state, "transport", "") == "c3-espnow"
        state_text = ({"GRBL_FRESH": "ESP-NOW LINKED",
                       "PAIRED_NO_GRBL": "ESP-NOW LINKED",
                       "PAIRING": "ESP-NOW PAIRING",
                       "LINK_LOST": "ESP-NOW LOST"}.get(link, "ESP-NOW WAITING")
                      if wireless else
                      ("READY" if model["jog_armed"] else state.machine_state.upper()))
        colors = theme.select(self.active_theme)
        if (state.estop_observed or state.estop_latched or
                state.machine_state in ("alarm", "estop")):
            state_color = colors["danger"]
        elif wireless:
            state_color = {
                "GRBL_FRESH": colors["success"],
                "PAIRED_NO_GRBL": colors["success"],
                "PAIRING": colors["warning"],
                "LINK_LOST": colors["danger"],
            }.get(link, colors["muted"])
        elif state.connection_state != "connected":
            state_color = colors["muted"]
        elif state.machine_state == "hold":
            state_color = colors["warning"]
        elif state.machine_state in ("run", "jog"):
            state_color = colors["accent"]
        else:
            state_color = colors["success"]
        changed = self.state_label.set(state_text) or changed
        changed = self.state_label.set_color(state_color) or changed
        changed = self.axis.update(
            selected_axis, coordinates.get(selected_axis), state.coordinate_mode,
            "mm",
        ) or changed
        changed = self.increment.update(model["resolution_selector"]) or changed
        controller = state.connection_state == "connected"
        changed = self.motion.update(
            model["jog_hold"], model["jog_armed"], model["mpg_activity"],
            controller, link if wireless else None, colors,
        ) or changed
        wifi = getattr(state, "wifi_state", "DISABLED") in (
            "CONNECTED", "connected"
        )
        changed = self.connectivity.update(
            wifi, state.storage_state == "available"
        ) or changed

        # The menu layer is hidden on the operational HOME instrument. Avoid
        # rebuilding menu strings and updating six retained rows on every
        # input poll; the first menu transition updates the complete layer.
        if not is_home:
            items = model.get("items", ())
            if model.get("details"):
                items = tuple(("{}: {}".format(key, value), True, "")
                              for key, value in model["details"])
            # Dynamic browser screens provide a disabled explanatory item
            # when empty. Render that state in the middle of the list area,
            # rather than as a selectable row at the top of the page.
            empty_browser = (
                model.get("screen") in ("JOBS", "JOB_BROWSER", "EXPLORER")
                and len(items) == 1 and not items[0][1]
            )
            if empty_browser:
                items = ()
            selected = min(model.get("selected", 0), max(0, len(items) - 1))
            window_start = menu_window_start(
                selected, len(items), len(self.menu))
            visible_items = items[window_start:window_start + len(self.menu)]
            changed = self.menu_title.set(model["title"]) or changed
            separator_count = max(0, min(len(self.menu_separators),
                                         len(visible_items) - 1))
            for index, separator in enumerate(self.menu_separators):
                hidden = index >= separator_count
                if separator.hidden != hidden:
                    separator.hidden = hidden
                    changed = True
            empty_state = (self._empty_state(model, state.storage_state)
                           if not visible_items else ("", ""))
            for index, component in enumerate(self.menu):
                text = ""
                if index < len(visible_items):
                    text = visible_items[index][0]
                    if not visible_items[index][1]:
                        text += "  -"
                elif not visible_items and index == len(self.menu) // 2:
                    text = empty_state[0]
                elif not visible_items and index == len(self.menu) // 2 + 1:
                    text = empty_state[1]
                changed = component.set(text) or changed
                row_color = self.menu_colors[0]
                if index < len(visible_items) and not visible_items[index][1]:
                    row_color = self.menu_colors[1]
                elif empty_browser:
                    row_color = (self.menu_colors[0]
                                 if index == len(self.menu) // 2 else
                                 self.menu_colors[1])
                elif not visible_items:
                    row_color = self.menu_colors[1]
                if model.get("details") and index < len(visible_items):
                    detail_index = window_start + index
                    if detail_index < len(model["details"]):
                        label, value = model["details"][detail_index]
                        semantic_color = _detail_status_color(
                            label, value, colors)
                        if semantic_color is not None:
                            row_color = semantic_color
                changed = component.set_color(row_color) or changed
            changed = self.menu_highlight.set(
                selected - window_start, bool(visible_items),
                animate=self.animations,
            ) or changed
            page = "{}/{}".format(selected + 1, len(items)) if items else "-"
            changed = self.menu_footer.set(page + "  BACK | HOME") or changed
        changed = self.overlay.update(model.get("overlay")) or changed
        changed = (theme_changed or self._halo_dirty or self._nav_dirty
                   or self._hud_dirty or self._highlight_dirty
                   or self._page_transition_dirty or self._encoder_dirty
                   or nav_changed or changed)
        self._halo_dirty = False
        self._nav_dirty = False
        self._hud_dirty = False
        self._highlight_dirty = False
        self._page_transition_dirty = False
        self._encoder_dirty = False
        refresh_started = self._profile_ticks_ms()
        self.last_update_ms = max(
            0, _profile_ticks_diff(refresh_started, update_started))
        self.last_refresh_ms = 0
        if not changed:
            self.skipped_count += 1
            return False
        self.render_count += 1
        try:
            self._refresh_if_manual()
        except (AttributeError, RuntimeError):
            pass
        self.last_refresh_ms = max(
            0, _profile_ticks_diff(self._profile_ticks_ms(), refresh_started))
        return True
