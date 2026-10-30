# Mechanical refinement backlog

This is a permanent workstream alongside the modularization and parameterization work recorded in `modular-migration-status.md`. Keep the original `pendant.FCStd` as the geometry/history baseline. Make intentional design changes only in disposable candidates first, record the reason and affected features, and promote only after native recompute, save/reopen, geometry, fit, and manufacturing checks pass.

## Priorities

1. **Top hanger opening (first mechanical refinement).** Measure both shell cuts and the remaining material/load paths; refine the opening and upper transitions while preserving alignment and screw/mating geometry. Do not use a simple global enlargement if it thins the shell or approaches the upper screw seats.
2. Inspect localized thin walls, fragile protrusions, sharp internal corners, and printability; favor small reversible sketch/feature changes.
3. Check screw passages, head seats, shell mating/alignment, cable and connector clearance, component access, and assembly convenience.
4. Look for unnecessary material, excessive wall thickness, abrupt curved-surface transitions, and difficult overhangs.

## Change categories

- **Geometry-preserving refactor:** keep the manufactured shape unchanged while improving dependencies, modularity, or parameterization.
- **Intentional mechanical improvement:** allow a controlled shape change only against explicit functional, structural, fit, and printability targets. Keep a measured baseline and document affected features and rationale.

Printer-dependent wall targets must remain provisional until nozzle, material, orientation, and slicer/perimeter settings are known. Do not describe a fillet as a strength improvement without checking the remaining material and load path.

## Current hanger status

- The first read-only audit is recorded in `reports/top-hanger-refinement-initial-audit-2026-10-30.md` and its JSON companion.
- A sketch-only, reversible 3.5 mm-wide slot candidate was valid and aligned across both shells, but the candidate shifted downward and left only about 0.25 mm at a sampled rear transition. **Rejected; not saved to production CAD.**
- A modest downward shift also reduces clearance to the nearby upper M2 head seats. Do not promote a dimensional change until the profile can satisfy both shell-material and screw-seat clearance checks.
- The required function is now confirmed: this must remain a **closed, load-bearing hole through both shell Bodies**, able to carry the pendant’s weight. A disposable 3.1 mm-wide / Y=81.05 mm center sketch candidate updated both hanger pocket outputs but did **not** propagate into the final Body Tips; downstream generic shape features retained their prior output. It was rejected as both a geometry proposal and an incomplete propagation test. Section screens show near-zero webs and possible local edge breakthrough, but are based on saved intermediate shapes and are not full-history or strength validation. The final saved Tip also has a rear section with no upper interval at X=12, Z=−25 mm, but touched/stale upstream features mean this remains diagnostic. Do not claim the current hanger is closed/load-safe until both shell chains regenerate and are checked.
- The dormant `Sketch015` profile is not a safe starting point: it is underconstrained, narrower than the active opening, leaves roughly 0.01 mm at sampled front-shell sections, and breaks through the rear shell at sampled side sections. Its associated helper cutter is a frozen `PartDesign::Feature`, not an active editable shell operation.
- The bounded read-only measurement can be reproduced with `scripts/audit_top_hanger_sections.py`; it records the source checksum and samples shell sections without recomputing or saving the monolith. Its optional 1 mm X/Z grid is a localization tool, not a proof of global minimum thickness or load strength.
- Next useful step: recover the construction inputs for `FrontBossToWallLoadPaths` and `RearBossToWallLoadPaths` from existing sketches and clearance features; they are generic stored-shape features with no regeneration script. `RearBossShoulderTransitions` is also stored geometry tied to generated edges. A five-feature stored-shape-delta replay exceeded its 170-second bound and produced no saved result; do not repeat it unchanged. Create a local disposable regeneration test, then design a reinforced bridge/boss integrated with both shells. Keep a continuous closed aperture and load path. Establish a measurable load case and inspect the full profile before testing native parametric reinforcement. Preserve screw-seat clearance, shell mating, and assembly fit; separate monolith recompute errors from candidate behavior.

## Validation gate for intentional changes

Record baseline and candidate dimensions; affected Bodies, features, and sketches; minimum material around the opening; opening alignment; screw/head-seat separation; nearby shell mating and retention geometry; solid validity; and the reason for the change. Require native feature recomputation, save/close/reopen/recompute, assembly fit and interference checks, and an appropriate manufacturing review. If these cannot be demonstrated, keep the proposal as an unpromoted candidate and document the blocker.
