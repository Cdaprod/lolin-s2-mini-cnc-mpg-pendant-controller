"""Combine validated rear-shell finishing and R0.50 bezel candidates.

The script writes only new review artifacts. It reads the source assembly,
rear-shell candidate, and anti-slip components without saving those documents.
Run from FreeCAD's Python runtime or freecadcmd.
"""
import json
import math
import shutil
from pathlib import Path

import FreeCAD as App
import MeshPart


ROOT = Path(__file__).resolve().parents[3]
ASSEMBLY_SOURCE = ROOT / "hardware/freecad/master-driven-leadins-candidate/pendant-modular-assembly-bezel-r0p50-review.FCStd"
REAR_SOURCE = ROOT / "hardware/freecad/pendant-bodies/rear-shell-fresh-fuse-structural-review-2026-11-01.FCStd"
PAD_SOURCE = ROOT / "hardware/freecad/pendant-bodies/rear-shell-anti-slip-crescent-pads-parametric-review-2026-10-31.FCStd"
OUTPUT = ROOT / "hardware/freecad/master-driven-leadins-candidate/pendant-modular-combined-finishing-review-2026-11-01.FCStd"
REPORT_JSON = ROOT / "hardware/freecad/reports/combined-finishing-review-2026-11-01.json"
REPORT_MD = ROOT / "hardware/freecad/reports/combined-finishing-review-2026-11-01.md"


def summary(shape):
    bb = shape.BoundBox
    return {
        "valid": bool(not shape.isNull() and shape.isValid()),
        "solid_count": len(shape.Solids),
        "volume_mm3": shape.Volume,
        "area_mm2": shape.Area,
        "faces": len(shape.Faces),
        "bounds_mm": [bb.XMin, bb.XMax, bb.YMin, bb.YMax,
                      bb.ZMin, bb.ZMax],
    }


def manifold(shape):
    mesh = MeshPart.meshFromShape(Shape=shape.copy(), LinearDeflection=0.08,
                                  AngularDeflection=0.35, Relative=False)
    incidence = {}
    degenerate = 0
    for facet in mesh.Facets:
        points = [tuple(round(float(value), 6) for value in point)
                  for point in facet.Points]
        degenerate += facet.Area < 1e-12
        for a, b in ((0, 1), (1, 2), (2, 0)):
            key = tuple(sorted((points[a], points[b])))
            incidence[key] = incidence.get(key, 0) + 1
    return {
        "closed": bool(mesh.isSolid()),
        "facets": len(mesh.Facets),
        "boundary_edges": sum(count == 1 for count in incidence.values()),
        "overincident_edges": sum(count > 2 for count in incidence.values()),
        "degenerate_facets": degenerate,
    }


def contact_plane(body):
    faces = []
    for index, face in enumerate(body.Shape.Faces, 1):
        if "Plane" not in str(type(face.Surface)):
            continue
        normal = face.Surface.Axis
        normal.normalize()
        center = face.CenterOfMass
        faces.append({
            "face": index,
            "area_mm2": face.Area,
            "normal": [normal.x, normal.y, normal.z],
            "center_mm": [center.x, center.y, center.z],
            "constant_mm": normal.dot(center),
        })
    if not faces:
        raise RuntimeError("Anti-slip pad has no planar face")
    return min(faces, key=lambda face: face["center_mm"][2])


def close(document):
    if document and App.getDocument(document.Name):
        App.closeDocument(document.Name)


for source_path in (ASSEMBLY_SOURCE, REAR_SOURCE, PAD_SOURCE):
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
for output_path in (OUTPUT, REPORT_JSON, REPORT_MD):
    if output_path.exists():
        raise FileExistsError("Refusing to overwrite review artifact: " + str(output_path))

