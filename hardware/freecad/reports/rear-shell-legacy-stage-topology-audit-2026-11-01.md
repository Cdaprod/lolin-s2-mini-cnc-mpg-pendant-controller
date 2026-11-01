# Rear-shell legacy stage and topology audit — 2026-11-01

## Result

The saved legacy value **+475.701580 mm³** is the net of three cached feature-stage changes, not one piece of material that can be removed:

| Saved stage | Volume change | BOP findings in saved shape |
|---|---:|---:|
| `Body002FullWidthSeat` baseline | — | 336 |
| `RearBossToWallLoadPaths` | +383.733575 mm³ | 2,440 |
| `RearBossShoulderTransitions` | −14.961450 mm³ | 740 |
| `RearBossWallRamps45` | +106.929454 mm³ | 740 |
| **Net** | **+475.701580 mm³** | — |

The read-only FreeCAD BOP check reported self-intersections, too-small edges, and invalid curve-on-surface records in the saved legacy shapes. The cached base was already topologically problematic; the load-path stage greatly increased the findings, and the shoulder-transition stage reduced them. These counts describe saved BRep topology checks, not the number of non-manifold mesh edges and not a direct proof of physical defects.

![Approximate mesh occupancy changes around the four boss-to-wall regions](images/rear-shell-loadpath-mesh-occupancy-2026-10-31.png)

## Mechanical role and location

The four paths bridge screw-boss roots to shell-wall profiles. The middle pair uses R7.0 mm root circles near X=±27 mm, Y=58.5 mm and R5.1 mm wall circles near X=±26 mm, Y=65 mm. The lower pair uses R4.2 mm roots near X=±18 mm, Y=−17.7566 mm and R3.5 mm wall profiles near X=±22.196 mm at the same Y. Their sketch planes span Z=−18.8 mm to −15.6 mm for the middle supports and Z=−18.8 mm to −14.9 mm for the lower supports. These positions and the original edge-defect clusters support the intended screw-boss-to-wall reinforcement role.

An existing 0.5 mm mesh-occupancy sample localizes about +262.875 mm³ net sampled occupancy across the four boss/wall neighborhoods: approximately +42.75/+40.625 mm³ at the upper pair and +90.625/+88.875 mm³ at the lower pair. The sampled extents are approximate voxel-center bins. Because the legacy final mesh is non-watertight and under-represents its saved BRep by about 223.155 mm³, the occupancy map cannot reconcile the exact +475.701580 mm³ BRep change.

The native reconstruction retains four parametric AdditiveLoft supports. In its saved feature sequence, BOP findings rise from 12 in the fused base to 24 after the first middle support, 36 after the second, 40 after the first lower support, and 40 after the second; the final finished Tip reports 42. Despite those residual BRep findings, the candidate recomputes as one valid solid and its exported mesh has zero boundary and zero overincident edges. This is a substantial mesh repair, but not proof of exact legacy shape equivalence or load capacity.

## Disposition

Do not discard the reinforcement. The evidence identifies its purpose and approximate regions, but not an exact pointwise material difference. The original cached feature outputs are not trustworthy enough for Boolean difference mapping, and a previous box-common grid failed its volume-conservation check. Preserve the protected monolith and the native reconstruction as separate references. Keep the receiver-connected shell assembly as a review candidate until shell mating and the remaining BRep findings are resolved.

The audit read saved monolithic shapes only: it did not recompute or save the protected document. Full measurements and caveats are in the [machine-readable record](rear-shell-legacy-stage-topology-audit-2026-11-01.json), the [native load-path review](rear-shell-native-loadpath-manifold-review-2026-11-01.md), and the [mesh occupancy study](rear-shell-mesh-occupancy-localization-2026-10-31.md).
