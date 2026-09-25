"""Cooperative CircuitPython network bootstrap and configuration service."""

import json
import os
import time


class NetworkState:
    DISABLED = "DISABLED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    AP_SETUP = "AP_SETUP"
    RECONNECTING = "RECONNECTING"
    ERROR = "ERROR"


class CredentialStore:
    """Small JSON credential store; values are never exposed through repr."""

    def __init__(self, path="/config/wifi.json"):
        self.path = path

    def __repr__(self):
        return "CredentialStore(path={!r}, credentials=<redacted>)".format(
            self.path
        )

    def save(self, ssid, password):
        directory = self.path.rsplit("/", 1)[0]
        if directory:
            try:
                os.mkdir(directory)
            except OSError:
                pass
        temporary = self.path + ".tmp"
        with open(temporary, "w") as target:
            json.dump({"ssid": ssid, "password": password}, target)
        try:
            os.rename(temporary, self.path)
        except OSError:
            try:
                os.remove(self.path)
            except OSError:
                pass
            os.rename(temporary, self.path)

    def load(self):
        try:
            with open(self.path, "r") as source:
                data = json.load(source)
        except (OSError, ValueError):
            return None
        if not isinstance(data, dict) or not data.get("ssid"):
            return None
        return data.get("ssid"), data.get("password", "")

    def forget(self):
        try:
            os.remove(self.path)
        except OSError:
            pass


