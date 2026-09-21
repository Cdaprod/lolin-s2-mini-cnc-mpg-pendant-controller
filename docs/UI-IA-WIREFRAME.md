# Pendant HMI information architecture and wireframes

## Status and authority

This document is the source of truth for the pendant HMI. No screen may be
implemented unless it appears in this information architecture (IA). Every UI
context declares exactly one handwheel mode: `MOTION`, `NAVIGATION`,
`VALUE_EDIT`, `TEXT_ENTRY`, or `DISABLED`.

Machine motion from the handwheel is permitted only when the active context
explicitly declares `MOTION`, which is normally only `HOME / JOG-DRO`. The
safety/action layer independently checks this ownership; changing a drawing or
display implementation cannot bypass the interlock.

## Product navigation grammar

The physical controls have consistent contextual meaning:

- **Turn** moves, navigates, changes a value, or selects a character according
  to the declared handwheel mode.
- **SELECT** enters or accepts the focused item.
- **BACK/CANCEL** returns one level, deletes during text entry, or invokes the
  explicitly shown cancel behavior.
- **FN** selects a secondary operation or changes text character group.
- **LONG SELECT** confirms completion of text entry.
- Dangerous actions require an explicit confirmation and existing controller,
  dead-man, E-stop, and machine-state interlocks.

Normalized UI events are `ROTATE_CW`, `ROTATE_CCW`, `SELECT`, `BACK`, `FN`,
`CANCEL`, `LONG_SELECT`, and `LONG_FN`. GPIO drivers emit these events; screens
never inspect pins or send GRBL/network/storage commands.

## Main information architecture

```text
BOOT / Connecting
└── HOME / JOG-DRO
    └── MAIN MENU
        ├── Machine
        │   ├── Home
        │   ├── Zero Selected Axis
        │   ├── Zero XYZ
        │   ├── Probe Z
        │   ├── Safe Z
        │   ├── Park
        │   ├── Unlock
        │   └── Reset
        ├── Jobs
        │   ├── Browse
        │   │   └── Job Details
        │   │       └── Confirm Start
        │   │           └── Active Job
        │   ├── Recent (unavailable: no persistent history yet)
        │   └── Active Job
        ├── Macros
        │   ├── Browse
        │   │   └── Macro Details
        │   │       └── Confirm Run
        │   └── Manage (unavailable: no on-device macro editor yet)
        ├── Controller
        │   ├── Status
        │   ├── Identity
        │   ├── Transport
        │   ├── GRBL Info
        │   ├── Pin State
        │   └── Diagnostics
        ├── Network
        │   ├── Wi-Fi On / Off
        │   ├── Scan Networks
        │   │   └── Select SSID
        │   │       └── Password Entry
        │   ├── Saved Networks (unavailable: browser not implemented)
        │   ├── Manual SSID
        │   │   └── Password Entry
        │   ├── Disconnect
        │   ├── Forget Network (unavailable: browser not implemented)
        │   └── Network Info
        ├── Settings
        │   ├── Jog (unavailable: editor not implemented)
        │   ├── Units (unavailable: editor not implemented)
        │   ├── Display (unavailable: editor not implemented)
        │   ├── Controls (unavailable: editor not implemented)
        │   ├── MPG (unavailable: editor not implemented)
        │   ├── Safety (unavailable: editor not implemented)
        │   ├── Storage (unavailable: editor not implemented)
        │   └── UI (unavailable: editor not implemented)
        └── System / About
            ├── Firmware
            ├── Hardware
            ├── Storage
            ├── Diagnostics
            ├── Logs
            ├── Version
            └── Restart → Confirm Restart
```

Unavailable items are displayed as unavailable, include a reason, cannot emit
commands, and are skipped only if the final display design chooses automatic
focus skipping. They are not represented as functional merely to complete the
tree.

## Contextual handwheel ownership

