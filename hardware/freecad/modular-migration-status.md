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

## Not yet migrated

- Front shell, rear shell, upper faceplate, encoder faceplate, and encoder pocket: retain in `pendant.FCStd`. The baseline shows cross-Body binders, shared parameter expressions, transfer tools, and interdependent split geometry. Extract them only as complete dependency groups and only after candidate tests.
- Archived/display-retainer v1 and helper/cutter/envelope Bodies: not physical component sources; retained in the original document.
- `pendant-master.FCStd` and the linked top-level assembly have not been created. Moving existing parameter sources before a safe expression migration would leave current features disconnected, so this is deliberately pending dependency mapping.
- No cross-document parameter propagation has yet been claimed or tested.

## Recovery and execution rules

Keep `pendant.FCStd`, recovery files, and historical repair candidates untouched until the linked assembly passes acceptance tests. For each next component, use a disposable copy, preserve its complete dependency group, compare geometry in a common coordinate system, and reopen/recompute before promotion. A blocked component stays in the original document while independent components proceed.
