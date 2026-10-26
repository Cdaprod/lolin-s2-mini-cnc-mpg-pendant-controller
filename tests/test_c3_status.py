"""Regression tests for C3 bench controller. No CNC command may escape."""
import sys
import types
import unittest
from unittest.mock import patch

from src.controller.c3_status import C3StatusController
from src.state import PendantState


class Radio:
    enabled = True
    mac_address = bytes((1, 2, 3, 4, 5, 6))


class Esp:
    def __init__(self):
        self.active = False
        self.peers = []
        self.incoming = []
        self.sent = []

    def add_peer(self, mac):
        if mac not in self.peers:
            self.peers.append(mac)

    def read(self):
        return self.incoming.pop(0) if self.incoming else None

    def send(self, msg, peer=None):
        self.sent.append((peer, bytes(msg)))


class C3StatusTests(unittest.TestCase):
    def test_all_machine_actions_denied(self):
        state = PendantState()
        esp = Esp()
        espnow = types.ModuleType("espnow")
        espnow.Peer = lambda mac: types.SimpleNamespace(mac=bytes(mac))
        with patch.dict(sys.modules, {"espnow": espnow}):
            controller = C3StatusController(
                state, radio=Radio(), esp=esp, now=lambda: 0, session=42)
        self.assertFalse(controller.queue_jog("X", 1, 300))
        self.assertFalse(controller.queue_command("$H"))
        self.assertFalse(controller.realtime("hold"))
        self.assertTrue(controller.cancel_jog())
        controller.poll()
        self.assertEqual(state.connection_state, "disconnected")
        self.assertFalse(state.jog_active)
        self.assertEqual(len(controller.queue), 0)
        from src.transport import c3_espnow_protocol as proto
        self.assertEqual([proto.decode(frame)[0] for _, frame in esp.sent],
                         [proto.PAIR])


if __name__ == "__main__":
    unittest.main()
