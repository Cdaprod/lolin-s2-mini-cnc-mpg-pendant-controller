"""Pendant composition root and cooperative runtime."""

import gc
import sys
import time

from src.controller.actions import ActionDispatcher
from src.controller.grbl import GRBLController
from src.controller.bridge import BridgeController
from src.controller.c3_status import C3StatusController
from src.controller.c3_wireless import C3WirelessController
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
from src.diagnostics import emit


# CircuitPython peripheral objects are interpreter-owned singletons. Track
# composition in sys.modules so re-importing src.app cannot bypass the guard.
_CIRCUITPY_COMPOSITION_KEY = "_cdaprod_circuitpython_app_composition"


class PendantApplication:
    def __init__(self, state, transport, controller, safety, actions, display,
                 storage, streamer, watchdog, indicator, ui, network_service,
                 macros, input_manager, indicator_output, sd_mount=None,
                 touch_manager=None, clock=time.monotonic, spi_bus=None,
                 i2c_bus=None):
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
        # Keep the shared bus alive independently of individual drivers.
        self.spi_bus = spi_bus
        self.i2c_bus = i2c_bus
        self.mirror = None
        self._last_heap_warning = None
        self._diag_last_heartbeat = None
        self._diag_encoder_delta = 0
        self._diag_last_touch_error = None
        self._diag_last_wifi_state = None
        self._diag_last_controller_state = None
        self._diag_last_display_state = None
        self._diag_last_selectors_valid = None
        self._diag_last_input_valid = None
        self._diag_buttons = {}
        self._diag_last_input_error = None

    @classmethod
    def from_config(cls, config, transport=None, display=None,
                    clock=time.monotonic, network_service=None,
                    input_manager=None, input_adapter=None, storage=None,
                    indicator_output=None, shared_spi=None, shared_i2c=None,
                    touch_manager=None, touch_source=None):
        if sys.implementation.name == "circuitpython":
            if sys.modules.get(_CIRCUITPY_COMPOSITION_KEY):
                raise RuntimeError(
                    "CircuitPython app composition is one-shot per run; "
                    "use supervisor.reload() to restart safely")
            # Mark before allocating peripherals: partial initialization may
            # already have claimed pins even when a later optional service fails.
            sys.modules[_CIRCUITPY_COMPOSITION_KEY] = True
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
            if mode in ("c3_espnow_bench", "c3_espnow"):
                transport = MockTransport(connected=False)
            elif mode in ("uart", "bridge"):
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
        if mode == "c3_espnow_bench":
            if sys.implementation.name != "circuitpython":
                raise RuntimeError("ESP-NOW hardware mode requires CircuitPython")
            controller = C3StatusController(state)
        elif mode == "c3_espnow":
            if sys.implementation.name != "circuitpython":
                raise RuntimeError("ESP-NOW hardware mode requires CircuitPython")
            controller = C3WirelessController(state, now=clock)
        elif mode == "bridge":
            controller = BridgeController(
                state, transport, clock,
                motion_enabled=config.get("bridge_motion_enabled", False))
        else:
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
        # One SPI object must be shared by the GC9A01 and SD card. Build it
        # with MISO at creation (the LCD alone only needs SCK and MOSI).
        # Never make SD a prerequisite for starting the round UI.
        sd_spi = shared_spi
        display_release_error = None
        if (display is None and sd_spi is None and config.get("display_enabled") and
                config.get("display_renderer") == "round" and
                sys.implementation.name == "circuitpython"):
            try:
                from src.display.round_ui.display import release_existing_displays
                release_existing_displays()
            except (ImportError, OSError, RuntimeError, AttributeError) as exc:
                display_release_error = "display release failed: {}".format(
                    type(exc).__name__)
                print("display release diagnostic:", type(exc).__name__, str(exc)[:80])
        if (display_release_error is None and sd_spi is None and config.get("sd_enabled") and
                config.get("display_enabled") and
                config.get("display_renderer") == "round" and
                sys.implementation.name == "circuitpython"):
            from src.hardware import build_shared_spi
            try:
                sd_spi = build_shared_spi(config)
            except (OSError, RuntimeError, ValueError, AttributeError,
                    ImportError, KeyError) as exc:
                print("shared SPI allocation failed:", type(exc).__name__, str(exc)[:80])
        # Initialize the round GC9A01 before mounting the SPI SD card.
        # A card/mount failure must never prevent critical display startup.
        ui = UIManager(state)
        ui.complete_boot()
        display_error = display_release_error
        if display_release_error is not None:
            renderer = build_display({"display_enabled": False})
        else:
            try:
                renderer = display or build_display(config, shared_spi=sd_spi)
            except (OSError, RuntimeError, ValueError, AttributeError,
                    ImportError, KeyError) as exc:
                display_error = "display initialization failed: {}".format(
                    type(exc).__name__)
                print("display diagnostic:", type(exc).__name__, str(exc)[:80])
                renderer = build_display({"display_enabled": False})
        sd_mount = None
        if storage is None:
            if (config.get("sd_enabled") and config.get("display_enabled") and
                    config.get("display_renderer") == "round" and
                    sd_spi is None and sys.implementation.name == "circuitpython"):
                sd_config = dict(config)
                sd_config["sd_enabled"] = False
                storage, sd_mount = build_storage(sd_config)
                state.sd_startup_error = "shared SPI unavailable"
            else:
                storage, sd_mount = build_storage(config, sd_spi)
        macros = MacroLibrary(storage.macros_path)
        streamer = GCodeStreamer(state, controller, clock=clock)
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
                from src.input.touch import build_chsc6x, build_cst8xx
                touch_driver = config.get("touch_driver", "chsc6x")
                touch_source = (build_chsc6x(shared_i2c, config.get("touch_irq_pin", "D7"))
                                if touch_driver == "chsc6x" else
                                build_cst8xx(shared_i2c))
            except Exception as exc:
                touch_error = "touch initialization failed: {}".format(
                    type(exc).__name__)
        if touch_manager is None and touch_source is not None:
            from src.input.touch import TouchInput
            touch_manager = TouchInput(
                touch_source, clock=clock,
                rotation=config.get("touch_rotation", 0),
                invert_x=config.get("touch_invert_x", False),
                invert_y=config.get("touch_invert_y", False))
        state.storage_state = storage.status
        state.storage_error = storage.error
        addresses, i2c_error = scan_i2c(shared_i2c)
        expected_address = config.get("mcp23017_address", 0x20)
        state.mcp23017_detected = expected_address in addresses
        state.mcp23017_address = expected_address if state.mcp23017_detected else None
        state.i2c_addresses = addresses
        state.i2c_error = i2c_init_error or i2c_error
        state.display_error = display_error
        state.touch_error = touch_error
        if storage.error:
            print("storage diagnostic:", storage.error)
        if state.i2c_error:
            print("I2C diagnostic:", state.i2c_error)
        if touch_error:
            print("touch diagnostic:", touch_error)
        storage_status = str(state.storage_state).lower()
        state.subsystems = {
            "display": "ERROR" if state.display_error else
                       "OK" if config.get("display_enabled") or display is not None
                       else "DISABLED",
            "storage": "OK" if storage_status == "available" else
                       "NOT PRESENT" if storage_status == "missing" else
                       "ERROR" if storage_status == "mount_error" else
                       "DISABLED" if storage_status == "unconfigured" else
                       "ERROR" if state.storage_error else "DISABLED",
            "sd": ("DISABLED" if not config.get("sd_enabled") else
                   "MOUNTED" if storage_status == "available" else
                   "NOT PRESENT" if storage_status == "missing" else
                   "ERROR" if state.storage_error else "DISABLED"),
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
            emit("subsystem", name=name, status=state.subsystems[name])
        input_adapter_configured = bool(
            getattr(getattr(input_manager, "adapter", None), "configured", False))
        emit("input_configuration",
             selector_backend=state.selector_backend,
             inputs_enabled=config.get("inputs_enabled", False),
             adapter_configured=input_adapter_configured,
             mcp23017_detected=state.mcp23017_detected,
             mcp23017_address=("0x{:02x}".format(state.mcp23017_address)
                               if state.mcp23017_address is not None else "none"))
        state.free_heap = gc.mem_free() if hasattr(gc, "mem_free") else None
        if state.free_heap is not None:
            print("runtime heap:", state.free_heap)
        if config.get("round_ui_bootstrap"):
            from src.display.round_ui.bootstrap import apply_mock_state
            apply_mock_state(state)
        app = cls(state, transport, controller, safety, actions,
                  renderer, storage, streamer, watchdog, Indicator(), ui,
                  network_service, macros, input_manager, indicator_output,
                  sd_mount, touch_manager, clock, sd_spi, shared_i2c)
        if config.get("mirror_enabled") and sys.implementation.name == "circuitpython":
            if not 1024 <= config.get("mirror_port", 8080) <= 65535:
                print("mirror disabled: invalid port")
            else:
                try:
                    from src.network_mirror import PendantMirror
                    radio = network_service.radio
                    pool_factory = getattr(network_service, "socket_pool", None)
                    socket_pool = pool_factory() if pool_factory else None
                    app.mirror = PendantMirror(
                        radio, app, config.get("mirror_port", 8080),
                        config.get("mirror_navigation", False),
                        socket_pool=socket_pool)
                    print("mirror listening on port", config.get("mirror_port", 8080))
                except (OSError, ImportError, RuntimeError, ValueError,
                        AttributeError) as exc:
                    state.mirror_error = "startup: {}".format(type(exc).__name__)
                    print("mirror startup failed:", type(exc).__name__, str(exc)[:80])
        return app

    def observe_estop(self, active):
        """Observe supplementary E-stop contact and immediately inhibit I/O."""
        self.safety.observe_estop(active)
        if active and (self.transport.connected or isinstance(self.controller, C3WirelessController)):
            self.controller.cancel_jog()
            self.streamer.inhibit()

    def recover_estop(self):
        """Explicit recovery after the independently wired contact is safe."""
        self.state.clear_estop_latch()

    def _machine_activity_blocks_network_association(self):
        """Defer blocking CircuitPython Wi-Fi association during machine work."""
        if (self.state.jog_active or self.state.deadman_enabled or
                self.state.machine_state in ("jog", "run", "hold", "home",
                                             "probe", "check")):
            return True
        if self.state.sd_job_state in ("streaming", "paused"):
            return True
        return any(len(item) > 1 and item[1] in ("jog", "stream")
                   for item in getattr(self.controller, "queue", ()))

    def deinit(self):
        """Release optional services and peripheral ownership before reload."""
        if getattr(self, "_deinitialized", False):
            return
        self._deinitialized = True
        if self.mirror is not None:
            try:
                self.mirror.deinit()
            except (OSError, RuntimeError):
                pass
            self.mirror = None
        if hasattr(self.network_service, "deinit"):
            try:
                self.network_service.deinit()
            except (OSError, RuntimeError):
                pass
        if self.sd_mount is not None and hasattr(self.sd_mount, "deinit"):
            try:
                self.sd_mount.deinit()
            except (OSError, RuntimeError, ImportError):
                pass
            self.sd_mount = None
        if self.touch_manager is not None and hasattr(self.touch_manager, "deinit"):
            try:
                self.touch_manager.deinit()
            except (OSError, RuntimeError):
                pass
            self.touch_manager = None
        if self.spi_bus is not None or hasattr(self.display, "display"):
            try:
                from src.display.round_ui.display import release_existing_displays
                release_existing_displays()
            except (ImportError, RuntimeError, AttributeError):
                pass
            if self.spi_bus is not None and hasattr(self.spi_bus, "deinit"):
                try:
                    self.spi_bus.deinit()
                except (OSError, RuntimeError):
                    pass
            self.spi_bus = None
        if self.i2c_bus is not None and hasattr(self.i2c_bus, "deinit"):
            try:
                self.i2c_bus.deinit()
            except (OSError, RuntimeError):
                pass
            self.i2c_bus = None

    def handle_ui_event(self, event):
        """Route a normalized UI event and execute only its semantic result."""
        if self.ui.current_screen in ("JOBS", "JOB_BROWSER", "EXPLORER"):
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
        if (name in ("NETWORK_CONNECT", "NETWORK_SCAN", "NETWORK_TOGGLE",
                     "NETWORK_SETUP_AP", "NETWORK_DISCONNECT") and
                self._machine_activity_blocks_network_association()):
            if name == "NETWORK_CONNECT":
                command.value = None
            self.ui.toast = "Wi-Fi changes wait until machine activity stops"
            return False
        if name == "JOG":
            return self.actions.jog(command.value)
        if name == "ACTION":
            if command.value == "ESTOP_RECOVER":
                self.recover_estop()
                return True
            return self.actions.dispatch(command.value)
        if name == "JOB_START":
            if isinstance(self.controller, (BridgeController, C3StatusController, C3WirelessController)):
                raise SafetyError("bridge file streaming is not implemented")
            job = self.storage.select_job(command.value)
            self.streamer.start(job, self.clock())
            self.ui.enter("ACTIVE_JOB")
            return True
        if name == "JOB_HOLD":
            if isinstance(self.controller, (C3StatusController, C3WirelessController)):
                raise SafetyError("C3 bench mode cannot control jobs")
            self.streamer.pause()
            return True
        if name == "JOB_RESUME":
            if isinstance(self.controller, C3StatusController):
                raise SafetyError("C3 bench mode cannot control jobs")
            self.streamer.resume()
            return True
        if name == "JOB_CANCEL":
            if isinstance(self.controller, C3StatusController):
                raise SafetyError("C3 bench mode cannot control jobs")
            self.streamer.cancel()
            return True
        if name == "MACRO_RUN":
            if isinstance(self.controller, (BridgeController, C3WirelessController, C3StatusController)):
                raise SafetyError("wireless macros are not implemented")
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
                self.deinit()
                import supervisor
                supervisor.reload()
            return True
        return command

    def poll(self):
        started = self.clock()
        sample = self.input_manager.poll(started)
        if (sample.selector_changed or sample.multiplier_changed or
                sample.selectors_valid_changed or sample.input_valid_changed):
            # The input manager drops detents spanning selector transitions.
            # Clear retained visual/diagnostic activity as well so stale
            # movement is not shown or later attributed to the new selection.
            self.state.mpg_activity = 0
            self.state.mpg_activity_timestamp = None
            self._diag_encoder_delta = 0
        if sample.encoder_overrun:
            self.state.mpg_activity = 0
            self.state.mpg_activity_timestamp = None
            self._diag_encoder_delta = 0
            emit("encoder_overrun", delta=sample.encoder_overrun_delta,
                 max_detents=getattr(self.input_manager,
                                     "MAX_ENCODER_DETENTS_PER_POLL", 4))
        input_backend_configured = bool(
            getattr(self.input_manager.adapter, "configured", True))
        if (input_backend_configured and
                (self._diag_last_input_valid is None or
                 self._diag_last_input_valid != self.state.input_valid)):
            emit("input_validity", domain="hardware",
                 valid=self.state.input_valid,
                 reason=self.state.input_error or "none")
            self._diag_last_input_valid = self.state.input_valid
        if sample.input_valid_changed and self.state.input_valid is False:
            # A failed MCP23017 snapshot invalidates the deadman and every
            # selector at once. Revoke both queued and active jog ownership.
            queued_jog = any(item[1] == "jog"
                             for item in getattr(self.controller, "queue", ()))
            self.controller.discard_queued("jog")
            if (isinstance(self.controller, C3WirelessController) or
                    (self.transport.connected and
                     (self.state.jog_active or queued_jog))):
                self.controller.cancel_jog()
            self.state.jog_active = False
        if (input_backend_configured and
                (self._diag_last_selectors_valid is None or
                 self._diag_last_selectors_valid != self.state.selectors_valid)):
            emit("input_validity", domain="selectors",
                 valid=self.state.selectors_valid,
                 reason=self.state.selector_error or "none")
            self._diag_last_selectors_valid = self.state.selectors_valid
        for name, active in sample.button_states.items():
            active = bool(active)
            if self._diag_buttons.get(name) != active:
                emit("input_state", input="button_" + name.lower(), active=active)
                self._diag_buttons[name] = active
        if self.state.error and self.state.error != self._diag_last_input_error:
            emit("input_rejected", reason=self.state.error)
            self._diag_last_input_error = self.state.error
        if sample.mpg_activity:
            self.state.mpg_activity = sample.mpg_activity
            self.state.mpg_activity_timestamp = started
            self._diag_encoder_delta += int(sample.mpg_activity)
        elif (self.state.mpg_activity_timestamp is not None and
              started - self.state.mpg_activity_timestamp >= 0.20):
            self.state.mpg_activity = 0
        if sample.selector_changed:
            emit("selector_state", axis=self.state.selected_axis or "OFF",
                 selector_position=self.state.selected_physical_axis or "OFF",
                 increment=self.state.selected_multiplier,
                 axis_direction=sample.selector_direction)
            self._record_selector_transition(
                "axis", sample.selector_direction, started)
            # Every physical selector transition revokes the previous motion
            # owner before any wheel event from this sample is dispatched.
            queued_jog = any(item[1] == "jog" for item in self.controller.queue)
            self.controller.discard_queued("jog")
            if (self.transport.connected or isinstance(self.controller, C3WirelessController)) and (self.state.jog_active or queued_jog):
                self.controller.cancel_jog()
            self.state.jog_active = False
            self.ui.apply_selector_context()
        if sample.multiplier_changed:
            emit("selector_state", axis=self.state.selected_axis or "OFF",
                 selector_position=self.state.selected_physical_axis or "OFF",
                 increment=self.state.selected_multiplier,
                 increment_direction=sample.multiplier_direction)
            # Resolution changes also revoke the previous handwheel command.
            # Never interpret wheel deltas across a multiplier transition.
            if isinstance(self.controller, C3WirelessController):
                self.controller.cancel_jog()
            self._record_selector_transition(
                "resolution", sample.multiplier_direction, started)
        for kind in ("axis", "resolution"):
            timestamp = getattr(self.state, kind + "_transition_timestamp")
            if timestamp is not None and started - timestamp >= 0.30:
                setattr(self.state, kind + "_transition_direction", 0)
        if sample.estop_changed:
            emit("input_state", input="estop_observe", active=sample.estop)
            self.observe_estop(sample.estop)
        if sample.deadman_changed and not self.state.deadman_enabled:
            emit("input_state", input="deadman", active=False)
            queued_jog = any(item[1] == "jog" for item in self.controller.queue)
            if (self.transport.connected or isinstance(self.controller, C3WirelessController)) and (self.state.jog_active or queued_jog):
                self.controller.cancel_jog()
        elif sample.deadman_changed:
            emit("input_state", input="deadman", active=True)
        for event in sample.events:
            emit("operator_input", action=event,
                 axis=self.state.selected_axis or "OFF",
                 selector_position=self.state.selected_physical_axis or "OFF",
                 increment=self.state.selected_multiplier)
            try:
                self.handle_ui_event(event)
            except SafetyError as exc:
                self.ui.toast = str(exc)
        if self.touch_manager is not None:
            for event in self.touch_manager.poll():
                emit("touch_gesture", kind=event.kind, x=event.x, y=event.y)
                try:
                    self.handle_ui_event(event)
                except SafetyError as exc:
                    self.ui.toast = str(exc)
            if getattr(self.touch_manager, "consecutive_errors", 0) >= 3:
                self.state.touch_error = "touch polling failed: " + self.touch_manager.last_error
                self.state.subsystems["touch"] = "ERROR"
                if self._diag_last_touch_error != self.touch_manager.last_error:
                    emit("touch_error", error=self.touch_manager.last_error,
                         consecutive=self.touch_manager.consecutive_errors)
                    self._diag_last_touch_error = self.touch_manager.last_error
            elif getattr(self.touch_manager, "last_error", None) is None:
                self.state.touch_error = None
                self.state.subsystems["touch"] = "OK"
                if self._diag_last_touch_error is not None:
                    emit("touch_recovered")
                    self._diag_last_touch_error = None
            # Feedback is visual only. No touch event can write controller I/O
            # except through the existing safety-checked UI action dispatcher.
            feedback = self.touch_manager.last_feedback
            if feedback is not None:
                if hasattr(self.display, "touch_feedback"):
                    self.display.touch_feedback(
                        feedback[:2], self.touch_manager.feedback_until)
                self.touch_manager.last_feedback = None
        if hasattr(self.display, "animate"):
            self.display.animate(started)
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
        if not isinstance(self.controller, (C3StatusController, C3WirelessController)):
            self.streamer.poll(started)
        events = self.watchdog.poll(started)
        if "jog_timeout" in events and (self.transport.connected or isinstance(self.controller, C3WirelessController)):
            self.controller.cancel_jog()
        self.ui.refresh_context()
        display_state = (self.ui.current_screen, self.state.active_page)
        if display_state != self._diag_last_display_state:
            emit("display_navigation", screen=display_state[0],
                 page=display_state[1])
            self._diag_last_display_state = display_state
        # Give network transitions their turn after physical safety and
        # transport processing; HTTP services themselves advance one bounded
        # nonblocking operation per poll.
        # CircuitPython's portable wifi.radio.connect() call is synchronous.
        # Do not let a reconnect or setup-portal submission pause pendant
        # servicing while a jog or job has authority on the machine.
        if not self._machine_activity_blocks_network_association():
            self.network_service.poll()
        info = self.network_service.info()
        self.state.wifi_state = info.get("state", "DISABLED")
        self.state.wifi_ssid = info.get("ssid")
        self.state.wifi_ip = info.get("ipv4_address")
        self.state.wifi_rssi = info.get("rssi")
        self.state.hostname = info.get("hostname")
        self.state.network_error = info.get("last_error")
        self.state.subsystems["wifi"] = self.state.wifi_state
        if self.state.wifi_state != self._diag_last_wifi_state:
            emit("wifi_state", state=self.state.wifi_state,
                 connected=bool(info.get("connected", False)),
                 ip=info.get("ipv4_address"))
            self._diag_last_wifi_state = self.state.wifi_state
        self.state.subsystems["controller"] = (
            "DISABLED" if not self.state.controller_enabled else
            "CONNECTED" if self.state.connection_state == "connected" else
            "OFFLINE" if self.state.connection_state != "connecting" else
            "CONNECTING")
        controller_state = "{}:{}".format(self.state.connection_state,
                                           self.state.machine_state)
        if controller_state != self._diag_last_controller_state:
            previous_connection = (
                self._diag_last_controller_state.split(":", 1)[0]
                if self._diag_last_controller_state is not None else None)
            if (previous_connection is not None and
                    previous_connection != self.state.connection_state):
                reset_encoder = getattr(self.input_manager,
                                        "reset_encoder", None)
                if reset_encoder is not None:
                    reset_encoder()
                self.state.mpg_activity = 0
                self.state.mpg_activity_timestamp = None
                self._diag_encoder_delta = 0
            emit("controller_state", state=self.state.connection_state,
                 machine=self.state.machine_state,
                 link=getattr(self.state, "link_state", None))
            self._diag_last_controller_state = controller_state
        self._update_indicator()
        self.display.render(self.state)
        self.state.render_count = getattr(self.display, "render_count", 0)
        # Low-priority, one-step nonblocking HTTP work runs only after safety,
        # inputs, transport, UI and display refresh have had their turn.
        if self.mirror is not None:
            self.mirror.poll()
            self.state.mirror_clients = self.mirror.completed_requests
            self.state.mirror_errors = self.mirror.client_errors
            self.state.mirror_error = self.mirror.last_error
        self.state.loop_count += 1
        finished = self.clock()
        self.state.last_loop_duration = max(0.0, finished - started)
        last = self.state.last_controller_response
        self.state.last_status_age = (None if last is None else
                                      max(0.0, finished - last))
        self.state.free_heap = gc.mem_free() if hasattr(gc, "mem_free") else None
        if self._diag_last_heartbeat is None or finished - self._diag_last_heartbeat >= 10.0:
            input_backend_configured = bool(
                getattr(self.input_manager.adapter, "configured", True))
            input_health = (
                "unknown" if not input_backend_configured or
                self.state.input_valid is None else
                ("valid" if self.state.input_valid else "invalid"))
            selector_health = (
                "unknown" if not input_backend_configured else
                ("valid" if self.state.selectors_valid else "invalid"))
            if not input_backend_configured or self.state.input_valid is None:
                axis_state = selector_position_state = "unknown"
                increment_state = deadman_state = "unknown"
            elif self.state.input_valid is False:
                axis_state = selector_position_state = "unavailable"
                increment_state = deadman_state = "unavailable"
            else:
                axis_state = (self.state.selected_axis or "OFF"
                              if self.state.selectors_valid else "invalid")
                selector_position_state = (
                    self.state.selected_physical_axis or "OFF"
                    if self.state.selectors_valid else "invalid")
                increment_state = (self.state.selected_multiplier
                                   if self.state.selectors_valid else "invalid")
                deadman_state = ("active" if self.state.deadman_enabled
                                 else "inactive")
            if self._diag_encoder_delta:
                emit("encoder_delta", delta=self._diag_encoder_delta,
                     axis=self.state.selected_axis or "OFF",
                     selector_position=(
                         self.state.selected_physical_axis or "OFF"),
                     increment=self.state.selected_multiplier,
                     deadman=self.state.deadman_enabled)
                self._diag_encoder_delta = 0
            emit("runtime", loops=self.state.loop_count,
                 renders=self.state.render_count,
                 free_heap=self.state.free_heap,
                 touch_samples=getattr(self.touch_manager, "sample_count", 0)
                               if self.touch_manager is not None else 0,
                 touch_events=getattr(self.touch_manager, "event_count", 0)
                              if self.touch_manager is not None else 0,
                 touch_errors=getattr(self.touch_manager, "consecutive_errors", 0)
                               if self.touch_manager is not None else 0,
                 mcp23017_read_errors=sum(
                     getattr(resource, "read_errors", 0)
                     for resource in getattr(
                         getattr(self.input_manager, "adapter", None),
                         "resources", ())),
                 input_backend=("configured" if input_backend_configured
                                else "disabled"),
                 input_validity=input_health,
                 selector_validity=selector_health,
                 axis=axis_state,
                 selector_position=selector_position_state,
                 increment=increment_state,
                 deadman=deadman_state,
                 wifi=self.state.wifi_state,
                 controller=self.state.connection_state)
            self._diag_last_heartbeat = finished
        if (self.state.free_heap is not None and self.state.free_heap < 32768 and
                (self._last_heap_warning is None or
                 finished - self._last_heap_warning >= 10.0)):
            print("runtime heap warning:", self.state.free_heap, "bytes free")
            self._last_heap_warning = finished

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
