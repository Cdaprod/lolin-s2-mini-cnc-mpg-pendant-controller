"""Retained, allocation-conscious components for the round instrument UI."""

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


class InstrumentRing:
    """Drive the state ring and its directional, relative MPG arcs."""

    def __init__(self, node):
        self.node = node
        self.signature = None

    def update(self, machine_state, activity, armed):
        signature = (str(machine_state).lower(), int(activity), bool(armed))
        if signature == self.signature:
            return False
        self.signature = signature
        if hasattr(self.node, "update"):
            self.node.update(*signature)
        else:
            self.node.color = theme.MACHINE_COLORS.get(signature[0], theme.MUTED)
        return True


class AxisReadout:
    def __init__(self, axis_line, value_line, context_line):
        self.axis = TextComponent(axis_line)
        self.value = TextComponent(value_line)
        self.context = TextComponent(context_line)

    def update(self, axis, value, coordinate_mode, units, transition=0):
        marker = ">" if transition > 0 else "<" if transition < 0 else ""
        changed = self.axis.set("{}{}".format(marker, axis or "OFF"))
        shown = "---" if value is None else "{:+.3f}".format(value)
        changed = self.value.set(shown) or changed
        return self.context.set("{}  {}".format(
            str(coordinate_mode).upper(), units
        )) or changed


class IncrementBadge:
    def __init__(self, line):
        self.text = TextComponent(line)

    def update(self, selected, transition=0):
        marker = ">" if transition > 0 else "<" if transition < 0 else ""
        return self.text.set("{}{}".format(marker, selected))


class MotionPrompt:
    """Describe the physical Jog Hold and signed relative MPG feedback."""

    def __init__(self, line):
        self.text = TextComponent(line)

    def update(self, hold, armed, activity, controller):
        activity = int(activity)
        if not controller:
            value = "CONTROLLER OFFLINE"
        elif not hold:
            value = "HOLD TO JOG"
        elif not armed:
            value = "MOTION INHIBITED"
        elif activity > 0:
            value = "CW  " + ">" * min(4, activity)
        elif activity < 0:
            value = "<" * min(4, -activity) + "  CCW"
        else:
            value = "JOG READY"
        return self.text.set(value)


class ConnectivityGlyphs:
    """Compact secondary status; healthy services recede behind machining data."""

    def __init__(self, line):
        self.text = TextComponent(line)

    def update(self, wifi, storage):
        return self.text.set("NET{}  SD{}  MENU".format(
            "+" if wifi else "-", "+" if storage else "-"
        ))


class MenuHighlight:
    def __init__(self, node):
        self.node = node
        self.row = None

    def set(self, row, visible=True):
        row = int(row)
        changed = row != self.row or self.node.hidden == bool(visible)
        self.row = row
        self.node.hidden = not visible
        self.node.y = 58 + row * 22
        return changed


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
