# Top-hanger feature-history audit

Date: 2026-10-29 (local)  
Branch: `hardware-integration`  
Source: `hardware/freecad/pendant.FCStd`  
Source SHA-256: `dc2aeddf7be327c73022a1dc053bf8a27d5cf476e9cd68468a4ee73ab8264881`

## Method

Ran `scripts/audit_hanger_feature_history.py` in FreeCAD 1.1.1 through a separate `FreeCADCmd` process. It opened the monolith to inspect stored metadata, did not recompute or save it, and closed the document. The source checksum before and after the audit matched. The JSON companion contains five feature records and 15 related sketch records.

Shape values below are **stored cached-shape descriptors** only. Their validity and the document's `Up-to-date` state do not establish that the feature chain will regenerate or that the hanger is strong enough.

## Findings

| Feature | `BaseFeature` | Cached volume (mm³) | Cached faces | Regeneration method recorded |
|---|---|---:|---:|---|
| `FrontBossToWallLoadPaths` | `FrontFullWidthReceiver` | 37,548.7539 | 544 | None |
| `RearBossToWallLoadPaths` | `Body002FullWidthSeat` | 40,869.3910 | 506 | None |
| `RearBossShoulderTransitions` | `RearBossToWallLoadPaths` | 40,854.4296 | 509 | None |
| `FrontHighToLowTransitions` | `FrontBossToWallLoadPaths` | 37,690.1198 | 560 | `regenerate_front_high_low_transitions.py` |
| `RearBossWallRamps45` | `RearBossShoulderTransitions` | 40,961.3590 | 534 | `regenerate_rear_boss_wall_ramps.py` |

The two boss-to-wall load-path inputs are generic stored `PartDesign::Feature` objects with one cached solid each, but no `RegenerationScript` or `RegenerationMethod` property. The existing scripts rebuild downstream high-to-low transitions and rear wall ramps; they do **not** regenerate either boss-to-wall load-path input. Running those downstream scripts alone would therefore not test whether a hanger-profile change reaches the shell Tips.

The audit found legacy screw-support transition profiles and the active paired hanger profiles. Their existence is not enough to identify the exact clipping recipe for the stored load-path shapes. The old additive-loft chain remains rejected as a regeneration source because its right-side loft recomputed invalid in the previous disposable test.

## Result and next action

This closes the metadata-identification step but changes no geometry and establishes no load capacity. The next viable experiment must reconstruct the source geometry and clipping inputs for one boss-to-wall feature in a disposable candidate, or isolate a smaller load-path feature that is demonstrably connected to the closed hanger opening. Before that, trace the actual material added by the feature against the hanger region and its screw/magnet keep-outs. Do not reuse the downstream transition scripts as a substitute, and do not promote the candidate unless both shell Tips recompute and the closed opening remains aligned through both Bodies.

The user requirement remains: the closed hanger opening must safely support the assembled pendant's full weight. The user has now specified PLA, shells printed flat on their broad faces, and a physical proof load of **5× assembled weight**. The exact mass (including electronics and fasteners) remains unknown. Geometry and feature-history recomputation are still prerequisites to a meaningful candidate test; physical proof testing is still required before claiming strength.