shutil.copy2(ASSEMBLY_SOURCE, OUTPUT)
assembly = App.openDocument(str(OUTPUT))
rear_doc = None
pad_doc = None
try:
    assembly.recompute()
    root = assembly.getObject("AssemblyRoot")
    shell_group = assembly.getObject("ShellModule")
    other_group = assembly.getObject("OtherEditableComponents")
    shell_link = assembly.getObject("Interim_Body002")
    faceplate_link = assembly.getObject("Editable_UpperFaceplateBezel")
    if not all((root, shell_group, other_group, shell_link, faceplate_link)):
        raise RuntimeError("Expected assembly root, shell link, or live R0.50 bezel link is missing")

    source_shell_placement = shell_link.LinkPlacement
    source_faceplate = faceplate_link.LinkedObject
    if source_faceplate is None:
        raise RuntimeError("The R0.50 faceplate link is unresolved")

    rear_doc = App.openDocument(str(REAR_SOURCE))
    pad_doc = App.openDocument(str(PAD_SOURCE))
    rear_doc.recompute()
    pad_doc.recompute()
    rear_body = rear_doc.getObject("RearShellStructuralFirstNoDuplicatePad")
    upper_body = pad_doc.getObject("UpperCrescentAntiSlipPadBody")
    lower_body = pad_doc.getObject("LowerCrescentAntiSlipPadBody")
    if not all((rear_body, upper_body, lower_body)):
        raise RuntimeError("A rear-shell or anti-slip source Body is missing")
    if (not rear_body.Tip or not rear_body.Tip.Shape.isValid()
            or len(rear_body.Tip.Shape.Solids) != 1):
        raise RuntimeError("Fresh-fuse rear-shell native feature chain is invalid")

    pad_profile_stats = {}
    for name in ("UpperCrescentAntiSlipProfile", "LowerCrescentAntiSlipProfile"):
        profile = pad_doc.getObject(name)
        if profile is None or not profile.FullyConstrained:
            raise RuntimeError("Anti-slip profile is not fully constrained: " + name)
        pad_profile_stats[name] = {
            "fully_constrained": bool(profile.FullyConstrained),
            "constraint_count": profile.ConstraintCount,
        }

    shell_link.LinkedObject = rear_body
    shell_link.LinkPlacement = source_shell_placement
    shell_link.Label = "Review — fresh-fuse rear shell with native supports and R0.25 perimeter finish"

    pad_links = []
    for link_name, label, body in (
        ("Review_AntiSlipPadUpper", "Upper TPU crescent — review link", upper_body),
        ("Review_AntiSlipPadLower", "Lower TPU crescent — review link", lower_body),
    ):
        link = assembly.addObject("App::Link", link_name)
        link.Label = label
        link.LinkedObject = body
        link.LinkPlacement = App.Placement()
        other_group.addObject(link)
        pad_links.append(link)

    assembly.recompute()
    if not root.Shape.isValid():
        raise RuntimeError("Combined assembly root is invalid before save")
    if not faceplate_link.Shape.isValid() or len(faceplate_link.Shape.Solids) != 1:
        raise RuntimeError("R0.50 bezel link is not a valid single solid")
    if shell_link.LinkPlacement != source_shell_placement:
        raise RuntimeError("Replacing the rear link changed its assembly placement")

    rear_shape = shell_link.Shape.copy()
    rear_stats = summary(rear_shape)
    rear_mesh = manifold(rear_shape)
    if (not rear_stats["valid"] or rear_stats["solid_count"] != 1
            or not rear_mesh["closed"] or rear_mesh["boundary_edges"]
            or rear_mesh["overincident_edges"] or rear_mesh["degenerate_facets"]):
        raise RuntimeError("Fresh-fuse rear shell failed the manifold one-solid check")

    pad_stats = {}
    for link in pad_links:
        if not link.Shape.isValid() or len(link.Shape.Solids) != 1:
            raise RuntimeError("Invalid anti-slip link: " + link.Name)
        overlap = rear_shape.common(link.Shape)
        pad_stats[link.Name] = {
            "shape": summary(link.Shape),
            "rear_shell_overlap_mm3": overlap.Volume,
            "contact_plane": contact_plane(link.LinkedObject),
        }
        if not overlap.isValid() or overlap.Volume > 1e-7:
            raise RuntimeError("Anti-slip pad intersects the rear shell: " + link.Name)

    upper = pad_stats["Review_AntiSlipPadUpper"]["contact_plane"]
    lower = pad_stats["Review_AntiSlipPadLower"]["contact_plane"]
    dot = sum(a * b for a, b in zip(upper["normal"], lower["normal"]))
    angle = math.degrees(math.acos(max(-1.0, min(1.0, abs(dot)))))
    plane_offset = abs(upper["constant_mm"] - lower["constant_mm"])
    if angle > 0.1 or plane_offset > 0.01:
        raise RuntimeError("Upper and lower anti-slip contact planes do not match")

    # Retain known assembly contact at the USB cover; report all other
    # intersections so the combined review does not hide fit issues.
    intersections = []
    for neighbor in assembly.Objects:
        if neighbor in (shell_link, *pad_links) or not hasattr(neighbor, "Shape"):
            continue
        if neighbor.TypeId not in ("App::Link", "Part::Feature"):
            continue
        shape = neighbor.Shape
        if shape.isNull():
            continue
        common = rear_shape.common(shape)
        if not common.isValid():
            raise RuntimeError("Invalid rear-shell intersection result with " + neighbor.Name)
        volume = common.Volume
        intersections.append({"neighbor": neighbor.Name, "volume_mm3": volume})
        allowed = 0.80 if neighbor.Name == "Editable_Body_USBTetheredCover" else 1e-4
        if volume > allowed:
            raise RuntimeError("Unexpected rear-shell overlap with %s: %.9g mm3" %
                               (neighbor.Name, volume))

    links = [obj for obj in assembly.Objects if obj.TypeId == "App::Link"]
    static_interims = [obj.Name for obj in assembly.Objects
                       if obj.Name.startswith("Interim_") and obj.TypeId == "Part::Feature"]
    if any(not obj.LinkedObject or obj.Shape.isNull() or not obj.Shape.isValid()
           for obj in links):
        raise RuntimeError("At least one live assembly link is unresolved")

    assembly.recompute()
    assembly.save()
finally:
    close(assembly)
    close(rear_doc)
    close(pad_doc)

