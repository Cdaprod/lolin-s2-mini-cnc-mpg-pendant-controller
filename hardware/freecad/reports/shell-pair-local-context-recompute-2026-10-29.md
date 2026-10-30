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
