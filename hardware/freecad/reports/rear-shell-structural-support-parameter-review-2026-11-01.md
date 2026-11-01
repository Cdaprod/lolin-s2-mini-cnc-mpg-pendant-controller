# Rear-shell structural support parameter review

Date: 2026-11-01

Status: validated disposable CAD study; not production-approved

## Native feature editability

The four reconstructed boss-to-wall support profiles and two lower inner-web profiles now read their dimensions from a single local **Rear support and web parameters** spreadsheet. Each profile remains fully constrained, and all six native PartDesign Pad lengths are expression-driven. The candidate preserves the previously reviewed 0.25 mm bottom-perimeter fillet and shallow anti-slip seats.

![Rear shell underside with support webs, bottom-perimeter edge finish, and anti-slip seats](images/rear-shell-structural-first-fillet-base-preserving-bottom-view-2026-10-31.png)

The builder [`build_rear_shell_structural_support_parameter_review.py`](../scripts/build_rear_shell_structural_support_parameter_review.py) makes a new file and refuses to overwrite an existing candidate. It does not open the protected monolith or production assembly for saving.

## Validation

- All six support sketches remained fully constrained after rebinding 42 expressions to 21 named dimensions.
- The baseline recomputed as a valid single solid with volume `40,847.861698 mm³`, 522 faces, and 1,509 edges.
- Moving `UpperBossXAbs` from 24.8 to 24.9 mm changed the Tip volume by `−1.483425 mm³`; restoring it returned to the original measured value.
- Increasing `UpperSupportPadSpan` from 13.0 to 13.1 mm changed the Tip volume by `+0.181494 mm³`; restoring it returned to baseline.
- Save, cold reopen, and recompute passed. The Body remained valid with one solid. A mesh generated from a copy of the reopened Body shape was closed with 16,020 facets.
- The protected monolith and production assembly were not modified.

Machine-readable evidence: [JSON validation](rear-shell-structural-support-parameter-review-2026-11-01.json).

## Structural material remains unresolved

The source cached history records `+383.733575 mm³` at `RearBossToWallLoadPaths`, `−14.961450 mm³` at `RearBossShoulderTransitions`, and `+106.929454 mm³` at `RearBossWallRamps45`, for `+475.701580 mm³` over the clean base.

The archived four-profile reconstruction produces `+124.036209 mm³` over the clean base and a valid one-solid closed mesh. Its volume remains `351.665371 mm³` below the saved legacy Tip before the newer lower-web and finishing operations. The current parameterized candidate is `113.497311 mm³` below that cached Tip after the lower webs, bottom fillet, and shallow seat cuts.

The profile recreation therefore demonstrates a manifold native construction method, but does **not** account for all old material or prove the remaining difference is redundant. The prior occupancy maps place much of the sampled change near the four boss-to-wall transitions, while BRep/mesh volume disagreement and failed whole-shape Booleans prevent exact spatial classification. Do not remove or promote geometry on the basis of these volume comparisons alone.

Structural capacity, including the 5× complete-pendant proof-load target, remains unverified. This review candidate is a parametric repair study, not the production rear shell.
