"""C3 wireless controller integration tests with fake ESP-NOW hardware."""
import unittest

from src.controller.c3_wireless import C3WirelessController
from src.state import PendantState
from src.transport import c3_espnow_protocol as proto


class Radio:
    mac_address = bytes.fromhex("aabbccddeeff")
    enabled = True


class Esp:
    def __init__(self):
        self.active = False
        self.sent = []
        self.peers = []
    def add_peer(self, peer):
        self.peers.append(peer)
    def send(self, packet, peer):
        self.sent.append((packet, peer))
    def read(self):
        return None


class WirelessTests(unittest.TestCase):
    def setUp(self):
        self.time = [100.0]
        self.esp = Esp()
        self.state = PendantState()
        self.ctrl = C3WirelessController(
            self.state, radio=Radio(), esp=self.esp, now=lambda: self.time[0],
            session=123)
        self.ctrl.transport.paired = True
        self.ctrl.transport.peer = bytes.fromhex("010203040506")
        self.ctrl.transport.last_rx = 100.0

    def status(self, line):
        self.ctrl.transport.events.append(
            (proto.UART_RESPONSE, 0, line.encode("ascii") + b"\n"))
        self.ctrl.poll()

    def test_no_motion_without_fresh_grbl_status(self):
        self.state.deadman_enabled = True
        self.assertFalse(self.ctrl.queue_jog("X", .01, 200))
        self.status("<Idle|MPos:1.000,2.000,3.000|FS:0,0>")
        self.assertEqual(self.state.machine_position["X"], 1.0)
        self.assertEqual(self.state.connection_state, "connected")
        self.assertTrue(self.ctrl.queue_jog("X", .01, 200))
        frame, peer = self.esp.sent[-1]
        kind, session, seq, payload = proto.decode(frame)
        self.assertEqual(kind, proto.MPG_JOG)
        self.assertEqual((session, peer), (123, self.ctrl.transport.peer))
        self.assertEqual(payload, bytes.fromhex("58010a000000c800"))
        self.assertFalse(self.ctrl.queue_jog("X", .01, 200))
        self.ctrl.transport.events.append((proto.MPG_JOG_ACK, seq, b"\x01"))
        self.ctrl.poll()
        self.time[0] += .51
        self.ctrl.poll()
        self.assertEqual(self.state.connection_state, "disconnected")
        self.assertFalse(self.ctrl.queue_jog("X", .01, 200))

    def test_negative_ack_and_expiring_ack(self):
        self.state.deadman_enabled = True
        self.status("<Idle|MPos:0,0,0|FS:0,0>")
        self.assertTrue(self.ctrl.queue_jog("Z", -.1, 100))
        seq = self.ctrl._pending_seq
        self.ctrl.transport.events.append((proto.MPG_JOG_ACK, seq, b"\x00"))
        self.ctrl.poll()
        self.assertEqual(self.state.error, "C3 rejected jog")
        self.assertTrue(self.ctrl.queue_jog("Z", -.1, 100))
        self.time[0] += .21
        self.ctrl.poll()
        self.assertEqual(self.state.error, "C3 jog acknowledgment timeout")
        self.assertIn(proto.MPG_STOP, [
            proto.decode(pkt)[0] for pkt, peer in self.esp.sent])

    def test_stop_ack_matching_retry_and_latched_inhibition(self):
        self.state.deadman_enabled = True
        self.status("<Idle|MPos:0,0,0|FS:0,0>")
        self.assertTrue(self.ctrl.cancel_jog())
        seq = self.ctrl._stop_seq
        self.ctrl.transport.events.append(
            (proto.MPG_STOP_ACK, (seq + 1) & 65535, b"\x01"))
        self.ctrl.poll()
        self.assertTrue(self.ctrl._stop_pending)
        self.time[0] += 0.09
        self.ctrl.poll()
        self.assertNotEqual(self.ctrl._stop_seq, seq)
        self.assertFalse(self.ctrl.queue_jog("X", 0.01, 200))
        self.ctrl.transport.events.append(
            (proto.MPG_STOP_ACK, self.ctrl._stop_seq, b"\x01"))
        self.ctrl.poll()
        self.assertFalse(self.ctrl._stop_pending)
        self.assertTrue(self.ctrl.queue_jog("X", 0.01, 200))

    def test_deadman_and_axis_rejected(self):
        self.status("<Idle|MPos:0,0,0|FS:0,0>")
        self.assertFalse(self.ctrl.queue_jog("X", .01, 200))
        self.state.deadman_enabled = True
        self.assertFalse(self.ctrl.queue_jog("A", .01, 200))
        self.assertFalse(self.ctrl.queue_jog("X", 2, 200))


if __name__ == "__main__":
    unittest.main()
