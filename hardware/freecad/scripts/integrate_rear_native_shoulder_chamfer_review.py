"""Link the validated native upper-boss chamfer into a disposable review assembly."""
import json
import os
from pathlib import Path

import FreeCAD as App
import MeshPart


ROOT = Path(__file__).resolve().parents[3]
SOURCE_ASSEMBLY = ROOT / "hardware/freecad/pendant-modular-fresh-fuse-tpu-crescent-0p6-review-2026-11-01.FCStd"
SOURCE_COMPONENT = ROOT / "hardware/freecad/pendant-bodies/rear-shell-native-shoulder-chamfer-review-2026-11-01.FCStd"
OUTPUT = ROOT / "hardware/freecad/pendant-modular-fresh-fuse-tpu-crescent-shoulder-chamfer-review-2026-11-01.FCStd"
REPORT = ROOT / "hardware/freecad/reports/rear-shell-native-shoulder-chamfer-assembly-review-2026-11-01.json"
for path in (SOURCE_ASSEMBLY, SOURCE_COMPONENT):
    if not path.exists():
        raise FileNotFoundError(path)
for path in (OUTPUT, REPORT):
    if path.exists():
        raise FileExistsError("Refusing to overwrite: " + str(path))


def mesh_metrics(shape):
    mesh = MeshPart.meshFromShape(Shape=shape.copy(), LinearDeflection=0.08,
                                  AngularDeflection=0.35, Relative=False)
    incidence = {}
    for facet in mesh.Facets:
        points = [tuple(round(float(v), 6) for v in p) for p in facet.Points]
        for i, j in ((0, 1), (1, 2), (2, 0)):
            key = tuple(sorted((points[i], points[j])))
            incidence[key] = incidence.get(key, 0) + 1
    return {
        "mesh_closed": bool(mesh.isSolid()),
        "facets": len(mesh.Facets),
        "boundary_edges": sum(n == 1 for n in incidence.values()),
        "overincident_edges": sum(n > 2 for n in incidence.values()),
        "degenerate_facets": sum(f.Area < 1e-12 for f in mesh.Facets),
    }


def common_volume(a, b):
    if a.isNull() or b.isNull():
        return 0.0
    return a.common(b).Volume


assembly = component = cold = None
try:
    assembly = App.openDocument(str(SOURCE_ASSEMBLY))
    component = App.openDocument(str(SOURCE_COMPONENT))
    link = assembly.getObject("Interim_Body002")
    body = component.getObject("RearShellStructuralFirstNoDuplicatePad")
    if link is None or body is None:
        raise RuntimeError("Expected rear-shell App::Link or component Body is missing")
    old_target = link.LinkedObject
    old_place = link.LinkPlacement
    old_shape = link.Shape.copy()
    neighbors = [o for o in assembly.Objects
                 if ((o.TypeId == "App::Link") or o.TypeId == "Part::Feature")
                 and o.Name != link.Name and hasattr(o, "Shape") and not o.Shape.isNull()]
    before_intersections = {o.Name: common_volume(old_shape, o.Shape) for o in neighbors}

    link.LinkedObject = body
    link.LinkPlacement = old_place
    assembly.recompute()
    new_shape = link.Shape.copy()
    after_intersections = {o.Name: common_volume(new_shape, o.Shape) for o in neighbors}
    intersection_deltas = {name: after_intersections[name] - before_intersections[name]
                           for name in before_intersections}
    if any(abs(delta) > 1e-5 for delta in intersection_deltas.values()):
        raise RuntimeError("Shoulder chamfer changed an assembly intersection: " +
                           json.dumps(intersection_deltas))
    if abs(link.LinkPlacement.Base.x - old_place.Base.x) > 1e-9 or abs(
            link.LinkPlacement.Base.y - old_place.Base.y) > 1e-9 or abs(
            link.LinkPlacement.Base.z - old_place.Base.z) > 1e-9:
        raise RuntimeError("Rear-shell App::Link placement changed")
    if not new_shape.isValid() or len(new_shape.Solids) != 1:
        raise RuntimeError("Updated rear-shell link is not one valid solid")
    mesh_before_save = mesh_metrics(new_shape)
    if (not mesh_before_save["mesh_closed"] or mesh_before_save["boundary_edges"]
            or mesh_before_save["overincident_edges"] or mesh_before_save["degenerate_facets"]):
        raise RuntimeError("Updated rear-shell link is not a closed manifold mesh")
    assembly.recompute()
    assembly.saveAs(str(OUTPUT))
finally:
    if component is not None and App.getDocument(component.Name):
        App.closeDocument(component.Name)
    if assembly is not None and App.getDocument(assembly.Name):
        App.closeDocument(assembly.Name)

cold = App.openDocument(str(OUTPUT))
try:
    cold.recompute()
    link = cold.getObject("Interim_Body002")
    if link is None or link.LinkedObject is None:
        raise RuntimeError("Cold-open rear-shell link did not resolve")
    resolved = []
    unresolved = []
    for obj in cold.Objects:
        if obj.TypeId == "App::Link":
            target = obj.LinkedObject
            if target is None:
                unresolved.append(obj.Name)
            else:
                resolved.append(obj.Name)
    if unresolved:
        raise RuntimeError("Cold-open assembly has unresolved links: " + repr(unresolved))
    if (Path(link.LinkedObject.Document.FileName).resolve() != SOURCE_COMPONENT.resolve()
            or link.LinkedObject.Name != "RearShellStructuralFirstNoDuplicatePad"):
        raise RuntimeError("Cold-open rear-shell link does not target the validated native component")
    final_shape = link.Shape
    final_mesh = mesh_metrics(final_shape)
    if (not final_shape.isValid() or len(final_shape.Solids) != 1
            or not final_mesh["mesh_closed"] or final_mesh["boundary_edges"]
            or final_mesh["overincident_edges"] or final_mesh["degenerate_facets"]):
        raise RuntimeError("Cold-open rear-shell link geometry failed manifold validation")
    root = cold.getObject("AssemblyRoot")
    result = {
        "status": "disposable review assembly; not production-approved",
        "candidate_assembly": str(OUTPUT),
        "source_assembly": str(SOURCE_ASSEMBLY),
        "source_component": str(SOURCE_COMPONENT),
        "updated_link": link.Name,
        "linked_body": link.LinkedObject.Name,
        "linked_component_file": link.LinkedObject.Document.FileName,
        "link_placement": str(link.LinkPlacement),
        "link_placement_preserved": True,
        "resolved_app_links": resolved,
        "unresolved_app_links": unresolved,
        "other_component_intersection_volumes_before_mm3": before_intersections,
        "other_component_intersection_volumes_after_mm3": after_intersections,
        "intersection_deltas_mm3": intersection_deltas,
        "pre_save_link_mesh": mesh_before_save,
        "cold_reopen_link": {
            "valid": final_shape.isValid(),
            "solid_count": len(final_shape.Solids),
            "volume_mm3": final_shape.Volume,
            **final_mesh,
        },
        "assembly_root": {
            "valid": root.Shape.isValid(),
            "solid_count": len(root.Shape.Solids),
            "volume_mm3": root.Shape.Volume,
        },
        "production_assembly_modified": False,
        "protected_monolith_modified": False,
    }
    REPORT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, separators=(",", ":")))
finally:
    if cold is not None and App.getDocument(cold.Name):
        App.closeDocument(cold.Name)
