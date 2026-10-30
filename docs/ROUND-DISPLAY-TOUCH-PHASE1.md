# Round Display & Touch — Phase 1

Baseline: latest main `0548d180`, Seeed XIAO ESP32-S3 + GC9A01A 240x240 + CST816/CST8XX capacitive controller. Do not change physical selector semantics, reliable transport, or machine safety controls.

## Current diagnosis

- Rendering at **240x240 physical pixels is already the panel's native resolution**. More rendering pixels cannot improve the physical resolution. Clarity instead comes from appropriate visual hierarchy, vector-like primitives, font size, and antialias-safe assets.
- `MPG_TOUCH_ENABLED=true` is required in the deployed `settings.toml` (not only in `settings.toml.example`).
- Firmware must contain `adafruit_cst8xx` compatible with the installed CircuitPython release. The hardware touch controller and MCP23017 share D4/D5 I2C; the touch controller must be detected and bus contention absent.
- Boot prints the TOUCH subsystem state. If ERROR, examine `state.touch_error` (the original exception name is preserved).
- Touch events fire **on finger release**, not touch-down. This intentionally prevents inadvertent repeated selections.
- Tap on HOME enters the existing menu. Swipe up/down scrolls; left/right only navigate BACK/HOME. Tap a menu row to focus/select. Long press cannot perform E-stop recovery.

## Bench verification — machine disconnected

1. Inspect serial boot diagnostics and verify `touch OK` without suppressing any failures.
2. Read I2C scan results: expect 0x20 for MCP23017 if installed, and a separate address for the touch controller. Do not assume the touch address, scan for it.
3. Verify `adafruit_cst8xx` can read physical touches and report changing coordinates.
4. Hold finger for >0.8 s and release, swipe all four directions, then test taps at center and perimeter. If mapping is rotated/mirrored, set `MPG_TOUCH_ROTATION`, `MPG_TOUCH_INVERT_X`, `MPG_TOUCH_INVERT_Y` and reboot.
5. Verify tapping controls does not generate JOG actions; physical deadman/selector and controller state remain authoritative.
6. Verify no touch action can recover a latched E-stop and that alarms remain visible.

## Visual direction / staged implementation

Next PR phases (separate from the hardware-activation patch):

- **Theme system**: editable Python constants for `oled_black`, `ice_cyan`, `industrial_amber`, and `spectrum` palettes. Preserve high contrast; reserve red for ALARM / E-stop.
- **Clarity**: improve native-pixel font assets, trim long labels, keep the DRO dominant; optimize character clipping around the round bezel.
- **Retained animations**: easing for ring and selection highlight, transient touch ripple/cursor and short status transition. Rate-limit updates; preallocate objects, and never block the input/network/watchdog poll loop.
- **Touch affordances**: explicit HOME/MENU/BACK screen regions, pressed-state feedback, vertical swipe navigation, optional settings page to calibrate touch. Touch is navigation-only, not jog/macro execution.
- **Perf gates**: heap headroom, input-poll latency, redraw count and smoothness under live ESP-NOW telemetry. Regression tests for orientation and safety, plus instrumented hardware benchmarks.

## Development commands

```sh
python -m unittest discover -s tests -p 'test_touch_gestures.py' -v
python -m unittest discover -s tests -p 'test_ui.py' -v
python -m unittest discover -s tests -p 'test_round_ui.py' -v
```

Do not merge without physical touch validation on the user's exact Seeed Round Display hardware.
