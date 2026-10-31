# Rear-shell repair candidate — volume-difference localization

## Finding

The current hybrid candidate is **351.665996 mm³ smaller** than the saved legacy rear-shell Tip (`40,609.693012` vs `40,961.359008 mm³`). Its native candidate Pad/Pocket chain recomputes to one valid solid, with the same outer bounds as the original. The source `Body002` also loads as a valid one-solid BREP, although its prior mesh audit found non-manifold edge incidence and the full legacy history has not completed a bounded recompute.

The discrepancy is a **known, intentional reconstruction difference**, not an unexplained drift: the candidate starts from `Body002FullWidthSeat`, adds four newly modeled support profiles, and cuts the six M2 passages. It does not regenerate the original `RearBossShoulderTransitions` and `RearBossWallRamps45` geometry. The difference is therefore not yet approved as mechanically equivalent or acceptable.

| History stage | Volume (mm³) | Change from prior stage (mm³) |
|---|---:|---:|
| Clean base — `Body002FullWidthSeat` | 40,485.657428 | — |
| Saved `RearBossToWallLoadPaths` | 40,869.391004 | +383.733575 |
| Saved `RearBossShoulderTransitions` | 40,854.429554 | −14.961450 |
| Saved active Tip — `RearBossWallRamps45` | 40,961.359008 | +106.929454 |
| Candidate after four native Pads, before clearance Pocket | 40,644.593132 | +158.935703 from clean base |
| Candidate Tip — `RearM2PassageClearance` | 40,609.693012 | +124.035584 from clean base |

Localized intersections against the four declared triangular pad prisms show the upper-left and upper-right candidate intersections match the saved legacy Tip within `6.5e-7 mm³`. In the lower-left and lower-right prisms, the saved legacy Tip contains no material while the candidate adds about `10.56 mm³` over the clean base in each. The lower ribs are deliberate new geometry in this reconstruction recipe; their load-path value and clearance to nearby internal components are not established here.

The old support and finishing chain contributes substantially more volume than the current replacement. The exact removed-material map outside the four local prisms remains unknown: whole-shell symmetric-difference Booleans on the defective legacy shell were unreliable or too slow, and prior full-history recomputation exceeded 170 seconds. This audit therefore does not claim exact BREP equivalence. It classifies the net difference as intentional but mechanically unresolved, with the omitted transition/ramp geometry as the primary design gap.

## Candidate assembly appearance

The candidate assembly remains a linked, nine-solid review model. The three static interim representations and hybrid rear-shell source are identified as such; this preview is not a structural analysis.

![Master-driven lead-in candidate assembly, underside](master-driven-leadins-assembly-preview/pendant-modular-assembly-bottom.png)

## Validation scope

The source monolith was opened read-only and its saved feature-stage shapes were measured without recomputing the whole legacy chain. The isolated hybrid rear component was recomputed in FreeCAD and its native Pad/Pocket stages measured. Local comparisons use FreeCAD `Shape.common(profile_prism)` intersection volumes; no CAD document was saved or changed. The reproducible audit is `scripts/audit_rear_shell_repair_difference.py`, with machine-readable values in `rear-shell-repair-difference-localization-2026-10-31.json`.

The existing screw and magnet clearance checks, assembly placement checks, and zero-intersection result against the front shell remain candidate-level evidence from the prior rear-shell validation. They do not validate the newly added lower ribs against all internal parts, nor demonstrate strength. Keep the rear-shell candidate unpromoted until the omitted transitions are characterized and fit/load-path requirements are reviewed.
