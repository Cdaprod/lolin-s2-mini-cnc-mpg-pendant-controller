# Top hanger refinement: initial audit

Date: 2026-10-30
Branch: `hardware-integration`
Scope: read-only source audit plus disposable sketch/section checks. No production CAD geometry was changed.

## Baseline feature structure

The monolithic `pendant.FCStd` contains shared `HangerParameters` and two native, fully constrained obround profile sketches:

| Shell | Profile | Current cut feature | Cut length | Sketch placement |
|---|---|---|---:|---|
| Front | `SmallHangerProfileBody` | `SmallHangerPocketBody` (“Hanger — Small Rear-to-Front Slot”) | 37 mm | `(0, 81, 1)` |
| Rear | `SmallHangerProfileBody002` | `SmallHangerPocketBody002` (“Hanger — Small Rear-to-Front Slot001”) | 22 mm | `(0, 81, -18)` |

The profiles are driven by `HangerParameters`: `SlotCenterY=81 mm`, `SlotLength=35.6 mm`, and `SlotWidth=3.0 mm`. They have coincident global XY extents, X `[-17.8,17.8]` mm and Y `[80.5,83.5]` mm, and R1.5 mm ends. Both shell Bodies are one valid saved solid. The front Tip is `RestoreUpperFaceplateHoles` (volume 37,683.5175 mm³); the rear Tip is `RearBossWallRamps45` (volume 40,961.3590 mm³). These saved Tip measurements are baseline descriptors, not evidence that a full-document recompute is clean.

## Material and nearby screw checks

Ray samples through the pre-hanger base shapes at the current upper slot edge found minimum remaining material of approximately 0.164 mm on the front shell (sample near X=12, Z=-14 mm) and 0.240 mm on the rear shell (near X=-12, Z=-24 mm). At nearby rear sections the shell already opens to the exterior. These sparse samples identify a thin-web concern; they are not a complete stress analysis or a global minimum-thickness proof.

The upper screw row is at X=±16.97 mm, Y=76.85 mm. The M2 head-seat radius is 2.05 mm, so its top reaches Y=78.90 mm. Current slot lower edge is Y=80.50 mm, a 1.60 mm vertical separation in the sketch plane. The passage radius is 1.15 mm. This is an important constraint on moving or reshaping the lower end of the hanger opening; true 3D separation still requires checking the shell solids and cut directions.

## Disposable candidate and disposition

On a disposable document, a sketch-only proposal changed width 3.0→3.5 mm, length remained 35.6 mm, and the shared center alias was shifted 81.0→80.25 mm. Both sketches remained fully constrained and aligned, with R1.75 mm ends and global XY bounds X `[-17.8,17.8]`, Y `[79.5,83.0]` mm. At sampled rear sections this candidate left only about 0.25 mm of material at one transition, although it improved the sampled front web. It also reduced the lower-edge gap to the upper head-seat envelope from 1.60 mm to 0.60 mm.

**Disposition: rejected.** The candidate was never saved to or promoted into production CAD. A second larger downward shift was not pursued because the lower opening edge would approach/intersect the screw-seat envelope. A global obround enlargement therefore does not satisfy both the upper material and lower screw-clearance constraints.

## Closed, load-bearing hanger requirement and follow-up candidate

The user confirmed that this is a **closed hole intended to carry the pendant's weight** and that it passes through both shell Bodies. This is a functional and structural requirement, not just a visual preference. A closed silhouette alone does not establish adequate load strength.

