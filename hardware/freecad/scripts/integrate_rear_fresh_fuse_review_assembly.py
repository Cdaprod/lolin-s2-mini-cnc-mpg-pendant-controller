"""Build a disposable full review assembly using the fresh-fuse rear shell.

The production assembly and component sources remain untouched. The script
preserves the prior review assembly's links and placements, replaces only its
rear-shell review link, then checks the shell, anti-slip pads, screw clearances,
save/reopen behavior, and a reversible component parameter edit.
"""
import json
import math
import shutil
from pathlib import Path

import FreeCAD as App
import MeshPart


ROOT = Path(__file__).resolve().parents[3]
SOURCE_ASSEMBLY = ROOT / "hardware/freecad/pendant-modular-rear-shell-structural-support-param-review-assembly-2026-11-01.FCStd"
SOURCE_COMPONENT = ROOT / "hardware/freecad/pendant-bodies/rear-shell-fresh-fuse-structural-review-2026-11-01.FCStd"
OUTPUT = ROOT / "hardware/freecad/pendant-modular-fresh-fuse-tpu-crescent-review-2026-11-01.FCStd"
REPORT = ROOT / "hardware/freecad/reports/rear-shell-fresh-fuse-crescent-assembly-review-2026-11-01.json"

for path in (SOURCE_ASSEMBLY, SOURCE_COMPONENT):
    if not path.is_file():
        raise FileNotFoundError(path)
if OUTPUT.exists() or REPORT.exists():
    raise FileExistsError("Refusing to overwrite an existing review artifact")


def summary(shape):
    box = shape.BoundBox
    return {
        "valid": bool(shape.isValid()),
        "solids": len(shape.Solids),
        "volume_mm3": shape.Volume,
        "area_mm2": shape.Area,
        "faces": len(shape.Faces),
        "edges": len(shape.Edges),
        "bounds_mm": [box.XMin, box.XMax, box.YMin, box.YMax,
                      box.ZMin, box.ZMax],
    }


def manifold_summary(shape):
    mesh = MeshPart.meshFromShape(Shape=shape.copy(), LinearDeflection=0.08,
                                  AngularDeflection=0.35, Relative=False)
    incidence = {}
    for facet in mesh.Facets:
        points = [tuple(round(float(value), 6) for value in point)
                  for point in facet.Points]
        for first, second in ((0, 1), (1, 2), (2, 0)):
            edge = tuple(sorted((points[first], points[second])))
            incidence[edge] = incidence.get(edge, 0) + 1
    return {
        "is_solid": bool(mesh.isSolid()),
        "facets": len(mesh.Facets),
        "boundary_edges": sum(count == 1 for count in incidence.values()),
        "overincident_edges": sum(count > 2 for count in incidence.values()),
        "degenerate_facets": sum(facet.Area < 1e-12 for facet in mesh.Facets),
    }


def contact_plane(body):
    planar = []
    for index, face in enumerate(body.Shape.Faces, 1):
        surface = face.Surface
        if "Plane" not in str(type(surface)):
            continue
        normal = surface.Axis
        normal.normalize()
        center = face.CenterOfMass
        planar.append({
            "face": index,
            "area_mm2": face.Area,
            "normal": [normal.x, normal.y, normal.z],
            "center_mm": [center.x, center.y, center.z],
            "plane_constant_mm": normal.dot(center),
        })
    if not planar:
        raise RuntimeError("Anti-slip pad has no planar contact face")
    return min(planar, key=lambda item: item["center_mm"][2])


shutil.copy2(SOURCE_ASSEMBLY, OUTPUT)
assembly = App.openDocument(str(OUTPUT))
component = App.openDocument(str(SOURCE_COMPONENT))
assembly.recompute()
body = component.getObject("RearShellStructuralFirstNoDuplicatePad")
shell_link = assembly.getObject("Interim_Body002")
if body is None or shell_link is None:
    raise RuntimeError("Rear shell or review link is missing")
placement = shell_link.LinkPlacement
shell_link.LinkedObject = body
shell_link.LinkPlacement = placement
assembly.recompute()
baseline = summary(shell_link.Shape)
if not baseline["valid"] or baseline["solids"] != 1:
    raise RuntimeError("Fresh-fuse shell link is not one valid solid")

