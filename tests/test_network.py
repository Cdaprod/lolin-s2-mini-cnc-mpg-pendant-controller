import os
import tempfile
import unittest
from unittest.mock import patch

from src.config import load_config
from src.network import (CredentialStore, NetworkState, PortalServer,
                         WiFiService)


class FakeNetwork:
    def __init__(self, ssid, rssi):
        self.ssid = ssid
        self.rssi = rssi


class FakeRadio:
    def __init__(self):
        self.enabled = True
        self.connected = False
        self.hostname = "pendant"
        self.ipv4_address = None
        self.ipv4_address_ap = "192.168.4.1"
        self.mac_address = bytes((0, 1, 2, 3, 0xA3, 0x1F))
        self.ap_ssid = None
        self.stopped_scan = False
        self.networks = [FakeNetwork("Shop", -50),
                         FakeNetwork("Lab", -20),
                         FakeNetwork("Shop", -40)]

    def start_scanning_networks(self):
        return iter(self.networks)

    def stop_scanning_networks(self):
        self.stopped_scan = True

    def connect(self, ssid, password, timeout=None):
        self.connect_timeout = timeout
        self.connected = True
        self.ipv4_address = "192.0.2.10"

    def stop_station(self):
        self.connected = False

    def start_ap(self, ssid):
        self.ap_ssid = ssid

    def stop_ap(self):
        self.ap_ssid = None


class FailingRadio(FakeRadio):
    def connect(self, ssid, password, timeout=None):
        raise ConnectionError("password must never appear here")


class CountingFailingRadio(FailingRadio):
    def __init__(self):
        super().__init__()
        self.attempts = 0

    def connect(self, ssid, password, timeout=None):
        self.attempts += 1
        super().connect(ssid, password, timeout)


class FailingAPRadio(FakeRadio):
    def start_ap(self, ssid):
        raise RuntimeError("radio unavailable")


class FakePortal:
    def __init__(self, credentials=None):
        self.credentials = credentials
        self.closed = False

    def poll(self):
        result = self.credentials
        self.credentials = None
        return result

    def deinit(self):
        self.closed = True


class FakeMDNS:
    def __init__(self):
        self.closed = False

    def deinit(self):
        self.closed = True


