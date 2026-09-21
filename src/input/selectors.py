"""Axis and multiplier selector models using manufacturer signal names."""

DEFAULT_AXIS_MAP = {
    "X": "X", "Y": "Y", "Z": "Z",
    "4": "A", "5": "B", "6": "C",
}
MULTIPLIERS = {"X1": 1, "X10": 10, "X100": 100}


class SelectorError(ValueError):
    pass


class SelectorModel:
    def __init__(self, state, axis_map=None):
        self.state = state
        self.axis_map = dict(DEFAULT_AXIS_MAP)
        if axis_map:
            self.axis_map.update(axis_map)

    def select_axis(self, physical_axis):
        name = str(physical_axis).upper()
        if name == "OFF":
            self.state.selected_physical_axis = "OFF"
            self.state.selected_axis = None
            return None
        if name not in self.axis_map:
            raise SelectorError("invalid physical axis: " + name)
        self.state.selected_physical_axis = name
        self.state.selected_axis = self.axis_map[name]
        return self.state.selected_axis

    def select_multiplier(self, label):
        name = str(label).upper()
        if name not in MULTIPLIERS:
            raise SelectorError("invalid multiplier: " + name)
        self.state.selected_multiplier = name
        self.state.jog_increment = (
            self.state.base_increment * MULTIPLIERS[name]
        )
        return self.state.jog_increment

    def update_contacts(self, active_axes, active_multipliers):
        """Decode one-hot contacts; ambiguous states fail to OFF/error."""
        axes = list(active_axes)
        multipliers = list(active_multipliers)
        if len(axes) != 1:
            self.select_axis("OFF")
            raise SelectorError("axis selector is not one-hot")
        if len(multipliers) != 1:
            raise SelectorError("multiplier selector is not one-hot")
        self.select_axis(axes[0])
        self.select_multiplier(multipliers[0])
