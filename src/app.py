"""Pendant composition root and cooperative runtime."""

import gc
import sys
import time

from src.controller.actions import ActionDispatcher
from src.controller.grbl import GRBLController
from src.display.base import Indicator
from src.display.ui import UIManager
from src.gcode.macros import MacroLibrary
from src.gcode.streamer import GCodeStreamer
from src.hardware import (build_display, build_indicator, build_inputs,
                          build_shared_i2c, build_storage, scan_i2c)
from src.input.manager import InputManager
from src.safety.state_machine import SafetyError, SafetyStateMachine
from src.safety.watchdog import Watchdog
from src.state import PendantState
from src.network import MockWiFiService, WiFiService
from src.transport.mock import MockGRBLTransport, MockTransport
from src.transport.uart import UARTTransport


class PendantApplication:
    def __init__(self, state, transport, controller, safety, actions, display,
                 storage, streamer, watchdog, indicator, ui, network_service,
                 macros, input_manager, indicator_output, sd_mount=None,
                 touch_manager=None, clock=time.monotonic):
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
        self.input_manager = input_manager
        self.indicator_output = indicator_output
        self.sd_mount = sd_mount
        self.touch_manager = touch_manager
        self.clock = clock

    @classmethod
    def from_config(cls, config, transport=None, display=None,
                    clock=time.monotonic, network_service=None,
                    input_manager=None, input_adapter=None, storage=None,
                    indicator_output=None, shared_spi=None, shared_i2c=None,
                    touch_manager=None, touch_source=None):
        state = PendantState(config.get("base_increment", 0.001))
        state.runtime_version = getattr(sys, "version", "unknown").split(";", 1)[0]
        state.board_profile = config.get("board_profile", "") or "default"
        state.display_profile = config.get("display_profile", "") or "default"
        state.selector_backend = config.get("selector_backend", "disabled")
        i2c_init_error = None
        if shared_i2c is None and sys.implementation.name == "circuitpython":
            shared_i2c, i2c_init_error = build_shared_i2c(config)
        mode = config.get("controller_mode", "disabled")
        state.controller_enabled = mode != "disabled"
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
        sd_mount = None
        if storage is None:
            storage, sd_mount = build_storage(config, shared_spi)
        macros = MacroLibrary(storage.macros_path)
        streamer = GCodeStreamer(state, controller, clock=clock)
        ui = UIManager(state)
        ui.complete_boot()
        display_error = None
        try:
            renderer = display or build_display(config)
        except Exception as exc:
            display_error = "display initialization failed: {}".format(
                type(exc).__name__)
            renderer = build_display({"display_enabled": False})
        if hasattr(renderer, "bind_ui"):
            renderer.bind_ui(ui)
        if network_service is None:
            network_service = (WiFiService(
                ap_timeout=config.get("network_ap_timeout", 600),
                connect_timeout=config.get("network_connect_timeout", 15)
            ) if
                               sys.implementation.name == "circuitpython" else
                               MockWiFiService())
        network_service.start(
            config.get("hostname", "cdaprod-cnc-pendant"),
            config.get("wifi_ssid", ""),
            config.get("wifi_password", "")
        )
        if input_manager is None:
            try:
                input_manager = (InputManager(
                    state, input_adapter,
                    config.get("mpg_counts_per_detent", 4),
                    config.get("mpg_direction", 1),
                    config.get("button_debounce", 0.03),
                    config.get("button_long_press", 0.8),
                    config.get("axis_map"),
                ) if input_adapter is not None else build_inputs(
                    config, state, shared_i2c))
            except Exception as exc:
                state.input_error = "input initialization failed: {}".format(
                    type(exc).__name__)
                input_manager = build_inputs({}, state)
        indicator_output = indicator_output or build_indicator(config)
        touch_error = None
        if (touch_manager is None and touch_source is None and
                config.get("touch_enabled")):
            try:
                if shared_i2c is None:
                    raise RuntimeError("shared I2C unavailable")
                from src.input.touch import build_cst8xx
                touch_source = build_cst8xx(shared_i2c)
            except Exception as exc:
                touch_error = "touch initialization failed: {}".format(
                    type(exc).__name__)
        if touch_manager is None and touch_source is not None:
            from src.input.touch import TouchInput
            touch_manager = TouchInput(touch_source, clock=clock)
        state.storage_state = storage.status
        state.storage_error = storage.error
        addresses, i2c_error = scan_i2c(shared_i2c)
        expected_address = config.get("mcp23017_address", 0x20)
        state.mcp23017_detected = expected_address in addresses
        state.mcp23017_address = expected_address if state.mcp23017_detected else None
        state.i2c_error = i2c_init_error or i2c_error
        state.display_error = display_error
        state.touch_error = touch_error
        storage_status = str(state.storage_state).lower()
        state.subsystems = {
            "display": "ERROR" if state.display_error else
                       "OK" if config.get("display_enabled") or display is not None
                       else "DISABLED",
            "storage": "OK" if storage_status == "available" else
                       "NOT PRESENT" if storage_status in ("missing", "unconfigured")
                       else "ERROR" if state.storage_error else "DISABLED",
            "sd": ("NOT PRESENT" if not config.get("sd_enabled") else
                   "MOUNTED" if storage_status == "available" else
                   "NOT PRESENT" if storage_status in ("missing", "unconfigured")
                   else "ERROR" if state.storage_error else "DISABLED"),
            "i2c": "ERROR" if state.i2c_error else
                   "OK" if shared_i2c is not None else "DISABLED",
            "inputs": "ERROR" if state.input_error else
                      "OK" if config.get("inputs_enabled") else "DISABLED",
            "touch": "ERROR" if state.touch_error else
                     "OK" if touch_manager is not None else "DISABLED",
            "wifi": network_service.state,
            "controller": ("DISABLED" if mode == "disabled" else "CONNECTING"),
        }
        for name in ("display", "storage", "sd", "i2c", "inputs", "touch",
                     "wifi", "controller"):
            print("{:<13} {}".format(name, state.subsystems[name]))
        if config.get("round_ui_bootstrap"):
            from src.display.round_ui.bootstrap import apply_mock_state
            apply_mock_state(state)
        return cls(state, transport, controller, safety, actions,
                   renderer, storage, streamer, watchdog, Indicator(), ui,
                   network_service, macros, input_manager, indicator_output,
                   sd_mount, touch_manager, clock)

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
            self.state.storage_state = self.storage.status
            self.state.storage_error = self.storage.error
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
            if command.value == "ESTOP_RECOVER":
                self.recover_estop()
                return True
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
            try:
                self.network_service.start_scan()
            except Exception as exc:
                self.ui.warning = "Wi-Fi scan failed: {}".format(
                    type(exc).__name__
                )
                return False
            self.ui.set_dynamic_items("ssids", self.network_service.scan_results)
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
        if name == "NETWORK_SETUP_AP":
            started = self.network_service.start_setup_ap(manual=True)
            self.ui.toast = "Setup AP started" if started else "AP failed"
            return started
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
        started = self.clock()
        self.network_service.poll()
        sample = self.input_manager.poll(started)
        if sample.mpg_activity:
            self.state.mpg_activity = sample.mpg_activity
            self.state.mpg_activity_timestamp = started
        elif (self.state.mpg_activity_timestamp is not None and
              started - self.state.mpg_activity_timestamp >= 0.20):
            self.state.mpg_activity = 0
        if sample.selector_changed:
            self._record_selector_transition(
                "axis", sample.selector_direction, started)
        if sample.multiplier_changed:
            self._record_selector_transition(
                "resolution", sample.multiplier_direction, started)
        for kind in ("axis", "resolution"):
            timestamp = getattr(self.state, kind + "_transition_timestamp")
            if timestamp is not None and started - timestamp >= 0.30:
                setattr(self.state, kind + "_transition_direction", 0)
        if sample.estop_changed:
            self.observe_estop(sample.estop)
        if ((sample.deadman_changed and not self.state.deadman_enabled) or
                (sample.selector_changed and self.state.selected_axis is None)):
            queued_jog = any(item[1] == "jog" for item in self.controller.queue)
            if self.transport.connected and (self.state.jog_active or queued_jog):
                self.controller.cancel_jog()
        for event in sample.events:
            try:
                self.handle_ui_event(event)
            except SafetyError as exc:
                self.ui.toast = str(exc)
        if self.touch_manager is not None:
            for event in self.touch_manager.poll():
                try:
                    self.handle_ui_event(event)
                except SafetyError as exc:
                    self.ui.toast = str(exc)
        if getattr(self.network_service, "scanning", False):
            if self.network_service.poll_scan():
                self.ui.set_dynamic_items(
                    "ssids", self.network_service.scan_results
                )
                if getattr(self.network_service, "last_error", None):
                    self.ui.warning = self.network_service.last_error
                else:
                    self.ui.toast = "{} networks".format(
                        len(self.network_service.scan_results)
                    )
        self.controller.poll(started)
        self.streamer.poll(started)
        events = self.watchdog.poll(started)
        if "jog_timeout" in events and self.transport.connected:
            self.controller.cancel_jog()
        self.ui.refresh_context()
        info = self.network_service.info()
        self.state.wifi_state = info.get("state", "DISABLED")
        self.state.wifi_ssid = info.get("ssid")
        self.state.wifi_ip = info.get("ipv4_address")
        self.state.wifi_rssi = info.get("rssi")
        self.state.hostname = info.get("hostname")
        self.state.network_error = info.get("last_error")
        self.state.subsystems["wifi"] = self.state.wifi_state
        self.state.subsystems["controller"] = (
            "DISABLED" if not self.state.controller_enabled else
            "CONNECTED" if self.state.connection_state == "connected" else
            "OFFLINE" if self.state.connection_state != "connecting" else
            "CONNECTING")
        self._update_indicator()
        self.display.render(self.state)
        self.state.render_count = getattr(self.display, "render_count", 0)
        self.state.loop_count += 1
        finished = self.clock()
        self.state.last_loop_duration = max(0.0, finished - started)
        last = self.state.last_controller_response
        self.state.last_status_age = (None if last is None else
                                      max(0.0, finished - last))
        self.state.free_heap = gc.mem_free() if hasattr(gc, "mem_free") else None

    def _record_selector_transition(self, kind, direction, now):
        setattr(self.state, kind + "_transition_direction", int(direction))
        setattr(self.state, kind + "_transition_timestamp", now)

    def _update_indicator(self):
        if self.state.connection_state != "connected":
            value = "DISCONNECTED"
        elif (self.state.estop_observed or self.state.estop_latched or
              self.state.machine_state == "alarm"):
            value = "ALARM"
        elif self.state.machine_state in ("jog", "run", "hold"):
            value = self.state.machine_state.upper()
        else:
            value = "READY"
        self.indicator.set(value)
        self.indicator_output.update(value)
