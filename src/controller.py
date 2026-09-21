"""
CNC controller transport boundary.

IMPORTANT:
Motion/control requests are intentionally not implemented yet.
The network bootstrap can therefore be tested without accidentally
moving a CNC machine.
"""


VALID_MODES = ("disabled", "ugs", "esp3d", "grbl")


class Controller:
    def __init__(self, mode, host, port, network):
        if mode not in VALID_MODES:
            raise ValueError(
                "Unknown controller mode {!r}; expected {}".format(
                    mode, VALID_MODES
                )
            )

        self.mode = mode
        self.host = host
        self.port = int(port)
        self.network = network
        self.started = False

    def begin(self):
        print("[controller] mode:", self.mode)

        if self.mode == "disabled":
            print("[controller] CNC output disabled")
            self.started = True
            return

        if not self.host:
            raise RuntimeError(
                "MPG_CONTROLLER_HOST must be configured when "
                "MPG_CONTROLLER_MODE is not disabled"
            )

        print(
            "[controller] target: {}:{}".format(
                self.host,
                self.port,
            )
        )

        if self.mode == "ugs":
            print("[controller] UGS adapter reserved; commands disabled")
        elif self.mode == "esp3d":
            print("[controller] ESP3D adapter reserved; commands disabled")
        elif self.mode == "grbl":
            print("[controller] GRBL adapter reserved; commands disabled")

        self.started = True

    def poll(self):
        # Future reconnect/watchdog/status polling belongs here.
        return

    def send_action(self, action, **kwargs):
        raise RuntimeError(
            "CNC actions are intentionally disabled in the initial scaffold"
        )
