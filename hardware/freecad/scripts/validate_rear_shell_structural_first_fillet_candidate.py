"""Cold-open validation for the structural-first rear-shell review candidate.

Reads the protected monolith and review assemblies without saving them. The
new assembly link opens the structural-first component from disk, after which
the script recomputes the full link tree, checks mesh incidence and measured
neighbor clearances, and performs a reversible Pad edit through the link.
"""
import json
from pathlib import Path

import FreeCAD as App
import MeshPart


ROOT = Path(__file__).resolve().parents[3]
MONOLITH = ROOT / "hardware/freecad/pendant.FCStd"
OLD_ASSEMBLY = ROOT / "hardware/freecad/pendant-modular-recovered-screw-pad-review-assembly-2026-10-31.FCStd"
ASSEMBLY = ROOT / "hardware/freecad/pendant-modular-structural-first-fillet-review-assembly-2026-10-31.FCStd"
COMPONENT = ROOT / "hardware/freecad/pendant-bodies/rear-shell-structural-first-fillet-candidate-2026-10-31.FCStd"
OUTPUT = ROOT / "hardware/freecad/reports/rear-shell-structural-first-fillet-validation-2026-10-31.json"


def close_doc(doc):
    if doc and App.getDocument(doc.Name):
        App.closeDocument(doc.Name)


def metrics(shape):
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
        return tuple(round(float(value), 6) for value in point)

    degenerate = 0
    for facet in mesh.Facets:
        if facet.Area < 1e-12:
            degenerate += 1
        points = [point_key(point) for point in facet.Points]
        for a, b in ((points[0], points[1]), (points[1], points[2]), (points[2], points[0])):
            edge = tuple(sorted((a, b)))
            incidence[edge] = incidence.get(edge, 0) + 1
    return {
        "facets": len(mesh.Facets),
        "reports_solid": bool(mesh.isSolid()),
        "boundary_edges": sum(count == 1 for count in incidence.values()),
        "overincident_edges": sum(count > 2 for count in incidence.values()),
        "degenerate_facets": degenerate,
    }


def rear_intersections(doc, rear_name):
    rear = doc.getObject(rear_name)
    neighbors = (
        "Interim_Body",
        "Interim_Body003",
        "Interim_EncoderFaceplatePocketUnsplit",
        "Editable_Body_DisplayRetainer_EditableV2",
        "Editable_Body_USBTetheredCover",
        "Editable_Body_FaceplateLocator_A",
        "Editable_Body_FaceplateLocator_B",
        "Editable_Body006",
        "Review_AntiSlipPadUpper",
        "Review_AntiSlipPadLower",
    )
    rows = []
    for name in neighbors:
        other = doc.getObject(name)
        if not other or not hasattr(other, "Shape") or other.Shape.isNull():
            continue
        common = rear.Shape.common(other.Shape)
        rows.append({
            "neighbor": name,
            "label": other.Label,
            "common_valid": bool(common.isValid()),
            "common_volume_mm3": common.Volume,
            "common_solid_count": len(common.Solids),
        })
    return rows


result = {
    "date": "2026-10-31",
    "status": "disposable review candidate; not production-approved",
    "files": {
        "protected_monolith": str(MONOLITH.relative_to(ROOT)),
        "component": str(COMPONENT.relative_to(ROOT)),
        "review_assembly": str(ASSEMBLY.relative_to(ROOT)),
    },
    "documents_saved_by_validator": False,
}

monolith = App.openDocument(str(MONOLITH))
try:
    base = monolith.getObject("Body002FullWidthSeat")
    legacy = monolith.getObject("RearBossWallRamps45")
    result["protected_saved_baseline"] = {
        "recomputed": False,
        "clean_base": metrics(base.Shape),
        "legacy_tip": metrics(legacy.Shape),
        "legacy_tip_mesh": mesh_metrics(legacy.Shape),
        "saved_stage_net_mm3": legacy.Shape.Volume - base.Shape.Volume,
        "stage_deltas_mm3": {
            "RearBossToWallLoadPaths": 383.733575,
            "RearBossShoulderTransitions": -14.961450,
            "RearBossWallRamps45": 106.929454,
        },
    }
finally:
    close_doc(monolith)

