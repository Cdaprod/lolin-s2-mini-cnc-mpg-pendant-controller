"""Universal controller adapter contract plus mock and GRBL backends."""

import math
import time

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

    def renew_jog(self):
        return True

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
        self._last_status_poll = None
        self._status_poll_interval = 0.2
        self._work_offset = None
        self._machine_fresh = False
        self._active_jog = None
        self._last_jog_at = None
        self._jog_segment_mm = 0.5
        self._jog_segment_max_ms = 180

    def _send_segment(self):
        if self._active_jog is None or not self.motion_enabled:
            return False
        axis, direction, feed = self._active_jog
        distance = min(self._jog_segment_mm,
                       feed * self._jog_segment_max_ms / 60000.0)
        if distance <= 0:
            return False
        line = "$J=G91 G21 {}{:.4f} F{:.3f}\\n".format(
            axis, direction * distance, feed)
        self.transport.write(line.encode("ascii"))
        self._last_jog_at = time.monotonic()
        return True

    def start_jog(self, axis, direction, feed):
        if (not self.motion_enabled or not self.transport.connected or
                axis not in AXES or direction not in (-1, 1) or
                not math.isfinite(feed) or feed <= 0):
            return False
        if self._active_jog is not None:
            return False
        self._active_jog = (axis, direction, float(feed))
        if not self._send_segment():
            self._active_jog = None
            return False
        return True

    def renew_jog(self):
        if self._active_jog is None or not self.motion_enabled:
            return False
        # Send only on an authenticated, in-order, valid lease renewal.
        # At most one short segment per renewal, never a queued stream.
        return self._send_segment()

    def stop_jog(self):
        self._active_jog = None
        self._last_jog_at = None
        self.transport.write(b"\\x85")
        return True

    def command(self, name):
        # HOME and RESUME can initiate motion even without an active jog.
        if name in ("HOME", "RESUME") and not self.motion_enabled:
            return False
        if name in self._REALTIME:
            self.transport.write(self._REALTIME[name])
            return True
        if name == "HOME":
            self.transport.write(b"$H\n")
            return True
        return False

    def poll(self):
        now = time.monotonic()
        if (self.transport.connected and
                (self._last_status_poll is None or
                 now - self._last_status_poll >= self._status_poll_interval)):
            self.transport.write(b"?")
            self._last_status_poll = now
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
        explicit_work = False
        fresh_machine = False
        for field in parts[1:]:
            if field.startswith("MPos:"):
                self._coordinates(self.state.machine_position, field[5:])
                fresh_machine = True
            elif field.startswith("WPos:"):
                self._coordinates(self.state.work_position, field[5:])
                explicit_work = True
            elif field.startswith("WCO:"):
                offsets = dict((axis, None) for axis in AXES)
                self._coordinates(offsets, field[4:])
                self._work_offset = offsets
            elif field.startswith("FS:"):
                values = field[3:].split(",")
                self.state.feed_rate = float(values[0])
                if len(values) > 1:
                    self.state.spindle_speed = float(values[1])
        if fresh_machine and self._work_offset is not None and not explicit_work:
            for axis in AXES:
                machine = self.state.machine_position[axis]
                offset = self._work_offset[axis]
                if machine is not None and offset is not None:
                    self.state.work_position[axis] = machine - offset

    @staticmethod
    def _coordinates(target, raw):
        for index, value in enumerate(raw.split(",")[:len(AXES)]):
            target[AXES[index]] = float(value)
