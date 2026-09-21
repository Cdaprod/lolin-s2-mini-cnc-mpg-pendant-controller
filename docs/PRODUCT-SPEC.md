# Product specification

## Product definition

This project is a standalone, controller-agnostic CNC manual-pulse-generator
(MPG) pendant. It will provide precise manual jogging, controller-reported
machine state and coordinates, common machine functions, USB integration, and
a separate direct machine interface. Later releases may stream G-code from
removable storage without a computer.

The LOLIN S2 Mini remains the reference controller until the measured GPIO,
memory, and peripheral budget proves that it cannot meet these requirements.

## Scope and terminology

- **Core** is required for the first motion-capable release.
- **High** is designed into the hardware and delivered after safe jogging.
- **Later** must remain architecturally possible but does not block V1.
- **Design-in** reserves protocol, UI, or electrical capacity without promising
  implementation in V1.
- **Controller position** is the position reported by GRBL-compatible firmware.
  It is not independently measured position.

## Feature requirements

| System | Requirement | Priority |
| --- | --- | --- |
| MPG | Decode a quadrature A/B handwheel in both directions without losing normal-speed detents | Core |
| MPG | Select X, Y, Z, and A axes | Core |
| MPG | Reserve B and C axis values in the input/state model | Design-in |
| MPG | Select x1, x10, and x100 increments | Core |
| MPG | Configure physical increments independently of selector labels; defaults are 0.001, 0.01, and 0.1 mm | Core |
| MPG | Support incremental jog and a separately enabled continuous-jog mode | High |
| Display | Show selected axis and increment at all times in the jog screen | Core |
| Display | Show controller-reported X/Y/Z/A coordinates and their machine/work frame | Core |
| Display | Show Idle, Jog, Run, Hold, Door, Home, Check, Sleep, and Alarm states without treating unknown states as Idle | Core |
| Display | Show stale-data and disconnected indications | Core |
| Display | Show feed, commanded spindle speed, active WCS, limit/probe flags, and connection transport when supplied by the controller | High |
| Display | Show selected file, progress, and stream state | Later |
| Controls | Home, Zero selected axis, Cycle Start/Resume, Feed Hold, Jog Cancel, and Reset | Core |
| Controls | Zero all configured linear axes, Unlock, Probe Z, Safe Z/retract, and configurable function actions | High |
| Controls | Feed override, spindle override, and spindle start/stop | Later |
| Connectivity | Use the board USB-C only for standards-compliant USB power/device functions | Core |
| Connectivity | Provide a physically distinct, keyed machine port | Core |
| Connectivity | Support direct GRBL 1.1 serial through a replaceable controller-specific adapter/cable | Core |
| Connectivity | Document and implement a verified Doesbot adapter | Core |
| Connectivity | Preserve Wi-Fi configuration and transport abstraction | Existing |
| Connectivity | Support host/HID or UGS integration | High |
| Connectivity | Allow grblHAL and FluidNC protocol profiles | Future |
| Storage | Reserve shared SPI capacity and enclosure access for microSD | High |
| Storage | Browse and select `.nc`, `.gcode`, and `.tap` files | High |
| Storage | Reliably stream, pause, resume, and cancel a program with progress reporting | Later |
| Extensibility | Load named, configurable macros from storage rather than compiling every function mapping | High |
| Safety | Require a deliberate enable/dead-man state for handwheel motion | Core |
| Safety | Debounce switches and reject invalid selector states | Core |
| Safety | Gate every action by current connection and controller state | Core |
| Safety | Cancel queued jogging and visibly fault on communication loss | Core |
| Safety | Surface controller alarms and require deliberate recovery | Core |

## User controls

The preferred panel has dedicated `HOME`, `ZERO`, `START`, `HOLD`, `PROBE`,
`FN`, and `CANCEL` controls plus the handwheel, axis selector, increment
selector, and enable/dead-man switch. Final button count depends on the MPG
wiring survey; an I/O expander is preferable to removing safety controls.

Default mappings are:

| Input | Primary action | `FN` action |
| --- | --- | --- |
| `HOME` | Home (`$H`) after confirmation/interlock | Safe Z macro |
| `ZERO` | Zero selected axis | Zero configured X/Y/Z axes |
| `START` | Cycle start/resume | Spindle toggle, disabled by default |
| `HOLD` | Feed hold | Soft reset, requiring a deliberate long press |
| `PROBE` | Probe Z workflow | Configurable macro |
| `CANCEL` | Jog cancel or leave menu | Abort stream after confirmation |

Mappings must be configuration data, validated on load, and displayed before a
potentially dangerous macro runs. Reset, unlock, homing, probing, spindle, and
job-start actions must not be triggered by a single ambiguous or bouncing edge.

## Jog behavior

For GRBL 1.1, incremental wheel movement uses `$J=` commands with explicit
units, incremental distance, selected axis, and feed. Jog commands are admitted
only when controller state and the enable input permit them. The action layer
must wait for or account for acknowledgements and bound queued travel.

Releasing enable, selecting an invalid axis/increment, detecting a stuck input,
losing communications, or exceeding the jog watchdog deadline transitions the
pendant to a non-commanding fault state. The implementation sends GRBL's jog
cancel real-time byte when a live transport remains available; loss of a link
must never be displayed as a confirmed stop.

