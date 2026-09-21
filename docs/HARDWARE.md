# Hardware definition

## Status

This is a requirements and measurement document, not a fabrication-ready
pinout. The actual MPG cable and target controller must be surveyed before any
signal is attached to the LOLIN S2 Mini. Unknown conductors must remain marked
`TBD`; guesses must not be promoted to pin assignments.

## Physical architecture

```text
                         PENDANT
       ┌────────────────────────────────────┐
       │ LOLIN S2 Mini / CircuitPython      │
       │ MPG inputs   display   buttons     │
       │                  shared SPI ── SD  │
       └───────┬───────────────────┬────────┘
               │                   │
          USB-C (USB)       keyed machine port
               │                   │
          PC / power        replaceable adapter
                                   ├── Doesbot
                                   └── generic GRBL UART
```

The onboard USB-C receptacle retains standards-compliant USB functions only.
The machine port must be mechanically keyed and must not be USB-C, micro-USB,
or another connector commonly assumed to carry USB. Controller-specific
voltage conversion, isolation, power selection, and pin rearrangement live in
the replaceable adapter, not in an undocumented cable.

## Required assemblies

1. S2 Mini carrier with protected MPG inputs, display/storage buses, button
   inputs, and a keyed machine-port receptacle.
2. Short replaceable machine cable.
3. Doesbot adapter based on a verified connector pinout and voltage survey.
4. Generic GRBL UART adapter with explicit TX, RX, signal ground, and optional
   isolated power policy.
5. Enclosure that prevents strain on the board USB connector and provides SD
   access without exposing energized electronics.

## Electrical rules

- Treat all MPG and controller conductors as unknown until measured.
- Never connect an unknown signal directly to a 3.3 V GPIO.
- Inputs require voltage compatibility and appropriate pull-up/down, series
  resistance, filtering, and ESD protection selected after measurement.
- Outputs to a 5 V controller require a verified level-shifting strategy.
- A shared ground is permitted only after checking for hazardous potential and
  ground-loop implications; otherwise use galvanic isolation.
- Cable shield/drain is bonded according to the measured machine grounding
  scheme and is never silently used as signal ground.
- The pendant must not back-power the controller, or be back-powered through a
  GPIO/UART signal, in any USB/controller power combination.
- External emergency-stop and machine enable circuits do not pass through or
  depend on pendant firmware.

## Machine-port contract

The final keyed connector must provide only signals justified by the selected
transport. The preferred minimal contract is:

| Signal | Direction at pendant | Requirement |
| --- | --- | --- |
| `UART_TX` | Output | 3.3 V logic at carrier; adapter translates/isolates as required |
| `UART_RX` | Input | Protected 3.3 V logic at carrier |
| `SIGNAL_GND` | Reference | Connected only under the approved isolation/power design |
| `ADAPTER_ID` | Input | Optional passive identification; fail closed if unknown |
| `CTRL_PRESENT` | Input | Optional protected controller/adapter presence signal |
| `AUX_3V3` | Output | Optional, current-limited adapter logic power; never controller power |
| Reserved | — | At least two contacts for a later verified need |

The final connector family, contact count, current rating, latch, pin order,
and mating cable remain open until the Doesbot survey. The machine port must be
labeled `MACHINE — NOT USB` on PCB and enclosure.

## Peripheral and GPIO budget

This budget determines feasibility before assigning physical pins. Counts are
worst-case direct GPIO requirements; shared buses and an expander reduce them.

| Function | Interface | Direct GPIO | Notes |
| --- | --- | ---: | --- |
| MPG encoder | digital inputs | 2 | A/B; interrupt-capable preferred |
| Axis selector | digital inputs | 4–6 | Actual common/contact topology unknown |
| Increment selector | digital inputs | 3 | Actual topology unknown |
| Enable/dead-man | digital input | 1 | Dedicated, fail-safe polarity |
| Function buttons | digital inputs | 7 | May move to I2C expander |
| Machine controller | UART | 2 | Dedicated RX/TX |
| Display | I2C or SPI | 2–5 | Select display only after UI/layout test |
| microSD | shared SPI | 1 extra | SCK/MOSI/MISO shared; dedicated CS |
| Input expander | shared I2C | 0 extra | Uses display SDA/SCL if electrically compatible |
| Adapter identification | analog/digital | 1 | Optional but preferred |
| Buzzer/haptic/status LED | outputs | 1–3 | Optional, transistor driver as required |

Direct wiring can demand 23 or more GPIOs before optional feedback and is not a
safe assumption. The preferred architecture is:

