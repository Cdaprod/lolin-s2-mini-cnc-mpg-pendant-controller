"""Read-only validation of master-driven middle support radii.

Run inside FreeCADCmd with the repository in place. The script opens the
master, component, and disposable review assembly, then makes a reversible
in-memory 7.00 -> 7.05 -> 7.00 mm probe. It never saves CAD documents.
"""
import json
import os
import FreeCAD as App
import MeshPart


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MASTER = os.path.join(ROOT, "pendant-master.FCStd")
COMPONENT = os.path.join(
    ROOT, "pendant-bodies", "rear-shell-native-loadpath-master-radius-review-2026-11-01.FCStd"
)
ASSEMBLY = os.path.join(
    ROOT, "pendant-modular-rear-loadpath-master-radius-review-2026-11-01.FCStd"
)
PARAM_SHEET = "InternalHardware"
PARAM_CELL = "B4"
PARAM_ALIAS = "MiddleSupportRadius"
EXPRESSIONS = {
    "MiddleLeftRoot": "pendant_master#<<InternalHardware>>.MiddleSupportRadius",
    "MiddleRightRoot": "pendant_master#<<InternalHardware>>.MiddleSupportRadius",
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def body_metrics(shape):
    box = shape.BoundBox
    mesh = MeshPart.meshFromShape(
        Shape=shape, LinearDeflection=0.12, AngularDeflection=0.18, Relative=False
    )
    incidence = {}
    for facet in mesh.Facets:
        points = [tuple(round(float(value), 6) for value in point)
                  for point in facet.Points]
        for i, j in ((0, 1), (1, 2), (2, 0)):
            edge = tuple(sorted((points[i], points[j])))
            incidence[edge] = incidence.get(edge, 0) + 1
    try:
        shape.check(True)
        bop = []
    except Exception as exc:
        bop = [line.strip() for line in str(exc).splitlines()
               if line.strip().startswith("Error in")]
    return {
        "valid": bool(shape.isValid()),
        "solid_count": len(shape.Solids),
        "volume_mm3": shape.Volume,
        "area_mm2": shape.Area,
        "bounds_mm": [box.XMin, box.XMax, box.YMin, box.YMax,
                      box.ZMin, box.ZMax],
        "bop_findings": len(bop),
        "bop_types": sorted(set(x.split(":", 1)[-1].strip() for x in bop)),
        "mesh_facets": len(mesh.Facets),
        "mesh_closed": bool(mesh.isSolid()),
        "mesh_boundary_edges": sum(n == 1 for n in incidence.values()),
        "mesh_overincident_edges": sum(n > 2 for n in incidence.values()),
        "mesh_degenerate_facets": sum(facet.Area < 1e-12 for facet in mesh.Facets),
    }


def check_probe(master, recompute_docs, shape_getter, label):
    sheet = master.getObject(PARAM_SHEET)
    baseline_text = sheet.getContents(PARAM_CELL)
    require(abs(getattr(sheet, PARAM_CELL).Value - 7.0) < 1e-9,
            "unexpected baseline MiddleSupportRadius")
    base = shape_getter()
    base_volume = base.Volume
    sheet.set(PARAM_CELL, "7.05 mm")
    master.recompute()
    for doc in recompute_docs:
        doc.recompute()
    changed = shape_getter()
    require(changed.isValid() and len(changed.Solids) == 1,
            label + ": perturbed radius produced an invalid Body")
    require(abs(changed.Volume - base_volume) > 1e-4,
            label + ": master radius did not change geometry")
    sheet.set(PARAM_CELL, baseline_text)
    master.recompute()
    for doc in recompute_docs:
        doc.recompute()
    restored = shape_getter()
    require(restored.isValid() and len(restored.Solids) == 1,
            label + ": restored Body is invalid")
    require(abs(restored.Volume - base_volume) < 1e-6,
            label + ": restored volume did not match baseline")
    return {"baseline_volume_mm3": base_volume,
            "changed_volume_mm3": changed.Volume,
            "changed_delta_mm3": changed.Volume - base_volume,
            "restored_volume_mm3": restored.Volume,
            "restore_error_mm3": restored.Volume - base_volume}


for path in (MASTER, COMPONENT, ASSEMBLY):
    require(os.path.isfile(path), "required review file missing: " + path)

master = App.openDocument(MASTER)
component = App.openDocument(COMPONENT)
master.recompute()
component.recompute()
body = component.getObject("RearShellBody")
require(body is not None and body.Tip.Name == "RearCrescentAntiSlipSeatPocket",
        "rear Body or final Tip missing")
for name, expected in EXPRESSIONS.items():
    sketch = component.getObject(name)
    require(sketch is not None and sketch.FullyConstrained,
            name + " is missing or underconstrained")
    sketch_expressions = dict(sketch.ExpressionEngine)
    require(sketch_expressions.get("Constraints[2]") == expected,
            name + " radius is not linked to the master")
    require("Constraints[0]" not in sketch_expressions
            and "Constraints[1]" not in sketch_expressions,
            name + " center position should remain fixed to the stored shell base")
component_baseline = body_metrics(body.Tip.Shape)
require(component_baseline["valid"] and component_baseline["solid_count"] == 1,
        "component baseline is not one valid solid")
require(component_baseline["mesh_closed"]
        and component_baseline["mesh_boundary_edges"] == 0
        and component_baseline["mesh_overincident_edges"] == 0
        and component_baseline["mesh_degenerate_facets"] == 0,
        "component baseline mesh is not closed manifold")
component_probe = check_probe(master, [component], lambda: body.Tip.Shape, "component")
App.closeDocument(component.Name)
App.closeDocument(master.Name)

master = App.openDocument(MASTER)
assembly = App.openDocument(ASSEMBLY)
assembly.recompute()
rear_link = assembly.getObject("Editable_RearShell_Loadpaths")
require(rear_link is not None and rear_link.TypeId == "App::Link",
        "rear App::Link missing from review assembly")
require(rear_link.LinkedObject.Document.FileName == COMPONENT,
        "review assembly rear link resolves to an unexpected component")
require(len([obj for obj in assembly.Objects if obj.TypeId == "App::Link"]) == 9,
        "review assembly link count changed")
link_placement = str(rear_link.LinkPlacement)
assembly_probe = check_probe(master, [rear_link.LinkedObject.Document, assembly],
                             lambda: rear_link.Shape, "assembly link")
result = {
    "status": "PASS",
    "master": MASTER,
    "component": COMPONENT,
    "assembly": ASSEMBLY,
    "master_alias": PARAM_ALIAS,
    "component_baseline": component_baseline,
    "component_parameter_probe": component_probe,
    "assembly_parameter_probe": assembly_probe,
    "assembly_links": 9,
    "rear_link_placement": link_placement,
    "cad_files_saved": False,
}
print(json.dumps(result, indent=2))
App.closeDocument(assembly.Name)
App.closeDocument(master.Name)