old_assembly = App.openDocument(str(OLD_ASSEMBLY))
old_assembly.recompute()
new_assembly = App.openDocument(str(ASSEMBLY))
new_assembly.recompute()
try:
    root = new_assembly.getObject("AssemblyRoot")
    rear_link = new_assembly.getObject("Interim_Body002")
    target = rear_link.LinkedObject
    target_doc = target.Document
    body = target
    if body.Name != "RearShellStructuralFirst":
        raise RuntimeError("Review link points to the wrong rear Body: %s" % body.Name)
    tip = body.Tip
    pre_fillet = target_doc.getObject("FinishOrder_RecoveredM2")
    fillet = target_doc.getObject("StructuralFirstBottomPerimeterFinish")
    seat = target_doc.getObject("FinishOrder_AntiSlipSeatPocket")
    reinforcement = target_doc.getObject("FinishOrder_RecoveredRearMountReinforcementPad")
    if not (root and rear_link and tip and pre_fillet and fillet and seat and reinforcement):
        raise RuntimeError("Review assembly is missing a required feature or link")

    result["component"] = {
        "linked_document_path": target_doc.FileName,
        "body": body.Name,
        "tip": tip.Name,
        "tip_state": list(tip.State),
        "tip_shape": metrics(body.Shape),
        "tip_mesh": mesh_metrics(body.Shape),
        "support_feature_order": [
            "4 boss-to-wall Pads",
            "six M2 passage Pocket",
            "2 lower inner-web Pads",
            "six-circle recovered reinforcement Pad",
            "six M2 passage Pocket",
            "R0.25 bottom perimeter Fillet",
            "0.10 mm anti-slip seat Pocket",
        ],
        "fillet": {
            "radius_mm": fillet.Radius.Value,
            "base_feature": fillet.Base[0].Name,
            "selected_edges": list(fillet.Base[1]),
            "selected_edge_count": len(fillet.Base[1]),
            "pre_fillet_volume_mm3": pre_fillet.Shape.Volume,
            "post_fillet_volume_mm3": fillet.Shape.Volume,
            "removed_volume_mm3": pre_fillet.Shape.Volume - fillet.Shape.Volume,
            "source_face_area_mm2": 4243.2288642514,
            "source_face_normal": [0.0, -0.0436193874, -0.9990482216],
        },
        "seat_pocket": {
            "length_mm": seat.Length.Value,
            "base_feature": seat.BaseFeature.Name,
            "volume_removed_mm3": fillet.Shape.Volume - seat.Shape.Volume,
        },
        "sketches": [],
    }
    if not body.Shape.isValid() or len(body.Shape.Solids) != 1:
        raise RuntimeError("Rear candidate is not one valid solid")
    if result["component"]["tip_mesh"]["boundary_edges"] or result["component"]["tip_mesh"]["overincident_edges"]:
        raise RuntimeError("Rear candidate mesh has non-manifold edges")
    if not result["component"]["tip_mesh"]["reports_solid"]:
        raise RuntimeError("Rear candidate mesh does not report a closed solid")
    if result["component"]["fillet"]["radius_mm"] != 0.25 or len(fillet.Base[1]) != 19:
        raise RuntimeError("Unexpected bottom-perimeter fillet selection")
    for name in (
        "FinishOrder_UpperLeftSupportPadProfile",
        "FinishOrder_UpperRightSupportPadProfile",
        "FinishOrder_LowerLeftSupportPadProfile",
        "FinishOrder_LowerRightSupportPadProfile",
        "FinishOrder_LowerLeftInnerWebPadProfile",
        "FinishOrder_LowerRightInnerWebPadProfile",
        "FinishOrder_RecoveredRearMountReinforcementPadProfile",
    ):
        sketch = target_doc.getObject(name)
        result["component"]["sketches"].append({
            "name": name,
            "geometry_count": sketch.GeometryCount,
            "constraint_count": len(sketch.Constraints),
            "fully_constrained": bool(sketch.FullyConstrained),
            "external_geometry_count": getattr(sketch, "ExternalGeometryCount", 0),
        })
    circle_sketch = target_doc.getObject("FinishOrder_RecoveredRearMountReinforcementPadProfile")
    if not circle_sketch.FullyConstrained or circle_sketch.GeometryCount != 6:
        raise RuntimeError("Recovered six-circle reinforcement sketch is not fully constrained")

    source_doc = App.openDocument(str(MONOLITH))
    try:
        screw_tool = source_doc.getObject("RearTaperedSeats").Shape.cut(
            source_doc.getObject("Pocket018").Shape
        )
        screw_common = body.Shape.common(screw_tool)
        result["component"]["m2_passage_clearance"] = {
            "tool_definition": "RearTaperedSeats.Shape cut Pocket018.Shape",
            "tool_valid": bool(screw_tool.isValid()),
            "tool_solid_count": len(screw_tool.Solids),
            "common_valid": bool(screw_common.isValid()),
            "common_volume_mm3": screw_common.Volume,
            "result": "zero material intersection with six M2 clearance volumes" if screw_common.Volume <= 1e-7 else "interference remains",
        }
        if not screw_tool.isValid() or screw_common.Volume > 1e-7:
            raise RuntimeError("New component intrudes into the six M2 clearance volumes")
    finally:
        close_doc(source_doc)

    baseline_volume = body.Shape.Volume
    baseline_assembly_volume = root.Shape.Volume
    original_length = reinforcement.Length.Value
    reinforcement.Length = original_length + 0.1
    target_doc.recompute()
    new_assembly.recompute()
    probe_volume = body.Shape.Volume
    probe_assembly_volume = root.Shape.Volume
    reinforcement.Length = original_length
    target_doc.recompute()
    new_assembly.recompute()
    restored_volume = body.Shape.Volume
    restored_assembly_volume = root.Shape.Volume
    result["component"]["linked_parameter_probe"] = {
        "feature": reinforcement.Name,
        "values_mm": [original_length, original_length + 0.1, original_length],
        "component_delta_mm3": probe_volume - baseline_volume,
        "assembly_delta_mm3": probe_assembly_volume - baseline_assembly_volume,
        "component_restoration_delta_mm3": restored_volume - baseline_volume,
        "assembly_restoration_delta_mm3": restored_assembly_volume - baseline_assembly_volume,
        "scope": "reversible native geometry propagation through the App::Link; volume evidence, not exact BRep equivalence",
    }
    if abs(restored_volume - baseline_volume) > 1e-6 or abs(restored_assembly_volume - baseline_assembly_volume) > 1e-6:
        raise RuntimeError("Reversible linked feature probe failed to restore baseline volumes")

    result["assembly"] = {
        "root": root.Name,
        "valid": bool(root.Shape.isValid()),
        "solid_count": len(root.Shape.Solids),
        "link_count": sum(obj.TypeId == "App::Link" for obj in new_assembly.Objects),
        "all_links_valid": all(obj.Shape.isValid() for obj in new_assembly.Objects if obj.TypeId == "App::Link"),
        "rear_link_target": target.Name,
        "rear_link_placement": str(rear_link.LinkPlacement),
        "rear_link_valid": bool(rear_link.Shape.isValid()),
        "rear_link_volume_mm3": rear_link.Shape.Volume,
    }
    if not root.Shape.isValid() or len(root.Shape.Solids) != 11:
        raise RuntimeError("Review assembly root invalid or unexpected solid count")

    old_rows = rear_intersections(old_assembly, "Interim_Body002")
    new_rows = rear_intersections(new_assembly, "Interim_Body002")
    new_by_name = {row["neighbor"]: row for row in new_rows}
    comparisons = []
    for old in old_rows:
        new = new_by_name[old["neighbor"]]
        delta = new["common_volume_mm3"] - old["common_volume_mm3"]
        comparisons.append({
            "neighbor": old["neighbor"],
            "old_common_mm3": old["common_volume_mm3"],
            "new_common_mm3": new["common_volume_mm3"],
            "delta_mm3": delta,
            "both_valid": old["common_valid"] and new["common_valid"],
        })
        if not old["common_valid"] or not new["common_valid"] or abs(delta) > 1e-6:
            raise RuntimeError("Assembly interaction changed or Boolean invalid for %s" % old["neighbor"])
    result["assembly"]["rear_neighbor_intersection_comparison"] = comparisons
    result["assembly"]["known_usb_cover_engagement_mm3"] = new_by_name["Editable_Body_USBTetheredCover"]["common_volume_mm3"]
finally:
    close_doc(new_assembly)
    close_doc(old_assembly)

result["material_localization"] = {
    "legacy_net_brep_delta_mm3": 475.701580,
    "previous_0p5mm_sampled_net_mm3": 262.875,
    "regions_net_mm3": {
        "upper_left": 42.750,
        "upper_right": 40.625,
        "lower_left": 90.625,
        "lower_right": 88.875,
    },
    "interpretation": "Sampling localizes likely boss-to-wall reinforcement but does not spatially account for the full BRep delta. No material is classified as redundant by this test.",
}
result["geometry_scope"] = {
    "candidate_minus_saved_legacy_tip_mm3": result["component"]["tip_shape"]["volume_mm3"] - result["protected_saved_baseline"]["legacy_tip"]["volume_mm3"],
    "candidate_minus_clean_base_mm3": result["component"]["tip_shape"]["volume_mm3"] - result["protected_saved_baseline"]["clean_base"]["volume_mm3"],
    "exact_brep_equivalence_proven": False,
    "structural_capacity_proven": False,
    "production_files_modified": False,
}

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
