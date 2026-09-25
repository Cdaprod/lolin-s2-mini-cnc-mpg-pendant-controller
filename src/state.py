"""Shared, allocation-conscious pendant state model."""

AXES = ("X", "Y", "Z", "A", "B", "C")


def _coordinates():
    return dict((axis, None) for axis in AXES)


class PendantState:
    """Single source of truth shared by inputs, protocol, safety, and UI."""

    def __init__(self, base_increment=0.001):
        self.connection_state = "disconnected"
        self.connection_started_timestamp = None
        self.controller_identity = ""
        self.controller_capabilities = set()
        self.machine_state = "disconnected"
        self.selected_physical_axis = "OFF"
        self.selected_axis = None
        self.selected_multiplier = "X1"
        self.base_increment = float(base_increment)
        self.jog_increment = self.base_increment
        self.machine_position = _coordinates()
        self.work_position = _coordinates()
        self.work_coordinate_offset = _coordinates()
        self.coordinate_mode = "WPos"
        self.active_coordinate_system = None
        self.feed_rate = 0.0
        self.spindle_speed = 0.0
        self.spindle_command = None
        self.feed_override = 100
        self.rapid_override = 100
        self.spindle_override = 100
        self.alarm = None
        self.error = None
        self.message = None
        self.pin_state = set()
        self.transport = "disabled"
        self.wifi_state = "DISABLED"
        self.wifi_ssid = None
        self.wifi_ip = None
        self.wifi_rssi = None
        self.hostname = None
        self.network_error = None
        self.i2c_error = None
        self.controller_error = None
        self.controller_enabled = False
        self.input_error = None
        self.display_error = None
        self.touch_error = None
        self.board_profile = ""
        self.display_profile = ""
        self.selector_backend = "disabled"
        self.mcp23017_detected = False
        self.mcp23017_address = None
        self.subsystems = {}
        self.runtime_version = "unknown"
        self.sd_job_state = "idle"
        self.storage_state = "unknown"
        self.storage_error = None
        self.current_filename = None
        self.streaming_progress = 0.0
        self.streaming_line = 0
        self.streaming_bytes = 0
        self.jog_active = False
        self.estop_observed = False
        self.estop_latched = False
        self.deadman_enabled = False
        self.mpg_activity = 0
        self.mpg_activity_timestamp = None
        self.axis_transition_direction = 0
        self.axis_transition_timestamp = None
        self.resolution_transition_direction = 0
        self.resolution_transition_timestamp = None
        self.last_controller_response = None
        # UI context is mirrored here so the safety layer independently gates
        # wheel-generated motion; display navigation is not a safety boundary.
        self.ui_screen = "BOOT"
        self.ui_handwheel_mode = "DISABLED"
        self.loop_count = 0
        self.last_loop_duration = 0.0
        self.free_heap = None
        self.render_count = 0
        self.last_status_age = None
        self.round_ui_bootstrap = False

    def set_estop(self, active):
        self.estop_observed = bool(active)
        if active:
            self.estop_latched = True
            self.machine_state = "estop"
            self.jog_active = False
            self.sd_job_state = "inhibited"

    def clear_estop_latch(self):
        if self.estop_observed:
            raise RuntimeError("cannot recover while E-stop contact is active")
        self.estop_latched = False
        self.machine_state = "connecting"

    def update_derived_positions(self):
        """Derive the missing open-loop coordinate set where possible."""
        for axis in AXES:
            machine = self.machine_position[axis]
            work = self.work_position[axis]
            offset = self.work_coordinate_offset[axis]
            if work is None and machine is not None and offset is not None:
                self.work_position[axis] = machine - offset
            elif machine is None and work is not None and offset is not None:
                self.machine_position[axis] = work + offset
            elif offset is None and machine is not None and work is not None:
                self.work_coordinate_offset[axis] = machine - work

    def displayed_position(self):
        if self.coordinate_mode == "MPos":
            return self.machine_position
        return self.work_position
