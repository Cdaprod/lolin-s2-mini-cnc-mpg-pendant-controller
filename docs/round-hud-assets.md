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
deterministically writes 240 x 240 transparent RGBA previews decoded from the
same indexed colors used by the device, row-major 4-bpp runtime bitmaps,
CircuitPython palette constants, a manifest, and contact sheets. The
decorative palette is limited to 55% of the source accent luminance, keeping
the bezel visible while subordinate to telemetry on the GC9A01; text and safety
colors are unchanged. The default cyan theme uses a thin circular guide, twelve
illuminated outer sectors, alternating inner echoes, and sparse radial ticks.
This keeps the circular instrument silhouette legible without filling the
center or merging the sectors into a bright annulus. Intermediate supersampled
frames stay in memory. Only `.4bpp` files in
`assets/round_hud/runtime/` are deployed. The twelve production images occupy
345,600 bytes of filesystem storage; the selected bitmap occupies 28,800 bytes
in RAM. The 4x4 subpixel orb atlas adds 648 bytes. The rotor arc atlas occupies
135,424 bytes on storage and in RAM; it is loaded once at startup. The fixed
rotor uses 24 small palettes and retained TileGrids; no animation-frame bitmap
is allocated. A missing bezel falls
back to the established instrument backdrop; a missing atlas falls back to
the simpler retained marker. The generator keeps light
strokes narrow and leaves gaps between segmented arcs transparent. Palette
selection uses 32-bit RGB distance arithmetic so squared-color comparisons do
not overflow and corrupt the indexed firmware image.

Select a bezel with `MPG_UI_BEZEL` in `settings.toml` (for example
`cyan_reactor`, `turquoise_energy`, `amber_precision`, or `violet_hologram`).
Invalid names use the default. Existing settings remain unchanged unless the
user applies a settings update.

## Retained motion

The bezel artwork and its radial scale do not rotate. Twenty-four antialiased
outer arc sections stay in fixed positions and orientations. A smooth
three-peak brightness wave travels clockwise or counterclockwise around them;
the arc shapes never pivot or rotate on their own axes. The inner counter-orbit
orbs remain independent. This hybrid avoids a full-screen rotated framebuffer
and keeps labels and scale marks stationary. It uses the normalized signed MPG
activity already maintained by the app; it never reads the encoder, changes
counts, modifies jog state, or sends commands.

`MPG_BEZEL_ROTATION_ENABLED` controls the outer rotor. Ambient speed defaults
to one turn per 54 seconds; direction changes use a deterministic 20–40 second
interval and ease through deceleration. Encoder detent rate sets signed rotor
speed, capped at `MPG_BEZEL_MAX_SPEED_RAD_S`; after the input becomes idle, the
velocity blends toward the current ambient speed with `MPG_BEZEL_INERTIA_S`.
Presentation is limited by `MPG_BEZEL_FRAME_RATE` (default 24 Hz). The fixed
ring accents use precomputed 23x23 curved-arc tiles with 32 tangent
orientations and 16 subpixel phases. The animation updates retained palette
brightness only; it does not reposition or rotate the arcs and does not
construct bitmaps at runtime. Page swipes ease into and out of the transition while matching
velocity at the outgoing/incoming page handoff. These settings are clamped by
the rotor model and do not affect UI polling or communication loops.

HOME-to-menu and menu-to-HOME page swipes move the two retained page groups
together over 0.48 seconds with a smoothstep curve. Their separation stays one
screen width, so the incoming page follows the outgoing page without a blank
handoff. Menu-to-menu pages share one retained menu group and use the existing
bounded out/in transition while that group changes content; duplicating all
menu text and controls solely to cross-slide them would increase retained
DisplayIO memory. Critical safety overlays cancel either transition immediately.

The renderer preview script decodes the exact runtime 4-bpp bezel data and
approximates the GC9A01's RGB565 color conversion; typography and the retained
scene are still host approximations. It emits the normal screen snapshots plus
`bezel-angle-000.png`, `bezel-angle-090.png`, `bezel-angle-180.png`, and
`bezel-angle-270.png` to inspect the brightness-wave direction over fixed arc
geometry. Previews are layout aids, not
pixel-exact device captures. Physical frame pacing, heap stability, the
continuous page slide, and the visual response to a connected handwheel must be
checked on the S3.

Critical `ALARM` and `E-STOP` overlays retint the existing bezel palette to the
dim red alarm palette while preserving its geometry and transparent index. The
change is a bounded palette update on the normal UI render path; motion markers
and rotor segments remain hidden while the critical overlay is active. Clearing
the overlay restores the selected bezel's original palette.

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
