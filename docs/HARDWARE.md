# Hardware definition

## Status

This is a requirements and integration document, not a fabrication-ready
pinout. Manufacturer documentation now establishes the pendant conductor
functions and that `COM` is the common terminal for its switches. Electrical
levels and interface requirements remain subject to measurement before any
unknown-voltage signal is attached to the LOLIN S2 Mini. Those measurements are
a hardware-integration gate; they do not block hardware-neutral firmware.

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

## Manufacturer-confirmed pendant wiring

The supplied MBLKJ manufacturer sheets are authoritative for identity and
function. They do not establish the safe ESP32 interface voltage for the
purchased unit. Signal names in this table are also the names used by firmware.

| Wire | Signal | Manufacturer-documented function |
| --- | --- | --- |
| Red | `VCC` | MPG encoder supply |
| Black | `0V` | Encoder ground |
| Green | `A` | Encoder A phase |
| White | `B` | Encoder B phase |
| Violet | `A-` | Differential/inverted A |
| Violet/Black | `B-` | Differential/inverted B |
| Yellow | `X` | X-axis selector |
| Yellow/Black | `Y` | Y-axis selector |
| Brown | `Z` | Z-axis selector |
| Brown/Black | `4` | Axis 4 selector |
| Pink | `5` | Axis 5 selector |
| Pink/Black | `6` | Axis 6 selector |
| Gray | `X1` | x1 multiplier selector |
| Gray/Black | `X10` | x10 multiplier selector |
| Orange | `X100` | x100 multiplier selector |
| Orange/Black | `COM` | Required selector common |
| Blue | `C` | Emergency-stop contact |
| Blue/Black | `NC/CN` | Emergency-stop NC contact |
| Green/Black | `LED+` | Pendant indicator LED positive |
| White/Black | `LED-` | Pendant indicator LED negative |
| Shield | `Shield` | Cable shield |

The switch inputs share `COM`. The firmware models axis positions `OFF`, `X`,
`Y`, `Z`, `4`, `5`, and `6`, with default logical mapping `4` → A, `5` → B,
and `6` → C. It models multiplier contacts as the ratios x1, x10, and x100.
`A-` and `B-` terminate in future verified receiver/interface circuitry; the
application quadrature decoder consumes normalized A/B logic and therefore
does not depend on the eventual receiver choice.

`C` and `NC/CN` form the physical emergency-stop contact. Firmware may observe
that contact, inhibit commands, cancel software activity, and display E-STOP,
but it is not the primary safety mechanism. The contact must ultimately
interrupt the appropriate machine safety/control circuit independently of the
ESP32-S2 and CircuitPython.

## Electrical verification before connection

Use a disconnected pendant, multimeter, current-limited supply where justified,
and oscilloscope/logic analyzer. Record the instrument, setup, measured values,
and photographs for each result. Verify all of the following before selecting
interface circuitry or GPIO pins:

- [ ] Purchased-unit encoder `VCC` requirement; the manufacturer sheets warn
  that units may be supplied for different voltages, so do not infer it.
- [ ] `A`/`A-` and `B`/`B-` low/high/common-mode levels, phase relationship,
  edge rate, pulses/counts per detent, noise, and output topology.
- [ ] Whether a differential receiver or level translator is required and the
  exact qualified part/circuit.
- [ ] Selector `COM` behavior, contact resistance, active polarity,
  break/make behavior, and isolation from encoder `0V`.
- [ ] E-stop `C` to `NC/CN` normal/pressed behavior, contact rating, and the
  independent machine safety circuit in which it will be installed.
- [ ] `LED+`/`LED-` operating voltage, current, polarity, and required driver;
  do not drive it from a GPIO before this is known.
- [ ] Shield-to-pendant/chassis continuity and the final single-/multi-point
  chassis termination strategy.
- [ ] Doesbot 8-pin connector numbering, UART/other protocol, voltage levels,
  grounding/isolation, power direction, and safe behavior when either side is
  unpowered.
- [ ] Final keyed direct-controller connector pinout and final ESP32-S2 GPIO
  assignment after the interface circuits and peripherals are selected.

Explicitly unresolved are encoder VCC, A/A-/B/B- voltage and topology, receiver
or level translator choice, LED voltage/current, shield termination, GPIO
assignment, direct-controller connector pinout, and Doesbot 8-pin electrical
pinout. No unresolved signal is approved for direct connection to 3.3 V GPIO.

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

- [x] Record manufacturer-confirmed conductor functions and selector common.
- [ ] Complete and photograph the electrical-verification checklist.
- [ ] Verify the Doesbot connector identity, levels, and protocol.
- [ ] Select the keyed machine connector and publish its numbered pinout.
- [ ] Decide isolated versus common-ground UART from measurements.
- [ ] Select and bench-test display and microSD modules together.
- [ ] Allocate GPIOs and audit boot straps, USB, UART, I2C/SPI, and board aliases.
- [ ] Verify every external signal is safe with either side unpowered.
- [ ] Bench-test with a controller/simulator before attaching machine motion.
