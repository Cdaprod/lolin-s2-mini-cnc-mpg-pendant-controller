"""Fault-injection and safety-invariant tests for the reliable protocol."""

import pytest

from src.transport.mock import MockTransport
from src.transport.protocol import (
    ACK, COMMAND, DATA, HEARTBEAT, MOTION, MOTION_RENEW, MOTION_START, MOTION_STOP,
    NAK, SESSION_INIT, FrameParser, Packet, ReliableSession, encode,
    FRAME_OVERHEAD, MAX_PAYLOAD,
)


class Clock:
    def __init__(self, seconds=1.0):
        self.value = float(seconds)

    def __call__(self):
        return self.value

    def advance(self, milliseconds):
        self.value += milliseconds / 1000


def move(source, destination, transform=None):
    frames = source.writes[:]
    source.writes[:] = []
    for frame in frames:
        result = transform(frame) if transform else frame
        if result is not None:
            destination.inject_bytes(result)
    return frames


def build_pair(client_clock=None, server_clock=None, lease=30, lost=100,
               client_nonce=0x1111, server_nonce=0x2222):
    client_clock = client_clock or Clock()
    server_clock = server_clock or Clock()
    client_transport, server_transport = MockTransport(), MockTransport()
    client_events, server_events, stops = [], [], []
    client = ReliableSession(
        client_transport, lambda packet: client_events.append(packet),
        client_clock, role="initiator", session_id=client_nonce,
        nonce_factory=lambda: client_nonce + 1, motion_lease_ms=lease,
        heartbeat_interval_ms=10, link_lost_timeout_ms=lost)
    server = ReliableSession(
        server_transport, lambda packet: server_events.append(packet),
        server_clock, role="responder", session_id=server_nonce,
        nonce_factory=lambda: server_nonce + 1, motion_lease_ms=lease,
        heartbeat_interval_ms=10, link_lost_timeout_ms=lost,
        on_motion_stop=lambda: stops.append("stop"))
    return (client_clock, server_clock, client_transport, server_transport,
            client, server, client_events, server_events, stops)


def negotiate(pair):
    _, _, ct, st, client, server, _, _, _ = pair
    client.poll()
    move(ct, st)
    server.poll()
    move(st, ct)
    client.poll()
    move(ct, st)
    server.poll()
    assert client.established and server.established
    ct.writes[:] = []
    st.writes[:] = []


def exchange(pair):
    _, _, ct, st, client, server, _, _, _ = pair
    move(ct, st)
    server.poll()
    move(st, ct)
    client.poll()


def test_handshake_required_and_heartbeats_do_not_authorize_motion():
    pair = build_pair()
    _, _, _, st, client, server, _, events, _ = pair
    assert client.link_state == "DISCONNECTED"
    assert not client.send_motion_start(b"jog")
    server._receive(Packet(HEARTBEAT, session_id=0x1111,
                           peer_session_id=0x2222), 1000)
    assert events == []
    assert not server.motion_active
    negotiate(pair)
    assert client.link_state in ("HEALTHY", "SESSION_NEGOTIATING")
    assert not server.motion_active


def test_zero_session_identity_is_rejected():
    with pytest.raises(ValueError):
        ReliableSession(MockTransport(), lambda packet: True, Clock(),
                        session_id=0)


def test_normal_data_ack_and_lost_ack_duplicate_executes_once():
    pair = build_pair()
    negotiate(pair)
    _, _, ct, st, client, server, _, events, _ = pair
    assert client.send(b"cycle-start")
    original = ct.writes[-1]
    move(ct, st)
    server.poll()
    assert [packet.payload for packet in events] == [b"cycle-start"]
    st.writes[:] = []  # lose ACK
    client.outstanding[2] -= client.ack_timeout_ms
    client.poll()
    assert original in ct.writes
    move(ct, st)
    server.poll()
    assert [packet.payload for packet in events] == [b"cycle-start"]
    assert server.diagnostics.duplicate_packets == 1


def test_nak_and_timeout_retransmit_identical_session_scoped_frame():
    pair = build_pair()
    negotiate(pair)
    _, _, ct, _, client, _, _, _, _ = pair
    client.send(b"x")
    original = ct.writes[-1]
    ct.inject_bytes(encode(Packet(
        NAK, 0, session_id=client.remote_session,
        peer_session_id=client.local_session)))
    client.poll()
    assert original in ct.writes[1:]
    client.outstanding[2] -= client.ack_timeout_ms
    client.poll()
    assert ct.writes.count(original) == 3


