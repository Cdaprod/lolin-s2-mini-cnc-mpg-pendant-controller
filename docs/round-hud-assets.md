# Round display HUD artwork and bezel motion

The round UI can use one of twelve generated, light-only bezel designs. The
Python generator is a host tool; CircuitPython only loads the selected compact
4-bit indexed bitmap and the matching 16-entry palette. Text, touch feedback,
menus, status, and alarms remain in the existing retained DisplayIO scene above
the artwork. The generated PNGs are previews and are not loaded by firmware.

## Regenerating artwork and previews

Install host dependencies and regenerate both the full-resolution development
PNGs and the production bitmaps:

```sh
python3 -m pip install -r requirements-host-tools.txt
python3 tools/generate_hud_bezels.py --supersample 8
python3 tools/render_round_ui.py --output assets/round_hud/previews
```

The generator also accepts `--supersample 4` and `--palette-json PATH`. It
deterministically writes 240 x 240 transparent RGBA previews, row-major 4-bpp
runtime bitmaps, CircuitPython palette constants, a manifest, and contact
sheets. Intermediate supersampled frames stay in memory. Only `.4bpp` files in
`assets/round_hud/runtime/` are deployed. The twelve production images occupy
345,600 bytes of filesystem storage; the selected bitmap occupies 28,800 bytes
in RAM. The 4x4 subpixel orb atlas adds 648 bytes on storage and in RAM. A
missing bezel falls back to the established instrument backdrop; a missing orb
atlas falls back to the simpler retained marker.

Select a bezel with `MPG_UI_BEZEL` in `settings.toml` (for example
`cyan_reactor`, `turquoise_energy`, `amber_precision`, or `violet_hologram`).
Invalid names use the default. Existing settings remain unchanged unless the
user applies a settings update.

## Retained motion

The bezel artwork and its radial scale do not rotate. A retained outer light
marker moves over the segmented ring, while the inner counter-orbit marker
remains independent. This hybrid keeps labels and scale marks stationary and
avoids a full-screen rotated framebuffer. It uses the normalized signed MPG
activity already maintained by the app; it never reads the encoder, changes
counts, modifies jog state, or sends commands.

`MPG_BEZEL_ROTATION_ENABLED` controls the outer marker. Ambient speed defaults
to one turn per 54 seconds; direction changes use a deterministic 20–40 second
interval and ease through deceleration. Encoder detent rate sets signed rotor
speed, capped at `MPG_BEZEL_MAX_SPEED_RAD_S`; after the input becomes idle, the
velocity blends toward the current ambient speed with `MPG_BEZEL_INERTIA_S`.
Presentation is limited by `MPG_BEZEL_FRAME_RATE` (default 24 Hz). Orb motion
uses sixteen supersampled, precomputed tile phases to antialias fractional
positions; the frame loop changes only retained tile indices and integer
coordinates. It does not construct rotated bitmaps or sample geometry at
runtime. Page swipes ease into and out of the transition while matching
velocity at the outgoing/incoming page handoff. These settings are clamped by
the rotor model and do not affect UI polling or communication loops.

The renderer preview script emits the normal screen snapshots plus
`bezel-angle-000.png`, `bezel-angle-090.png`, `bezel-angle-180.png`, and
`bezel-angle-270.png` to inspect the marker path. Previews are layout aids, not
pixel-exact device captures. Physical frame pacing, heap stability, and the
visual response to a connected handwheel must be checked on the S3.

## Validation

```sh
python3 -m unittest tests.test_bezel_rotor tests.test_hud_bezels \
  tests.test_round_ui -v
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Hardware deployment should use the existing guarded deploy tool and its
runtime-only mode when configuration must remain untouched:

```sh
CIRCUITPY=/Volumes/CIRCUITPY ./deploy.sh --runtime-only
```

This only validates the visual feature. It is not authorization to enable CNC
motion or spindle operation.
