# Front-shell feature recompute trace

Date: 2026-10-30
Branch: `hardware-integration`
Scope: disposable diagnostic only; no FreeCAD document was saved.

## Purpose

The prior disposable front-shell Tip recompute ran for several minutes without a useful feature-level progress record. This trace isolated sequential recomputation of the 72 Tip-reachable front Body group members in the rear-sketch-reference-pruned candidate at `/tmp/rear-tip-unconstrained-ref-prune-20261030/pendant-bodies/front-rear-shells-rear-sketch-refs-pruned.FCStd` (with its adjacent master document).

The macro touched and recomputed each unsuppressed member individually, recording the current object before entering FreeCAD's recompute call. It did not save the document. As a result, this is a timing and feature-state diagnostic, not a clean full-document recompute or geometry-acceptance test.

## Results

The trace completed 66 feature stages before being stopped. All 66 returned successfully, had valid available Shapes, and recorded no exceptions. Three features took longer than five seconds:

| Feature | Recompute time | Result |
|---|---:|---|
| `Pad` | 35.522 s | valid one-solid shape; measured geometry unchanged across stage |
| `Pad015` | 25.690 s | stage returned successfully |
| `PreserveOriginalFrontExterior` | 11.540 s | stage returned successfully |

The trace then reached `SmallHangerPocketBody` at group index 67 of 72. That individual stage consumed more than 4 minutes 29 seconds at approximately 99% CPU and did not return. The disposable FreeCADCmd process was interrupted. It had not reached the later shell Tip stage and did not save the document.

The current hanger profile sketch, `SmallHangerProfileBody`, had already recomputed successfully at index 66. Its recorded bounds were X `[-17.8, 17.8]`, Y `[80.5, 83.5]`, Z `1.0` mm, consistent with the existing 35.6 × 3.0 mm closed obround. This does not validate the downstream cut or structural adequacy.

## Interpretation and next action

The observed prolonged stage is `SmallHangerPocketBody`, the front-shell 37 mm hanger pocket feature. This is a concrete performance bottleneck and is consistent with the earlier front Tip recompute delay, but this trace alone does not prove it was the only source of the earlier delay. The paired rear hanger feature, downstream `SmallHangerPocketBody002`, and whole-shell feature history have not been freshly recomputed in this experiment.

Do not retry the full front/rear history as a first diagnostic. Next, inspect the hanger Pocket's profile/support, direction, length, Base geometry complexity, and resulting cut in a disposable session; then profile only the smallest relevant upstream dependency set and the hanger feature. Preserve the closed through-both-shells requirement. The pendant mass is not yet measured, so the selected 5× proof-load target cannot yet be converted to a force or used to claim strength. The earlier sampled sub-0.25 mm material concern and absence of structural analysis remain open.

No production CAD, master, or modular assembly was modified. This report records a diagnostic, not a geometry change or safety validation.
