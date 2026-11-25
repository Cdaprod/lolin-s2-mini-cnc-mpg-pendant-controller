# Display retainer passage diameters driven by master

Date: 2026-10-29
Branch: `hardware-integration`
Component: `pendant-bodies/display-retainer.FCStd`

## Change

The three display mounting passage radii in `DisplayRetainerMountingPatternV2` (`Constraints[8, 11, 14]`) now reference `pendant_master#<<InternalHardware>>.DisplayMountPassageDiameter / 2`. The new master alias is in `InternalHardware.B8` at the existing 2.20 mm design value. The two shell mounting passages remain separately controlled by `ShellMountPassageDiameter = 2.30 mm` in `B7`, through constraints `[2, 5]`. All five M2 passage radii on the retainer are now master-driven. The existing `LocalParameters` spreadsheet is retained, but its former passage-diameter aliases no longer drive these constraints.

## Validation

A disposable candidate was recomputed, saved, reopened, and compared at the unchanged baseline. The final `Body_DisplayRetainer_EditableV2` stayed a valid one-solid Body with Tip `RetainerShellClearancePocketV3`; its baseline BREP difference against the pre-change source was zero in both directions.

A relocated copy of the project was used for the reversible master-to-component-to-assembly test:

| `DisplayMountPassageDiameter` | Retainer Tip volume (mm³) | Fresh-process live link volume (mm³) | Result |
| ---: | ---: | ---: | --- |
| 2.20 mm baseline | 2050.792480333789 | 2050.792480333789 | Valid one-solid Body/link |
| 2.22 mm test | 2050.1697232614306 | 2050.16972326143 | Valid one-solid Body/link; bounds unchanged |
| restored 2.20 mm | 2050.792480333789 | 2050.792480333789 | Returned to baseline |

Both changed and restored refreshes reported no errors, saved the component, and validated all five live links and five static interim solids. Separate fresh FreeCADCmd processes opened the saved assemblies at the changed and restored values. A standalone open of the component auto-loaded the master through `../pendant-master.FCStd`; all five expressions reported `Valid`, and recompute retained the baseline shape.

## Dependency boundary

The Tip-rooted dependency audit now reports `READY` when the master parameter source `pendant_master#InternalHardware` is allowed. The remaining local spreadsheet is no longer an active dependency for this Body Tip. The only external dependencies are the five intentional passage-diameter expressions, all resolved through the existing relative master file. This establishes the retainer's audit-level extraction readiness; it does not imply every other component is ready or validate assembly mechanical fit.

## Preservation

Before promotion, the prior master and component were backed up outside the worktree at `/tmp/retainer-display-master-parameterization/production-before/`.

SHA-256 before this change:

- master: `5027bf0a9d3329ae3468e93c2f428f285ad8f291014e39d7fde9dd46942ca622`
- retainer: `4637bb84bc9897500b41f7c8e9d543df235c464babd235dce51662e8b5e20709`

SHA-256 after this change:

- master: `d3b226b50cbbefd20a4f414afd60532d320b7b32dacca38844360035b4e2ffe7`
- retainer: `066e82cb63553b66c423395e7fdc52fdca88a4694697d98d1482e7e249f4065b`

The monolithic pendant and modular assembly files were not modified. The relocated assembly copy was used for propagation testing only. After promotion, the canonical `pendant-modular-assembly.FCStd` was also opened in a fresh FreeCADCmd process without saving. It loaded the master and all four component documents, recomputed, and validated five live links and five static interim solids. The retainer link and source each remained one valid solid at `2050.792480333789 mm³`; the master aliases read 2.30 mm and 2.20 mm.
