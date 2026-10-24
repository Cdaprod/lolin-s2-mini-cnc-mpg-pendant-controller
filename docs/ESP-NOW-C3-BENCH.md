# ESP32-S3 CircuitPython ↔ ESP32-C3 bridge: bench integration

## Verified baseline

- PR #12 is merged: Protocol v1 reliable session is framed with CRC16, session IDs, motion lease, and host-side admission.
- PR #13 is merged: USB host *feasibility only*; not a USB host implementation.
- PR #15 is an unrelated draft USB status-only development track.
- The flashed third-party ESP32-C3 firmware v1.3.1 is associated with `cda_Lab` and obtains a pfSense DHCP address (observed `192.168.0.91`); its web UI advertises ESP-NOW waiting.
- **No hardware interoperability has been demonstrated.** The upstream C3 binary ESP-NOW v1 format is now extracted from `include/espnow_protocol.h` and `src/espnow_handler.c`. It is not the pendant PR #12 Protocol v1. The exact locally flashed C3 revision and CircuitPython on-board ESP-NOW API remain unverified.

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

## Implemented vendor-compatible radio diagnostics

The `src/transport/c3_espnow_protocol.py` module encodes and strictly decodes the vendor's **10-byte little-endian header** (version, type, 32-bit session, 16-bit sequence, 16-bit length), with 250-byte maximum packet size. The C3 source verifies that the new `PAIR` payload must begin with the sender's six-byte MAC, and replies with a 9-byte `PAIR_ACK` consisting of bridge-type 1, version 1, local sender MAC and assigned function.

`src/transport/c3_pairing_bench.py` sends only `PAIR`, `HEARTBEAT`, and `HEARTBEAT_ACK`. No `UART_COMMAND`, G-code, or jog packet is ever sent. The client's paired state only denotes an active radio link. Bench API is a candidate pending a CircuitPython hardware check; this module is intentionally not invoked automatically by the pendant app.

Example, on an isolated CircuitPython board with the C3 UART **disconnected**:

```python
from src.transport.c3_pairing_bench import C3PairingBench
bench = C3PairingBench()
bench.start()
while True:
    bench.poll()
    # Inspect bench.info() from a REPL/diagnostic harness.
```

The S3 must use the same Wi-Fi radio channel as the C3; if both join `cda_Lab` this should be verified from logs.

## Critical discovered C3 safety gap

The upstream `espnow_rx_task` `ESPNOW_MSG_UART_COMMAND` case forwards arbitrary packet payload to `serial_send_data`, appending a newline if not already present. Its `UART_ACK` confirms forwarding to the UART queue, **not GRBL execution**, and **does not use** the receiver-local motion lease from pendant PR #12.

Consequently, merely framing `$J=...` or realtime commands inside a vendor UART_COMMAND is **not sufficient** for safe remote CNC control. Before motion, implement explicit command allowlisting, source arbitration, status freshness, motion lease expiry and cancellation on the C3/controller side, with loss-of-radio fail-safe behavior, and test machine feedback thoroughly. Do not accidentally assume the C3's five-second peer heartbeat timeout is a safe CNC motion stop time.

## Remaining acceptance checklist

- [x] Identify upstream C3 binary header layout, PAIR requirements and heartbeat types.
- [x] Add strict host-testable encode/decode vectors and receive-only radio tests.
- [x] Add candidate CircuitPython ESP-NOW pairing/heartbeat helper, separate from app motion.
- [ ] Confirm the actual board's CircuitPython build supports the ESP-NOW class, peer API and Wi-Fi co-existence.
- [ ] Confirm an actual XIAO S3 MAC-address PAIR_ACK and heartbeat exchanged with the C3 firmware you flashed.
- [ ] Implement and validate a **safe C3 firmware extension** for a limited CNC command protocol with a receiver-side watchdog and stop callback; requires updating/flashing your local ESP-IDF C3 project.
- [ ] Route status messages to the existing pendant display/UI while keeping stale state disconnected.
- [ ] Integrate motion only after mechanical clearance, controller UART voltage, and deadman / link-loss verification.
