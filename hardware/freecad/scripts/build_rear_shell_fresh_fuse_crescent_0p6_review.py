"""Build a disposable 0.6 mm-proud crescent-pad review variant.

Copies the eight-link review assembly, links the already validated native pad
module, and cold-open validates the assembly. The 0.8 mm review baseline and
production documents are never written.
"""
import json
import math
import shutil
from pathlib import Path

import FreeCAD as App
import MeshPart


ROOT = Path(__file__).resolve().parents[3]
SOURCE_ASSEMBLY = ROOT / "hardware/freecad/pendant-modular-rear-shell-structural-support-param-review-assembly-2026-11-01.FCStd"
PAD_COMPONENT = ROOT / "hardware/freecad/pendant-bodies/rear-shell-anti-slip-crescent-pads-parametric-0p6-review-2026-11-01.FCStd"
REAR_SHELL = ROOT / "hardware/freecad/pendant-bodies/rear-shell-fresh-fuse-structural-review-2026-11-01.FCStd"
OUTPUT_ASSEMBLY = ROOT / "hardware/freecad/pendant-modular-fresh-fuse-tpu-crescent-0p6-review-2026-11-01.FCStd"
REPORT = ROOT / "hardware/freecad/reports/rear-shell-crescent-0p6-review-2026-11-01.json"

for path in (SOURCE_ASSEMBLY, PAD_COMPONENT, REAR_SHELL):
    if not path.is_file():
        raise FileNotFoundError(path)
for path in (OUTPUT_ASSEMBLY, REPORT):
    if path.exists():
        raise FileExistsError("Refusing to overwrite review artifact: " + str(path))


def close(doc):
    if doc and App.getDocument(doc.Name):
        App.closeDocument(doc.Name)


def shell_summary(shape):
    box = shape.BoundBox
    mesh = MeshPart.meshFromShape(Shape=shape.copy(), LinearDeflection=0.08,
                                  AngularDeflection=0.35, Relative=False)
    edges = {}
    for facet in mesh.Facets:
        points = [tuple(round(float(v), 6) for v in point) for point in facet.Points]
        for a, b in ((0, 1), (1, 2), (2, 0)):
            edge = tuple(sorted((points[a], points[b])))
            edges[edge] = edges.get(edge, 0) + 1
    return {
        "valid": bool(shape.isValid()), "solids": len(shape.Solids),
        "volume_mm3": shape.Volume, "faces": len(shape.Faces),
        "edges": len(shape.Edges), "mesh_is_solid": bool(mesh.isSolid()),
        "mesh_facets": len(mesh.Facets),
        "mesh_boundary_edges": sum(v == 1 for v in edges.values()),
        "mesh_overincident_edges": sum(v > 2 for v in edges.values()),
        "bounds_mm": [box.XMin, box.XMax, box.YMin, box.YMax,
                      box.ZMin, box.ZMax],
    }


def contact_plane(body):
    faces = []
    for index, face in enumerate(body.Shape.Faces, 1):
        if "Plane" not in str(type(face.Surface)):
            continue
        normal = face.Surface.Axis
        normal.normalize()
        center = face.CenterOfMass
        faces.append({"face": index, "area_mm2": face.Area,
                      "normal": [normal.x, normal.y, normal.z],
                      "center_mm": [center.x, center.y, center.z],
                      "constant_mm": normal.dot(center)})
    if not faces:
        raise RuntimeError("No planar anti-slip contact face")
    return min(faces, key=lambda item: item["center_mm"][2])


shutil.copy2(SOURCE_ASSEMBLY, OUTPUT_ASSEMBLY)
pads_doc = App.openDocument(str(PAD_COMPONENT))
pads_doc.recompute()
params = pads_doc.getObject("AntiSlipDesignParameters")
if params is None:
    raise RuntimeError("Native anti-slip parameter sheet is missing")
if (abs(params.UpperPadProtrusion.Value - 0.6) > 1e-9
        or abs(params.LowerPadProtrusion.Value - 0.6) > 1e-9):
    raise RuntimeError("The linked component must be the validated 0.6 mm variant")
for name in ("UpperCrescent", "LowerCrescent"):
    body = pads_doc.getObject(name + "AntiSlipPadBody")
    if body is None or body.Tip is None:
        raise RuntimeError("Native pad Body is missing: " + name)
    profile = pads_doc.getObject(name + "AntiSlipProfile")
    if (body.Tip.State != ["Up-to-date"] or not body.Tip.Shape.isValid()
            or len(body.Tip.Shape.Solids) != 1 or not profile.FullyConstrained):
        raise RuntimeError("Native 0.6 mm pad failed feature validation: " + name)
pads_doc.save()

rear_doc = App.openDocument(str(REAR_SHELL))
assembly = App.openDocument(str(OUTPUT_ASSEMBLY))
assembly.recompute()
shell_link = assembly.getObject("Interim_Body002")
if shell_link is None:
    raise RuntimeError("Rear-shell review link is missing")
