"""Generic GRBL 1.1 parser, command queue, and real-time protocol."""

from .base import ControllerProtocol
from src.state import AXES

REALTIME = {
    "status": b"?", "start": b"~", "hold": b"!",
    "jog_cancel": b"\x85", "soft_reset": b"\x18",
}

_STATE_MAP = {
    "idle": "idle", "jog": "jog", "run": "run", "hold": "hold",
    "alarm": "alarm", "door": "hold", "home": "run", "check": "idle",
    "sleep": "hold",
}


def _vector(value):
    parts = value.split(",")
    result = {}
    for index, raw in enumerate(parts[:len(AXES)]):
        result[AXES[index]] = float(raw)
    return result


class GRBLController(ControllerProtocol):
    def __init__(self, state, transport, clock=None, queue_limit=8,
                 status_interval=0.2):
        self.state = state
        self.transport = transport
        self.clock = clock
        self.queue_limit = int(queue_limit)
        self.status_interval = float(status_interval)
        self.queue = []
        self.awaiting_response = None
        self.observers = []
        self.last_status_query = None
        state.transport = transport.name

    def add_observer(self, callback):
        self.observers.append(callback)

    def _notify(self, event, value=None):
        for callback in self.observers:
            callback(event, value)

    def queue_command(self, command, kind="normal"):
        command = command.strip()
        if not command:
            return False
        if len(self.queue) >= self.queue_limit:
            return False
        self.queue.append((command, kind))
        return True

    def queue_jog(self, axis, distance, feed, units="mm"):
        axis = axis.upper()
        if axis not in AXES:
            raise ValueError("invalid jog axis: " + axis)
        unit = "G21" if units == "mm" else "G20"
        command = "$J=G91 {} {}{:.6f} F{:.3f}".format(
            unit, axis, float(distance), float(feed)
        )
        # Coalesce queued (not transmitted) same-axis jogs to bound latency.
        prefix = "$J=G91 {} {}".format(unit, axis)
        if self.queue and self.queue[-1][1] == "jog" and self.queue[-1][0].startswith(prefix):
            previous = self.queue.pop()[0]
            old = float(previous.split(axis, 1)[1].split(" ", 1)[0])
            command = "$J=G91 {} {}{:.6f} F{:.3f}".format(
                unit, axis, old + float(distance), float(feed)
            )
        return self.queue_command(command, "jog")

    def realtime(self, name):
        if name == "soft_reset":
            self.queue = []
            self.awaiting_response = None
        self.transport.write(REALTIME[name])

    def cancel_jog(self):
        self.queue = [item for item in self.queue if item[1] != "jog"]
        self.realtime("jog_cancel")
        self.state.jog_active = False

    def discard_queued(self, kind):
        """Discard commands not yet transmitted, preserving other producers."""
        self.queue = [item for item in self.queue if item[1] != kind]

    def _timestamp(self, now):
        if now is not None:
            return now
        return self.clock() if self.clock else 0.0

    def parse_line(self, raw, now=None):
        if isinstance(raw, bytes):
            try:
                raw = raw.decode("ascii")
            except UnicodeError:
                self.state.error = "malformed non-ASCII response"
                self._notify("malformed", raw)
                return "malformed"
        line = raw.strip()
        if not line:
            return None
        self.state.last_controller_response = self._timestamp(now)
        self.state.connection_state = "connected"
        if line == "ok":
            completed = self.awaiting_response
            self.awaiting_response = None
            self._notify("ok", completed)
            return "ok"
        if line.startswith("error:"):
            self.state.error = line
            completed = self.awaiting_response
            self.awaiting_response = None
            if completed is not None:
                self.discard_queued(completed[1])
            self._notify("error", (line, completed))
            return "error"
        if line.startswith("ALARM:"):
            self.state.alarm = line.split(":", 1)[1]
            self.state.machine_state = "alarm"
            self.state.jog_active = False
            self.queue = []
            self.awaiting_response = None
            self._notify("alarm", self.state.alarm)
            return "alarm"
        if line.startswith("Grbl "):
            self.state.controller_identity = line.split(" [", 1)[0]
            self.state.controller_capabilities.add("grbl-1.1")
            self.state.machine_state = "connecting"
            self._notify("startup", line)
            return "startup"
        if line.startswith("[MSG:"):
            self.state.message = line[5:-1] if line.endswith("]") else line[5:]
            self._notify("message", self.state.message)
            return "message"
        if line.startswith("[") and line.endswith("]"):
            if line.startswith("[VER:") or line.startswith("[OPT:"):
                self.state.controller_identity = line[1:-1]
            elif line.startswith("[GC:"):
                modes = line[4:-1].split()
                for mode in modes:
                    if mode in ("G54", "G55", "G56", "G57", "G58", "G59"):
                        self.state.active_coordinate_system = mode
                    elif mode in ("M3", "M4", "M5"):
                        self.state.spindle_command = {
                            "M3": "CW", "M4": "CCW", "M5": "OFF"
                        }[mode]
            self._notify("info", line[1:-1])
            return "info"
        if line.startswith("<") and line.endswith(">"):
            self._parse_status(line[1:-1])
            self._notify("status", line)
            return "status"
        self._notify("unknown", line)
        return "unknown"

    def _parse_status(self, report):
        fields = report.split("|")
        raw_state = fields[0].split(":", 1)[0].lower()
        self.state.machine_state = _STATE_MAP.get(raw_state, "error")
        self.state.jog_active = self.state.machine_state == "jog"
        for field in fields[1:]:
            if ":" not in field:
                continue
            name, value = field.split(":", 1)
            try:
                if name == "MPos":
                    self.state.machine_position.update(_vector(value))
                elif name == "WPos":
                    self.state.work_position.update(_vector(value))
                elif name == "WCO":
                    self.state.work_coordinate_offset.update(_vector(value))
                elif name == "FS":
                    values = value.split(",")
                    self.state.feed_rate = float(values[0])
                    self.state.spindle_speed = float(values[1])
                elif name == "F":
                    self.state.feed_rate = float(value)
                elif name == "Ov":
                    values = value.split(",")
                    self.state.feed_override = int(values[0])
                    self.state.rapid_override = int(values[1])
                    self.state.spindle_override = int(values[2])
                elif name == "Pn":
                    self.state.pin_state = set(value)
                elif name == "A":
                    self.state.spindle_command = (
                        "CCW" if "C" in value else
                        "CW" if "S" in value else "OFF"
                    )
                elif name == "WCS":
                    self.state.active_coordinate_system = value
            except (ValueError, IndexError):
                self.state.error = "malformed status field: " + field
        self.state.update_derived_positions()

    def poll(self, now=None):
        timestamp = self._timestamp(now)
        connected = self.transport.connected
        if not connected:
            self.state.connection_state = "disconnected"
            self.state.machine_state = "disconnected"
            self.state.connection_started_timestamp = None
            return
        if self.state.connection_state == "disconnected":
            self.state.connection_state = "connecting"
            self.state.machine_state = "connecting"
            self.state.connection_started_timestamp = timestamp
        self.transport.poll()
        for _ in range(8):
            line = self.transport.readline()
            if line is None:
                break
            self.parse_line(line, timestamp)
        if (self.last_status_query is None or
                timestamp - self.last_status_query >= self.status_interval):
            self.realtime("status")
            self.last_status_query = timestamp
        if self.awaiting_response is None and self.queue:
            command = self.queue.pop(0)
            self.transport.write((command[0] + "\n").encode("ascii"))
            self.awaiting_response = command
            self._notify("sent", command)
