# LOLIN S2 Mini CNC MPG Pendant Controller

CircuitPython firmware for a standalone, controller-agnostic CNC MPG pendant
built around the **LOLIN S2 Mini (ESP32-S2)**. Generic GRBL 1.1 support is the
first implemented controller protocol.

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

Physical GPIO assignments remain intentionally unset until the documented
electrical measurements and interface design are complete. Firmware can be
developed and simulated without connecting unknown-voltage pendant signals.

## Documentation

- [`docs/PRODUCT-SPEC.md`](docs/PRODUCT-SPEC.md) — product and safety contract
- [`docs/HARDWARE.md`](docs/HARDWARE.md) — manufacturer wiring map, unresolved
  electrical properties, interface rules, and verification checklist
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — runtime boundaries and flow
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

`deploy.sh` recursively copies Python modules and `lib/` while preserving an
existing board `settings.toml`:

```bash
CIRCUITPY=/path/to/CIRCUITPY ./deploy.sh
```

## Configuration

Copy `settings.toml.example` to the CIRCUITPY root as `settings.toml`. The safe
default is:

```toml
MPG_CONTROLLER_MODE="disabled"
MPG_UART_TX_PIN=""
MPG_UART_RX_PIN=""
```

After electrical verification and a reviewed pin allocation, direct GRBL uses:

```toml
MPG_CONTROLLER_MODE="uart"
MPG_UART_TX_PIN="<CircuitPython board pin name>"
MPG_UART_RX_PIN="<CircuitPython board pin name>"
MPG_UART_BAUDRATE="115200"
```

Do not populate the pin names from guesswork. The machine UART and pendant MPG
inputs require their documented interface/protection circuitry.

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

## Host tests

Core modules avoid CircuitPython-only imports; `busio` and `board` are imported
only when constructing a real UART transport. Run the complete host suite with:

```bash
python -m unittest discover -v
python -m compileall -q code.py src tests
```

No external Python test dependency is required.
