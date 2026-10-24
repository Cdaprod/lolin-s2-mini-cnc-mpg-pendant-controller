"""CircuitPython ESP-NOW C3 pairing/heartbeat diagnostics (NO CNC TX).

Source protocol: ennio64 ESP32-C3-Telnet-EspNow-Bridge-V1.3.1
PAIRED means radio-level pairing only; it grants NO machine-motion authority.
"""
import os
import time
from . import c3_espnow_protocol as proto

BROADCAST = bytes((255, 255, 255, 255, 255, 255))


class C3PairingBench:
    def __init__(self, radio=None, now=None, esp=None, session=None):
        if radio is None:
            import wifi
            radio = wifi.radio
        if esp is None:
            import espnow
            esp = espnow.ESPNow()
        self.radio = radio
        self.esp = esp
        self.now = now or time.monotonic
        if session is None:
            session = int.from_bytes(os.urandom(4), "little") or 1
        self.session = session
        self.local_mac = bytes(radio.mac_address)
        if len(self.local_mac) != 6:
            raise ValueError("invalid Wi-Fi MAC")
        self.peer = None
        self.last_rx = None
        self.last_pair = None
        self.last_heartbeat = None
        self.sequence = 0
        self.paired = False
        self.good = 0
        self.bad = 0

    def start(self):
        if not self.radio.enabled:
            raise RuntimeError("Wi-Fi disabled")
        self.esp.active = True
        # CircuitPython ESPNow.add_peer accepts a six-byte MAC.
        self.esp.add_peer(BROADCAST)

    def _send(self, mac, kind, payload=b""):
        packet = proto.encode(kind, self.session, self.sequence, payload)
        self.sequence = (self.sequence + 1) & 65535
        self.esp.send(packet, peer=mac)

    def poll(self):
        current = self.now()
        if self.last_rx is not None and current - self.last_rx > 5:
            self.paired = False
            self.peer = None
        for _ in range(4):
            packet = self.esp.read()
            if packet is None:
                break
            sender = bytes(packet.mac)
            try:
                kind, session, seq, payload = proto.decode(packet.msg)
                if kind == proto.PAIR_ACK and session == self.session:
                    peer_mac, _function = proto.validate_pair_ack(
                        packet.msg, self.session, self.local_mac)
                    if peer_mac != self.local_mac:
                        raise ValueError("pair ACK contains wrong local MAC")
                    self.esp.add_peer(sender)
                    self.peer = sender
                    self.paired = True
                    self.last_rx = current
                    self.good += 1
                elif self.paired and sender == self.peer and kind in (
                        proto.HEARTBEAT, proto.HEARTBEAT_ACK):
                    if session not in (0, self.session) or payload:
                        raise ValueError("invalid heartbeat")
                    self.last_rx = current
                    self.good += 1
                    if kind == proto.HEARTBEAT:
                        self._send(self.peer, proto.HEARTBEAT_ACK)
                else:
                    self.bad += 1
            except (ValueError, TypeError):
                self.bad += 1
        if not self.paired and (
                self.last_pair is None or current - self.last_pair >= 3):
            self.last_pair = current
            self._send(BROADCAST, proto.PAIR, self.local_mac)
        elif self.paired and (
                self.last_heartbeat is None or
                current - self.last_heartbeat >= 1):
            self.last_heartbeat = current
            self._send(self.peer, proto.HEARTBEAT)

    def info(self):
        return {
            "paired": self.paired,
            "bridge_mac": ":".join("%02x" % c for c in self.peer)
                          if self.peer else None,
            "valid_packets": self.good,
            "rejected_packets": self.bad,
            "motion_enabled": False,
        }

    def close(self):
        self.esp.active = False
