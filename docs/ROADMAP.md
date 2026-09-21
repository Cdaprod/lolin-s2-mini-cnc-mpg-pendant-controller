# Delivery roadmap

Milestones are dependency ordered. A later milestone cannot bypass the exit
criteria of an earlier safety gate.

## M0 — Product baseline (complete)

- Define product scope, priorities, exclusions, and release acceptance criteria.
- Separate standards-compliant USB-C from the direct machine connection.
- Define controller-reported DRO semantics rather than wheel-count estimation.
- Establish contextual controls, removable-storage, macro, and adapter targets.
- Record the provisional peripheral budget and MPG survey procedure.

**Exit:** Product and hardware requirements are reviewable without enabling
motion in firmware.

## M1 — Hardware evidence and feasibility

- Complete the `HARDWARE.md` 24-wire survey with photographs and measurements.
- Identify the Doesbot connector, protocol, voltage levels, and grounding.
- Choose the display, microSD interface, input expander, and keyed machine port.
- Produce a physical GPIO allocation with ESP32-S2 boot/USB constraints.
- Decide whether the S2 Mini has adequate pins, RAM, flash, and buses. Move to
  S3/custom hardware only if measured requirements fail this review.

**Exit:** Reviewed schematics/pinout have no unknown powered connections and at
least two spare GPIOs; every interface has a bench-verification plan.

## M2 — Testable input and state foundation

- Refactor the runtime into input, state, action/safety, controller-protocol,
  transport, and display boundaries without enabling output by default.
- Implement config schema/version validation and safe fallbacks.
- Implement quadrature decoding, selectors, buttons, long-press/chord behavior,
  debounce, and enable/dead-man handling behind hardware-neutral interfaces.
- Add desktop tests using fake pins and time.

**Exit:** Recorded input traces pass automated tests, invalid/bouncing input
fails closed, and disabled mode cannot emit a controller byte.

## M3 — Read-only GRBL status and display

- Implement a UART transport with bounded receive parsing and reconnect state.
- Parse GRBL status, response, alarm, and startup messages without sending
  motion; query status at no more than 5 Hz by default.
- Model machine/work coordinates, WCO, state, feed/spindle, pins, WCS, status
  age, and unknown fields.
- Render jog, disconnected, stale, alarm, and confirmation screens.

**Exit:** Transcript tests cover partial/interleaved/malformed messages, and a
bench controller shows correctly labeled controller-reported coordinates.

## M4 — Safe incremental MPG motion

- Implement named actions and controller-state interlocks.
- Generate explicit GRBL 1.1 `$J=` incremental commands from validated state.
- Track acknowledgements, bound queued distance, and implement jog cancel.
- Add watchdog and communication-loss fault latching.
- Validate first on a simulator, then an unpowered controller, then a guarded
  machine at reduced feed with an independent emergency stop.

**Exit:** All safe-input and motion acceptance criteria in `PRODUCT-SPEC.md`
pass; USB/Wi-Fi failure cannot silently leave the UI in a ready state.

## M5 — Machine functions and adapter release

- Implement guarded Home, Zero, Start, Hold, Reset, Unlock, Probe Z, and Safe Z.
- Make primary/FN mappings configurable and validate them fail-closed.
- Fabricate and document the Doesbot and generic UART adapters.
- Add connection/adapter identity indication and installation instructions.

**Exit:** Every action has state-table tests and explicit confirmation rules;
adapter pinouts and electrical tests are published.

## M6 — microSD browser and macros

- Mount/remount SD safely and browse allowed file types with bounded memory.
- Add versioned pendant configuration and declarative macro metadata.
- Execute macros through the same checked command/response engine as other
  actions; prohibit unreviewed or invalid macros.
- Handle card removal, I/O errors, long names, empty directories, and malformed
  files without blocking cancel/hold processing.

**Exit:** File and macro tests use temporary/in-memory resources and all errors
return to a non-commanding visible state.

## M7 — Standalone G-code streaming

- Implement simple send-response streaming first; optimize buffer utilization
  only after correctness and memory measurements.
- Track source line, acknowledged line, progress, controller push messages, and
  stream state independently.
- Implement confirmation, hold/resume, cancel, error/alarm handling, and an
  explicit no-auto-resume policy after reset/reconnect.
- Optionally preflight with GRBL check mode while preserving the warning that
  controller/modal behavior must be understood.

**Exit:** All standalone-job acceptance criteria pass transcript, fault
injection, and bench-controller tests before a powered machine test.

## M8 — Additional transports and controllers

- Add USB host/HID or UGS integration only through existing action/protocol and
  transport interfaces.
- Add grblHAL and FluidNC profiles based on captured protocol differences,
  feature negotiation, and compatibility tests.
- Add feed/spindle overrides and spindle controls with dedicated safety review.

**Exit:** Compatibility matrices and regression transcripts demonstrate that
new backends do not weaken GRBL safety behavior.

## Planned repository shape

Create modules when their milestone begins; empty scaffolding is intentionally
avoided.

```text
src/
  app.py              # cooperative runtime orchestration
  config.py           # validated configuration
  input/              # MPG, selectors, and buttons
  display/            # views and display adapter
  controller/         # protocol/state models
  transport/          # UART, USB, and Wi-Fi byte/message transport
  gcode/              # storage, macros, and streamer
  safety/             # interlocks, watchdog, action state machine
hardware/
  pcb/
  enclosure/
  adapters/
```

The current `src/controller.py` boundary is preserved until M2 replaces it with
a package in one atomic, tested refactor.
