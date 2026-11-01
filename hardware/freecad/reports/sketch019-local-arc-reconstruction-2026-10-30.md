# Sketch019 local-arc reconstruction test

Date: 2026-10-30  
Branch: `hardware-integration`  
Scope: disposable FreeCAD shell-pair candidate only. The production monolith, master, modular assembly, and pre-existing untracked shell-pair file were not modified.

## Candidate

The test used `/tmp/front-rear-shells-bypass-validation-20261030/sketch019-reconstruction/pendant-bodies/front-rear-shells-sketch019-local.FCStd`, SHA-256 `da90e080504e48f28b7574a51bfe97ecba7dc74de7f91e6d3391402e77b05772`. It contains the validated `RemoveWarpProneTongues` bypass and the separate successful removal of six unused `Sketch020` references.

## Sketch019 reconstruction

The five constraint-driving generated circular arcs were copied from the source references into `Sketch019` as internal construction geometry. Each local arc matched its referenced source arc's endpoints. The nine existing constraints were rewired from external geometry IDs `-10`, `-11`, `-12`, `-13`, and `-15` to the five internal arcs. Each copied construction arc was fixed with a Block constraint. All 13 `Sketch019` external references were then removed.

| Check | Result |
|---|---|
| Original native sketch geometries preserved | Yes; original 42 geometries unchanged |
| Added construction arcs | 5 |
| Constraints | 129 total (124 original + 5 Block) |
| Sketch degrees of freedom | 0 |
| Fully constrained / valid / up-to-date | Yes |
| Remaining external references in `Sketch019` | 0 (apart from the two standard sketch axes) |
| Constraint-driving references replaced | 5; nine existing constraints rewired |
| Other external references removed | 8 references in `Sketch019` that drove no constraints |

The full model dependency object counts do not fall because the source features remain required through other paths. After the substitution, the serialized audit shows active Sketcher external-reference counts of 19 → 0 for the front Tip and 31 → 12 for the rear Tip. This is a reduction in one dependency category, not proof of independent shell documents.

## Immediate downstream validation

`Pocket016` and its downstream `Hole` feature were recomputed after the sketch change. Both remained valid one-solid shapes. Before/after Boolean symmetric differences were valid and returned zero volume. The candidate was saved and reopened with the master but without the monolith; a forced recompute of these immediate consumers passed after reopen.

This validates the reconstructed sketch and its immediate downstream consumers only. It does not establish complete front or rear Tip equivalence.

## Full front-Tip attempt

A disposable FreeCADCmd run opened the candidate and master. The candidate's front Tip, `RestoreUpperFaceplateHoles`, opened valid as one solid before recompute. Its measured cached properties were volume `37,683.517481 mm³`, area `23,570.962457 mm²`, 562 faces, 1,654 edges, and bounds `[-42.774377, -92.364725, -19]` to `[42.810208, 86.689108, 0]` mm. `Sketch019` reopened fully constrained with zero external references.

The test force-touched all 125 objects in the front Tip's expanded dependency closure and began `d.recompute([tip])`. FreeCAD emitted out-of-scope warnings for six width-controlled sketches referencing `ExteriorEnvelope`. After more than four minutes of high CPU use, the recompute had not returned or reached the shape-comparison/save stages. The disposable process was stopped. It did not save the candidate. Therefore full front-Tip native recomputation, geometry equivalence, and save/reopen after the forced recompute remain **unverified**. The previously successful immediate feature checks remain the strongest validation for this candidate.

The candidate remains unsuitable for promotion or assembly integration. The 12 remaining rear-Tip Sketcher references and active cross-shell Body dependencies require further targeted work. The slow front-Tip recompute also needs profiling before repeating a whole-closure force-touch; no further broad recompute is justified without narrowing the expensive features or dependency paths.

## Preservation

No tracked CAD source file was changed. The worktree's pre-existing untracked `00000.log`, `hardware/freecad/backups/`, and `hardware/freecad/pendant-bodies/front-rear-shells.FCStd` were left untouched. This report records a disposable experiment, not a production geometry change.
