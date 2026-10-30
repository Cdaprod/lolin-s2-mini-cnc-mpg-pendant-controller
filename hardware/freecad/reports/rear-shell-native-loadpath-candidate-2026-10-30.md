# Rear-shell native load-path candidate

Date: 2026-10-30 · Branch: `hardware-integration`

## Result

A disposable hybrid component now replaces the rear-shell static interim shape
in `pendant-modular-repair-candidate.FCStd`. The source file is
`pendant-bodies/rear-shell-loadpath-repair-candidate.FCStd`. The component has
a native PartDesign Body and Tip, four native support Pads, and a native Pocket
that restores the six M2 passages. A 0.2 mm change to `UpperLeftSupportPad`
changed the recomputed Tip volume by 0.180262 mm³; restoring the Pad length
returned the volume within 0.00000013 mm³ of its baseline. Both changed and
restored Tip meshes were closed.

The shell's base is still a static imported BREP from the original
`Body002FullWidthSeat` shape. This is a hybrid, editable load-path candidate,
not a fully native or independently regenerated rear shell. Its four profile
sketches are blocked at their current geometry; the Pad lengths and feature
histories are editable. This result does not validate a hanger load rating or
authorize replacement of the production shell.

## CAD and assembly validation

The saved component was closed, reopened, and recomputed. Its final Tip is
`RearM2PassageClearance`; the Body and Tip are valid one-solid shapes with a
closed FreeCAD mesh. The Tip volume is 40,609.693012 mm³. The six screw-passage
clearances match the imported base exactly, and the measured magnet-clearance
difference is 5.1e-13 mm³.

The disposable assembly now uses a live `App::Link` to this candidate at the
rear shell's prior placement. After save and reopen, all six live links
resolved; the rear shape remained a valid single solid with a closed mesh, and
its measured intersection with the front shell was 0 mm³. The complete
eight-part mesh export completed without exporter errors.

The script `scripts/regenerate_rear_shell_native_loadpath_candidate.FCMacro`
rebuilds this hybrid candidate from the protected monolith into a caller-chosen
output path. Its run reproduced the saved candidate volume within 3e-11 mm³,
preserved the screw and magnet clearances, and yielded a valid one-solid closed
mesh. It emitted two OpenCascade `TopoShapeExpansion` hasher-mismatch warnings
while loading the legacy source; they did not prevent recomputation or saving.

The component-to-assembly refresh workflow also passed in a relocated,
disposable copy containing the master and all component files. Editing
`UpperLeftSupportPad.Length` from 13.0 to 13.2 mm, saving the component, and
reopening the assembly changed the linked assembly volume from 40,609.693012
to 40,609.873274 mm³. Restoring 13.0 mm and reopening returned the original
assembly volume. All six assembly links resolved during this test. The
reusable `scripts/validate_rear_shell_link_refresh.FCMacro` performs this
check on explicitly supplied disposable paths.

## Mesh defect check

`scripts/audit_stl_edge_incidence.py` checks welded triangle-edge incidence in
binary STL exports. At 0.00001 mm weld tolerance, all eight meshes in the
disposable assembly had zero boundary edges, zero edges incident to more than
two facets, and zero degenerate triangles. The rear shell had 19,126 facets
and 28,689 welded edges, each incident to exactly two facets. The candidate
rear shell therefore exports as a closed two-manifold mesh; the repair exists
in the FreeCAD component/assembly candidate and does not depend on OrcaSlicer's
mesh-repair function.

The result is recorded in
`rear-shell-native-loadpath-candidate-mesh-audit-2026-10-30.json`.

## Remaining limits

The original monolith, production master, production assembly, production
rear-shell STL, and user-owned OrcaSlicer 3MF remain untouched. The candidate
has not been substituted into those production files. The imported base still
prevents full rear-shell parametric independence; the support-profile geometry
also needs mechanical review before any production promotion. A closed mesh
and CAD-valid solid establish topology only, not structural strength or
equivalence to the original failed mesh.

To regenerate the candidate and export its assembly meshes, use the documented
macro with `PENDANT_REPO_ROOT` and `PENDANT_CANDIDATE_OUTPUT` set to disposable
paths, then run `hardware/printing/pendant/build_meshes.py --assembly
hardware/freecad/pendant-modular-repair-candidate.FCStd --output-dir
/tmp/pendant-repair-mesh-review` and audit the resulting STL files with the
incidence checker.
