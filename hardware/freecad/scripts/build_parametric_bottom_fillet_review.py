"""Expose the validated rear bottom-perimeter fillet radius as a parameter.

Creates a new disposable component copy, tests a reversible radius edit, and
validates save/reopen/recompute. The source review component is read-only.
"""
import json
from pathlib import Path

import FreeCAD as App
import MeshPart


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "hardware/freecad/pendant-bodies/rear-shell-parametric-shoulder-chamfer-review-2026-11-01.FCStd"
OUTPUT = ROOT / "hardware/freecad/pendant-bodies/rear-shell-parametric-bottom-fillet-review-2026-11-01.FCStd"
REPORT = ROOT / "hardware/freecad/reports/rear-shell-parametric-bottom-fillet-review-2026-11-01.json"
ALIAS = "BottomPerimeterFilletRadius"
BASELINE = 0.25
PROBE = 0.30

for path in (SOURCE, OUTPUT, REPORT):
    if not path.exists() and path == SOURCE:
        raise FileNotFoundError(path)
for path in (OUTPUT, REPORT):
    if path.exists():
        raise FileExistsError("Refusing to overwrite review artifact: " + str(path))


def shape_metrics(shape):
    mesh = MeshPart.meshFromShape(Shape=shape.copy(), LinearDeflection=0.08,
                                  AngularDeflection=0.35, Relative=False)
    incidence = {}
    degenerate = 0
    for facet in mesh.Facets:
        points = [tuple(round(float(v), 6) for v in p) for p in facet.Points]
        degenerate += facet.Area < 1e-12
        for a, b in ((0, 1), (1, 2), (2, 0)):
            key = tuple(sorted((points[a], points[b])))
            incidence[key] = incidence.get(key, 0) + 1
    bb = shape.BoundBox
    return {
        "valid": bool(not shape.isNull() and shape.isValid()),
        "solid_count": len(shape.Solids), "volume_mm3": shape.Volume,
        "area_mm2": shape.Area, "face_count": len(shape.Faces),
        "bounds_mm": [bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax],
        "mesh_closed": bool(mesh.isSolid()), "mesh_facets": len(mesh.Facets),
        "mesh_boundary_edges": sum(v == 1 for v in incidence.values()),
        "mesh_overincident_edges": sum(v > 2 for v in incidence.values()),
        "mesh_degenerate_facets": degenerate,
    }


def check_mesh(m):
    return (m["valid"] and m["solid_count"] == 1 and m["mesh_closed"]
            and m["mesh_boundary_edges"] == 0
            and m["mesh_overincident_edges"] == 0
            and m["mesh_degenerate_facets"] == 0)


doc = App.openDocument(str(SOURCE))
try:
    doc.recompute()
    body = doc.getObject("RearShellStructuralFirstNoDuplicatePad")
    sheet = doc.getObject("StructuralSupportParameters")
    fillet = doc.getObject("StructuralFirstBottomPerimeterFinish")
    if not all((body, sheet, fillet)) or fillet not in body.Group:
        raise RuntimeError("Expected rear Body, parameter sheet, and native bottom fillet")
    if fillet.TypeId != "PartDesign::Fillet" or body.Tip.Name != "NativeUpperBossShoulderChamfer":
        raise RuntimeError("Expected fillet to remain upstream of the active shoulder chamfer")
    if abs(fillet.Radius.Value - BASELINE) > 1e-8:
        raise RuntimeError("Source perimeter fillet is not at the validated 0.25 mm baseline")

    baseline = shape_metrics(body.Shape)
    if not check_mesh(baseline):
        raise RuntimeError("Source rear shell is not a valid one-solid manifold-mesh candidate")

    sheet.set("A24", ALIAS)
    sheet.set("B24", "0.25 mm")
    sheet.setAlias("B24", ALIAS)
    fillet.setExpression("Radius", "StructuralSupportParameters." + ALIAS)
    doc.recompute()
    if abs(fillet.Radius.Value - BASELINE) > 1e-8:
        raise RuntimeError("Named fillet parameter did not bind at baseline")
    linked_baseline = shape_metrics(body.Shape)

    sheet.set(sheet.getCellFromAlias(ALIAS), "%.2f mm" % PROBE)
    doc.recompute()
    edited = shape_metrics(body.Shape)
    if not check_mesh(edited) or abs(fillet.Radius.Value - PROBE) > 1e-8:
        raise RuntimeError("0.30 mm perimeter fillet probe failed solid or mesh validation")
    if abs(edited["volume_mm3"] - linked_baseline["volume_mm3"]) < 1e-5:
        raise RuntimeError("Fillet radius edit did not propagate to the Body Tip")

    sheet.set(sheet.getCellFromAlias(ALIAS), "%.2f mm" % BASELINE)
    doc.recompute()
    restored = shape_metrics(body.Shape)
    if (not check_mesh(restored)
            or abs(restored["volume_mm3"] - linked_baseline["volume_mm3"]) > 1e-7
            or abs(restored["area_mm2"] - linked_baseline["area_mm2"]) > 1e-6
            or restored["face_count"] != linked_baseline["face_count"]
            or restored["bounds_mm"] != linked_baseline["bounds_mm"]):
        raise RuntimeError("Restoring 0.25 mm failed to recover baseline shape metrics")

    doc.recompute()
    doc.saveAs(str(OUTPUT))
finally:
    App.closeDocument(doc.Name)

check = App.openDocument(str(OUTPUT))
try:
    check.recompute()
    body = check.getObject("RearShellStructuralFirstNoDuplicatePad")
    sheet = check.getObject("StructuralSupportParameters")
    fillet = check.getObject("StructuralFirstBottomPerimeterFinish")
    cold = shape_metrics(body.Shape)
    expressions = dict(fillet.ExpressionEngine)
    if (body.Tip.Name != "NativeUpperBossShoulderChamfer"
            or abs(fillet.Radius.Value - BASELINE) > 1e-8
            or sheet.getCellFromAlias(ALIAS) != "B24"
            or expressions.get("Radius") != "StructuralSupportParameters." + ALIAS
            or not check_mesh(cold)
            or abs(cold["volume_mm3"] - restored["volume_mm3"]) > 1e-7):
        raise RuntimeError("Cold-open fillet parameter validation failed")
    result = {
        "status": "validated disposable component study; not production-approved",
        "source": str(SOURCE.relative_to(ROOT)),
        "candidate": str(OUTPUT.relative_to(ROOT)),
        "protected_monolith_modified": False,
        "production_assembly_modified": False,
        "feature": fillet.Name,
        "parameter": {
            "spreadsheet": sheet.Name, "alias": ALIAS, "cell": "B24",
            "expression": expressions.get("Radius"), "baseline_mm": BASELINE,
            "reversible_probe_mm": [BASELINE, PROBE, BASELINE],
        },
        "baseline_after_expression_binding": linked_baseline,
        "edited_at_0p30_mm": edited,
        "restored_at_0p25_mm": restored,
        "cold_open_recompute": cold,
        "save_close_reopen_recompute": "passed",
        "limitations": [
            "The component base is still a stored-shape review base.",
            "The legacy 475.701580 mm3 load-path stage difference remains unresolved.",
            "Mesh closure is not a structural proof-load result.",
        ],
    }
    REPORT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
finally:
    App.closeDocument(check.Name)
