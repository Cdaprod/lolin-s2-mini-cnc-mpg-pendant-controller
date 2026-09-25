import os
import tempfile
import unittest

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

    def connect(self, ssid, password):
        self.connected = True
        self.ipv4_address = "192.0.2.10"

    def stop_station(self):
        self.connected = False

    def start_ap(self, ssid):
        self.ap_ssid = ssid

    def stop_ap(self):
        self.ap_ssid = None


class FailingRadio(FakeRadio):
    def connect(self, ssid, password):
        raise ConnectionError("password must never appear here")


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
        self.assertEqual(service.state, NetworkState.CONNECTED)
        self.assertEqual(service.info()["hostname"], "cnc-pendant")
        self.assertIsNone(radio.ap_ssid)

    def test_failed_station_falls_back_and_portal_reconnects(self):
        radio = FailingRadio()
        portal = FakePortal(("New Shop", "new secret"))
        service = self.make_service(radio, portal=portal)
        self.assertFalse(service.start("cnc-pendant", "Old Shop", "bad"))
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
