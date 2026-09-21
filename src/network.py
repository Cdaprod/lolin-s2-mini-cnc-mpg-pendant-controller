"""CircuitPython Wi-Fi service and credential persistence boundaries."""

import json
import os
import time


class NetworkState:
    def __init__(self):
        self.connected = False
        self.ip = None
        self.hostname = None


def connect_wifi(ssid, password, hostname, retries=3):
    import wifi
    state = NetworkState()

    wifi.radio.hostname = hostname
    state.hostname = hostname

    print("[net] hostname:", hostname)
    print("[net] connecting to:", ssid)

    last_error = None

    for attempt in range(1, retries + 1):
        try:
            if not wifi.radio.connected:
                wifi.radio.connect(ssid, password)

            state.connected = bool(wifi.radio.connected)
            state.ip = wifi.radio.ipv4_address

            print("[net] connected")
            print("[net] ip:", state.ip)
            print("[net] gateway:", wifi.radio.ipv4_gateway)
            print("[net] dns:", wifi.radio.ipv4_dns)
            return state

        except Exception as exc:
            last_error = exc
            print("[net] attempt", attempt, "failed:", repr(exc))
            time.sleep(1)

    raise RuntimeError("Wi-Fi connection failed: {}".format(last_error))


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
    """Non-UI Wi-Fi operations using CircuitPython's radio when invoked."""

    def __init__(self, radio=None, credential_store=None):
        if radio is None:
            import wifi
            radio = wifi.radio
        self.radio = radio
        self.credentials = credential_store or CredentialStore()
        self.last_error = None
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
        try:
            self.radio.connect(ssid, password)
        except Exception as exc:
            # Never retain or interpolate the password into errors.
            self.last_error = "Wi-Fi connection failed: {}".format(
                type(exc).__name__
            )
            return False
        if persist:
            try:
                self.credentials.save(ssid, password)
            except OSError:
                # The CIRCUITPY volume can be host-mounted/read-only. The radio
                # connection remains valid; persistence is reported separately.
                self.last_error = "connected; credential storage is read-only"
        return True

    def disconnect(self):
        self.radio.stop_station()

    def info(self):
        return {
            "enabled": self.enabled, "connected": self.connected,
            "hostname": self.radio.hostname,
            "ipv4_address": str(self.radio.ipv4_address)
            if self.radio.ipv4_address else None,
        }


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

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)

    def scan(self):
        return list(self.networks)

    def start_scan(self):
        self.scan_results = list(self.networks)[:32]
        self.scanning = False

    def poll_scan(self, budget=2):
        return True

    def connect(self, ssid, password, persist=True):
        self.connected = True
        self.ssid = ssid
        self.password_length = len(password)
        return True

    def disconnect(self):
        self.connected = False

    def info(self):
        return {"enabled": self.enabled, "connected": self.connected,
                "ssid": self.ssid}
