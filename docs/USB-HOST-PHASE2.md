# USB host phase 2: bench validation and DRO preparation

This phase extends merged PRs #12 and #13, **without claiming operational USB host support**.

## What changed

- Added `src/transport/grbl_status.py` to parse GRBL 1.1 status frames for future DRO updates. Parsing never grants motion authority.
- Added bounded `read(count)` access to already-validated status lines in the PR13 USB status-only transport; unsolicited GRBL text is not forwarded.
- Added status parsing and read-boundary regression tests.
- No native CH34x host backend, VBUS switching circuit, USB role switch, or physical jog functionality is implemented in this patch.

## Bench task for operator

1. On development computer, run `python -m unittest discover -s tests -p 'test_usb*.py' -v`.
2. Copy `tools/probe_usb_capabilities.py` to the XIAO ESP32-S3 CIRCUITPY drive.
3. Execute `import probe_usb_capabilities; probe_usb_capabilities.probe()` from the CircuitPython REPL.
4. Record board firmware version, module exports, and returned verification flags.
5. Do **not** attach USB-C directly to Doesbot USB-B as a host test, or energize VBUS, until CC and power-path verification is documented.
6. Once the protected host hardware is independently verified, implement actual WCH 1A86:7523 enumeration and vendor configuration; establish a read-only `?` status transaction before any jog implementation.

## Remaining gates

- VBUS power source / current limit / reverse blocking verified on actual XIAO and battery circuit.
- USB-C CC role identification and transition from CircuitPython maintenance/device role.
- Native CH340/CH341 host implementation, hardware endpoint and baud validation.
- Read-only status to live round-display DRO wiring.
- Motion authorization, short-segment jog and cancellation under disconnect/stale status.
- Wired vs ESP-NOW arbitration with no queued-motion replay.

Until these pass, the status-only transport is **not** a usable wired pendant, and test injection booleans are not evidence of hardware validation. Physical emergency stopping must remain independent of USB and wireless transport.