# Cold-open in a fresh document state and ensure both source modules resolve.
check = App.openDocument(str(OUTPUT))
try:
    check.recompute()
    root = check.getObject("AssemblyRoot")
    shell_link = check.getObject("Interim_Body002")
    faceplate_link = check.getObject("Editable_UpperFaceplateBezel")
    pad_links = [check.getObject("Review_AntiSlipPadUpper"),
                 check.getObject("Review_AntiSlipPadLower")]
    links = [obj for obj in check.Objects if obj.TypeId == "App::Link"]
    if (not root.Shape.isValid() or not shell_link.LinkedObject
            or not faceplate_link.LinkedObject or any(not link.LinkedObject for link in pad_links)
            or any(obj.Shape.isNull() or not obj.Shape.isValid() for obj in links)):
        raise RuntimeError("Combined review assembly failed cold-open link validation")
    cold_pad_doc = pad_links[0].LinkedObject.Document
    for name in pad_profile_stats:
        profile = cold_pad_doc.getObject(name)
        if profile is None or not profile.FullyConstrained:
            raise RuntimeError("Cold-open anti-slip profile lost constraints: " + name)
    cold_shell = summary(shell_link.Shape)
    cold_mesh = manifold(shell_link.Shape)
    if cold_shell != rear_stats or cold_mesh != rear_mesh:
        raise RuntimeError("Cold-open rear shell differs from the recomputed pre-save state")
    root_summary = summary(root.Shape)
    if not root_summary["valid"]:
        raise RuntimeError("Cold-open assembly root is invalid")

    result = {
        "status": "disposable combined finishing review; not production approved",
        "assembly": str(OUTPUT.relative_to(ROOT)),
        "source_assembly": str(ASSEMBLY_SOURCE.relative_to(ROOT)),
        "rear_shell_source": str(REAR_SOURCE.relative_to(ROOT)),
        "anti_slip_source": str(PAD_SOURCE.relative_to(ROOT)),
        "live_link_count": len(links),
        "static_interim_components": static_interims,
        "assembly_root_after_reopen": root_summary,
        "rear_shell": {"before_save": rear_stats, "after_reopen": cold_shell,
                       "mesh": cold_mesh, "placement_preserved": True},
        "r050_bezel_link": summary(faceplate_link.Shape),
        "anti_slip_pad_profiles": pad_profile_stats,
        "anti_slip_pads": pad_stats,
        "anti_slip_contact_plane_angle_deg": angle,
        "anti_slip_contact_plane_offset_mm": plane_offset,
        "rear_neighbor_intersections_mm3": intersections,
        "save_close_reopen_recompute": "passed",
        "protected_monolith_and_production_assembly_modified": False,
        "limitations": [
            "Rear shell is a hybrid review Body with a stored-shape base.",
            "Legacy 475.701580 mm3 cached-stage volume delta is not a spatial material map.",
            "The original cached rear-shell feature chain has BRep/mesh defects.",
            "No PLA strength rating or 5x pendant proof-load claim is established.",
        ],
    }
    REPORT_JSON.write_text(json.dumps(result, indent=2) + "\n")
    REPORT_MD.write_text("""# Combined pendant finishing review\n\nStatus: **validated disposable assembly; not production approved.**\n\nThis review combines the live hybrid upper-faceplate component with its native R0.50 mm bezel fillet, the fresh-fuse rear-shell candidate with its native 0.25 mm bottom-perimeter fillet, and separate upper/lower TPU crescent pad links. It preserves the source placements and leaves the protected monolith and production assembly unchanged.\n\n## Previews\n\n![Combined finishing review assembly, underside view](images/combined-finishing-review-2026-11-01/assembly-bottom.png)\n\n![Combined finishing review assembly, front view](images/combined-finishing-review-2026-11-01/assembly-top.png)\n\n![Rear-shell candidate underside with native supports, bottom edge finish, and crescent seats](images/rear-shell-fresh-fuse-structural-review-bottom-2026-11-01.png)\n\n![Display-bezel edge before and after the R0.50 mm native fillet](images/display-bezel-r0p50/before-after.png)\n\n## Validation\n\nThe combined assembly was recomputed, saved, closed, reopened, and recomputed. Its live links resolve. The rear shell is one valid solid with a closed manifold mesh; both crescent pads remain separate and have zero positive-volume overlap with the shell. Their exposed contact planes are coplanar. The assembly-level rear neighbor intersections are recorded in the [machine-readable validation](combined-finishing-review-2026-11-01.json).\n\nThe rear shell remains a hybrid review Body with a stored-shape base. Its legacy 475.701580 mm³ cached-stage volume delta is not an exact material map, and its structural equivalence and PLA load capacity remain unverified. Keep this assembly as a review candidate.\n\n## Files\n\n- [Combined review assembly](../master-driven-leadins-candidate/pendant-modular-combined-finishing-review-2026-11-01.FCStd)\n- [Reusable builder and validator](../scripts/build_combined_finishing_review.py)\n- [JSON results](combined-finishing-review-2026-11-01.json)\n""", encoding="utf-8")
    print(json.dumps(result, indent=2))
finally:
    close(check)