| Context | Mode | Wheel behavior | Can emit machine jog? |
| --- | --- | --- | --- |
| Boot | `DISABLED` | None | No |
| Home / Jog-DRO | `MOTION` | Jog selected logical axis | Yes, after safety validation |
| Main and section menus | `NAVIGATION` | Move focus | No |
| Job/file browser | `NAVIGATION` | Scroll files | No |
| Macro browser | `NAVIGATION` | Scroll macros | No |
| Wi-Fi scan | `NAVIGATION` | Scroll SSIDs | No |
| Settings browser | `NAVIGATION` | Move focus | No |
| Future setting editor | `VALUE_EDIT` | Adjust focused value | No |
| Text entry | `TEXT_ENTRY` | Select character | No |
| Confirmation | `NAVIGATION` | Choose reject/accept | No |
| Active job | `NAVIGATION` | Select Hold/Resume/Cancel | No |
| E-stop/alarm/disconnect/stream error | `DISABLED` | None | No |

```text
HANDWHEEL ROTATION
        │
        ▼
  UIManager context
        │
   ┌────┼────────────┬─────────────┐
   ▼    ▼            ▼             ▼
MOTION  NAVIGATION  VALUE/TEXT    DISABLED
   │    (focus only) (edit only)   (nothing)
   ▼
semantic JOG event
   │
   ▼
ActionDispatcher → SafetyStateMachine → GRBL

ONLY THIS PATH CAN MOVE THE CNC.
```

The UI revokes motion ownership before pushing a new screen. The central state
mirrors the active screen and handwheel mode, and `SafetyStateMachine` refuses
wheel jogging unless that mode is `MOTION`.

## Global overlays

Overlays are independent of the navigation stack and never become menu
destinations. Highest active priority wins:

| Priority | Overlay | Trigger | Dismiss/recovery | Wheel |
| ---: | --- | --- | --- | --- |
| 100 | E-STOP / inhibited | Contact observed or latch set | Release contact, then explicit recovery | Disabled |
| 90 | Controller alarm | GRBL `ALARM` | Controller recovery/unlock policy | Disabled |
| 80 | Disconnected/stale | No connection or watchdog timeout | Verified status response/reconnect | Disabled |
| 70 | Streaming error | Stream error/alarm | Acknowledge after stream is stopped | Disabled |
| 60 | Confirmation | Deliberate action requested | Select reject/accept | Navigation only |
| 50 | Warning/message | Persistent nonfatal problem | Acknowledge | No motion |
| 40 | Notification/toast | Completed/nonfatal operation | Timeout/acknowledge | Underlying context policy |

Removing an overlay does not clear a controller alarm, E-stop latch, dead-man
requirement, or other safety condition. Overlay dismissal alone never authorizes
motion.

## Screen contract matrix

| Screen | Parent / children | Entry and exit | Wheel / buttons | Required state and motion |
| --- | --- | --- | --- | --- |
| Boot | Root → Home | Startup; exits when components are composed | Inputs ignored | `DISABLED`; no motion |
| Home / Jog-DRO | Root → Main Menu | Boot/back-home; SELECT opens menu | Wheel jog; CANCEL jog-cancel | Connected Idle/Jog, selected axis, dead-man, no inhibit; `MOTION` |
| Main Menu | Home → sections | SELECT from Home; BACK returns Home | Wheel focus; SELECT enter | `NAVIGATION`; no motion |
| Machine | Main Menu → confirmations | Select Machine; BACK | Wheel focus; SELECT asks confirmation | Connected/safe state evaluated by action layer; no wheel motion |
| Jobs | Main Menu → browser/active | Select Jobs; BACK | Wheel focus; SELECT enter | `NAVIGATION`; no motion |
| Job Browser | Jobs → details | Browse; BACK | Wheel scroll; SELECT file | Mounted/readable storage; no motion |
| Job Details | Browser → confirmation | File selection; BACK | SELECT requests Start | Idle/safe checked at execution; no wheel motion |
| Active Job | Details/Jobs | Successful start; BACK does not stop job | Hold/Resume/Cancel; cancel confirms | Stream owns commands; wheel never jogs |
| Macros | Main Menu → browser | Select Macros; BACK | Wheel focus; SELECT enter | No motion |
| Macro Browser | Macros → details | Browse; BACK | Wheel scroll; SELECT macro | No motion |
| Macro Details | Browser → confirmation | Macro selection; BACK | SELECT requests Run | State/interlock checked at execution; no wheel motion |
| Controller | Main Menu → info | Select Controller; BACK | Wheel focus; SELECT details | Read-only; no motion |
| Network | Main Menu → scan/text/info | Select Network; BACK | Wheel focus; SELECT operation | Network service only; no motion |
| Wi-Fi Scan | Network → password | Scan completes; BACK | Wheel SSID; SELECT | `NAVIGATION`; no motion |
| Text Entry | Network workflow | SSID chosen/manual entry; CANCEL | Wheel char, SELECT accept, FN group, BACK delete, LONG SELECT done | `TEXT_ENTRY`; no motion |
| Settings | Main Menu → future editors | Select Settings; BACK | Wheel focus | Current entries explicitly unavailable; no motion |
| System/About | Main Menu → info/restart | Select System; BACK | Wheel focus; SELECT details/action | Restart confirms; no motion |

