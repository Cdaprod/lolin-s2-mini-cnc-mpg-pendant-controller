# Rear-shell repair candidate previews

These orthographic renders show the disposable `pendant-modular-repair-candidate.FCStd` assembly from above and below, plus its static interim components separately from the underside. The repaired rear-shell link is blue. The images are read-only renders of saved shapes; they do not modify CAD files or represent a strength simulation.

The preview manifest records six live links, three static interim shapes, and nine valid single-solid components. The renderer also passed a regression run on the production assembly using its default five-link/four-interim expectations; that run wrote only to `/tmp`.

To regenerate the candidate preview:

```sh
python3 hardware/freecad/scripts/render_modular_preview.py \
  --assembly hardware/freecad/pendant-modular-repair-candidate.FCStd \
  --output-dir hardware/freecad/reports/rear-shell-native-loadpath-preview \
  --expected-links 6 --expected-interim 3
```
