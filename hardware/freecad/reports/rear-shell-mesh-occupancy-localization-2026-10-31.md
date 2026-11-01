# Rear-shell reinforcement mesh occupancy localization

Date: 2026-10-31  
Status: approximate spatial analysis of saved stage meshes; not an exact BRep difference or structural approval.

## Result

The exported mesh occupancy comparison places the main positive material change around the four rear screw-boss-to-wall transitions and adjacent lower webs. At 0.5 mm voxel-center sampling in the four defect neighborhoods, the observed net occupancy increase is about `262.875 mm³` (`283.625 mm³` added samples and `20.750 mm³` removed samples). The upper pair accounts for about `83.375 mm³` net and the lower pair about `179.500 mm³` net.

![Approximate occupancy difference map by Z slab](images/rear-shell-loadpath-mesh-occupancy-2026-10-31.png)

## Local 0.5 mm occupancy samples

| Boss/wall region | Added occupancy | Removed occupancy | Net | Sampled added extent (X, Y, Z mm) |
|---|---:|---:|---:|---|
| Upper-left | 46.500 mm³ | 3.750 mm³ | 42.750 mm³ | `[-33.75, -23.25] × [48.25, 64.75] × [-30.75, -19.75]` |
| Upper-right | 46.750 mm³ | 6.125 mm³ | 40.625 mm³ | `[23.25, 33.75] × [49.25, 68.75] × [-30.75, -19.75]` |
| Lower-left | 96.250 mm³ | 5.625 mm³ | 90.625 mm³ | `[-25.25, -10.25] × [-26.75, -10.75] × [-29.25, -20.75]` |
| Lower-right | 94.125 mm³ | 5.250 mm³ | 88.875 mm³ | `[10.25, 24.75] × [-24.75, -8.25] × [-29.25, -21.25]` |

The 1 mm full-shell ray-occupancy estimate found `300 mm³` of added and `42 mm³` of removed occupancy, or `+258 mm³` net. This places nearly all sampled positive change in the lower shell volume and is close to the four-zone `+262.875 mm³` result. It supports the interpretation that the changed material functions as screw-boss-to-wall support and lower inner-web reinforcement.

## Native candidate versus legacy mesh

The cold-recomputed native review candidate (`LowerRightInnerWebPad` Tip) is a valid one-solid BRep at `40,847.861700 mm³`; its mesh is closed. A 1 mm whole-shell ray-occupancy comparison to the saved legacy Tip mesh gives `173 mm³` added and `104 mm³` removed candidate occupancy (`+69 mm³` net). By Z band, candidate-minus-legacy is `−4 mm³` for `Z = −36.84…−25 mm` and `+73 mm³` for `Z = −25…−14.59 mm`.

At 1 mm sampling in the boss neighborhoods, candidate-minus-legacy is about `+2 mm³` upper-left, `−1 mm³` upper-right, `+31 mm³` lower-left, and `+32 mm³` lower-right. This suggests the upper native supports closely track the legacy mesh locally, while the new lower webs place additional material around the lower boss/wall regions. The lower webs are an intentional candidate reinforcement and remain unapproved pending fit and load-path review.

![Approximate native-candidate-minus-legacy occupancy map](images/rear-shell-candidate-vs-legacy-occupancy-2026-10-31.png)

The candidate's exact BRep volume is `113.497309 mm³` below the legacy BRep Tip, opposite the mesh occupancy estimate. The candidate processed mesh volume is `40,829.369299 mm³`; the legacy processed mesh volume is `40,738.203639 mm³`, a `+91.165660 mm³` mesh-volume difference. This sign disagreement is consistent with the legacy non-watertight mesh under-representing its cached BRep. Mesh occupancy therefore helps locate changed zones but cannot certify the candidate's spatial equivalence or classify the remaining exact BRep difference.

## Limits and disposition

The exact BRep volume increase from `Body002FullWidthSeat` to the saved `RearBossWallRamps45` Tip is `+475.701580 mm³`. The base mesh is watertight and has volume `40,466.973152 mm³` versus its BRep `40,485.657428 mm³`. The saved final Tip mesh is **not watertight** and has mesh volume `40,738.203639 mm³` versus its BRep `40,961.359008 mm³`. The final mesh therefore under-represents its BRep by about `223.155 mm³`; the whole-shell occupancy estimate is about `217.702 mm³` below the exact BRep change.

Consequently, this map identifies likely reinforcement locations but cannot account for the complete `475.702 mm³` BRep difference. The unresolved portion may be affected by the defective final tessellation and sampling; it must not be treated as redundant material. The 0.5 mm sampled extents are bins of occupied voxel centers, not exact faces or a substitute for BRep equivalence. The structural role is inferred from the four screw-boss/wall locations and feature labels, not proven by this mesh test.

The next CAD step remains validation of the native support/web candidate against the intended load path, magnet and screw clearances, shell mating, and downstream geometry. Keep the monolith and production assembly unchanged. The candidate's one-solid and manifold-mesh checks remain positive, but load capacity and exact legacy equivalence remain unverified.

Machine-readable source metrics and regional samples: [`rear-shell-loadpath-mesh-occupancy-2026-10-31.json`](rear-shell-loadpath-mesh-occupancy-2026-10-31.json). The prior BRep-cell method failed volume conservation and is explicitly rejected in [`rear-shell-cached-stage-regional-probe-2026-10-31.md`](rear-shell-cached-stage-regional-probe-2026-10-31.md).
