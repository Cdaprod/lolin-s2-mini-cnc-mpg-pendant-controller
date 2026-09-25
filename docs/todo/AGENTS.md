# Engineering ledger

Prepend new work under the applicable heading. Mark an item complete only when
its implementation, tests, and documentation are committed together. Do not
enable CNC motion merely to satisfy a task; each roadmap exit gate applies.

## 2026-09-25 — Physical XIAO stabilization

- [x] Route XIAO D4/D5 diagnostics and verified selectors through one shared
  I²C bus; keep scan results and errors independent of storage.
- [x] Defer bounded synchronous STA association to cooperative polling, verify
  reconnect attempts, and remove constructor-time provisioning scans.
- [x] Window long diagnostics, derive scene positions from round safe-area
  metrics, and allow offline navigation while motion remains inhibited.
- [x] Derive subsystem status from initialization/configuration results and
  retain independent network, storage, I²C, controller, input, display errors.
- [x] Reject stale/ordinary CIRCUITPY directories, bound macOS inspection, and
  diagnose the known Disk Arbitration/FSKit `Us` failure without remediation.
- [x] Expose sanitized deterministic Wi-Fi/AP/reconnect state through the
  shared runtime state, serial transitions, and round Network/Diagnostics UI.
- [x] Separate controller-offline labeling from Wi-Fi state and centralize the
  240×240 circular safe-area metrics used by the retained renderer.
- [x] Preserve disabled controller behavior even when round UI sample data is
  requested; sample rendering no longer fabricates network/storage health.
- [ ] Physically validate STA, AP fallback/HTTP, display safe area, SD status,
  and a non-destructive MCP23017 address scan on CircuitPython 10.3.1.

## 2026-09-25 — CircuitPython deployment reconciliation

- [x] Reconcile tracked defaults, optional repo-local settings, and active
  device settings while preserving device values and secrets by default.
- [x] Add explicit non-secret/secret sync, redacted plans, backups, staged
  writes, duplicate/profile validation, and dry-run/verify modes.
- [x] Restrict deployment to runtime files, manifest managed paths, and remove
  only stale files previously managed by this tool.
- [x] Add a dependency inventory and reject selected display profiles whose
  required CircuitPython modules are absent.
- [x] Test blank, stale, malformed, secret, profile, dependency, dry-run,
  idempotence, missing-volume, and verification cases on fake volumes.
- [ ] Run dry-run, deployment, repeated deployment, and verification against a
  backed-up physical XIAO ESP32-S3 CIRCUITPY volume.
- [ ] Confirm `boot_out.txt` board detection across each XIAO and the retained
  LOLIN profile before relying on mismatch warnings.

## 2026-09-25 — Common XIAO ESP32-S3 network bootstrap

- [x] Model Wi-Fi as a cooperative service with disabled, connecting,
  connected, setup-AP, reconnecting, and error states.
- [x] Load persisted credentials before settings defaults, fall back to a
  device-unique SoftAP, and provide an on-demand setup-AP menu action.
- [x] Serve a local credential form, persist successful credentials, stop the
  AP after STA connection, expire automatic setup mode, and advertise mDNS.
- [x] Keep controller, input, storage, and rendering polls independent of
  network availability and cover bootstrap transitions with host tests.
- [ ] Validate STA timeout behavior, SoftAP address, HTTP form submission, AP
  expiry, and `.local` discovery on physical XIAO ESP32-S3 hardware.
- [ ] Replace setup-time synchronous SSID enumeration with bounded incremental
  scanning after SoftAP-plus-scan behavior is verified on CircuitPython 10.3.1.
- [ ] Derive an optional MAC suffix for hostnames before provisioning multiple
  devices with the same product profile.
- [ ] Add captive-portal DNS/OS detection only after measuring its heap cost on
  the target CircuitPython build.

## 2026-09-23 — XIAO round-display HMI foundation

- [x] Separate board and display profiles while retaining the original
  `hardware_profile` compatibility path.
- [x] Add the XIAO ESP32-S3 board resources and independently selectable Seeed
  240×240 GC9A01 display/default wiring.
- [x] Add a retained round renderer with reusable ring, radial tabs, DRO,
  multiplier, connectivity, menu, and overlay components driven by UIManager.
- [x] Test profile binding, component mutation, dirty rendering, overlays, and
  compatibility with the existing UI navigation state machine.
- [ ] Validate the documented Seeed shield pin aliases and GC9A01 dependency on
  physical XIAO ESP32-S3 hardware before enabling CNC motion.
- [ ] Measure heap/frame timing and tune the production round layout on-device.

## 2026-09-21 — LOLIN S2 Mini reference pin profile

- [x] Encode the proposed LOLIN S2 Mini v1.0.0 pin allocation as an opt-in
  profile using actual CircuitPython `IO<n>` board aliases.
- [x] Keep all enable and electrical-verification gates false when the profile
  fills pin values; explicit settings continue to override profile values.
- [x] Implement and test cached MCP23017 selector inputs at address `0x20` for
  X/Y/Z/4/5/6 and x1/x10/x100, leaving GPB1–GPB7 spare.
- [x] Encode shared SPI metadata and allow the SD mount to consume an injected
  SPI bus for eventual sharing with the verified LCD driver.
- [x] Document reserved/spare pins, native USB/BOOT/onboard LED exclusions, and
  the GPIO12/GPIO13 silkscreen warning.
- [ ] Verify the selector contacts are dry, establish the correct `COM`
  reference, and approve the MCP23017 input circuit before setting
  `MPG_SELECTOR_INTERFACE_VERIFIED=true`.
- [ ] Identify the LCD controller/module and verify its voltage, control pins,
  offsets, backlight circuit, and the particular board's GPIO12/13 labeling.

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
