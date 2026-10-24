"""Radio-health-only controller for the vendor C3 ESP-NOW bench mode.

CRITICAL: The upstream C3 UART_COMMAND is unrestricted and does not provide
GRBL acknowledgments or a receiver-side motion lease. Therefore this adapter
does not transmit any CNC command, including status queries or hold.
"""
from src.transport.c3_pairing_bench import C3PairingBench


class C3StatusController:
    def __init__(self, state, radio=None, now=None, esp=None, session=None):
        self.state = state
        self.transport = C3PairingBench(radio=radio, now=now, esp=esp,
                                        session=session)
        self.queue = []
        self.observers = []
        state.transport = "c3-espnow-bench"
        state.connection_state = "disconnected"
        state.machine_state = "disconnected"
        state.controller_enabled = True
        self.transport.start()

    def poll(self, now=None):
        try:
            self.transport.poll()
        except (OSError, RuntimeError, ValueError) as exc:
            self.state.controller_error = "C3 ESP-NOW: " + type(exc).__name__
            self.state.connection_state = "disconnected"
            self.state.machine_state = "disconnected"
            self.state.link_state = "DISCONNECTED"
            return
        linked = bool(self.transport.paired)
        # Radio pairing is not evidence that GRBL itself is connected.
        self.state.connection_state = "disconnected"
        self.state.machine_state = "disconnected"
        self.state.link_state = "PAIRED_NO_CONTROLLER" if linked else "DISCONNECTED"
        self.state.controller_error = None if linked else "C3 radio not paired"

    def add_observer(self, callback):
        self.observers.append(callback)

    def queue_command(self, command, kind="normal"):
        return False

    def queue_jog(self, axis, distance, feed, units="mm"):
        return False

    def realtime(self, name):
        return False

    def discard_queued(self, kind):
        return None

    def cancel_jog(self):
        self.state.jog_active = False
        return True

    def close(self):
        self.transport.close()
