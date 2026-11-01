"""Cold-open validation of the recovered native rear-shell support candidate.

Run with FreeCADCmd/FreeCAD Python. This reads the protected monolith without
recomputing or saving it, recomputes the disposable candidate and review
assembly in memory, and writes a JSON record beside the report. It never saves
any FCStd document.
"""
import json
import os
from pathlib import Path

import FreeCAD as App
import MeshPart


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "hardware/freecad/pendant.FCStd"
CANDIDATE = ROOT / "hardware/freecad/pendant-bodies/rear-shell-recovered-screw-pad-review-candidate-2026-10-31.FCStd"
ASSEMBLY = ROOT / "hardware/freecad/pendant-modular-recovered-screw-pad-review-assembly-2026-10-31.FCStd"
OUTPUT = ROOT / "hardware/freecad/reports/rear-shell-recovered-screw-pad-candidate-validation-2026-10-31.json"


def shape_metrics(shape):
    box = shape.BoundBox
    return {
        "valid": bool(shape.isValid()),
        "solid_count": len(shape.Solids),
        "volume_mm3": shape.Volume,
        "surface_area_mm2": shape.Area,
        "face_count": len(shape.Faces),
        "bounds_mm": [box.XMin, box.XMax, box.YMin, box.YMax, box.ZMin, box.ZMax],
    }


def mesh_metrics(shape):
    mesh = MeshPart.meshFromShape(
        Shape=shape, LinearDeflection=0.08, AngularDeflection=0.35, Relative=False
    )
    incidence = {}

    def point_key(point):
        return tuple(round(float(c), 6) for c in point)

    degenerate = 0
    for facet in mesh.Facets:
        if facet.Area < 1e-12:
            degenerate += 1
        pts = [point_key(p) for p in facet.Points]
        for a, b in ((pts[0], pts[1]), (pts[1], pts[2]), (pts[2], pts[0])):
            edge = tuple(sorted((a, b)))
            incidence[edge] = incidence.get(edge, 0) + 1
    return {
        "facet_count": len(mesh.Facets),
        "mesh_reports_solid": bool(mesh.isSolid()),
        "boundary_edges": sum(count == 1 for count in incidence.values()),
        "overincident_edges": sum(count > 2 for count in incidence.values()),
        "degenerate_facets": degenerate,
    }


def close_doc(doc):
    if doc is not None and App.getDocument(doc.Name):
        App.closeDocument(doc.Name)


result = {
    "date": "2026-10-31",
    "status": "disposable native reconstruction review; not production-approved",
    "source_document": str(SOURCE.relative_to(ROOT)),
    "candidate_document": str(CANDIDATE.relative_to(ROOT)),
    "assembly_document": str(ASSEMBLY.relative_to(ROOT)),
    "source_recomputed_or_saved": False,
    "candidate_saved_by_validator": False,
}

source_doc = App.openDocument(str(SOURCE))
try:
    saved_tip = source_doc.getObject("RearBossWallRamps45")
    clean_base = source_doc.getObject("Body002FullWidthSeat")
    result["protected_saved_source"] = {
        "tip": saved_tip.Name,
        "tip_shape": shape_metrics(saved_tip.Shape),
        "tip_mesh": mesh_metrics(saved_tip.Shape),
        "clean_base": shape_metrics(clean_base.Shape),
        "stage_net_addition_mm3": saved_tip.Shape.Volume - clean_base.Shape.Volume,
        "stage_deltas_mm3": {
            "RearBossToWallLoadPaths": 383.733575,
            "RearBossShoulderTransitions": -14.961450,
            "RearBossWallRamps45": 106.929454,
        },
        "stages_source": "previously recorded saved feature-stage measurements; source document deliberately not recomputed",
    }
finally:
    close_doc(source_doc)

