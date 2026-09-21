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

    def poll(self):
        return None

    def close(self):
        return None
