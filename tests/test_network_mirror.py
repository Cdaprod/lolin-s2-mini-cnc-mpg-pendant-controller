"""Browser mirror authorization and motion-dispatch regression tests."""
import unittest
import sys
from types import SimpleNamespace
from unittest.mock import patch
from src.network_mirror import PendantMirror
from src.display.ui import UIManager
from src.state import PendantState


class FakeApp:
    def __init__(self):
        self.state = PendantState()
        self.state.machine_state = "idle"
        self.state.connection_state = "connected"
        self.ui = UIManager(self.state)
        self.ui.complete_boot()
        self.ui.refresh_context()


def mirror(allow=True):
    # Bypass hardware socket init to test pure input authorization.
    obj = PendantMirror.__new__(PendantMirror)
    obj.app = FakeApp()
    obj.allow_navigation = allow
    obj.pool = None
    obj.sock = None
    obj._time = lambda: 0.0
    obj._client = None
    obj._request = bytearray(obj.REQUEST_LIMIT)
    obj._request_size = 0
    obj._request_length = None
    obj._response = None
    obj._response_offset = 0
    obj._client_started = 0.0
    obj.completed_requests = 0
    obj.client_errors = 0
    obj.last_error = None
    return obj


class FakeClient:
    def __init__(self, chunks=(), send_limit=97):
        self.chunks = list(chunks)
        self.send_limit = send_limit
        self.sent = bytearray()
        self.closed = False

    def setblocking(self, value):
        self.blocking = value

    def recv_into(self, target):
        if not self.chunks:
            raise BlockingIOError()
        chunk = self.chunks.pop(0)
        count = min(len(target), len(chunk))
        target[:count] = chunk[:count]
        if count < len(chunk):
            self.chunks.insert(0, chunk[count:])
        return count

    def send(self, data):
        count = min(self.send_limit, len(data))
        self.sent.extend(data[:count])
        return count

    def close(self):
        self.closed = True


class FakeListener:
    def __init__(self, clients=()):
        self.clients = list(clients)
        self.closed = False

    def accept(self):
        if not self.clients:
            raise BlockingIOError()
        return self.clients.pop(0), ("127.0.0.1", 1)

    def setblocking(self, value):
        self.blocking = value

    def bind(self, address):
        self.address = address

    def listen(self, backlog):
        self.backlog = backlog

    def close(self):
        self.closed = True


def socket_mirror(clients=(), now=None):
    obj = mirror()
    obj.sock = FakeListener(clients)
    obj._time = now or (lambda: 0.0)
    return obj


