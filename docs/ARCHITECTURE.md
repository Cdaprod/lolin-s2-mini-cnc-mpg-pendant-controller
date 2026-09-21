# Architecture

## Goal

Keep physical controls, safety policy, controller protocol, transport, display,
and storage independent while sharing one `PendantState` instance.

```text
┌─────────────────────────────┐
│ LOLIN S2 Mini / ESP32-S2    │
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
6. Wi-Fi configuration stays in `settings.toml`, not source code.

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
