# Rear-shell selective loft refinement study — 2026-11-01

## Result

A disposable one-property change was cold-opened, recomputed, and checked. Disabling `Refine` only on `MiddleLeftNativeLoadPath` reduced BOP findings from 42 to 28 while retaining a valid single-solid rear Body and a closed two-manifold test mesh. The remaining findings are all `BOPAlgo_InvalidCurveOnSurface`. The R0.25 mm bottom-perimeter fillet remains in the native feature history before the crescent-seat pocket.

![Rear shell underside showing the reconstructed load paths and retained bottom finish](images/rear-shell-native-loadpaths-2026-11-01/rear-shell-bottom.png)

| Measure | Existing review candidate | Selective-refine candidate |
|---|---:|---:|
| Valid solids | 1 | 1 |
| BOP findings | 42 | 28 |
| Test-mesh boundary edges | 0 | 0 |
| Test-mesh overincident edges | 0 | 0 |
| Test-mesh degenerate facets | 0 | 0 |
| BRep volume | 41080.894143992 mm³ | 41080.894246519 mm³ |
| BRep area | 30697.513988156 mm² | 30697.513987678 mm² |
| BRep faces | 463 | 463 |
| Bounding-box difference | — | 0 mm on all six bounds |

The BRep volume differs by 0.000103 mm³ and area by 4.8×10⁻⁷ mm². Coarser and finer tessellations both remain closed; their reported volumes differ by 1.547 mm³ at 0.12 mm linear deflection and 0.438 mm³ at 0.03 mm. The triangulation counts and mesh area also vary, so the mesh comparison supports close surface agreement without proving exact BRep equivalence.

## Rejected variations and Boolean limitation

Turning refinement off on all four lofts lowered the BOP count to 30 but introduced four boundary edges. Turning it off on the middle-right or lower-right loft alone did not reduce BOP findings. The lower-left-only variation raised the count to 44 and introduced four boundary edges. Combining the middle-left and middle-right settings gave the same 28 findings and manifold mesh as the middle-left-only change.

An exact BRep Boolean comparison failed its conservation check: `common()` reported zero volume for nearly identical solids, and the first cut returned more volume than its entire input. The symmetric-difference operation then exceeded the 170-second limit. Those Boolean results were discarded. Exact geometry equivalence remains unproven.

## Disposition

Keep the selective candidate separate from the review assembly. Its BOP and manifold mesh results are improved, but its front/rear mating clearance has not been retested and exact BRep equivalence is unresolved. The protected monolith, master, and production assembly were not modified. No FEM or physical 5× proof-load test was performed.

Run the cold-open validator with [validate_rear_shell_selective_refine.py](../scripts/validate_rear_shell_selective_refine.py). The full measurements and trial results are in the [machine-readable validation record](rear-shell-selective-refine-review-2026-11-01.json).
