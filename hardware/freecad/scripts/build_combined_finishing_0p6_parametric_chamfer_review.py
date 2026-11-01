"""Integrate the parameterized native upper-boss chamfer into the 0.60 mm pad review.

The builder copies a disposable review assembly, replaces only its rear-shell
link, and preserves all source placements. It does not write the source assembly,
the protected monolith, or either source component document.
"""
import json
import math
import shutil
from pathlib import Path

import FreeCAD as App
import MeshPart
import Part


ROOT = Path(__file__).resolve().parents[3]
ASSEMBLY_SOURCE = ROOT / "hardware/freecad/master-driven-leadins-candidate/pendant-modular-combined-finishing-0p6-crescents-review-2026-11-01.FCStd"
REAR_SOURCE = ROOT / "hardware/freecad/pendant-bodies/rear-shell-parametric-shoulder-chamfer-review-2026-11-01.FCStd"
MONOLITH_SOURCE = ROOT / "hardware/freecad/pendant.FCStd"
OUTPUT = ROOT / "hardware/freecad/master-driven-leadins-candidate/pendant-modular-combined-finishing-0p6-parametric-chamfer-review-2026-11-01.FCStd"
REPORT_JSON = ROOT / "hardware/freecad/reports/combined-finishing-0p6-parametric-chamfer-review-2026-11-01.json"
REPORT_MD = ROOT / "hardware/freecad/reports/combined-finishing-0p6-parametric-chamfer-review-2026-11-01.md"


def close(doc):
    if doc is not None and App.getDocument(doc.Name):
        App.closeDocument(doc.Name)


def summary(shape):
    bb = shape.BoundBox
    return {"valid": bool(not shape.isNull() and shape.isValid()),
            "solid_count": len(shape.Solids), "volume_mm3": shape.Volume,
            "area_mm2": shape.Area, "face_count": len(shape.Faces),
            "bounds_mm": [bb.XMin, bb.XMax, bb.YMin, bb.YMax,
                          bb.ZMin, bb.ZMax]}


def mesh_audit(shape):
    mesh = MeshPart.meshFromShape(Shape=shape.copy(), LinearDeflection=0.08,
                                  AngularDeflection=0.35, Relative=False)
    incidence = {}
    degenerate = 0
    for facet in mesh.Facets:
        points = [tuple(round(float(v), 6) for v in p) for p in facet.Points]
        degenerate += facet.Area < 1e-12
        for a, b in ((0, 1), (1, 2), (2, 0)):
            edge = tuple(sorted((points[a], points[b])))
            incidence[edge] = incidence.get(edge, 0) + 1
    return {"closed": bool(mesh.isSolid()), "facets": len(mesh.Facets),
            "boundary_edges": sum(v == 1 for v in incidence.values()),
            "overincident_edges": sum(v > 2 for v in incidence.values()),
            "degenerate_facets": degenerate}


def contact_plane(body):
    planes = []
    for index, face in enumerate(body.Shape.Faces, 1):
        if "Plane" not in str(type(face.Surface)):
            continue
        normal = face.Surface.Axis
        normal.normalize()
        center = face.CenterOfMass
        planes.append({"face": index, "area_mm2": face.Area,
                       "normal": [normal.x, normal.y, normal.z],
                       "constant_mm": normal.dot(center),
                       "center_mm": [center.x, center.y, center.z]})
    if not planes:
        raise RuntimeError("A crescent pad has no planar contact face")
    return min(planes, key=lambda p: p["center_mm"][2])


for path in (ASSEMBLY_SOURCE, REAR_SOURCE, MONOLITH_SOURCE):
    if not path.is_file():
        raise FileNotFoundError(path)
for path in (OUTPUT, REPORT_JSON, REPORT_MD):
    if path.exists():
        raise FileExistsError("Refusing to overwrite review artifact: " + str(path))

