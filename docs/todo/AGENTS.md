# Engineering ledger

Prepend new work under the applicable heading. Mark an item complete only when
its implementation, tests, and documentation are committed together. Do not
enable CNC motion merely to satisfy a task; each roadmap exit gate applies.

## 2026-09-21 — Product re-baseline

- [x] Define the complete pendant product, display, control, connectivity,
  storage, macro, and safety target.
- [x] Separate USB-C USB duties from a keyed, adapter-based machine port.
- [x] Define controller-reported DRO behavior and its open-loop limitation.
- [x] Add a dependency-ordered roadmap with measurable release gates.
- [x] Add a 24-wire MPG survey record and provisional GPIO/peripheral budget.
- [ ] Measure and record all 24 MPG conductors and controller-side signals in
  `docs/HARDWARE.md`, with connector photographs and a second-person review.
- [ ] Verify the Doesbot connector identity, electrical levels, grounding, and
  serial protocol without connecting unknown signals to the S2 Mini.
- [ ] Select the display, microSD hardware, input expander, and keyed machine
  connector; then publish a reviewed physical GPIO allocation.
- [ ] Implement M2 only after the M1 hardware evidence gate passes.
