# Single-port USB-C / Doesbot CH34x feasibility gate

Status: **research and bench validation only**. No production USB host transport is implemented.

## Physical constraints

- Exactly one external USB-C connection on the pendant.
- Mac: pendant is a USB device for CircuitPython maintenance.
- Doesbot USB-B: pendant must be USB host and source protected 5V VBUS.
- USB charger: power-only behavior; no GRBL commands.
- No additional external UART, Ethernet, or proprietary signal cable.
- Do not repurpose USB D+/D- as raw UART. Do not feed 5V into ESP32-S3 GPIO.
- Hardwired E-stop is not replaced by software USB stop; a safety-rated stop remains a machine-level requirement.

## Confirmed controller enumeration (macOS)

User-observed USB descriptor: WCH VID 0x1A86, PID 0x7523, USB full speed (12 Mb/s).
Common CH340/CH341 USB-to-UART family; precise silicon variant unconfirmed.
Reported USB current 98 mA is a descriptor, not a load measurement.

## Firmware decision gate

1. Run `tools/probe_usb_capabilities.py` under the actual XIAO ESP32-S3 CircuitPython build.
2. Verify whether that specific CircuitPython port/build supports native `usb_host` and host transfers; Python module import alone is insufficient.
3. Determine whether USB host and USB device roles can be selected safely on the board; a reboot-based transition is acceptable.
4. Verify native host stack CH34x support, including vendor-specific setup, baud configuration, bulk endpoints, and disconnect behavior. Generic CDC ACM alone is not sufficient for 1A86:7523.
5. If CircuitPython does not expose host transfers, evaluate a custom CircuitPython build with native bindings, or a native ESP-IDF component with a Python-accessible interface. There is no pure-Python package that replaces the USB hardware driver.
6. Confirm USB-C CC wiring, VBUS switch/current limit, reverse-current protection, battery and external-power behavior using schematics and measurements. Never energize host VBUS before verification.

## Architecture contract

`GRBLController` remains responsible for GRBL 1.1 text commands/status.
`BridgeController` / Protocol v1 remain exclusively for the intermediary host bridge.
A future `USBHostSerialTransport` must implement the same transport API as `UARTTransport` but may not report connected until USB enumeration and CH34x setup succeed.

### Mandatory fail-closed behavior

- Default USB host motion disabled.
- USB unplug, role transition, read/write error, stale status, or reconnect: revoke pending jog and require fresh user input.
- Never replay queued motion on reconnect.
- Avoid claiming guaranteed motor stop on USB loss: GRBL may have accepted motion already. Limit jog segments and require fresh status/admission.
- Role switching must not be inferred solely from a USB-C-to-USB-B cable; explicit user mode selection or trustworthy hardware detection is needed.
- A host cannot enumerate a peripheral unless the 5V VBUS power path is correct.

## Next deliverable

Implement a host-driver proof-of-concept that enumerates 1A86:7523 and performs a read-only GRBL `?` status query on an isolated bench setup. Do not enable jogging until disconnect and stop behavior are hardware-tested.
