"""Cohesive pendant information architecture and contextual event router."""

from .text_entry import TextEntry

MOTION = "MOTION"
NAVIGATION = "NAVIGATION"
VALUE_EDIT = "VALUE_EDIT"
TEXT_ENTRY = "TEXT_ENTRY"
DISABLED = "DISABLED"

ROTATE_CW = "ROTATE_CW"
ROTATE_CCW = "ROTATE_CCW"
SELECT = "SELECT"
BACK = "BACK"
FN = "FN"
CANCEL = "CANCEL"
LONG_SELECT = "LONG_SELECT"
LONG_FN = "LONG_FN"


class UICommand:
    """Semantic output consumed by the application, never by a screen."""

    def __init__(self, name, value=None):
        self.name = name
        self.value = value

    def __repr__(self):
        safe = "<redacted>" if self.name == "NETWORK_CONNECT" else repr(self.value)
        return "UICommand({}, {})".format(self.name, safe)


class MenuItem:
    def __init__(self, label, target=None, command=None, value=None,
                 enabled=True, reason=""):
        self.label = label
        self.target = target
        self.command = command
        self.value = value
        self.enabled = bool(enabled)
        self.reason = reason


class Screen:
    def __init__(self, screen_id, title, parent, wheel_mode=NAVIGATION,
                 items=None, dynamic=None):
        self.id = screen_id
        self.title = title
        self.parent = parent
        self.wheel_mode = wheel_mode
        self.items = items or []
        self.dynamic = dynamic


def _disabled(label, reason):
    return MenuItem(label, enabled=False, reason=reason)


def build_screens():
    """Build the documented IA; unavailable backends are visibly disabled."""
    screens = {}
    screens["BOOT"] = Screen("BOOT", "BOOT — Connecting…", None, DISABLED)
    screens["HOME"] = Screen("HOME", "JOG / DRO", None, MOTION)
    screens["MAIN_MENU"] = Screen("MAIN_MENU", "MAIN MENU", "HOME", items=[
        MenuItem("Machine", "MACHINE"), MenuItem("Jobs", "JOBS"),
        MenuItem("Macros", "MACROS"), MenuItem("Controller", "CONTROLLER"),
        MenuItem("Network", "NETWORK"), MenuItem("Settings", "SETTINGS"),
        MenuItem("System / About", "SYSTEM"),
    ])
    machine = (
        ("Home", "HOME"), ("Zero Selected Axis", "ZERO_AXIS"),
        ("Zero XYZ", "ZERO_XYZ"), ("Probe Z", "PROBE_Z"),
        ("Safe Z", "SAFE_Z"), ("Park", "PARK"),
        ("Unlock", "UNLOCK"), ("Recover E-stop", "ESTOP_RECOVER"),
        ("Reset", "SOFT_RESET"),
    )
    screens["MACHINE"] = Screen("MACHINE", "MACHINE", "MAIN_MENU", items=[
        MenuItem(label, command="CONFIRM_ACTION", value=action)
        for label, action in machine
    ])
    screens["JOBS"] = Screen("JOBS", "JOBS", "MAIN_MENU", items=[
        MenuItem("Browse", "JOB_BROWSER"),
        _disabled("Recent", "job history is not implemented"),
        MenuItem("Active Job", "ACTIVE_JOB"),
    ])
    screens["JOB_BROWSER"] = Screen(
        "JOB_BROWSER", "SELECT FILE", "JOBS", dynamic="jobs"
    )
    screens["JOB_DETAILS"] = Screen("JOB_DETAILS", "JOB DETAILS", "JOB_BROWSER")
    screens["ACTIVE_JOB"] = Screen("ACTIVE_JOB", "ACTIVE JOB", "JOBS", items=[
        MenuItem("Hold", command="JOB_HOLD"),
        MenuItem("Resume", command="JOB_RESUME"),
        MenuItem("Cancel", command="CONFIRM_JOB_CANCEL"),
    ])
    screens["MACROS"] = Screen("MACROS", "MACROS", "MAIN_MENU", items=[
        MenuItem("Browse", "MACRO_BROWSER"),
        _disabled("Manage", "macro editing requires a future editor"),
    ])
    screens["MACRO_BROWSER"] = Screen(
        "MACRO_BROWSER", "SELECT MACRO", "MACROS", dynamic="macros"
    )
    screens["MACRO_DETAILS"] = Screen(
        "MACRO_DETAILS", "MACRO DETAILS", "MACRO_BROWSER"
    )
    controller = (
        "Status", "Identity", "Transport", "GRBL Info", "Pin State",
        "Diagnostics",
    )
    screens["CONTROLLER"] = Screen(
        "CONTROLLER", "CONTROLLER", "MAIN_MENU",
        items=[MenuItem(label, "CONTROLLER_INFO") for label in controller]
    )
    screens["CONTROLLER_INFO"] = Screen(
        "CONTROLLER_INFO", "CONTROLLER INFO", "CONTROLLER"
    )
    screens["NETWORK"] = Screen("NETWORK", "NETWORK", "MAIN_MENU", items=[
        MenuItem("Wi-Fi On / Off", command="NETWORK_TOGGLE"),
        MenuItem("Scan Networks", command="NETWORK_SCAN"),
        _disabled("Saved Networks", "saved-network browser is not implemented"),
        MenuItem("Manual SSID", command="NETWORK_MANUAL_SSID"),
        MenuItem("Start Setup AP", command="NETWORK_SETUP_AP"),
        MenuItem("Disconnect", command="NETWORK_DISCONNECT"),
        _disabled("Forget Network", "saved-network deletion is not implemented"),
        MenuItem("Network Info", "NETWORK_INFO"),
    ])
    screens["WIFI_SCAN"] = Screen(
        "WIFI_SCAN", "SELECT NETWORK", "NETWORK", dynamic="ssids"
    )
    screens["TEXT_ENTRY"] = Screen(
        "TEXT_ENTRY", "TEXT ENTRY", "NETWORK", TEXT_ENTRY
    )
    screens["NETWORK_INFO"] = Screen(
        "NETWORK_INFO", "NETWORK INFO", "NETWORK"
    )
    settings = ("Jog", "Units", "Display", "Controls", "MPG", "Safety",
                "Storage", "UI")
    screens["SETTINGS"] = Screen("SETTINGS", "SETTINGS", "MAIN_MENU", items=[
        _disabled(label, "settings editor is not implemented") for label in settings
    ])
    system = ("Firmware", "Hardware", "Storage", "Diagnostics", "Logs",
              "Version", "Restart")
    screens["SYSTEM"] = Screen("SYSTEM", "SYSTEM / ABOUT", "MAIN_MENU", items=[
        MenuItem(label, "SYSTEM_INFO") if label != "Restart" else
        MenuItem(label, command="CONFIRM_RESTART") for label in system
    ])
    screens["SYSTEM_INFO"] = Screen("SYSTEM_INFO", "SYSTEM INFO", "SYSTEM")
    return screens