shutil.copy2(ASSEMBLY_SOURCE, OUTPUT)
assembly = App.openDocument(str(OUTPUT))
rear_doc = monolith = None
try:
    assembly.recompute()
    root = assembly.getObject("AssemblyRoot")
    rear_link = assembly.getObject("Interim_Body002")
    upper_pad_link = assembly.getObject("Review_AntiSlipPadUpper")
    lower_pad_link = assembly.getObject("Review_AntiSlipPadLower")
    if not all((root, rear_link, upper_pad_link, lower_pad_link)):
        raise RuntimeError("Combined 0.60 mm review is missing expected links")
    original_placement = rear_link.LinkPlacement
    source_rear_shape = rear_link.Shape.copy()

    rear_doc = App.openDocument(str(REAR_SOURCE))
    rear_doc.recompute()
    rear_body = rear_doc.getObject("RearShellStructuralFirstNoDuplicatePad")
    chamfer = rear_doc.getObject("NativeUpperBossShoulderChamfer")
    bottom_fillet = rear_doc.getObject("StructuralFirstBottomPerimeterFinish")
    if not all((rear_body, rear_body.Tip, chamfer, bottom_fillet)):
        raise RuntimeError("Rear chamfer candidate is missing a required feature")
    if rear_body.Tip != chamfer or abs(bottom_fillet.Radius.Value - 0.25) > 1e-8:
        raise RuntimeError("Rear candidate does not end at the expected chamfer after R0.25 fillet")
    if abs(chamfer.Size.Value - 1.0) > 1e-8:
        raise RuntimeError("Expected a native 1.0 mm upper-boss shoulder chamfer")
    parameter_sheet = rear_doc.getObject("StructuralSupportParameters")
    chamfer_cell = parameter_sheet.getCellFromAlias("UpperBossShoulderChamferSize")
    chamfer_expression = dict(chamfer.ExpressionEngine).get("Size")
    if (chamfer_cell != "B23"
            or chamfer_expression != "StructuralSupportParameters.UpperBossShoulderChamferSize"):
        raise RuntimeError("The named shoulder-chamfer parameter/expression is missing")
    if not rear_body.Shape.isValid() or len(rear_body.Shape.Solids) != 1:
        raise RuntimeError("Chamfered rear-shell Body is not one valid solid")

    rear_link.LinkedObject = rear_body
    rear_link.LinkPlacement = original_placement
    rear_link.Label = "Review — rear shell with R0.25 bottom fillet and R1.0 boss chamfers"
    assembly.recompute()
    if not root.Shape.isValid() or len(root.Shape.Solids) != 11:
        raise RuntimeError("Combined review root is not a valid 11-solid assembly")
    if rear_link.LinkPlacement != original_placement:
        raise RuntimeError("Replacing the rear link changed its assembly placement")

    before = summary(source_rear_shape)
    after = summary(rear_link.Shape)
    mesh = mesh_audit(rear_link.Shape)
    if (not after["valid"] or after["solid_count"] != 1 or not mesh["closed"]
            or mesh["boundary_edges"] or mesh["overincident_edges"]
            or mesh["degenerate_facets"]):
        raise RuntimeError("Chamfered rear shell failed the one-solid/manifold mesh check")

    # Six 2.00 mm shank gauges must pass through the six Ø2.30 mm passages.
    m2_profile = rear_doc.getObject("FinishOrder_M2PassagesProfile")
    circles = [g for g in m2_profile.Geometry if hasattr(g, "Radius")]
    if len(circles) != 6 or any(abs(g.Radius - 1.15) > 1e-8 for g in circles):
        raise RuntimeError("Expected six constrained Ø2.30 mm M2 passage circles")
    bbox = rear_link.Shape.BoundBox
    shank_checks = []
    for index, circle in enumerate(circles):
        center = m2_profile.Placement.multVec(circle.Center)
        gauge = Part.makeCylinder(1.0, bbox.ZLength + 10.0,
                                  App.Vector(center.x, center.y, bbox.ZMin - 5.0),
                                  App.Vector(0, 0, 1))
        common = rear_link.Shape.common(gauge)
        if not common.isValid() or common.Volume > 1e-7:
            raise RuntimeError("Chamfer interferes with M2 shank gauge %d" % index)
        shank_checks.append({"index": index, "center_mm": [center.x, center.y],
                             "intersection_mm3": common.Volume})

    # Pad/shank and contact-plane checks apply to the final linked assembly.
    pad_stats = {}
    for link in (upper_pad_link, lower_pad_link):
        shape = link.Shape
        if shape.isNull() or not shape.isValid() or len(shape.Solids) != 1:
            raise RuntimeError("Invalid crescent pad link: " + link.Name)
        common = rear_link.Shape.common(shape)
        if not common.isValid() or common.Volume > 1e-7:
            raise RuntimeError("Crescent pad intersects the chamfered rear shell")
        pad_stats[link.Name] = {"shape": summary(shape),
                                "rear_shell_intersection_mm3": common.Volume,
                                "contact_plane": contact_plane(link.LinkedObject)}
    a = pad_stats["Review_AntiSlipPadUpper"]["contact_plane"]
    b = pad_stats["Review_AntiSlipPadLower"]["contact_plane"]
    dot = sum(x * y for x, y in zip(a["normal"], b["normal"]))
    contact_angle = math.degrees(math.acos(max(-1.0, min(1.0, abs(dot)))))
    contact_offset = abs(a["constant_mm"] - b["constant_mm"])
    if contact_angle > 0.1 or contact_offset > 0.01:
        raise RuntimeError("Upper/lower crescent contact planes are not coplanar")

    # Compare inherited magnet regions before and after the chamfer.
    monolith = App.openDocument(str(MONOLITH_SOURCE))
    upper_tool = monolith.getObject("Pad007").Shape.cut(monolith.getObject("Pocket").Shape)
    lower_tool = monolith.getObject("Pad019").Shape.cut(monolith.getObject("Pocket015").Shape)
    magnet_checks = {}
    for label, tool in (("upper", upper_tool), ("slot", lower_tool)):
        before_common = source_rear_shape.common(tool)
        after_common = rear_link.Shape.common(tool)
        if not before_common.isValid() or not after_common.isValid():
            raise RuntimeError("Invalid %s magnet clearance comparison" % label)
        magnet_checks[label] = {"before_mm3": before_common.Volume,
                                "after_mm3": after_common.Volume,
                                "delta_mm3": after_common.Volume - before_common.Volume}
        if abs(magnet_checks[label]["delta_mm3"]) > 1e-6:
            raise RuntimeError("Shoulder chamfer changed %s magnet clearance" % label)

    # Preserve the known 0.780472 mm³ USB press-fit engagement and reject new clashes.
    neighbor_intersections = []
    for obj in assembly.Objects:
        if obj in (rear_link, upper_pad_link, lower_pad_link) or not hasattr(obj, "Shape"):
            continue
        if obj.TypeId not in ("App::Link", "Part::Feature") or obj.Shape.isNull():
            continue
        common = rear_link.Shape.common(obj.Shape)
        if not common.isValid():
            raise RuntimeError("Invalid rear-shell intersection against " + obj.Name)
        volume = common.Volume
        neighbor_intersections.append({"object": obj.Name, "volume_mm3": volume})
        allowed = 0.80 if obj.Name == "Editable_Body_USBTetheredCover" else 1e-4
        if volume > allowed:
            raise RuntimeError("Unexpected rear-shell clash with %s: %.9g mm3" % (obj.Name, volume))

    # Test the lower-web parameter through the chamfered native source and link.
    sheet = rear_doc.getObject("StructuralSupportParameters")
    cell = sheet.getCellFromAlias("LowerWebP2XAbs")
    base_volume = rear_link.Shape.Volume
    sheet.set(cell, "10.0")
    rear_doc.recompute()
    assembly.recompute()
    changed_volume = rear_link.Shape.Volume
    if abs(changed_volume - base_volume) < 1e-4:
        raise RuntimeError("Rear parameter did not propagate through chamfer and live link")
    sheet.set(cell, "9.9")
    rear_doc.recompute()
    assembly.recompute()
    restored_volume = rear_link.Shape.Volume
    if abs(restored_volume - base_volume) > 1e-7:
        raise RuntimeError("Restoring rear parameter did not recover baseline geometry")

    base_chamfer_summary = summary(rear_link.Shape)
    base_root_volume = root.Shape.Volume
    parameter_sheet.set(chamfer_cell, "0.8 mm")
    rear_doc.recompute()
    assembly.recompute()
    changed_chamfer_summary = summary(rear_link.Shape)
    changed_root_volume = root.Shape.Volume
    changed_chamfer_mesh = mesh_audit(rear_link.Shape)
    if (not changed_chamfer_summary["valid"]
            or changed_chamfer_summary["solid_count"] != 1
            or abs(changed_chamfer_summary["volume_mm3"] - base_chamfer_summary["volume_mm3"]) < 1e-4
            or abs(changed_root_volume - base_root_volume) < 1e-4
            or not changed_chamfer_mesh["closed"] or changed_chamfer_mesh["boundary_edges"]
            or changed_chamfer_mesh["overincident_edges"] or changed_chamfer_mesh["degenerate_facets"]):
        raise RuntimeError("0.8 mm shoulder chamfer did not propagate as a manifold one-solid link")
    parameter_sheet.set(chamfer_cell, "1.0 mm")
    rear_doc.recompute()
    assembly.recompute()
    restored_chamfer_summary = summary(rear_link.Shape)
    restored_root_volume = root.Shape.Volume
    if (abs(restored_chamfer_summary["volume_mm3"] - base_chamfer_summary["volume_mm3"]) > 1e-6
            or abs(restored_root_volume - base_root_volume) > 1e-6):
        raise RuntimeError("Restoring the shoulder chamfer did not recover the 1.0 mm baseline")

    links = [obj for obj in assembly.Objects if obj.TypeId == "App::Link"]
    static_interims = [obj.Name for obj in assembly.Objects
                       if obj.Name.startswith("Interim_") and obj.TypeId == "Part::Feature"]
    live_interims = [obj.Name for obj in assembly.Objects
                     if obj.Name.startswith("Interim_") and obj.TypeId == "App::Link"]
    if any(not obj.LinkedObject or obj.Shape.isNull() or not obj.Shape.isValid()
           for obj in links):
        raise RuntimeError("Combined assembly contains an unresolved link")
    assembly.recompute()
    assembly.save()
