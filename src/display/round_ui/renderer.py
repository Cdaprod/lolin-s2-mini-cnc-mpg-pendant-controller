"""Map the authoritative UIManager view model onto a round CNC instrument."""

from .components import (AxisReadout, ConnectivityGlyphs, IncrementBadge,
                         InstrumentRing, MenuHighlight, MotionPrompt, Overlay,
                         TextComponent)


class RoundRenderer:
    """Mutate a small persistent scene; never issue controller operations."""

    def __init__(self, display, scene_factory):
        self.display = display
        self.ui = None
        self.render_count = 0
        self.skipped_count = 0
        scene = scene_factory(display)
        self.root = scene["root"]
        self.home_group = scene.get("home_group")
        self.menu_group = scene.get("menu_group")
        self.ring = InstrumentRing(scene["ring"])
        self.state_label = TextComponent(scene["state_label"])
        self.axis = AxisReadout(scene["axis"], scene["value"], scene["context"])
        self.increment = IncrementBadge(scene["increment"])
        self.motion = MotionPrompt(scene["motion"])
        self.connectivity = ConnectivityGlyphs(scene["connectivity"])
        self.menu_title = TextComponent(scene["menu_title"])
        self.menu = [TextComponent(line) for line in scene["menu"]]
        self.menu_highlight = MenuHighlight(scene["menu_highlight"])
        self.menu_footer = TextComponent(scene["menu_footer"])
        self.overlay = Overlay(scene["overlay_group"], scene["overlay_title"],
                               scene["overlay_detail"])
        self.display.root_group = self.root

    def bind_ui(self, ui):
        self.ui = ui

    def render(self, state):
        if self.ui is None:
            raise RuntimeError("RoundRenderer must be bound to UIManager")
        model = self.ui.view_model()
        is_home = model["screen"] == "HOME"
        if self.home_group is not None:
            self.home_group.hidden = not is_home
        if self.menu_group is not None:
            self.menu_group.hidden = is_home

        changed = self.ring.update(
            state.machine_state,
            model["mpg_activity"] if model["jog_armed"] else 0,
            model["jog_armed"],
        )
        state_text = "READY" if model["jog_armed"] else state.machine_state.upper()
        changed = self.state_label.set(state_text) or changed
        coordinates = state.displayed_position()
        selected_axis = state.selected_axis
        changed = self.axis.update(
            selected_axis, coordinates.get(selected_axis), state.coordinate_mode,
            "mm", model["axis_transition_direction"],
        ) or changed
        changed = self.increment.update(
            state.selected_multiplier,
            model["resolution_transition_direction"],
        ) or changed
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
        window_start = max(0, min(selected - len(self.menu) + 1,
                                  len(items) - len(self.menu)))
        visible_items = items[window_start:window_start + len(self.menu)]
        changed = self.menu_title.set(model["title"]) or changed
        for index, component in enumerate(self.menu):
            text = ""
            if index < len(visible_items):
                text = visible_items[index][0]
                if not visible_items[index][1]:
                    text += "  -"
            changed = component.set(text) or changed
        changed = self.menu_highlight.set(
            selected - window_start, bool(visible_items)
        ) or changed
        page = "{}/{}".format(selected + 1, len(items)) if items else "-"
        changed = self.menu_footer.set(page + "  BACK | HOME") or changed
        changed = self.overlay.update(model.get("overlay")) or changed
        if not changed:
            self.skipped_count += 1
            return False
        self.render_count += 1
        try:
            self.display.refresh(minimum_frames_per_second=0)
        except (AttributeError, RuntimeError):
            pass
        return True
