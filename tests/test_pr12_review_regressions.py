"""Regression tests for the five PR #12 Codex review findings."""

from host_bridge.adapters import GrblAdapter
from host_bridge.model import MachineState
from src.app import PendantApplication
from src.controller.bridge import BridgeController
from src.display.console import ConsoleDisplay
from src.transport.mock import MockTransport
from src.transport.protocol import (ReliableSession, SOF, Packet, encode,
                                    DATA, MOTION, MOTION_RENEW, RELIABLE)


class Clock:
    def __init__(self, value=1.0):
        self.value = float(value)

    def __call__(self):
        return self.value

    def advance(self, ms):
        self.value += ms / 1000.0


def test_application_constructs_real_protocol_initiator():
    transport = MockTransport()
    app = PendantApplication.from_config(
        {"controller_mode": "bridge"}, transport=transport,
        clock=Clock(), display=ConsoleDisplay(lambda value: None))
    assert isinstance(app.controller, BridgeController)
    assert app.controller.session.role == "initiator"
    assert not app.controller.motion_enabled
    app.poll()
    assert transport.writes
    assert transport.writes[0][0] == SOF
    assert b"?" not in transport.writes
    assert not app.controller.queue_command("G0 X20")
    assert not app.controller.queue_jog("X", 0.1, 500)


def test_session_receive_draining_is_bounded_and_expires_motion():
    clock = Clock()

    class EndlessNoise(MockTransport):
        def __init__(self):
            super().__init__()
            self.read_count = 0

        def read(self, count=64):
            self.read_count += 1
            clock.advance(11)
            return b"\x00" * count

    transport = EndlessNoise()
    stops = []
    session = ReliableSession(
        transport, lambda packet: True, clock, role="responder",
        session_id=100, on_motion_stop=lambda: stops.append(True))
    session.established = True
    session.remote_session = 200
    session.last_receive_ms = 1000
    session.motion_active = True
    session.motion_intent_sequence = 0
    session.motion_lease_deadline = 1010
    session.poll()
    assert transport.read_count <= 16
    assert not session.motion_active
    assert session.diagnostics.lease_expirations == 1
    assert stops == [True]


def test_failed_grbl_cancel_is_retried_when_transport_recovers():
    class FailOnce(MockTransport):
        def __init__(self):
            super().__init__()
            self.fail_cancel = True

        def write(self, data):
            if data == b"\x85" and self.fail_cancel:
                self.fail_cancel = False
                raise OSError("temporary serial backpressure")
            return super().write(data)

    transport = FailOnce()
    adapter = GrblAdapter(transport)
    adapter._active_jog = ("X", 1, 100.0)
    adapter._cancel_pending = True
    adapter._cancel_sent = False
    assert not adapter.stop_jog()
    assert adapter._cancel_pending
    assert not adapter.start_jog("X", 1, 100.0)
    adapter.poll()
    assert transport.writes.count(b"\x85") == 1
    assert adapter._cancel_sent
    assert not adapter._cancel_pending
    adapter.stop_jog()
    assert transport.writes.count(b"\x85") == 1


def test_malformed_mpos_does_not_partially_publish_valid_wpos():
    adapter = GrblAdapter(MockTransport())
    adapter.state.machine_position["X"] = 12.0
    adapter.state.work_position["X"] = 9.0
    adapter.state.feed_rate = 30.0
    adapter._parse_line("<Idle|MPos:bad,2,3|WPos:7,8,9|FS:10,20>", 2.0)
    assert adapter.state.machine_position["X"] == 12.0
    assert adapter.state.work_position["X"] == 9.0
    assert adapter.state.feed_rate == 30.0
    assert adapter._last_status_at is None


def test_invalid_wco_also_rejects_status_atomically():
    adapter = GrblAdapter(MockTransport())
    adapter._parse_line("<Idle|MPos:1,2,3|WCO:broken|FS:10,20>", 2.0)
    assert adapter._last_status_at is None
    assert adapter.state.machine_position["X"] is None


def test_status_payload_remains_ascii_and_field_bounded():
    state = MachineState()
    state.mode = "idle\ufffd|jog"
    state.alarm = "ALARM:\ufffd|\x00bad"
    payload = state.status_payload()
    assert payload.isascii()
    fields = payload.decode("ascii").split("|")
    assert len(fields) == 13
    assert "\ufffd" not in fields[1]
    assert "\ufffd" not in fields[11]


def test_renewal_arriving_after_deadline_during_read_is_rejected():
    clock = Clock()

    class DelayedRenewal(MockTransport):
        def read(self, count=64):
            clock.advance(11)
            return super().read(count)

    transport = DelayedRenewal()
    stops = []
    session = ReliableSession(
        transport, lambda packet: True, clock, role="responder",
        session_id=100, on_motion_stop=lambda: stops.append("stop"))
    session.established = True
    session.remote_session = 200
    session.last_receive_ms = 1000
    session.motion_active = True
    session.motion_intent_sequence = 5
    session.motion_lease_deadline = 1010
    renewal = Packet(DATA, 6, b"\x00\x05", MOTION,
                     flags=RELIABLE | MOTION_RENEW,
                     session_id=200, peer_session_id=100)
    transport.inject_bytes(encode(renewal))
    session.poll()
    assert stops == ["stop"]
    assert not session.motion_active
    assert session.diagnostics.rejected_renewals == 1
