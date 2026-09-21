"""Console/mock renderer for development and serial-console operation."""

from .base import Display
from src.state import AXES


class ConsoleDisplay(Display):
    def __init__(self, output=print):
        self.output = output
        self.last_frame = None

    def format(self, state):
        title = "{} {:>12}".format(
            state.controller_identity or state.transport.upper(),
            state.machine_state.upper(),
        )
        positions = state.displayed_position()
        rows = [title, "Connection: {} via {}".format(
            state.connection_state, state.transport
        ), "{} coordinates (open-loop controller)".format(
            state.coordinate_mode
        )]
        for axis in AXES:
            value = positions[axis]
            marker = ">" if axis == state.selected_axis else " "
            rows.append("{} {} {:>+11.3f}".format(
                axis, marker, value if value is not None else 0.0
            ))
        rows.append("{} / {:.3f}mm  {}".format(
            state.selected_multiplier, state.jog_increment,
            state.active_coordinate_system or "---"
        ))
        rows.append("F:{:.1f} S:{:.0f} Ov:{}/{}/{}".format(
            state.feed_rate, state.spindle_speed, state.feed_override,
            state.rapid_override, state.spindle_override
        ))
        rows.append("SD:{} {:>5.1f}% {}".format(
            state.sd_job_state, state.streaming_progress * 100,
            state.current_filename or ""
        ))
        if state.estop_observed or state.estop_latched:
            rows.append("*** E-STOP OBSERVED — INHIBITED ***")
        if state.alarm or state.error:
            rows.append("FAULT: {}".format(state.alarm or state.error))
        return "\n".join(rows)

    def render(self, state):
        frame = self.format(state)
        if frame != self.last_frame:
            self.output(frame)
            self.last_frame = frame
        return frame
