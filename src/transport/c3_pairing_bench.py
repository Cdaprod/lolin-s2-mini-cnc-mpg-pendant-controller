"""CircuitPython ESP-NOW C3 pairing/heartbeat diagnostics (NO CNC TX).

Source protocol: ennio64 ESP32-C3-Telnet-EspNow-Bridge-V1.3.1
PAIRED means radio-level pairing only; it grants NO machine-motion authority.
"""
import os
import time
from . import c3_espnow_protocol as proto

BROADCAST = bytes((255, 255, 255, 255, 255, 255))


class C3PairingBench:
    name = "c3-espnow"
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
        self.broadcast_peer = None
        self.unicast_peer = None
        self.last_rx = None
        self.last_pair = None
        self.last_heartbeat = None
        self.sequence = 0
        self.paired = False
        self.good = 0
        self.bad = 0
        self.events = []

    def start(self):
        if not self.radio.enabled:
            raise RuntimeError("Wi-Fi disabled")
        import espnow
        self.broadcast_peer = espnow.Peer(mac=BROADCAST)
        self.esp.peers.append(self.broadcast_peer)

    def _send(self, mac, kind, payload=b""):
        sequence = self.sequence
        packet = proto.encode(kind, self.session, sequence, payload)
        self.sequence = (self.sequence + 1) & 65535
        target = self.broadcast_peer if mac == BROADCAST else self.unicast_peer
        if target is None or bytes(target.mac) != mac:
            raise RuntimeError("ESP-NOW peer not registered")
        self.esp.send(packet, peer=target)
        return sequence

    def send_mpg_jog(self, axis, microns, feed, deadman):
        if not self.paired or self.peer is None:
            return None
        seq = self.sequence
        packet = proto.encode_mpg_jog(self.session, seq, axis, microns, feed, deadman)
        self.sequence = (self.sequence + 1) & 65535
        if self.unicast_peer is None or bytes(self.unicast_peer.mac) != self.peer:
            raise RuntimeError("ESP-NOW peer not registered")
        self.esp.send(packet, peer=self.unicast_peer)
        return seq

    def send_mpg_stop(self):
        if not self.paired or self.peer is None:
            return None
        return self._send(self.peer, proto.MPG_STOP)

    def poll(self):
        current = self.now()
        if self.last_rx is not None and current - self.last_rx > 5:
            self.paired = False
            self.peer = None
            self.unicast_peer = None
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
                    if sender == BROADCAST or sender == self.local_mac:
                        raise ValueError("invalid bridge MAC")
                    import espnow
                    if self.unicast_peer is None or bytes(self.unicast_peer.mac) != sender:
                        candidate = espnow.Peer(mac=sender)
                        self.esp.peers.append(candidate)
                        self.unicast_peer = candidate
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
                elif (self.paired and sender == self.peer and
                      session == self.session and kind in
                      (proto.MPG_JOG_ACK, proto.MPG_STOP_ACK, proto.UART_RESPONSE)):
                    if kind in (proto.MPG_JOG_ACK, proto.MPG_STOP_ACK) and len(payload) != 1:
                        raise ValueError("invalid MPG result")
                    if len(self.events) >= 16:
                        self.events.pop(0)
                    self.events.append((kind, seq, payload))
                    self.good += 1
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
        self.esp.deinit()
