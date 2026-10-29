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

## Pad labels, source profile, and intended geometry

Read-only inspection of the monolith shows that these are native features in `Body002` (`Body_RearShell`), ordered after `Pocket015 - Magnet Slot`; they were not created by the modular migration. Their internal labels are still generic for all three Pads.

| Feature | Label and input | Feature settings | Saved state |
|---|---|---|---|
| `Pad020` | `Pad020`; base `Pocket015`; profile `Binder016.Face2`, `Binder016.Face1` | Length 0.8 mm, straight pad, along +Z | Suppressed |
| `Pad021` | `Pad021`; base `Pad020`; profile `Binder016.Face4`, `Binder016.Face3` | Length 0.8 mm, taper −13°, along +Z | Suppressed |
| `Pad022` | `Pad022`; base `Pad021`; profile `Pad021.?Face97` | `UpToShape`, saved length 10 mm; its selected generated face no longer resolves | Suppressed |

`Binder016` is labeled `Binder016` and supports `Body.Sketch019 - Alignment Pockets` from the front shell. That sketch has 42 geometries and 124 constraints at Z = −19 mm; it is also used by front-shell `Pocket016 - Alignment Grooves`. The binder contains four planar faces (48 edges, no solids), with bounds X `−33.874…33.875`, Y `−84.394…76.985`, Z `−19 mm`. The paired face selections used by Pad020 and Pad021 therefore correspond to the front-shell alignment-groove profile. Based on the native labels and the generated feature geometry, their intended purpose is complementary rear-shell registration tongues/pads that engage those grooves. This is a well-supported interpretation of Pads 020–021; Pad022's exact intended form remains unknown because its up-to-face profile is broken.

To distinguish intended geometry from the suppressed cached shape, a disposable copy of the monolith was made and only Pads 020 and 021 were unsuppressed in sequence. Pad020 recomputed as a valid one-solid shape with volume `38508.061656 mm³` (an increase of `162.255490 mm³` from Pocket015) and Z maximum `−18.2 mm`. Pad021 then recomputed as valid one-solid geometry with volume `38565.812640 mm³` (a further `57.750984 mm³`) and the same bounds, with its −13° taper. These tests confirm that the two pads would add real protrusions toward the front-side grooves. Pad022 remained suppressed and became `Touched`; its broken `?Face97` was not repaired or tested as active. The disposable test was not saved or promoted, and the monolith was not changed. FreeCAD also logged unrelated out-of-scope-link/refine warnings during the limited recompute, so this result validates the two pad shapes only, not the full document.

The following active `RemoveWarpProneTongues` feature is labeled “Remove continuous thin tongues to parting plane,” has a 0.81 mm pocket length, and uses `RearSeamFlushSketch`. Its name and placement in the history indicate the author intended to trim thin tongue material at the seam after the pad branch. Because the Pads are currently suppressed and the pocket's saved shape equals its base shape, the saved model does not establish how much of the would-be tongues the pocket removes when the pads are enabled. Do not call the branch an obsolete experiment or delete it based on the present evidence: the pair's alignment function is evident, but the active design intent of Pad022 and the interaction with the seam-trimming pocket need a separate disposable test before any history edit.

## Current saved shell-interface inventory

The saved feature states show that the Sketch019 alignment groove/tongue system is **not present in the current final shell Tips**: front `Pocket016 - Alignment Grooves` and `RestoreFrontSeamLand` are suppressed, as are rear `Pad020`–`Pad022`. The front sketch and rear binder remain in the model tree as source/reference history. `RemoveWarpProneTongues` is unsuppressed, but its saved shape matches its base while the tongue Pads are suppressed. Thus the paired registration system appears designed but is currently disabled in the saved geometry.

Other candidate shell-interface features are present:

| Feature group | Saved state and observed role |
|---|---|
| `FrontTaperedSeats` + `RearTaperedSeats` | Both unsuppressed. The front feature is labeled “Complementary tapered receivers - 0.25 mm radial clearance”; its two circles are centered at X = ±18 mm, Y ≈ −17.757 mm, radius 4.05 mm, with 1.1 mm depth and 12° taper. The rear feature is labeled “Broad shallow tapered screw-seat locators”; its two circles share those centers, radius 3.8 mm, with a 0.8 mm pad and 12° taper. These are screw-seat features, not evidence of a shell-seam tongue-and-groove system. |
| Full-width seam interface | `RearFullWidthReceiver`, `FrontFullWidthReceiver`, and rear `Body002FullWidthSeat` are unsuppressed Boolean features with valid cached one-solid shapes. Their names and role in the shell history indicate broad receiver/seat mating geometry, making them the strongest existing candidate for continuous shell registration in the current design. Each was marked `Touched` at inspection, so this read-only inventory does not certify fresh recomputation, contact, or clearance. |
| Matched shell profiles | Rear matched inner cavity and related width-controlled rear profiles remain unsuppressed and shape-valid. They define the shell wall/envelope relationship; they are not discrete registration keys by themselves. |

This inventory does not establish that the full-width interface alone prevents shell shift or that it has acceptable assembly clearance. No current saved discrete alignment tongue is verified. A separate, narrowly scoped interface-fit check would need to recompute disposable copies of the active full-width receiver/seat chain, compare their mating surfaces, and check interference/clearance in the assembly coordinate frame. No geometry was changed for this inventory.

