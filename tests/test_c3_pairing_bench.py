"""Deterministic tests for C3 radio-level pairing with machine TX forbidden."""
import unittest
import contextlib
import io
from src.transport.c3_pairing_bench import C3PairingBench, BROADCAST
from src.transport import c3_espnow_protocol as proto


class Radio:
    enabled = True
    mac_address = bytes.fromhex("010203040506")


class Packet:
    def __init__(self, mac, msg):
        self.mac, self.msg = mac, msg


class Peer:
    def __init__(self, mac):
        self.mac = mac


class Esp:
    def __init__(self):
        self.active = False
        self.peers = []
        self.incoming = []
        self.sent = []

    def register_peer(self, mac):
        peer = Peer(mac)
        self.peers.append(peer)
        return peer

    def read(self):
        return self.incoming.pop(0) if self.incoming else None

    def send(self, msg, peer=None):
        self.sent.append((peer.mac if peer else None, msg))


class PairTests(unittest.TestCase):
    def test_pair_and_heartbeat_no_uart(self):
        esp, t = Esp(), [0]
        client = C3PairingBench(Radio(), now=lambda: t[0], esp=esp, session=7)
        client.start()
        client.poll()
        self.assertEqual(esp.sent[0][0], BROADCAST)
        self.assertEqual(proto.decode(esp.sent[0][1])[0], proto.PAIR)
        self.assertEqual(client.info()["tx_pair_requests"], 1)
        self.assertEqual(proto.decode(esp.sent[0][1])[3], Radio.mac_address)
        bridge = bytes.fromhex("aabbccddeeff")
        ack = proto.encode(proto.PAIR_ACK, 7, payload=bytes((1, 1)) +
                           Radio.mac_address + bytes((255,)))
        esp.incoming.append(Packet(bridge, ack))
        t[0] = 1
        client.poll()
        self.assertTrue(client.paired)
        self.assertEqual(client.peer, bridge)
        self.assertEqual(proto.decode(esp.sent[-1][1])[0], proto.HEARTBEAT)
        self.assertEqual(client.info()["tx_heartbeats"], 1)
        for _peer, raw in esp.sent:
            self.assertNotEqual(proto.decode(raw)[0], proto.UART_COMMAND)
        t[0] = 7
        client.poll()
        self.assertFalse(client.paired)
        self.assertFalse(client.info()["motion_enabled"])

    def test_packet_diagnostics_include_session_sequence_and_peer(self):
        esp = Esp()
        client = C3PairingBench(Radio(), now=lambda: 12.5, esp=esp, session=7)
        client.start()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            client.poll()
        self.assertIn("event=espnow_tx packet_type=pair session=7 seq=0", output.getvalue())
        self.assertIn("peer=ff:ff:ff:ff:ff:ff result=driver_accepted_not_ota_ack uptime_ms=12500", output.getvalue())

    def test_pair_accepts_c3_sensor_assignment(self):
        esp, t = Esp(), [0]
        client = C3PairingBench(Radio(), now=lambda: t[0], esp=esp, session=7)
        client.start()
        client.poll()
        bridge = bytes.fromhex("aabbccddeeff")
        ack = proto.encode(proto.PAIR_ACK, 7, payload=bytes((1, 1)) +
                           Radio.mac_address + bytes((255,)))
        assignment = proto.encode(proto.SENSOR_ASSIGNMENT, 7, payload=b"\xff")
        esp.incoming.extend((Packet(bridge, ack), Packet(bridge, assignment)))

        t[0] = 1
        client.poll()

        self.assertTrue(client.paired)
        self.assertEqual(client.info()["assigned_function"], 255)
        self.assertEqual(client.info()["rejected_packets"], 0)
        self.assertEqual(client.info()["valid_packets"], 2)

    def test_repair_to_new_peer_drops_queued_old_peer_ack(self):
        esp = Esp()
        client = C3PairingBench(Radio(), now=lambda: 1, esp=esp, session=7)
        client.start()
        first = bytes.fromhex("aabbccddeeff")
        second = bytes.fromhex("112233445566")
        pair_ack = lambda: proto.encode(
            proto.PAIR_ACK, 7, payload=bytes((1, 1)) +
            Radio.mac_address + bytes((255,)))
        esp.incoming.append(Packet(first, pair_ack()))
        client.poll()
        self.assertEqual(client.peer, first)

        # Both frames are read in one transport poll. The first ACK was valid
        # when received, but its sequence belongs to the old peer.
        esp.incoming.extend((
            Packet(first, proto.encode(proto.MPG_STOP_ACK, 7, sequence=42,
                                       payload=b"\x01")),
            Packet(second, pair_ack()),
        ))
        client.poll()

        self.assertEqual(client.peer, second)
        self.assertEqual(client.events, [])

    def test_heartbeat_timeout_discards_queued_peer_events(self):
        esp, t = Esp(), [0]
        client = C3PairingBench(Radio(), now=lambda: t[0], esp=esp, session=7)
        client.start()
        peer = bytes.fromhex("aabbccddeeff")
        ack = proto.encode(proto.PAIR_ACK, 7, payload=bytes((1, 1)) +
                           Radio.mac_address + bytes((255,)))
        esp.incoming.append(Packet(peer, ack))
        client.poll()
        client.events.append((proto.MPG_STOP_ACK, 4, b"\x01"))

        t[0] = 6
        client.poll()

        self.assertFalse(client.paired)
        self.assertEqual(client.events, [])

    def test_repeated_timeout_does_not_leak_registered_peers(self):
        esp, t = Esp(), [0]
        client = C3PairingBench(Radio(), now=lambda: t[0], esp=esp, session=7)
        client.start()
        bridge = bytes.fromhex("aabbccddeeff")
        ack = proto.encode(proto.PAIR_ACK, 7, payload=bytes((1, 1)) +
                           Radio.mac_address + bytes((255,)))
        for cycle in range(4):
            esp.incoming.append(Packet(bridge, ack))
            client.poll()
            self.assertTrue(client.paired)
            self.assertEqual(len(esp.peers), 2)
            t[0] += 6
            client.poll()
            self.assertFalse(client.paired)
            self.assertEqual(len(esp.peers), 2)
            t[0] += 1

    def test_mismatched_ack_session_diagnostics(self):
        esp = Esp()
        client = C3PairingBench(Radio(), now=lambda: 0, esp=esp, session=7)
        client.start()
        bridge = bytes.fromhex("aabbccddeeff")
        ack = proto.encode(proto.PAIR_ACK, 8, payload=bytes((1, 1)) +
                           Radio.mac_address + bytes((255,)))
        esp.incoming.append(Packet(bridge, ack))
        client.poll()
        self.assertFalse(client.paired)
        self.assertEqual(client.info()["pair_ack_session_mismatch"], 1)
        self.assertEqual(client.info()["last_pair_ack_sender"], "aa:bb:cc:dd:ee:ff")

    def test_spoofed_pair_ack_wrong_mac_rejected(self):
        esp = Esp()
        client = C3PairingBench(Radio(), now=lambda: 0, esp=esp, session=2)
        client.start()
        wrong = proto.encode(proto.PAIR_ACK, 2, payload=bytes((1, 1)) +
                             bytes(6) + bytes((255,)))
        esp.incoming.append(Packet(bytes.fromhex("aabbccddeeff"), wrong))
        client.poll()
        self.assertFalse(client.paired)
        self.assertEqual(client.bad, 1)


if __name__ == "__main__":
    unittest.main()
