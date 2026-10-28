"""C3 wireless controller integration tests with fake ESP-NOW hardware."""
import unittest

from src.controller.c3_wireless import C3WirelessController
from src.controller.actions import ActionDispatcher
from src.display.ui import ROTATE_CW, UIManager
from src.input.manager import InputManager, SyntheticInputAdapter
from src.safety.state_machine import SafetyStateMachine
from src.state import PendantState
from src.transport import c3_espnow_protocol as proto


class Radio:
    mac_address = bytes.fromhex("aabbccddeeff")
    enabled = True


class Peer:
    def __init__(self, mac):
        self.mac = mac


class Esp:
    def __init__(self):
        self.active = False
        self.sent = []
        self.peers = []
    def register_peer(self, mac):
        peer = Peer(mac)
        self.peers.append(peer)
        return peer
    def send(self, packet, peer):
        self.sent.append((packet, peer.mac if peer else None))
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
        self.ctrl.transport.unicast_peer = self.esp.register_peer(self.ctrl.transport.peer)
        self.ctrl.transport.last_rx = 100.0

    def status(self, line):
        self.ctrl.transport.events.append(
            (proto.UART_RESPONSE, 0, line.encode("ascii") + b"\n"))
        self.ctrl.poll()

    def test_display_reports_pairing_radio_and_grbl_independently(self):
        from src.display.round_ui.renderer import RoundRenderer
        from src.display.ui import UIManager
        from tests.test_round_ui import Display, scene_factory
        ui = UIManager(self.state)
        ui.complete_boot()
        renderer = RoundRenderer(Display(), scene_factory)
        renderer.bind_ui(ui)
        self.ctrl.transport.paired = False
        self.ctrl.poll()
        renderer.render(self.state)
        self.assertEqual(renderer.state_label.value, "ESP-NOW PAIRING")
        self.ctrl.transport.paired = True
        self.ctrl.poll()
        renderer.render(self.state)
        self.assertEqual(renderer.state_label.value, "ESP-NOW LINKED")
        self.assertEqual(renderer.motion.text.value, "GRBL OFFLINE")
        self.assertEqual(self.state.connection_state, "disconnected")
        self.status("<Idle|MPos:0,0,0|FS:0,0>")
        renderer.render(self.state)
        self.assertEqual(self.state.link_state, "GRBL_FRESH")
        self.assertEqual(renderer.state_label.value, "ESP-NOW LINKED")
        self.time[0] += .51
        self.ctrl.poll()
        renderer.render(self.state)
        self.assertEqual(renderer.motion.text.value, "GRBL OFFLINE")
        self.assertEqual(self.state.connection_state, "disconnected")
        self.ctrl.transport.paired = False
        self.ctrl.poll()
        renderer.render(self.state)
        self.assertEqual(renderer.state_label.value, "ESP-NOW LOST")

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

    def test_deadman_rejection_and_fourth_axis_a_packet(self):
        self.status("<Idle|MPos:0,0,0|FS:0,0>")
        self.assertFalse(self.ctrl.queue_jog("X", .01, 200))
        self.state.deadman_enabled = True
        self.state.selectors_valid = False
        self.assertFalse(self.ctrl.queue_jog("A", .01, 200))
        self.state.selectors_valid = True
        self.assertTrue(self.ctrl.queue_jog("A", .01, 200))
        frame, _peer = self.esp.sent[-1]
        kind, _session, _seq, payload = proto.decode(frame)
        self.assertEqual(kind, proto.MPG_JOG)
        self.assertEqual(payload[0], ord("A"))
        self.ctrl._pending_seq = None  # test fixture: no physical ACK expected
        self.assertFalse(self.ctrl.queue_jog("B", .01, 200))
        self.assertFalse(self.ctrl.queue_jog("X", 2, 200))

    def test_physical_input_pipeline_emits_exact_fourth_axis_frame(self):
        self.state.connection_state = "connected"
        self.state.machine_state = "idle"
        adapter = SyntheticInputAdapter()
        inputs = InputManager(self.state, adapter, counts_per_detent=4)
        ui = UIManager(self.state)
        ui.complete_boot()
        actions = ActionDispatcher(
            self.state, self.ctrl, SafetyStateMachine(self.state),
            jog_feed=500)

        adapter.set(axes=("X",), multipliers=("X1",), deadman=True,
                    mpg_delta=0)
        inputs.poll(0)
        ui.apply_selector_context()
        ui.refresh_context()
        adapter.set(axes=("4",), multipliers=("X10",), deadman=True,
                    mpg_delta=0)
        transition = inputs.poll(1)
        self.assertEqual(transition.events, [])
        ui.apply_selector_context()
        ui.refresh_context()

        adapter.set(mpg_delta=4)
        detent = inputs.poll(2)
        self.assertEqual(detent.events, [ROTATE_CW])
        command = ui.handle(detent.events[0])
        self.assertEqual(command.name, "JOG")
        self.assertTrue(actions.jog(command.value))

        frame, peer = self.esp.sent[-1]
        self.assertEqual(peer, self.ctrl.transport.peer)
        self.assertEqual(frame, bytes.fromhex(
            "01307b0000000000080041010a000000f401"))


if __name__ == "__main__":
    unittest.main()