## Representative wireframes

### Home / Jog-DRO

```text
┌────────────────────────────┐
│ ● IDLE        G54     UART │
├────────────────────────────┤
│ ▶ X   +125.400 mm          │
│   Y    +42.150 mm          │
│   Z     -8.000 mm          │
│   A     +0.000°            │
│                            │
├────────────────────────────┤
│ X      ×10      0.010 mm   │
└────────────────────────────┘
```

Coordinates are GRBL controller-reported open-loop MPos/WPos values, not
independently measured physical DRO values. Lost mechanical steps are not
detectable without scales/servo feedback.

### Main menu

```text
┌────────────────────────────┐
│ CNC PENDANT           IDLE │
├────────────────────────────┤
│ > Machine                  │
│   Jobs                     │
│   Macros                   │
│   Controller               │
│   Network                  │
│   Settings                 │
│   System / About           │
└────────────────────────────┘
```

### Wi-Fi scan and password

```text
┌────────────────────────────┐
│ SELECT NETWORK             │
├────────────────────────────┤
│ > cda_Lab           -31 dB │
│   CNC-Shop          -52 dB │
│   Other             -76 dB │
└────────────────────────────┘

┌────────────────────────────┐
│ cda_Lab — PASSWORD         │
├────────────────────────────┤
│ ••••••••_                  │
│          [ G ]             │
│ group: abc ABC 123 #+=     │
├────────────────────────────┤
│ TURN CHAR  PRESS ACCEPT    │
│ LONG PRESS DONE            │
└────────────────────────────┘
```

Password values are masked, redacted from representations, never rendered to
the console, and cleared from UI state after submission. Credential persistence
is delegated to the network service and must tolerate a read-only CIRCUITPY
filesystem without misreporting the live radio connection.

### Job journey

```text
JOBS → BROWSE → SELECT FILE → JOB DETAILS → CONFIRM START → ACTIVE JOB
                                                               ├─ HOLD
                                                               ├─ RESUME
                                                               └─ CANCEL
                                                                    └─ CONFIRM
```

```text
┌────────────────────────────┐
│ ACTIVE JOB            RUN │
├────────────────────────────┤
│ bracket.nc                 │
│ ███████████░░░░      68%   │
│ F 500       S 12000        │
│                            │
│ > HOLD                     │
│   RESUME                   │
│   CANCEL                   │
└────────────────────────────┘
```

The streamer, not the screen, performs hold/resume/cancel and reports progress
through shared state.

## Rendering contract

`UIManager.view_model()` exposes backend-independent primitives: screen ID,
title, mode, focus, item labels/availability, safe text-entry presentation, and
top overlay. It never returns the unmasked password. `ConsoleDisplay` consumes
that model for host testing. A future `displayio` adapter must reuse the same
model and retained widgets, updating only dirty values instead of rebuilding an
object tree every runtime iteration.

Controller polling, E-stop observation, HOLD, CANCEL, and streaming continue in
the cooperative application loop regardless of the active screen. Navigation
depth, command queues, macro size, and displayed collections remain bounded.

## Acceptance rules

1. The same normalized wheel event jogs only on Home, navigates menus/files/
   SSIDs, and selects text characters according to context.
2. No non-Home context emits a `JOG` command.
3. All motion-producing menu actions use semantic commands, confirmation where
   specified, and independent safety/action validation.
4. Disabled entries emit no command and explain their unavailable backend.
5. Safety overlays preempt all screens and cannot be dismissed into unsafe
   motion.
6. Screens never access GPIO, UART, Wi-Fi radio, filesystem streaming, or GRBL
   directly.
7. Password plaintext is absent from render models, logs, diagnostics, repr,
   and exception messages.
8. Physical display work is incomplete until a selected displayio driver and
   actual resolution pass readability, heap, refresh, and responsiveness tests.
