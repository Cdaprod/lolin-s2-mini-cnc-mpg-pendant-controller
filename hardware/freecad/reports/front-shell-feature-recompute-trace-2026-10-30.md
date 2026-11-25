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

## Follow-up and corrected interpretation

Subsequent tests show that the Pocket is not intrinsically a multi-minute operation. On a fresh candidate with its relative master document correctly resolved, touching and recomputing the direct base chain (`SideButtonRemoveFragileSeatRim` → `PreserveOriginalFrontExterior` → `SmallHangerProfileBody` → `SmallHangerPocketBody`) completed the Pocket in 3.654 s. It remained a valid, up-to-date, one-solid shape with 339 faces, 1,033 edges, and volume 40,859.167821 mm³.

The long delay was reproduced only after other master-driven width-profile and downstream features had been recomputed, leaving a broad dirty dependency set. Recomputing `PreserveOriginalFrontExterior` marked 47 dependents touched, including the front and rear Bodies, shell binders, land transfers, and seam/back profiles. Recomputing `WidthControlled_FrontMatchedProfile0` also dirtied `AdditiveLoft` and its descendants. Explicitly recomputing the loft alone did not clear the full downstream dirty set. This strongly suggests that the earlier Pocket call was paying for a broader, incorrectly ordered dependency update; it does not prove which individual descendant accounts for all of the stall time.

A dependency-ordered disposable replay refreshed the six master-driven profiles before their loft/cavity consumers and the later shell features. The Pocket then recomputed in 3.6 s, followed by `FrontFullLandTransfer` (8.9 s), `RearFullLandTransfer` (11.7 s), `RearFullWidthReceiver` (9.2 s), and `FrontFullWidthReceiver` (57.6 s). A forced save/reopen Tip recompute completed, but geometry acceptance failed: the in-memory Tip bounds contracted by about 3 mm while volume and face/edge counts stayed the same; after reopen the bounds returned to the saved baseline while the 0.05 mm mesh hash differed. The candidate remains rejected. During the same ordered run, `FrontMatchedInnerCavity` was the first feature whose in-memory bounds changed; later read-only inspection of the saved/reopened candidate found the cavity and six profile geometry records matching the baseline descriptors. The exact source of the Tip mesh difference remains unresolved.

One attempted pocket-length control copied the component file outside its expected relative path and therefore failed to resolve `pendant-master.FCStd`; all timing and geometry conclusions from that control are withdrawn. No cut-length change is proposed.

Next, investigate the unstable feature-level geometry and recompute ordering with a narrow, master-resolved comparison centered on `FrontMatchedInnerCavity`, its BaseFeature/Profile/Sections, and the stored downstream load-path features. Do not interpret the earlier Pocket stall as an isolated boolean bottleneck. The paired rear hanger cut and complete shell pair still require validation. Preserve the closed through-both-shells requirement. The pendant mass is not yet measured, so the selected 5× proof-load target cannot be converted to force or used to claim strength; the earlier sampled sub-0.25 mm material concern and absence of structural analysis remain open.

No production CAD, master, or modular assembly was modified. The saved ordered candidate is disposable evidence, not a geometry-preserving replacement or safety validation.
