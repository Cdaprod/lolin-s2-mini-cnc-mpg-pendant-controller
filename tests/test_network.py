import os
import tempfile
import unittest

from src.network import CredentialStore, WiFiService


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


class NetworkTests(unittest.TestCase):
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
