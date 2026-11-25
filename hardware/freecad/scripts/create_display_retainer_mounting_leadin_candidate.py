"""Add small native lead-ins to the five display-retainer M2 passages.

This script writes only a new disposable candidate. Set PENDANT_REPO_ROOT and
optionally PENDANT_DISPLAY_RETAINER_OUTPUT. It never saves the source file.
Five dimensioned circles feed a shallow, tapered native Pocket, avoiding
fragile generated-edge selections.
"""
import json
import os

import FreeCAD as App
import MeshPart
import Part


root = os.environ.get("PENDANT_REPO_ROOT", "/private/tmp/pendant-hardware-integration")
source = os.path.join(root, "hardware/freecad/pendant-bodies/display-retainer.FCStd")
output = os.environ.get(
    "PENDANT_DISPLAY_RETAINER_OUTPUT",
    os.path.join(root, "hardware/freecad/pendant-bodies/display-retainer-mounting-leadin-candidate.FCStd"),
)
report = os.path.join(root, "hardware/freecad/reports/display-retainer-mounting-leadin-validation.json")
mesh_before_path = "/private/tmp/display-retainer-leadin-before.stl"
mesh_after_path = "/private/tmp/display-retainer-leadin-after.stl"
if os.path.realpath(source) == os.path.realpath(output):
    raise RuntimeError("Refusing to overwrite the source component")
if not os.path.isfile(source):
    raise RuntimeError("Display-retainer source is missing: " + source)
if os.path.exists(output):
    raise RuntimeError("Candidate already exists; choose another disposable output: " + output)

LEAD_IN_MM = 0.15
BODY_NAME = "Body_DisplayRetainer_EditableV2"
TIP_NAME = "RetainerShellClearancePocketV3"
HOLES = {
    (-25.8, -10.5): 1.15,
    (25.8, -10.5): 1.15,
    (-11.811, -12.605): 1.10,
    (11.811, -12.605): 1.10,
    (0.0, 22.449): 1.10,
}


def bounds(shape):
    bb = shape.BoundBox
    return [bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax]


def valid_one_solid(shape):
    return bool(not shape.isNull() and shape.isValid() and len(shape.Solids) == 1)


def mesh(shape, path):
    m = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.08,
                               AngularDeflection=0.18, Relative=False)
    if not m.isSolid():
        raise RuntimeError("Tessellated component mesh is not closed: " + path)
    m.write(path)
    return m.CountFacets


doc = App.openDocument(source)
try:
    body = doc.getObject(BODY_NAME)
    old_tip = doc.getObject(TIP_NAME)
    if body is None or body.Tip != old_tip:
        raise RuntimeError("Expected editable display-retainer Body/Tip was not found")
    doc.recompute([old_tip])
    before = old_tip.Shape.copy()
    if not valid_one_solid(before):
        raise RuntimeError("Source display-retainer Tip is not one valid solid")
    top_z = before.BoundBox.ZMax

    # Confirm all five nominal through-clearances are already open. The lead-in
    # changes only the mouth; the cylindrical passage remains nominally sized.
    passage_checks = []
    for (x, y), radius in HOLES.items():
        tool = Part.makeCylinder(radius, 20.0, App.Vector(x, y, before.BoundBox.ZMin - 2.0), App.Vector(0, 0, 1))
        interference = before.common(tool).Volume
        passage_checks.append({"center_mm": [x, y], "nominal_radius_mm": radius,
                               "source_interference_mm3": interference})
        if interference > 1e-5:
            raise RuntimeError("Nominal through-passage is obstructed before lead-in at %r" % ((x, y),))

    profile = body.newObject("Sketcher::SketchObject", "DisplayRetainerMountingLeadInProfile")
    profile.Label = "M2 passage lead-in profiles — 0.15 mm radial"
    profile.Placement = App.Placement(App.Vector(0, 0, top_z), App.Rotation())
    for (x, y), radius in HOLES.items():
        idx = profile.addGeometry(
            Part.Circle(App.Vector(x, y, 0), App.Vector(0, 0, 1), radius + LEAD_IN_MM), False)
        profile.addConstraint(Sketcher.Constraint("DistanceX", idx, 3, x))
        profile.addConstraint(Sketcher.Constraint("DistanceY", idx, 3, y))
        profile.addConstraint(Sketcher.Constraint("Radius", idx, radius + LEAD_IN_MM))
    pocket = body.newObject("PartDesign::Pocket", "DisplayRetainerMountingLeadIns")
    pocket.Label = "Display retainer M2 tapered lead-ins — 0.15 mm"
    pocket.Profile = profile
    pocket.Length = LEAD_IN_MM
    pocket.TaperAngle = -45.0
    pocket.Refine = True
    body.Tip = pocket
    doc.recompute([pocket])
    after = pocket.Shape.copy()
    if not profile.FullyConstrained:
        raise RuntimeError("Lead-in profile sketch is not fully constrained")
    if not valid_one_solid(after):
        raise RuntimeError("Native tapered lead-in Pocket did not produce one valid solid")

    removed = before.cut(after)
    added = after.cut(before)
    if removed.isNull() or not removed.isValid() or removed.Volume <= 0:
        raise RuntimeError("Lead-in Pocket did not remove the expected localized mouth material")
    if not added.isNull() and added.Volume > 1e-5:
        raise RuntimeError("Lead-in Pocket unexpectedly added material")
    if max(abs(a-b) for a, b in zip(bounds(before), bounds(after))) > 1e-6:
        raise RuntimeError("Mating envelope bounds changed")

    after_passages = []
    for (x, y), radius in HOLES.items():
        tool = Part.makeCylinder(radius, 20.0, App.Vector(x, y, before.BoundBox.ZMin - 2.0), App.Vector(0, 0, 1))
        interference = after.common(tool).Volume
        after_passages.append({"center_mm": [x, y], "nominal_radius_mm": radius,
                               "candidate_interference_mm3": interference})
        if interference > 1e-5:
            raise RuntimeError("Lead-in Pocket obstructed a nominal mounting passage at %r" % ((x, y),))

    facets_before = mesh(before, mesh_before_path)
    facets_after = mesh(after, mesh_after_path)
    profile.Visibility = False
    doc.saveAs(output)
    doc.save()