pad_common = {}
pad_planes = {}
for name in ("Review_AntiSlipPadUpper", "Review_AntiSlipPadLower"):
    pad = assembly.getObject(name)
    if pad is None or pad.Shape.isNull() or not pad.Shape.isValid():
        raise RuntimeError("Missing/invalid anti-slip pad: " + name)
    pad_common[name] = shell_link.Shape.common(pad.Shape).Volume
    pad_planes[name] = contact_plane(pad)

upper_plane = pad_planes["Review_AntiSlipPadUpper"]
lower_plane = pad_planes["Review_AntiSlipPadLower"]
normal_dot = sum(a * b for a, b in zip(upper_plane["normal"], lower_plane["normal"]))
normal_angle = math.degrees(math.acos(max(-1.0, min(1.0, abs(normal_dot)))))
plane_offset = abs(upper_plane["plane_constant_mm"] - lower_plane["plane_constant_mm"])
if normal_angle > 0.1 or plane_offset > 0.01:
    raise RuntimeError("Upper and lower anti-slip contact faces are not coplanar")
if any(volume > 1e-7 for volume in pad_common.values()):
    raise RuntimeError("An anti-slip pad overlaps the rear shell")

parameter = component.getObject("StructuralSupportParameters")
if parameter is None:
    raise RuntimeError("Structural support parameter sheet is missing")
parameter.set("B15", "24.9")
component.recompute()
assembly.recompute()
edited = summary(shell_link.Shape)
if abs(edited["volume_mm3"] - baseline["volume_mm3"]) < 1e-4:
    raise RuntimeError("Component edit did not propagate to the assembly link")
parameter.set("B15", "24.8")
component.recompute()
assembly.recompute()
restored = summary(shell_link.Shape)
if abs(restored["volume_mm3"] - baseline["volume_mm3"]) > 1e-7:
    raise RuntimeError("Restoring the component parameter did not restore geometry")

assembly.recompute()
assembly.save()
assembly_name, component_name = assembly.Name, component.Name
App.closeDocument(assembly_name)
App.closeDocument(component_name)

check = App.openDocument(str(OUTPUT))
check.recompute()
link = check.getObject("Interim_Body002")
if link is None or link.Shape.isNull() or not link.Shape.isValid():
    raise RuntimeError("Cold-open assembly shell link did not resolve")
cold = summary(link.Shape)
mesh = manifold_summary(link.Shape)
if cold["solids"] != 1 or abs(cold["volume_mm3"] - baseline["volume_mm3"]) > 1e-6:
    raise RuntimeError("Cold-open shell geometry differs from review baseline")
if (not mesh["is_solid"] or mesh["boundary_edges"]
        or mesh["overincident_edges"] or mesh["degenerate_facets"]):
    raise RuntimeError("Cold-open assembly rear-shell mesh is not manifold")
if link.LinkPlacement != placement:
    raise RuntimeError("Review shell placement changed")
links = [obj for obj in check.Objects if obj.TypeId == "App::Link"]
if len(links) != 8 or any(obj.Shape.isNull() or not obj.Shape.isValid() for obj in links):
    raise RuntimeError("Review assembly links failed cold-open validation")

REPORT.write_text(json.dumps({
    "status": "disposable review assembly; not production approved",
    "assembly": str(OUTPUT),
    "component": str(SOURCE_COMPONENT),
    "replaced_link": "Interim_Body002",
    "link_placement_preserved": True,
    "live_link_count_after_reopen": len(links),
    "fresh_fuse_shell": baseline,
    "cold_reopen_shell": cold,
    "cold_reopen_mesh": mesh,
    "anti_slip_pad_common_volume_mm3": pad_common,
    "anti_slip_contact_planes": pad_planes,
    "anti_slip_plane_normal_angle_deg": normal_angle,
    "anti_slip_plane_offset_mm": plane_offset,
    "reversible_parameter_test": {
        "parameter": "UpperBossXAbs",
        "original_mm": 24.8,
        "test_mm": 24.9,
        "edited_shell": edited,
        "restored_shell": restored,
        "restoration_volume_error_mm3": restored["volume_mm3"] - baseline["volume_mm3"],
    },
    "protected_monolith_and_production_assembly_modified": False,
    "structural_capacity_verified": False,
}, indent=2) + "\n")
print(json.dumps({"assembly": str(OUTPUT), "shell": cold,
                   "mesh": mesh,
                   "anti_slip_pad_common_volume_mm3": pad_common,
                   "anti_slip_plane_normal_angle_deg": normal_angle,
                   "anti_slip_plane_offset_mm": plane_offset,
                   "live_links": len(links)}, indent=2))
App.closeDocument(check.Name)
