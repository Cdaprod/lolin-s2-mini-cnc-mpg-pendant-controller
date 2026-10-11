"""Tests for the universal host bridge and controller adapters."""

from host_bridge.adapters import GrblAdapter, MockControllerAdapter
from host_bridge.bridge import HostBridge
from host_bridge.model import MachineState
from src.transport.mock import MockGRBLTransport, MockTransport
from src.transport.protocol import ReliableSession, STATUS


class Clock:
    def __init__(self):
        self.value = 1.0

    def __call__(self):
        return self.value

    def advance(self, milliseconds):
        self.value += milliseconds / 1000


def move(source, destination):
    frames = source.writes[:]
    source.writes[:] = []
    for frame in frames:
        destination.inject_bytes(frame)


def connected_bridge(motion_enabled=False):
    clock = Clock()
    pendant_transport = MockTransport()
    host_transport = MockTransport()
    telemetry = []
    pendant = ReliableSession(
        pendant_transport, lambda packet: telemetry.append(packet), clock,
        role="initiator", session_id=0x1010,
        heartbeat_interval_ms=10, link_lost_timeout_ms=100)
    adapter = MockControllerAdapter(motion_enabled=motion_enabled)
    bridge = HostBridge(host_transport, adapter, clock, session_id=0x2020,
                        status_interval_ms=10)
    pendant.poll()
    move(pendant_transport, host_transport)
    bridge.poll()
    move(host_transport, pendant_transport)
    pendant.poll()
    move(pendant_transport, host_transport)
    bridge.poll()
    pendant_transport.writes[:] = []
    host_transport.writes[:] = []
    telemetry[:] = []
    return clock, pendant_transport, host_transport, pendant, bridge, telemetry


def exchange(pendant_transport, host_transport, pendant, bridge):
    move(pendant_transport, host_transport)
    bridge.poll()
    move(host_transport, pendant_transport)
    pendant.poll()


def test_machine_state_payload_is_normalized_and_bounded():
    state = MachineState()
    state.connected = True
    state.mode = "idle"
    state.work_position["X"] = 12.5
    state.feed_rate = 100
    payload = state.status_payload()
    assert payload.startswith(b"STATE|idle|1|12.5000|")
    assert len(payload) < 256


def test_motion_is_disabled_by_default_and_state_does_not_optimistically_move():
    _, pt, ht, pendant, bridge, _ = connected_bridge()
    assert pendant.send_motion_start(b"JOG|X|1|500")
    exchange(pt, ht, pendant, bridge)
    assert bridge.adapter.events == []
    assert bridge.state.mode == "idle"
    assert not bridge.session.motion_active


def test_enabled_mock_motion_executes_once_and_lease_expiry_stops_it():
    clock, pt, ht, pendant, bridge, _ = connected_bridge(motion_enabled=True)
    bridge.session.motion_lease_ms = 30
    assert pendant.send_motion_start(b"JOG|X|1|500")
    original = pt.writes[-1]
    move(pt, ht)
    bridge.poll()
    assert bridge.adapter.events == [("jog_start", "X", 1, 500.0)]
    ht.writes[:] = []  # lose ACK and force identical retransmission
    ht.inject_bytes(original)
    bridge.poll()
    assert bridge.adapter.events == [("jog_start", "X", 1, 500.0)]
    clock.advance(30)
    bridge.poll()
    assert bridge.adapter.events[-1] == ("jog_stop",)
    assert bridge.state.mode == "idle"


def test_explicit_stop_routes_through_lease_owner_immediately():
    _, pt, ht, pendant, bridge, _ = connected_bridge(motion_enabled=True)
    pendant.send_motion_start(b"JOG|Y|-1|250")
    exchange(pt, ht, pendant, bridge)
    assert pendant.send_motion_stop()
    exchange(pt, ht, pendant, bridge)
    assert bridge.adapter.events == [
        ("jog_start", "Y", -1, 250.0), ("jog_stop",)]
    assert not bridge.session.motion_active


def test_bridge_publishes_controller_reported_telemetry_upstream():
    clock, pt, ht, pendant, bridge, telemetry = connected_bridge()
    bridge.adapter.state.work_position["X"] = 7.25
    clock.advance(10)
    bridge.poll()
    move(ht, pt)
    pendant.poll()
    status = [packet for packet in telemetry if packet.message_class == STATUS]
    assert status
    assert b"7.2500" in status[-1].payload


