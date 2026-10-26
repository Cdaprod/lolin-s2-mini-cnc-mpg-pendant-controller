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
        if "/" in self.path:
            directory = self.path.rsplit("/", 1)[0]
        elif chr(92) in self.path:
            directory = self.path.rsplit(chr(92), 1)[0]
        else:
            directory = ""
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
                 reconnect_interval=10, connect_timeout=15,
                 reconnect_attempts=3, logger=print):
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
        self.reconnect_attempts = int(reconnect_attempts)
        self.logger = logger
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
        self._reconnect_count = 0
        self._connect_pending = False
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
        self._transition(NetworkState.CONNECTING, "SSID {}".format(ssid))
        self._connect_pending = True
        return True

    def _transition(self, state, detail=None):
        """Publish a sanitized transition; callers must never pass secrets."""
        if state != self.state:
            message = "wifi {:s} -> {:s}".format(self.state, state)
            if detail:
                message += " ({})".format(detail)
            if self.logger:
                self.logger(message)
        self.state = state

    def poll(self):
        """Service portal requests, loss of STA, reconnect, and AP expiry."""
        now = self.clock()
        entered_state = self.state
        if self.state == NetworkState.CONNECTING and self._connect_pending:
            self._connect_pending = False
            if not self._connect_saved():
                self.start_setup_ap()
        if self.state == NetworkState.CONNECTED and not self.connected:
            self._stop_mdns()
            self._reconnect_count = 0
            self._transition(NetworkState.RECONNECTING, "connection lost")
            self._next_reconnect = now
        if (self.state == NetworkState.RECONNECTING and
                now >= self._next_reconnect):
            self._reconnect_count += 1
            self._next_reconnect = now + self.reconnect_interval
            if self.connect(self.ssid, self._password or "", persist=False):
                self._reconnect_count = 0
            elif self._reconnect_count >= self.reconnect_attempts:
                self.start_setup_ap()
            else:
                self._transition(NetworkState.RECONNECTING,
                                 "attempt {} failed".format(self._reconnect_count))
        if self.state == NetworkState.AP_SETUP and entered_state == NetworkState.AP_SETUP:
            if self._portal:
                credentials = self._portal.poll()
                if credentials:
                    if not self.connect(credentials[0], credentials[1]):
                        self.start_setup_ap()
            if (self.state == NetworkState.AP_SETUP and
                    not self._manual_ap and self.ap_timeout > 0 and
                    now - self._ap_started >= self.ap_timeout):
                self._stop_ap()
                self._transition(NetworkState.ERROR)
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
            self._transition(NetworkState.AP_SETUP, "SSID {}".format(self.ap_ssid))
            self.last_error = None
            return True
        except Exception as exc:
            self._transition(NetworkState.ERROR)
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
            # CircuitPython's association call is synchronous. Its supported
            # timeout is always supplied so one cooperative poll is bounded.
            self.radio.connect(ssid, password, timeout=self.connect_timeout)
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
        self._transition(NetworkState.CONNECTED, "SSID {}".format(ssid))
        self._start_mdns()
        return True

    def disconnect(self):
        self.radio.stop_station()
        self._stop_mdns()
        self.state = NetworkState.DISABLED

    def deinit(self):
        """Close cooperative servers before the radio or runtime is reset."""
        self._stop_mdns()
        self._stop_ap()
        try:
            self.radio.stop_station()
        except (AttributeError, OSError, RuntimeError):
            pass
        self.state = NetworkState.DISABLED

    def info(self):
        result = {
            "enabled": self.enabled, "connected": self.connected,
            "state": self.state, "ssid": self.ssid,
            "hostname": self.hostname or self.radio.hostname,
            "ipv4_address": str(self.radio.ipv4_address)
            if self.radio.ipv4_address else None,
            "last_error": self.last_error,
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
        self._client = None
        self._request = bytearray(1024)
        self._request_size = 0
        self._request_length = None
        self._response = None
        self._response_offset = 0
        self._credentials = None
        self._client_started = 0.0
        self._time = time.monotonic

    @staticmethod
    def _build_form(radio):
        return ("<html><meta name=viewport content='width=device-width'>"
                "<h1>Wi-Fi setup</h1><form method=post action=/configure>"
                "SSID <input name=ssid required><br>Password "
                "<input name=password type=password><br>"
                "<button>Connect</button></form></html>")

    @staticmethod
    def _html_escape(value):
        return (value.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace("'", "&#39;")
                .replace('"', "&quot;"))

    def poll(self):
        """Advance one bounded portal socket operation; do not wait for clients."""
        if self.socket is None:
            return None
        now = self._time()
        if self._client is None:
            try:
                self._client, _ = self.socket.accept()
                self._client.setblocking(False)
                self._client_started = now
            except OSError:
                return None
            return None
        if now - self._client_started > 2.0:
            self._close_client()
            return None
        if self._response is None:
            remaining = len(self._request) - self._request_size
            if remaining <= 0:
                self._response_for(None)
            else:
                try:
                    received = self._client.recv_into(
                        memoryview(self._request)[self._request_size:])
                except OSError:
                    return None
                if received <= 0:
                    self._close_client()
                    return None
                self._request_size += received
                if not self._request_complete():
                    return None
                request = bytes(memoryview(self._request)[:self._request_size])
                try:
                    credentials = self._parse_credentials(request.decode("utf-8"))
                except UnicodeError:
                    credentials = None
                self._response_for(credentials)
                return None
        end = min(self._response_offset + 256, len(self._response))
        try:
            sent = self._client.send(
                memoryview(self._response)[self._response_offset:end])
        except OSError:
            return None
        if sent is None or sent <= 0:
            self._close_client()
            return None
        self._response_offset += sent
        if self._response_offset >= len(self._response):
            credentials = self._credentials
            self._close_client()
            return credentials
        return None

    def _request_complete(self):
        raw = bytes(memoryview(self._request)[:self._request_size])
        boundary = raw.find(b"\r\n\r\n")
        if boundary < 0:
            return False
        if self._request_length is None:
            header = raw[:boundary].decode("utf-8", "replace")
            first = header.split("\r\n", 1)[0]
            if first.startswith("POST /configure "):
                try:
                    self._request_length = int(next(
                        line.split(":", 1)[1].strip()
                        for line in header.split("\r\n")
                        if line.lower().startswith("content-length:")))
                except (StopIteration, ValueError):
                    self._request_length = -1
                if not 0 <= self._request_length <= 512:
                    self._request_length = -1
                    return True
            else:
                self._request_length = 0
        if self._request_length < 0:
            return True
        return self._request_size >= boundary + 4 + self._request_length

    def _response_for(self, credentials):
        self._credentials = credentials
        body = self.SUBMITTED if credentials else self.form
        encoded = body.encode("utf-8")
        header = ("HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n"
                  "Connection: close\r\nContent-Length: {}\r\n\r\n"
                  .format(len(encoded))).encode("utf-8")
        self._response = header + encoded
        self._response_offset = 0

    def _close_client(self):
        client = self._client
        self._client = None
        self._request_size = 0
        self._request_length = None
        self._response = None
        self._response_offset = 0
        self._credentials = None
        if client is not None:
            try:
                client.close()
            except OSError:
                pass

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
        ssid, password = values["ssid"], values.get("password", "")
        if len(ssid.encode("utf-8")) > 32 or len(password.encode("utf-8")) > 63:
            return None
        return ssid, password

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
        self._close_client()
        if self.socket is not None:
            self.socket.close()
            self.socket = None


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

    def deinit(self):
        self.connected = False
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
