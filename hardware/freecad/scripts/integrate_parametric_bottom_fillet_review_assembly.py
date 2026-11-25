"""Link the named bottom-fillet parameter into a disposable full review assembly."""
import json
import shutil
from pathlib import Path

import FreeCAD as App
import MeshPart
import Part


ROOT = Path(__file__).resolve().parents[3]
ASSEMBLY_SOURCE = ROOT / "hardware/freecad/master-driven-leadins-candidate/pendant-modular-combined-finishing-0p6-parametric-chamfer-review-2026-11-01.FCStd"
REAR_SOURCE = ROOT / "hardware/freecad/pendant-bodies/rear-shell-parametric-bottom-fillet-review-2026-11-01.FCStd"
OUTPUT = ROOT / "hardware/freecad/master-driven-leadins-candidate/pendant-modular-combined-finishing-0p6-parametric-bottom-fillet-review-2026-11-01.FCStd"
REPORT = ROOT / "hardware/freecad/reports/combined-finishing-0p6-parametric-bottom-fillet-review-2026-11-01.json"
ALIAS = "BottomPerimeterFilletRadius"

for path in (ASSEMBLY_SOURCE, REAR_SOURCE):
    if not path.is_file():
        raise FileNotFoundError(path)
for path in (OUTPUT, REPORT):
    if path.exists():
        raise FileExistsError("Refusing to overwrite: " + str(path))


def close(doc):
    if doc is not None and App.getDocument(doc.Name):
        App.closeDocument(doc.Name)


def shape_summary(shape):
    bb = shape.BoundBox
    return {"valid": bool(not shape.isNull() and shape.isValid()),
            "solid_count": len(shape.Solids), "volume_mm3": shape.Volume,
            "area_mm2": shape.Area, "bounds_mm": [bb.XMin, bb.XMax,
            bb.YMin, bb.YMax, bb.ZMin, bb.ZMax]}


def mesh_summary(shape):
    mesh = MeshPart.meshFromShape(Shape=shape.copy(), LinearDeflection=0.08,
                                  AngularDeflection=0.35, Relative=False)
    incidence = {}
    degenerate = 0
    for facet in mesh.Facets:
        points = [tuple(round(float(v), 6) for v in p) for p in facet.Points]
        degenerate += facet.Area < 1e-12
        for i, j in ((0, 1), (1, 2), (2, 0)):
            key = tuple(sorted((points[i], points[j])))
            incidence[key] = incidence.get(key, 0) + 1
    return {"closed": bool(mesh.isSolid()), "facets": len(mesh.Facets),
            "boundary_edges": sum(v == 1 for v in incidence.values()),
            "overincident_edges": sum(v > 2 for v in incidence.values()),
            "degenerate_facets": degenerate}


shutil.copy2(ASSEMBLY_SOURCE, OUTPUT)
assembly = App.openDocument(str(OUTPUT))
rear = None
try:
    assembly.recompute()
    root = assembly.getObject("AssemblyRoot")
    rear_link = assembly.getObject("Interim_Body002")
    if root is None or rear_link is None:
        raise RuntimeError("Review assembly root or rear-shell link is missing")
    placement = rear_link.LinkPlacement
    original = shape_summary(rear_link.Shape)

    rear = App.openDocument(str(REAR_SOURCE))
    rear.recompute()
    body = rear.getObject("RearShellStructuralFirstNoDuplicatePad")
    sheet = rear.getObject("StructuralSupportParameters")
    fillet = rear.getObject("StructuralFirstBottomPerimeterFinish")
    if not all((body, body.Tip, sheet, fillet)):
        raise RuntimeError("Parametric rear-shell source is incomplete")
    if body.Tip.Name != "NativeUpperBossShoulderChamfer":
        raise RuntimeError("Rear shell no longer ends at the validated shoulder chamfer")
    if sheet.getCellFromAlias(ALIAS) != "B24":
        raise RuntimeError("Bottom fillet alias is missing from the component source")

    rear_link.LinkedObject = body
    rear_link.LinkPlacement = placement
    rear_link.Label = "Review — rear shell with editable R0.25 bottom fillet and R1.0 boss chamfers"
    assembly.recompute()
    baseline = shape_summary(rear_link.Shape)
    baseline_mesh = mesh_summary(rear_link.Shape)
    if (not root.Shape.isValid() or len(root.Shape.Solids) != 11
            or not baseline["valid"] or baseline["solid_count"] != 1
            or rear_link.LinkPlacement != placement
            or not baseline_mesh["closed"] or baseline_mesh["boundary_edges"]
            or baseline_mesh["overincident_edges"] or baseline_mesh["degenerate_facets"]):
        raise RuntimeError("Linked assembly failed shell placement, solid, or mesh checks")

    cell = sheet.getCellFromAlias(ALIAS)
    sheet.set(cell, "0.30 mm")
    rear.recompute()
    assembly.recompute()
    changed = shape_summary(rear_link.Shape)
    if abs(changed["volume_mm3"] - baseline["volume_mm3"]) < 1e-5:
        raise RuntimeError("Bottom fillet parameter did not reach the linked assembly")
    sheet.set(cell, "0.25 mm")
    rear.recompute()
    assembly.recompute()
    restored = shape_summary(rear_link.Shape)
    if (abs(restored["volume_mm3"] - baseline["volume_mm3"]) > 1e-7
            or abs(restored["area_mm2"] - baseline["area_mm2"]) > 1e-6
            or restored["bounds_mm"] != baseline["bounds_mm"]):
        raise RuntimeError("Assembly geometry did not return to baseline after radius restore")

    # Confirm the independently modeled contact inserts remain clear of the shell.
    pad_intersections = {}
    for name in ("Review_AntiSlipPadUpper", "Review_AntiSlipPadLower"):
        pad = assembly.getObject(name)
        common = rear_link.Shape.common(pad.Shape)
        if not common.isValid() or common.Volume > 1e-7:
            raise RuntimeError("Rear shell intersects anti-slip pad: " + name)
        pad_intersections[name] = common.Volume

    rear.recompute()
    rear.save()
    assembly.recompute()
    assembly.save()
