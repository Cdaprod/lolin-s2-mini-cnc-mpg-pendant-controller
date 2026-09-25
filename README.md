# CircuitPython CNC MPG Pendant Controller

CircuitPython firmware for a standalone, controller-agnostic CNC MPG pendant
with independent XIAO ESP32-S3 and legacy LOLIN S2 Mini board profiles. Generic
GRBL 1.1 support is the first implemented controller protocol.

The firmware currently provides:

- a shared pendant/controller/job state model;
- validated quadrature decoding and X/Y/Z/4/5/6 selector mapping;
- x1/x10/x100 increment ratios;
- a generic GRBL 1.1 parser, real-time commands, semantic actions, and bounded
  incremental jogging;
- fail-closed E-stop observation, dead-man policy, and watchdogs;
- UART and host-test mock transports;
- controller-reported MPos/WPos/WCO coordinates (not physical scale feedback);
- display and indicator abstractions with a console renderer;
- incremental `.nc`, `.gcode`, and `.tap` access, send-response streaming, and
  file-backed macros;
- CPython tests including an MPG-to-GRBL-to-display simulation.
- a cooperatively polled physical-input pipeline for conditioned MPG A/B,
  selectors, configurable buttons, dead-man, and supplementary E-stop state;
- a retained-object DisplayIO renderer for an already initialized, explicitly
  configured display, plus optional configured SPI SD mounting and indicator
  output adapters.

Physical GPIO assignments remain intentionally unset until the documented
electrical measurements and interface design are complete. Firmware can be
developed and simulated without connecting unknown-voltage pendant signals.

## Documentation

- [`docs/PRODUCT-SPEC.md`](docs/PRODUCT-SPEC.md) — product and safety contract
- [`docs/HARDWARE.md`](docs/HARDWARE.md) — manufacturer wiring map, unresolved
  electrical properties, interface rules, and verification checklist
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — runtime boundaries and flow
- [`docs/UI-IA-WIREFRAME.md`](docs/UI-IA-WIREFRAME.md) — authoritative HMI tree,
  contextual wheel ownership, overlays, interaction rules, and wireframes
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — staged hardware/firmware integration
- [`docs/todo/AGENTS.md`](docs/todo/AGENTS.md) — engineering ledger

## CircuitPython entry point and filesystem

CircuitPython automatically discovers and executes root-level `code.py` on
startup and reload. It is deliberately a small composition/bootstrap layer: it
loads configuration, constructs `PendantApplication`, and runs the cooperative
event loop. Application modules are under `src/`. Any external CircuitPython
libraries must be placed under `lib/` so imports resolve on the board.

```text
CIRCUITPY/
├── code.py
├── patterns.py
├── settings.toml
├── src/
│   ├── app.py
│   ├── state.py
│   ├── controller/
│   ├── display/
│   ├── gcode/
│   ├── input/
│   ├── safety/
│   ├── storage/
│   └── transport/
└── lib/
```

`deploy.sh` deploys only runtime Python files and vendored `lib/` content. It
reconciles configuration with this default precedence:

```text
existing CIRCUITPY/settings.toml > repo-local settings.toml > settings.toml.example
```

Existing device values and secrets are preserved. Local values populate missing
keys, and tracked defaults fill the remaining schema:

```bash
CIRCUITPY=/path/to/CIRCUITPY ./deploy.sh --dry-run
CIRCUITPY=/path/to/CIRCUITPY ./deploy.sh
CIRCUITPY=/path/to/CIRCUITPY ./deploy.sh --verify
```

`--apply-local-settings` intentionally replaces existing non-secret values from
the ignored local file. `--apply-local-secrets` separately authorizes protected
credential replacement. Output remains redacted. The tool backs up settings,
stages replacements, records Git/profile/managed-file metadata, and removes
only stale files listed by its prior manifest. Run `./deploy.sh --help` for all
options.

Before a real deployment the tool checks host write access and aborts before
staging any file when the mounted target is read-only; it never attempts a
remount, host-service restart, or filesystem repair.

Manifest reconciliation accepts the narrowly retired historical `boot.py`
entry so a target written by the immediately preceding deployer can migrate
safely. A dry run reports it as `remove-managed`; an applied deployment removes
that formerly managed file and writes a new manifest containing only the
current runtime. Absolute, traversing, malformed, and unrelated root paths
remain invalid.

Deployment refuses a path that is not present in the host mount table and
requires a readable CircuitPython `boot_out.txt`; a stale directory named
`/Volumes/CIRCUITPY` is never a valid target. On macOS every `diskutil`
inspection has a bounded timeout. If the drive is absent and
`diskarbitrationd` is in the known stuck `Us` state, the tool prints this
operator-reviewed recovery command but never executes it:

```bash
sudo killall -9 com.apple.fskit.msdos fskit_helper fskitd fskit_agent diskarbitrationd DiskArbitrationAgent
```

Physical validation showed that restarting the stuck macOS FSKit/Disk
Arbitration processes changed the same connected XIAO from media/volume
read-only to writable without any CircuitPython storage change. There is no
repository `boot.py` storage workaround; recovery remains an explicit host
operator action after confirming the documented `Us` process state.

