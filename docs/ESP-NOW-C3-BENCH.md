# ESP32-S3 ↔ ESP32-C3 wireless MPG integration

This document describes the current firmware paths and the safe commissioning
sequence. Pairing proves only that the radios exchanged protocol messages; it
does not prove controller readiness or authorize machine motion.

## Controller modes

| `MPG_CONTROLLER_MODE` | Behavior | Motion behavior |
| --- | --- | --- |
| `disabled` | No machine controller transport. This is the default. | No controller commands. |
| `c3_espnow_bench` | Pairs and exchanges radio heartbeats/status diagnostics. | Does not send MPG jog intents. |
| `c3_espnow` | Uses the dedicated S3↔C3 MPG protocol and GRBL status path. | S3 sends bounded MPG intents only when physical input, deadman, E-stop, selector, and fresh controller-state gates pass. The C3 makes the final admission decision. |
| `bridge` | Uses Protocol v1 over a UART bridge. | `MPG_BRIDGE_MOTION_ENABLED` applies only to this mode. It does not enable or disable `c3_espnow`. |

The default profile in `settings.toml.example` keeps the controller and physical
inputs disabled. Copying the example therefore cannot select the wireless MPG
controller accidentally. A device's ignored `settings.toml` is user data; do
not replace it as part of testing.

## S3-to-C3 data path

In `c3_espnow` mode, the existing S3 application reads encoder and selector
state, rejects invalid input snapshots and selector transitions, and forms a
bounded per-detent intent. The packet carries axis X/Y/Z/A, deadman state,
signed distance in micrometers, feed, a session ID, and a 16-bit sequence. The
C3 decodes that vendor-compatible packet and uses its current GRBL status,
trusted S3 MAC, session/sequence state, deadman bit, source arbiter, and short
receiver lease before formatting a GRBL `$J=` command.

The S3 and C3 implementations are under review in [S3 PR #22](https://github.com/Cdaprod/lolin-s2-mini-cnc-mpg-pendant-controller/pull/22), [C3 MPG PR #6](https://github.com/Cdaprod/esp32-c3-cnc-bridge/pull/6), and [C3 console PR #4](https://github.com/Cdaprod/esp32-c3-cnc-bridge/pull/4). C3 PR #4 is stacked on PR #6. Their open-PR state is not evidence that a particular firmware image is installed on a device.

The C3 firmware defaults to `CONFIG_MPG_ENABLE_MOTION=n` and
`CONFIG_MPG_DRY_RUN=y`. In that configuration, production packet decoding,
session/sequence checks, fresh GRBL-state admission, jog formatting, and the
dry-run log execute, but `$J=` jog commands do not reach UART0. Dry-run requires
a locally provisioned trusted S3 MAC and a fresh status report. A log or ACK
must be read according to its result: a dry-run proposal is not a GRBL command
transmission, and ESP-NOW driver acceptance is not proof of over-the-air
delivery.

When explicitly built for physical jogging, the C3 keeps a 250 ms receiver
lease, checks status freshness, rejects duplicate/stale sequences, arbitrates
the UART against its other sender, and sends GRBL's real-time `0x85` jog-cancel
on STOP, lease expiry, or ownership loss. The cancel byte can stop an active
jog but cannot initiate motion. Radio pairing, a valid input packet, or a dry-
run result alone never authorizes a physical jog. An independent hardwired
machine E-stop remains required; wireless STOP is not safety-rated.

## C3-to-Doesbot boundary

The intended machine link is C3 UART0 at 115200 baud, TX GPIO21 and RX GPIO20,
through the documented 5 V↔3.3 V logic-level shifter. C3 USB Serial/JTAG is a
separate diagnostics connection. The dashboard's passive serial reader must
not share/open the C3 UART or send any CNC commands.

The dashboard shows validated GRBL status records that C3 parsed from UART0;
it marks them stale when fresh reports stop. The S3 also consumes controller
status forwarded by the C3. Stale status must remain disconnected and cannot
authorize motion. UART status query `?` is read-only; no `$J=`, spindle, homing,
or other motion-capable command is permitted during dry-run acceptance.

## Safe commissioning sequence

1. Keep the Doesbot motion/spindle disabled. Keep C3 firmware motion disabled
   and dry-run enabled. Do not flash or enable a motion-capable build for
   diagnostic testing.
2. Preserve the saved device configuration. When the documented MCP23017 and
   encoder harness is connected, enable only the intended S3 input backend and
   retain the `c3_espnow` controller mode only for the dedicated radio test.
3. Configure the C3 dry-run build with the S3 Wi-Fi MAC in
   `CONFIG_MPG_TRUSTED_MAC`. The USB serial UID is not that MAC.
4. Start the dashboard with one reader per USB device. Verify S3 runtime input
   snapshots, selector/deadman transitions, encoder deltas, ESP-NOW session and
   sequence events, C3 accepted/rejected admission, and a matching dry-run
   proposal. Do not treat a S3 transmit event as confirmed C3 receipt.
5. Test negative cases: deadman released, invalid selector/MCP read, stale GRBL
   status, duplicate/out-of-order sequence, timeout, and reconnect. Each must
   produce no `$J=` UART output; reconnect must not replay old encoder counts.
6. Use only an isolated GRBL simulator/mock for command-response tests. Do not
   send motion-capable commands to the Doesbot. Physical input validation can
   verify the dry-run signal chain without actuating the machine.

Only a separately authorized commissioning process may enable physical motion,
after physical input, machine interlocks, source ownership, and loss/recovery
behavior are independently verified. Neither PR #22, PR #6, nor a green build
changes the board configuration or authorizes motion.

## Evidence boundaries

- Host fixtures prove protocol vectors, admission gates, command formatting,
  dry-run UART isolation, and lifecycle logic covered by those tests.
- Prior live radio pairing/heartbeat observations prove radio exchange only;
  they do not prove current source compatibility or GRBL execution.
- Physical encoder/MCP input and Doesbot UART telemetry remain unverified until
  those exact signals are observed through the connected hardware and
  dashboard. Keep the historical S3 HARD_FAULT issue open until dispositioned
  with evidence.
