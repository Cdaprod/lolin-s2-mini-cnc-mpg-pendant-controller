"""Cross-firmware MPG packet vectors, bounds and deadman assertions."""
import unittest
from src.transport import c3_espnow_protocol as proto


class MPGWireTests(unittest.TestCase):
    def test_jog_contract_and_stop(self):
        frame = proto.encode_mpg_jog(0x12345678, 0x100, "X", -10, 250, True)
        self.assertEqual(frame, bytes.fromhex(
            "013078563412000108005801f6fffffffa00"))
        self.assertEqual(proto.decode(frame),
                         (proto.MPG_JOG, 0x12345678, 256,
                          bytes.fromhex("5801f6fffffffa00")))
        stop = proto.encode_mpg_stop(1, 2)
        self.assertEqual(proto.decode(stop), (proto.MPG_STOP, 1, 2, b""))

    def test_invalid_jogs_do_not_encode(self):
        for axis, distance, feed, deadman in (
            ("Q", 10, 250, True), ("X", 0, 250, True),
            ("X", 1001, 250, True), ("X", -1001, 250, True),
            ("X", 10, 0, True), ("X", 10, 1001, True),
            ("X", 10.1, 250, True), ("X", 10, 250, 1),
        ):
            with self.subTest(axis=axis, distance=distance, feed=feed):
                with self.assertRaises(ValueError):
                    proto.encode_mpg_jog(1, 1, axis, distance, feed, deadman)

    def test_fourth_axis_a_uses_existing_v1_payload(self):
        frame = proto.encode_mpg_jog(0x12345678, 0x101, "A", 10, 250, True)
        self.assertEqual(frame, bytes.fromhex(
            "0130785634120101080041010a000000fa00"))
        self.assertEqual(proto.decode(frame)[3][0], ord("A"))


if __name__ == "__main__":
    unittest.main()
