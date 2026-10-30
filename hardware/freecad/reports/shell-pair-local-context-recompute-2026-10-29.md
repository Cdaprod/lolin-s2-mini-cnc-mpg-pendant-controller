# Shell-pair local context and recompute test

Date: 2026-10-29

Branch: `hardware-integration`

Scope: disposable validation only. The production monolith, master, and modular assembly were not modified.

## Candidate and method

The test started from the disposable shell-pair copy that uses the previously validated `RemoveWarpProneTongues.BaseFeature = Pocket015` bypass. Its root Bodies are `Body` and `Body002`; it is not the untracked candidate in the worktree. The candidate initially retained `Context` XLinks to the monolith’s top-level `Part` container.

In the disposable file, a local `App::Part` container was created and the existing `Body`, `Body002`, and `RearExteriorEnvelope` objects were grouped under it. The 30 `Context` properties that pointed into the source monolith were rebound to the matching paths in that local container. No shape, sketch geometry, feature parameter, or placement was intentionally changed. The candidate was saved under `/tmp/front-rear-shells-bypass-validation-20261030/standalone/` with the master beside it; the monolithic file was omitted from that directory.

## Rear Tip result

The rear Tip was compared before and after the context change and after native recomputation. The Tip’s 157-object expanded dependency closure was force-touched from the saved manifest and recomputed through `Body002.Tip`.

| Check | Result |
|---|---|
| Recomputed dependencies | 157 touched; 156 recompute events |
| Recompute duration | 150.44 seconds |
| Tip | `RearBossWallRamps45` |
| Shape | Valid, one solid |
| Volume | 40,961.359008 mm³ before and after |
| Surface area | 30,590.902197 mm² before and after |
| Faces / edges | 534 / 1,517 before and after |
| Bounding box | `[-39.909661, -88.312349, -36.844984]` to `[39.879179, 86.688463, 0]` mm before and after |
| Save/reopen | Passed; the Tip reopened valid and `Up-to-date` |
| Documents loaded after reopen | Shell-pair file and `pendant-master.FCStd`; no monolith |
| Recompute immediately after reopen | 0 events because the reopened Tip was already current |

The post-reopen no-op is not a second forced rebuild. The fresh rebuild occurred before saving, in the monolith-free candidate. Geometry comparison here uses volume, area, topology counts, bounds, and shape validity; it does not prove exact BREP equivalence.

The auditor reports 44 ordinary and 157 expanded dependencies for the rear Tip. Its three active `Context` references now resolve within the shell-pair document. Extraction readiness remains **BLOCKED**: the rear Body still consumes front-shell and helper objects in the same paired document, including the land-transfer chain. This is a portable editable shell-pair candidate, not two independent shell component documents.

## Front Tip result

A separate disposable attempt force-touched the front Tip’s 125-object expanded closure and recomputed `Body.Tip`. It did not complete within 180 seconds and emitted missing Sketcher generated-edge references in `Sketch019` and `Sketch020`, along with existing out-of-scope references involving `ExteriorEnvelope` and `FrontFullLandTransfer`. The worker was stopped before its save stage. This does not validate the front Tip’s native feature history in the local-context candidate.

## Disposition

Do not integrate or promote this shell-pair candidate yet. The rear Tip’s recomputed geometry is promising, and rebinding `Context` metadata removes the monolith from the rear pair’s open/recompute requirement. However, the front Tip still lacks a successful forced closure recompute, and the shell Bodies remain coupled inside the same document. Keep the production assembly’s existing representations until both Tips and assembly links pass their own acceptance tests.

No CAD files were added to the repository. The pre-existing untracked shell-pair candidate, recovery log, and backup directory remain untouched.

## Follow-up: remove six unused `Sketch020` external references

The full front-Tip force-recompute attempt was stopped at its 180-second bound. The log showed unresolved external subelements in active `Sketch019` and `Sketch020` references, plus out-of-scope links from the width-controlled profiles to `ExteriorEnvelope`. The static dependency manifest marks 19 generated-edge references in these sketches as Tip-reachable: 13 in `Sketch019` and six in `Sketch020`. In `Sketch019`, five references drive constraints; these were left intact. All six `Sketch020` references were confirmed to drive no constraints.

In a second disposable copy, only the six `Sketch020` external references were removed with `Sketcher::SketchObject.delExternal`. Its 14 constraints, full constraint state, and native sketch geometry remained unchanged. The consuming `Hole` feature recomputed in 31.77 seconds and remained a valid one-solid shape. The pre/post shapes had matching volume (`39,878.513898 mm³`), area (`23,383.403264 mm²`), 248 faces, 736 edges, and bounding box. Both BREP symmetric-difference operations were valid and returned zero volume. After save/reopen, the candidate opened with only the shell-pair file and master; `Sketch020` remained without external geometries, and `Hole` retained its valid shape.

The serialized Tip-rooted audits confirm that active `Sketch020` external references fell from six to zero for both `Body` and `Body002`. The object closures remained 79/125 for the front Tip and 44/157 for the rear Tip, because the removed source objects remain required elsewhere in the feature graph. `Sketch019` remains unchanged with its five constraint-driving generated-edge references; the full front/rear shell Tip recompute was not repeated after this local cleanup.

This validates a narrow removal of unused sketch references in the disposable candidate. It does not validate either complete shell Tip after this cleanup, eliminate the cross-shell feature dependencies, or authorize assembly integration. The source candidate hash before this cleanup was `478d2944f85475edea9a021213f9fb2664ff445c4341e2876a242bed066d7ae3`; the saved experimental result hash is `b1e4a85658626e672cf2daf15839a6c1d1abbdfbe2fba45b1c6accd537656ac7`. Neither file is tracked or promoted.
