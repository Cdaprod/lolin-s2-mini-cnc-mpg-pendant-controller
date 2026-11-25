"""Make the existing upper-boss shoulder chamfer size locally parametric.

Only a new review component is saved. The protected monolith and existing
shoulder-chamfer candidate remain unchanged.
"""
import json
import os
from pathlib import Path

import FreeCAD as App
import MeshPart


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "hardware/freecad/pendant-bodies/rear-shell-native-shoulder-chamfer-review-2026-11-01.FCStd"
OUTPUT = ROOT / "hardware/freecad/pendant-bodies/rear-shell-parametric-shoulder-chamfer-review-2026-11-01.FCStd"
REPORT = ROOT / "hardware/freecad/reports/rear-shell-parametric-shoulder-chamfer-review-2026-11-01.json"
ALIAS = "UpperBossShoulderChamferSize"


def summary(shape):
    bb = shape.BoundBox
    return {"valid": bool(not shape.isNull() and shape.isValid()),
            "solid_count": len(shape.Solids), "volume_mm3": shape.Volume,
            "area_mm2": shape.Area, "faces": len(shape.Faces),
            "bounds_mm": [bb.XMin, bb.XMax, bb.YMin, bb.YMax,
                          bb.ZMin, bb.ZMax]}


def same_geometry(a, b):
    return (a["valid"] and b["valid"] and a["solid_count"] == b["solid_count"] == 1
            and abs(a["volume_mm3"] - b["volume_mm3"]) <= 1e-6
            and abs(a["area_mm2"] - b["area_mm2"]) <= 1e-5
            and a["faces"] == b["faces"] and a["bounds_mm"] == b["bounds_mm"])


def mesh_audit(shape):
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
    return {"closed": bool(mesh.isSolid()), "facets": len(mesh.Facets),
            "boundary_edges": sum(v == 1 for v in incidence.values()),
            "overincident_edges": sum(v > 2 for v in incidence.values()),
            "degenerate_facets": degenerate}


if not SOURCE.is_file():
    raise FileNotFoundError(SOURCE)
for path in (OUTPUT, REPORT):
    if path.exists():
        raise FileExistsError("Refusing to overwrite review artifact: " + str(path))

doc = App.openDocument(str(SOURCE))
try:
    doc.recompute()
    body = doc.getObject("RearShellStructuralFirstNoDuplicatePad")
    sheet = doc.getObject("StructuralSupportParameters")
    chamfer = doc.getObject("NativeUpperBossShoulderChamfer")
    if not all((body, sheet, chamfer)) or body.Tip != chamfer:
        raise RuntimeError("Expected active native shoulder-chamfer feature was not found")
    if not body.Shape.isValid() or len(body.Shape.Solids) != 1:
        raise RuntimeError("Source shoulder-chamfer candidate is not one valid solid")
    if abs(chamfer.Size.Value - 1.0) > 1e-8:
        raise RuntimeError("Expected original shoulder chamfer size 1.0 mm")

    original = summary(body.Shape)
    original_mesh = mesh_audit(body.Shape)
    sheet.set("A23", ALIAS)
    sheet.set("B23", "1.0 mm")
    sheet.setAlias("B23", ALIAS)
    chamfer.setExpression("Size", "StructuralSupportParameters." + ALIAS)
    doc.recompute()
    if abs(chamfer.Size.Value - 1.0) > 1e-8 or not chamfer.Shape.isValid():
        raise RuntimeError("Named parameter did not bind to the native Chamfer feature")

    sheet.set(sheet.getCellFromAlias(ALIAS), "0.8 mm")
    doc.recompute()
    changed = summary(body.Shape)
    changed_mesh = mesh_audit(body.Shape)
    if (not changed["valid"] or changed["solid_count"] != 1
            or abs(chamfer.Size.Value - 0.8) > 1e-8
            or abs(changed["volume_mm3"] - original["volume_mm3"]) < 1e-4
            or not changed_mesh["closed"] or changed_mesh["boundary_edges"]
            or changed_mesh["overincident_edges"] or changed_mesh["degenerate_facets"]):
        raise RuntimeError("0.8 mm parameter probe failed native geometry/mesh validation")

    sheet.set(sheet.getCellFromAlias(ALIAS), "1.0 mm")
    doc.recompute()
    restored = summary(body.Shape)
    restored_mesh = mesh_audit(body.Shape)
    if (not same_geometry(restored, original) or not restored_mesh["closed"]
            or restored_mesh["boundary_edges"] or restored_mesh["overincident_edges"]
            or restored_mesh["degenerate_facets"]):
        raise RuntimeError("Restoring 1.0 mm did not recover baseline geometry and a manifold mesh")

    doc.recompute()
    doc.saveAs(str(OUTPUT))
finally:
    App.closeDocument(doc.Name)

# Cold-open, recompute, and verify the expression and baseline.
check = App.openDocument(str(OUTPUT))
try:
    check.recompute()
    body = check.getObject("RearShellStructuralFirstNoDuplicatePad")
    sheet = check.getObject("StructuralSupportParameters")
    chamfer = check.getObject("NativeUpperBossShoulderChamfer")
    actual = summary(body.Shape)
    actual_mesh = mesh_audit(body.Shape)
    expressions = dict(chamfer.ExpressionEngine)
    if (not body.Shape.isValid() or len(body.Shape.Solids) != 1
            or abs(chamfer.Size.Value - 1.0) > 1e-8
            or sheet.getCellFromAlias(ALIAS) != "B23"
            or expressions.get("Size") != "StructuralSupportParameters." + ALIAS
            or not same_geometry(actual, original) or not actual_mesh["closed"]
            or actual_mesh["boundary_edges"] or actual_mesh["overincident_edges"]
            or actual_mesh["degenerate_facets"]):
        raise RuntimeError("Cold-open parametric chamfer validation failed")
    result = {
        "status": "disposable parametric feature candidate; not production approved",
        "component": str(OUTPUT.relative_to(ROOT)),
        "source": str(SOURCE.relative_to(ROOT)),
        "parameter": {"spreadsheet": "StructuralSupportParameters", "alias": ALIAS,
                      "cell": "B23", "unit": "mm", "baseline": 1.0,
                      "reversible_test": "1.0 -> 0.8 -> 1.0"},
        "expression": expressions.get("Size"),
        "original": original,
        "edited": changed,
        "restored": restored,
        "cold_open_recompute": actual,
        "mesh_baseline": original_mesh,
        "mesh_edited": changed_mesh,
        "mesh_restored": restored_mesh,
        "restored_geometry_equivalent_within_tolerances": same_geometry(restored, original),
        "save_close_reopen_recompute": "passed",
        "protected_documents_modified": False,
    }
    REPORT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
finally:
    App.closeDocument(check.Name)