candidate_doc = App.openDocument(str(CANDIDATE))
try:
    candidate_doc.recompute()
    body = candidate_doc.getObject("RearShell")
    tip = body.Tip
    sketch = candidate_doc.getObject("RecoveredRearMountReinforcementSketch")
    pad = candidate_doc.getObject("RecoveredRearMountReinforcementPad")
    clearance = candidate_doc.getObject("RecoveredRearM2Clearance")
    assert body and tip and sketch and pad and clearance
    baseline_volume = tip.Shape.Volume
    result["candidate"] = {
        "body": body.Name,
        "tip": tip.Name,
        "body_state": list(body.State),
        "tip_shape": shape_metrics(tip.Shape),
        "tip_mesh": mesh_metrics(tip.Shape),
        "reinforcement_sketch": {
            "geometry_count": sketch.GeometryCount,
            "constraint_count": len(sketch.Constraints),
            "fully_constrained": bool(sketch.FullyConstrained),
            "plane_z_mm": sketch.Placement.Base.z,
        },
        "native_pad": {
            "feature": pad.Name,
            "type": pad.TypeId,
            "length_mm": pad.Length.Value,
            "reversed": bool(pad.Reversed),
            "state": list(pad.State),
            "shape": shape_metrics(pad.Shape),
        },
        "m2_clearance_pocket": {
            "feature": clearance.Name,
            "length_mm": clearance.Length.Value,
            "state": list(clearance.State),
            "shape": shape_metrics(clearance.Shape),
        },
        "delta_vs_saved_legacy_tip_mm3": baseline_volume - result["protected_saved_source"]["tip_shape"]["volume_mm3"],
        "delta_vs_clean_base_mm3": baseline_volume - result["protected_saved_source"]["clean_base"]["volume_mm3"],
    }
    assert tip.Shape.isValid() and len(tip.Shape.Solids) == 1
    assert result["candidate"]["tip_mesh"]["mesh_reports_solid"]
    assert result["candidate"]["tip_mesh"]["boundary_edges"] == 0
    assert result["candidate"]["tip_mesh"]["overincident_edges"] == 0
    assert result["candidate"]["tip_mesh"]["degenerate_facets"] == 0
    assert sketch.FullyConstrained and pad.Length.Value == 6.0 and pad.Reversed
    pad.Length = 6.1
    candidate_doc.recompute()
    changed_volume = body.Tip.Shape.Volume
    pad.Length = 6.0
    candidate_doc.recompute()
    restored_volume = body.Tip.Shape.Volume
    result["candidate"]["reversible_parameter_probe"] = {
        "parameter": "RecoveredRearMountReinforcementPad.Length",
        "values_mm": [6.0, 6.1, 6.0],
        "change_delta_mm3": changed_volume - baseline_volume,
        "restored_volume_delta_mm3": restored_volume - baseline_volume,
        "restored_tip_valid_one_solid": body.Tip.Shape.isValid() and len(body.Tip.Shape.Solids) == 1,
        "scope": "volume and native recomputation only; no exact BRep equivalence claim",
    }
    assert abs(restored_volume - baseline_volume) <= 1e-6
finally:
    close_doc(candidate_doc)

assembly_doc = App.openDocument(str(ASSEMBLY))
try:
    assembly_doc.recompute()
    root = assembly_doc.getObject("AssemblyRoot")
    assert root
    links = []
    for obj in assembly_doc.Objects:
        if obj.TypeId == "App::Link":
            target = getattr(obj, "LinkedObject", None)
            links.append({
                "name": obj.Name,
                "target": target.Name if target else None,
                "target_document": target.Document.Name if target else None,
                "valid": bool(obj.Shape.isValid()),
                "solid_count": len(obj.Shape.Solids),
                "volume_mm3": obj.Shape.Volume,
                "placement": str(obj.LinkPlacement),
            })
    result["review_assembly"] = {
        "root": root.Name,
        "root_valid": bool(root.Shape.isValid()),
        "root_solid_count": len(root.Shape.Solids),
        "link_count": len(links),
        "links": links,
        "candidate_rear_link_present": any(
            link["target_document"] == Path(CANDIDATE).stem.replace("-", "_")
            for link in links
        ),
        "previous_pairwise_check": {
            "new_intersections_from_candidate": 0,
            "existing_usb_cover_rear_overlap_mm3": 0.7804718846,
            "scope": "previous disposable pairwise comparison; overlap unchanged; not recalculated by this script",
        },
    }
    assert root.Shape.isValid() and len(root.Shape.Solids) == 11
    assert result["review_assembly"]["candidate_rear_link_present"]
    assert all(link["valid"] for link in links)
finally:
    close_doc(assembly_doc)

result["interpretation"] = {
    "regional_material_map": "Prior 0.5 mm mesh occupancy sampling located +262.875 mm3 net in four screw-boss-to-wall regions: upper-left +42.750, upper-right +40.625, lower-left +90.625, lower-right +88.875 mm3. This is approximate occupancy, not exact material partitioning.",
    "unresolved_difference": "The 475.701580 mm3 saved-stage BRep delta is not fully spatially accounted for. The legacy Tip mesh is non-watertight, and sampled occupancy is not an exact BRep difference.",
    "decision": "Keep candidate review-only. It is one valid solid with a closed mesh and has native, editable support pads, but it is not geometrically equivalent to the saved legacy Tip and has no validated load rating.",
}

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
