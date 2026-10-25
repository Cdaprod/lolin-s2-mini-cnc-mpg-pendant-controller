"""Map the authoritative UIManager view model onto a round CNC instrument."""

import math
import time

from ..navigation import menu_window_start

from .components import (AxisReadout, ConnectivityGlyphs, IncrementBadge,
                         InstrumentRing, MenuHighlight, MotionPrompt, Overlay,
                         SelectorFeedback, TextComponent)


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
        state_text = "READY" if model["jog_armed"] else state.machine_state.upper()
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
            controller,
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
        changed = self._halo_dirty or self._nav_dirty or nav_changed or changed
        self._halo_dirty = False
        self._nav_dirty = False
        if not changed:
            self.skipped_count += 1
            return False
        self.render_count += 1
        try:
            self.display.refresh(minimum_frames_per_second=0)
        except (AttributeError, RuntimeError):
            pass
        return True
