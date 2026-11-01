"""Build and validate small screw-entry lead-ins on both locator bodies.

Creates a disposable .FCStd beside the source component. The original source
file is never overwritten. FreeCAD 1.1.1, run with freecadcmd.
"""
import FreeCAD as App
import Part
import Sketcher
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, "pendant-bodies", "faceplate-locators.FCStd")
OUTPUT = os.path.join(ROOT, "pendant-bodies", "faceplate-locators-leadin-candidate.FCStd")
REPORT = os.path.join(ROOT, "reports", "faceplate-locators-leadin-validation.json")
BEFORE_STL = "/tmp/faceplate-locators-leadin-before.stl"
AFTER_STL = "/tmp/faceplate-locators-leadin-after.stl"
RADIUS = 1.15
LEAD = 0.15
DEPTH = 0.15
# The existing hole sketches start at local z=1.0, but the locator's top solid
# face is z=0.7. Start the entry cut on that material face so a short pocket
# cannot terminate in the pre-existing through-hole void.
PLANE_Z = 0.7

if os.path.exists(OUTPUT):
    raise RuntimeError("Refusing to overwrite existing candidate: " + OUTPUT)

def mesh_closed(shape):
    m = shape.copy().tessellate(0.08)
    counts = {}
    for tri in m[1]:
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            k = tuple(sorted((a, b)))
            counts[k] = counts.get(k, 0) + 1
    return all(n == 2 for n in counts.values()), len(m[1]), sum(n == 1 for n in counts.values()), sum(n > 2 for n in counts.values())

def metrics(shape):
    bb = shape.BoundBox
    return {"volume_mm3": shape.Volume, "area_mm2": shape.Area,
            "faces": len(shape.Faces), "edges": len(shape.Edges),
            "solids": len(shape.Solids), "valid": shape.isValid(),
            "bounds_mm": [bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax]}

doc = App.openDocument(SOURCE)
doc.recompute()
bodies = [(doc.getObject("Body_FaceplateLocator_A"), "0"),
          (doc.getObject("Body_FaceplateLocator_B"), "1")]
if any(b is None or b.Tip is None or not b.Shape.isValid() or len(b.Shape.Solids) != 1 for b, _ in bodies):
    raise RuntimeError("Source locator bodies are not valid single solids")
baseline = {b.Name: b.Shape.copy() for b, _ in bodies}
for b, suffix in bodies:
    sketch = doc.addObject("Sketcher::SketchObject", "LocatorScrewLeadInProfile_" + suffix)
    b.addObject(sketch)
    sketch.Label = "Locator screw entry lead-in — " + b.Name[-1]
    sketch.Placement = App.Placement(App.Vector(0, 0, PLANE_Z), App.Rotation())
    # Centers are taken from the existing constrained screw passage sketches.
    source_sketch = doc.getObject("LocatorPassageProfile" + suffix)
    circle = next(g for g in source_sketch.Geometry if hasattr(g, "Radius") and abs(g.Radius - RADIUS) < 1e-7)
    center = circle.Center
    idx = sketch.addGeometry(Part.Circle(App.Vector(center.x, center.y, 0), App.Vector(0, 0, 1), RADIUS + LEAD), False)
    sketch.addConstraint(Sketcher.Constraint("Radius", idx, RADIUS + LEAD))
    # Lock center to exact source dimensions, preserving the native feature inputs.
    sketch.addConstraint(Sketcher.Constraint("DistanceX", idx, 3, center.x))
    sketch.addConstraint(Sketcher.Constraint("DistanceY", idx, 3, center.y))
    pocket = b.newObject("PartDesign::Pocket", "LocatorScrewLeadIn_" + suffix)
    pocket.Label = "Locator screw entry lead-in — " + b.Name[-1]
    pocket.Profile = sketch
    pocket.Length = DEPTH
    pocket.TaperAngle = -45.0
    pocket.Refine = True
    doc.recompute()
    if not sketch.FullyConstrained:
        raise RuntimeError(sketch.Name + " is not fully constrained")
    if pocket.Shape.isNull() or not pocket.Shape.isValid() or len(pocket.Shape.Solids) != 1:
        raise RuntimeError(pocket.Name + " failed to produce a valid single solid: " + str(pocket.getStatusString()))
    b.Tip = pocket

doc.recompute()
for b, _ in bodies:
    if not b.Shape.isValid() or len(b.Shape.Solids) != 1:
        raise RuntimeError(b.Name + " invalid after full recompute")
Part.export([doc.getObject("LocatorScrewPassage0"), doc.getObject("LocatorScrewPassage1")], BEFORE_STL)
Part.export([b for b, _ in bodies], AFTER_STL)
doc.saveAs(OUTPUT)
doc_name = doc.Name
App.closeDocument(doc_name)

# Cold-open and recompute from saved feature histories.
doc = App.openDocument(OUTPUT)
doc.recompute()
result = {"source": SOURCE, "candidate": OUTPUT, "lead_radial_expansion_mm": LEAD,
          "lead_depth_mm": DEPTH, "taper_angle_deg": -45.0, "bodies": {}}
for name, suffix in (("Body_FaceplateLocator_A", "0"), ("Body_FaceplateLocator_B", "1")):
    b = doc.getObject(name)
    base = baseline[name]
    changed = b.Shape
    closed, facets, boundary, over = mesh_closed(changed)
    unchanged = metrics(base)
    altered = metrics(changed)
    if not changed.isValid() or len(changed.Solids) != 1 or not closed or boundary or over:
        raise RuntimeError(name + " failed cold-open mesh validation")
    if any(abs(a-c) > 1e-7 for a,c in zip(unchanged["bounds_mm"], altered["bounds_mm"])):
        raise RuntimeError(name + " outside bounds changed")
    # A cylindrical through-clearance gauge at nominal radius must remain wholly in void.
    src = doc.getObject("LocatorPassageProfile" + suffix)
    cir = next(g for g in src.Geometry if hasattr(g, "Radius") and abs(g.Radius-RADIUS)<1e-7)
    center = cir.Center
    gauge = Part.makeCylinder(RADIUS, 3.0, App.Vector(center.x, center.y, -2.0), App.Vector(0,0,1))
    interference = changed.common(gauge).Volume
    if interference > 1e-7:
        raise RuntimeError(name + " nominal screw clearance reduced: " + str(interference))
    result["bodies"][name] = {"before": unchanged, "after": altered,
                              "removed_mm3": unchanged["volume_mm3"]-altered["volume_mm3"],
                              "added_mm3": max(0.0, altered["volume_mm3"]-unchanged["volume_mm3"]),
                              "nominal_bore_gauge_interference_mm3": interference,
                              "fully_constrained_profile": doc.getObject("LocatorScrewLeadInProfile_"+suffix).FullyConstrained,
                              "mesh_closed": closed, "facets": facets,
                              "boundary_edges": boundary, "over_incident_edges": over,
                              "placement": str(b.Placement)}
doc.recompute()
doc.save()
with open(REPORT, "w") as f:
    json.dump(result, f, indent=2)
    f.write("\n")
App.closeDocument(doc.Name)
print(json.dumps(result, indent=2))