class WiFiService:
    """Own STA/AP transitions without making networking a boot prerequisite."""

    def __init__(self, radio=None, credential_store=None, clock=time.monotonic,
                 portal_factory=None, mdns_factory=None, ap_timeout=600,
                 reconnect_interval=10, connect_timeout=15):
        if radio is None:
            import wifi
            radio = wifi.radio
        self.radio = radio
        self.credentials = credential_store or CredentialStore()
        self.clock = clock
        self.portal_factory = portal_factory
        self.mdns_factory = mdns_factory
        self.ap_timeout = float(ap_timeout)
        self.reconnect_interval = float(reconnect_interval)
        self.connect_timeout = float(connect_timeout)
        self.last_error = None
        self.state = NetworkState.DISABLED
        self.hostname = None
        self.ssid = None
        self.ap_ssid = None
        self._password = None
        self._portal = None
        self._mdns = None
        self._ap_started = None
        self._manual_ap = False
        self._next_reconnect = 0
        self._scan_iterator = None
        self._scan_found = {}
        self.scan_results = []
        self.scanning = False

    @property
    def enabled(self):
        return bool(self.radio.enabled)

    @property
    def connected(self):
        return bool(self.radio.connected)

    def set_enabled(self, enabled):
        self.radio.enabled = bool(enabled)
        if not enabled:
            self._stop_ap()
            self._stop_mdns()
            self.state = NetworkState.DISABLED
        elif self.state == NetworkState.DISABLED:
            self.start(self.hostname or getattr(self.radio, "hostname", None) or
                       "xiao-dev")

    def start(self, hostname, ssid="", password=""):
        """Load credentials, attempt STA, then fall back to the setup AP."""
        self.hostname = hostname
        self.radio.hostname = hostname
        if not self.enabled:
            self.state = NetworkState.DISABLED
            return False
        saved = self.credentials.load()
        if saved:
            ssid, password = saved
        if not ssid:
            self.start_setup_ap()
            return False
        self.ssid, self._password = ssid, password
        self.state = NetworkState.CONNECTING
        return self._connect_saved()

    def poll(self):
        """Service portal requests, loss of STA, reconnect, and AP expiry."""
        now = self.clock()
        if self.state == NetworkState.CONNECTED and not self.connected:
            self._stop_mdns()
            self.state = NetworkState.RECONNECTING
            self._next_reconnect = now
        if (self.state == NetworkState.RECONNECTING and
                now >= self._next_reconnect):
            self._next_reconnect = now + self.reconnect_interval
            self._connect_saved()
        if self.state == NetworkState.AP_SETUP:
            if self._portal:
                credentials = self._portal.poll()
                if credentials:
                    if not self.connect(credentials[0], credentials[1]):
                        self.start_setup_ap()
            if (self.state == NetworkState.AP_SETUP and
                    not self._manual_ap and self.ap_timeout > 0 and
                    now - self._ap_started >= self.ap_timeout):
                self._stop_ap()
                self.state = NetworkState.ERROR
                self.last_error = "setup AP timed out"

    def start_setup_ap(self, manual=False):
        """Start the local configuration AP, either fallback or on demand."""
        self._stop_mdns()
        suffix = self._device_suffix()
        self.ap_ssid = "Cdaprod-{}-Setup".format(suffix)
        try:
            try:
                self.radio.stop_station()
            except (AttributeError, RuntimeError):
                pass
            self.radio.start_ap(self.ap_ssid)
            factory = self.portal_factory or self._default_portal_factory
            self._portal = factory(self.radio, self.ap_ssid)
            self._ap_started = self.clock()
            self._manual_ap = bool(manual)
            self.state = NetworkState.AP_SETUP
            self.last_error = None
            return True
        except Exception as exc:
            self.state = NetworkState.ERROR
            self.last_error = "setup AP failed: {}".format(type(exc).__name__)
            return False

    def _device_suffix(self):
        address = getattr(self.radio, "mac_address", None) or b"\x00\x00"
        return "".join("{:02X}".format(value) for value in address[-2:])

    def _connect_saved(self):
        if not self.ssid:
            return self.start_setup_ap()
        if self.connect(self.ssid, self._password or "", persist=False):
            return True
        self.start_setup_ap()
        return False

    def _start_mdns(self):
        self._stop_mdns()
        try:
            factory = self.mdns_factory or self._default_mdns_factory
            self._mdns = factory(self.radio, self.hostname)
        except (ImportError, OSError, RuntimeError) as exc:
            self.last_error = "connected; mDNS unavailable: {}".format(
                type(exc).__name__)

    def _stop_mdns(self):
        if self._mdns and hasattr(self._mdns, "deinit"):
            self._mdns.deinit()
        self._mdns = None

    def _stop_ap(self):
        if self._portal and hasattr(self._portal, "deinit"):
            self._portal.deinit()
        self._portal = None
        try:
            self.radio.stop_ap()
        except (AttributeError, RuntimeError):
            pass
        self._ap_started = None

    @staticmethod
    def _default_portal_factory(radio, ap_ssid):
        return PortalServer(radio, ap_ssid)

    @staticmethod
    def _default_mdns_factory(radio, hostname):
        import mdns
        server = mdns.Server(radio)
        server.hostname = hostname
        return server

    def scan(self):
        """Return deduplicated `(ssid, rssi)` values without retaining scans."""
        found = {}
        networks = self.radio.start_scanning_networks()
        try:
            for network in networks:
                ssid = str(network.ssid)
                rssi = int(network.rssi)
                if ssid and (ssid not in found or rssi > found[ssid]):
                    found[ssid] = rssi
        finally:
            self.radio.stop_scanning_networks()
        return sorted(found.items(), key=lambda item: item[1], reverse=True)

    def start_scan(self):
        if self.scanning:
            return
        self._scan_found = {}
        self.scan_results = []
        self._scan_iterator = iter(self.radio.start_scanning_networks())
        self.scanning = True

    def poll_scan(self, budget=2):
        """Consume a bounded number of scan results per cooperative poll."""
        if not self.scanning:
            return True
        for _ in range(budget):
            try:
                network = next(self._scan_iterator)
            except StopIteration:
                self.radio.stop_scanning_networks()
                self.scanning = False
                self._scan_iterator = None
                self.scan_results = sorted(
                    self._scan_found.items(), key=lambda item: item[1],
                    reverse=True
                )[:32]
                return True
            except Exception as exc:
                try:
                    self.radio.stop_scanning_networks()
                except Exception:
                    pass
                self.scanning = False
                self._scan_iterator = None
                self.last_error = "Wi-Fi scan failed: {}".format(
                    type(exc).__name__
                )
                return True
            ssid = str(network.ssid)
            rssi = int(network.rssi)
            if (ssid and (ssid not in self._scan_found or
                          rssi > self._scan_found[ssid])):
                self._scan_found[ssid] = rssi
        return False

    def connect(self, ssid, password, persist=True):
        self.last_error = None
        self._stop_ap()
        try:
            try:
                self.radio.connect(ssid, password, timeout=self.connect_timeout)
            except TypeError:
                # Host fakes and older CircuitPython builds lack this keyword.
                self.radio.connect(ssid, password)
        except Exception as exc:
            # Never retain or interpolate the password into errors.
            self.last_error = "Wi-Fi connection failed: {}".format(
                type(exc).__name__
            )
            return False
        self.ssid = ssid
        self._password = password
        if persist:
            try:
                self.credentials.save(ssid, password)
            except OSError:
                # The CIRCUITPY volume can be host-mounted/read-only. The radio
                # connection remains valid; persistence is reported separately.
                self.last_error = "connected; credential storage is read-only"
        self._stop_ap()
        self.state = NetworkState.CONNECTED
        self._start_mdns()
        return True

    def disconnect(self):
        self.radio.stop_station()
        self._stop_mdns()
        self.state = NetworkState.DISABLED

    def info(self):
        result = {
            "enabled": self.enabled, "connected": self.connected,
            "state": self.state, "ssid": self.ssid,
            "hostname": self.hostname or self.radio.hostname,
            "ipv4_address": str(self.radio.ipv4_address)
            if self.radio.ipv4_address else None,
        }
        if self.state == NetworkState.AP_SETUP:
            result["ssid"] = self.ap_ssid
            result["ipv4_address"] = str(getattr(
                self.radio, "ipv4_address_ap", "192.168.4.1"))
        if self.connected:
            result["rssi"] = getattr(self.radio, "ap_info", None)
            if result["rssi"] is not None:
                result["rssi"] = getattr(result["rssi"], "rssi", None)
        return result


