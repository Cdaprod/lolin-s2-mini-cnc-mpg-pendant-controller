# Rear Tip dependency audit (5073c86)

This audit supersedes the earlier shell-pair closure estimates in `shell-dependency-report.md` for the specific question of what the **active rear Body Tip** reaches. It compares the saved monolith with the validated disposable frame-preserving candidate from commit `5073c86`. The candidate remains under `/tmp`; neither the monolith nor the production master/assembly was modified.

## Method and result

The root is `Body002.Tip = RearBossWallRamps45`. Starting there, the audit follows FreeCAD feature input dependencies (`OutList`) transitively, while excluding `PartDesign::Body` / `App::Part` ownership containers and Body `Group` membership. It then inspects property-level inputs (`BaseFeature`, `Profile`, `Support`, `Base`, and link targets) and the `Suppressed` state. This prevents Body ownership from expanding the traversal to every object in a Body.

| Graph view | Monolith | Frame-preserving candidate |
|---|---:|---:|
| Tip-rooted feature dependency closure, including suppressed ancestry | 51 | 51 |
| Traversal stopping at suppressed features | 29 | 29 |
| Front-shell subelement targets reached through the non-suppressed traversal | 0 | 0 |
| Front-shell subelement targets reached when suppressed ancestry is included | 1 (`Body.Sketch019`, via `Binder016.Support`) | 1 (`Body.Sketch019`, via `Binder016.Support`) |

The active Tip remains a valid one-solid shape in both saved documents. The source/candidate shape comparison and save/reopen/recompute validation for the frame-preserving candidate are recorded in the preceding report section; this audit itself was read-only and did not recompute or save either document.

## Remaining paths

There is one cross-shell source object in the complete feature ancestry. It is reached by two property paths through suppressed historical Pads:

1. `RearBossWallRamps45` → `RearBossShoulderTransitions` → `RearBossToWallLoadPaths` → `Body002FullWidthSeat` → `SmallHangerPocketBody002` → `USBConformalCoverSeatBody002` → `USB15mmCableAccessBody002` → `SideButtonRearNutRelief` → `SideButtonRearHeadRelief` → `Pocket019` → `Pocket018` → `RearTaperedSeats` → `ConformRearReinforcementToLoft` → `USBRearRecessStructuralBulk` → `RearMountReinforcement` → `RemoveWarpProneTongues.BaseFeature` → **suppressed `Pad022`** → **suppressed `Pad021.Profile`** → `Binder016.Support` → `Body.Sketch019`.
2. The same path through `Pad022` and `Pad021`, then **suppressed `Pad020.Profile`** → `Binder016.Support` → `Body.Sketch019` (Pad021 also retains `Pad020` as its BaseFeature).

The first shell-boundary edge on each path is `Binder016.Support`, which references subelement `Sketch019.` in the front-shell `Body`. The containing `Body` is a support owner, not a dependency on every object in that Body. The other Pad-to-Binder references are `Pad020.Profile = Binder016.Face2, Face1` and `Pad021.Profile = Binder016.Face4, Face3`.

`Pad020`, `Pad021`, and `Pad022` all have `Suppressed = True`. `Pad022.Profile` also retains the unresolved generated-face token `Pad021.?Face97`. `RemoveWarpProneTongues` is not suppressed and retains `Pad022` as its `BaseFeature`, so the full serialized feature ancestry still reaches the suppressed branch. Consequently, this report does **not** claim complete transitive independence. The branch is historical/suppressed in the feature tree; it is not reached by the traversal that stops at suppressed nodes. No change was made to remove or reroute it because doing so would rewrite that history without an engineering need demonstrated by the active geometry.

The five relevant shape records (`Pocket015`, `Pad020`, `Pad021`, `Pad022`, `RemoveWarpProneTongues`) each report one valid solid and identical volume `38345.80616578121 mm³`, surface area `27398.84845923107 mm²`, and bounds `[-36.233262, 36.233272, -85.564273, 86.688463, -36.844984, -19.0] mm`. The checked symmetric difference between `Pocket015` and each of `Pad020` and `Pad021` was exactly zero. This supports the classification of the suppressed pads as geometry-neutral in the saved state, but does not repair or validate the unresolved `?Face97` reference.

## What the master substitutions changed—and why the count stayed the same

The disposable candidate retains the validated frame-preserving `App::Link.LinkPlacement` setup:

| Candidate input | Candidate reference | Reachable from `RearBossWallRamps45`? |
|---|---|---|
| `Binder008.Support` | `LinkSharedRearSeamSketch` → master `SharedRearSeamSketch`, placement Z = −19 mm | No |
| `Binder009.Support` | `LinkSharedRearBackSketch` → master `SharedRearBackSketch`, placement Z = −27 mm, yaw −5° | No |
| `RearFullLandTransfer.Base` | `LinkSharedRearLandTransfer` → master `SharedRearLandTransfer` | No |

These references are present in the candidate document, and their frame-preserving geometry tests passed in the prior validation. They are not in the `RearBossWallRamps45` dependency closure. The seam/back profile and land-transfer objects therefore do not form the root-to-tip path that the earlier broad shell-pair reports implied. Replacing them cannot reduce this Tip-rooted closure, so the unchanged `51 → 51` result is expected. The candidate’s three master links are real cross-document `App::Link` references, but they are outside this Tip’s transitive feature inputs.

Body and top-level Part membership, Body `Group` ownership, and document-container references do not contribute to the active geometry traversal. Counting those objects (or all objects in a dependency-bearing Body) yields a different set and cannot be compared with this Tip-rooted result. The prior 331/307-style closure figures should not be used as a target for this audit.

## Outcome and next action

No feature or geometry was changed in this audit, and there is no CAD change to promote. The specific remaining front-shell reference is isolated to the suppressed `Binder016` branch. Before considering its removal, the next bounded test should establish whether the live `RemoveWarpProneTongues` result can be based on a pre-branch feature without changing its shape or breaking downstream features; otherwise preserve the current history and document that this reference is dormant but retained. Do not repeat seam/back/land substitutions as a route to reducing the active rear Tip closure.