Continuous jog is not an unbounded move. It consists of short, bounded `$J=`
moves with acknowledgement tracking and an immediate cancel path.

## Position and status display

The pendant obtains its DRO from periodic controller status reports initiated
with the GRBL `?` real-time query. Polling must not exceed 5 Hz by default. A
typical report is:

```text
<Idle|MPos:125.400,42.150,-8.000|FS:0,0>
```

The parser must tolerate reordered, omitted, and unknown fields. It retains
both machine position (`MPos`) and work-coordinate offset (`WCO`) when present,
derives work position only when inputs are current, and labels the displayed
frame. Status age is tracked; stale coordinates are dimmed or replaced rather
than presented as live.

These values are controller-reported open-loop coordinates. If a motor stalls,
the controller and pendant may still report the commanded position. The UI and
documentation must never call this a scale-measured or true position.

Suggested primary screen:

```text
┌────────────────────────────┐
│ IDLE        UART       G54 │
│ X > +125.400 mm            │
│ Y    +42.150 mm            │
│ Z     -8.000 mm            │
│ A     +0.000 deg           │
│ STEP 0.100 mm     ENABLED  │
└────────────────────────────┘
```

Alarm, disconnection, stale status, active streaming, and confirmation prompts
take precedence over decorative or secondary information.

## Connectivity and protocol boundaries

Inputs emit named actions; they never construct G-code, serial bytes, URLs, or
socket requests. The safety/action layer decides whether an action is allowed.
A controller protocol turns allowed actions into controller operations, and a
transport moves bytes. This preserves the boundary already established by
`src/controller.py`.

USB-C on the S2 Mini is USB only: power, CircuitPython filesystem, USB CDC,
optional HID, and configuration. Direct controller serial uses the keyed
machine port described in `HARDWARE.md`. A non-USB electrical interface must
never use a USB-C receptacle.

## Storage, jobs, and macros

The target storage layout is:

```text
/jobs/
  bracket.nc
/macros/
  park.gcode
  probe_z.gcode
/config/
  pendant.json
```

Job streaming uses GRBL response flow control: normalize and validate one line,
send within the chosen buffer policy, associate each `ok`/`error` response with
an outstanding line, and halt on errors or alarms. Real-time and push messages
are parsed separately. The pendant must never dump a complete file into UART.

Job start requires controller readiness, enable policy satisfaction, file
review, and explicit confirmation. Hold, resume, cancel, reset, disconnect, SD
removal, read failure, malformed input, and alarm each have a deterministic UI
and stream-state transition. Resume after reset or reconnect is prohibited.

Macros use the same checked command/response engine. They declare a name,
allowed controller states, confirmation requirement, and commands. Unsafe or
unknown metadata disables a macro rather than falling back to permissive
behavior.

## Non-functional requirements

- Boot and configuration failure must leave all CNC output disabled.
- Configuration has explicit defaults, validation, and a visible version.
- The event loop remains responsive to cancel/hold while display, storage, or
  networking work is pending.
- Core behavior is testable on desktop Python using fake inputs, clocks, and
  transports; hardware drivers remain thin adapters.
- No controller-specific electrical assumptions cross the machine adapter.
- Logs do not expose Wi-Fi credentials and use bounded storage if persisted.
- Firmware updates and repeated deployment do not rewrite user jobs or config.

## Release acceptance criteria

### Hardware-definition gate

- Every conductor function is identified from the manufacturer map, and each
  electrical property required by `HARDWARE.md` is verified by measurement.
- The machine controller connector is identified by measurement/documentation.
- Voltage levels, common conductors, shielding, active polarity, and isolation
  needs are known before either device is connected to the S2 Mini.
- A reviewed GPIO/peripheral allocation fits without boot-strap conflicts.

### Safe-input gate

- Automated tests cover quadrature direction, bounce, missed/invalid
  transitions, selector invalid states, long-press actions, and enable release.
- No input test can produce controller output while the controller mode is
  disabled or safety state is not ready.

### Motion gate

- Bench tests use a simulator or unpowered controller before a machine.
- Each wheel detent produces only the selected, bounded jog distance.
- Enable release and cancel stop command production immediately.
- Disconnect and status timeout enter a latched visible fault and never claim a
  successful stop.
- Alarm, Run, Hold, Door, Home, and unknown states block jogging unless an
  explicitly documented transition permits an action.

### Standalone-job gate

- The streamer never exceeds its configured receive-buffer accounting.
- `error`, alarm, reset, disconnect, SD removal, and read errors halt sending.
- Hold/resume/cancel behavior is verified with deterministic transcript tests.
- A job cannot auto-resume after reboot or reconnection.

## Explicit exclusions

- The pendant is not an emergency-stop circuit or safety-rated device.
- It does not infer actual machine position from wheel counts.
- It does not replace hard limits, guarding, contactors, or the controller's
  safety chain.
- USB host operation is not assumed; the S2 Mini USB connector is initially a
  USB device connection.
- B/C axes and standalone streaming are not V1 commitments.

## Protocol references

- [GRBL interface basics](https://github.com/gnea/grbl/blob/master/doc/markdown/interface.md)
- [GRBL v1.1 jogging](https://github.com/gnea/grbl/blob/master/doc/markdown/jogging.md)
- [GRBL real-time status reports](https://github.com/gnea/grbl/blob/master/doc/markdown/interface.md#real-time-status-reports)
