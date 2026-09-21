"""Pendant composition root and cooperative runtime."""

import time

from src.controller.actions import ActionDispatcher
from src.controller.grbl import GRBLController
from src.display.base import Indicator
from src.display.console import ConsoleDisplay
from src.gcode.streamer import GCodeStreamer
from src.safety.state_machine import SafetyStateMachine
from src.safety.watchdog import Watchdog
from src.state import PendantState
from src.storage.sdcard import SDStorage
from src.transport.mock import MockGRBLTransport, MockTransport
from src.transport.uart import UARTTransport


class PendantApplication:
    def __init__(self, state, transport, controller, safety, actions, display,
                 storage, streamer, watchdog, indicator, clock=time.monotonic):
        self.state = state
        self.transport = transport
        self.controller = controller
        self.safety = safety
        self.actions = actions
        self.display = display
        self.storage = storage
        self.streamer = streamer
        self.watchdog = watchdog
        self.indicator = indicator
        self.clock = clock

    @classmethod
    def from_config(cls, config, transport=None, display=None,
                    clock=time.monotonic):
        state = PendantState(config.get("base_increment", 0.001))
        mode = config.get("controller_mode", "disabled")
        if transport is None:
            if mode == "uart":
                transport = UARTTransport.from_pin_names(
                    config.get("uart_tx_pin"), config.get("uart_rx_pin"),
                    config.get("uart_baudrate", 115200)
                )
            elif mode == "mock":
                transport = MockGRBLTransport()
            elif mode == "disabled":
                transport = MockTransport(connected=False)
            else:
                raise ValueError("unsupported controller mode: " + mode)
        controller = GRBLController(
            state, transport, clock=clock,
            status_interval=config.get("status_interval", 0.2)
        )
        safety = SafetyStateMachine(state)
        watchdog = Watchdog(state)
        actions = ActionDispatcher(
            state, controller, safety, config.get("jog_feed", 500), {
                "PROBE_Z": config.get("probe_z", "G91 G38.2 Z-10 F100"),
                "SAFE_Z": config.get("safe_z", "G53 G0 Z0"),
                "PARK": config.get("park", "G53 G0 X0 Y0"),
            }, watchdog=watchdog, clock=clock
        )
        storage = SDStorage(config.get("jobs_path", "/jobs"),
                            config.get("macros_path", "/macros"))
        streamer = GCodeStreamer(state, controller, clock=clock)
        return cls(state, transport, controller, safety, actions,
                   display or ConsoleDisplay(), storage, streamer, watchdog,
                   Indicator(), clock)

    def observe_estop(self, active):
        """Observe supplementary E-stop contact and immediately inhibit I/O."""
        self.safety.observe_estop(active)
        if active and self.transport.connected:
            self.controller.cancel_jog()
            self.streamer.inhibit()

    def recover_estop(self):
        """Explicit recovery after the independently wired contact is safe."""
        self.state.clear_estop_latch()

    def poll(self):
        now = self.clock()
        self.controller.poll(now)
        self.streamer.poll(now)
        events = self.watchdog.poll(now)
        if "jog_timeout" in events and self.transport.connected:
            self.controller.cancel_jog()
        self._update_indicator()
        self.display.render(self.state)

    def _update_indicator(self):
        if self.state.connection_state != "connected":
            value = "DISCONNECTED"
        elif self.state.estop_observed or self.state.machine_state == "alarm":
            value = "ALARM"
        elif self.state.machine_state in ("jog", "run", "hold"):
            value = self.state.machine_state.upper()
        else:
            value = "READY"
        self.indicator.set(value)
