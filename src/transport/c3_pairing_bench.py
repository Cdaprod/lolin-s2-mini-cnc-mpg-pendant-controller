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
        self.assigned_function = None
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
        self.rx_frames = 0
        self.tx_pair_requests = 0
        self.tx_heartbeats = 0
        self.rx_pair_acks = 0
        self.last_rx_error = None
        self.last_pair_ack_sender = None
        self.pair_ack_session_mismatch = 0
        self._last_diag = None

    def _packet_diag(self, direction, kind, sequence, peer, session=None,
                     result=None):
        names = {
            proto.PAIR: "pair", proto.PAIR_ACK: "pair_ack",
            proto.HEARTBEAT: "heartbeat", proto.HEARTBEAT_ACK: "heartbeat_ack",
            proto.SENSOR_ASSIGNMENT: "sensor_assignment",
            proto.MPG_JOG: "mpg_jog", proto.MPG_STOP: "mpg_stop",
            proto.MPG_JOG_ACK: "mpg_jog_ack", proto.MPG_STOP_ACK: "mpg_stop_ack",
            proto.UART_RESPONSE: "uart_response",
        }
        print("[event] event=espnow_{} packet_type={} session={} seq={} peer={} result={} uptime_ms={}".format(
            direction, names.get(kind, "0x{:02x}".format(kind)),
            self.session if session is None else session, sequence,
            ":".join("%02x" % byte for byte in peer) if peer else "broadcast",
            result or "driver_accepted_not_ota_ack", int(self.now() * 1000)))

    def start(self):
        if not self.radio.enabled:
            raise RuntimeError("Wi-Fi disabled")
        if hasattr(self.esp, "register_peer"):
            self.broadcast_peer = self.esp.register_peer(BROADCAST)
            return
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
        self._packet_diag("tx", kind, sequence, mac)
        if kind == proto.PAIR:
            self.tx_pair_requests += 1
        elif kind == proto.HEARTBEAT:
            self.tx_heartbeats += 1
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
        self._packet_diag("tx", proto.MPG_JOG, seq, self.peer)
        return seq

    def send_mpg_stop(self):
        if not self.paired or self.peer is None:
            return None
        return self._send(self.peer, proto.MPG_STOP)

    def poll(self):
        current = self.now()
        if self.last_rx is not None and current - self.last_rx > 5:
            old_peer = self.peer
            self.paired = False
            self.peer = None
            self.last_rx = None
            self.last_heartbeat = None
            print("[event] event=espnow_link state=lost reason=heartbeat_timeout peer={} uptime_ms={}".format(
                ":".join("%02x" % byte for byte in old_peer) if old_peer else "unknown",
                int(current * 1000)))
            # Retain registered peer object; re-registering stale MACs can
            # overflow the fixed CircuitPython ESP-NOW peer table.
        for _ in range(4):
            packet = self.esp.read()
            if packet is None:
                break
            sender = bytes(packet.mac)
            self.rx_frames += 1
            try:
                kind, session, seq, payload = proto.decode(packet.msg)
                if kind == proto.PAIR_ACK:
                    self.rx_pair_acks += 1
                    self.last_pair_ack_sender = ":".join("%02x" % x for x in sender)
                    if session != self.session:
                        self.pair_ack_session_mismatch += 1
                if kind == proto.PAIR_ACK and session == self.session:
                    peer_mac, assigned_function = proto.validate_pair_ack(
                        packet.msg, self.session, self.local_mac)
                    if peer_mac != self.local_mac:
                        raise ValueError("pair ACK contains wrong local MAC")
                    if sender == BROADCAST or sender == self.local_mac:
                        raise ValueError("invalid bridge MAC")
                    if self.unicast_peer is None or bytes(self.unicast_peer.mac) != sender:
                        if hasattr(self.esp, "register_peer"):
                            self.unicast_peer = self.esp.register_peer(sender)
                        else:
                            import espnow
                            candidate = espnow.Peer(mac=sender)
                            self.esp.peers.append(candidate)
                            self.unicast_peer = candidate
                    self.peer = sender
                    self.paired = True
                    self.assigned_function = assigned_function
                    self.last_heartbeat = None
                    self.last_rx = current
                    self.good += 1
                    self._packet_diag("rx", kind, seq, sender, session,
                                      "accepted_function_{}".format(assigned_function))
                    print("[event] event=espnow_link state=paired session={} peer={} assigned_function={} uptime_ms={}".format(
                        self.session, ":".join("%02x" % x for x in sender),
                        assigned_function, int(current * 1000)))
                elif (self.paired and sender == self.peer and
                      session == self.session and
                      kind == proto.SENSOR_ASSIGNMENT):
                    if (len(payload) != 1 or
                            (payload[0] > 6 and payload[0] != 255)):
                        raise ValueError("invalid sensor assignment")
                    self.assigned_function = payload[0]
                    self.last_rx = current
                    self.good += 1
                    self._packet_diag("rx", kind, seq, sender, session, "accepted")
                elif self.paired and sender == self.peer and kind in (
                        proto.HEARTBEAT, proto.HEARTBEAT_ACK):
                    if session not in (0, self.session) or payload:
                        raise ValueError("invalid heartbeat")
                    self.last_rx = current
                    self.good += 1
                    if kind == proto.HEARTBEAT:
                        self._send(self.peer, proto.HEARTBEAT_ACK)
                    self._packet_diag("rx", kind, seq, sender, session,
                                      "accepted")
                elif (self.paired and sender == self.peer and
                      session == self.session and kind in
                      (proto.MPG_JOG_ACK, proto.MPG_STOP_ACK, proto.UART_RESPONSE)):
                    if kind in (proto.MPG_JOG_ACK, proto.MPG_STOP_ACK) and len(payload) != 1:
                        raise ValueError("invalid MPG result")
                    if len(self.events) >= 16:
                        self.events.pop(0)
                    self.events.append((kind, seq, payload))
                    self.good += 1
                    self._packet_diag("rx", kind, seq, sender, session,
                                      "accepted_payload_{}".format(len(payload)))
                else:
                    self.bad += 1
                    self._packet_diag("rx", kind, seq, sender, session,
                                      "rejected_unpaired_or_unexpected")
            except (ValueError, TypeError) as exc:
                self.bad += 1
                self.last_rx_error = repr(exc)
                print("[event] event=espnow_rx_rejected peer={} reason={} uptime_ms={}".format(
                    ":".join("%02x" % x for x in sender),
                    type(exc).__name__, int(current * 1000)))
        if self._last_diag is None or current - self._last_diag >= 10:
            self._last_diag = current
            print("[espnow] paired=%s pair_tx=%d heartbeat_tx=%d rx=%d pair_acks=%d good=%d bad=%d last_error=%s" % (
                self.paired, self.tx_pair_requests, self.tx_heartbeats,
                self.rx_frames, self.rx_pair_acks, self.good, self.bad, self.last_rx_error))
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
            "assigned_function": self.assigned_function,
            "valid_packets": self.good,
            "rx_frames": self.rx_frames,
            "tx_pair_requests": self.tx_pair_requests,
            "tx_heartbeats": self.tx_heartbeats,
            "rx_pair_acks": self.rx_pair_acks,
            "pair_ack_session_mismatch": self.pair_ack_session_mismatch,
            "last_pair_ack_sender": self.last_pair_ack_sender,
            "last_rx_error": self.last_rx_error,
            "rejected_packets": self.bad,
            "motion_enabled": False,
        }

    def close(self):
        self.esp.deinit()
