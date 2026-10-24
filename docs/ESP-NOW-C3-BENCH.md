# ESP32-S3 CircuitPython ↔ ESP32-C3 bridge: bench integration

## Verified baseline

- PR #12 is merged: Protocol v1 reliable session is framed with CRC16, session IDs, motion lease, and host-side admission.
- PR #13 is merged: USB host *feasibility only*; not a USB host implementation.
- PR #15 is an unrelated draft USB status-only development track.
- The flashed third-party ESP32-C3 firmware v1.3.1 is associated with `cda_Lab` and obtains a pfSense DHCP address (observed `192.168.0.91`); its web UI advertises ESP-NOW waiting.
- **No interoperability has been demonstrated.** The C3 ESP-NOW protocol is not Protocol v1. Its "PAIR" and datagram layout have not been extracted or validated against the CircuitPython API.

## CircuitPython verification (no CNC attached)

1. Keep CNC UART disconnected; leave pendant controller mode `disabled` and bridge motion disabled.
2. On the actual XIAO ESP32-S3 REPL, check `import espnow; print(espnow)` and `import wifi; print(wifi.radio.enabled)`. Some CircuitPython versions/boards may not expose ESP-NOW.
3. With the pendant associated to `cda_Lab` and radio enabled, run the receive-only `EspNowBench` harness:
   ```python
   from src.transport.espnow_bench import EspNowBench
   bench = EspNowBench()
   bench.start()
   while True:
       bench.poll()
       # Debug readouts only; do not connect machine or send PAIR yet.
   ```
4. Confirm stable channel compatibility: C3 reported Wi-Fi/ESP-NOW channel 9. The C3 AP advertises 6 as its configured AP channel; AP+STA operation can follow the STA radio channel.
5. Inspect the exact C3 sources for ESP-NOW packet layouts, pairing and acknowledgement semantics, maximum payload, retransmission, stale data handling, and peer authentication. Document byte-level test vectors.
6. Implement **a versioned protocol adapter on both ends** or a verified compatibility transport; never send raw Protocol-v1 frames to an unmodified C3 receiver and assume they work.
7. Only after automated CRC/replay/disconnect tests, bounded receive tests, and bench heartbeat/pairing pass should status-only telemetry be enabled. Hardware motion remains disabled until independent safety approval.

## Design boundary

CircuitPython stays on ESP32-S3. The existing application, physical selectors, encoder, MCP23017, display and PR #12 host bridge remain intact. The receive-only bench module is deliberately not wired into `PendantApplication`. It does **not** interpret C3 packets or issue commands. Never use Wi-Fi/ESP-NOW as an emergency-stop safety chain. An independently wired machine E-stop is required.

## C3 integration backlog

- Capture and review the *exact flashed local C3 source revision*, including any local NVS sync/DHCP edits (these are not present in this repository).
- Align the C3 radio protocol with pendant session ACK/NAK, sequence, heartbeats and stale-motion rejection.
- Ensure stop on deadman release, loss of link, selector change, alarm, and software hang at the *controller side*; evaluate the GRBL hold/cancel semantics with spindle and steppers disabled.
- Disable/reset-on-Telnet-disconnect only after deciding an explicit, safe controller reset policy.
- Run real ESP32-S3/C3 cross-device tests and capture results before enabling any jog.
