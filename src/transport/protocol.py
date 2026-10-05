"""Bounded framed protocol and reliable session for pendant byte transports."""

PROTOCOL_VERSION = 1
MAX_PAYLOAD = 256
ACK_TIMEOUT_MS = 150
MAX_RETRIES = 3
HEARTBEAT_INTERVAL_MS = 500
LINK_LOST_TIMEOUT_MS = 2000
MOTION_PACKET_TTL_MS = 250

SOF = 0xA5
EOF = 0x5A
DATA = 1
ACK = 2
NAK = 3
HEARTBEAT = 4
CONTROL = 5

SAFETY = 1
MOTION = 2
COMMAND = 3
STATUS = 4
CONFIG = 5
FILE = 6

RELIABLE = 0x01
HEADER_SIZE = 12
FRAME_OVERHEAD = HEADER_SIZE + 4


def crc16(data):
    """CRC-16/CCITT-FALSE (poly 0x1021, init 0xffff)."""
    crc = 0xFFFF
    for value in data:
        crc ^= value << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


class Packet:
    def __init__(self, packet_type, sequence_id=0, payload=b"", message_class=CONTROL,
                 reliable=False, sent_ms=0):
        self.packet_type = int(packet_type)
        self.sequence_id = int(sequence_id) & 0xFFFF
        self.payload = bytes(payload)
        self.message_class = int(message_class)
        self.reliable = bool(reliable)
        self.sent_ms = int(sent_ms) & 0xFFFFFFFF


def encode(packet):
    if len(packet.payload) > MAX_PAYLOAD:
        raise ValueError("payload exceeds MAX_PAYLOAD")
    length = len(packet.payload)
    header = bytes((PROTOCOL_VERSION, packet.packet_type,
                    packet.sequence_id >> 8, packet.sequence_id & 0xFF,
                    packet.message_class, RELIABLE if packet.reliable else 0,
                    length >> 8, length & 0xFF,
                    (packet.sent_ms >> 24) & 0xFF, (packet.sent_ms >> 16) & 0xFF,
                    (packet.sent_ms >> 8) & 0xFF, packet.sent_ms & 0xFF))
    protected = header + packet.payload
    check = crc16(protected)
    return bytes((SOF,)) + protected + bytes((check >> 8, check & 0xFF, EOF))


class FrameParser:
    """Allocation-bounded parser that resynchronizes at every candidate SOF."""
    def __init__(self, max_payload=MAX_PAYLOAD):
        self.max_payload = int(max_payload)
        self.buffer = bytearray()
        self.crc_failures = 0
        self.malformed = 0
        self.rejected_sequences = []

    def feed(self, data):
        packets = []
        for value in data or b"":
            if not self.buffer:
                if value == SOF:
                    self.buffer.append(value)
                continue
            self.buffer.append(value)
            if len(self.buffer) == 1 + HEADER_SIZE:
                length = (self.buffer[7] << 8) | self.buffer[8]
                if length > self.max_payload:
                    self.malformed += 1
                    self.buffer = bytearray((SOF,)) if value == SOF else bytearray()
                    continue
            if len(self.buffer) < 1 + HEADER_SIZE:
                continue
            length = (self.buffer[7] << 8) | self.buffer[8]
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
            if packet_type not in (DATA, ACK, NAK, HEARTBEAT, CONTROL):
                self.malformed += 1
                self._reject(raw)
                continue
            sent = (raw[9] << 24) | (raw[10] << 16) | (raw[11] << 8) | raw[12]
            packets.append(Packet(packet_type, (raw[3] << 8) | raw[4],
                                  raw[13:13 + length], raw[5],
                                  bool(raw[6] & RELIABLE), sent))
        # Recovery may leave an entire nested frame buffered when a damaged
        # length swallowed the next SOF. Process it without waiting for bytes.
        if len(self.buffer) >= 1 + HEADER_SIZE:
            length = (self.buffer[7] << 8) | self.buffer[8]
            if length <= self.max_payload and len(self.buffer) >= FRAME_OVERHEAD + length:
                pending = bytes(self.buffer)
                self.buffer = bytearray()
                packets.extend(self.feed(pending))
        return packets

    def _reject(self, raw):
        if len(raw) >= 5 and raw[2] in (DATA, CONTROL):
            self.rejected_sequences.append((raw[3] << 8) | raw[4])

    def _recover(self, raw):
        try:
            index = raw.index(SOF)
        except ValueError:
            return
        tail = bytes(raw[index:])
        self.buffer = bytearray()
        # A complete valid frame in the tail will be consumed by the next feed;
        # retain it without ever growing beyond the maximum frame size.
        if len(tail) <= FRAME_OVERHEAD + self.max_payload:
            self.buffer.extend(tail)


class Diagnostics:
    def __init__(self):
        for name in ("crc_failures", "malformed_packets", "ack_timeouts",
                     "nak_count", "retransmissions", "duplicate_packets",
                     "packets_sent", "packets_received", "retry_exhaustion"):
            setattr(self, name, 0)
        self.last_valid_packet_ms = None
        self.heartbeat_age_ms = None