A second disposable candidate changed `SlotWidth` from 3.0 to 3.1 mm and `SlotCenterY` from 81.0 to 81.05 mm, preserving the lower edge at Y=80.5 mm and raising the upper edge from Y=83.5 to Y=83.6 mm. Both active sketches remained fully constrained, and both `SmallHangerPocketBody` features recomputed to different shapes. However, the final Body Tips did not change: front volume stayed `37,683.517480502655 mm³`, rear stayed `40,961.35900828918 mm³`, and sampled final-Tip intervals matched the source. Their downstream generic `PartDesign::Feature` load-path outputs retained the same volumes despite changed upstream pocket/receiver shapes. Some shell branches also contain `Touched` intermediates in the source. Thus the candidate did **not** demonstrate propagation into the manufactured shells; Tip validity and an `Up-to-date` state were insufficient evidence. The candidate was saved in `/tmp/pendant-hanger-closed-hole-candidate.FCStd` but was not reopened or promoted. It also reports an invalid `PartChamferTrial` object outside the hanger chain.

The candidate trace localizes the first non-propagating outputs:

| Feature | Source volume (mm³) | Candidate volume (mm³) | Result |
|---|---:|---:|---|
| `SmallHangerPocketBody` | 40,859.1678 | 40,840.1329 | Updated |
| `RearFullWidthReceiver` | 38,556.8470 | 38,540.3195 | Updated |
| `FrontFullWidthReceiver` | 37,466.5924 | 37,450.0649 | Updated |
| `FrontBossToWallLoadPaths` | 37,548.7539 | 37,548.7539 | Stored `PartDesign::Feature` output unchanged |
| `FrontHighToLowTransitions` / front Tip | 37,690.1198 / 37,683.5175 | same / same | No profile change reached front Tip |
| `SmallHangerPocketBody002` | 38,207.2519 | 38,187.7641 | Updated |
| `Body002FullWidthSeat` | 40,485.6574 | 40,463.6153 | Updated |
| `RearBossToWallLoadPaths` | 40,869.3910 | 40,869.3910 | Stored `PartDesign::Feature` output unchanged |
| `RearBossShoulderTransitions` / rear Tip | 40,854.4296 / 40,961.3590 | same / same | No profile change reached rear Tip |

The candidate-side receiver/seat objects reported `Up-to-date`, but the generic shape features retained their previous stored output. This identifies the immediate repair target for a valid hanger experiment: regenerate those two load-path shape features from their updated inputs, then validate every downstream feature and final Tip. It does not establish that the original source document can be fully recomputed safely.

A disposable attempt to rebase the five stored `PartDesign::Feature` outputs by transferring their source base-to-output shape deltas ran to its 170-second process limit before producing a validation record. The experiment’s copy remained byte-identical to the input candidate (`SHA256 ab43282cebb687c862e98ebe84d829dac3e2148b79406ed3e1a9a59499091690`); neither it nor the authoritative monolith was saved by the attempt. This route is therefore unvalidated and should not be repeated unchanged. A more local regeneration method or simpler isolated feature test is needed.

A read-only metadata check found that `FrontBossToWallLoadPaths` and `RearBossToWallLoadPaths` are generic `PartDesign::Feature` objects with no Python proxy or regeneration-script property. Their design notes describe lofts clipped to shell envelopes and screw/magnet clearances, but do not preserve the construction recipe. `RearBossShoulderTransitions` is also stored as a generic shape feature and records source edges `Edge1373, Edge339`; native Chamfer recompute previously failed. By comparison, `FrontHighToLowTransitions` and `RearBossWallRamps45` each identify a regeneration script. The next focused task is to recover the missing loft/chamfer construction inputs from the existing sketches and clearance features, then build a small disposable regeneration test. The 170-second Boolean-delta replay is not the preferred route.

The read-only 1 mm X/Z line-section grid compared proposed upper-edge heights against saved pre-hanger intermediate shell shapes; it did not validate the final candidate Tips. At Y=83.6 mm, sampled minimum residuals were 0.0195 mm front and 0.00885 mm rear; at rear X=12 mm, Z=−25 mm the local shell surface is near Y=83.251 mm, below the proposed edge. Baseline sections at Y=83.5 mm also showed very thin residuals and local edge-beyond-surface classifications. A separate line-section query of the saved final Tips found the same source and candidate intervals, including no rear upper interval at X=12 mm, Z=−25 mm and only about 0.164 mm of front material at X=12 mm, Z=−14 mm. This raises concern about the saved baseline, but the source has stale/touched intermediate features and the candidate did not propagate through the downstream shape features, so the result remains diagnostic rather than a fresh full-history proof. See `top-hanger-section-screening-2026-10-30.png`; its colors visualize sampled intermediate geometry, not the final Tip or a load test.

