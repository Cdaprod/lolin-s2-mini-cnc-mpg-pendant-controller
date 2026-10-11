"""Minimal nonblocking transport contract."""


class Transport:
    name = "base"

    @property
    def connected(self):
        raise NotImplementedError

    def write(self, data):
        raise NotImplementedError

    def readline(self):
        raise NotImplementedError

    def read(self, count=64):
        """Return up to ``count`` raw bytes, or ``None`` when none are ready."""
        raise NotImplementedError

    def poll(self):
        return None

    def close(self):
        return None
