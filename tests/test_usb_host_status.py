import unittest
from src.transport.usb_host import USBHostStatusTransport, USBHostUnavailable

class FakeBackend:
    def __init__(self):
        self.connected = True
        self.writes = []
        self.reads = []
        self.closed = False
    def read(self, count):
        return self.reads.pop(0) if self.reads else None
    def write(self, data):
        self.writes.append(data)
        return len(data)
    def close(self):
        self.closed = True

class HostStatusTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        self.backend = FakeBackend()
    def make(self, **kw):
        return USBHostStatusTransport(self.backend, lambda: self.now,
            electrically_verified=True, host_verified=True,
            ch34x_verified=True, **kw)
    def test_unverified_hardware_never_opens(self):
        with self.assertRaises(USBHostUnavailable):
            USBHostStatusTransport(self.backend, lambda: 0)
        self.assertFalse(self.backend.writes)
    def test_only_status_query_and_status_response(self):
        t = self.make()
        t.poll()
        self.assertEqual(self.backend.writes, [b'?'])
        self.backend.reads = [b'Grbl 1.1h\n<Idle|MPos:0,1,2>\n']
        self.now = 0.1
        t.poll()
        self.assertEqual(t.readline(), b'<Idle|MPos:0,1,2>\n')
        self.assertIsNone(t.readline())
        with self.assertRaises(PermissionError):
            t.write(b'$J=G91 X1 F100\n')
        self.assertEqual(self.backend.writes, [b'?'])
    def test_timeout_closes_and_discards(self):
        t = self.make(status_timeout=0.8)
        t.poll()
        self.now = 0.81
        t.poll()
        self.assertFalse(t.connected)
        self.assertTrue(self.backend.closed)
        self.assertIsNone(t.readline())
    def test_disconnect_never_reconnects(self):
        t = self.make()
        t.poll()
        self.backend.connected = False
        t.poll()
        self.backend.connected = True
        t.poll()
        self.assertFalse(t.connected)
        self.assertEqual(self.backend.writes, [b'?'])
    def test_oversized_response_fails_closed(self):
        t = self.make(max_buffer=32, max_read=32)
        self.backend.reads = [b'x' * 32, b'x']
        t.poll()
        t.poll()
        self.assertFalse(t.connected)
    def test_backend_exception_fails_closed(self):
        t = self.make()
        def bad(_):
            raise OSError('unplug')
        self.backend.read = bad
        t.poll()
        self.assertFalse(t.connected)
    def test_fragmented_status(self):
        t = self.make()
        self.backend.reads = [b'<Idle|MPos:', b'1,2,3>\r\n']
        t.poll()
        self.now = .1
        t.poll()
        self.assertEqual(t.readline(), b'<Idle|MPos:1,2,3>\n')

if __name__ == '__main__':
    unittest.main()