def test_ack_and_nak_from_old_session_cannot_change_outstanding():
    pair = build_pair()
    negotiate(pair)
    _, _, ct, _, client, _, _, _, _ = pair
    client.send(b"current")
    outstanding = client.outstanding
    for packet_type in (ACK, NAK):
        ct.inject_bytes(encode(Packet(
            packet_type, outstanding[0].sequence_id,
            session_id=0xDEAD, peer_session_id=client.local_session)))
        client.poll()
        assert client.outstanding is outstanding
    assert client.diagnostics.rejected_stale_ack == 2
    assert client.diagnostics.retransmissions == 0


def test_retry_exhaustion_invalidates_session_and_motion_authority():
    pair = build_pair()
    negotiate(pair)
    _, _, _, _, client, _, _, _, _ = pair
    client.send(b"command")
    for _ in range(client.max_retries + 1):
        client.outstanding[2] -= client.ack_timeout_ms
        client.poll()
    assert client.outstanding is None
    assert not client.established
    assert client.diagnostics.retry_exhaustion == 1


def test_receiver_local_lease_with_radically_different_clock_epochs():
    pair = build_pair(Clock(10800), Clock(4), lease=30)
    negotiate(pair)
    _, server_clock, _, _, client, server, _, events, stops = pair
    assert client.send_motion_start(b"jog-positive")
    exchange(pair)
    assert server.motion_active
    assert [packet.payload for packet in events] == [b"jog-positive"]
    server_clock.advance(29)
    server.poll()
    assert server.motion_active
    server_clock.advance(1)
    server.poll()
    assert not server.motion_active
    assert stops == ["stop"]


def test_renewal_extends_lease_without_redispatch_and_duplicate_is_harmless():
    pair = build_pair(lease=30)
    negotiate(pair)
    _, server_clock, ct, st, client, server, _, events, _ = pair
    client.send_motion_start(b"jog")
    exchange(pair)
    server_clock.advance(20)
    assert client.send_motion_renew()
    renewal = ct.writes[-1]
    move(ct, st)
    server.poll()
    deadline = server.motion_lease_deadline
    assert len(events) == 1
    st.writes[:] = []
    st.inject_bytes(renewal)
    server.poll()
    assert server.motion_lease_deadline == deadline
    assert len(events) == 1
    assert server.diagnostics.duplicate_packets == 1


def test_lost_stop_and_no_stop_both_expire_receiver_lease():
    for send_stop in (True, False):
        pair = build_pair(lease=30)
        negotiate(pair)
        _, server_clock, ct, _, client, server, _, _, stops = pair
        client.send_motion_start(b"jog")
        exchange(pair)
        if send_stop:
            assert client.send_motion_stop()
            ct.writes[:] = []  # STOP is lost
        server_clock.advance(30)
        server.poll()
        assert not server.motion_active
        assert stops == ["stop"]


def test_explicit_stop_is_immediate():
    pair = build_pair(lease=100)
    negotiate(pair)
    _, _, _, _, client, server, _, events, stops = pair
    client.send_motion_start(b"jog")
    exchange(pair)
    assert client.send_motion_stop()
    exchange(pair)
    assert not server.motion_active
    assert stops == ["stop"]
    assert events[-1].flags & MOTION_STOP


def test_lost_and_corrupt_renewals_do_not_extend_lease():
    pair = build_pair(lease=30)
    negotiate(pair)
    _, server_clock, ct, st, client, server, _, events, stops = pair
    client.send_motion_start(b"jog")
    exchange(pair)
    original_deadline = server.motion_lease_deadline
    server_clock.advance(20)
    client.send_motion_renew()
    renewal = bytearray(ct.writes.pop())
    renewal[-3] ^= 0x01
    st.inject_bytes(renewal)
    server.poll()
    assert server.motion_lease_deadline == original_deadline
    server_clock.advance(10)
    server.poll()
    assert not server.motion_active
    assert len(events) == 1
    assert stops == ["stop"]


def test_delayed_renewal_after_expiration_cannot_resurrect_motion():
    pair = build_pair(lease=20)
    negotiate(pair)
    _, server_clock, ct, st, client, server, _, _, stops = pair
    client.send_motion_start(b"jog")
    exchange(pair)
    client.send_motion_renew()
    delayed = ct.writes.pop()
    server_clock.advance(20)
    server.poll()
    st.inject_bytes(delayed)
    server.poll()
    assert not server.motion_active
    assert stops == ["stop"]
    assert server.diagnostics.rejected_renewals == 1


