"""Map the authoritative UIManager view model onto retained round components."""

from .components import (AxisReadout, IndicatorStrip, JogMultiplier, Overlay,
                         RadialTabBar, StatusRing, TextComponent)


class RoundRenderer:
    """Rich renderer that mutates a persistent scene supplied by a factory."""

    HOME_TABS = ("STATUS", "JOG", "JOBS", "WIFI", "SETTINGS")

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
        changed = self.title.set(model["title"]) or changed
        coordinates = state.displayed_position()
        selected = state.selected_axis
        changed = self.axis.update(selected, coordinates.get(selected),
                                   coordinates) or changed
        changed = self.multiplier.set(state.selected_multiplier) or changed
        wifi = getattr(state, "wifi_state", "DISABLED") in (
            "CONNECTED", "connected"
        )
        changed = self.indicators.update(
            state.connection_state == "connected", wifi,
            state.storage_state == "available"
        ) or changed
        tab_index = 1 if is_home else 0
        changed = self.tabs.update(self.HOME_TABS, tab_index) or changed
        items = model.get("items", ())
        for index, component in enumerate(self.menu):
            text = ""
            if index < len(items):
                marker = "› " if index == model.get("selected") else "  "
                text = marker + items[index][0]
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
