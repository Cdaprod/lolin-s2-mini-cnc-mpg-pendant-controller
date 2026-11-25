# Rear shell unused Sketcher-reference pruning test

Date: 2026-10-30  
Branch: `hardware-integration`  
Scope: disposable shell-pair candidate only. No production CAD file was edited.

## Purpose

After replacing the 13 generated-edge references in `Sketch019` with local constrained construction arcs, a rear Tip audit found 12 more active Tip-reachable Sketcher external references. They were six unconstrained references each in `RearAlignedHeadSeatSketch` and `RearAlignedM2PassageSketch`, all pointing to generated edges on `RearScrewAlignmentBinder`. FreeCAD logged these source subelements as missing during the prior rear-shell recompute.

## Candidate change

Input candidate SHA-256: `e61deb7df422df2cd30e7109c521385198d501a4b7a2ed4832c94499f263afe7`.  
Output candidate: `/tmp/rear-tip-unconstrained-ref-prune-20261030/pendant-bodies/front-rear-shells-rear-sketch-refs-pruned.FCStd`  
Output SHA-256: `e5ba37e77c139d95120d62a850ed1f235e1fc79134bfba3f6ca92645bd083e3e`

The test removed only those 12 unconstrained external references. Each sketch retained its six native circles and all 14 original constraints; both remained fully constrained with zero degrees of freedom. The in-plane geometry and constraints compared unchanged before and after the deletion. The master document remained beside the candidate at the original relative path.

The two consuming features were `Pocket018` (M2 passages) and `Pocket019` (head seats). Their saved and recomputed shapes remained valid single solids with the same measured properties:

| Feature | Volume (mm³) | Area (mm²) | Faces / edges | Bounds (mm) |
|---|---:|---:|---:|---|
| `Pocket018` | 39,861.770316 | 28,623.976150 | 159 / 458 | `[-36.233262, -85.564273, -36.844984]` to `[36.233272, 86.688463, -18.2]` |
| `Pocket019` | 39,332.691370 | 28,906.679873 | 173 / 482 | `[-36.233262, -85.564273, -36.844984]` to `[36.233272, 86.688463, -18.2]` |

## Rear Tip validation

The updated rear Tip closure contained 156 expanded dependency objects (156 were present and touched). A forced native recompute returned after 152.99 seconds. `RearBossWallRamps45` and `Body002.Shape` were valid, one-solid shapes with matching measured volume, area, topology counts, and bounds. The Tip’s 0.05 mm mesh hash matched its pre-recompute saved candidate:

`abb7182718963ceb656e500b85b30aa96add6e45733ec259df183f0f545d0507`

The full-shape BREP Boolean symmetric-difference attempts were invalid and returned 16-solid outputs. They do not establish exact BREP equivalence. The identical measured descriptors and tessellated mesh are positive comparison evidence at the tested resolution, not a mathematical proof.

The candidate was saved, closed, reopened with `pendant-master.FCStd` and no monolith, then targeted-recomputed. In a fresh process without invoking MeshPart tessellation before the bounds check, the Body and Tip remained valid and one solid, with matching full bounds and Tip volume `40,961.359008 mm³`; the targeted recompute returned zero. `Pocket018`, `Pocket019`, both sketches, and the Tip were `Up-to-date`. The Body container still reported `Touched` after reopening. Recompute logs no longer contain missing generated-edge warnings for the two pruned sketches. They still contain out-of-scope warnings for `ExteriorEnvelope` references.

## Dependency result and disposition

The serialized Tip-rooted audit changed from 44 ordinary / 157 expanded dependencies to 44 ordinary / 156 expanded dependencies. Active Sketcher external-geometry references changed from 12 to zero. This removes the missing, unconstrained `RearScrewAlignmentBinder` sketch-edge references, but does not remove the actual shell coupling. Extraction readiness remains **BLOCKED** with 54 dependency blockers. The active `RearFullLandTransfer.Base → SmallHangerPocketBody` dependency remains, as does its `Tool → RearFullLandCutter` input.

This is a validated disposable feature-history cleanup, not a standalone rear-shell component. Do not promote the candidate to the assembly or replace the static shell representation. The `pendant.FCStd`, `pendant-master.FCStd`, modular assembly, and pre-existing untracked shell-pair file remain unchanged.
