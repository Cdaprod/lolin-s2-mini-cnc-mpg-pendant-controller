"""Session-scoped reliable packets and receiver-local CNC motion leases."""

import os

PROTOCOL_VERSION = 1
MAX_PAYLOAD = 256
ACK_TIMEOUT_MS = 150
MAX_RETRIES = 3
HEARTBEAT_INTERVAL_MS = 500
LINK_LOST_TIMEOUT_MS = 2000
MOTION_LEASE_MS = 300
MOTION_RENEW_INTERVAL_MS = 100

SOF = 0xA5
EOF = 0x5A
DATA = 1
ACK = 2
NAK = 3
HEARTBEAT = 4
CONTROL = 5
SESSION_INIT = 6
SESSION_CHALLENGE = 7
SESSION_CONFIRM = 8

SAFETY = 1
MOTION = 2
COMMAND = 3
STATUS = 4
CONFIG = 5
FILE = 6

RELIABLE = 0x01
MOTION_START = 0x02
MOTION_RENEW = 0x04
MOTION_STOP = 0x08
MOTION_FLAGS = MOTION_START | MOTION_RENEW | MOTION_STOP

# version(1), type(1), source session(8), peer session(8), sequence(2),
# class(1), flags(1), payload length(2)
HEADER_SIZE = 24
FRAME_OVERHEAD = HEADER_SIZE + 4


def crc16(data):
    """Return CRC-16/CCITT-FALSE (poly 0x1021, init 0xffff)."""
    crc = 0xFFFF
    for value in data:
        crc ^= value << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def _u64(value):
    return int(value).to_bytes(8, "big")


def _read_u64(data):
    return int.from_bytes(data, "big")


def generate_session_id():
    """Generate a nonzero stale-incarnation nonce; this is not authentication."""
    value = _read_u64(os.urandom(8))
    return value or 1


class Packet:
    def __init__(self, packet_type, sequence_id=0, payload=b"",
                 message_class=CONTROL, reliable=False, flags=0,
                 session_id=0, peer_session_id=0):
        self.packet_type = int(packet_type)
        self.session_id = int(session_id) & 0xFFFFFFFFFFFFFFFF
        self.peer_session_id = int(peer_session_id) & 0xFFFFFFFFFFFFFFFF
        self.sequence_id = int(sequence_id) & 0xFFFF
        self.payload = bytes(payload)
        self.message_class = int(message_class)
        self.flags = int(flags) | (RELIABLE if reliable else 0)
        self.reliable = bool(self.flags & RELIABLE)


def encode(packet):
    if len(packet.payload) > MAX_PAYLOAD:
        raise ValueError("payload exceeds MAX_PAYLOAD")
    length = len(packet.payload)
    header = (bytes((PROTOCOL_VERSION, packet.packet_type)) +
              _u64(packet.session_id) + _u64(packet.peer_session_id) +
              bytes((packet.sequence_id >> 8, packet.sequence_id & 0xFF,
                     packet.message_class, packet.flags,
                     length >> 8, length & 0xFF)))
    protected = header + packet.payload
    check = crc16(protected)
    return bytes((SOF,)) + protected + bytes((check >> 8, check & 0xFF, EOF))


