"""Pendant composition root and cooperative runtime."""

import time
import sys

from src.controller.actions import ActionDispatcher
from src.controller.grbl import GRBLController
from src.display.base import Indicator
from src.display.console import ConsoleDisplay
from src.display.ui import UIManager
from src.gcode.macros import MacroLibrary
from src.gcode.streamer import GCodeStreamer
from src.safety.state_machine import SafetyStateMachine
from src.safety.watchdog import Watchdog
from src.state import PendantState
from src.storage.sdcard import SDStorage
from src.network import MockWiFiService, WiFiService
from src.transport.mock import MockGRBLTransport, MockTransport
from src.transport.uart import UARTTransport


class PendantApplication:
    def __init__(self, state, transport, controller, safety, actions, display,
                 storage, streamer, watchdog, indicator, ui, network_service,
                 macros, clock=time.monotonic):
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
        self.ui = ui
        self.network_service = network_service
        self.macros = macros
        self.clock = clock

    @classmethod
    def from_config(cls, config, transport=None, display=None,
                    clock=time.monotonic, network_service=None):
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
        macros = MacroLibrary(config.get("macros_path", "/macros"))
        streamer = GCodeStreamer(state, controller, clock=clock)
        ui = UIManager(state)
        ui.complete_boot()
        renderer = display or ConsoleDisplay()
        if hasattr(renderer, "bind_ui"):
            renderer.bind_ui(ui)
        if network_service is None:
            network_service = (WiFiService() if
                               sys.implementation.name == "circuitpython" else
                               MockWiFiService())
        return cls(state, transport, controller, safety, actions,
                   renderer, storage, streamer, watchdog, Indicator(), ui,
                   network_service, macros, clock)

    def observe_estop(self, active):
        """Observe supplementary E-stop contact and immediately inhibit I/O."""
        self.safety.observe_estop(active)
        if active and self.transport.connected:
            self.controller.cancel_jog()
            self.streamer.inhibit()

    def recover_estop(self):
        """Explicit recovery after the independently wired contact is safe."""
        self.state.clear_estop_latch()

    def handle_ui_event(self, event):
        """Route a normalized UI event and execute only its semantic result."""
        if self.ui.current_screen in ("JOBS", "JOB_BROWSER"):
            self.ui.set_dynamic_items("jobs", self.storage.list_jobs())
        elif self.ui.current_screen in ("MACROS", "MACRO_BROWSER"):
            self.ui.set_dynamic_items("macros", self.macros.list())
        previous_screen = self.ui.current_screen
        command = self.ui.handle(event)
        if (previous_screen == "NETWORK" and
                self.ui.current_screen == "NETWORK_INFO"):
            self.ui.network_info = self.network_service.info()
            self.ui.dirty = True
        if command is None:
            return None
        name = command.name
        if name == "JOG":
            return self.actions.jog(command.value)
        if name == "ACTION":
            return self.actions.dispatch(command.value)
        if name == "JOB_START":
            job = self.storage.select_job(command.value)
            self.streamer.start(job, self.clock())
            self.ui.enter("ACTIVE_JOB")
            return True
        if name == "JOB_HOLD":
            self.streamer.pause()
            return True
        if name == "JOB_RESUME":
            self.streamer.resume()
            return True
        if name == "JOB_CANCEL":
            self.streamer.cancel()
            return True
        if name == "MACRO_RUN":
            self.macros.queue(command.value, self.controller, self.safety)
            return True
        if name == "NETWORK_SCAN":
            self.ui.set_dynamic_items("ssids", self.network_service.scan())
            self.ui.enter("WIFI_SCAN")
            return True
        if name == "NETWORK_CONNECT":
            ssid, password = command.value
            connected = self.network_service.connect(ssid, password)
            # Drop the only command reference that contained the password.
            command.value = None
            self.ui.toast = "Connected" if connected else "Connection failed"
            self.ui.back()
            return connected
        if name == "NETWORK_DISCONNECT":
            self.network_service.disconnect()
            self.ui.toast = "Wi-Fi disconnected"
            return True
        if name == "NETWORK_TOGGLE":
            enabled = not self.network_service.enabled
            self.network_service.set_enabled(enabled)
            self.ui.toast = "Wi-Fi on" if enabled else "Wi-Fi off"
            return True
        if name == "RESTART":
            if sys.implementation.name == "circuitpython":
                import supervisor
                supervisor.reload()
            return True
        return command

    def poll(self):
        now = self.clock()
        self.controller.poll(now)
        self.streamer.poll(now)
        events = self.watchdog.poll(now)
        if "jog_timeout" in events and self.transport.connected:
            self.controller.cancel_jog()
        self.ui.refresh_context()
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
