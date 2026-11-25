"""Validate the base-preserving rear-shell support/finish-order candidate.

The saved monolith is read without recompute or save. The review assembly is
cold-opened and recomputed, its rear App::Link is probed reversibly, and its
rear-neighbor intersections are compared with the previous review assembly.
"""
import json
from pathlib import Path

import FreeCAD as App
import MeshPart


ROOT = Path(__file__).resolve().parents[3]
MONOLITH = ROOT / "hardware/freecad/pendant.FCStd"
OLD_ASSEMBLY = ROOT / "hardware/freecad/pendant-modular-recovered-screw-pad-review-assembly-2026-10-31.FCStd"
ASSEMBLY = ROOT / "hardware/freecad/pendant-modular-structural-first-fillet-no-duplicate-review-assembly-2026-10-31.FCStd"
COMPONENT = ROOT / "hardware/freecad/pendant-bodies/rear-shell-structural-first-fillet-no-duplicate-pad-2026-10-31.FCStd"
OUTPUT = ROOT / "hardware/freecad/reports/rear-shell-structural-first-fillet-base-preserving-validation-2026-10-31.json"


def close_doc(doc):
    if doc and App.getDocument(doc.Name):
        App.closeDocument(doc.Name)


def shape_metrics(shape):
    box = shape.BoundBox
    return {
        "valid": bool(shape.isValid()),
        "solid_count": len(shape.Solids),
        "volume_mm3": shape.Volume,
        "area_mm2": shape.Area,
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


def rear_intersections(doc):
    rear = doc.getObject("Interim_Body002")
    neighbors = (
        "Interim_Body", "Interim_Body003", "Interim_EncoderFaceplatePocketUnsplit",
        "Editable_Body_DisplayRetainer_EditableV2", "Editable_Body_USBTetheredCover",
        "Editable_Body_FaceplateLocator_A", "Editable_Body_FaceplateLocator_B",
        "Editable_Body006", "Review_AntiSlipPadUpper", "Review_AntiSlipPadLower",
    )
    rows = []
    for name in neighbors:
        other = doc.getObject(name)
        if not other or not hasattr(other, "Shape") or other.Shape.isNull():
            continue
        common = rear.Shape.common(other.Shape)
        rows.append({
            "neighbor": name,
            "common_valid": bool(common.isValid()),
            "common_volume_mm3": common.Volume,
            "common_solid_count": len(common.Solids),
        })
    return rows


def dependency_ancestry(tip):
    seen = set()

    def walk(obj):
        if obj.Name in seen:
            return
        seen.add(obj.Name)
        for dependency in obj.OutList:
            if hasattr(dependency, "Name"):
                walk(dependency)

    walk(tip)
    return sorted(seen)


result = {
    "date": "2026-10-31",
    "status": "base-preserving disposable redesign candidate; not production-approved",
    "files": {
        "protected_monolith": str(MONOLITH.relative_to(ROOT)),
        "component": str(COMPONENT.relative_to(ROOT)),
        "review_assembly": str(ASSEMBLY.relative_to(ROOT)),
    },
    "validator_saves_documents": False,
}

monolith = App.openDocument(str(MONOLITH))
try:
    active_tip = monolith.getObject("RearBossWallRamps45")
    base = monolith.getObject("Body002FullWidthSeat")
    legacy = active_tip
    original_pad = monolith.getObject("RearMountReinforcement")
    original_pad_base = original_pad.BaseFeature
    ancestry = dependency_ancestry(active_tip)
    result["protected_saved_source"] = {
        "recomputed": False,
        "active_tip": active_tip.Name,
        "active_tip_metrics": shape_metrics(active_tip.Shape),
        "active_tip_mesh": mesh_metrics(active_tip.Shape),
        "clean_base": shape_metrics(base.Shape),
        "legacy_net_stage_delta_mm3": active_tip.Shape.Volume - base.Shape.Volume,
        "legacy_stage_deltas_mm3": {
            "RearBossToWallLoadPaths": 383.733575,
            "RearBossShoulderTransitions": -14.961450,
            "RearBossWallRamps45": 106.929454,
        },
        "original_rear_mount_pad": {
            "name": original_pad.Name,
            "label": original_pad.Label,
            "base_feature": original_pad_base.Name if original_pad_base else None,
            "shape": shape_metrics(original_pad.Shape),
            "base_shape": shape_metrics(original_pad_base.Shape) if original_pad_base else None,
            "in_active_tip_dependency_ancestry": original_pad.Name in ancestry,
        },
        "rear_mount_pad_is_upstream_of_clean_base": original_pad.Name in dependency_ancestry(base),
        "active_ancestry_contains": [
            name for name in ("RearMountReinforcement", "RemoveWarpProneTongues", "SmallHangerPocketBody002")
            if name in ancestry
        ],
        "interpretation": "The source six-circle Pad already occurs upstream of the protected active Tip and clean base. The review candidate imports the downstream clean-base shape and therefore does not append that Pad again.",
    }
finally:
    close_doc(monolith)

old_assembly = App.openDocument(str(OLD_ASSEMBLY))
old_assembly.recompute()
assembly = App.openDocument(str(ASSEMBLY))
assembly.recompute()
try:
    root = assembly.getObject("AssemblyRoot")
    rear_link = assembly.getObject("Interim_Body002")
    body = rear_link.LinkedObject
    body_doc = body.Document
    if body.Name != "RearShellStructuralFirstNoDuplicatePad":
        raise RuntimeError("Rear link resolves to unexpected target %s" % body.Name)
    tip = body.Tip
    pre_fillet = body_doc.getObject("FinishOrder_LowerRightInnerWebPad")
    fillet = body_doc.getObject("StructuralFirstBottomPerimeterFinish")
    seat = body_doc.getObject("FinishOrder_AntiSlipSeatPocket")
    upper_pad = body_doc.getObject("FinishOrder_UpperLeftSupportPad")
    if not (root and tip and pre_fillet and fillet and seat and upper_pad):
        raise RuntimeError("Review model lacks a required feature")

    result["candidate"] = {
        "linked_document_path": body_doc.FileName,
        "body": body.Name,
        "tip": tip.Name,
        "tip_state": list(tip.State),
        "tip_shape": shape_metrics(tip.Shape),
        "tip_mesh": mesh_metrics(tip.Shape),
        "base_shape": shape_metrics(body_doc.getObject("CleanRearShellBase").Shape),
        "base_shape_matches_saved_clean_base_metrics": {
            "volume_delta_mm3": body_doc.getObject("CleanRearShellBase").Shape.Volume - result["protected_saved_source"]["clean_base"]["volume_mm3"],
            "area_delta_mm2": body_doc.getObject("CleanRearShellBase").Shape.Area - result["protected_saved_source"]["clean_base"]["area_mm2"],
            "face_count_equal": len(body_doc.getObject("CleanRearShellBase").Shape.Faces) == result["protected_saved_source"]["clean_base"]["face_count"],
        },
        "feature_order": [
            "4 native boss-to-wall support Pads",
            "six M2 passage Pocket",
            "2 native lower inner-web Pads",
            "R0.25 mm bottom-perimeter Fillet",
            "0.10 mm crescent-seat Pocket",
        ],
        "fillet": {
            "radius_mm": fillet.Radius.Value,
            "base_feature": fillet.Base[0].Name,
            "selected_edge_count": len(fillet.Base[1]),
            "selected_edges": list(fillet.Base[1]),
            "pre_fillet_volume_mm3": pre_fillet.Shape.Volume,
            "post_fillet_volume_mm3": fillet.Shape.Volume,
            "removed_volume_mm3": pre_fillet.Shape.Volume - fillet.Shape.Volume,
            "source_face_area_mm2": 4243.2288642514,
            "source_face_normal": [0.0, -0.0436193874, -0.9990482216],
        },
        "seat_pocket": {
            "depth_mm": seat.Length.Value,
            "base_feature": seat.BaseFeature.Name,
            "volume_removed_mm3": fillet.Shape.Volume - seat.Shape.Volume,
        },
        "sketches": [],
    }
    if not tip.Shape.isValid() or len(tip.Shape.Solids) != 1:
        raise RuntimeError("Final rear Tip is not one valid solid")
    mesh_result = result["candidate"]["tip_mesh"]
    if not mesh_result["reports_solid"] or mesh_result["boundary_edges"] or mesh_result["overincident_edges"] or mesh_result["degenerate_facets"]:
        raise RuntimeError("Final rear Tip mesh is not closed/manifold")
    if fillet.Radius.Value != 0.25 or len(fillet.Base[1]) != 19:
        raise RuntimeError("Unexpected bottom fillet radius or edge count")

    for name in (
        "FinishOrder_UpperLeftSupportPadProfile", "FinishOrder_UpperRightSupportPadProfile",
        "FinishOrder_LowerLeftSupportPadProfile", "FinishOrder_LowerRightSupportPadProfile",
        "FinishOrder_LowerLeftInnerWebPadProfile", "FinishOrder_LowerRightInnerWebPadProfile",
    ):
        sketch = body_doc.getObject(name)
        result["candidate"]["sketches"].append({
            "name": name,
            "geometry_count": sketch.GeometryCount,
            "constraint_count": len(sketch.Constraints),
            "fully_constrained": bool(sketch.FullyConstrained),
            "external_geometry_count": getattr(sketch, "ExternalGeometryCount", 0),
        })

    source_doc = App.openDocument(str(MONOLITH))
    try:
        clearance_tools = {
            "six_m2_passages": source_doc.getObject("RearTaperedSeats").Shape.cut(source_doc.getObject("Pocket018").Shape),
            "magnet_slots": source_doc.getObject("Pad019").Shape.cut(source_doc.getObject("Pocket015").Shape),
        }
        result["candidate"]["keepout_checks"] = {}
        for name, tool in clearance_tools.items():
            common = tip.Shape.common(tool)
            result["candidate"]["keepout_checks"][name] = {
                "tool_valid": bool(tool.isValid()),
                "tool_solid_count": len(tool.Solids),
                "common_valid": bool(common.isValid()),
                "common_volume_mm3": common.Volume,
            }
            if not tool.isValid() or not common.isValid() or common.Volume > 1e-7:
                raise RuntimeError("Candidate intersects keepout: %s" % name)
    finally:
        close_doc(source_doc)

    baseline_component_volume = body.Shape.Volume
    baseline_assembly_volume = root.Shape.Volume
    original_length = upper_pad.Length.Value
    upper_pad.Length = original_length + 0.1
    body_doc.recompute()
    assembly.recompute()
    edited_component_volume = body.Shape.Volume
    edited_assembly_volume = root.Shape.Volume
    upper_pad.Length = original_length
    body_doc.recompute()
    assembly.recompute()
    result["candidate"]["linked_reversible_probe"] = {
        "feature": upper_pad.Name,
        "values_mm": [original_length, original_length + 0.1, original_length],
        "component_delta_mm3": edited_component_volume - baseline_component_volume,
        "assembly_delta_mm3": edited_assembly_volume - baseline_assembly_volume,
        "component_restoration_delta_mm3": body.Shape.Volume - baseline_component_volume,
        "assembly_restoration_delta_mm3": root.Shape.Volume - baseline_assembly_volume,
        "scope": "native parameter propagation through linked assembly; volume comparison only",
    }
    if abs(body.Shape.Volume - baseline_component_volume) > 1e-6 or abs(root.Shape.Volume - baseline_assembly_volume) > 1e-6:
        raise RuntimeError("Reversible linked Pad probe did not restore baseline volume")

    result["assembly"] = {
        "root": root.Name,
        "valid": bool(root.Shape.isValid()),
        "solid_count": len(root.Shape.Solids),
        "link_count": sum(obj.TypeId == "App::Link" for obj in assembly.Objects),
        "all_links_valid": all(obj.Shape.isValid() for obj in assembly.Objects if obj.TypeId == "App::Link"),
        "rear_link_valid": bool(rear_link.Shape.isValid()),
        "rear_link_placement": str(rear_link.LinkPlacement),
    }
    if not root.Shape.isValid() or len(root.Shape.Solids) != 11:
        raise RuntimeError("Review assembly root failed")

    old_rows = rear_intersections(old_assembly)
    new_rows = rear_intersections(assembly)
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
            raise RuntimeError("Neighbor intersection changed for %s" % old["neighbor"])
    result["assembly"]["rear_neighbor_intersection_comparison"] = comparisons
finally:
    close_doc(assembly)
    close_doc(old_assembly)

result["geometry_scope"] = {
    "candidate_minus_saved_legacy_tip_mm3": result["candidate"]["tip_shape"]["volume_mm3"] - result["protected_saved_source"]["active_tip_metrics"]["volume_mm3"],
    "candidate_minus_clean_base_mm3": result["candidate"]["tip_shape"]["volume_mm3"] - result["protected_saved_source"]["clean_base"]["volume_mm3"],
    "exact_brep_equivalence_proven": False,
    "structural_capacity_proven": False,
    "production_files_modified": False,
}
result["material_localization"] = {
    "legacy_net_brep_delta_mm3": result["protected_saved_source"]["legacy_net_stage_delta_mm3"],
    "approximate_0p5mm_sampled_net_mm3": 262.875,
    "regions_net_mm3": {"upper_left": 42.750, "upper_right": 40.625, "lower_left": 90.625, "lower_right": 88.875},
    "interpretation": "The sample locates likely structural support around screw bosses but does not account exactly for the full legacy BRep delta. No legacy material is classified as redundant.",
}

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
