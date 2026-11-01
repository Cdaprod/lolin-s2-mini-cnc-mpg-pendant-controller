"""Build a disposable rear-shell review candidate with a fresh union base.

The source component and protected monolith are read-only inputs. The script
replaces only the copied candidate's stored base Shape with a fresh union of
SmallHangerPocketBody002 and Body002FullLandTransferTool, then recomputes its
native support, fillet, and anti-slip-seat feature chain. It refuses to
overwrite outputs. This remains a hybrid review component because the fused
base is still a stored-shape PartDesign feature.

Run with FreeCAD's Python environment. Optional environment variables:
  PENDANT_FRESH_FUSE_OUTPUT: destination FCStd path
  PENDANT_FRESH_FUSE_REPORT: destination JSON path
"""
import json
import os
import shutil
from pathlib import Path

import FreeCAD as App
import MeshPart


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "hardware/freecad/pendant-bodies/rear-shell-structural-support-parameter-review-2026-11-01.FCStd"
MONOLITH = ROOT / "hardware/freecad/pendant.FCStd"
DEFAULT_OUTPUT = ROOT / "hardware/freecad/pendant-bodies/rear-shell-fresh-fuse-structural-review-2026-11-01.FCStd"
DEFAULT_REPORT = ROOT / "hardware/freecad/reports/rear-shell-fresh-fuse-structural-review-2026-11-01.json"
OUTPUT = Path(os.environ.get("PENDANT_FRESH_FUSE_OUTPUT", str(DEFAULT_OUTPUT))).expanduser().resolve()
REPORT = Path(os.environ.get("PENDANT_FRESH_FUSE_REPORT", str(DEFAULT_REPORT))).expanduser().resolve()

for path in (SOURCE, MONOLITH):
    if not path.exists():
        raise FileNotFoundError(path)
for path in (OUTPUT, REPORT):
    if path.exists():
        raise FileExistsError("Refusing to overwrite: %s" % path)


def metrics(shape, include_bop=False):
    box = shape.BoundBox
    mesh = MeshPart.meshFromShape(Shape=shape.copy(), LinearDeflection=0.08,
                                  AngularDeflection=0.35, Relative=False)
    incidence = {}
    for facet in mesh.Facets:
        points = [tuple(round(float(value), 6) for value in point)
                  for point in facet.Points]
        for first, second in ((0, 1), (1, 2), (2, 0)):
            edge = tuple(sorted((points[first], points[second])))
            incidence[edge] = incidence.get(edge, 0) + 1
    result = {
        "valid": bool(shape.isValid()),
        "solid_count": len(shape.Solids),
        "volume_mm3": shape.Volume,
        "area_mm2": shape.Area,
        "face_count": len(shape.Faces),
        "edge_count": len(shape.Edges),
        "bounds_mm": [box.XMin, box.XMax, box.YMin, box.YMax, box.ZMin, box.ZMax],
        "mesh_closed": bool(mesh.isSolid()),
        "mesh_facets": len(mesh.Facets),
        "mesh_boundary_edges": sum(count == 1 for count in incidence.values()),
        "mesh_overincident_edges": sum(count > 2 for count in incidence.values()),
        "mesh_degenerate_facets": sum(facet.Area < 1e-12 for facet in mesh.Facets),
    }
    if include_bop:
        try:
            shape.check(True)
            result["bop_check_errors"] = 0
        except Exception as error:
            result["bop_check_errors"] = sum(
                line.startswith("Error in ") for line in str(error).splitlines()
            )
    return result


def close_document(document):
    if document and App.getDocument(document.Name):
        App.closeDocument(document.Name)


