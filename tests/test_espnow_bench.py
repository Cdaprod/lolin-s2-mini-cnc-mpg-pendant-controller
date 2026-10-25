"""Host-side validation for the receive-only ESP-NOW bench facade."""

import unittest
from src.transport.espnow_bench import EspNowBench


class FakeRadio:
    enabled = True


class FakePacket:
    def __init__(self, msg=b"hello", mac=bytes((1, 2, 3, 4, 5, 6))):
        self.msg = msg
        self.mac = mac


class FakeEspNow:
    def __init__(self):
        self.active = False
        self.queue = []

    def read(self):
        return self.queue.pop(0) if self.queue else None


class BenchTests(unittest.TestCase):
    def test_bound_and_discard(self):
        esp = FakeEspNow()
        esp.queue = [FakePacket() for _ in range(9)]
        bench = EspNowBench(FakeRadio(), esp, clock=lambda: 10)
        bench.start()
        bench.poll(budget=99)
        self.assertEqual(bench.received, 4)
        self.assertEqual(len(esp.queue), 5)
        self.assertFalse(bench.info()["motion_enabled"])
        self.assertEqual(bench.info()["last_length"], 5)
        bench.close()
        self.assertFalse(esp.active)

    def test_disabled_wifi_rejected(self):
        radio = FakeRadio()
        radio.enabled = False
        bench = EspNowBench(radio, FakeEspNow())
        with self.assertRaises(RuntimeError):
            bench.start()


if __name__ == "__main__":
    unittest.main()