def test_malformed_renewal_does_not_affect_lease():
    pair = build_pair(lease=30)
    negotiate(pair)
    _, _, _, st, client, server, _, _, _ = pair
    client.send_motion_start(b"jog")
    exchange(pair)
    deadline = server.motion_lease_deadline
    malformed = Packet(DATA, 1, b"", MOTION, flags=1 | MOTION_RENEW,
                       session_id=client.local_session,
                       peer_session_id=server.local_session)
    st.inject_bytes(encode(malformed))
    server.poll()
    assert server.motion_lease_deadline == deadline
    assert server.diagnostics.rejected_renewals == 1


def test_unreliable_motion_is_never_authorized():
    pair = build_pair()
    negotiate(pair)
    _, _, _, st, client, server, _, events, _ = pair
    st.inject_bytes(encode(Packet(
        DATA, 0, b"jog", MOTION, flags=MOTION_START,
        session_id=client.local_session,
        peer_session_id=server.local_session)))
    server.poll()
    assert events == []
    assert not server.motion_active


def test_old_session_data_motion_ack_nak_are_rejected():
    pair = build_pair()
    negotiate(pair)
    _, _, ct, st, client, server, _, events, _ = pair
    old_source = client.local_session - 1
    for packet_type, message_class, flags in (
            (DATA, COMMAND, 1), (DATA, MOTION, 1 | MOTION_START),
            (ACK, COMMAND, 0), (NAK, COMMAND, 0)):
        st.inject_bytes(encode(Packet(
            packet_type, 7, b"old", message_class, flags=flags,
            session_id=old_source, peer_session_id=server.local_session)))
    server.poll()
    assert events == []
    assert not server.motion_active
    assert server.diagnostics.rejected_old_session == 4


def test_old_session_init_cannot_replace_established_session():
    pair = build_pair()
    negotiate(pair)
    _, _, _, st, _, server, _, _, _ = pair
    active = server.diagnostics.active_session
    st.inject_bytes(encode(Packet(SESSION_INIT, session_id=0x9999)))
    server.poll()
    assert server.established
    assert server.diagnostics.active_session == active
    assert server.diagnostics.rejected_old_session == 1


def test_pendant_reboot_during_jog_requires_fresh_session_and_intent():
    pair = build_pair(lease=20)
    negotiate(pair)
    _, server_clock, _, st, client, server, _, events, stops = pair
    old_motion = None
    client.send_motion_start(b"old-jog")
    old_motion = client.transport.writes[-1]
    exchange(pair)
    reboot_transport = MockTransport()
    rebooted = ReliableSession(reboot_transport, lambda packet: None, Clock(0),
                               role="initiator", session_id=0x3333)
    server_clock.advance(100)
    server.poll()
    st.inject_bytes(old_motion)
    server.poll()
    assert not server.motion_active
    assert stops == ["stop"]
    assert [packet.payload for packet in events] == [b"old-jog"]
    assert not rebooted.send_motion_start(b"new-jog")
    rebooted.poll()
    move(reboot_transport, st)
    server.poll()
    move(st, reboot_transport)
    rebooted.poll()
    move(reboot_transport, st)
    server.poll()
    assert rebooted.established and server.established
    assert not server.motion_active


def test_companion_reboot_starts_safe_and_rejects_buffered_old_motion():
    pair = build_pair(lease=50)
    negotiate(pair)
    _, _, ct, _, client, _, _, _, _ = pair
    client.send_motion_start(b"old-jog")
    old_motion = ct.writes[-1]
    fresh_transport = MockTransport()
    fresh_events = []
    fresh = ReliableSession(fresh_transport,
                            lambda packet: fresh_events.append(packet), Clock(0),
                            role="responder", session_id=0x4444)
    fresh_transport.inject_bytes(old_motion)
    fresh.poll()
    assert not fresh.established
    assert not fresh.motion_active
    assert fresh_events == []
    # The old client must time out, rotate its contribution, and negotiate;
    # neither heartbeat nor handshake recreates the preceding motion intent.
    client.clock.advance(client.link_lost_timeout_ms)
    client.poll()
    client.clock.advance(client.heartbeat_interval_ms)
    client.poll()
    move(ct, fresh_transport)
    fresh.poll()
    move(fresh_transport, ct)
    client.poll()
    move(ct, fresh_transport)
    fresh.poll()
    assert client.established and fresh.established
    assert not fresh.motion_active and fresh_events == []


