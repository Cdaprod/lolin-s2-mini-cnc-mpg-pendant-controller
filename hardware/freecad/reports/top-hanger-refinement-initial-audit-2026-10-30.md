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

## Recompute limits and baseline protection

The shared sketch-only recompute succeeded. A full disposable monolith recompute encountered pre-existing out-of-scope cross-Body links and the historical `Pad021.?Face97` / suppressed `Pad022` failure, then exceeded the bounded run time. No candidate shell recompute or final assembly-fit claim is made. The authoritative monolith was not saved or modified; its SHA-256 before the experiment was `dc2aeddf7be327c73022a1dc053bf8a27d5cf476e9cd68468a4ee73ab8264881`.

## Recommended next investigation

Do not move the whole obround profile down. Instead, investigate a locally reshaped upper cap/transition in both shared sketches while preserving the lower boundary and upper screw clearance. First establish shell-material sections along the full upper perimeter and the 3D distance from the actual screw-seat solids. Then test a controlled, symmetric sketch-level transition in a disposable copy and recompute the complete affected feature chains. If the existing cross-Body history prevents a trustworthy end-to-end validation, retain the proposal as unpromoted and document the exact blocker.

The 0.9 mm “two 0.45 mm lines” idea is only a provisional common 0.4 mm-nozzle print heuristic, not a validated requirement for this pendant or the user's printer. No minimum wall target has been adopted.
