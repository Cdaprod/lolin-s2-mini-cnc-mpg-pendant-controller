# Display retainer master-diameter propagation

Date: 2026-10-30
Branch: `hardware-integration`

## Existing native parameter links

The current `pendant-bodies/display-retainer.FCStd` already contains master-driven screw diameters in the fully constrained `DisplayRetainerMountingPatternV2` sketch. Constraints 2 and 5 reference `pendant_master#<<InternalHardware>>.ShellMountPassageDiameter / 2`; constraints 8, 11, and 14 reference `DisplayMountPassageDiameter / 2`. The master baselines are 2.30 mm for the two shell passages and 2.20 mm for the three display passages. No feature history or production CAD was changed for this test.

## Reversible component test

Tests ran in a disposable copy with `pendant-master.FCStd` in its expected relative location. The original retainer Tip was a valid, one-solid shape with 66 faces, 192 edges, and volume `2050.792480333789 mm³`.

Both master diameters were increased by 0.10 mm. After master recompute and component recompute, the five radii resolved to 1.20 mm (two shell holes) and 1.15 mm (three display holes). The retainer Tip remained valid, one solid, and up-to-date; its volume became `2045.454362405179 mm³` (a `5.338117928610 mm³` reduction), with 67 faces and 197 edges. Saving, closing, reopening, and recomputing at the changed values preserved the same measured Tip geometry and resolved expressions.

The master values were restored to 2.30/2.20 mm, and the retainer was recomputed and saved. After another close/reopen, the Tip returned to 66 faces, 192 edges, and baseline volume `2050.792480333789 mm³`; its 0.05 mm mesh hash matched the original baseline. Bounds matched within floating-point tolerance. This validates reversible propagation through the retainer's native feature history at the tested values.

## Live assembly refresh test

A disposable project copy included the master, four editable component documents, assembly, and existing `update_modular_project.py` workflow. With master diameters changed to 2.50/2.40 mm, the workflow completed with `ok: true`; the live display-retainer link was valid and matched its source Tip volume at `2039.9447674739174 mm³`. Restoring the master values and refreshing again returned both source and link to `2050.792480333789 mm³`. The final assembly reopen showed five valid live links, including the display retainer at placement `(0, 0, 0)`.

The full change/restore cycle ran only in `/tmp/display-retainer-assembly-propagation`. The authoritative master, retainer, assembly, monolith, and untracked recovery files were not modified. No mechanical-strength claim is implied by this parameter test.
