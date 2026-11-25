# Top hanger: legacy transition recovery test

Date: 2026-10-29  
Branch: `hardware-integration`  
Scope: read-only source inspection and unsuppression/recompute test on a disposable copy. No production CAD file was saved or changed.

## Structural requirement

The top hanger is a **closed hole** that must carry the pendant's weight through both the front and rear shell Bodies. Keeping the hole closed and aligned through both Bodies is a hard functional requirement. It is not enough for the CAD opening to look continuous: the surrounding material and load path must also be demonstrated to be adequate. This test did not establish strength or approve any dimensional change.

## Findings

The authoritative monolith still contains four suppressed native `PartDesign::AdditiveLoft` features and their profile sketches:

| Feature | Root profile | Top profile | Recompute result in candidate |
|---|---|---|---|
| `MiddleLeftSupportTransition` | `MiddleLeftSupportTransitionRoot`: circle centered at X=-27, Y=58.5, Z=-14; radius 7 mm | `MiddleLeftSupportTransitionTop`: circle centered at X=-26, Y=65, Z=-10; radius 5.1 mm | Valid loft, but 2 solids (volume 40,440.6972 mm³) |
| `LowerLeftSupportTransition` | `LowerLeftSupportTransitionRoot`: circle centered at X=-18, Y=-17.756618, Z=-14; radius 4.2 mm | `LowerLeftSupportTransitionTop`: circle centered at X=-22.196, Y=-17.756618, Z=-9.3; radius 3.5 mm | Valid, one solid (volume 40,056.1721 mm³) |
| `MiddleRightSupportTransition` | `MiddleRightSupportTransitionRoot`: circle centered at X=27, Y=58.5, Z=-14; radius 7 mm | `MiddleRightSupportTransitionTop`: circle centered at X=26, Y=65, Z=-10; radius 5.1 mm | Invalid shape after recompute (one reported solid; volume 40,135.7394 mm³) |
| `LowerRightSupportTransition` | `LowerRightSupportTransitionRoot`: circle centered at X=18, Y=-17.756618, Z=-14; radius 4.2 mm | `LowerRightSupportTransitionTop`: circle centered at X=22.196, Y=-17.756618, Z=-9.3; radius 3.5 mm | Invalid; inherited the preceding invalid result |

All four features were suppressed in the source. Their cached suppressed shapes were identical to the base screw-support pad, so cached shape validity did not imply a regenerated loft. In the disposable candidate, unsuppressing the first loft created disconnected material; adding the second fused to one solid; the mirrored third loft became invalid. This confirms the legacy sequence is not a safe regeneration path for updated hanger geometry.

The sketches remain useful as intent and dimension evidence, but the native feature sequence needs a robust replacement or a separately generated, clipped-and-fused set of transition solids. The current `FrontBossToWallLoadPaths` and `RearBossToWallLoadPaths` remain generic stored-shape features; this experiment did not regenerate them or validate propagation into either final shell Tip.

## Method and protection

FreeCAD 1.1.1 opened the source read-only for inspection. A byte-for-byte disposable copy at `/tmp/pendant-legacy-transition-test.FCStd` was used for the unsuppression test and closed without saving. The authoritative file SHA-256 remains `dc2aeddf7be327c73022a1dc053bf8a27d5cf476e9cd68468a4ee73ab8264881`.

A complementary shape-difference calculation between the two stored load-path features and their bases exceeded a 60-second bound without producing a result. Its read-only worker was terminated; no file was saved. Do not repeat this same Boolean comparison unchanged. Use a localized mesh/section comparison or recover the generator inputs first.

## Disposition and next step

Reject the legacy loft chain for production use. Keep the closed, two-Body hanger requirement unchanged. The next experiment should reconstruct the missing boss-to-wall load-path solids from their original sketch profiles and explicit envelope/clearance tools, one shell at a time, on a disposable copy. Require one valid solid, screw and magnet clearance preservation, unchanged mating boundaries outside the intended transition, save/reopen/recompute, and updated hanger geometry reaching each final Tip. Do not claim that the hanger is safe until its material/load case is evaluated and a suitable structural or physical test is passed.
