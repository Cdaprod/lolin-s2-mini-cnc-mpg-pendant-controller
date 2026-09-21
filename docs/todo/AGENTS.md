# Engineering ledger

Prepend new work under the applicable heading. Mark an item complete only when
its implementation, tests, and documentation are committed together. Do not
enable CNC motion merely to satisfy a task; each roadmap exit gate applies.

## 2026-09-21 — On-device hardware integration layer

- [x] Compose conditioned MPG, selector, button, dead-man, and observed E-stop
  input polling into `PendantApplication.poll()` before controller processing.
- [x] Implement bounded normalized events, debounce/short/long presses, and one
  contextual physical wheel stream with independent UI-motion safety gating.
- [x] Implement retained DisplayIO rendering, frame-change suppression, physical
  SD mount adapter, optional verified indicator output, and runtime diagnostics.
- [x] Centralize all optional hardware pin/configuration with safe disabled
  defaults and preserve the small root `code.py` composition entry point.
- [x] Add host tests for physical/synthetic input, application polling, E-stop
  preemption/recovery, DisplayIO retention/overlays, storage, and indicator.
- [ ] Obtain and verify the exact MPG interface, LCD, SD, Doesbot connector, LED
  driver, shield, and pin-allocation information listed in `docs/HARDWARE.md`.
- [ ] Run physical S2 Mini heap/timing, display readability, input trace, SD
  removal, Wi-Fi scan, and guarded unpowered-controller bench validation.

## 2026-09-21 — Cohesive HMI and contextual MPG

- [x] Define the authoritative IA, navigation grammar, handwheel modes, screen
  contracts, overlays, representative wireframes, and acceptance rules.
- [x] Implement UIManager with bounded navigation, focus, confirmations,
  dynamic files/macros/SSIDs, disabled entries, dirty state, and safe Home.
- [x] Implement reusable masked wheel-driven text entry and real Wi-Fi scan,
  connect/disconnect, and CircuitPython-appropriate credential persistence.
- [x] Expose jobs and macros through confirmation-driven UI workflows and route
  all UI commands through the application/service boundaries.
- [x] Independently gate MPG jogging on the central UI `MOTION` context.
- [x] Add overlay, navigation, text, job, macro, Wi-Fi, and same-wheel
  contextual end-to-end host tests.
- [ ] Select the physical display/controller and implement its thin `displayio`
  renderer against `UIManager.view_model()` without changing HMI behavior.
- [ ] Validate layout readability, heap use, dirty refresh cost, and HOLD/CANCEL/
  E-stop responsiveness on the physical S2 Mini.

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
