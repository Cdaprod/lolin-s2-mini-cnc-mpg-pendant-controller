"""Wire codec for ennio64 ESP32-C3 bridge ESP-NOW protocol v1.

Source: include/espnow_protocol.h in ESP32-C3-Telnet-EspNow-Bridge-V1.3.1.
This is NOT the pendant's reliable Protocol v1 and does not authorize motion.
"""
VERSION = 1
HEADER_SIZE = 10
MAX_FRAME = 250
MAX_PAYLOAD = MAX_FRAME - HEADER_SIZE

PAIR = 0x01
PAIR_ACK = 0x02
HEARTBEAT = 0x03
HEARTBEAT_ACK = 0x04
SENSOR_ASSIGNMENT = 0x14
UART_COMMAND = 0x20
UART_ACK = 0x21
UART_RESPONSE = 0x22
MPG_JOG = 0x30
MPG_JOG_ACK = 0x31
MPG_STOP = 0x32
MPG_STOP_ACK = 0x33
ERROR = 0x7F

DEVICE_BRIDGE = 1
DEVICE_SENSOR = 2
DEVICE_PENDANT = 3


def _u16(raw, start):
    return raw[start] | (raw[start + 1] << 8)


def _u32(raw, start):
    return (raw[start] | (raw[start + 1] << 8) |
            (raw[start + 2] << 16) | (raw[start + 3] << 24))


def encode(msg_type, session, sequence=0, payload=b""):
    payload = bytes(payload)
    if len(payload) > MAX_PAYLOAD:
        raise ValueError("ESP-NOW payload too long")
    if not 0 <= msg_type <= 255:
        raise ValueError("invalid message type")
    if not 0 <= session <= 0xFFFFFFFF:
        raise ValueError("invalid session")
    if not 0 <= sequence <= 0xFFFF:
        raise ValueError("invalid sequence")
    size = len(payload)
    return bytes((
        VERSION, msg_type,
        session & 255, (session >> 8) & 255,
        (session >> 16) & 255, (session >> 24) & 255,
        sequence & 255, (sequence >> 8) & 255,
        size & 255, (size >> 8) & 255
    )) + payload


def decode(raw):
    """Strict length checks; return (type, session, seq, payload)."""
    raw = bytes(raw)
    if len(raw) < HEADER_SIZE or len(raw) > MAX_FRAME:
        raise ValueError("invalid ESP-NOW frame length")
    if raw[0] != VERSION:
        raise ValueError("unsupported ESP-NOW protocol version")
    length = _u16(raw, 8)
    if length > MAX_PAYLOAD or len(raw) != HEADER_SIZE + length:
        raise ValueError("invalid ESP-NOW payload length")
    return raw[1], _u32(raw, 2), _u16(raw, 6), raw[HEADER_SIZE:]


def validate_pair_ack(raw, expected_session, expected_mac=None):
    kind, session, seq, payload = decode(raw)
    if kind != PAIR_ACK or session != expected_session or len(payload) != 9:
        raise ValueError("PAIR_ACK does not match active session")
    if payload[0] != DEVICE_BRIDGE or payload[1] != VERSION:
        raise ValueError("PAIR_ACK device/version mismatch")
    if expected_mac is not None and payload[2:8] != bytes(expected_mac):
        raise ValueError("PAIR_ACK peer mismatch")
    return payload[2:8], payload[8]


def encode_mpg_jog(session, sequence, axis, distance_microns, feed_mm_min,
                   deadman):
    """Encode a bounded MPG request for the C3 admission/dry-run path.

    A successful encode or radio ACK does not authorize physical motion; the
    receiver's trusted-peer, session, sequence, controller-state, and motion
    admission checks remain authoritative.
    """
    if axis not in ("X", "Y", "Z", "A"):
        raise ValueError("invalid MPG axis")
    if not isinstance(distance_microns, int) or not (-1000 <= distance_microns <= 1000) or distance_microns == 0:
        raise ValueError("invalid MPG microns")
    if not isinstance(feed_mm_min, int) or not (1 <= feed_mm_min <= 1000):
        raise ValueError("invalid MPG feed")
    if type(deadman) is not bool:
        raise ValueError("deadman must be boolean")
    payload = (bytes((ord(axis), int(deadman))) +
               int(distance_microns).to_bytes(4, "little", signed=True) +
               int(feed_mm_min).to_bytes(2, "little"))
    return encode(MPG_JOG, session, sequence, payload)


def encode_mpg_stop(session, sequence):
    return encode(MPG_STOP, session, sequence)
