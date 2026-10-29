# FreeCAD modular migration status

Date: 2026-10-29
Branch: `hardware-integration`
Authoritative source retained unchanged: `pendant.FCStd`

## Baseline

- FreeCAD 1.1.1, revision `0108fd4b4850cc46e625b60e53cea7a7bbe69f8d`.
- The source contains 816 document objects, including multiple physical Bodies, construction tools, archived versions, and transfer geometry. Object count is not a component count.
- The document already has shared parameter sources (`PendantDimensions`, `InternalHardware`, `ExteriorEnvelope`, `DualSided_OpposedWedge_Seam`, and `HangerParameters`). Their current expressions point within the monolithic document. They have not been moved or rewritten.
- Baseline Body inventory, Tips, shape validity, solid counts, volumes, and bounding boxes were captured in `/tmp/pendant_modular_baseline_audit.json` for this machine/session. The authoritative source was not saved or modified.
- A checksum-verified recovery backup of the source, working encoder handoff, and recovery log is stored outside the worktree at `/Users/davidcannan/Documents/FreeCAD-Backups/modular-migration-20261029T151539Z/`.

## Migrated and verified

`pendant-bodies/display-retainer.FCStd` contains the complete editable `Body_DisplayRetainer_EditableV2` history (nine features plus its Body Origin). FreeCAD's recursive cross-document object-copy operation was used. The candidate was recomputed, saved, closed, reopened, and recomputed again.

- Source and destination Body Tip: `RetainerShellClearancePocketV3`.
- Shape: valid, one solid.
- Volume: source `2050.792480333789 mm^3`; reopened destination `2050.792480333789 mm^3`.
- Bounding box: source and reopened destination `(-29.4202, -16, -10.0615, 29.4234, 25.8, -7.06147) mm`.
- No copied feature has a link back to the source document.
- The document remains independently editable. It currently has no external master dependency; no constraints were rewritten to create one.

`pendant-bodies/usb-tethered-cover.FCStd` contains the editable `Body_USBTetheredCover` plus the hidden envelope/press-fit dependency Bodies recursively required by its history. Its manufacturing Body tip is `USBPlugLeadIn`; the helper Bodies remain hidden. It was recomputed, saved, closed, reopened, and recomputed again.

- Manufacturing Body baseline: one valid solid, source volume `665.2206904482824 mm^3`, reopened destination `665.220690448208 mm^3` (difference about `7.4e-11 mm^3`); bounding box matches source.
- No dependency link points back to the source document. The extracted helper group contains seven valid single-solid Bodies; those helper solids are construction/dependency geometry and are not separate manufactured parts.

## Master and update behavior

`pendant-master.FCStd` now contains the original `PendantDimensions` sheet copied with its aliases and values, plus native sheets populated from the existing `InternalHardware`, `ExteriorEnvelope`, `DualSided_OpposedWedge_Seam`, and `HangerParameters` values. No values were invented. The source document's parameter objects and expressions remain unchanged. These copied values are not yet wired to migrated component sketches; that remains incremental work.

A disposable `Part::Box` test verified an external expression using the internal document name: `pendant_master#<<PendantDimensions>>.FaceplateThickness`. A change from `2.5 mm` to `3.0 mm` propagated after recompute, remained valid after save/reopen, and returned to `2.5 mm` when restored. The document label/file uses `pendant-master`, but the installed FreeCAD 1.1.1 expression parser required the loaded document's internal name `pendant_master`; using the hyphenated spelling produced an Invalid expression. The master was restored and saved at `2.5 mm`.

`hardware/freecad/scripts/update_modular_project.py` loads the master first, then recomputes, validates, and saves component documents. It can also refresh an explicitly supplied assembly candidate. The worker has a 300-second default timeout and process-group TERM/KILL cleanup. Its first full run successfully refreshed the master and both extracted component files; all reported Bodies were valid single solids. It does not open or save the untouched authoritative assembly.

## Not yet migrated

- Front shell, rear shell, upper faceplate, encoder faceplate, and encoder pocket: retain in `pendant.FCStd`. The baseline shows cross-Body binders, shared parameter expressions, transfer tools, and interdependent split geometry. Extract them only as complete dependency groups and only after candidate tests.
- Archived/display-retainer v1 and helper/cutter/envelope Bodies: not physical component sources; retained in the original document.
- The linked top-level assembly has not been created. `pendant.FCStd` remains the unchanged monolithic source, not an assembly candidate.

## Recovery and execution rules

Keep `pendant.FCStd`, recovery files, and historical repair candidates untouched until the linked assembly passes acceptance tests. For each next component, use a disposable copy, preserve its complete dependency group, compare geometry in a common coordinate system, and reopen/recompute before promotion. A blocked component stays in the original document while independent components proceed.