finally:
    App.closeDocument(doc.Name)

# Verify the native feature after closing and reopening the saved candidate.
check = App.openDocument(output)
try:
    check.recompute()
    body = check.getObject(BODY_NAME)
    pocket = check.getObject("DisplayRetainerMountingLeadIns")
    profile_check = check.getObject("DisplayRetainerMountingLeadInProfile")
    if (body is None or body.Tip != pocket or not valid_one_solid(pocket.Shape)
            or not profile_check.FullyConstrained):
        raise RuntimeError("Cold-reopen/recompute failed for display-retainer candidate")
    check_mesh = MeshPart.meshFromShape(Shape=pocket.Shape, LinearDeflection=0.08,
                                        AngularDeflection=0.18, Relative=False)
    if not check_mesh.isSolid():
        raise RuntimeError("Cold-reopened display-retainer mesh is not closed")
    result = {
        "source": source,
        "candidate": output,
        "native_feature": pocket.TypeId,
        "feature_name": pocket.Name,
        "base_feature": TIP_NAME,
        "profile_sketch": "DisplayRetainerMountingLeadInProfile",
        "profile_fully_constrained": profile_check.FullyConstrained,
        "mounting_centers_and_nominal_radii_mm": [
            {"center": list(center), "radius": radius} for center, radius in HOLES.items()
        ],
        "radial_lead_in_mm": LEAD_IN_MM,
        "taper_angle_deg": -45.0,
        "entry_plane_z_mm": top_z,
        "before": {"valid": before.isValid(), "solids": len(before.Solids), "volume_mm3": before.Volume, "bounds_mm": bounds(before)},
        "after": {"valid": pocket.Shape.isValid(), "solids": len(pocket.Shape.Solids), "volume_mm3": pocket.Shape.Volume, "bounds_mm": bounds(pocket.Shape)},
        "removed_volume_mm3": removed.Volume,
        "added_volume_mm3": 0.0 if added.isNull() else added.Volume,
        "through_clearance_checks_before": passage_checks,
        "through_clearance_checks_after": after_passages,
        "mesh_facets_before": facets_before,
        "mesh_facets_after": facets_after,
        "cold_reopen_mesh_facets": check_mesh.CountFacets,
        "cold_reopen_mesh_closed": check_mesh.isSolid(),
        "save_reopen_recompute": "passed",
        "source_component_modified": False,
    }
    os.makedirs(os.path.dirname(report), exist_ok=True)
    with open(report, "w") as f:
        json.dump(result, f, indent=2, sort_keys=True)
        f.write("\n")
    print("DISPLAY_RETAINER_MOUNTING_LEADIN=" + json.dumps(result, sort_keys=True))
finally:
    App.closeDocument(check.Name)