class MirrorTests(unittest.TestCase):
    def test_mirror_can_share_radio_socket_pool_with_setup_portal(self):
        class Pool:
            def __init__(self):
                self.listener = FakeListener()
            def socket(self):
                return self.listener
        pool = Pool()
        with patch.dict(sys.modules, {"socketpool": SimpleNamespace(
                SocketPool=lambda radio: self.fail("duplicate SocketPool"))}):
            m = PendantMirror(object(), FakeApp(), socket_pool=pool)
        self.assertIs(m.pool, pool)
        m.deinit()

    def test_socketpool_listener_is_nonblocking_and_owned(self):
        class Pool:
            def __init__(self, radio):
                self.listener = FakeListener()
            def socket(self):
                return self.listener
        module = SimpleNamespace(SocketPool=Pool)
        with patch.dict(sys.modules, {"socketpool": module}):
            m = PendantMirror(object(), FakeApp())
        listener = m.sock
        self.assertIs(m.sock.blocking, False)
        m.deinit()
        self.assertTrue(listener.closed)
        self.assertIsNone(m.sock)

    def test_http_uses_recv_into_and_handles_partial_writes(self):
        request = b"GET /api/state HTTP/1.1\r\nHost: pendant\r\n\r\n"
        client = FakeClient((request,), send_limit=31)
        m = socket_mirror((client,))
        for _ in range(40):
            m.poll()
            if client.closed:
                break
        self.assertTrue(client.closed)
        self.assertIn(b"HTTP/1.1 200 OK", client.sent)
        self.assertIn(b"application/json", client.sent)
        self.assertEqual(m.completed_requests, 1)

    def test_fragmented_post_body_and_repeated_connections(self):
        body = b'{"kind":"tap","x":100,"y":60}'
        first = (b"GET / HTTP/1.1\r\nHost: pendant\r\n\r\n")
        second = (b"POST /api/touch HTTP/1.1\r\nContent-Length: " +
                  str(len(body)).encode() + b"\r\n\r\n" + body)
        a, b = FakeClient((first,), send_limit=700), FakeClient(
            (second[:48], second[48:]), send_limit=700)
        m = socket_mirror((a, b))
        m.allow_navigation = False
        m.app.ui.enter("MAIN_MENU")
        for _ in range(30):
            m.poll()
        self.assertTrue(a.closed)
        self.assertTrue(b.closed)
        self.assertIn(b"200 OK", a.sent)
        self.assertIn(b"403 Forbidden", b.sent)
        self.assertEqual(m.completed_requests, 2)

    def test_disconnected_or_slow_client_is_bounded_and_released(self):
        now = [0.0]
        client = FakeClient()
        m = socket_mirror((client,), now=lambda: now[0])
        m.poll()  # accept
        m.poll()  # no request data
        now[0] = m.CLIENT_TIMEOUT + 0.1
        m.poll()
        self.assertTrue(client.closed)
        self.assertEqual(m.client_errors, 1)
        self.assertEqual(m.last_error, "TimeoutError")

    def test_opt_in_disabled(self):
        m = mirror(False)
        m.app.ui.enter("MAIN_MENU")
        self.assertFalse(m.navigate({"kind": "tap", "x": 100, "y": 60}))
        self.assertEqual(m.app.ui.current_screen, "MAIN_MENU")

    def test_submenu_entry_and_back(self):
        m = mirror()
        m.app.ui.enter("MAIN_MENU")
        self.assertTrue(m.navigate({"kind": "tap", "x": 100, "y": 60}))
        self.assertEqual(m.app.ui.current_screen, "MACHINE")
        self.assertTrue(m.navigate({"kind": "tap", "x": 20, "y": 210}))
        self.assertEqual(m.app.ui.current_screen, "MAIN_MENU")

    def test_motion_and_confirmation_not_accessible(self):
        m = mirror()
        self.assertFalse(m.navigate({"kind": "tap", "x": 120, "y": 120}))
        m.app.ui.enter("MAIN_MENU")
        m.app.ui.enter("MACHINE")
        self.assertFalse(m.navigate({"kind": "tap", "x": 120, "y": 60}))
        self.assertIsNone(m.app.ui.confirmation)

    def test_network_mutation_rejected(self):
        m = mirror()
        m.app.ui.enter("NETWORK")
        self.assertFalse(m.navigate({"kind": "tap", "x": 100, "y": 60}))

    def test_invalid_input_rejected(self):
        m = mirror()
        m.app.ui.enter("MAIN_MENU")
        for request in ({"kind": "swipe_left", "x": 20, "y": 20},
                        {"kind": "tap", "x": -1, "y": 60},
                        {"kind": "tap", "x": True, "y": 60},
                        {"kind": "tap", "x": 240, "y": 60}):
            self.assertFalse(m.navigate(request))

    def test_safety_overlay_blocks_browser_navigation(self):
        m = mirror()
        m.app.ui.enter("MAIN_MENU")
        m.app.state.set_estop(True)
        self.assertFalse(m.navigate({"kind": "tap", "x": 120, "y": 60}))

    def test_snapshot_omits_sensitive_details(self):
        m = mirror()
        m.app.ui.enter("NETWORK_INFO")
        result = m.snapshot()
        self.assertNotIn("details", result["ui"])
        self.assertNotIn("jog_armed", result["ui"])
        self.assertNotIn("motion_available", result["ui"])


if __name__ == "__main__":
    unittest.main()
