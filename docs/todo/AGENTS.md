# Engineering ledger

Prepend new work under the applicable heading. Mark an item complete only when
its implementation, tests, and documentation are committed together. Do not
enable CNC motion merely to satisfy a task; each roadmap exit gate applies.

## 2026-09-21 — Hardware-neutral firmware foundation

- [x] Record the manufacturer conductor map and replace the mystery-cable survey
  blocker with a focused electrical-verification gate.
- [x] Implement central state, quadrature/selectors/buttons, GRBL 1.1 protocol,
  semantic actions, fail-closed safety/watchdogs, and bounded jogging.
- [x] Implement UART/mock transports, display/indicator abstractions, incremental
  job storage, GRBL streaming, macros, and end-to-end host simulation tests.
- [x] Preserve root `code.py` as the small CircuitPython composition/event-loop
  entry point and recursively deploy source packages and `lib/` dependencies.
- [ ] Verify the listed electrical characteristics, select interface circuitry,
  and publish the reviewed physical GPIO and machine-port assignments.
- [ ] Add thin CircuitPython GPIO adapters for the verified pins and polarities,
  then validate recorded input traces on the unconnected bench pendant.

## 2026-09-21 — Product re-baseline

- [x] Define the complete pendant product, display, control, connectivity,
  storage, macro, and safety target.
- [x] Separate USB-C USB duties from a keyed, adapter-based machine port.
- [x] Define controller-reported DRO behavior and its open-loop limitation.
- [x] Add a dependency-ordered roadmap with measurable release gates.
- [x] Add a 24-wire MPG survey record and provisional GPIO/peripheral budget.
- [x] Replace the unknown-conductor inventory with the authoritative
  manufacturer function map while retaining all electrical unknowns.
- [ ] Verify the Doesbot connector identity, electrical levels, grounding, and
  serial protocol without connecting unknown signals to the S2 Mini.
- [ ] Select the display, microSD hardware, input expander, and keyed machine
  connector; then publish a reviewed physical GPIO allocation.
- [ ] Implement M2 only after the M1 hardware evidence gate passes.