shell_placement = shell_link.LinkPlacement
shell_link.LinkedObject = rear_doc.getObject("RearShellStructuralFirstNoDuplicatePad")
shell_link.LinkPlacement = shell_placement
for link_name, body_name in (("Review_AntiSlipPadUpper", "UpperCrescentAntiSlipPadBody"),
                             ("Review_AntiSlipPadLower", "LowerCrescentAntiSlipPadBody")):
    link = assembly.getObject(link_name)
    body = pads_doc.getObject(body_name)
    if link is None or body is None:
        raise RuntimeError("Missing pad link/body: " + link_name)
    placement = link.LinkPlacement
    link.LinkedObject = body
    link.LinkPlacement = placement
assembly.recompute()

pad_metrics = {}
for link_name in ("Review_AntiSlipPadUpper", "Review_AntiSlipPadLower"):
    link = assembly.getObject(link_name)
    shape = link.Shape
    if not shape.isValid() or len(shape.Solids) != 1:
        raise RuntimeError("Review pad link is invalid: " + link_name)
    pad_metrics[link_name] = {
        "valid": True, "solids": len(shape.Solids),
        "volume_mm3": shape.Volume,
        "shell_common_volume_mm3": shell_link.Shape.common(shape).Volume,
        "contact_plane": contact_plane(link),
    }
upper = pad_metrics["Review_AntiSlipPadUpper"]["contact_plane"]
lower = pad_metrics["Review_AntiSlipPadLower"]["contact_plane"]
dot = sum(a * b for a, b in zip(upper["normal"], lower["normal"]))
angle = math.degrees(math.acos(max(-1.0, min(1.0, abs(dot)))))
offset = abs(upper["constant_mm"] - lower["constant_mm"])
if angle > 0.1 or offset > 0.01:
    raise RuntimeError("The 0.6 mm crescent contact faces are not coplanar")
if any(row["shell_common_volume_mm3"] > 1e-7 for row in pad_metrics.values()):
    raise RuntimeError("A crescent pad intersects the rear shell")

assembly.recompute()
assembly.save()
assembly_name, pads_name, rear_name = assembly.Name, pads_doc.Name, rear_doc.Name
close(assembly)
close(pads_doc)
close(rear_doc)

check_pads = App.openDocument(str(PAD_COMPONENT))
check_pads.recompute()
check_assembly = App.openDocument(str(OUTPUT_ASSEMBLY))
check_assembly.recompute()
check_params = check_pads.getObject("AntiSlipDesignParameters")
if (check_params is None
        or abs(check_params.UpperPadProtrusion.Value - 0.6) > 1e-9
        or abs(check_params.LowerPadProtrusion.Value - 0.6) > 1e-9):
    raise RuntimeError("Cold-open pad parameters do not match the 0.6 mm variant")
for name in ("UpperCrescent", "LowerCrescent"):
    body = check_pads.getObject(name + "AntiSlipPadBody")
    profile = check_pads.getObject(name + "AntiSlipProfile")
    if (body is None or profile is None or body.Tip is None
            or body.Tip.State != ["Up-to-date"]
            or not body.Tip.Shape.isValid() or len(body.Tip.Shape.Solids) != 1
            or abs(body.Tip.Length.Value - 0.7) > 1e-9
            or not profile.FullyConstrained):
        raise RuntimeError("Cold-open native pad feature failed: " + name)
check_shell = check_assembly.getObject("Interim_Body002")
if not check_shell or not check_shell.Shape.isValid() or len(check_shell.Shape.Solids) != 1:
    raise RuntimeError("Cold-open rear shell failed validation")
mesh = shell_summary(check_shell.Shape)
if (not mesh["mesh_is_solid"] or mesh["mesh_boundary_edges"]
        or mesh["mesh_overincident_edges"]):
    raise RuntimeError("Cold-open rear-shell mesh is not manifold")
for name, expected_file in (("Review_AntiSlipPadUpper", str(PAD_COMPONENT)),
                            ("Review_AntiSlipPadLower", str(PAD_COMPONENT))):
    link = check_assembly.getObject(name)
    if not link or not link.Shape.isValid() or len(link.Shape.Solids) != 1:
        raise RuntimeError("Cold-open crescent link failed: " + name)
    if link.LinkedObject.Document.FileName != expected_file:
        raise RuntimeError("Cold-open crescent link resolved to the wrong source")
links = [o for o in check_assembly.Objects if o.TypeId == "App::Link"]
if len(links) != 8 or any(o.Shape.isNull() or not o.Shape.isValid() for o in links):
    raise RuntimeError("Cold-open assembly link check failed")

result = {
    "status": "disposable 0.6 mm-proud review candidate; not production-approved",
    "pad_component": str(PAD_COMPONENT),
    "assembly": str(OUTPUT_ASSEMBLY),
    "protrusion_mm": 0.6,
    "pad_total_length_mm": 0.7,
    "protrusion_reduction_from_0p8_mm": 0.2,
    "approximate_magnet_to_wall_distance_reduction_mm": 0.2,
    "native_pad_bodies": pad_metrics,
    "contact_plane_normal_angle_deg": angle,
    "contact_plane_offset_mm": offset,
    "cold_reopen_rear_shell": mesh,
    "cold_reopen_link_count": len(links),
    "protected_monolith_and_production_assembly_modified": False,
    "structural_capacity_verified": False,
    "physical_grip_and_TPU_durability_verified": False,
}
REPORT.write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
close(check_assembly)
close(check_pads)
