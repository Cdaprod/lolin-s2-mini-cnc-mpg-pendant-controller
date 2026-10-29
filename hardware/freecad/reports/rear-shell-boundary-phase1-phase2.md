# Rear shell reference boundary audit — Phase 1 and Phase 2

Date: 2026-10-29
Branch: `hardware-integration`
Baseline commit: `abe6a85`
Production files were not modified.

## Current result

The earlier `47`-object closure did not traverse the active Tip of helper
PartDesign Bodies, nor all serialized property links. The audit now follows a
referenced helper Body through its active Tip (not its entire Group/history),
includes geometry and parameter property links, and includes Sketcher external
geometry. It records but excludes `Context` links as document-container
relationships. Under that complete traversal the disposable bypass candidate
contains **162 active dependencies before cleanup** and **161 after cleanup**. The 12
unconstrained external references previously removed from the two rear screw
sketches remain removed; the two removed references are not the remaining
module boundary. Therefore the earlier `71 → 47` expanded-closure reduction
was a traversal artifact: after including active helper Body Tips, the cleanup
reduces the complete closure by only one object because the land-transfer path
still reaches most of the same front-shell history.

The current cleaned candidate is decisively **BLOCKED** for extraction. Its
active graph has 103 objects owned outside `Body002`, 15 active unowned helper
or parameter objects, and 19 active Sketcher references to front-shell
generated edges. Nineteen opaque persistent subelement tokens cannot yet be
certified as stable cross-document interfaces, so they are separately marked
indeterminate. The machine-readable readiness result and full paths are in the
[post-cleanup manifest](rear-shell-sketch-dependency-manifest.json).

The three manifests compare the authoritative monolith, the bypass candidate
before the 12-reference cleanup, and the candidate after cleanup:

- [Authoritative monolith](rear-shell-sketch-dependency-manifest-monolith.json): 51 ordinary / 166 expanded objects.
- [Bypass baseline](rear-shell-sketch-dependency-manifest-bypass-baseline.json): 47 ordinary / 162 expanded objects.
- [Cleaned bypass](rear-shell-sketch-dependency-manifest.json): 47 ordinary / 161 expanded objects.

The expanded counts changed because the audit now follows active helper Body
Tips and saved geometry/parameter links while excluding non-geometric Context
links; they do not indicate a geometry change.

## Phase 1 — generated-edge references

The 19 active references are in `Sketch019` and `Sketch020`, both in the
front-shell `Body`. Their native constraint use is:

| Sketch | Source object / refs | Constraint use | Frame |
|---|---|---|---|
| `Sketch019` | 9 refs to `Pad017`, 4 to `AdditiveLoft` | Five refs drive nine constraints: external orders 7–8 drive constraints 52, 53, 61 and 55, 63, 69; orders 9, 10, 12 drive 80, 81, 79. The other eight refs are not used by constraints. | Global placement: origin `(0,0,-19 mm)`, 180° about X. Source features and their Body have identity placement. |
| `Sketch020` | 6 refs to `Pocket016` | None of the six external geometries is used by a constraint. | Global placement: origin `(0,0,-19 mm)`, identity rotation. Source feature and its Body have identity placement. |

The exact persistent subelement tokens, projected arc geometry in the sketch
plane, constraint indices, paths, and source/owner placements are recorded in
the manifest. The four earlier non-driving references from the rear aligned
seat/passage sketches are gone in the cleaned candidate. The front-owned
`Sketch019`/`Sketch020` references are still in the active dependency graph
because the rear geometry also consumes the front-shell land-transfer chain.
Deleting their non-driving references alone would not disconnect that real
geometry input, so this phase did not remove or redirect them.

The principal cross-shell path is:

```text
Body002.Tip RearBossWallRamps45
  → Body002FullWidthSeat.Group → Body002FullLandTransferTool active Tip
  → RearSeatScrewPassageRelief.BaseFeature → RearFullLandTransfer
  → RearFullLandTransfer.Base → SmallHangerPocketBody (front Body)
  → front-shell mating/faceplate features → Pocket016 / Sketch019 / Sketch020
```

This is a geometric Base input, not only retained sketch history. Other active
rear Tip tool inputs are `USBSeatToolForBody002` and the `RearExteriorEnvelope`
Body; their active Tips and properties are included in the expanded graph.
`RearEnvelopeSeamProfile` and `RearEnvelopeBackProfile` are not in the active
Tip path of `RearExteriorEnvelope` and are treated as inactive construction
history for this extraction decision.

## Phase 2 — `ExteriorEnvelope`

`ExteriorEnvelope` is an active width parameter source, not a generated-face
shape input. The local VarSet stores `ExteriorWidth` and `ReferenceWidth`, both
`79.5569559596823 mm`. Seven active rear width-profile sketches use the
`EnvelopeControl` link and an expression for
`WidthRatio = ExteriorWidth / ReferenceWidth`:

- `WidthControlled_OriginalRearClosureProfile`
- `WidthControlled_RearMatchedProfile0` through `3`
- `WidthControlled_RearMatchedEnvelopeProfile0` and `1`

The master document already has an `ExteriorEnvelope` spreadsheet with aliases
`ExteriorWidth` and `ReferenceWidth` at the same values. In a disposable
candidate, I bound the local VarSet properties to
`pendant_master#<<ExteriorEnvelope>>.ExteriorWidth` and
`pendant_master#<<ExteriorEnvelope>>.ReferenceWidth`. After save/reopen, all
seven sketches recomputed to the original geometry at ratio 1. A temporary
80 mm master width changed every profile to ratio 1.005568891 and changed its
geometry and bounds; restoring the original width restored all seven profile
geometries exactly. The master document was not saved with the temporary
value. Detailed results are in the [parameter propagation test record](rear-shell-master-envelope-propagation-test.json).

This proves the external spreadsheet expression and profile-level propagation
for the width-controlled sketches. It does **not** yet validate downstream
shell Body recomputation at 80 mm, a component document reopened without the
master, or assembly refresh. The current implementation can retain a local
VarSet inside the extracted component and drive its properties from the master
spreadsheet; the dependency-update workflow must explicitly reopen/refresh and
recompute dependent documents, as FreeCAD documents for external spreadsheet
references ([official Spreadsheet documentation](https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Spreadsheet_Workbench.md#spreadsheet-data-in-expressions)).

## Extraction gate and next cut

The readiness checker returns `BLOCKED`; no standalone extraction was attempted
in this phase. The minimum practical next dependency cut is not the 19 sketch
references by themselves. It is the complete land-transfer boundary beginning
at `RearFullLandTransfer.Base`, plus the five constraint-driving `Sketch019`
references if they remain necessary after replacing that input. The smallest
candidate interface should reproduce only the front mating geometry actually
consumed by the land transfer, with stable profiles and placement in the
existing master frame. The three active rear helper/tool Bodies and the
parameter controls must remain native and editable in any eventual component.

The reusable audit generator now emits `READY`, `BLOCKED`, or `INDETERMINATE`,
including active Tip traversal through helper Body Tips, property-level
crossings, constraint use, exact external geometry tokens, and coordinates.
Run it with:

```sh
hardware/freecad/scripts/audit_sketch_dependencies.py \
  hardware/freecad/pendant.FCStd --body Body002 \
  --json /tmp/rear-shell-manifest.json
```
