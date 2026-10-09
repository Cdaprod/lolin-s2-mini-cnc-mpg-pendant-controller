"""Universal controller adapter contract plus mock and GRBL backends."""

from .model import AXES, MachineState


class ControllerAdapter:
    """Controller-neutral API consumed exclusively by the host bridge."""

    name = "base"

    def __init__(self, motion_enabled=False):
        self.motion_enabled = bool(motion_enabled)
        self.state = MachineState()

    def poll(self):
        return self.state

    def start_jog(self, axis, direction, feed):
        raise NotImplementedError

    def stop_jog(self):
        raise NotImplementedError

    def command(self, name):
        raise NotImplementedError

    def close(self):
        return None


class MockControllerAdapter(ControllerAdapter):
    """In-memory adapter for protocol and application tests."""

    name = "mock"

    def __init__(self, motion_enabled=False):
        super().__init__(motion_enabled)
        self.events = []
        self.state.connected = True
        self.state.mode = "idle"

    def start_jog(self, axis, direction, feed):
        if not self.motion_enabled:
            return False
        if axis not in AXES or direction not in (-1, 1) or feed <= 0:
            return False
        self.events.append(("jog_start", axis, direction, float(feed)))
        self.state.mode = "jog"
        return True

    def stop_jog(self):
        self.events.append(("jog_stop",))
        self.state.mode = "idle"
        return True

    def command(self, name):
        self.events.append(("command", name))
        return True


class GrblAdapter(ControllerAdapter):
    """GRBL/grblHAL serial adapter; construction does not enable motion."""

    name = "grbl"

    _REALTIME = {"HOLD": b"!", "RESUME": b"~", "RESET": b"\x18"}

    def __init__(self, transport, motion_enabled=False):
        super().__init__(motion_enabled)
        self.transport = transport
        self._buffer = bytearray()

    def start_jog(self, axis, direction, feed):
        if not self.motion_enabled:
            return False
        if axis not in AXES or direction not in (-1, 1) or feed <= 0:
            return False
        # A short incremental command is bounded again by the host lease, whose
        # expiry always emits GRBL jog cancel. No hardware is enabled by default.
        distance = 0.1 * direction
        line = "$J=G91 G21 {}{:.4f} F{:.3f}\n".format(
            axis, distance, float(feed))
        self.transport.write(line.encode("ascii"))
        return True

    def stop_jog(self):
        self.transport.write(b"\x85")
        return True

    def command(self, name):
        if name in self._REALTIME:
            self.transport.write(self._REALTIME[name])
            return True
        if name == "HOME":
            self.transport.write(b"$H\n")
            return True
        return False

    def poll(self):
        while True:
            line = self.transport.readline()
            if not line:
                break
            self._parse_line(line.decode("ascii", "replace").strip())
        self.state.connected = bool(self.transport.connected)
        return self.state

    def _parse_line(self, line):
        if not line.startswith("<") or not line.endswith(">"):
            if line.startswith("ALARM:"):
                self.state.alarm = line[6:]
                self.state.mode = "alarm"
            return
        parts = line[1:-1].split("|")
        self.state.mode = parts[0].lower()
        for field in parts[1:]:
            if field.startswith("MPos:"):
                self._coordinates(self.state.machine_position, field[5:])
            elif field.startswith("WPos:"):
                self._coordinates(self.state.work_position, field[5:])
            elif field.startswith("FS:"):
                values = field[3:].split(",")
                self.state.feed_rate = float(values[0])
                if len(values) > 1:
                    self.state.spindle_speed = float(values[1])

    @staticmethod
    def _coordinates(target, raw):
        for index, value in enumerate(raw.split(",")[:len(AXES)]):
            target[AXES[index]] = float(value)
