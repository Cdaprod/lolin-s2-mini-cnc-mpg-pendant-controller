"""Locate curve-on-surface BOP faults by rear-shell feature stage.

Run with FreeCADCmd from the repository root. The script is read-only: it
opens a review FCStd, exports temporary BREP files under the system temp
directory for pythonocc's BOPAlgo_ArgumentAnalyzer, and closes the document
without saving it.
"""
import json
import os
import tempfile

import FreeCAD as App
import MeshPart
from OCC.Core.BOPAlgo import BOPAlgo_ArgumentAnalyzer
from OCC.Core.BRep import BRep_Builder
from OCC.Core.BRepBndLib import brepbndlib
from OCC.Core.BRepTools import breptools
from OCC.Core.Bnd import Bnd_Box
from OCC.Core.TopoDS import TopoDS_Shape


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_CANDIDATE = os.path.join(
    ROOT, "pendant-bodies",
    "rear-shell-native-loadpath-selective-refine-review-2026-11-01.FCStd",
)
STAGES = (
    "FreshFusedBase",
    "MiddleLeftNativeLoadPath",
    "MiddleRightNativeLoadPath",
    "LowerLeftNativeLoadPath",
    "LowerRightNativeLoadPath",
    "RearM2ClearancePocket",
    "StructuralBottomPerimeterFillet",
    "RearCrescentAntiSlipSeatPocket",
)


def bbox(shape):
    bounds = Bnd_Box()
    brepbndlib.Add(shape, bounds)
    return [round(float(value), 4) for value in bounds.Get()]


def analyze_curve_on_surface(shape):
    fd, brep_path = tempfile.mkstemp(prefix="rear-shell-bop-", suffix=".brep")
    os.close(fd)
    try:
        shape.exportBrep(brep_path)
        topo_shape = TopoDS_Shape()
        breptools.Read(topo_shape, brep_path, BRep_Builder())
        analyzer = BOPAlgo_ArgumentAnalyzer()
        analyzer.SetShape1(topo_shape)
        analyzer.SetCurveOnSurfaceMode(True)
        analyzer.Perform()
        results = analyzer.GetCheckResult()
        records = []
        while results.Size():
            result = results.First()
            faulty = result.GetFaultyShapes1()
            pair = []
            while faulty.Size():
                item = faulty.First()
                pair.append({"topabs_type": int(item.ShapeType()), "bounds_mm": bbox(item)})
                faulty.RemoveFirst()
            records.append({
                "status": int(result.GetCheckStatus()),
                "max_distance_mm": float(result.GetMaxDistance1()),
                "max_parameter": float(result.GetMaxParameter1()),
                "faulty_shape_pair": pair,
            })
            results.RemoveFirst()
        return records
    finally:
        if os.path.exists(brep_path):
            os.remove(brep_path)


def freecad_bop_count(shape):
    try:
        shape.check(True)
        return 0
    except Exception as exc:
        return sum(line.strip().startswith("Error in")
                   for line in str(exc).splitlines())


def mesh_metrics(shape):
    mesh = MeshPart.meshFromShape(
        Shape=shape, LinearDeflection=0.12, AngularDeflection=0.18,
        Relative=False,
    )
    incidence = {}
    for facet in mesh.Facets:
        points = [tuple(round(float(value), 6) for value in point)
                  for point in facet.Points]
        for i, j in ((0, 1), (1, 2), (2, 0)):
            edge = tuple(sorted((points[i], points[j])))
            incidence[edge] = incidence.get(edge, 0) + 1
    return {
        "facets": len(mesh.Facets),
        "closed": bool(mesh.isSolid()),
        "boundary_edges": sum(value == 1 for value in incidence.values()),
        "overincident_edges": sum(value > 2 for value in incidence.values()),
        "degenerate_facets": sum(facet.Area < 1e-12 for facet in mesh.Facets),
    }


candidate = os.path.abspath(os.environ.get("REAR_SHELL_CANDIDATE", DEFAULT_CANDIDATE))
if not os.path.isfile(candidate):
    raise FileNotFoundError(candidate)

doc = App.openDocument(candidate)
try:
    doc.recompute()
    body = doc.getObject("RearShellBody")
    stages = []
    for name in STAGES:
        obj = doc.getObject(name)
        if obj is None:
            raise RuntimeError("Missing feature: " + name)
        shape = obj.Shape
        records = analyze_curve_on_surface(shape)
        stages.append({
            "feature": name,
            "valid": bool(shape.isValid()),
            "solid_count": len(shape.Solids),
            "volume_mm3": float(shape.Volume),
            "curve_on_surface_pair_count": len(records),
            "fault_pairs": records,
        })
    final_shape = body.Tip.Shape
    bounds = final_shape.BoundBox
    result = {
        "candidate": candidate,
        "body_tip": body.Tip.Name,
        "recompute_errors": [
            obj.Name for obj in doc.Objects
            if getattr(obj, "State", None)
            and ("Invalid" in obj.State or "Error" in obj.State)
        ],
        "final": {
            "valid": bool(final_shape.isValid()),
            "solid_count": len(final_shape.Solids),
            "volume_mm3": float(final_shape.Volume),
            "area_mm2": float(final_shape.Area),
            "bounds_mm": [bounds.XMin, bounds.XMax, bounds.YMin,
                          bounds.YMax, bounds.ZMin, bounds.ZMax],
            "freecad_bop_error_lines": freecad_bop_count(final_shape),
            "mesh": mesh_metrics(final_shape),
        },
        "stages": stages,
        "documents_saved": False,
    }
    print(json.dumps(result, indent=2))
finally:
    App.closeDocument(doc.Name)
