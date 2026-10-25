"""Pure-Python test vectors from the C3 ESP-NOW protocol header."""
import unittest
from src.transport import c3_espnow_protocol as proto


class CodecTests(unittest.TestCase):
    def test_binary_header_little_endian(self):
        packet = proto.encode(proto.HEARTBEAT, 0x12345678, 0xABCD)
        self.assertEqual(packet, bytes.fromhex("010378563412cdab0000"))
        self.assertEqual(proto.decode(packet),
                         (proto.HEARTBEAT, 0x12345678, 0xABCD, b""))

    def test_uart_payload_length(self):
        frame = proto.encode(proto.UART_COMMAND, 1, 2, b"?")
        self.assertEqual(frame, bytes.fromhex("012001000000020001003f"))
        self.assertEqual(proto.decode(frame)[3], b"?")

    def test_reject_truncated_corrupt_and_oversized(self):
        good = proto.encode(proto.HEARTBEAT, 1)
        for corrupted in (good[:-1], good + b"x", bytes((2,)) + good[1:]):
            with self.assertRaises(ValueError):
                proto.decode(corrupted)
        with self.assertRaises(ValueError):
            proto.encode(proto.UART_COMMAND, 1, payload=b"x" * 241)

    def test_pair_ack_verifies_bridge_and_session(self):
        mac = bytes.fromhex("aabbccddeeff")
        frame = proto.encode(proto.PAIR_ACK, 7, payload=bytes((1, 1)) + mac + bytes((255,)))
        self.assertEqual(proto.validate_pair_ack(frame, 7), (mac, 255))
        with self.assertRaises(ValueError):
            proto.validate_pair_ack(frame, 8)
        with self.assertRaises(ValueError):
            proto.validate_pair_ack(frame, 7, bytes(6))


if __name__ == "__main__":
    unittest.main()