class FrameParser:
    """Allocation-bounded parser that resynchronizes at candidate SOF bytes."""
    def __init__(self, max_payload=MAX_PAYLOAD):
        self.max_payload = int(max_payload)
        self.buffer = bytearray()
        self.crc_failures = 0
        self.malformed = 0
        self.rejected = []

    def feed(self, data):
        packets = []
        for value in data or b"":
            if not self.buffer:
                if value == SOF:
                    self.buffer.append(value)
                continue
            self.buffer.append(value)
            if len(self.buffer) == 1 + HEADER_SIZE:
                length = (self.buffer[23] << 8) | self.buffer[24]
                if length > self.max_payload:
                    self.malformed += 1
                    self.buffer = bytearray((SOF,)) if value == SOF else bytearray()
                    continue
            if len(self.buffer) < 1 + HEADER_SIZE:
                continue
            length = (self.buffer[23] << 8) | self.buffer[24]
            expected = FRAME_OVERHEAD + length
            if len(self.buffer) < expected:
                continue
            raw = self.buffer
            self.buffer = bytearray()
            if raw[-1] != EOF or raw[1] != PROTOCOL_VERSION:
                self.malformed += 1
                self._reject(raw)
                self._recover(raw[1:])
                continue
            protected = raw[1:1 + HEADER_SIZE + length]
            actual = (raw[-3] << 8) | raw[-2]
            if crc16(protected) != actual:
                self.crc_failures += 1
                self._reject(raw)
                self._recover(raw[1:])
                continue
            packet_type = raw[2]
            if packet_type not in (DATA, ACK, NAK, HEARTBEAT, CONTROL,
                                    SESSION_INIT, SESSION_CHALLENGE,
                                    SESSION_CONFIRM):
                self.malformed += 1
                self._reject(raw)
                continue
            packets.append(Packet(
                packet_type, (raw[19] << 8) | raw[20],
                raw[25:25 + length], raw[21], flags=raw[22],
                session_id=_read_u64(raw[3:11]),
                peer_session_id=_read_u64(raw[11:19])))
        if len(self.buffer) >= 1 + HEADER_SIZE:
            length = (self.buffer[23] << 8) | self.buffer[24]
            if (length <= self.max_payload and
                    len(self.buffer) >= FRAME_OVERHEAD + length):
                pending = bytes(self.buffer)
                self.buffer = bytearray()
                packets.extend(self.feed(pending))
        return packets

    def _reject(self, raw):
        if len(raw) >= 21 and raw[2] in (DATA, CONTROL):
            self.rejected.append((_read_u64(raw[3:11]),
                                  _read_u64(raw[11:19]),
                                  (raw[19] << 8) | raw[20]))

    def _recover(self, raw):
        try:
            index = raw.index(SOF)
        except ValueError:
            return
        tail = bytes(raw[index:])
        self.buffer = bytearray()
        if len(tail) <= FRAME_OVERHEAD + self.max_payload:
            self.buffer.extend(tail)


class Diagnostics:
    def __init__(self):
        for name in ("crc_failures", "malformed_packets", "ack_timeouts",
                     "nak_count", "retransmissions", "duplicate_packets",
                     "packets_sent", "packets_received", "retry_exhaustion",
                     "session_establishments", "session_resets",
                     "rejected_old_session", "rejected_stale_ack",
                     "lease_renewals", "lease_expirations",
                     "rejected_renewals", "link_loss_events"):
            setattr(self, name, 0)
        self.last_valid_packet_ms = None
        self.heartbeat_age_ms = None
        self.active_session = None