**Disposition: rejected as a geometry candidate and incomplete as a propagation test; disposable only.** Do not raise the opening edge or claim the current feature is load-safe. First restore a trustworthy downstream regeneration path from the active hanger pocket to both final Tips, including the generic stored-shape load-path features. Then investigate a local parametric hanger bridge/boss integrated with both shells, preserving the closed aperture, an uninterrupted load path, screw-seat clearance, and shell mating. Establish a measurable load case and inspect the full contour before making a design change. Structural capacity cannot be certified from these geometric section probes alone.

## Recompute limits and baseline protection

The shared sketch-only recompute succeeded. A full disposable monolith recompute encountered pre-existing out-of-scope cross-Body links and the historical `Pad021.?Face97` / suppressed `Pad022` failure, then exceeded the bounded run time. No candidate shell recompute or final assembly-fit claim is made. The authoritative monolith was not saved or modified; its SHA-256 before the experiment was `dc2aeddf7be327c73022a1dc053bf8a27d5cf476e9cd68468a4ee73ab8264881`.

## Follow-up: dormant hanger sketch and direct sections

A read-only property audit found `Sketch015` (“Hanger Pocket Sketch001”) and `Body_HangerCutTool/HangerFacetedSlotAndLipRelief` in the source. `Sketch015` has no downstream consumer, is not fully constrained, and spans only about 33.58 mm in X (versus 35.6 mm for the active opening); its upper edge is at Y≈84.128 mm while the lower edge remains near Y=80.548 mm. `HangerFacetedSlotAndLipRelief` is a standalone `PartDesign::Feature` shape in an unused helper Body, not a native editable pocket profile and not linked into either shell's active cut. These dormant objects do not establish an approved hanger design.

To verify the thin-web observations efficiently, direct BREP line-section intersections were taken through the pre-hanger shell features in the Y direction. They reproduced the current-edge samples: front shell at X=±12,Z=-14 has about 0.164 mm; rear shell at X=±12,Z=-24 has about 0.240 mm. At the dormant sketch's upper edge Y≈84.128 mm, front shell samples at X=±12,Z=-15 leave only about 0.010 mm; rear shell samples at X=±12,Z=-24 are already outside the shell interval (the shell section ends around Y=83.740 mm). Thus that profile would leave near-zero front material and open the rear slot through the exterior at those sections. It is also narrower horizontally, so it does not simply enlarge the existing hanger opening. The line-section probe completed in a bounded FreeCADCmd run without recomputing or saving the source.

**Disposition: dormant sketch rejected as a candidate source.** Do not use it to enlarge the opening. The confirmed requirement is a closed load-bearing hole through both Bodies.

The read-only measurement is now reproducible with `scripts/audit_top_hanger_sections.py`. It accepts one or more proposed global-Y cut-edge positions, records the source checksum and FreeCAD version, samples both shell base shapes, and does not recompute or save the CAD file. A fresh run reproduced the measurements and source checksum in this report.

## Recommended next investigation

For the confirmed closed, load-bearing hole, do not move the whole obround upward or reuse `Sketch015`. Investigate a local reinforced bridge/boss or another native parametric shape that thickens the load path through both shells without opening the hole or intersecting screw seats. Establish the design load case, inspect the full opening contour and shell overlap, measure 3D clearance to screw-seat solids, and recompute the complete affected feature chains in a disposable copy. If the existing cross-Body history prevents trustworthy end-to-end validation, retain any proposal as unpromoted and document the exact blocker.

The 0.9 mm “two 0.45 mm lines” idea is only a provisional common 0.4 mm-nozzle print heuristic, not a validated requirement for this pendant or the user's printer. No minimum wall target has been adopted.
