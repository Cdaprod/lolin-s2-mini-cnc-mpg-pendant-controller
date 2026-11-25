# Rear-shell lower boss-to-wall web candidate

Status: disposable review candidate; not installed in the modular production assembly.

## CAD change

Added two mirrored native PartDesign Pads, `LowerLeftInnerWebPad` and `LowerRightInnerWebPad`, to the hybrid rear-shell candidate. Their fully constrained sketch profiles extend the lower boss-side webs toward the adjacent shell wall. The profiles were shaped from a sampled section of the stored legacy mesh near `y = -18.34 mm`, where the current native support candidate lacks material. Each Pad is 8.5 mm long.

The rear shell base is still an imported static BREP in this candidate. The new sketches use fixed `Block` constraints, so they are editable native sketches but are not yet driven by named dimensional parameters or the master document.

![Approximate lower web section used to define the native Pad test](images/rear-shell-lower-inner-web-section-review.png)

## Validation

The candidate was recomputed, saved, closed, reopened, and recomputed again. The two web Pads each add about `131.66 mm³` to the preceding Tip. The resulting Body has one valid solid and a closed STL tessellation.

| Check | Result |
|---|---:|
| Rear Body Tip | `LowerRightInnerWebPad` |
| Body validity / solid count | Valid / 1 |
| Volume | `40,873.009665 mm³` |
| Surface area / face count | `30,824.129739 mm²` / 494 |
| Bounds (X, Y, Z) | `[-39.9097, 39.8792] × [-88.3123, 86.6885] × [-36.8450, 0] mm` |
| Fully constrained web sketches | 2 of 2 |
| Feature error states after reopen | None |
| STL triangles / welded edges | 19,162 / 28,743 |
| Boundary / over-incident / degenerate edges | 0 / 0 / 0 |
| Magnet-clearance, magnet-slot, and M2-passage volume change | 0 / 0 / 0 mm³ |

The independent STL incidence check used a `1e-5 mm` vertex-weld tolerance. The source’s existing intersection with the `Pocket - Magnet Clearance` diagnostic cutter is `168.000373 mm³`; it remained exactly the same before and after these Pads. The new feature did not change that baseline intersection.

## What the spatial comparison says

The stored legacy history has these reported stage-volume changes over `Body002FullWidthSeat`: `RearBossToWallLoadPaths +383.733575 mm³`, `RearBossShoulderTransitions −14.961450 mm³`, and `RearBossWallRamps45 +106.929454 mm³`, for a net `+475.701580 mm³`.

A 0.5 mm XY ray-section comparison of the tessellated shapes localizes most visible load-path additions around the paired lower boss regions. It shows a sampled web roughly 4 mm high near `x ≈ ±13 mm`, `y ≈ −18 mm`, with approximate `z` extent `−25.5…−21 mm`. The later 45-degree ramps appear mainly around the upper boss regions. This is a mesh-derived location/function estimate, not an exact BREP difference.

The updated candidate is `88.349343 mm³` below the stored legacy Tip by BREP volume. The raster comparison is also not exact: the legacy Tip’s tessellation is about `0.476%` below its BREP volume, versus `0.082%` for the candidate. In the lower zones the candidate contains both mesh-estimated extra material and legacy-only material. This indicates the legacy geometry changes across Y; a constant-section Pad matches the sampled section but does not reproduce the complete stored shape. The preview therefore describes the section used for this bounded test, not a fully restored reinforcement.

## Limits and next design step

This candidate passes native recompute, save/reopen, reserved-volume comparison, and manifold-mesh checks. It does **not** prove exact equivalence to the defective cached history, structural capacity, or the 5× pendant-weight proof target. It retains a static shell base and has not replaced the production assembly representation.

The next geometry experiment should use the measured Y-dependent section changes to test a native multi-section Loft or another controlled variable-profile feature. Keep the current Pad candidate as a comparison. Do not apply the R0.25 mm bottom fillet to this candidate until the reinforcement profile is accepted; the prior 19-edge fillet study remains separate. The protected monolith and production modular assembly were not modified.
