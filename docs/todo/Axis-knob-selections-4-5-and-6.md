Don’t forget we discussed either… using extra axis’ as configuration displayed menus or renders… they could be like… since I only have x, y, z… using 4, 5, and 6 for….

File Explorer: of SD card stuff and running programs

Configuration: everything from connecting, wifi, hardware, etc…

Test & Demo: a neat preview of what the buttons do and an isometric preview of the axis’s multipliers and the encoder wheel moving a spindle over a preview of the bed

Yes — that belongs in the Codex task because it changes what **Axis 4/5/6 mean semantically** in your three-axis machine. The physical selector inputs should still be preserved as `GPA3/GPA4/GPA5`, but rather than pretending you have A/B/C motion axes, those three selector positions can become **top-level pendant modes**.

Add this section to the Codex message:

```text
THREE-AXIS MACHINE / AXIS 4-5-6 MODE SELECTOR
==============================================

This machine currently uses only three physical motion axes:

- X
- Y
- Z

The existing MPG pendant nevertheless has six axis-selector positions:

- X
- Y
- Z
- 4
- 5
- 6

Do NOT waste selector positions 4, 5 and 6 by simply mapping them to nonexistent
A/B/C machine axes for the current three-axis configuration.

Preserve their physical MCP23017 inputs:

- X -> GPA0
- Y -> GPA1
- Z -> GPA2
- 4 -> GPA3
- 5 -> GPA4
- 6 -> GPA5

But introduce a semantic selector layer so the meaning of positions 4/5/6 can be
configured independently from the physical switch wiring.

For the CURRENT three-axis build, use:

X = X-axis MPG/jog mode
Y = Y-axis MPG/jog mode
Z = Z-axis MPG/jog mode

4 = FILE EXPLORER / JOBS
5 = CONFIGURATION
6 = TEST & DEMO

This should be configurable rather than permanently baking the assumption into
the MCP23017 driver.

The MCP layer should report physical selector positions. A higher-level input/UI
mapping should decide what those positions mean.


FILE EXPLORER / JOBS — SELECTOR POSITION 4
===========================================

Position 4 should enter a File Explorer / Jobs mode centered around the Round
Display and microSD support already planned in the repository.

This should eventually provide a compact pendant-native interface for:

- browsing the microSD card
- folders/directories
- viewing available G-code files
- selecting a program
- viewing basic file/program information
- previewing a selected job where practical
- starting a program
- pause/resume
- cancel/abort with confirmation
- job progress
- current line / relevant execution state
- recently used jobs if supported by the existing architecture
- macros stored on SD where appropriate

Do not make merely entering selector position 4 automatically execute anything.

Position 4 changes CONTEXT.

The wheel and buttons can then become contextual navigation controls.

For example:

MPG wheel:
    scroll through files/menu entries

SELECT:
    open/select

BACK:
    go up/back

FN:
    contextual secondary action

The UI should make it unmistakable that the wheel is navigating files rather
than commanding machine motion.

Entering File Explorer mode must therefore suppress accidental MPG motion.


CONFIGURATION — SELECTOR POSITION 5
===================================

Position 5 should enter a pendant Configuration mode.

This is intended to become the central on-device configuration interface rather
than requiring every normal setting change to be performed by editing files.

Configuration can expose appropriate settings such as:

NETWORK
- Wi-Fi scan
- saved SSID
- connect/disconnect
- setup AP
- hostname
- connection status

CONTROLLER
- controller mode
- connection status
- GRBL connection information
- transport information

MPG
- direction
- counts per detent
- increment behavior
- multiplier behavior

DISPLAY / UI
- brightness
- rotation if supported
- UI preferences

HARDWARE
- detected MCP23017
- I2C status
- SD status
- touch status
- encoder status
- input status

SYSTEM
- firmware/version information
- board profile
- display profile
- reboot/reload actions where appropriate
- diagnostics

Do NOT expose settings that could make the electrical interface unsafe without
appropriate safeguards.

In particular, software configuration must not pretend to electrically verify
encoder voltage, LED voltage, or other physical characteristics that require
measurement.

The wheel should become a natural configuration-navigation control while in
this mode rather than moving the CNC.


TEST & DEMO — SELECTOR POSITION 6
=================================

Position 6 should enter a dedicated Test & Demo / Input Visualizer mode.

This is important both as a useful diagnostic tool and as a polished visual
demonstration of the pendant.

Use the 240x240 Round Display to create a visually clear live representation of
what the physical controls are doing.

The eventual target is an isometric-style machine visualization showing
something conceptually like:

            Z
            |
            v
         [spindle]
             \
              \
       +—————+
      /               /|
     /      BED      / |
    +—————+  |
    |               | /
    +—————+/

The exact graphics should fit the existing round-renderer architecture rather
than requiring a heavyweight 3D engine.

This can be a lightweight 2D/isometric renderer.

It should visually respond to the pendant controls.

Examples:

Select X:
    emphasize/highlight the X direction.

Select Y:
    emphasize/highlight the Y direction.

Select Z:
    emphasize/highlight the Z direction.

x1 / x10 / x100:
    visibly change the displayed movement scale/increment.

Turn MPG clockwise:
    animate the virtual spindle/tool in the positive selected direction.

Turn MPG counterclockwise:
    animate it in the negative selected direction.

Press SELECT:
    visually show SELECT activation.

Press other installed buttons:
    show their semantic action/state.

Remote stop:
    show the remote-stop state prominently.

Encoder:
    show direction, activity and preferably raw/accumulated count information
    in a diagnostic overlay.

MCP23017:
    optionally provide an input-inspection view showing live selector/button
    states.

The demo should make it immediately understandable how:

- axis selection
- multiplier selection
- MPG direction
- MPG movement
- buttons
- remote stop

are being interpreted by the firmware.


SAFE DEMO MODE
==============

Test & Demo mode must be designed so that interacting with the pendant does NOT
unexpectedly move the real machine.

By default, selector position 6 should consume MPG/button activity for the
visualizer rather than issuing motion commands.

This makes it useful for:

- initial pendant bring-up
- testing the 25-wire harness
- checking selector wiring
- checking encoder direction
- determining counts per detent
- verifying multiplier behavior
- testing buttons
- demonstrating the pendant without a CNC connected
- UI development
- troubleshooting

This is especially useful while:

MPG_INPUTS_ENABLED=false

or while portions of the electrical interface are still being commissioned.

Where possible, support a diagnostic state that distinguishes:

PHYSICAL INPUT
      |
      v
INPUT BACKEND
      |
      v
SEMANTIC ACTION
      |
      +——> LIVE MACHINE COMMAND
      |
      +——> DEMO / VISUALIZER

The demo path should exercise the same input interpretation used by the real
machine without transmitting the resulting motion command.


CONTEXTUAL MPG WHEEL
====================

Treat the MPG wheel as a context-sensitive physical input.

Its meaning depends on the selected pendant mode.

X selected:
    wheel = X jog

Y selected:
    wheel = Y jog

Z selected:
    wheel = Z jog

4 / File Explorer:
    wheel = file/menu navigation

5 / Configuration:
    wheel = setting/menu navigation or value adjustment

6 / Test & Demo:
    wheel = simulated machine movement / diagnostic visualization

This contextual behavior should occur ABOVE the raw encoder driver.

Do not put UI knowledge into the encoder hardware backend.

Preferred conceptual flow:

    Encoder hardware
          |
          v
    Encoder delta
          |
          v
    Input / semantic router
          |
          +-————— X/Y/Z —> Jog command
          |
          +-————— 4 -——> File navigation
          |
          +-————— 5 -——> Configuration navigation
          |
          +-————— 6 -——> Demo simulation


SELECTOR SEMANTICS / CONFIGURATION
==================================

Do not permanently assume every six-position MPG selector represents six CNC
motion axes.

Separate:

PHYSICAL POSITION

from:

SEMANTIC FUNCTION

The settings/profile architecture should be capable of representing something
conceptually equivalent to:

X -> AXIS_X
Y -> AXIS_Y
Z -> AXIS_Z
4 -> FILES
5 -> CONFIG
6 -> DEMO

A future machine with A/B/C axes should be able to use another profile such as:

X -> AXIS_X
Y -> AXIS_Y
Z -> AXIS_Z
4 -> AXIS_A
5 -> AXIS_B
6 -> AXIS_C

without rewiring the MCP23017.

Design the abstraction accordingly.


ROUND-DISPLAY UX
================

These modes should follow the project’s existing round-display UX direction:

- very short glance interactions
- one-hand operation
- wheel-first navigation where appropriate
- large central information
- minimal desktop-style menu behavior
- immediate feedback
- obvious current context
- obvious selected item
- error-tolerant interaction
- confirmations for destructive/motion-related operations
- easy recovery/back navigation

Changing selector position should provide immediate visual confirmation of the
new context.

The user should never have to wonder whether turning the MPG wheel will:

- move X
- move Y
- move Z
- scroll files
- change a setting
- manipulate the demo

The current context must always be visually obvious.


IMPLEMENTATION SCOPE
====================

Inspect the existing UI/navigation/input architecture before creating new
parallel systems.

Integrate these concepts into the existing:

- UIManager
- round renderer
- semantic command/input architecture
- jobs support
- microSD support
- network configuration
- controller state
- overlays
- menu hierarchy
- MPG activity handling

Where the underlying functionality already exists, expose/reuse it rather than
implementing a duplicate subsystem.

For functionality that is not yet complete, establish the architecture and
working UI state cleanly rather than filling the repository with fake behavior.

Mock/demo data is acceptable specifically inside mock/demo mode when clearly
identified as such.


TESTS
=====

Add tests for the semantic selector behavior.

At minimum:

- physical X -> AXIS_X
- physical Y -> AXIS_Y
- physical Z -> AXIS_Z
- physical 4 -> FILES
- physical 5 -> CONFIG
- physical 6 -> DEMO

Verify:

- wheel in X/Y/Z routes to jog behavior
- wheel in FILES does not generate jog motion
- wheel in CONFIG does not generate jog motion
- wheel in DEMO does not generate real jog motion
- FILES wheel events navigate the appropriate model
- CONFIG wheel events navigate/adjust the appropriate model
- DEMO receives signed encoder activity
- changing multiplier is represented in demo state
- remote-stop state is visible to the diagnostic model
- returning from 4/5/6 to X/Y/Z restores normal axis context safely

Most importantly, test that changing into a non-motion context cannot leave a
stale X/Y/Z jog destination active and accidentally convert UI wheel movement
into machine movement.
```

I especially like **4 = Files, 5 = Configuration, 6 = Test & Demo** for this build. It turns three otherwise-unused mechanical selector detents into three major modes without adding more buttons, while preserving the exact same hardware so a future 4/5/6-axis profile could map those positions back to A/B/C.

And the **Test & Demo mode is more than eye candy**: it can become the commissioning screen for the whole 25-wire harness. When you turn the wheel or flip X/Y/Z/x1/x10/x100, you get immediate visual proof of what the firmware thinks happened *without moving the CNC*. That will be particularly useful when we physically bring up the MCP23017 and encoder receiver. 