class ReliableSession:
    """Single-flight reliable channel suitable for constrained runtimes."""
    def __init__(self, transport, handler, clock, ack_timeout_ms=ACK_TIMEOUT_MS,
                 max_retries=MAX_RETRIES, heartbeat_interval_ms=HEARTBEAT_INTERVAL_MS,
                 link_lost_timeout_ms=LINK_LOST_TIMEOUT_MS,
                 motion_ttl_ms=MOTION_PACKET_TTL_MS, on_link_lost=None, state=None):
        self.transport, self.handler, self.clock = transport, handler, clock
        self.ack_timeout_ms, self.max_retries = int(ack_timeout_ms), int(max_retries)
        self.heartbeat_interval_ms = int(heartbeat_interval_ms)
        self.link_lost_timeout_ms, self.motion_ttl_ms = int(link_lost_timeout_ms), int(motion_ttl_ms)
        self.on_link_lost, self.state = on_link_lost, state
        self.parser, self.diagnostics = FrameParser(), Diagnostics()
        self.next_sequence, self.outstanding = 0, None
        self.last_accepted_sequence = None
        self.last_receive_ms = None
        self.last_heartbeat_ms = None
        self.link_state = "DISCONNECTED"
        self._forced_lost = False

    def _now(self):
        return int(self.clock() * 1000)

    def send(self, payload, message_class=COMMAND, reliable=True):
        if reliable and self.outstanding is not None:
            return False
        now = self._now()
        packet = Packet(DATA, self.next_sequence, payload, message_class, reliable, now)
        frame = encode(packet)
        self.transport.write(frame)
        self.diagnostics.packets_sent += 1
        self.next_sequence = (self.next_sequence + 1) & 0xFFFF
        if reliable:
            self.outstanding = [packet, frame, now, 0]
        return True

    def _reply(self, packet_type, sequence):
        self.transport.write(encode(Packet(packet_type, sequence, sent_ms=self._now())))
        self.diagnostics.packets_sent += 1

    def poll(self):
        now = self._now()
        while True:
            chunk = self.transport.read(64)
            if not chunk:
                break
            before_crc, before_bad = self.parser.crc_failures, self.parser.malformed
            packets = self.parser.feed(chunk)
            self.diagnostics.crc_failures += self.parser.crc_failures - before_crc
            self.diagnostics.malformed_packets += self.parser.malformed - before_bad
            while self.parser.rejected_sequences:
                self._reply(NAK, self.parser.rejected_sequences.pop(0))
            for packet in packets:
                self._receive(packet, now)
        if self.outstanding and now - self.outstanding[2] >= self.ack_timeout_ms:
            self.diagnostics.ack_timeouts += 1
            self._retry(now)
        if self.last_heartbeat_ms is None or now - self.last_heartbeat_ms >= self.heartbeat_interval_ms:
            self.transport.write(encode(Packet(HEARTBEAT, sent_ms=now)))
            self.diagnostics.packets_sent += 1
            self.last_heartbeat_ms = now
        prior = self.link_state
        if self._forced_lost:
            self.link_state = "LOST"
        elif self.last_receive_ms is None:
            self.link_state = "CONNECTING" if self.transport.connected else "DISCONNECTED"
        else:
            age = now - self.last_receive_ms
            self.diagnostics.heartbeat_age_ms = age
            self.link_state = "LOST" if age >= self.link_lost_timeout_ms else "DEGRADED" if age >= self.heartbeat_interval_ms * 2 else "HEALTHY"
        if self.link_state == "LOST" and prior != "LOST" and self.on_link_lost:
            self.on_link_lost()
        self._publish()

    def _receive(self, packet, now):
        self.diagnostics.packets_received += 1
        self.diagnostics.last_valid_packet_ms = now
        self.last_receive_ms = now
        self._forced_lost = False
        if packet.packet_type == ACK:
            if self.outstanding and packet.sequence_id == self.outstanding[0].sequence_id:
                self.outstanding = None
            return
        if packet.packet_type == NAK:
            self.diagnostics.nak_count += 1
            if self.outstanding and packet.sequence_id == self.outstanding[0].sequence_id:
                self._retry(now)
            return
        if packet.packet_type == HEARTBEAT:
            return
        if packet.packet_type not in (DATA, CONTROL):
            return
        if packet.reliable and self.last_accepted_sequence is not None and not self._is_new(packet.sequence_id):
            self.diagnostics.duplicate_packets += 1
            self._reply(ACK, packet.sequence_id)
            return
        age = (now - packet.sent_ms) & 0xFFFFFFFF
        if packet.message_class == MOTION and age > self.motion_ttl_ms:
            self._reply(NAK, packet.sequence_id)
            return
        accepted = self.handler(packet)
        if accepted is False:
            self._reply(NAK, packet.sequence_id)
            return
        if packet.reliable:
            self.last_accepted_sequence = packet.sequence_id
            self._reply(ACK, packet.sequence_id)

    def _is_new(self, sequence):
        """Use half-range serial arithmetic to reject duplicates and old data."""
        delta = (sequence - self.last_accepted_sequence) & 0xFFFF
        return 0 < delta < 0x8000

    def _retry(self, now):
        if not self.outstanding:
            return
        if self.outstanding[3] >= self.max_retries:
            self.diagnostics.retry_exhaustion += 1
            self.outstanding = None
            self.link_state = "LOST"
            self._forced_lost = True
            if self.on_link_lost:
                self.on_link_lost()
            return
        self.transport.write(self.outstanding[1])
        self.outstanding[2], self.outstanding[3] = now, self.outstanding[3] + 1
        self.diagnostics.retransmissions += 1
        self.diagnostics.packets_sent += 1

    def _publish(self):
        if self.state is not None:
            self.state.link_state = self.link_state
            self.state.link_diagnostics = self.diagnostics