class UIManager:
    """Bounded navigation, overlays, focus, text entry, and wheel ownership."""

    MAX_STACK = 8
    MAX_DYNAMIC_ITEMS = 64

    def __init__(self, state):
        self.state = state
        self.screens = build_screens()
        self.stack = ["BOOT"]
        self.focus = {}
        self.dynamic_items = {"jobs": [], "macros": [], "ssids": []}
        self.selected_job = None
        self.selected_macro = None
        self.selected_ssid = None
        self.manual_ssid = None
        self.text_entry = None
        self.text_purpose = None
        self.detail_title = None
        self.network_info = {}
        self.confirmation = None
        self.warning = None
        self.toast = None
        self.dirty = True
        self._sync_context()

    @property
    def current_screen(self):
        return self.stack[-1]

    @property
    def screen(self):
        return self.screens[self.current_screen]

    @property
    def handwheel_mode(self):
        overlay = self.active_overlay()
        if overlay and overlay[0] in (
                "ESTOP", "ALARM", "DISCONNECTED", "STREAM_ERROR"):
            return DISABLED
        if self.confirmation:
            return NAVIGATION
        return self.screen.wheel_mode

    def complete_boot(self):
        self.stack = ["HOME"]
        self._changed()

    def _changed(self):
        self.dirty = True
        self._sync_context()

    def _sync_context(self):
        self.state.ui_screen = self.current_screen
        self.state.ui_handwheel_mode = self.handwheel_mode

    def refresh_context(self):
        """Refresh overlay-derived ownership after shared state changes."""
        self._sync_context()

    def enter(self, screen_id):
        if screen_id not in self.screens:
            raise ValueError("unknown screen: " + screen_id)
        # Revoke motion before the destination becomes interactive.
        self.state.ui_handwheel_mode = DISABLED
        if len(self.stack) >= self.MAX_STACK:
            raise RuntimeError("navigation stack limit reached")
        self.stack.append(screen_id)
        self._changed()

    def home(self):
        self.confirmation = None
        self.text_entry = None
        self.stack = ["HOME"]
        self._changed()

    def back(self):
        if self.confirmation:
            self.confirmation = None
        elif self.current_screen == "TEXT_ENTRY":
            self.text_entry = None
            self.text_purpose = None
            self.stack.pop()
        elif len(self.stack) > 1:
            self.stack.pop()
        self._changed()

    def set_dynamic_items(self, name, values):
        if name not in self.dynamic_items:
            raise ValueError("unknown dynamic list: " + name)
        values = list(values)[:self.MAX_DYNAMIC_ITEMS]
        if self.dynamic_items[name] == values:
            return
        self.dynamic_items[name] = values
        self.focus[name] = min(self.focus.get(name, 0),
                               max(0, len(values) - 1))
        self._changed()

    def items(self):
        if self.screen.dynamic:
            if self.screen.dynamic == "ssids":
                return [MenuItem("{}  {} dBm".format(value[0], value[1]),
                                 value=value[0])
                        for value in self.dynamic_items["ssids"]]
            return [MenuItem(str(value), value=value)
                    for value in self.dynamic_items[self.screen.dynamic]]
        return self.screen.items

    def selected_item(self):
        items = self.items()
        if not items:
            return None
        index = self.focus.get(self.current_screen, 0) % len(items)
        return items[index]

    def rotate(self, delta):
        mode = self.handwheel_mode
        if mode == MOTION:
            return UICommand("JOG", 1 if delta > 0 else -1)
        if mode == TEXT_ENTRY and self.text_entry:
            self.text_entry.rotate(1 if delta > 0 else -1)
            self._changed()
            return None
        if mode in (NAVIGATION, VALUE_EDIT):
            if self.confirmation:
                self.confirmation["accept"] = not self.confirmation["accept"]
            else:
                items = self.items()
                if items:
                    key = self.current_screen
                    self.focus[key] = (self.focus.get(key, 0) + delta) % len(items)
            self._changed()
        return None

    def _start_text(self, title, purpose, masked=False, initial=""):
        self.text_entry = TextEntry(title, masked=masked, initial=initial)
        self.text_purpose = purpose
        self.enter("TEXT_ENTRY")

    def _confirm(self, title, command, value=None):
        self.confirmation = {
            "title": title, "command": command, "value": value,
            "accept": False,
        }
        self._changed()

    def _select_item(self):
        item = self.selected_item()
        if item is None or not item.enabled:
            if item is not None:
                self.toast = item.reason or "Unavailable"
                self._changed()
            return None
        if self.current_screen == "JOB_BROWSER":
            self.selected_job = item.value
            self.enter("JOB_DETAILS")
            return None
        if self.current_screen == "MACRO_BROWSER":
            self.selected_macro = item.value
            self.enter("MACRO_DETAILS")
            return None
        if self.current_screen == "WIFI_SCAN":
            self.selected_ssid = item.value
            self._start_text(item.label, "WIFI_PASSWORD", masked=True)
            return None
        if item.target:
            if item.target in ("CONTROLLER_INFO", "SYSTEM_INFO", "NETWORK_INFO"):
                self.detail_title = item.label
            self.enter(item.target)
            return None
        if item.command == "CONFIRM_ACTION":
            self._confirm(item.label + "?", "ACTION", item.value)
            return None
        if item.command == "CONFIRM_JOB_CANCEL":
            self._confirm("Cancel active job?", "JOB_CANCEL")
            return None
        if item.command == "CONFIRM_RESTART":
            self._confirm("Restart pendant?", "RESTART")
            return None
        if item.command == "NETWORK_SCAN":
            return UICommand("NETWORK_SCAN")
        if item.command == "NETWORK_MANUAL_SSID":
            self._start_text("SSID", "WIFI_SSID")
            return None
        return UICommand(item.command, item.value) if item.command else None

    def _select(self):
        if self.confirmation:
            modal = self.confirmation
            self.confirmation = None
            self._changed()
            if modal["accept"]:
                return UICommand(modal["command"], modal["value"])
            return UICommand("CONFIRM_REJECTED")
        if self.current_screen == "HOME":
            self.enter("MAIN_MENU")
            return None
        if self.current_screen == "JOB_DETAILS":
            self._confirm("Start {}?".format(self.selected_job),
                          "JOB_START", self.selected_job)
            return None
        if self.current_screen == "MACRO_DETAILS":
            self._confirm("Run {}?".format(self.selected_macro),
                          "MACRO_RUN", self.selected_macro)
            return None
        if self.current_screen == "TEXT_ENTRY":
            self.text_entry.accept()
            self._changed()
            return None
        return self._select_item()

    def _submit_text(self):
        value = self.text_entry.value
        purpose = self.text_purpose
        if purpose == "WIFI_SSID":
            self.manual_ssid = value
            self.text_entry = TextEntry(value, masked=True)
            self.text_purpose = "WIFI_PASSWORD"
            self._changed()
            return None
        if purpose == "WIFI_PASSWORD":
            ssid = self.selected_ssid or self.manual_ssid
            password = value
            self.text_entry.clear()
            self.text_entry = None
            self.text_purpose = None
            self.stack.pop()
            self._changed()
            return UICommand("NETWORK_CONNECT", (ssid, password))
        return None

    def handle(self, event):
        if (event == LONG_SELECT and self.state.estop_latched and
                not self.state.estop_observed):
            return UICommand("ACTION", "ESTOP_RECOVER")
        if event == ROTATE_CW:
            return self.rotate(1)
        if event == ROTATE_CCW:
            return self.rotate(-1)
        if self.handwheel_mode == DISABLED and event not in (BACK, CANCEL):
            return None
        if event == SELECT:
            return self._select()
        if event == LONG_SELECT and self.current_screen == "TEXT_ENTRY":
            return self._submit_text()
        if event == FN and self.current_screen == "TEXT_ENTRY":
            self.text_entry.next_group()
            self._changed()
            return None
        if event == CANCEL and self.current_screen == "HOME":
            return UICommand("ACTION", "JOG_CANCEL")
        if event == BACK and self.current_screen == "TEXT_ENTRY":
            self.text_entry.backspace()
            self._changed()
            return None
        if event in (BACK, CANCEL):
            self.back()
        return None

    def active_overlay(self):
        if self.state.estop_observed or self.state.estop_latched:
            return ("ESTOP", "E-STOP / INHIBITED", 100)
        if self.state.alarm is not None:
            return ("ALARM", "Controller alarm: " + str(self.state.alarm), 90)
        if self.state.connection_state not in ("connected", "connecting"):
            return ("DISCONNECTED", "Controller disconnected", 80)
        if self.state.sd_job_state in ("error", "alarm"):
            return ("STREAM_ERROR", self.state.error or "Streaming error", 70)
        if self.confirmation:
            return ("CONFIRMATION", self.confirmation["title"], 60)
        if self.warning:
            return ("WARNING", self.warning, 50)
        if self.toast:
            return ("TOAST", self.toast, 40)
        return None

    def view_model(self):
        """Return backend-independent primitives without exposing passwords."""
        items = self.items()
        selected = self.focus.get(self.current_screen, 0)
        model = {
            "screen": self.current_screen, "title": self.screen.title,
            "wheel_mode": self.handwheel_mode, "selected": selected,
            "items": [(item.label, item.enabled, item.reason) for item in items],
            "overlay": self.active_overlay(), "dirty": self.dirty,
        }
        if self.current_screen == "CONTROLLER_INFO":
            model["title"] = self.detail_title or model["title"]
            model["details"] = (
                ("Identity", self.state.controller_identity or "unknown"),
                ("Connection", self.state.connection_state),
                ("Machine", self.state.machine_state),
                ("Transport", self.state.transport),
                ("Pins", "".join(sorted(self.state.pin_state)) or "none"),
            )
        elif self.current_screen == "SYSTEM_INFO":
            model["title"] = self.detail_title or model["title"]
            model["details"] = (
                ("Job", self.state.sd_job_state),
                ("File", self.state.current_filename or "none"),
                ("UI", self.current_screen),
                ("Free heap", self.state.free_heap or "unknown"),
            )
        elif self.current_screen == "NETWORK_INFO":
            model["details"] = tuple(sorted(self.network_info.items()))
        if self.current_screen == "TEXT_ENTRY" and self.text_entry:
            model["text"] = self.text_entry.display_value()
            model["character"] = self.text_entry.selected_character
            model["group"] = self.text_entry.group_name
            model["masked"] = self.text_entry.masked
        if self.current_screen == "JOB_DETAILS":
            model["filename"] = self.selected_job
        if self.current_screen in ("JOBS", "JOB_BROWSER"):
            model["storage_state"] = self.state.storage_state
            model["storage_error"] = self.state.storage_error
        if self.current_screen == "MACRO_DETAILS":
            model["macro"] = self.selected_macro
        if self.current_screen == "ACTIVE_JOB":
            model["filename"] = self.state.current_filename
            model["progress"] = self.state.streaming_progress
            model["stream_state"] = self.state.sd_job_state
            model["controller_state"] = self.state.machine_state
            model["feed"] = self.state.feed_rate
            model["spindle"] = self.state.spindle_speed
        self.dirty = False
        return model
