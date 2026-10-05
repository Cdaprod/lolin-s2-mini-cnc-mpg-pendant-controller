"""Fault-oriented tests for the bounded controller transport protocol."""

import pytest

from src.transport.mock import MockTransport
from src.transport.protocol import (ACK, DATA, MOTION, FrameParser, Packet,
                                    ReliableSession, encode, MAX_PAYLOAD)


class Clock:
    def __init__(self):
        self.value = 1.0

    def __call__(self):
        return self.value

    def advance(self, milliseconds):
        self.value += milliseconds / 1000


def deliver(source, destination, mutate=None):
    frames = source.writes[:]
    source.writes[:] = []
    for frame in frames:
        destination.inject_bytes(mutate(frame) if mutate else frame)


def sessions(**kwargs):
    clock = Clock()
    left, right = MockTransport(), MockTransport()
    received = []
    sender = ReliableSession(left, lambda packet: True, clock, **kwargs)
    receiver = ReliableSession(right, lambda packet: received.append(packet.payload), clock,
                               **kwargs)
    return clock, left, right, sender, receiver, received


def test_data_ack_and_duplicate_ack_without_redispatch():
    clock, left, right, sender, receiver, received = sessions()
    assert sender.send(b"cycle-start")
    original = left.writes[-1]
    deliver(left, right)
    receiver.poll()
    assert received == [b"cycle-start"]
    deliver(right, left)
    sender.poll()
    assert sender.outstanding is None
    right.inject_bytes(original)
    receiver.poll()
    assert received == [b"cycle-start"]
    assert receiver.diagnostics.duplicate_packets == 1
    parsed = FrameParser().feed(right.writes[-1])
    assert parsed[0].packet_type == ACK


def test_corrupt_data_never_dispatches_and_next_frame_recovers():
    clock, left, right, sender, receiver, received = sessions()
    corrupt = bytearray(encode(Packet(DATA, 2, b"danger", reliable=True, sent_ms=1000)))
    corrupt[14] ^= 0x40
    valid = encode(Packet(DATA, 3, b"safe", reliable=True, sent_ms=1000))
    right.inject_bytes(b"garbage" + corrupt + valid)
    receiver.poll()
    assert received == [b"safe"]
    assert receiver.diagnostics.crc_failures == 1


def test_damaged_length_that_swallows_following_frame_resynchronizes():
    parser = FrameParser()
    damaged = bytearray(encode(Packet(DATA, 1, b"bad")))
    damaged[7], damaged[8] = 0, 19  # consume the following 16-byte frame
    following = encode(Packet(DATA, 2, b"ok"))
    packets = parser.feed(damaged + following)
    assert [packet.payload for packet in packets] == [b"ok"]


def test_nak_and_timeout_retransmit_identical_frame():
    clock, left, right, sender, receiver, received = sessions(ack_timeout_ms=10)
    sender.send(b"x")
    original = left.writes[-1]
    left.inject_bytes(encode(Packet(3, 0)))
    sender.poll()
    assert original in left.writes[1:]
    clock.advance(11)
    sender.poll()
    assert left.writes.count(original) == 3
    assert sender.diagnostics.retransmissions == 2


def test_retries_are_bounded_and_loss_callback_stops_motion():
    stopped = []
    clock = Clock()
    transport = MockTransport()
    session = ReliableSession(transport, lambda packet: True, clock,
                              ack_timeout_ms=10, max_retries=2,
                              on_link_lost=lambda: stopped.append(True))
    session.send(b"jog", MOTION)
    for _ in range(3):
        clock.advance(11)
        session.poll()
    assert session.outstanding is None
    assert session.diagnostics.retransmissions == 2
    assert session.diagnostics.retry_exhaustion == 1
    assert stopped == [True]


def test_stale_motion_is_naked_and_not_dispatched():
    clock, left, right, sender, receiver, received = sessions(motion_ttl_ms=20)
    right.inject_bytes(encode(Packet(DATA, 8, b"jog", MOTION, True, sent_ms=900)))
    receiver.poll()
    assert received == []
    assert FrameParser().feed(right.writes[0])[0].packet_type == 3


def test_parser_rejects_oversize_and_truncation_with_bounded_storage():
    parser = FrameParser()
    parser.feed(bytes((0xA5, 1, 1, 0, 0, 3, 1, 0xFF, 0xFF, 0, 0, 0, 0)))
    assert parser.malformed == 1
    assert len(parser.buffer) <= MAX_PAYLOAD + 16
    half = encode(Packet(DATA, 1, b"partial"))[:-3]
    assert parser.feed(half) == []


def test_link_health_loss_and_recovery_without_reboot():
    clock, left, right, sender, receiver, received = sessions(
        heartbeat_interval_ms=10, link_lost_timeout_ms=30)
    right.inject_bytes(encode(Packet(4, sent_ms=1000)))
    receiver.poll()
    assert receiver.link_state == "HEALTHY"
    clock.advance(31)
    receiver.poll()
    assert receiver.link_state == "LOST"
    right.inject_bytes(encode(Packet(4, sent_ms=1031)))
    receiver.poll()
    assert receiver.link_state == "HEALTHY"


def test_sequence_rollover_and_payload_limit():
    clock, left, right, sender, receiver, received = sessions()
    sender.next_sequence = 0xFFFF
    sender.send(b"last")
    assert sender.next_sequence == 0
    with pytest.raises(ValueError):
        encode(Packet(DATA, payload=b"x" * (MAX_PAYLOAD + 1)))
