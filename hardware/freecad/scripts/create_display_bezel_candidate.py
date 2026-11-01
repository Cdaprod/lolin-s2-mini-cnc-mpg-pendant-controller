"""Create a disposable native-filleted upper-faceplate candidate.

Run with FreeCAD's Python runtime (freecadcmd) and set:
  PENDANT_MONOLITH=/path/to/pendant.FCStd
  PENDANT_BEZEL_CANDIDATE=/path/to/disposable-candidate.FCStd

The protected monolith is opened read-only in spirit and never saved in place.
The script copies it with saveAs, locates the two circular top-rim edges by
geometry, appends a native PartDesign Fillet, then cold-reopens and validates.
"""
import json
import math
import os

import FreeCAD as App
import MeshPart

source = os.environ.get("PENDANT_MONOLITH")
output = os.environ.get("PENDANT_BEZEL_CANDIDATE")
if not source or not output:
    raise RuntimeError("Set PENDANT_MONOLITH and PENDANT_BEZEL_CANDIDATE")
source = os.path.realpath(source)
output = os.path.realpath(output)
if source == output:
    raise RuntimeError("Refusing to overwrite the protected monolith")
if not os.path.isfile(source):
    raise RuntimeError("Source monolith not found: " + source)

RADIUS_MM = 0.3
CENTER_X, CENTER_Y, TOP_Z = 0.0, 2.99855, 4.0
TARGET_RADII = (20.0, 22.5)


def find_rim_edges(body_tip):
    found = {}
    for index, edge in enumerate(body_tip.Shape.Edges, 1):
        curve = getattr(edge, "Curve", None)
        if curve is None or curve.__class__.__name__ != "Circle":
            continue
        center = curve.Center
        if (abs(center.x - CENTER_X) > 1e-4 or
                abs(center.y - CENTER_Y) > 1e-3 or
                abs(center.z - TOP_Z) > 1e-4 or
                abs(edge.BoundBox.ZMin - TOP_Z) > 1e-4 or
                abs(edge.BoundBox.ZMax - TOP_Z) > 1e-4):
            continue
        for radius in TARGET_RADII:
            if abs(curve.Radius - radius) < 1e-4:
                found[radius] = "Edge%d" % index
    if set(found) != set(TARGET_RADII):
        raise RuntimeError("Could not uniquely find top rim circles: %r" % found)
    return [found[r] for r in TARGET_RADII]


def shape_summary(shape):
    bb = shape.BoundBox
    return {
        "valid": bool(shape.isValid()),
        "solids": len(shape.Solids),
        "volume_mm3": shape.Volume,
        "faces": len(shape.Faces),
        "bounds_mm": [bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax],
    }


doc = App.openDocument(source)
try:
    body = doc.getObject("Body003")
    if body is None or body.Tip is None:
        raise RuntimeError("Body003 or its active Tip is missing")
    base = body.Tip
    doc.recompute([base])
    before = base.Shape.copy()
    if not before.isValid() or len(before.Solids) != 1:
        raise RuntimeError("Source upper-faceplate Tip is not one valid solid")
    edges = find_rim_edges(base)
    doc.saveAs(output)
    fillet = body.newObject("PartDesign::Fillet", "DisplayBezelSoftEdge")
    fillet.Label = "Display bezel soft edge — R0.3 mm"
    fillet.Base = (base, edges)
    fillet.Radius = RADIUS_MM
    body.Tip = fillet
    doc.recompute([fillet])
    after = fillet.Shape.copy()
    if not after.isValid() or len(after.Solids) != 1:
        raise RuntimeError("Native display-bezel fillet did not produce one valid solid")
    removed = before.cut(after)
    added = after.cut(before)
    doc.save()
finally:
    App.closeDocument(doc.Name)

# Cold-reopen the candidate and verify the saved native feature again.
check = App.openDocument(output)
try:
    check.recompute()
    body = check.getObject("Body003")
    fillet = check.getObject("DisplayBezelSoftEdge")
    if body.Tip != fillet or not fillet.Shape.isValid() or len(fillet.Shape.Solids) != 1:
        raise RuntimeError("Cold-reopened candidate failed feature/solid validation")
    mesh = MeshPart.meshFromShape(Shape=fillet.Shape, LinearDeflection=0.15,
                                  AngularDeflection=0.25, Relative=False)
    if not mesh.isSolid():
        raise RuntimeError("Cold-reopened faceplate mesh is not closed")
    result = {
        "source": source,
        "candidate": output,
        "native_feature": "PartDesign::Fillet",
        "feature_name": fillet.Name,
        "selected_edges": edges,
        "radius_mm": RADIUS_MM,
        "before": shape_summary(before),
        "after": shape_summary(fillet.Shape),
        "removed_volume_mm3": removed.Volume,
        "added_volume_mm3": added.Volume,
        "mesh_facets": mesh.CountFacets,
        "mesh_closed": mesh.isSolid(),
        "cold_reopen_recompute": "passed",
        "production_monolith_modified": False,
    }
    print("DISPLAY_BEZEL_CANDIDATE=" + json.dumps(result, sort_keys=True))
finally:
    App.closeDocument(check.Name)