class ReliableSession:
    """Role-based handshake, reliable delivery, and local motion watchdog."""
    def __init__(self, transport, handler, clock, role="initiator",
                 session_id=None, nonce_factory=generate_session_id,
                 ack_timeout_ms=ACK_TIMEOUT_MS, max_retries=MAX_RETRIES,
                 heartbeat_interval_ms=HEARTBEAT_INTERVAL_MS,
                 link_lost_timeout_ms=LINK_LOST_TIMEOUT_MS,
                 motion_lease_ms=MOTION_LEASE_MS,
                 motion_renew_interval_ms=MOTION_RENEW_INTERVAL_MS,
                 on_link_lost=None, on_motion_stop=None, state=None):
        if role not in ("initiator", "responder"):
            raise ValueError("role must be initiator or responder")
        self.transport, self.handler, self.clock = transport, handler, clock
        self.role, self.nonce_factory = role, nonce_factory
        self.local_session = int(nonce_factory() if session_id is None else
                                 session_id)
        if not self.local_session:
            raise ValueError("session_id must be nonzero")
        self.remote_session = None
        self.established = False
        self.ack_timeout_ms, self.max_retries = int(ack_timeout_ms), int(max_retries)
        self.heartbeat_interval_ms = int(heartbeat_interval_ms)
        self.link_lost_timeout_ms = int(link_lost_timeout_ms)
        self.motion_lease_ms = int(motion_lease_ms)
        self.motion_renew_interval_ms = int(motion_renew_interval_ms)
        self.on_link_lost, self.on_motion_stop = on_link_lost, on_motion_stop
        self.state = state
        self.parser, self.diagnostics = FrameParser(), Diagnostics()
        self.next_sequence, self.outstanding = 0, None
        self.last_accepted_sequence = None
        self.last_receive_ms = None
        self.last_transmit_ms = None
        self.link_state = "DISCONNECTED"
        self.motion_active = False
        self.motion_intent_sequence = None
        self.motion_lease_deadline = None

    def _now(self):
        return int(self.clock() * 1000)

    def _packet(self, packet_type, sequence=0, payload=b"",
                message_class=CONTROL, flags=0):
        return Packet(packet_type, sequence, payload, message_class,
                      flags=flags, session_id=self.local_session,
                      peer_session_id=self.remote_session or 0)

    def _write(self, packet):
        frame = encode(packet)
        self.transport.write(frame)
        self.diagnostics.packets_sent += 1
        self.last_transmit_ms = self._now()
        return frame

    def send(self, payload, message_class=COMMAND, reliable=True, flags=0):
        if not self.established or (reliable and self.outstanding is not None):
            return False
        sequence = self.next_sequence
        packet = self._packet(DATA, sequence, payload, message_class,
                              flags | (RELIABLE if reliable else 0))
        frame = self._write(packet)
        self.next_sequence = (sequence + 1) & 0xFFFF
        if reliable:
            now = self._now()
            self.outstanding = [packet, frame, now, 0, now]
        return True

    def send_motion_start(self, payload=b""):
        if not self.send(payload, MOTION, True, MOTION_START):
            return False
        self.motion_intent_sequence = self.outstanding[0].sequence_id
        return True

    def send_motion_renew(self, payload=b""):
        if self.motion_intent_sequence is None:
            return False
        intent = bytes((self.motion_intent_sequence >> 8,
                        self.motion_intent_sequence & 0xFF))
        return self.send(intent + bytes(payload), MOTION, True, MOTION_RENEW)

    def send_motion_stop(self, payload=b""):
        if self.motion_intent_sequence is None:
            return False
        intent = bytes((self.motion_intent_sequence >> 8,
                        self.motion_intent_sequence & 0xFF))
        sent = self.send(intent + bytes(payload), MOTION, True, MOTION_STOP)
        if sent:
            self.motion_intent_sequence = None
        return sent

    def poll(self):
        now = self._now()
        self._check_motion_lease(now)
        while True:
            chunk = self.transport.read(64)
            if not chunk:
                break
            before_crc = self.parser.crc_failures
            before_bad = self.parser.malformed
            packets = self.parser.feed(chunk)
            self.diagnostics.crc_failures += self.parser.crc_failures - before_crc
            self.diagnostics.malformed_packets += self.parser.malformed - before_bad
            while self.parser.rejected:
                source, peer, sequence = self.parser.rejected.pop(0)
                if self._matches_active(source, peer):
                    self._reply(NAK, sequence)
            for packet in packets:
                self._receive(packet, now)
        self._check_motion_lease(now)
        if self.outstanding and now - self.outstanding[2] >= self.ack_timeout_ms:
            self.diagnostics.ack_timeouts += 1
            self._retry(now)
        if self.established:
            if (self.last_transmit_ms is None or
                    now - self.last_transmit_ms >= self.heartbeat_interval_ms):
                self._write(self._packet(HEARTBEAT))
        elif self.role == "initiator" and (
                self.last_transmit_ms is None or
                now - self.last_transmit_ms >= self.heartbeat_interval_ms):
            self._write(Packet(SESSION_INIT, session_id=self.local_session))
        self._update_link(now)
        self._publish()

    def _receive(self, packet, now):
        self.diagnostics.packets_received += 1
        if packet.packet_type in (SESSION_INIT, SESSION_CHALLENGE,
                                  SESSION_CONFIRM):
            self._receive_handshake(packet, now)
            return
        if not self._matches_active(packet.session_id, packet.peer_session_id):
            self.diagnostics.rejected_old_session += 1
            if packet.packet_type in (ACK, NAK):
                self.diagnostics.rejected_stale_ack += 1
            return
        self.last_receive_ms = now
        self.diagnostics.last_valid_packet_ms = now
        if packet.packet_type == ACK:
            if (self.outstanding and
                    packet.sequence_id == self.outstanding[0].sequence_id):
                self.outstanding = None
            return
        if packet.packet_type == NAK:
            self.diagnostics.nak_count += 1
            if (self.outstanding and
                    packet.sequence_id == self.outstanding[0].sequence_id):
                self._retry(now)
            return
        if packet.packet_type == HEARTBEAT:
            return
        if packet.packet_type not in (DATA, CONTROL):
            return
        if (packet.reliable and self.last_accepted_sequence is not None and
                not self._is_new(packet.sequence_id)):
            self.diagnostics.duplicate_packets += 1
            self._reply(ACK, packet.sequence_id)
            return
        if packet.message_class == MOTION:
            accepted = self._receive_motion(packet, now)
        else:
            accepted = self.handler(packet)
        if accepted is False:
            self._reply(NAK, packet.sequence_id)
            return
        if packet.reliable:
            self.last_accepted_sequence = packet.sequence_id
            self._reply(ACK, packet.sequence_id)

    def _receive_handshake(self, packet, now):
        if self.role == "responder" and packet.packet_type == SESSION_INIT:
            if not packet.session_id or packet.peer_session_id:
                self.diagnostics.rejected_old_session += 1
                return
            if self.established and packet.session_id != self.remote_session:
                self.diagnostics.rejected_old_session += 1
                return
            if not self.established and packet.session_id != self.remote_session:
                self._reset_generation(rotate_local=self.remote_session is not None)
                self.remote_session = packet.session_id
            if packet.session_id == self.remote_session:
                self._write(self._packet(SESSION_CHALLENGE))
            return
        if self.role == "initiator" and packet.packet_type == SESSION_CHALLENGE:
            if (not packet.session_id or
                    packet.peer_session_id != self.local_session):
                self.diagnostics.rejected_old_session += 1
                return
            if self.established and packet.session_id != self.remote_session:
                self.diagnostics.rejected_old_session += 1
                return
            self.remote_session = packet.session_id
            self._write(self._packet(SESSION_CONFIRM))
            self._establish(now)
            return
        if self.role == "responder" and packet.packet_type == SESSION_CONFIRM:
            if (packet.session_id == self.remote_session and
                    packet.peer_session_id == self.local_session):
                self._establish(now)
            else:
                self.diagnostics.rejected_old_session += 1

    def _establish(self, now):
        if not self.established:
            self.established = True
            self.last_accepted_sequence = None
            self.last_receive_ms = now
            self.diagnostics.session_establishments += 1
            self.diagnostics.active_session = (self.local_session,
                                               self.remote_session)

    def _matches_active(self, source, peer):
        return (self.established and source == self.remote_session and
                peer == self.local_session)

    def _reply(self, packet_type, sequence):
        self._write(self._packet(packet_type, sequence))

    def _receive_motion(self, packet, now):
        if not packet.reliable:
            self.diagnostics.rejected_renewals += 1
            return False
        action = packet.flags & MOTION_FLAGS
        if action == MOTION_START:
            accepted = self.handler(packet)
            if accepted is False:
                return False
            self.motion_active = True
            self.motion_intent_sequence = packet.sequence_id
            self.motion_lease_deadline = now + self.motion_lease_ms
            return True
        if action in (MOTION_RENEW, MOTION_STOP):
            if len(packet.payload) < 2:
                self.diagnostics.rejected_renewals += 1
                return False
            intent = (packet.payload[0] << 8) | packet.payload[1]
            if intent != self.motion_intent_sequence:
                self.diagnostics.rejected_renewals += 1
                return False
            if action == MOTION_RENEW:
                if (not self.motion_active or self.motion_lease_deadline is None or
                        now >= self.motion_lease_deadline):
                    self.diagnostics.rejected_renewals += 1
                    return False
                self.motion_lease_deadline = now + self.motion_lease_ms
                self.diagnostics.lease_renewals += 1
                return True
            accepted = self.handler(packet)
            if accepted is False:
                return False
            self._stop_motion()
            return True
        self.diagnostics.rejected_renewals += 1
        return False

    def _check_motion_lease(self, now):
        if (self.motion_active and self.motion_lease_deadline is not None and
                now >= self.motion_lease_deadline):
            self.diagnostics.lease_expirations += 1
            self._stop_motion()

    def _stop_motion(self):
        was_active = self.motion_active
        self.motion_active = False
        self.motion_intent_sequence = None
        self.motion_lease_deadline = None
        if was_active and self.on_motion_stop:
            self.on_motion_stop()

    def _is_new(self, sequence):
        delta = (sequence - self.last_accepted_sequence) & 0xFFFF
        return 0 < delta < 0x8000

    def _retry(self, now):
        if not self.outstanding:
            return
        if self.outstanding[3] >= self.max_retries:
            self.diagnostics.retry_exhaustion += 1
            self.outstanding = None
            self._lose_session()
            return
        self.transport.write(self.outstanding[1])
        self.outstanding[2] = now
        self.outstanding[3] += 1
        self.diagnostics.retransmissions += 1
        self.diagnostics.packets_sent += 1

    def _update_link(self, now):
        prior = self.link_state
        if not self.transport.connected:
            self.link_state = "DISCONNECTED"
            if self.established:
                self._lose_session()
        elif not self.established:
            if prior != "LOST":
                self.link_state = "SESSION_NEGOTIATING"
        else:
            age = now - self.last_receive_ms
            self.diagnostics.heartbeat_age_ms = age
            if age >= self.link_lost_timeout_ms:
                self.link_state = "LOST"
                self._lose_session()
            elif age >= self.heartbeat_interval_ms * 2:
                self.link_state = "DEGRADED"
            else:
                self.link_state = "HEALTHY"
        if self.link_state == "LOST" and prior != "LOST":
            self.diagnostics.link_loss_events += 1
            if self.on_link_lost:
                self.on_link_lost()

    def _lose_session(self):
        if self.established or self.remote_session is not None:
            self.diagnostics.session_resets += 1
        self._stop_motion()
        self.established = False
        self.remote_session = None
        self.outstanding = None
        self.last_accepted_sequence = None
        self.motion_intent_sequence = None
        # A fresh local contribution makes replay of a buffered handshake from
        # the preceding connection generation insufficient to re-establish it.
        self.local_session = int(self.nonce_factory()) or 1
        self.diagnostics.active_session = None

    def _reset_generation(self, rotate_local=False):
        self._stop_motion()
        self.established = False
        self.outstanding = None
        self.last_accepted_sequence = None
        self.motion_intent_sequence = None
        if rotate_local:
            self.local_session = int(self.nonce_factory()) or 1
        self.diagnostics.session_resets += 1
        self.diagnostics.active_session = None

    def _publish(self):
        if self.state is not None:
            self.state.link_state = self.link_state
            self.state.link_diagnostics = self.diagnostics
