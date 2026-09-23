"""Stateful retained components used by the round renderer."""

from . import theme


class TextComponent:
    def __init__(self, line, prefix=""):
        self.line = line
        self.prefix = prefix
        self.value = None

    def set(self, value):
        value = self.prefix + str(value)
        if value == self.value:
            return False
        self.value = value
        return self.line.set_text(value)


class StatusRing:
    def __init__(self, node):
        self.node = node
        self.state = None

    def set(self, state):
        state = str(state).lower()
        if state == self.state:
            return False
        self.state = state
        self.node.color = theme.MACHINE_COLORS.get(state, theme.MUTED)
        return True


class AxisReadout:
    def __init__(self, axis_line, value_line, secondary_line):
        self.axis = TextComponent(axis_line)
        self.value = TextComponent(value_line)
        self.secondary = TextComponent(secondary_line)

    def update(self, axis, value, coordinates):
        changed = self.axis.set(axis or "—")
        shown = "---" if value is None else "{:+.3f}".format(value)
        changed = self.value.set(shown) or changed
        values = []
        for name in ("X", "Y", "Z", "A"):
            coordinate = coordinates.get(name)
            values.append("{}:{}".format(
                name, "---" if coordinate is None else "{:.2f}".format(coordinate)
            ))
        return self.secondary.set("  ".join(values)) or changed


class RadialTabBar:
    def __init__(self, lines):
        self.lines = lines
        self.selected = None

    def update(self, labels, selected):
        changed = selected != self.selected
        self.selected = selected
        for index, line in enumerate(self.lines):
            label = labels[index] if index < len(labels) else ""
            value = ("•" if index == selected else " ") + label
            changed = line.set_text(value) or changed
        return changed


class JogMultiplier:
    def __init__(self, line):
        self.text = TextComponent(line)

    def set(self, selected):
        labels = []
        for value in ("X1", "X10", "X100"):
            labels.append("[{}]".format(value) if value == selected else value)
        return self.text.set("  ".join(labels))


class IndicatorStrip:
    def __init__(self, line):
        self.text = TextComponent(line)

    def update(self, controller, wifi, storage):
        return self.text.set("CNC:{}  WIFI:{}  SD:{}".format(
            "●" if controller else "○", "●" if wifi else "○",
            "●" if storage else "○"
        ))


class Overlay:
    def __init__(self, group, title_line, detail_line):
        self.group = group
        self.title = TextComponent(title_line)
        self.detail = TextComponent(detail_line)
        self.signature = None

    def update(self, overlay):
        signature = tuple(overlay) if overlay else None
        if signature == self.signature:
            return False
        self.signature = signature
        self.group.hidden = not bool(overlay)
        self.title.set(overlay[0] if overlay else "")
        self.detail.set(overlay[1] if overlay else "")
        return True