finally:
    close(assembly)
    close(rear_doc)
    close(monolith)

# Cold-open validation: all links resolve and the native rear source recomputes.
check = App.openDocument(str(OUTPUT))
try:
    check.recompute()
    root = check.getObject("AssemblyRoot")
    rear_link = check.getObject("Interim_Body002")
    links = [obj for obj in check.Objects if obj.TypeId == "App::Link"]
    if (root is None or not root.Shape.isValid() or len(root.Shape.Solids) != 11
            or rear_link is None or not rear_link.LinkedObject
            or any(not obj.LinkedObject or obj.Shape.isNull() or not obj.Shape.isValid()
                   for obj in links)):
        raise RuntimeError("Combined chamfer review failed cold-open link validation")
    cold_rear = summary(rear_link.Shape)
    cold_mesh = mesh_audit(rear_link.Shape)
    mesh_quality_keys = ("closed", "boundary_edges", "overincident_edges", "degenerate_facets")
    if (cold_rear != after
            or any(cold_mesh[k] != mesh[k] for k in mesh_quality_keys)):
        raise RuntimeError("Cold-open chamfered rear geometry or mesh quality differs from pre-save state")
    root_stats = summary(root.Shape)
    result = {
        "status": "disposable combined review; not production approved",
        "assembly": str(OUTPUT.relative_to(ROOT)),
        "source_assembly": str(ASSEMBLY_SOURCE.relative_to(ROOT)),
        "rear_component_source": str(REAR_SOURCE.relative_to(ROOT)),
        "live_link_count": len(links),
        "static_interim_components": static_interims,
        "interim_labelled_live_links": live_interims,
        "assembly_root_after_reopen": root_stats,
        "rear_shell": {"before_chamfer_source": before, "after_chamfer": cold_rear,
                       "mesh": cold_mesh, "placement_preserved": True},
        "native_finish": {"bottom_perimeter_fillet_radius_mm": 0.25,
                          "upper_boss_shoulder_chamfer_mm": 1.0,
                          "shoulder_chamfer_parameter": "StructuralSupportParameters.UpperBossShoulderChamferSize",
                          "chamfer_removed_material_mm3": before["volume_mm3"] - after["volume_mm3"]},
        "m2_shank_gauges": shank_checks,
        "magnet_clearance_comparison_mm3": magnet_checks,
        "crescent_pads": pad_stats,
        "crescent_contact_plane_angle_deg": contact_angle,
        "crescent_contact_plane_offset_mm": contact_offset,
        "rear_neighbor_intersections_mm3": neighbor_intersections,
        "reversible_lower_web_parameter_mm": {"baseline_volume_mm3": base_volume,
                                               "changed_volume_mm3": changed_volume,
                                               "restored_volume_mm3": restored_volume,
                                               "change": "9.9 -> 10.0 -> 9.9"},
        "reversible_shoulder_chamfer_parameter_mm": {
            "alias": "UpperBossShoulderChamferSize", "change": "1.0 -> 0.8 -> 1.0",
            "baseline": base_chamfer_summary, "edited": changed_chamfer_summary,
            "restored": restored_chamfer_summary, "edited_mesh": changed_chamfer_mesh,
            "assembly_root_volume_baseline_mm3": base_root_volume,
            "assembly_root_volume_edited_mm3": changed_root_volume,
            "assembly_root_volume_restored_mm3": restored_root_volume},
        "save_close_reopen_recompute": "passed",
        "protected_monolith_and_production_assembly_modified": False,
        "limitations": [
            "Rear shell remains a hybrid review Body with a stored-shape base.",
            "Legacy 475.701580 mm3 stage difference is not a spatial material map.",
            "No PLA strength rating or 5x complete-pendant proof-load claim is established.",
        ],
    }
    REPORT_JSON.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    REPORT_MD.write_text("""# Combined 0.60 mm crescent and rear shoulder-finish review

Status: **validated disposable assembly; not production approved.**

The assembly combines the live R0.50 mm display-bezel component, the fresh-fuse rear shell with its R0.25 mm bottom-perimeter fillet and native R1.0 mm upper-boss shoulder chamfers driven by `UpperBossShoulderChamferSize`, and separate 0.60 mm-proud upper/lower crescent pads. The corrected crescent source labels match the measured geometry. The protected monolith and production assembly remain unchanged.

## Embedded visual context

The assembly views document component arrangement. The underside planform image documents the crescent footprints; the chamfers are small local transitions around the upper screw-boss shoulders and should be inspected in the linked FreeCAD component.

![0.60 mm crescent-pad underside planform](images/rear-shell-anti-slip-variant-c-bottom.png)

![Combined finishing assembly underside arrangement](images/combined-finishing-review-2026-11-01/assembly-bottom.png)

![Rear-shell underside with support webs, bottom fillet, and anti-slip seats](images/rear-shell-fresh-fuse-structural-review-bottom-2026-11-01.png)

![Context view of the shoulder and crescent review candidate](images/rear-shell-crescent-tpu-pads-review-2026-10-31.png)

## Validation

The assembly was recomputed, saved, closed, reopened, and recomputed. All live links resolve. The rear shell remains one valid solid; its 0.08 mm mesh is closed with zero boundary, over-incident, or degenerate edges. The six 2.00 mm shank gauges pass through the modeled 2.30 mm passages. The 1.0 mm chamfers change the two upper-boss shoulder arcs without changing the inherited magnet-clearance intersection. Both crescent pads remain separate one-solid components with coplanar contact faces and zero shell intersection. The rear parameter `LowerWebP2XAbs` propagated through the chamfered PartDesign chain and live link at 10.0 mm, then restored the 9.9 mm baseline. The new `UpperBossShoulderChamferSize` alias also propagated 1.0→0.8→1.0 mm through the live link; both sizes produced a valid one-solid shell and closed mesh, and the baseline volume returned within 1×10⁻⁶ mm³.

This combined assembly is a review model. The rear shell still has a stored-shape base, and the legacy 475.701580 mm³ stage delta remains spatially unresolved. No structural equivalence, PLA load rating, or 5× proof-load capacity is claimed. Measurements and the exact retained interim representation list are in the [JSON validation](combined-finishing-0p6-shoulder-chamfer-review-2026-11-01.json).

## Files

- [Combined review assembly](../master-driven-leadins-candidate/pendant-modular-combined-finishing-0p6-shoulder-chamfer-review-2026-11-01.FCStd)
- [Rear component with editable chamfer parameter](../pendant-bodies/rear-shell-parametric-shoulder-chamfer-review-2026-11-01.FCStd)
- [Reusable builder and validator](../scripts/build_combined_finishing_0p6_parametric_chamfer_review.py)
- [JSON results](combined-finishing-0p6-shoulder-chamfer-review-2026-11-01.json)
""", encoding="utf-8")
    print(json.dumps(result, indent=2))
finally:
    close(check)