## What the master substitutions changed—and why the count stayed the same

The disposable candidate retains the validated frame-preserving `App::Link.LinkPlacement` setup:

| Candidate input | Candidate reference | Reachable from `RearBossWallRamps45`? |
|---|---|---|
| `Binder008.Support` | `LinkSharedRearSeamSketch` → master `SharedRearSeamSketch`, placement Z = −19 mm | No |
| `Binder009.Support` | `LinkSharedRearBackSketch` → master `SharedRearBackSketch`, placement Z = −27 mm, yaw −5° | No |
| `RearFullLandTransfer.Base` | `LinkSharedRearLandTransfer` → master `SharedRearLandTransfer` | No |

These references are present in the candidate document, and their frame-preserving geometry tests passed in the prior validation. They are not in the `RearBossWallRamps45` dependency closure. The seam/back profile and land-transfer objects therefore do not form the root-to-tip path that the earlier broad shell-pair reports implied. Replacing them cannot reduce this Tip-rooted closure, so the unchanged `51 → 51` result is expected. The candidate’s three master links are real cross-document `App::Link` references, but they are outside this Tip’s transitive feature inputs.

Body and top-level Part membership, Body `Group` ownership, and document-container references do not contribute to the active geometry traversal. Counting those objects (or all objects in a dependency-bearing Body) yields a different set and cannot be compared with this Tip-rooted result. The prior 331/307-style closure figures should not be used as a target for this audit.

## Disposable test: bypassing the suppressed tongue branch (2026-10-29)

A disposable copy `/tmp/remove-warp-bypass.FCStd` tested the narrow hypothesis that the active `RemoveWarpProneTongues` Pocket can use `Pocket015` directly as its `BaseFeature`, while leaving Pads 020–022 suppressed. The source monolith, master, and modular assembly were not edited.

The Pocket and all 16 downstream features through `RearBossWallRamps45` recomputed as valid, one-solid, `Up-to-date` shapes. The active Tip retained its baseline volume (`40961.35900828918 mm³`) and bounds (`[-39.909661,39.879179, -88.312349,86.688463, -36.844984,0] mm`). `RemoveWarpProneTongues` itself had zero symmetric-difference volume against its original cached shape. The Tip-rooted feature closure dropped from 51 to 47 objects; neither `Pad022` nor `Binder016` was reachable, including after saving, closing, reopening, and recomputing the downstream chain.

However, the fully recomputed candidate Tip had a **22.0978457 mm³ symmetric-difference volume** against the original Tip, both before and after reopen. Equal Tip volumes and equal bounds do not establish geometric equivalence. The specific downstream feature that first introduces the spatial difference was not isolated in this experiment. Therefore the candidate is **rejected for promotion**, and this test does not establish that the old branch is safe to remove. It does establish that the branch can be disconnected without a recompute error, while also exposing a downstream topology-sensitive geometry change that requires localization before another candidate can be accepted. The temporary candidate is diagnostic only.

FreeCAD emitted existing out-of-scope-link/refine warnings during recomputation, including links involving `FrontFullLandTransferRestricted` and `RearFullLandTransfer`; the affected chain objects nevertheless reported valid one-solid shapes. Those warnings are not proof that the difference is harmless.

## Read-only shell mating check (saved cached shapes)

In the authoritative monolith, the front Tip (`Body.Tip`) and rear Tip (`Body002.Tip`) are valid one-solid shapes in a common coordinate frame. Their cached-shape Boolean common volume is `0 mm³` and `distToShape` reports minimum separation `0 mm` with coincident points on the Z = −19 mm seam. This indicates no volumetric intersection and at least local surface contact in the saved shapes; it does not establish adequate contact area, assembly retention, or tolerance clearance.

`FrontFullWidthReceiver` and `Body002FullWidthSeat` cached shapes also report `0 mm³` common volume. The intermediate receiver/seat features remain marked `Touched`, so these results are strictly read-only observations of saved caches, not recomputed acceptance results. The front Tip versus rear Tip surface contact is consistent with the common seam plane; the actual full-width mating faces and clearance envelope still require a controlled recompute and face-level inspection. No geometry was changed.

The receiver hierarchy is also not a one-to-one component pair: `FrontFullWidthReceiver.BaseFeature = RearFullWidthReceiver`, and the front `FrontFullWidthReceiver` cached shape is fully contained in `RearFullWidthReceiver` (`common = 37466.592366 mm³`). Do not interpret that intermediate Boolean relationship as shell-to-shell interference.

## Outcome and next action

The bypass provides a real active Tip-closure reduction (51 → 47) and removes the suppressed front-shell Binder016 path from that candidate's complete Tip-rooted dependency graph, but it fails exact geometry preservation downstream. Preserve the source history. Next, localize the first downstream feature whose recomputed shape differs, comparing shapes feature-by-feature from `RemoveWarpProneTongues` to `RearBossWallRamps45`; only then can a less topology-sensitive bypass be designed. Separately, recompute disposable copies of the receiver/seat chain and inspect the seam faces before making any mating-clearance claim. Do not promote this candidate or alter production CAD from these results.
