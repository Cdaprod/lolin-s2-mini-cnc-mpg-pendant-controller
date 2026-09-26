"""Map the authoritative UIManager view model onto retained round components."""

from .components import (AxisReadout, IndicatorStrip, JogActivity,
                         JogMultiplier, Overlay, RadialTabBar, StatusRing,
                         TextComponent)


class RoundRenderer:
    """Rich renderer that mutates a persistent scene supplied by a factory."""

    HOME_TABS = ("TAP: MENU",)

    def __init__(self, display, scene_factory):
        self.display = display
        self.ui = None
        self.render_count = 0
        self.skipped_count = 0
        scene = scene_factory(display)
        self.root = scene["root"]
        self.home_group = scene.get("home_group")
        self.menu_group = scene.get("menu_group")
        self.status_ring = StatusRing(scene["ring"])
        self.title = TextComponent(scene["title"])
        self.axis = AxisReadout(scene["axis"], scene["value"],
                                scene["secondary"])
        self.tabs = RadialTabBar(scene["tabs"])
        self.multiplier = JogMultiplier(scene["multiplier"])
        self.activity = JogActivity(scene["activity"])
        self.indicators = IndicatorStrip(scene["indicators"])
        self.menu = [TextComponent(line) for line in scene["menu"]]
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
        changed = self.status_ring.set(state.machine_state)
        changed = self.status_ring.activity(
            model["mpg_activity"] if model["jog_armed"] else 0,
                                            model["jog_armed"]) or changed
        if is_home:
            readiness = "JOG ARMED" if model["jog_armed"] else "MOTION OFF"
            title = "{} / {}".format(state.machine_state.upper(), readiness)
        else:
            title = model["title"]
        changed = self.title.set(title) or changed
        coordinates = state.displayed_position()
        selected = state.selected_axis
        changed = self.axis.update(selected, coordinates.get(selected),
                                   coordinates,
                                   model["axis_transition_direction"]) or changed
        changed = self.multiplier.set(
            state.selected_multiplier,
            model["resolution_transition_direction"]) or changed
        changed = self.activity.update(
            model["jog_hold"], model["mpg_activity"]
        ) or changed
        wifi = getattr(state, "wifi_state", "DISABLED") in (
            "CONNECTED", "connected"
        )
        changed = self.indicators.update(
            state.connection_state == "connected", wifi,
            state.storage_state == "available"
        ) or changed
        changed = self.tabs.update(self.HOME_TABS, 0) or changed
        items = model.get("items", ())
        if model.get("details"):
            items = tuple(("{}: {}".format(key, value), True, "")
                          for key, value in model["details"])
        selected = min(model.get("selected", 0), max(0, len(items) - 1))
        window_start = max(0, min(selected - len(self.menu) + 1,
                                  len(items) - len(self.menu)))
        visible_items = items[window_start:window_start + len(self.menu)]
        for index, component in enumerate(self.menu):
            text = ""
            if index < len(visible_items):
                absolute = window_start + index
                marker = "› " if absolute == selected else "  "
                text = marker + visible_items[index][0]
            changed = component.set(text) or changed
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
