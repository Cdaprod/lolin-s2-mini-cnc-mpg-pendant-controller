# Display retainer shell-mount passage driven by master

Date: 2026-10-29
Branch: `hardware-integration`
Component: `pendant-bodies/display-retainer.FCStd`

## Change

The two shell-mount passage radii in `DisplayRetainerMountingPatternV2` (`Constraints[2]` and `[5]`) now reference `pendant_master#<<InternalHardware>>.ShellMountPassageDiameter / 2`. The master alias is in `InternalHardware.B7` at the existing design value, `2.30 mm`. The component-to-master reference is relative (`../pendant-master.FCStd`). The three display mounting passages remain controlled by their component-local `DisplayMountPassageDiameter = 2.20 mm`; those holes were not changed.

The existing local `ShellMountPassageDiameter` alias is retained as historical local data, but no longer drives these two constraints. This avoids deleting the prior parameterization history. The master gained one alias at the component's established value; no manufactured dimension was changed at baseline.

## Geometry and feature-history validation

A disposable candidate was recomputed, saved, closed, reopened, and recomputed. Both external expressions reported `Valid`. The final `Body_DisplayRetainer_EditableV2` remained one valid solid at Tip `RetainerShellClearancePocketV3`. At the original 2.30 mm value, the candidate's final BREP had valid zero-volume differences in both Boolean directions against the pre-change source.

| Shell passage diameter | Tip volume (mm³) | Live assembly link (mm³) | Solid / bounds |
| ---: | ---: | ---: | --- |
| 2.30 mm baseline | 2050.792480333789 | 2050.792480333789 | 1 valid solid; unchanged bounds |
| 2.32 mm reversible test | 2050.357055592002 | 2050.3570555920014 | 1 valid solid; same bounds |
| restored 2.30 mm | 2050.792480333789 | 2050.792480333789 | 1 valid solid; returned to baseline |

The test used a relocated disposable project. Each update ran `refresh_modular_assembly.py`, which saved the component with refreshed master expressions and refreshed its App::Link. Refresh reported no errors. A separate fresh FreeCADCmd process reopened the assembly at both the changed and restored values. A separate standalone-open check also opened the component first, auto-loaded the master through the relative expression, recomputed successfully, and found both expressions valid.

The baseline and restored bounding box was `(-29.4201928, 29.4234403, -16.0, 25.8, -10.0614672, -7.0614672) mm`. The 2.32 mm perturbation changed the intended passage geometry; it is a propagation test and not a fit recommendation.

## Dependency boundary and limits

The Tip-rooted dependency auditor recognizes both external expressions as explicit master references and confirms the master file exists at the relative path. It reports extraction readiness `BLOCKED` because `LocalParameters` remains an active unowned helper object in the display-passage sketch's dependency chain. This change parameterizes the shared shell passage dimension; it does not claim a single-Body extraction boundary or remove that helper dependency.

## Source preservation and verification

Before promotion, the production master and retainer files were backed up outside the worktree at `/tmp/retainer-master-parameterization/production-before/`. SHA-256 before promotion:

- master: `3e2f041254ec1b6743a44bf1e1abb3925cc06bee913a4cd8a3b4eb304890fbfb`
- retainer: `8d1247566eee3e2b492e04a21061ad68483e5820b92d374928d284137c1622ca`

Promoted candidate SHA-256:

- master: `5027bf0a9d3329ae3468e93c2f428f285ad8f291014e39d7fde9dd46942ca622`
- retainer: `4637bb84bc9897500b41f7c8e9d543df235c464babd235dce51662e8b5e20709`

The authoritative monolithic pendant and modular assembly were not modified. The existing refresh script's save-on-master-refresh behavior was exercised by the relocated tests.
