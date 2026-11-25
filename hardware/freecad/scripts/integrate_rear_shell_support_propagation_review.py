"""Test a parameterized rear-shell support candidate in a disposable assembly."""
import json
import shutil
from pathlib import Path

import FreeCAD as App
import MeshPart


ROOT = Path(__file__).resolve().parents[3]
ASSEMBLY_SOURCE = ROOT / "hardware/freecad/pendant-modular-fresh-fuse-tpu-crescent-shoulder-chamfer-review-2026-11-01.FCStd"
COMPONENT = ROOT / "hardware/freecad/pendant-bodies/rear-shell-native-support-propagation-review-2026-11-01.FCStd"
OUTPUT = ROOT / "hardware/freecad/pendant-modular-rear-support-propagation-review-2026-11-01.FCStd"
REPORT = ROOT / "hardware/freecad/reports/rear-shell-native-support-propagation-assembly-review-2026-11-01.json"

for path in (ASSEMBLY_SOURCE, COMPONENT):
    if not path.exists():
        raise FileNotFoundError(path)
for path in (OUTPUT, REPORT):
    if path.exists():
        raise FileExistsError("Refusing to overwrite: " + str(path))
shutil.copy2(ASSEMBLY_SOURCE, OUTPUT)


def mesh_metrics(shape):
    mesh = MeshPart.meshFromShape(Shape=shape.copy(), LinearDeflection=0.08,
                                  AngularDeflection=0.35, Relative=False)
    incidence = {}
    for facet in mesh.Facets:
        pts = [tuple(round(float(v), 6) for v in point) for point in facet.Points]
        for i, j in ((0, 1), (1, 2), (2, 0)):
            key = tuple(sorted((pts[i], pts[j])))
            incidence[key] = incidence.get(key, 0) + 1
    return {
        "closed": bool(mesh.isSolid()),
        "facets": len(mesh.Facets),
        "boundary_edges": sum(n == 1 for n in incidence.values()),
        "overincident_edges": sum(n > 2 for n in incidence.values()),
        "degenerate_facets": sum(f.Area < 1e-12 for f in mesh.Facets),
    }


assembly = component = cold = None
try:
    assembly = App.openDocument(str(OUTPUT))
    link = assembly.getObject("Interim_Body002")
    if link is None:
        raise RuntimeError("Review assembly rear-shell link is missing")
    old_place = link.LinkPlacement
    old_shape = link.Shape.copy()
    neighbors = [o for o in assembly.Objects
                 if o.Name != link.Name and hasattr(o, "Shape") and not o.Shape.isNull()
                 and (o.TypeId == "App::Link" or o.TypeId == "Part::Feature")]
    before = {o.Name: old_shape.common(o.Shape).Volume for o in neighbors}

    component = App.openDocument(str(COMPONENT))
    body = component.getObject("RearShellStructuralFirstNoDuplicatePad")
    if body is None or body.Tip is None:
        raise RuntimeError("Parameterized rear-shell Body/Tip is missing")
    link.LinkedObject = body
    link.LinkPlacement = old_place
    assembly.recompute()
    new_shape = link.Shape.copy()
    after = {o.Name: new_shape.common(o.Shape).Volume for o in neighbors}
    deltas = {name: after[name] - before[name] for name in before}
    if any(abs(v) > 1e-5 for v in deltas.values()):
        raise RuntimeError("Component substitution changed an assembly intersection: " + json.dumps(deltas))
    if (not new_shape.isValid() or len(new_shape.Solids) != 1
            or abs(link.LinkPlacement.Base.x - old_place.Base.x) > 1e-9
            or abs(link.LinkPlacement.Base.y - old_place.Base.y) > 1e-9
            or abs(link.LinkPlacement.Base.z - old_place.Base.z) > 1e-9):
        raise RuntimeError("Replacement link geometry or placement failed validation")
    before_save_mesh = mesh_metrics(new_shape)
    if (not before_save_mesh["closed"] or before_save_mesh["boundary_edges"]
            or before_save_mesh["overincident_edges"] or before_save_mesh["degenerate_facets"]):
        raise RuntimeError("Replacement rear-shell link mesh is not manifold")
    assembly.recompute()
    assembly.save()
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
        raise RuntimeError("Cold-open review assembly has an unresolved rear-shell link")
    linked_path = Path(link.LinkedObject.Document.FileName).resolve()
    if linked_path != COMPONENT.resolve():
        raise RuntimeError("Cold-open rear link resolved to an unexpected component: " + str(linked_path))
    resolved, unresolved = [], []
    for obj in cold.Objects:
        if obj.TypeId == "App::Link":
            (resolved if obj.LinkedObject is not None else unresolved).append(obj.Name)
    if unresolved:
        raise RuntimeError("Cold-open assembly has unresolved App::Links: " + repr(unresolved))
    final_shape = link.Shape
    cold_mesh = mesh_metrics(final_shape)
    if (not final_shape.isValid() or len(final_shape.Solids) != 1
            or not cold_mesh["closed"] or cold_mesh["boundary_edges"]
            or cold_mesh["overincident_edges"] or cold_mesh["degenerate_facets"]):
        raise RuntimeError("Cold-open rear-shell link failed solid/manifold checks")
    root = cold.getObject("AssemblyRoot")
    result = {
        "status": "disposable review assembly; not production-approved",
        "assembly": str(OUTPUT),
        "component": str(COMPONENT),
        "rear_link": link.Name,
        "linked_body": link.LinkedObject.Name,
        "placement": str(link.LinkPlacement),
        "resolved_links": resolved,
        "unresolved_links": unresolved,
        "intersection_volumes_before_mm3": before,
        "intersection_volumes_after_mm3": after,
        "intersection_deltas_mm3": deltas,
        "pre_save_mesh": before_save_mesh,
        "cold_reopen_link": {
            "valid": final_shape.isValid(),
            "solid_count": len(final_shape.Solids),
            "volume_mm3": final_shape.Volume,
            **cold_mesh,
        },
        "assembly_root": {
            "valid": root.Shape.isValid(),
            "solid_count": len(root.Shape.Solids),
            "volume_mm3": root.Shape.Volume,
        },
        "protected_monolith_modified": False,
        "production_assembly_modified": False,
    }
    REPORT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
finally:
    if App.getDocument(cold.Name):
        App.closeDocument(cold.Name)
