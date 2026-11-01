# Rear full-land transfer interface investigation

Date: 2026-10-29
Branch: `hardware-integration`
Starting commit: `6eea7f2`
Scope: read-only geometry/dependency investigation in a disposable copy of the cleaned bypass candidate. No production FreeCAD document was changed.

## Result

The active rear-to-front boundary remains the `Part::Common` input
`RearFullLandTransfer.Base → SmallHangerPocketBody`. The Base is a whole
feature shape link; it does not select a stable face, edge, or subelement.
`RearFullLandTransfer.Tool` is the rear-owned `RearFullLandCutter` Body, whose
Tip is `RearFullWidthSeatLoft`.

The Common result is not a small planar land. In the saved/recomputed
`rear-reference-cleanup.FCStd` candidate it is a valid single solid with
2,302.413614 mm³ volume, 230 faces, and 771 edges. Its front input is a
339-face, 1,033-edge solid. A surface-overlap probe found 110 front-input
faces with positive-area overlap against the transfer result: 71 B-spline,
24 cylindrical, 13 planar, and 2 conical faces. This is a broad, trimmed
interface region, not evidence for a replacement based on one existing
profile or datum.

The rear cutter comes from two rear-owned section binders. `RearFullLandProfile0`
is located at Z = −19 mm; `RearFullLandProfile1` is at Z = −13.641016151 mm.
Their loft is a valid single solid with 34,961.321756 mm³ volume, 90 faces,
and 264 edges. These existing rear profiles and their width-control links can
remain rear-owned; they do not remove the need to reconstruct the front-side
solid clipped by the cutter.

## Active cross-shell paths

The corrected candidate manifest reports one direct active Body-boundary
property edge:

```text
Body002.Tip RearBossWallRamps45
  → Body002FullWidthSeat
  → Body002FullLandTransferTool.Tip
  → RearSeatScrewPassageRelief.BaseFeature
  → RearFullLandTransfer.Base
  → SmallHangerPocketBody (front Body)
```

This is the only direct active rear-to-front object/property crossing in the
manifest. It reaches a much longer front feature chain through
`SmallHangerPocketBody.BaseFeature → PreserveOriginalFrontExterior` and its
base/tool dependencies. The same chain contains the 19 active Sketcher
external-edge references in `Sketch019` and `Sketch020` (five references in
`Sketch019` drive nine constraints; the six `Sketch020` references are
unconstrained). Those references are additional dependencies *within the
front-side branch of this path*; they are not separate direct inputs from the
rear Body. The manifest still reports extraction `BLOCKED` at 161 expanded
dependencies.

The whole-shape Common property has no explicit `FaceN`/`EdgeN` mapping to
preserve. The 110 overlapping source faces were compared against face topology
in 80 upstream geometric objects reached through BaseFeature, Tool, Group,
Profile, and Support references. None returned an `isSame` topology match.
That does not prove the surfaces are unrelated; Boolean trimming and feature
reconstruction can change topological identity. It does mean there is no
reliable face-number mapping from this probe to use for a safe parametric
rebuild.

## Geometry checks and limitations

The disposable candidate recomputed with `RearFullLandTransfer` valid and
one-solid. A direct `SmallHangerPocketBody.Shape.common(RearFullLandCutter.Shape)`
also returned one valid solid with the same face and edge counts and a volume
of 2,302.413647 mm³ (difference from the saved feature: 0.000032 mm³). Boolean
subtraction checks reported no residual volume outside either operand. These
are useful consistency checks, but they do not establish exact BREP
equivalence.

The Common's reported `BoundBox` is unexpectedly broader than either operand:
it reports X = [−39.910, 39.879], Y = [−88.312, 86.688], Z = [−19, 0] mm,
while the cutter reports X = [−36.233, 36.233], Y = [−85.564, 86.688],
Z = [−19, −13.641] mm. The Common's 541 vertices instead range from
approximately [−35.977, −85.564, −19] to [35.977, 86.688, −14.588] mm.
Treat the raw Common bounding box as an overestimate and do not use it to
claim fit or clearance. The vertex range and successful Boolean checks do not
replace a robust whole-shape equivalence or mating-clearance test.

## Architectural decision

No independent master-owned geometric interface was created. The evidence
does not yet identify a sufficiently small set of stable profiles or datums
that reproduces the 110-face clipped front region. Moving the existing Common
shape into the master would only relocate a front-dependent result, and
freezing that result as a BREP would not meet the editable-source requirement.

The next safe investigation is face provenance by geometric surface/trim
comparison through the front-side feature history, followed by grouping the
actual contributing surfaces by the features that generate them. Only then
can we tell whether a compact native master interface can reproduce the
transfer. Until that provenance is known, keep the rear shell extraction
blocked and retain the validated static interim assembly representation.

## Files and validation

- Source candidate: `rear-reference-cleanup.FCStd`, SHA-256
  `25f1e36637947c6cf4228db84fd03218ce5338b852cb0449f5a0f138be8f0b8d`
- Disposable audit copy and probe outputs were kept under `/private/tmp` and
  are not repository deliverables.
- `pendant.FCStd`, `pendant-master.FCStd`, and
  `pendant-modular-assembly.FCStd` were not modified.
- Existing untracked recovery and candidate files were left untouched.
- No shell geometry, assembly link, or parameterization change is promoted by
  this investigation.
