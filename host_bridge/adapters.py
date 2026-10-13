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
        if (axis not in AXES or direction not in (-1, 1) or
                not math.isfinite(feed) or feed <= 0):
            return False
        self.events.append(("jog_start", axis, direction, float(feed)))
        self.state.mode = "jog"
        return True

    def stop_jog(self):
        self.events.append(("jog_stop",))
        self.state.mode = "idle"
        return True

    def command(self, name):
        if name in ("HOME", "RESUME") and not self.motion_enabled:
            return False
        if name not in ("HOME", "RESUME", "HOLD", "RESET"):
            return False
        self.events.append(("command", name))
        return True


class GrblAdapter(ControllerAdapter):
    """GRBL/grblHAL serial adapter; construction does not enable motion."""

    name = "grbl"

    _REALTIME = {"HOLD": b"!", "RESUME": b"~", "RESET": b"\x18"}

    def __init__(self, transport, motion_enabled=False, clock=time.monotonic,
                 status_poll_interval=0.2, status_stale_timeout=1.0):
        super().__init__(motion_enabled)
        self.transport = transport
        self.clock = clock
        self._last_status_poll = None
        self._last_status_at = None
        self._status_poll_interval = float(status_poll_interval)
        self._status_stale_timeout = float(status_stale_timeout)
        self._active_jog = None
        self._last_jog_at = None
        self._pending_jog = False
        self._cancel_sent = False
        self._jog_segment_mm = 0.5
        self._jog_segment_max_ms = 180
        self._jog_ack_timeout = 0.3
        self._jog_completion_timeout = 0.6

    def _send_segment(self):
        if (self._active_jog is None or not self.motion_enabled or
                self._pending_jog or not self.transport.connected or
                not self.state.telemetry_fresh or
                self.state.mode != "idle"):
            return False
        axis, direction, feed = self._active_jog
        distance = min(self._jog_segment_mm,
                       feed * self._jog_segment_max_ms / 60000.0)
        if distance <= 0:
            return False
        line = "$J=G91 G21 {}{:.4f} F{:.3f}\n".format(
            axis, direction * distance, feed)
        try:
            written = self.transport.write(line.encode("ascii"))
        except (OSError, RuntimeError):
            return False
        if written is not None and written != len(line):
            return False
        self._pending_jog = True
        self._cancel_sent = False
        self._last_jog_at = self.clock()
        return True

    def start_jog(self, axis, direction, feed):
        if (not self.motion_enabled or not self.transport.connected or
                axis not in AXES or direction not in (-1, 1) or
                not math.isfinite(feed) or feed <= 0 or
                not self.state.telemetry_fresh or
                self.state.mode not in ("idle", "jog")):
            return False
        if self._active_jog is not None:
            return False
        self._active_jog = (axis, direction, float(feed))
        if not self._send_segment():
            self._active_jog = None
            return False
        return True

    def renew_jog(self):
        if (self._active_jog is None or not self.motion_enabled or
                not self.transport.connected):
            return False
        now = self.clock()
        if self._pending_jog:
            # A prompt renewal may extend the host lease while GRBL is still
            # acknowledging, but a missing acknowledgement fails closed.
            return now - self._last_jog_at <= self._jog_ack_timeout
        if self._last_jog_at is not None:
            if now - self._last_jog_at > self._jog_completion_timeout:
                return False
            # An ACK means "accepted", not "finished". Admit another segment
            # only after a later status report confirms controller Idle.
            if (self._last_status_at is None or
                    self._last_status_at <= self._last_jog_at or
                    self.state.mode != "idle"):
                return True
        return self._send_segment()

    def stop_jog(self):
        self._active_jog = None
        self._last_jog_at = None
        self._pending_jog = False
        if not self._cancel_sent and self.transport.connected:
            try:
                written = self.transport.write(b"\x85")
            except (OSError, RuntimeError):
                return False
            if written is not None and written != 1:
                return False
            self._cancel_sent = True
        return self._cancel_sent

    def command(self, name):
        # HOME and RESUME can initiate motion even without an active jog.
        if name in ("HOME", "RESUME") and not self.motion_enabled:
            return False
        if not self.transport.connected:
            return False
        if name in self._REALTIME:
            try:
                self.transport.write(self._REALTIME[name])
            except (OSError, RuntimeError):
                return False
            return True
        if name == "HOME":
            try:
                self.transport.write(b"$H\n")
            except (OSError, RuntimeError):
                return False
            return True
        return False

    def poll(self):
        now = self.clock()
        if not self.transport.connected:
            if self._active_jog is not None or self._pending_jog:
                self.stop_jog()
            self.state.connected = False
            self.state.telemetry_fresh = False
            self.state.mode = "disconnected"
            self._last_status_poll = None
            return self.state
        # A failed realtime cancellation must be retried after the serial
        # transport becomes writable, even with no remaining jog intent.
        if not self._cancel_sent:
            self.stop_jog()
        if (self.transport.connected and
                (self._last_status_poll is None or
                 now - self._last_status_poll >= self._status_poll_interval)):
            try:
                self.transport.write(b"?")
            except (OSError, RuntimeError):
                self.stop_jog()
                self.state.connected = False
                self.state.telemetry_fresh = False
                return self.state
            else:
                self._last_status_poll = now
        while True:
            line = self.transport.readline()
            if not line:
                break
            self._parse_line(line.decode("ascii", "replace").strip(), now)
        self.state.connected = bool(self.transport.connected)
        self.state.telemetry_fresh = bool(
            self._last_status_at is not None and
            now - self._last_status_at <= self._status_stale_timeout)
        return self.state

    def _parse_line(self, line, now=None):
        if not line.startswith("<") or not line.endswith(">"):
            if line == "ok":
                self._pending_jog = False
                return
            if line.startswith("error:"):
                self._pending_jog = False
                if self._active_jog is not None:
                    self.stop_jog()
                self.state.alarm = line
                return
            if line.startswith("ALARM:"):
                self.state.alarm = line[6:]
                self.state.mode = "alarm"
                if self._active_jog is not None or self._pending_jog:
                    self.stop_jog()
            return
        parts = line[1:-1].split("|")
        mode = parts[0].lower()
        machine = work = offset = None
        feed = spindle = None
        for field in parts[1:]:
            if field.startswith("MPos:"):
                machine = self._coordinates(field[5:])
                if machine is None:
                    return
            elif field.startswith("WPos:"):
                work = self._coordinates(field[5:])
                if work is None:
                    return
            elif field.startswith("WCO:"):
                offset = self._coordinates(field[4:])
                if offset is None:
                    return
            elif field.startswith("FS:"):
                try:
                    values = field[3:].split(",")
                    feed = float(values[0])
                    spindle = float(values[1]) if len(values) > 1 else 0.0
                    if not math.isfinite(feed) or not math.isfinite(spindle):
                        return
                except (ValueError, IndexError):
                    return
        if machine is None and work is None:
            return
        self.state.mode = mode
        if machine is not None:
            self.state.machine_position.update(machine)
        if work is not None:
            self.state.work_position.update(work)
        elif machine is not None and offset is not None:
            for axis in AXES:
                if machine[axis] is not None and offset[axis] is not None:
                    self.state.work_position[axis] = machine[axis] - offset[axis]
        elif machine is not None:
            for axis in AXES:
                self.state.work_position[axis] = None
        if feed is not None:
            self.state.feed_rate = feed
            self.state.spindle_speed = spindle
        self.state.alarm = None if mode != "alarm" else self.state.alarm
        self._last_status_at = self.clock() if now is None else now
        if mode not in ("idle", "jog"):
            if self._active_jog is not None or self._pending_jog:
                self.stop_jog()

    @staticmethod
    def _coordinates(raw):
        values = raw.split(",")
        if not 3 <= len(values) <= len(AXES):
            return None
        try:
            parsed = [float(value) for value in values]
        except ValueError:
            return None
        if not all(math.isfinite(value) for value in parsed):
            return None
        result = dict((axis, None) for axis in AXES)
        for index, value in enumerate(parsed):
            result[AXES[index]] = value
        return result
