"""Read-only, fail-closed GRBL USB-host status transport.

A native CH34x backend and verified VBUS circuitry are prerequisites.
No USB hardware is initialized by this module.
"""

class USBHostUnavailable(RuntimeError):
    pass

class USBHostStatusTransport:
    name = "usb_host_status_only"

    def __init__(self, backend, clock, *, electrically_verified=False,
                 host_verified=False, ch34x_verified=False,
                 status_interval=0.25, status_timeout=1.0,
                 max_buffer=256, max_read=64):
        if not (electrically_verified and host_verified and ch34x_verified):
            raise USBHostUnavailable("host, CH34x and power require verification")
        if status_interval <= 0 or status_timeout <= status_interval:
            raise ValueError("invalid status timing")
        if max_buffer < 16 or max_read < 1 or max_read > max_buffer:
            raise ValueError("invalid receive bounds")
        self._backend = backend
        self._clock = clock
        self._interval = status_interval
        self._timeout = status_timeout
        self._max_buffer = max_buffer
        self._max_read = max_read
        self._buffer = bytearray()
        self._lines = []
        self._closed = False
        self._last_query = None
        self._last_status = None
        self.error = None

    @property
    def connected(self):
        if self._closed:
            return False
        try:
            return bool(self._backend.connected)
        except Exception:
            self._fail("backend state unavailable")
            return False

    @property
    def last_status(self):
        return self._last_status

    def write(self, data):
        raise PermissionError("read-only feasibility transport")

    def read(self, count=64):
        if count <= 0:
            raise ValueError("count must be positive")
        if not self._lines:
            return None
        line = self._lines[0]
        if len(line) > count:
            return None
        return self._lines.pop(0)

    def readline(self):
        return self._lines.pop(0) if self._lines else None

    def _fail(self, reason):
        self.error = reason
        self.close()

    def poll(self):
        if not self.connected:
            self._fail("USB disconnected")
            return
        now = float(self._clock())
        if self._last_status is not None and now - self._last_status > self._timeout:
            self._fail("stale GRBL status")
            return
        if self._last_query is not None and self._last_status is None and now - self._last_query > self._timeout:
            self._fail("GRBL status timeout")
            return
        try:
            chunk = self._backend.read(self._max_read)
            if chunk:
                if not isinstance(chunk, (bytes, bytearray)) or len(chunk) > self._max_read:
                    raise ValueError("invalid USB read")
                self._buffer.extend(chunk)
                if len(self._buffer) > self._max_buffer:
                    raise ValueError("USB receive overflow")
                for _ in range(8):
                    end = self._buffer.find(b"\n")
                    if end < 0:
                        break
                    line = bytes(self._buffer[:end + 1]).strip()
                    del self._buffer[:end + 1]
                    if line.startswith(b"<") and line.endswith(b">") and len(line) >= 6:
                        self._last_status = now
                        if len(self._lines) >= 8:
                            self._lines.pop(0)
                        self._lines.append(line + b"\n")
            if self._last_query is None or now - self._last_query >= self._interval:
                if self._backend.write(b"?") != 1:
                    raise OSError("incomplete status query")
                self._last_query = now
        except Exception as exc:
            self._fail("USB I/O failure: " + type(exc).__name__)

    def close(self):
        if self._closed:
            return
        self._closed = True
        self._buffer.clear()
        self._lines.clear()
        try:
            self._backend.close()
        except Exception:
            pass
