"""Read-only cold-open validation of the selective rear-loft refinement study.

Run with FreeCADCmd and the repository checked out in its current layout.
The validator opens the original review candidate and the selective candidate,
recomputes them, checks BOP diagnostics and exported mesh incidence, then closes
both without saving.
"""
import json
import os
import FreeCAD as App
import MeshPart


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BODY_DIR = os.path.join(ROOT, "pendant-bodies")
BASELINE = os.path.join(BODY_DIR, "rear-shell-native-loadpath-manifold-review-2026-11-01.FCStd")
CANDIDATE = os.path.join(BODY_DIR, "rear-shell-native-loadpath-selective-refine-review-2026-11-01.FCStd")
LOFTS = ("MiddleLeftNativeLoadPath", "MiddleRightNativeLoadPath",
         "LowerLeftNativeLoadPath", "LowerRightNativeLoadPath")


def bop_findings(shape):
    try:
        shape.check(True)
        return []
    except Exception as exc:
        return [line.strip() for line in str(exc).splitlines()
                if line.strip().startswith("Error in")]


def mesh_metrics(shape):
    mesh = MeshPart.meshFromShape(
        Shape=shape, LinearDeflection=0.12, AngularDeflection=0.18, Relative=False
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
        "boundary_edges": sum(count == 1 for count in incidence.values()),
        "overincident_edges": sum(count > 2 for count in incidence.values()),
        "degenerate_facets": sum(facet.Area < 1e-12 for facet in mesh.Facets),
    }


def inspect(path, refine_override=None):
    doc = App.openDocument(path)
    try:
        doc.recompute()
        if refine_override is not None:
            doc.getObject("MiddleLeftNativeLoadPath").Refine = refine_override
            doc.recompute()
        body = doc.getObject("RearShellBody")
        shape = body.Tip.Shape
        box = shape.BoundBox
        return {
            "file": os.path.basename(path),
            "tip": body.Tip.Name,
            "valid": bool(shape.isValid()),
            "solid_count": len(shape.Solids),
            "volume_mm3": shape.Volume,
            "area_mm2": shape.Area,
            "face_count": len(shape.Faces),
            "bounds_mm": [box.XMin, box.XMax, box.YMin, box.YMax,
                          box.ZMin, box.ZMax],
            "refine_flags": {name: bool(doc.getObject(name).Refine) for name in LOFTS},
            "bop_findings": bop_findings(shape),
            "mesh": mesh_metrics(shape),
            "recompute_errors": [obj.Name for obj in doc.Objects
                                 if getattr(obj, "State", None)
                                 and "Invalid" in obj.State],
        }
    finally:
        App.closeDocument(doc.Name)


if not os.path.isfile(BASELINE) or not os.path.isfile(CANDIDATE):
    raise FileNotFoundError("Required rear-shell candidate file is missing")
base = inspect(BASELINE)
candidate = inspect(CANDIDATE)
vol_delta = candidate["volume_mm3"] - base["volume_mm3"]
area_delta = candidate["area_mm2"] - base["area_mm2"]
bounds_delta = [candidate["bounds_mm"][i] - base["bounds_mm"][i]
                for i in range(6)]
checks = {
    "candidate_valid_single_solid": candidate["valid"] and candidate["solid_count"] == 1,
    "cold_recompute_has_no_invalid_features": not candidate["recompute_errors"],
    "middle_left_refine_disabled_only": (
        candidate["refine_flags"]["MiddleLeftNativeLoadPath"] is False
        and all(candidate["refine_flags"][name] for name in LOFTS[1:])
    ),
    "candidate_mesh_closed_manifold": (
        candidate["mesh"]["closed"] and candidate["mesh"]["boundary_edges"] == 0
        and candidate["mesh"]["overincident_edges"] == 0
        and candidate["mesh"]["degenerate_facets"] == 0
    ),
    "bop_count_reduced": len(candidate["bop_findings"]) < len(base["bop_findings"]),
    "bounds_unchanged_within_tolerance": all(abs(v) < 1e-7 for v in bounds_delta),
    "brep_volume_delta_below_0p001_mm3": abs(vol_delta) < 0.001,
    "brep_area_delta_below_0p001_mm2": abs(area_delta) < 0.001,
}
result = {
    "status": "PASS" if all(checks.values()) else "FAIL",
    "baseline": base,
    "candidate": candidate,
    "deltas": {"volume_mm3": vol_delta, "area_mm2": area_delta,
               "bounds_mm": bounds_delta,
               "bop_finding_count": len(candidate["bop_findings"]) - len(base["bop_findings"])},
    "checks": checks,
    "documents_saved": False,
}
print(json.dumps(result, indent=2))
if not all(checks.values()):
    raise RuntimeError("Selective refinement candidate failed validation")