class NetworkTests(unittest.TestCase):
    def make_service(self, radio, clock=lambda: 0, portal=None):
        self.mdns = FakeMDNS()
        return WiFiService(
            radio, CredentialStore("/path/that/does/not/exist"), clock=clock,
            portal_factory=lambda unused_radio, unused_ssid: (
                portal or FakePortal()),
            mdns_factory=lambda unused_radio, unused_hostname: self.mdns,
        )

    def test_scan_deduplicates_and_orders_by_signal(self):
        radio = FakeRadio()
        service = WiFiService(radio, credential_store=None)
        self.assertEqual(service.scan(), [("Lab", -20), ("Shop", -40)])
        self.assertTrue(radio.stopped_scan)

    def test_default_hostname_identifies_cnc_pendant(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(load_config()["hostname"],
                             "cdaprod-cnc-pendant")

    def test_credentials_round_trip_without_repr_leak(self):
        with tempfile.TemporaryDirectory() as root:
            store = CredentialStore(os.path.join(root, "wifi.json"))
            store.save("Lab", "TopSecret")
            self.assertEqual(store.load(), ("Lab", "TopSecret"))
            self.assertNotIn("TopSecret", repr(store))
            store.forget()
            self.assertIsNone(store.load())

    def test_connect_persists_without_logging_password(self):
        with tempfile.TemporaryDirectory() as root:
            radio = FakeRadio()
            store = CredentialStore(os.path.join(root, "wifi.json"))
            service = WiFiService(radio, store)
            self.assertTrue(service.connect("Lab", "TopSecret"))
            self.assertEqual(store.load(), ("Lab", "TopSecret"))
            self.assertNotIn("TopSecret", repr(service.credentials))

    def test_boot_without_credentials_starts_named_fallback_ap(self):
        radio = FakeRadio()
        service = self.make_service(radio)
        self.assertFalse(service.start("cnc-pendant"))
        self.assertEqual(service.state, NetworkState.AP_SETUP)
        self.assertEqual(radio.ap_ssid, "Cdaprod-A31F-Setup")
        self.assertEqual(service.info()["ipv4_address"], "192.168.4.1")

    def test_successful_boot_starts_mdns_and_closes_ap(self):
        radio = FakeRadio()
        service = self.make_service(radio)
        self.assertTrue(service.start("cnc-pendant", "Shop", "secret"))
        self.assertEqual(service.state, NetworkState.CONNECTING)
        service.poll()
        self.assertEqual(service.state, NetworkState.CONNECTED)
        self.assertEqual(service.info()["hostname"], "cnc-pendant")
        self.assertIsNone(radio.ap_ssid)
        self.assertEqual(radio.connect_timeout, service.connect_timeout)

    def test_start_defers_bounded_association_until_poll(self):
        radio = FakeRadio()
        service = self.make_service(radio)
        self.assertTrue(service.start("pendant", "Shop", "secret"))
        self.assertEqual(service.state, NetworkState.CONNECTING)
        self.assertFalse(radio.connected)
        service.poll()
        self.assertTrue(radio.connected)

    def test_settings_credentials_reach_radio_without_password_log(self):
        messages = []
        radio = FakeRadio()
        service = WiFiService(radio, CredentialStore("/missing"),
                              portal_factory=lambda *_: FakePortal(),
                              mdns_factory=lambda *_: FakeMDNS(),
                              logger=messages.append)
        with patch.dict(os.environ, {"CIRCUITPY_WIFI_SSID": "Shop",
                                    "CIRCUITPY_WIFI_PASSWORD": "TopSecret"}):
            config = load_config()
        self.assertTrue(service.start("pendant", config["wifi_ssid"],
                                      config["wifi_password"]))
        service.poll()
        self.assertNotIn("TopSecret", " ".join(messages) + repr(service.info()))

    def test_lost_connection_reconnects_then_falls_back(self):
        now = [0]
        radio = FakeRadio()
        service = self.make_service(radio, clock=lambda: now[0])
        service.reconnect_attempts = 2
        service.start("pendant", "Shop", "secret")
        service.poll()
        radio.connected = False
        radio.connect = FailingRadio.connect.__get__(radio, FakeRadio)
        service.poll()
        self.assertEqual(service.state, NetworkState.RECONNECTING)
        now[0] += service.reconnect_interval
        service.poll()
        self.assertEqual(service.state, NetworkState.AP_SETUP)

    def test_reconnect_attempt_limit_is_exact(self):
        now = [0]
        radio = CountingFailingRadio()
        service = self.make_service(radio, clock=lambda: now[0])
        service.reconnect_attempts = 3
        service.ssid, service._password = "Shop", "secret"
        service.state = NetworkState.CONNECTED
        for expected in (1, 2):
            service.poll()
            self.assertEqual(radio.attempts, expected)
            self.assertEqual(service.state, NetworkState.RECONNECTING)
            now[0] += service.reconnect_interval
        service.poll()
        self.assertEqual(radio.attempts, 3)
        self.assertEqual(service.state, NetworkState.AP_SETUP)

    def test_lost_connection_can_reconnect(self):
        radio = FakeRadio()
        service = self.make_service(radio)
        service.start("pendant", "Shop", "secret")
        service.poll()
        radio.connected = False
        service.poll()
        self.assertEqual(service.state, NetworkState.CONNECTED)

    def test_ap_start_failure_is_diagnostic_error(self):
        service = self.make_service(FailingAPRadio())
        self.assertFalse(service.start("pendant"))
        self.assertEqual(service.state, NetworkState.ERROR)
        self.assertIn("RuntimeError", service.last_error)

    def test_failed_station_falls_back_and_portal_reconnects(self):
        radio = FailingRadio()
        portal = FakePortal(("New Shop", "new secret"))
        service = self.make_service(radio, portal=portal)
        self.assertTrue(service.start("cnc-pendant", "Old Shop", "bad"))
        service.poll()
        self.assertEqual(service.state, NetworkState.AP_SETUP)
        radio.connect = FakeRadio.connect.__get__(radio, FailingRadio)
        service.poll()
        self.assertEqual(service.state, NetworkState.CONNECTED)
        self.assertEqual(service.ssid, "New Shop")
        self.assertTrue(portal.closed)

    def test_automatic_ap_expires_without_blocking_runtime(self):
        now = [0]
        service = self.make_service(FakeRadio(), clock=lambda: now[0])
        service.ap_timeout = 10
        service.start("cnc-pendant")
        now[0] = 11
        service.poll()
        self.assertEqual(service.state, NetworkState.ERROR)
        self.assertEqual(service.last_error, "setup AP timed out")

    def test_portal_decodes_form_without_retaining_request(self):
        request = ("POST /configure HTTP/1.1\r\nContent-Length: 35\r\n\r\n"
                   "ssid=Workshop+Net&password=p%40ss")
        self.assertEqual(PortalServer._parse_credentials(request),
                         ("Workshop Net", "p@ss"))

    def test_portal_explains_that_ap_drops_during_connection(self):
        self.assertIn("setup network will disappear", PortalServer.SUBMITTED)
