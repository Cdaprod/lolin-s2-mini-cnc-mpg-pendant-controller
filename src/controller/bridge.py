"""Protocol-v1 pendant endpoint. Never sends raw GRBL to a host bridge."""

import math

from src.state import AXES
from src.transport.protocol import (COMMAND, MOTION_RENEW_INTERVAL_MS,
                                    STATUS, ReliableSession)


class BridgeController:
    """GRBLController-shaped, fail-closed adapter for the reliable host link.

    Motion requires an independent explicit configuration opt-in. All ordinary
    G-code streaming is rejected until a dedicated bridge file protocol exists.
    """

    _COMMANDS = {"HOME": "HOME", "HOLD": "HOLD",
                 "RESUME": "RESUME", "RESET": "RESET"}

    def __init__(self, state, transport, clock, motion_enabled=False):
        self.state, self.transport, self.clock = state, transport, clock
        self.motion_enabled = bool(motion_enabled)
        self.queue = []
        self.observers = []
        self._intent = None
        self._last_motion_at = None
        self._last_renew_at = None
        self._pending_stop = False
        self._last_status_at = None
        self.session = ReliableSession(
            transport, self._handle_packet, clock, role="initiator",
            on_link_lost=self.cancel_jog, state=state)
        state.transport = "bridge-v1"

    def add_observer(self, callback):
        self.observers.append(callback)

    def _notify(self, event, value=None):
        for callback in self.observers:
            callback(event, value)

    def queue_command(self, command, kind="normal"):
        # A bridge COMMAND payload must be an allowlisted semantic action.
        # Arbitrary G-code and SD streaming are NOT supported by this adapter.
        name = self._COMMANDS.get(str(command).strip())
        if name is None or len(self.queue) >= 8:
            return False
        self.queue.append((name, kind))
        return True

    def discard_queued(self, kind):
        self.queue = [item for item in self.queue if item[1] != kind]

    def queue_jog(self, axis, distance, feed, units="mm"):
        # This host protocol authorizes bounded continuous jog segments, not
        # exact per-detent displacement. Keep it off unless explicitly enabled.
        if (not self.motion_enabled or not self.session.established or
                self.state.connection_state != "connected" or
                self.state.machine_state not in ("idle", "jog") or
                self.state.ui_handwheel_mode != "MOTION" or
                not self.state.deadman_enabled or self.state.estop_latched or
                self.state.estop_observed or axis not in AXES or
                units != "mm" or not math.isfinite(distance) or
                distance == 0 or not math.isfinite(feed) or feed <= 0):
            return False
        direction = 1 if distance > 0 else -1
        intent = (axis, direction, float(feed))
        if self._intent is not None and self._intent != intent:
            self.cancel_jog()
            return False
        self._intent = intent
        self._last_motion_at = self.clock()
        return True

    def realtime(self, name):
        if name in ("hold", "soft_reset"):
            self.cancel_jog()
        action = {"hold": "HOLD", "start": "RESUME",
                  "soft_reset": "RESET"}.get(name)
        if action is None:
            return False
        return self.queue_command(action, "realtime")

    def cancel_jog(self):
        self.queue = [entry for entry in self.queue if entry[1] != "jog"]
        self._intent = None
        self._pending_stop = self.session.motion_intent_sequence is not None
        self.state.jog_active = False
        return True

    def _handle_packet(self, packet):
        if packet.message_class != STATUS:
            return False
        try:
            fields = packet.payload.decode("ascii").split("|")
            if len(fields) != 13 or fields[0] != "STATE":
                return False
            mode, connected = fields[1], fields[2]
            if connected not in ("0", "1") or mode not in (
                    "idle", "jog", "run", "hold", "alarm", "disconnected"):
                return False
            positions = []
            for raw in fields[3:9]:
                value = float(raw) if raw else None
                if value is not None and not math.isfinite(value):
                    return False
                positions.append(value)
            feed, spindle = float(fields[9]), float(fields[10])
            if not math.isfinite(feed) or not math.isfinite(spindle):
                return False
            if fields[12] not in ("FRESH", "STALE"):
                return False
        except (ValueError, UnicodeError):
            return False
        self.state.machine_state = mode
        for axis, value in zip(AXES, positions):
            self.state.work_position[axis] = value
        self.state.feed_rate, self.state.spindle_speed = feed, spindle
        self.state.alarm = fields[11] or None
        self.state.connection_state = (
            "connected" if connected == "1" and fields[12] == "FRESH"
            else "disconnected")
        self._last_status_at = self.clock()
        self.state.last_controller_response = self._last_status_at
        if self.state.connection_state != "connected" or mode not in ("idle", "jog"):
            self.cancel_jog()
        return True

    def poll(self, now=None):
        self.session.poll()
        current = self.clock()
        healthy = (self.session.established and
                   self.session.link_state in ("HEALTHY", "DEGRADED") and
                   self._last_status_at is not None and
                   current - self._last_status_at <= 1.0)
        if not healthy:
            self.cancel_jog()
            self.state.connection_state = "disconnected"
        if self._intent is not None and (
                not healthy or not self.motion_enabled or
                not self.state.deadman_enabled or self.state.estop_latched or
                self.state.estop_observed or
                current - self._last_motion_at > 0.15):
            self.cancel_jog()
        if self._pending_stop:
            if self.session.send_motion_stop():
                self._pending_stop = False
            return
        if self.session.outstanding is not None or not healthy:
            return
        if self._intent is not None:
            if self.session.motion_intent_sequence is None:
                axis, direction, feed = self._intent
                payload = "JOG|{}|{}|{:.3f}".format(
                    axis, direction, feed).encode("ascii")
                if self.session.send_motion_start(payload):
                    self._last_renew_at = current
            elif (self._last_renew_at is None or
                  (current - self._last_renew_at) * 1000 >=
                  MOTION_RENEW_INTERVAL_MS):
                if self.session.send_motion_renew():
                    self._last_renew_at = current
            return
        if self.queue:
            name, kind = self.queue[0]
            if self.session.send(name.encode("ascii"), COMMAND, reliable=True):
                self.queue.pop(0)
                self._notify("sent", (name, kind))