finally:
    close(assembly)
    close(rear)

# Cold-open both files to verify the external link remains intentional and resolvable.
check_assembly = App.openDocument(str(OUTPUT))
check_rear = None
try:
    check_assembly.recompute()
    root = check_assembly.getObject("AssemblyRoot")
    link = check_assembly.getObject("Interim_Body002")
    if root is None or link is None or link.LinkedObject is None:
        raise RuntimeError("Cold-open assembly lost the rear-shell live link")
    check_rear = link.LinkedObject.Document
    body = link.LinkedObject
    sheet = check_rear.getObject("StructuralSupportParameters")
    fillet = check_rear.getObject("StructuralFirstBottomPerimeterFinish")
    cold = shape_summary(link.Shape)
    cold_mesh = mesh_summary(link.Shape)
    if (len(root.Shape.Solids) != 11 or not root.Shape.isValid()
            or body.Tip.Name != "NativeUpperBossShoulderChamfer"
            or sheet.getCellFromAlias(ALIAS) != "B24"
            or abs(fillet.Radius.Value - 0.25) > 1e-8
            or not cold_mesh["closed"] or cold_mesh["boundary_edges"]
            or cold_mesh["overincident_edges"] or cold_mesh["degenerate_facets"]):
        raise RuntimeError("Cold-open linked assembly validation failed")

    cell = sheet.getCellFromAlias(ALIAS)
    sheet.set(cell, "0.30 mm")
    check_rear.recompute()
    check_assembly.recompute()
    cold_probe = shape_summary(link.Shape)
    sheet.set(cell, "0.25 mm")
    check_rear.recompute()
    check_assembly.recompute()
    cold_restore = shape_summary(link.Shape)
    if (abs(cold_probe["volume_mm3"] - cold["volume_mm3"]) < 1e-5
            or abs(cold_restore["volume_mm3"] - cold["volume_mm3"]) > 1e-7):
        raise RuntimeError("Cold-open component edit did not propagate and restore through assembly link")

    result = {
        "status": "validated disposable linked assembly; not production-approved",
        "source_assembly": str(ASSEMBLY_SOURCE.relative_to(ROOT)),
        "candidate_component": str(REAR_SOURCE.relative_to(ROOT)),
        "candidate_assembly": str(OUTPUT.relative_to(ROOT)),
        "protected_monolith_modified": False,
        "production_assembly_modified": False,
        "live_link": link.Name,
        "placement_preserved": True,
        "assembly_root": shape_summary(root.Shape),
        "rear_shell_baseline": baseline,
        "rear_shell_baseline_mesh": baseline_mesh,
        "parameter": {"alias": ALIAS, "baseline_mm": 0.25,
                      "probe_mm": 0.30, "propagation": "component and assembly link"},
        "assembly_probe": changed,
        "assembly_restored": restored,
        "cold_open_recompute": cold,
        "cold_open_mesh": cold_mesh,
        "cold_open_parameter_probe": cold_probe,
        "cold_open_parameter_restored": cold_restore,
        "anti_slip_pad_intersections_mm3": pad_intersections,
        "limitations": [
            "The rear-shell component still uses a stored-shape base.",
            "The legacy 475.701580 mm3 transition-stage difference is not spatially reconciled.",
            "No structural proof-load capacity is claimed.",
        ],
    }
    REPORT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
finally:
    close(check_assembly)
    close(check_rear)
