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
- Next useful step: derive an asymmetric sketch-level top transition that preserves the lower slot boundary/screw clearance, then evaluate material sections and the complete native shell chain in a controlled candidate. The monolith's pre-existing cross-Body and suppressed-feature recompute errors must be separated from any candidate regression.

## Validation gate for intentional changes

Record baseline and candidate dimensions; affected Bodies, features, and sketches; minimum material around the opening; opening alignment; screw/head-seat separation; nearby shell mating and retention geometry; solid validity; and the reason for the change. Require native feature recomputation, save/close/reopen/recompute, assembly fit and interference checks, and an appropriate manufacturing review. If these cannot be demonstrated, keep the proposal as an unpromoted candidate and document the blocker.
