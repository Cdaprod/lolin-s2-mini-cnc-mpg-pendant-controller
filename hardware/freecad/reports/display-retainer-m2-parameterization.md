# Display retainer M2 passage parameterization

Date: 2026-10-29  
Branch: `hardware-integration`

## Change

Added a native `LocalParameters` spreadsheet to `pendant-bodies/display-retainer.FCStd` and bound the existing fully constrained mounting-pattern radii to two component-local aliases:

- `DisplayMountPassageDiameter = 2.20 mm` drives radius constraints `DisplayRetainerMountingPatternV2.Constraints[8, 11, 14]` (three display mounting passages).
- `ShellMountPassageDiameter = 2.30 mm` drives radius constraints `DisplayRetainerMountingPatternV2.Constraints[2, 5]` (two shell mounting passages).

The sketch geometry, constraint count, hole centers, feature order, and baseline manufactured geometry remain unchanged. These are local pattern dimensions; the master currently has no matching shared M2 passage aliases, and this change does not invent or alter a shared fastener standard.

## Feature-history validation

The Body `Body_DisplayRetainer_EditableV2` retained Tip `RetainerShellClearancePocketV3`, remained one valid solid, and stayed up-to-date through both tests. The mounting pocket, header pocket, structural junction fillets, and final shell-clearance pocket all recomputed successfully.

| Test | Display passage | Shell passage | Tip volume (mm³) | Surface area (mm²) | Mesh vertices |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original / parameterized baseline | 2.20 mm | 2.30 mm | 2050.792480333789 | 2183.563637888774 | 1,736 |
| Display group perturbation | 2.22 mm | 2.30 mm | 2050.1697232614306 | 2182.4501494739625 | 1,732 |
| Shell group perturbation | 2.20 mm | 2.32 mm | 2050.357055592002 | 2183.650345846013 | 1,736 |
| Both groups after save/reopen | 2.22 mm | 2.32 mm | 2049.7342985196424 | — | — |
| Restored after save/reopen | 2.20 mm | 2.30 mm | 2050.792480333789 | 2183.563637888774 | 1,736 |

Each changed state was saved and reopened. Restoring each value returned the original Tip metrics; after both aliases were restored, the final baseline was saved, reopened, and recomputed. Volume, area, bounding box, and tessellation vertex count returned at recorded precision. All sketches remained fully constrained.

## Linked assembly and portability

Copied the candidate project to a second temporary root. Its relative App::Links resolved to the copied source documents. With both diameter aliases changed, `refresh_modular_assembly.py` completed without errors, all four live links and six interim solids were valid, and assembly save/reopen passed. The retainer link volume was 2049.7342985196424 mm³. After restoring both aliases and refreshing, the link volume returned to 2050.792480333789 mm³; save/reopen passed again.

The master, assembly, original monolith, and existing recovery files were not modified.

## Scope

This makes the two existing M2 passage groups independently adjustable while retaining their original values. It does not resolve shell dependencies or make the encoder faceplate/pocket editable as separate native components.

## Later shared-master refinement

The two shell mounting passages (`Constraints[2]` and `[5]`) were subsequently connected to the master `InternalHardware.ShellMountPassageDiameter` alias at the same 2.30 mm baseline. Their reversible 2.32 mm propagation through the complete retainer Tip and refreshed live assembly link, cold-start reopen, and restoration are documented in `display-retainer-shared-shell-mounting.md` and its JSON evidence. The three display mounting passages remain component-local at 2.20 mm. The local shell-passage alias remains stored as historical data but no longer drives those two constraints.