- encoder A/B and enable on dedicated GPIO;
- UART on dedicated GPIO;
- display and input expander on shared I2C, if the chosen display is I2C;
- microSD on SPI with a dedicated chip-select;
- selector and function-button contacts on the input expander;
- at least two uncommitted GPIOs after accounting for board boot/USB constraints.

No physical GPIO number is assigned until the conductor survey, chosen display,
chosen SD breakout, CircuitPython board pin aliases, and ESP32-S2 boot-strapping
constraints have all been checked together.

## 24-wire MPG survey

### Equipment

- disconnected pendant and controller;
- multimeter with continuity, resistance, diode, and DC-voltage modes;
- current-limited bench supply only if passive measurements are insufficient;
- oscilloscope or logic analyzer for powered encoder verification;
- breakout leads, labels, and photographs of both connector faces.

### Procedure

1. Photograph the cable, connector orientation, PCB markings, selectors, all
   switches, and handwheel. Assign conductor IDs `W01` through `W24` by color
   and connector position; do not rely on color alone.
2. With all power removed, map continuity to shields, chassis, commons, switch
   contacts, and any LED/buzzer leads. Record resistance, not just continuity.
3. Exercise every selector position and button separately. Record all contact
   combinations and distinguish break-before-make, make-before-break, binary,
   one-hot, and resistor-ladder behavior.
4. Rotate the handwheel slowly in both directions. Identify passive A/B/common
   contacts or powered encoder supply/output conductors. Do not apply power to
   an unidentified encoder.
5. Identify diodes, lamps, LEDs, resistors, or active devices with polarity and
   resistance/diode measurements. Trace the pendant PCB where accessible.
6. Separately survey the controller-side connector while powered and
   disconnected from the pendant. Record steady voltage, transient range,
   source impedance where safe, and behavior in every controller state.
7. If an encoder needs power, apply only its verified voltage through a current
   limit. Capture A/B low/high levels, phase order, pulses per detent/revolution,
   maximum observed edge rate, and bounce/noise.
8. Repeat continuity and powered observations to rule out probe/orientation
   errors. A second reviewer must compare the table to connector photographs.
9. Only then design protection/translation and assign S2 Mini GPIO pins.

### Survey record

Populate every row; use `NC` only after verification and retain `TBD` for
unknowns.

| ID | Color/marking | Pendant endpoint | Behavior by control position | Passive measurements | Powered range/source | Proposed role | Confidence/evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| W01 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| W02 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| W03 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| W04 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| W05 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| W06 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| W07 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| W08 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| W09 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| W10 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| W11 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| W12 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| W13 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| W14 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| W15 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| W16 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| W17 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| W18 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| W19 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| W20 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| W21 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| W22 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| W23 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| W24 | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

Also record:

| Property | Result |
| --- | --- |
| Connector manufacturer/series | TBD |
| Connector key orientation and pin numbering source | TBD |
| Cable shield/drain termination | TBD |
| Encoder type and supply | TBD |
| Encoder pulses/detents per revolution | TBD |
| Axis selector encoding/common | TBD |
| Increment selector encoding/common | TBD |
| Enable switch normal and active states | TBD |
| Button normal and active states | TBD |
| Indicators/loads and current | TBD |
| Controller connector voltages | TBD |

## Display requirements and selection gate

The display must legibly present four coordinate rows, selected axis,
increment, controller state, connection/stale state, and confirmations. The
candidate must have a maintained CircuitPython driver, fit memory with the
status parser, and remain readable in workshop lighting. Prefer I2C when it
avoids a GPIO conflict and its refresh rate meets the UI requirement; otherwise
share SPI with SD using independent chip-select lines.

Before purchase/finalization, render the proposed jog and alarm screens at the
actual pixel dimensions and measure refresh time and heap usage on the S2 Mini.

## microSD requirements

- 3.3 V-compatible SPI interface with its own chip-select.
- Card-detect is preferred; absence must also be detected through I/O errors.
- Removal during a stream causes an immediate stream fault and no more queued
  file lines.
- Filesystem writes are never required during motion; logs/config writes are
  deferred and atomic where possible.
- The enclosure allows deliberate card insertion without confusing it with the
  machine connector.

## Hardware verification checklist

- [ ] Complete and photograph the 24-wire survey.
- [ ] Verify the Doesbot connector identity, levels, and protocol.
- [ ] Select the keyed machine connector and publish its numbered pinout.
- [ ] Decide isolated versus common-ground UART from measurements.
- [ ] Select and bench-test display and microSD modules together.
- [ ] Allocate GPIOs and audit boot straps, USB, UART, I2C/SPI, and board aliases.
- [ ] Verify every external signal is safe with either side unpowered.
- [ ] Bench-test with a controller/simulator before attaching machine motion.