class PortalServer:
    """Tiny cooperative HTTP form served only on the isolated setup AP."""

    SUBMITTED = ("Credentials received. The setup network will disappear "
                 "while the device attempts to connect.")

    def __init__(self, radio, ap_ssid):
        import socketpool
        self.ap_ssid = ap_ssid
        self.pool = socketpool.SocketPool(radio)
        self.socket = self.pool.socket()
        self.socket.setblocking(False)
        self.socket.bind(("0.0.0.0", 80))
        self.socket.listen(1)
        self.form = self._build_form(radio)

    @staticmethod
    def _build_form(radio):
        options = []
        try:
            networks = radio.start_scanning_networks()
            for network in networks:
                ssid = PortalServer._html_escape(str(network.ssid))
                if ssid and ssid not in options:
                    options.append(ssid)
        except (AttributeError, OSError, RuntimeError):
            pass
        finally:
            try:
                radio.stop_scanning_networks()
            except (AttributeError, OSError, RuntimeError):
                pass
        choices = "".join("<option value='{}'>{}</option>".format(item, item)
                          for item in options[:32])
        return ("<html><meta name=viewport content='width=device-width'>"
                "<h1>Wi-Fi setup</h1><form method=post action=/configure>"
                "SSID <input name=ssid list=networks required>"
                "<datalist id=networks>{}</datalist><br>Password "
                "<input name=password type=password><br>"
                "<button>Connect</button></form></html>").format(choices)

    @staticmethod
    def _html_escape(value):
        return (value.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace("'", "&#39;")
                .replace('"', "&quot;"))

    def poll(self):
        try:
            client, _ = self.socket.accept()
        except OSError:
            return None
        try:
            client.settimeout(0.1)
            request = client.recv(1024).decode("utf-8")
            credentials = self._parse_credentials(request)
            body = self.SUBMITTED if credentials else self.form
            response = ("HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n"
                        "Connection: close\r\nContent-Length: {}\r\n\r\n{}"
                        .format(len(body), body))
            client.send(response.encode("utf-8"))
            return credentials
        finally:
            client.close()

    @staticmethod
    def _parse_credentials(request):
        if not request.startswith("POST /configure ") or "\r\n\r\n" not in request:
            return None
        body = request.split("\r\n\r\n", 1)[1]
        values = {}
        for field in body.split("&"):
            key, separator, value = field.partition("=")
            if separator:
                values[key] = PortalServer._url_decode(value)
        if not values.get("ssid"):
            return None
        return values["ssid"], values.get("password", "")

    @staticmethod
    def _url_decode(value):
        value = value.replace("+", " ")
        output = ""
        index = 0
        while index < len(value):
            if value[index] == "%" and index + 2 < len(value):
                try:
                    output += chr(int(value[index + 1:index + 3], 16))
                    index += 3
                    continue
                except ValueError:
                    pass
            output += value[index]
            index += 1
        return output

    def deinit(self):
        self.socket.close()


class MockWiFiService:
    """Host-test Wi-Fi service with no credential logging or global state."""

    def __init__(self, networks=None):
        self.networks = list(networks or [])
        self.enabled = True
        self.connected = False
        self.ssid = None
        self.password_length = 0
        self.scan_results = []
        self.scanning = False
        self.state = NetworkState.DISABLED
        self.hostname = None

    def start(self, hostname, ssid="", password=""):
        self.hostname = hostname
        if ssid:
            return self.connect(ssid, password)
        self.state = NetworkState.AP_SETUP
        return False

    def poll(self):
        return None

    def start_setup_ap(self, manual=False):
        self.state = NetworkState.AP_SETUP
        return True

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        if not enabled:
            self.state = NetworkState.DISABLED

    def scan(self):
        return list(self.networks)

    def start_scan(self):
        self.scan_results = list(self.networks)[:32]
        self.scanning = False

    def poll_scan(self, budget=2):
        return True

    def connect(self, ssid, password, persist=True):
        self.connected = True
        self.state = NetworkState.CONNECTED
        self.ssid = ssid
        self.password_length = len(password)
        return True

    def disconnect(self):
        self.connected = False
        self.state = NetworkState.DISABLED

    def info(self):
        return {"enabled": self.enabled, "connected": self.connected,
                "state": self.state, "hostname": self.hostname,
                "ssid": self.ssid}
