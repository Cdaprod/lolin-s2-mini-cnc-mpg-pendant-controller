"""Map the authoritative UIManager view model onto a round CNC instrument."""

import math
import time

from ..navigation import menu_window_start
from . import theme

from .components import (AxisReadout, ConnectivityGlyphs, IncrementBadge,
                         InstrumentRing, MenuHighlight, MotionPrompt, Overlay,
                         SelectorFeedback, TextComponent)

# At 24 updates/s, keep tangential motion below one pixel per update at the
# retained marker radii. Integer DisplayIO coordinates then produce a regular
# one-pixel cadence instead of the visible multi-pixel jumps from faster rates.
HUD_ORBIT_RATES = (0.20, -0.16)


class RoundRenderer:
    """Mutate a small persistent scene; never issue controller operations."""

    def __init__(self, display, scene_factory, animations=True):
        self.display = display
        self.ui = None
        self.render_count = 0
        self.skipped_count = 0
        self.animations = bool(animations)
        self._halo_until = 0
        self._halo_visible = False
        self._halo_dirty = False
        self._nav_until = 0.0
        self._nav_visible = False
        self._nav_dirty = False
        self._nav_signature = None
        scene = scene_factory(display)
        self.root = scene["root"]
        self.touch_halo = scene.get("touch_halo")
        self.nav_group = scene.get("nav_group")
        self.nav_dots = scene.get("nav_dots", ())
        self.hud_markers = scene.get("hud_markers", ())
        self._hud_phase = -1
        self._hud_dirty = False
        self.palettes = scene.get("palettes", {})
        self.themed_text = scene.get("themed_text", ())
        self.active_theme = None
        self.home_group = scene.get("home_group")
        self.menu_group = scene.get("menu_group")
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
        self.menu_colors = scene.get("menu_colors", (None, None))
        self.menu_highlight = MenuHighlight(scene["menu_highlight"])
        self.menu_footer = TextComponent(scene["menu_footer"])
        self.overlay = Overlay(scene["overlay_group"], scene["overlay_title"],
                               scene["overlay_detail"])
        self.display.root_group = self.root


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
            self.palettes["halo"][1] = colors["accent"]
            for index, palette in enumerate(self.palettes.get("hud_markers", ())):
                color = colors["accent"] if index == 0 else colors["highlight"]
                palette[1] = color
                palette[2] = ((color & 0xFEFEFE) >> 1)
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
        self._halo_dirty = True

    def animate(self, now):
        """Expire transient indicators without blocking or allocating bitmaps."""
        changed = False
        if self.touch_halo is not None and self._halo_visible:
            if float(now) >= self._halo_until:
                self.touch_halo.hidden = True
                self._halo_visible = False
                self._halo_dirty = True
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
            else:
                # Time-based angular motion: quantize refresh cadence, not
                # position/angle. The old 8 Hz phase produced visible jumps.
                frame = int(float(now) * 24)
                if frame != self._hud_phase:
                    self._hud_phase = frame
                    for index, (sprite, radius, _) in enumerate(self.hud_markers):
                        angle = float(now) * HUD_ORBIT_RATES[index]
                        x = 117 + round(radius * math.cos(angle))
                        y = 117 + round(radius * math.sin(angle))
                        if sprite.x != x or sprite.y != y or sprite.hidden:
                            sprite.x, sprite.y = x, y
                            sprite.hidden = False
                            self._hud_dirty = True
                            changed = True
        return changed

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

    def render(self, state):
        if self.ui is None:
            raise RuntimeError("RoundRenderer must be bound to UIManager")
        model = self.ui.view_model()
        theme_changed = self._apply_page_theme(model.get("active_page", "HOME"))
        nav_changed = self._navigation(model)
        if model.get("overlay") and self._nav_visible:
            self.nav_group.hidden = True
            self._nav_visible = False
            nav_changed = True
        is_home = model["screen"] == "HOME"
        if self.home_group is not None:
            self.home_group.hidden = not is_home
        if self.menu_group is not None:
            self.menu_group.hidden = is_home

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
        changed = self.state_label.set(state_text) or changed
        coordinates = state.displayed_position()
        selected_axis = state.selected_axis
        changed = self.axis.update(
            selected_axis, coordinates.get(selected_axis), state.coordinate_mode,
            "mm",
        ) or changed
        changed = self.increment.update(state.selected_multiplier) or changed
        controller = state.connection_state == "connected"
        changed = self.motion.update(
            model["jog_hold"], model["jog_armed"], model["mpg_activity"],
            controller, link if wireless else None,
        ) or changed
        wifi = getattr(state, "wifi_state", "DISABLED") in (
            "CONNECTED", "connected"
        )
        changed = self.connectivity.update(
            wifi, state.storage_state == "available"
        ) or changed

        items = model.get("items", ())
        if model.get("details"):
            items = tuple(("{}: {}".format(key, value), True, "")
                          for key, value in model["details"])
        selected = min(model.get("selected", 0), max(0, len(items) - 1))
        window_start = menu_window_start(selected, len(items), len(self.menu))
        visible_items = items[window_start:window_start + len(self.menu)]
        changed = self.menu_title.set(model["title"]) or changed
        for index, component in enumerate(self.menu):
            text = ""
            if index < len(visible_items):
                text = visible_items[index][0]
                if not visible_items[index][1]:
                    text += "  -"
            changed = component.set(text) or changed
            row_color = self.menu_colors[0]
            if index < len(visible_items) and not visible_items[index][1]:
                row_color = self.menu_colors[1]
            changed = component.set_color(row_color) or changed
        changed = self.menu_highlight.set(
            selected - window_start, bool(visible_items)
        ) or changed
        page = "{}/{}".format(selected + 1, len(items)) if items else "-"
        changed = self.menu_footer.set(page + "  BACK | HOME") or changed
        changed = self.overlay.update(model.get("overlay")) or changed
        changed = (theme_changed or self._halo_dirty or self._nav_dirty
                   or self._hud_dirty or nav_changed or changed)
        self._halo_dirty = False
        self._nav_dirty = False
        self._hud_dirty = False
        if not changed:
            self.skipped_count += 1
            return False
        self.render_count += 1
        try:
            self.display.refresh(minimum_frames_per_second=0)
        except (AttributeError, RuntimeError):
            pass
        return True
