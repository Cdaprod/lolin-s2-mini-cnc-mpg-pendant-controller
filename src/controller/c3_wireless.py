"""ESP-NOW GRBL endpoint for per-detent jogging.

MOTION REMAINS OPT-IN AT THE C3 RECEIVER. This adapter never equates
radio pairing with machine state. The C3 must confirm fresh GRBL status.
"""
import time
from src.controller.grbl import GRBLController
from src.transport.c3_pairing_bench import C3PairingBench
from src.transport import c3_espnow_protocol as proto


class C3WirelessController:
    def __init__(self, state, radio=None, now=None, esp=None, session=None):
        self.state = state
        self.clock = now or time.monotonic
        self.transport = C3PairingBench(radio=radio, now=self.clock, esp=esp,
                                        session=session)
        self.parser = GRBLController(state, self.transport, clock=self.clock)
        self.queue = []
        self.observers = []
        self._partial = bytearray()
        self._last_status = None
        self._status_peer = None
        self._had_pair = False
        self._pending_seq = None
        self._pending_at = None
        self._stop_pending = False
        self._stop_seq = None
        self._stop_at = None
        self._stop_attempts = 0
        state.transport = "c3-espnow"
        state.connection_state = "disconnected"
        state.machine_state = "disconnected"
        state.controller_enabled = True
        state.link_state = "PAIRING"
        self.transport.start()

    def add_observer(self, callback):
        self.observers.append(callback)

    def queue_command(self, command, kind="normal"):
        return False

    def discard_queued(self, kind):
        return None

    def queue_jog(self, axis, distance, feed, units="mm"):
        if (units != "mm" or not self.transport.paired or
                self.state.connection_state != "connected" or
                self.state.machine_state not in ("idle", "jog") or
                not getattr(self.state, "selectors_valid", True) or
                getattr(self.state, "input_valid", True) is not True or
                not self.state.deadman_enabled or self.state.estop_observed or
                self.state.estop_latched or self._pending_seq is not None or
                self._stop_pending):
            return False
        if axis not in ("X", "Y", "Z", "A") or not isinstance(distance, (float, int)):
            return False
        try:
            microns = round(float(distance) * 1000)
        except (ValueError, OverflowError, TypeError):
            return False
        if not isinstance(feed, (float, int)):
            return False
        try:
            feed_int = round(float(feed))
        except (ValueError, OverflowError, TypeError):
            return False
        if not (0 < abs(microns) <= 1000 and 0 < feed_int <= 1000):
            return False
        try:
            seq = self.transport.send_mpg_jog(axis, microns, feed_int, True)
        except (ValueError, OverflowError, OSError):
            self.cancel_jog()
            return False
        if seq is None:
            return False
        self._pending_seq = seq
        self._pending_at = self.clock()
        return True

    def cancel_jog(self):
        self._pending_seq = None
        self._pending_at = None
        self.state.jog_active = False
        if not self._stop_pending:
            self._stop_seq = None
            self._stop_at = None
            self._stop_attempts = 0
        self._stop_pending = True
        # Avoid flooding duplicate STOP packets if a radio read keeps failing
        # while the most recent STOP is still inside its ACK window.
        if (self._stop_at is not None and
                self.clock() - self._stop_at < 0.08):
            return True
        return self._send_stop()

    def _send_stop(self):
        if not self.transport.paired:
            return False
        # Count failed local sends as attempts too, and timestamp them before
        # calling the driver. Otherwise a persistent driver error can retry on
        # every cooperative poll and flood the radio/log stream.
        self._stop_attempts += 1
        self._stop_at = self.clock()
        self._stop_seq = None
        try:
            seq = self.transport.send_mpg_stop()
        except (OSError, RuntimeError):
            return False
        if seq is None:
            return False
        self._stop_seq = seq
        return True

    def realtime(self, name):
        if name in ("jog_cancel", "hold"):
            return self.cancel_jog()
        return False

    def _consume_uart(self, payload):
        # C3 UART_RESPONSE can split status lines at arbitrary byte boundaries.
        for byte in payload:
            if byte in (10, 13):
                if self._partial:
                    line = bytes(self._partial)
                    self._partial = bytearray()
                    if line.startswith(b"<") and line.endswith(b">"):
                        if self.parser.parse_line(line, self.clock()) == "status":
                            self._last_status = self.clock()
                            self._status_peer = self.transport.peer
                continue
            if len(self._partial) >= 127:
                self._partial = bytearray()
                continue
            self._partial.append(byte)

    def poll(self, now=None):
        current = self.clock() if now is None else now
        try:
            self.transport.poll()
        except (OSError, RuntimeError, ValueError):
            self.state.connection_state = "disconnected"
            self.state.link_state = "LINK_LOST" if self.transport.paired else "PAIRING"
            self.cancel_jog()
            return
        while self.transport.events:
            kind, seq, payload = self.transport.events.pop(0)
            if kind == proto.UART_RESPONSE:
                self._consume_uart(payload)
            elif kind == proto.MPG_JOG_ACK:
                if seq == self._pending_seq:
                    self._pending_seq = None
                    self._pending_at = None
                    if payload != b"\x01":
                        self.state.error = "C3 rejected jog"
                        self.state.jog_active = False
            elif kind == proto.MPG_STOP_ACK:
                if (seq == self._stop_seq and payload in
                        (bytes((proto.RESULT_OK,)),
                         bytes((proto.RESULT_STOP_SUPPRESSED,)))):
                    self._stop_pending = False
                    self._stop_seq = None
                    self._stop_at = None
        if self.transport.paired:
            self._had_pair = True
        fresh = (self._last_status is not None and
                 current - self._last_status <= 0.5)
        online = bool(fresh and self.transport.paired and
                      self._status_peer == self.transport.peer)
        # Keep machine readiness distinct from radio pairing. A paired radio
        # cannot imply GRBL is ready or authorize jogging.
        self.state.connection_state = "connected" if online else "disconnected"
        self.state.link_state = ("GRBL_FRESH" if online else
                                 "PAIRED_NO_GRBL" if self.transport.paired
                                 else "LINK_LOST" if self._had_pair
                                 else "PAIRING")
        if self._stop_pending:
            if not self.transport.paired:
                # A stop that could not be sent while disconnected remains
                # latched and is retried after pairing returns.
                self._stop_at = None
            elif self._stop_at is None or current - self._stop_at >= 0.08:
                if self._stop_attempts < 4:
                    self._send_stop()
                else:
                    # Do not silently rearm motion after a lost STOP ACK.
                    self.state.error = "C3 STOP acknowledgment missing"
        if self._pending_seq is not None and (
                self._pending_at is None or current - self._pending_at > 0.2):
            self.cancel_jog()
            self.state.error = "C3 jog acknowledgment timeout"
        if not online:
            self.state.machine_state = "disconnected"
            if self.state.jog_active:
                self.cancel_jog()

    def close(self):
        self.cancel_jog()
        self.transport.close()
