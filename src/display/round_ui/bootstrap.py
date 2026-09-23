"""Production-renderer hardware bootstrap with deterministic mock CNC data."""


def apply_mock_state(state):
    """Populate representative status without connecting a GRBL controller."""
    state.connection_state = "connected"
    state.machine_state = "idle"
    state.controller_identity = "MOCK CNC"
    state.selected_axis = "X"
    state.selected_physical_axis = "X"
    state.selected_multiplier = "X10"
    state.jog_increment = state.base_increment * 10
    state.work_position.update({
        "X": 124.520, "Y": -18.250, "Z": 3.100, "A": 0.0,
    })
    state.storage_state = "available"
    state.sd_job_state = "idle"
    state.wifi_state = "connected"
    state.round_ui_bootstrap = True
    state.message = "Round UI hardware test"
