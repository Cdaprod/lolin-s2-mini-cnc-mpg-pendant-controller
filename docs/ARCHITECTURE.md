# Architecture

## Goal

Keep physical control logic independent of the network/backend used to reach GRBL.

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
│  Pendant State Machine      │
│          │                  │
│          ▼                  │
│  Safety / Action Layer      │
│          │                  │
│          ▼                  │
│  Controller Interface       │
└──────────┬──────────────────┘
           │ Wi-Fi / serial
           ▼
     ┌───────────────┐
     │ Adapter       │
     ├───────────────┤
     │ UGS HTTP      │
     │ ESP3D         │
     │ direct GRBL   │
     └───────────────┘
```

## Design rules

1. Inputs never construct URLs or G-code directly.
2. Jogging must have explicit start/stop semantics.
3. Loss of communication must never be treated as a successful stop.
4. A future jog implementation should use a watchdog/dead-man mechanism.
5. Machine-state-changing actions should be explicit named actions.
6. Wi-Fi configuration stays in `settings.toml`, not source code.
