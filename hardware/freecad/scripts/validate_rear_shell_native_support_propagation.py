"""Run a reversible lower-web parameter edit on a disposable rear-shell copy."""
import json
import os
import shutil
from pathlib import Path

import FreeCAD as App
import MeshPart


ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path(os.environ.get(
    "PENDANT_SUPPORT_PROPAGATION_SOURCE",
    str(ROOT / "hardware/freecad/pendant-bodies/rear-shell-native-shoulder-chamfer-review-2026-11-01.FCStd"),
)).expanduser().resolve()
OUTPUT = Path(os.environ.get(
    "PENDANT_SUPPORT_PROPAGATION_OUTPUT",
    str(ROOT / "hardware/freecad/pendant-bodies/rear-shell-native-support-propagation-review-2026-11-01.FCStd"),
)).expanduser().resolve()
REPORT = Path(os.environ.get(
    "PENDANT_SUPPORT_PROPAGATION_REPORT",
    str(ROOT / "hardware/freecad/reports/rear-shell-native-support-propagation-review-2026-11-01.json"),
)).expanduser().resolve()

for path in (SOURCE,):
    if not path.exists():
        raise FileNotFoundError(path)
for path in (OUTPUT, REPORT):
    if path.exists():
        raise FileExistsError("Refusing to overwrite: " + str(path))
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
REPORT.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(SOURCE, OUTPUT)


def metrics(shape):
    mesh = MeshPart.meshFromShape(Shape=shape.copy(), LinearDeflection=0.08,
                                  AngularDeflection=0.35, Relative=False)
    incidence = {}
    for facet in mesh.Facets:
        pts = [tuple(round(float(v), 6) for v in p) for p in facet.Points]
        for i, j in ((0, 1), (1, 2), (2, 0)):
            key = tuple(sorted((pts[i], pts[j])))
            incidence[key] = incidence.get(key, 0) + 1
    box = shape.BoundBox
    return {
        "valid": shape.isValid(),
        "solids": len(shape.Solids),
        "volume_mm3": shape.Volume,
        "area_mm2": shape.Area,
        "faces": len(shape.Faces),
        "edges": len(shape.Edges),
        "bounds_mm": [box.XMin, box.XMax, box.YMin, box.YMax,
                      box.ZMin, box.ZMax],
        "mesh_closed": mesh.isSolid(),
        "mesh_facets": len(mesh.Facets),
        "mesh_boundary_edges": sum(n == 1 for n in incidence.values()),
        "mesh_overincident_edges": sum(n > 2 for n in incidence.values()),
        "mesh_degenerate_facets": sum(f.Area < 1e-12 for f in mesh.Facets),
    }


doc = App.openDocument(str(OUTPUT))
try:
    doc.recompute()
    body = doc.getObject("RearShellStructuralFirstNoDuplicatePad")
    sheet = next(o for o in doc.Objects if o.TypeId == "Spreadsheet::Sheet"
                 and o.Label == "Rear support and web parameters")
    cell = next(c for c in sheet.getUsedCells()
                if sheet.getAlias(c) == "LowerWebP2XAbs")
    original_value = str(sheet.get(cell))
    baseline = body.Tip.Shape.copy()
    baseline_metrics = metrics(baseline)

    sheet.set(cell, "10.0")
    doc.recompute()
    changed = body.Tip.Shape.copy()
    changed_metrics = metrics(changed)
    if (not changed_metrics["valid"] or changed_metrics["solids"] != 1
            or abs(changed_metrics["volume_mm3"] - baseline_metrics["volume_mm3"]) < 1e-4):
        raise RuntimeError("LowerWebP2XAbs change did not propagate to a valid changed Tip")
    sketches = [o for o in body.Group if o.TypeId == "Sketcher::SketchObject"]
    if not all(o.FullyConstrained for o in sketches):
        raise RuntimeError("A support sketch lost full constraint during the parameter edit")

    sheet.set(cell, original_value)
    doc.recompute()
    restored = body.Tip.Shape.copy()
    diff_a, diff_b = restored.cut(baseline), baseline.cut(restored)
    if (diff_a.isNull() or diff_b.isNull() or not diff_a.isValid()
            or not diff_b.isValid() or diff_a.Volume + diff_b.Volume > 1e-6):
        raise RuntimeError("Restoring the parameter did not restore the baseline BREP")
    restored_metrics = metrics(restored)
    if (not restored_metrics["valid"] or restored_metrics["solids"] != 1
            or not restored_metrics["mesh_closed"]
            or restored_metrics["mesh_boundary_edges"]
            or restored_metrics["mesh_overincident_edges"]
            or restored_metrics["mesh_degenerate_facets"]):
        raise RuntimeError("Restored rear shell failed solid or mesh-manifold checks")
    for obj in body.Group:
        if obj.TypeId.startswith("PartDesign::") and any(
                state in obj.State for state in ("Invalid", "Error")):
            raise RuntimeError("Feature error after restore: %s %s" % (obj.Name, obj.State))
    doc.recompute()
    doc.save()
finally:
    if App.getDocument(doc.Name):
        App.closeDocument(doc.Name)

cold = App.openDocument(str(OUTPUT))
try:
    cold.recompute()
    body = cold.getObject("RearShellStructuralFirstNoDuplicatePad")
    cold_shape = body.Tip.Shape.copy()
    cold_metrics = metrics(cold_shape)
    a, b = cold_shape.cut(baseline), baseline.cut(cold_shape)
    cold_difference = a.Volume + b.Volume
    if (a.isNull() or b.isNull() or not a.isValid() or not b.isValid()
            or cold_difference > 1e-6):
        raise RuntimeError("Cold reopen/recompute did not reproduce the baseline BREP")
    if (body.Tip.Name != "NativeUpperBossShoulderChamfer"
            or not cold_metrics["valid"] or cold_metrics["solids"] != 1
            or not cold_metrics["mesh_closed"] or cold_metrics["mesh_boundary_edges"]
            or cold_metrics["mesh_overincident_edges"]
            or cold_metrics["mesh_degenerate_facets"]):
        raise RuntimeError("Cold-open rear Tip failed its solid/manifold checks")
    result = {
        "status": "disposable parameter-propagation candidate; not production-approved",
        "source": str(SOURCE),
        "candidate": str(OUTPUT),
        "parameter": {
            "alias": "LowerWebP2XAbs",
            "cell": cell,
            "baseline_value": original_value,
            "test_value": "10.0",
            "meaning": "mirrored inner lower-web profile X magnitude",
        },
        "baseline_tip": baseline_metrics,
        "perturbed_tip": changed_metrics,
        "perturbed_volume_delta_mm3": changed_metrics["volume_mm3"] - baseline_metrics["volume_mm3"],
        "restored_tip": restored_metrics,
        "restored_symmetric_difference_mm3": diff_a.Volume + diff_b.Volume,
        "cold_reopen_tip": cold_metrics,
        "cold_reopen_symmetric_difference_mm3": cold_difference,
        "support_sketches_fully_constrained": True,
        "production_documents_modified": False,
    }
    REPORT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
finally:
    if App.getDocument(cold.Name):
        App.closeDocument(cold.Name)