shutil.copy2(str(SOURCE), str(OUTPUT))
component = App.openDocument(str(OUTPUT))
monolith = App.openDocument(str(MONOLITH))
try:
    base = component.getObject("CleanRearShellBase")
    body = component.getObject("RearShellStructuralFirstNoDuplicatePad")
    source_hanger = monolith.getObject("SmallHangerPocketBody002")
    source_transfer = monolith.getObject("Body002FullLandTransferTool")
    if not all((base, body, source_hanger, source_transfer)):
        raise RuntimeError("Required base, Body, or source shape is missing")

    original_base = base.Shape.copy()
    fresh_base = source_hanger.Shape.copy().fuse(source_transfer.Shape.copy())
    old_bounds = original_base.BoundBox
    new_bounds = fresh_base.BoundBox
    if any(abs(a - b) > 1e-6 for a, b in zip(
            (old_bounds.XMin, old_bounds.XMax, old_bounds.YMin, old_bounds.YMax,
             old_bounds.ZMin, old_bounds.ZMax),
            (new_bounds.XMin, new_bounds.XMax, new_bounds.YMin, new_bounds.YMax,
             new_bounds.ZMin, new_bounds.ZMax))):
        raise RuntimeError("Fresh fused base changed the global bounding box")
    base.Shape = fresh_base
    component.recompute()
    body.Tip = component.getObject("FinishOrder_AntiSlipSeatPocket")

    names = (
        "CleanRearShellBase",
        "FinishOrder_UpperLeftSupportPad",
        "FinishOrder_UpperRightSupportPad",
        "FinishOrder_LowerLeftSupportPad",
        "FinishOrder_LowerRightSupportPad",
        "FinishOrder_M2Passages",
        "FinishOrder_LowerLeftInnerWebPad",
        "FinishOrder_LowerRightInnerWebPad",
        "StructuralFirstBottomPerimeterFinish",
        "FinishOrder_AntiSlipSeatPocket",
    )
    stages = {}
    for name in names:
        obj = component.getObject(name)
        if obj is None or not hasattr(obj, "Shape") or obj.Shape.isNull():
            raise RuntimeError("Missing or empty feature: " + name)
        stages[name] = {
            "state": list(obj.State),
            "shape": metrics(obj.Shape, include_bop=True),
        }
    if not body.Shape.isValid() or len(body.Shape.Solids) != 1:
        raise RuntimeError("Recomputed Body is not one valid solid")
    pre_save = metrics(body.Shape)
    if (not pre_save["mesh_closed"] or pre_save["mesh_boundary_edges"]
            or pre_save["mesh_overincident_edges"] or pre_save["mesh_degenerate_facets"]):
        raise RuntimeError("Recomputed Tip mesh is not manifold")

    component.recompute()
    component.save()
finally:
    close_document(component)
    close_document(monolith)

check = App.openDocument(str(OUTPUT))
try:
    check.recompute()
    body = check.getObject("RearShellStructuralFirstNoDuplicatePad")
    cold = metrics(body.Shape, include_bop=True)
    if body.Tip.Name != "FinishOrder_AntiSlipSeatPocket":
        raise RuntimeError("Cold-open Body Tip changed unexpectedly")
    if (not body.Shape.isValid() or len(body.Shape.Solids) != 1
            or not cold["mesh_closed"] or cold["mesh_boundary_edges"]
            or cold["mesh_overincident_edges"] or cold["mesh_degenerate_facets"]):
        raise RuntimeError("Cold-open validation failed")
    result = {
        "status": "disposable review candidate; not production-approved",
        "candidate": str(OUTPUT),
        "source_component": str(SOURCE),
        "source_monolith": str(MONOLITH),
        "base_method": "fresh fuse of saved SmallHangerPocketBody002 and Body002FullLandTransferTool shapes",
        "base_is_stored_shape": True,
        "native_support_features": True,
        "protected_monolith_modified": False,
        "production_assembly_modified": False,
        "original_candidate_base": metrics(original_base),
        "fresh_fused_base": metrics(fresh_base, include_bop=True),
        "fresh_base_delta_mm3": fresh_base.Volume - original_base.Volume,
        "feature_stages": stages,
        "cold_reopen": {
            "tip": body.Tip.Name,
            "tip_state": list(body.Tip.State),
            "shape": cold,
        },
        "structural_capacity_verified": False,
        "exact_equivalence_to_defective_legacy_tip": False,
    }
    REPORT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, separators=(",", ":")))
finally:
    close_document(check)