def test_grbl_adapter_parses_machine_state_and_keeps_motion_gated():
    transport = MockGRBLTransport(
        "<Idle|MPos:1,2,3|WPos:0.5,1.5,2.5|FS:123,456>")
    adapter = GrblAdapter(transport)
    transport.write(b"?")
    state = adapter.poll()
    assert state.connected
    assert state.mode == "idle"
    assert state.machine_position["X"] == 1.0
    assert state.work_position["Z"] == 2.5
    assert state.feed_rate == 123.0
    assert state.spindle_speed == 456.0
    writes = transport.writes[:]
    assert not adapter.start_jog("X", 1, 500)
    assert transport.writes == writes


def test_grbl_adapter_emits_controller_specific_cancel_on_lease_stop():
    transport = MockGRBLTransport()
    adapter = GrblAdapter(transport, motion_enabled=True)
    assert adapter.start_jog("X", 1, 500)
    assert transport.writes[-1].startswith(b"$J=G91")
    adapter.stop_jog()
    assert transport.writes[-1] == b"\x85"


def test_grbl_motion_commands_are_gated_but_hold_and_cancel_remain_available():
    transport = MockGRBLTransport()
    adapter = GrblAdapter(transport)
    before = transport.writes[:]
    assert adapter.command("HOME") is False
    assert adapter.command("RESUME") is False
    assert transport.writes == before
    assert adapter.command("HOLD")
    assert transport.writes[-1] == b"!"
    assert adapter.stop_jog()
    assert transport.writes[-1] == b"\x85"


def test_grbl_poll_requests_status_and_derives_work_coordinates():
    transport = MockGRBLTransport(
        "<Idle|MPos:10,20,30|WCO:1,2,3|FS:120,300>")
    adapter = GrblAdapter(transport)
    state = adapter.poll()
    assert b"?" in transport.writes
    assert state.work_position["X"] == 9.0
    assert state.work_position["Y"] == 18.0
    assert state.work_position["Z"] == 27.0
    assert state.feed_rate == 120.0
    assert state.spindle_speed == 300.0
    prior = transport.writes.count(b"?")
    adapter.poll()
    assert transport.writes.count(b"?") == prior


def test_grbl_rejects_nonfinite_jog_feed():
    transport = MockGRBLTransport()
    adapter = GrblAdapter(transport, motion_enabled=True)
    assert not adapter.start_jog("X", 1, float("nan"))
    assert not adapter.start_jog("X", 1, float("inf"))


def test_valid_renewal_emits_bounded_grbl_segment_and_stop_cancels():
    clock, pt, ht, pendant, bridge, _ = connected_bridge(motion_enabled=True)
    controller = MockGRBLTransport()
    grbl = GrblAdapter(controller, motion_enabled=True)
    bridge.adapter = grbl
    bridge.session.on_motion_stop = grbl.stop_jog
    bridge.session.on_motion_renew = grbl.renew_jog
    assert pendant.send_motion_start(b"JOG|X|1|500")
    exchange(pt, ht, pendant, bridge)
    commands = [w for w in controller.writes if w.startswith(b"$J=")]
    assert len(commands) == 1
    assert b"X0.5000" in commands[0]
    assert pendant.send_motion_renew()
    exchange(pt, ht, pendant, bridge)
    assert len([w for w in controller.writes if w.startswith(b"$J=")]) == 2
    assert bridge.session.diagnostics.lease_renewals == 1
    assert pendant.send_motion_stop()
    exchange(pt, ht, pendant, bridge)
    assert controller.writes[-1] == b"\x85"
    assert not bridge.session.motion_active
    before = len([w for w in controller.writes if w.startswith(b"$J=")])
    bridge.poll()
    assert len([w for w in controller.writes if w.startswith(b"$J=")]) == before


def test_expired_lease_cancels_grbl_and_never_queues_more_jogs():
    clock, pt, ht, pendant, bridge, _ = connected_bridge(motion_enabled=True)
    controller = MockGRBLTransport()
    grbl = GrblAdapter(controller, motion_enabled=True)
    bridge.adapter = grbl
    bridge.session.on_motion_stop = grbl.stop_jog
    bridge.session.on_motion_renew = grbl.renew_jog
    bridge.session.motion_lease_ms = 30
    assert pendant.send_motion_start(b"JOG|Y|-1|120")
    exchange(pt, ht, pendant, bridge)
    assert len([w for w in controller.writes if w.startswith(b"$J=")]) == 1
    clock.advance(31)
    bridge.poll()
    assert controller.writes[-1] == b"\x85"
    assert not bridge.session.motion_active
    assert not grbl.renew_jog()
    assert len([w for w in controller.writes if w.startswith(b"$J=")]) == 1
