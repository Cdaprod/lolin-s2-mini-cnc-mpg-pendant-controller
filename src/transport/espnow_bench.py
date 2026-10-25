"""Fail-closed ESP-NOW packet transport for CircuitPython bench diagnostics.

This is deliberately NOT a GRBL or Protocol-v1 motion transport.
The vendor C3 bridge uses a separate, unverified ESP-NOW wire protocol.
Do not pass these packets to BridgeController or the CNC.
"""

import time


class EspNowBench:
    """Bounded receive-only diagnostics; no commands or machine motion."""

    def __init__(self, radio=None, espnow_instance=None, clock=None):
        if radio is None:
            import wifi
            radio = wifi.radio
        if espnow_instance is None:
            import espnow
            espnow_instance = espnow.ESPNow()
        self.radio = radio
        self.espnow = espnow_instance
        self.clock = clock or time.monotonic
        self.received = 0
        self.dropped = 0
        self.last_packet_at = None
        self.last_sender = None
        self.last_length = 0

    def start(self):
        if not self.radio.enabled:
            raise RuntimeError("Wi-Fi radio must be enabled for ESP-NOW")
        # ESP-NOW shares the channel of the associated Wi-Fi access point.
        if not self.espnow.active:
            self.espnow.active = True

    def poll(self, budget=4):
        """Drain at most four datagrams per poll; discard all payloads."""
        for _ in range(min(max(int(budget), 0), 4)):
            packet = self.espnow.read()
            if packet is None:
                break
            self.received += 1
            self.last_packet_at = self.clock()
            self.last_sender = bytes(packet.mac)
            self.last_length = len(packet.msg)
            # No decoding, forwarding, ACK, PAIR, or jog transmission.

    def info(self):
        return {
            "active": bool(self.espnow.active),
            "received": self.received,
            "dropped": self.dropped,
            "last_sender": self.last_sender.hex(":") if self.last_sender else None,
            "last_length": self.last_length,
            "last_packet_at": self.last_packet_at,
            "motion_enabled": False,
        }

    def close(self):
        self.espnow.active = False
