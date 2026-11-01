# Rear-shell topology locations and midpoint-section trial — 2026-11-01

## Candidate and purpose

This is a review-only analysis of `rear-shell-native-loadpath-selective-refine-review-2026-11-01.FCStd`. The protected monolith, production master, and production assembly were not opened for writing or changed.

![Rear-shell load paths, bottom perimeter finish, and anti-slip seats in the review candidate](images/rear-shell-native-loadpaths-2026-11-01/rear-shell-bottom.png)

## Feature-stage findings

The FreeCAD shape checker reports 28 `BOPAlgo_InvalidCurveOnSurface` edge/face lines on the final shell. An independent OpenCascade `BOPAlgo_ArgumentAnalyzer` run with curve-on-surface checking enabled groups these into 14 faulty edge/face pairs. The per-stage count identifies when the pairs first appear:

| Feature output | Fault pairs | Change at stage |
|---|---:|---:|
| `FreshFusedBase` | 6 | Baseline faults already exist in the fused shell base |
| `MiddleLeftNativeLoadPath` | 6 | No new pair |
| `MiddleRightNativeLoadPath` | 11 | +5 pairs |
| `LowerLeftNativeLoadPath` | 13 | +2 pairs |
| `LowerRightNativeLoadPath` | 13 | No new pair |
| `RearM2ClearancePocket` | 14 | +1 pair |
| `StructuralBottomPerimeterFillet` | 14 | No new pair |
| `RearCrescentAntiSlipSeatPocket` | 14 | No new pair |

This separates pre-existing base topology issues from the later additions. The R0.25 mm bottom fillet and the 0.10 mm crescent-seat pocket do not add curve-on-surface pairs in this candidate. The detailed paired-shape bounds, max distances, and curve parameters are in the [machine-readable audit](rear-shell-bop-location-audit-2026-11-01.json). The repeatable, read-only analyzer is [diagnose_rear_shell_bop_locations.py](../scripts/diagnose_rear_shell_bop_locations.py).

## Targeted native reconstruction test

A disposable midpoint sketch was inserted into the `MiddleRightNativeLoadPath` section chain. The midpoint radius and center were linearly interpolated between the existing two fully constrained circle profiles. This was tested as a possible way to regularize the transition surface.

After save, close, reopen, and recompute, the candidate remained a valid single solid with no feature-state errors and a closed manifold test mesh. It did **not** improve the topology checker: the final BOP count remained 28 lines / 14 pairs. Relative to the freshly recomputed selective-refine baseline, it changed volume by −2.591084 mm³ and area by −0.361153 mm² while preserving the bounding box. Because it changed the manufactured surface without reducing the identified faults, the midpoint trial is rejected and remains a disposable local candidate.

## Current validated limits

The selective-refine rear-shell candidate recomputes as one valid solid. Its 0.12 mm test mesh has 31,174 facets, zero boundary edges, zero overincident edges, and zero degenerate facets. Thus the exported mesh incidence is manifold at this tested tolerance. The separate BOP curve-on-surface findings remain unresolved and must not be described as fixed.

The preserved native R0.25 mm bottom fillet and crescent-seat pocket are in the candidate feature history. The load-path support geometry remains a review reconstruction; the old cached geometry's exact intended structural contribution and load capacity are not established by this topology study. Do not promote this candidate or claim the 5× pendant-weight proof-load target is met.

## Next CAD action

Prioritize the five pairs first appearing at the middle-right load path, then the two at the lower-left path and the one at the screw-clearance pocket. Any replacement must preserve the designed support roots and screw passages, reduce the actual fault-pair count, maintain the single-solid closed mesh, and pass save/reopen/recompute before the rear-shell candidate is considered for promotion.
