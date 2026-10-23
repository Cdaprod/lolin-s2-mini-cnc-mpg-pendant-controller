import unittest
from src.transport.grbl_status import parse_status
from src.transport.usb_host import USBHostStatusTransport

class StatusParserTests(unittest.TestCase):
    def test_machine_coordinates(self):
        s = parse_status(b"<Idle|MPos:10.000,20.000,5.000|WCO:1,2,3>")
        self.assertEqual(s["wpos"], (9.0, 18.0, 2.0))
    def test_explicit_work_coordinates(self):
        s = parse_status("<Jog|WPos:1,2,3>")
        self.assertEqual(s["wpos"], (1.0, 2.0, 3.0))
    def test_reject_bad_frames(self):
        for value in (b"", b"Grbl 1.1", b"<Idle|MPos:nan,2,3>",
                      b"<Idle|MPos:1,2>", b"<Idle|MPos:1,inf,3>",
                      b"<Idle|MPos:1,2,3|WCO:1,2,3,4>",
                      b"<unknown|MPos:1,2,3>"):
            self.assertIsNone(parse_status(value))
    def test_partial_read_is_not_consumed(self):
        class Backend:
            connected = True
            def read(self, count):
                return b"<Idle|MPos:1,2,3>\n"
            def write(self, data):
                return len(data)
            def close(self):
                pass
        t = USBHostStatusTransport(Backend(), lambda: 0.0,
            electrically_verified=True, host_verified=True,
            ch34x_verified=True)
        t.poll()
        self.assertIsNone(t.read(3))
        self.assertEqual(t.read(64), b"<Idle|MPos:1,2,3>\n")
        self.assertIsNone(t.read(64))

if __name__ == "__main__":
    unittest.main()
