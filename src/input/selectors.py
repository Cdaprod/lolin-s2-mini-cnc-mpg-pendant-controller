"""Axis and multiplier selector models using manufacturer signal names."""

DEFAULT_AXIS_MAP = {
    "X": "AXIS_X", "Y": "AXIS_Y", "Z": "AXIS_Z",
    "4": "FILES", "5": "CONFIG", "6": "PREVIEW",
}
MOTION_AXES = ("X", "Y", "Z", "A", "B", "C")
PAGE_FOR_FUNCTION = {
    "FILES": "EXPLORER", "CONFIG": "CONFIGURATION", "PREVIEW": "PREVIEW",
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
            self.state.selector_function = "OFF"
            return "OFF"
        if name not in self.axis_map:
            raise SelectorError("invalid physical axis: " + name)
        self.state.selected_physical_axis = name
        function = str(self.axis_map[name]).upper()
        # Raw axis names remain accepted for existing/future six-axis profiles.
        if function in MOTION_AXES:
            function = "AXIS_" + function
        if function.startswith("AXIS_") and function[5:] in MOTION_AXES:
            self.state.selected_axis = function[5:]
            self.state.active_page = "OPERATIONAL"
        elif function in PAGE_FOR_FUNCTION:
            self.state.selected_axis = None
            self.state.active_page = PAGE_FOR_FUNCTION[function]
        else:
            raise SelectorError("invalid selector function: " + function)
        self.state.selector_function = function
        return function

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
