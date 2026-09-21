"""Deterministic in-memory transport for host simulation and tests."""

from .base import Transport


class MockTransport(Transport):
    name = "mock"

    def __init__(self, connected=True):
        self._connected = bool(connected)
        self.writes = []
        self.incoming = []

    @property
    def connected(self):
        return self._connected

    def connect(self):
        self._connected = True

    def disconnect(self):
        self._connected = False

    def write(self, data):
        if not self._connected:
            raise RuntimeError("transport disconnected")
        if isinstance(data, str):
            data = data.encode("ascii")
        self.writes.append(bytes(data))
        return len(data)

    def readline(self):
        if not self.incoming:
            return None
        return self.incoming.pop(0)

    def inject(self, line):
        if isinstance(line, str):
            line = line.encode("ascii")
        if not line.endswith(b"\n"):
            line += b"\n"
        self.incoming.append(line)


class MockGRBLTransport(MockTransport):
    """Small GRBL simulator that acknowledges lines and answers status queries."""

    name = "mock-grbl"

    def __init__(self, status=None):
        super().__init__(connected=True)
        self.status = status or "<Idle|MPos:0,0,0,0,0,0|WCO:0,0,0,0,0,0|FS:0,0>"
        self.inject("Grbl 1.1h ['$' for help]")

    def write(self, data):
        length = super().write(data)
        raw = data.encode("ascii") if isinstance(data, str) else data
        if raw == b"?":
            self.inject(self.status)
        elif raw.endswith(b"\n"):
            self.inject("ok")
        return length
