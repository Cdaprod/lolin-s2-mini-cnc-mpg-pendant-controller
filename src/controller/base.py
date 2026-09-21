"""Controller protocol contract."""


class ControllerProtocol:
    def poll(self, now=None):
        raise NotImplementedError

    def queue_command(self, command, kind="normal"):
        raise NotImplementedError