Do not remove the stale path, format the filesystem, or run the command unless
the process state has been confirmed. After recovery, unplug/replug the XIAO,
confirm `mount | grep CIRCUITPY`, then deploy with:

```bash
CIRCUITPY=/Volumes/CIRCUITPY ./deploy.sh
```

To observe first boot, connect USB, identify the CDC port with
`ls /dev/cu.usbmodem*`, then run `screen /dev/cu.usbmodemXXXX 115200` (exit with
Ctrl-A, then `k`, then `y`). The structured boot lines report display, storage,
SD, inputs, Wi-Fi, and controller independently.

## Configuration

`settings.toml.example` is the tracked schema/default inventory. The optional
ignored repo-local `settings.toml` contains per-device choices. Generic defaults
select no board/display and keep physical hardware disabled:

```toml
MPG_CONTROLLER_MODE="disabled"
MPG_UART_TX_PIN=""
MPG_UART_RX_PIN=""
MPG_BOARD_PROFILE=""
MPG_DISPLAY_PROFILE=""
```

At boot the network service first loads `/config/wifi.json`, then uses the
optional `CIRCUITPY_WIFI_SSID` settings. With no credentials, or after a failed
STA connection, it starts `Cdaprod-XXXX-Setup` and serves a setup form at
`http://192.168.4.1/`. The automatic AP expires after
`MPG_NETWORK_AP_TIMEOUT` seconds; **Network → Start Setup AP** starts it on
demand without that timeout. A successful connection stops the AP and enables
the configured `<hostname>.local` mDNS name. Network failure does not stop the
local UI, inputs, serial controller, or job runtime.

STA association starts from the cooperative application poll rather than the
application constructor. CircuitPython's association operation is synchronous,
so every call supplies `MPG_NETWORK_CONNECT_TIMEOUT`; reconnects are scheduled
between polls and never use an unbounded compatibility fallback.

The first XIAO pendant defaults to `cdaprod-cnc-pendant.local`. Override
`MPG_HOSTNAME` with another unique, lowercase name when provisioning additional
devices on the same network.

After electrical verification and a reviewed pin allocation, direct GRBL uses:

```toml
MPG_CONTROLLER_MODE="uart"
MPG_UART_TX_PIN="<CircuitPython board pin name>"
MPG_UART_RX_PIN="<CircuitPython board pin name>"
MPG_UART_BAUDRATE="115200"
```

Do not populate the pin names from guesswork. The machine UART and pendant MPG
inputs require their documented interface/protection circuitry.

All optional hardware is disabled when its pin/configuration values are blank.
`settings.toml.example` is the centralized inventory for UART, conditioned MPG,
selectors, buttons, dead-man/E-stop observation, board display, SD, and the
verified external indicator interface. Enabling inputs does not waive the
electrical verification requirements in `docs/HARDWARE.md`.

Board and display profiles remain independent. A repo-local configuration for
the round-display pendant can explicitly select both:

```toml
MPG_BOARD_PROFILE="xiao_esp32s3"
MPG_DISPLAY_PROFILE="seeed_round_240"
MPG_DISPLAY_ENABLED="true"
```

Other XIAO devices can leave `MPG_DISPLAY_PROFILE=""`. The legacy LOLIN S2
Mini/MCP23017 allocation remains supported without becoming a default:

```toml
MPG_HARDWARE_PROFILE="lolin_s2_mini_v1"
```

This reference profile uses CircuitPython's `IO<n>` aliases, shared predefined
SPI/I2C pins, native GPIO for conditioned MPG A/B, and MCP23017 inputs for the
slow selectors. Review the complete table and verification gates in
`docs/HARDWARE.md` before setting `MPG_INPUTS_ENABLED` or any verification flag.

## CircuitPython dependencies

`requirements-circuitpython.txt` is the deterministic dependency inventory.
Install it before selecting the Seeed round display:

```bash
circup --path /path/to/CIRCUITPY install -r requirements-circuitpython.txt
```

Deployment and `--verify` fail when a selected display profile's required
module is absent from both repository `lib/` and the mounted device.

## Runtime architecture

GPIO adapters emit normalized input events. Inputs never write serial data.

```text
normalized MPG/buttons/selectors
              │
              ▼
       central PendantState
              │
       semantic actions
              │
       safety/interlocks
              │
       GRBL 1.1 protocol
              │
        UART transport
              │
      controller / machine
```

GRBL status reports update the same central state consumed by the display and
streamer. A wheel event produces a bounded `$J=G91 ...` command only when the
connection, machine state, selector, dead-man, alarm, and observed E-stop state
are safe.

The software E-stop input is supplementary. The blue `C` and blue/black
`NC/CN` physical contact must interrupt the appropriate machine safety circuit
independently of the ESP32 and firmware.

The same physical MPG wheel is routed through `UIManager`: it creates semantic
jog events only on Home, and otherwise navigates menus, jobs, macros, SSIDs, or
text entry. `SafetyStateMachine` independently checks the mirrored UI ownership
before accepting a wheel-generated jog.

## Host tests

Core modules avoid CircuitPython-only imports; `busio` and `board` are imported
only when constructing a real UART transport. Run the complete host suite with:

```bash
python -m unittest discover -v
python -m compileall -q code.py src tests
```

No external Python test dependency is required.
