# Round-display fonts

The retained GC9A01 UI uses native-size DejaVu Sans bitmap fonts instead of
enlarging CircuitPython's 6×8 terminal font. The 10 px regular face is used
for compact status rows, 12 px regular for other labels and menus, 14 px bold
for headings and overlays, and 24 px bold for the primary axis and position
readouts. The 240×240 panel remains at its native resolution; these strikes
make its text sharper and more readable without nearest-neighbor scaling.

The BDF files were generated from DejaVu Sans 2.37 using
`tools/generate_display_fonts.py`. The original DejaVu license is included in
`DejaVu-LICENSE`. Regenerate with Pillow and the regular/bold TTF files from
the upstream `dejavu-fonts-ttf-2.37.zip` release:

```sh
python tools/generate_display_fonts.py \
  --regular /path/to/DejaVuSans.ttf \
  --bold /path/to/DejaVuSans-Bold.ttf
```

`deploy.sh` manages the BDF assets and the CircuitPython 10.x
`adafruit_bitmap_font` library. The renderer retains a terminal-font fallback
if the bitmap-font module or asset is unavailable.
