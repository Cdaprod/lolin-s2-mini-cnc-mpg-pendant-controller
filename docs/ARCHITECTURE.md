# Architecture

## Goal

Keep physical controls, safety policy, controller protocol, transport, display,
and storage independent while sharing one `PendantState` instance.

```text
┌─────────────────────────────┐
│ Profile-selected ESP32-Sx   │
│ CircuitPython               │
│                             │
│  Inputs                     │
│  ├─ encoder                 │
│  ├─ axis selector           │
│  ├─ increment selector      │
│  └─ buttons                 │
│          │                  │
│          ▼                  │
│  Central PendantState       │
│          │                  │
│          ▼                  │
│  Safety / Action Layer      │
│          │                  │
│          ▼                  │
│  Controller Interface       │
└──────────┬──────────────────┘
           │ protocol-neutral transport
           ▼
     ┌───────────────┐
     │ Adapter       │
     ├───────────────┤
     │ UART (now)    │
     │ mock (tests)  │
     │ future ports  │
     └───────────────┘
```

## Design rules

1. Inputs never construct URLs or G-code directly.
2. Jogging must have explicit start/stop semantics.
3. Loss of communication must never be treated as a successful stop.
4. A future jog implementation should use a watchdog/dead-man mechanism.
5. Machine-state-changing actions should be explicit named actions.
6. Wi-Fi credentials come from the credential store or `settings.toml`, never
   from source code.

## Implemented module boundaries

- `code.py` is the CircuitPython-discovered composition entry point.
- `src/app.py` constructs and cooperatively polls the application components.
- `src/state.py` is the only shared pendant/controller/job state model.
- `src/input/` converts normalized electrical input into detents, selections,
  and semantic actions without performing I/O.
- `src/safety/` enforces fail-closed state policy and watchdog deadlines.
- `src/controller/grbl.py` owns GRBL 1.1 parsing and command serialization.
- `src/transport/` contains hardware UART and in-memory test transports.
- `src/storage/` reads job files incrementally; `src/gcode/` streams commands
  and loads bounded named macros.
- `src/display/` renders shared state and exposes a logical LED abstraction
  without assuming unverified LED drive voltage/current.
- `src/network.py` owns the reusable STA/fallback-SoftAP state machine,
  credential portal, persistence, and mDNS lifecycle. Network failure never
  blocks construction or polling of the pendant application.
- `tools/deploy.py` is the host-only provisioning boundary. It reconciles the
  tracked schema, optional ignored local settings, and active device settings;
  its manifest is the sole authority for stale runtime-file removal.

## Deployment boundary

Configuration reconciliation preserves active device values by default, uses
repo-local values for missing keys, then fills the remainder from tracked
defaults. Explicit local sync can replace non-secret values; secret sync needs
a separate flag. Profile and dependency validation happens before writes.
Deployment is restricted to `code.py`, `patterns.py`, `src/**/*.py`, and actual
vendored `lib/` modules. Host tests use temporary fake volumes, never hardware.

## HMI event boundary

`UIManager` owns the bounded navigation stack, focus, contextual wheel mode,
text editor, confirmation modal, and prioritized global overlays. It emits
semantic `UICommand` values; `PendantApplication` routes those commands to the
existing action, streamer, storage, macro, and network services. Screens never
call a backend directly.

The active UI handwheel mode is mirrored in `PendantState`. The safety layer
requires `MOTION` in addition to controller, selector, dead-man, alarm, and
E-stop checks. Therefore neither a display bug nor a menu transition can make a
navigation wheel event into machine motion. The complete contract lives in
`UI-IA-WIREFRAME.md`.

CircuitPython hardware imports are isolated in `src/transport/uart.py`. Future
GPIO/display/SD hardware adapters must retain this boundary so host tests can
exercise all policy and protocol logic.

## On-device cooperative integration

`PendantApplication.poll()` services the cooperative network state machine,
then samples the supplementary E-stop and controls, dispatches bounded
normalized UI events, services an incremental Wi-Fi
scan, polls GRBL and the streamer, evaluates watchdogs, refreshes UI ownership,
updates the optional indicator, and finally renders. No input adapter writes
GRBL and no screen reads GPIO.

`src/hardware.py` is the centralized optional-hardware composition boundary.
CircuitPython-only imports remain inside the UART, GPIO, DisplayIO, indicator,
and SD adapters and occur only when explicitly enabled. Unconfigured devices
degrade to null/console/filesystem implementations without selecting pins.

The configured CircuitPython MPG path uses `rotaryio` with raw transition
counting so edges are accumulated outside the Python polling cadence, then the
same bounded `InputManager` applies counts-per-detent and emits contextual
semantic wheel events. A polling decoder remains available for host simulation
and verified interfaces where `rotaryio` is intentionally disabled.

`src/hardware_profiles.py` fills otherwise blank assignments without enabling
hardware. The LOLIN S2 Mini profile places the MPG and E-stop observation on
native conditioned GPIO, UI buttons on local GPIO, GRBL on UART1 pins, LCD/SD
on shared SPI, and selector contacts on an MCP23017 using predefined I2C pins.
The minimal MCP23017 driver caches one 16-bit read per application poll, so UI
lookups do not cause repeated I2C transactions.

The DisplayIO backend accepts the already initialized display object and keeps
fixed header, body, footer, and overlay objects. It updates changed text only
and skips unchanged frames. It deliberately does not select an LCD controller,
bus, offsets, rotation, or pins.
