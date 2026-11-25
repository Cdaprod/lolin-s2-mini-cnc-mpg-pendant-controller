# Breakout board extraction and assembly integration

Date: 2026-10-29
Branch: `hardware-integration`
Source: `pendant.FCStd`, Body `Body006`
Component: `pendant-bodies/breakout-board.FCStd`

## Extraction

The breakout-board Body was independently copied with its native PartDesign history: `Sketch022 → Pad023`. The source Body also contained inactive `Binder018` (“From Original Assembly Sketch”), whose support points into the monolith. It was removed only from the in-memory Body group of the disposable extraction worker so recursive copy would not pull that inactive monolithic history. The authoritative `pendant.FCStd` was not saved or modified.

The component uses two intentional links to `pendant-master.FCStd`:

- Body placement Z: `-PendantDimensions.BoardFrontSetback` (13.2 mm at baseline).
- `Pad023.Length`: `PendantDimensions.BoardThickness` (1.6 mm at baseline).

The dependency audit reports `READY` for Body006 when `pendant_master#PendantDimensions` is explicitly permitted. Its Tip-rooted feature closure is `Sketch022` and `Pad023`; the Body placement expression is separately included as an owner-level dependency; there are no references back to the monolith. The two external expressions resolve through the relocatable relative path `../pendant-master.FCStd`.

## Geometry and parameter checks

The recomputed standalone Body is a valid, up-to-date single solid with 10 faces, volume `2660.5453836083534 mm³`, and world bounds `(-30, 20, -14.8)` to `(30, 50, -13.2) mm`. Against the saved source Body, FreeCAD’s Boolean symmetric-difference check returned valid zero-volume residuals in both directions. The component was saved, closed, reopened, and recomputed; its Body and Tip remained valid and the geometry comparison again returned zero difference.

Reversible master-parameter tests passed:

| Change | Result | Restored result |
| --- | --- | --- |
| BoardThickness `1.6 → 1.7 → 1.6 mm` | Volume `2660.5454 → 2826.8295 mm³`; one valid solid | Zero Boolean difference from baseline |
| BoardFrontSetback `13.2 → 13.3 → 13.2 mm` | World Z bounds shift by `−0.1 mm`; volume unchanged | Zero Boolean difference from baseline |

Both master values were restored and the saved component re-opened with the original metrics.

## Assembly and portability

The assembly builder now links `Body006` from this component and no longer includes the breakout board as a static interim BREP. The production modular assembly was rebuilt with five live Body links (the two locator Bodies count separately) and five static interim solids. All links and interim solids passed validity, single-solid, volume, and bounds checks; the assembly saved, closed, reopened, and recomputed successfully.

The refresh workflow explicitly touches and reassigns each cross-document spreadsheet expression after opening the master, then recomputes and saves master-driven components. A plain recompute after reopening the master kept the old cached values; the explicit expression refresh is required. Refresh also resynchronizes each generated link’s `LinkPlacement` from its source Body placement after recomputation because the board’s master-driven Body Z placement otherwise leaves an existing App::Link at its previous position. Current assembly links mirror source Body placements; an intentional assembly-only offset would need explicit offset handling before refresh so it is preserved.

A full end-to-end test ran the actual refresh script in a relocated disposable project. Changing the master values to BoardThickness `1.7 mm` and BoardFrontSetback `13.3 mm` produced a valid board of `2826.829470083875 mm³`, with bounds `(-30, 20, -15)` to `(30, 50, -13.3) mm`. The saved, reopened assembly link matched its component source. Restoring `1.6 mm` and `13.2 mm` and refreshing again returned the component and reopened link to `2660.5453836083534 mm³` and the baseline bounds, with no errors.

A relocated disposable project containing the master, component documents, and assembly reopened with five valid live links and five valid interim shapes. The board’s external expressions and the assembly’s relative component links resolved from the relocated tree.

The companion project-update workflow was also exercised against the relocated tree; it refreshed and validated the four canonical component files, synced the five links, checked all five interim solids, and completed without errors. It uses an explicit file list, so the pre-existing untracked `front-rear-shells.FCStd` candidate is not auto-loaded or rewritten. The headless preview exporter now expects five links and five interim solids. It rendered updated top, bottom, and static-interim views from the production assembly; the exporter validated all ten preview shapes.

## Remaining limits

The source monolith and master were not modified. The encoder faceplate, encoder pocket, upper faceplate, and front/rear shells remain static interim assembly representations. The shell dependency investigation is still blocked at the complex `RearFullLandTransfer.Base → SmallHangerPocketBody` boundary. The preview is for visual inspection; geometry acceptance comes from the FreeCAD recompute and shape checks above.