def test_both_endpoint_reboot_has_no_motion_or_session_continuity():
    old = build_pair()
    negotiate(old)
    old[4].send_motion_start(b"jog")
    exchange(old)
    fresh = build_pair(client_nonce=0xAAAA, server_nonce=0xBBBB)
    assert not fresh[4].established and not fresh[5].established
    assert not fresh[5].motion_active
    negotiate(fresh)
    assert fresh[4].established and fresh[5].established
    assert not fresh[5].motion_active


def test_session_change_discards_outstanding_and_stale_ack_cannot_complete_it():
    pair = build_pair()
    negotiate(pair)
    _, _, ct, _, client, _, _, _, _ = pair
    client.send(b"pending")
    old_packet = client.outstanding[0]
    client._lose_session()
    assert client.outstanding is None
    ct.inject_bytes(encode(Packet(
        ACK, old_packet.sequence_id, session_id=old_packet.peer_session_id,
        peer_session_id=old_packet.session_id)))
    client.poll()
    assert client.outstanding is None
    assert not client.established


def test_sequence_rollover_within_one_session_is_forward_progress():
    pair = build_pair()
    negotiate(pair)
    _, _, _, st, client, server, _, events, _ = pair
    server.last_accepted_sequence = 65533
    for sequence in (65534, 65535, 0, 1):
        st.inject_bytes(encode(Packet(
            DATA, sequence, bytes((sequence & 0xFF,)), COMMAND, reliable=True,
            session_id=client.local_session,
            peer_session_id=server.local_session)))
        server.poll()
    assert len(events) == 4
    assert server.last_accepted_sequence == 1


def test_link_loss_during_motion_stops_no_later_than_local_lease():
    pair = build_pair(lease=20, lost=100)
    negotiate(pair)
    _, server_clock, _, _, client, server, _, _, stops = pair
    client.send_motion_start(b"jog")
    exchange(pair)
    server_clock.advance(20)
    server.poll()
    assert not server.motion_active
    assert stops == ["stop"]
    assert server.established  # lease is independent and shorter than link loss


def test_link_loss_recovery_never_replays_motion():
    pair = build_pair(lease=20, lost=30)
    negotiate(pair)
    _, server_clock, _, _, client, server, _, events, stops = pair
    client.send_motion_start(b"jog")
    exchange(pair)
    server_clock.advance(31)
    server.poll()
    assert not server.established and not server.motion_active
    assert stops == ["stop"]
    assert len(events) == 1


def test_crc_invalid_motion_never_dispatches_or_extends_lease():
    pair = build_pair(lease=30)
    negotiate(pair)
    _, _, _, st, client, server, _, events, _ = pair
    frame = bytearray(encode(Packet(
        DATA, 0, b"jog", MOTION, flags=1 | MOTION_START,
        session_id=client.local_session,
        peer_session_id=server.local_session)))
    frame[26] ^= 0x20
    st.inject_bytes(frame)
    server.poll()
    assert events == []
    assert not server.motion_active
    assert server.diagnostics.crc_failures == 1


def test_garbage_corruption_and_damaged_length_recover_current_session_frame():
    parser = FrameParser()
    bad = bytearray(encode(Packet(DATA, 1, b"bad", session_id=1)))
    good = encode(Packet(DATA, 2, b"good", session_id=1))
    bad[23], bad[24] = 0, len(bad) + len(good) - FRAME_OVERHEAD
    packets = parser.feed(b"garbage" + bad + good)
    assert [packet.payload for packet in packets] == [b"good"]


def test_oversized_and_truncated_frames_are_bounded_and_recoverable():
    parser = FrameParser()
    prefix = bytearray(1 + 24)
    prefix[0], prefix[1], prefix[2] = 0xA5, 1, DATA
    prefix[23], prefix[24] = 0xFF, 0xFF
    parser.feed(prefix)
    assert parser.malformed == 1
    assert len(parser.buffer) <= MAX_PAYLOAD + FRAME_OVERHEAD
    partial = encode(Packet(DATA, payload=b"partial"))[:-3]
    assert parser.feed(partial) == []
    assert len(parser.buffer) <= MAX_PAYLOAD + FRAME_OVERHEAD
    with pytest.raises(ValueError):
        encode(Packet(DATA, payload=b"x" * (MAX_PAYLOAD + 1)))
