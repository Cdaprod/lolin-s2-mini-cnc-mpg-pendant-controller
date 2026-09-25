"""Production-renderer hardware bootstrap with deterministic mock CNC data."""


def apply_mock_state(state):
    """Populate representative status without connecting a GRBL controller."""
    state.selected_axis = "X"
    state.selected_physical_axis = "X"
    state.selected_multiplier = "X10"
    state.jog_increment = state.base_increment * 10
    state.work_position.update({
        "X": 124.520, "Y": -18.250, "Z": 3.100, "A": 0.0,
    })
    state.round_ui_bootstrap = True
    state.message = "Round UI hardware test"
