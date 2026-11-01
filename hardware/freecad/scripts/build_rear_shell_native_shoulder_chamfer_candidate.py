"""Add the original two 1 mm upper-boss shoulder chamfers to a disposable rear shell.

The source and monolith are read-only inputs. The candidate is copied to a
new, non-production file and receives a native PartDesign Chamfer after its
existing native support, bottom-fillet, and anti-slip features. The two
historical circular edges are re-identified by curve type, coordinates, and
arc length rather than copied topological edge numbers.
"""
import json
import os
import shutil
from pathlib import Path

import FreeCAD as App
import MeshPart


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "hardware/freecad/pendant-bodies/rear-shell-fresh-fuse-structural-review-2026-11-01.FCStd"
MONOLITH = ROOT / "hardware/freecad/pendant.FCStd"
OUTPUT = Path(os.environ.get(
    "PENDANT_SHOULDER_CHAMFER_OUTPUT",
    str(ROOT / "hardware/freecad/pendant-bodies/rear-shell-native-shoulder-chamfer-review-2026-11-01.FCStd"),
)).expanduser().resolve()
REPORT = Path(os.environ.get(
    "PENDANT_SHOULDER_CHAMFER_REPORT",
    str(ROOT / "hardware/freecad/reports/rear-shell-native-shoulder-chamfer-review-2026-11-01.json"),
)).expanduser().resolve()

for path in (SOURCE, MONOLITH):
    if not path.exists():
        raise FileNotFoundError(path)
for path in (OUTPUT, REPORT):
    if path.exists():
        raise FileExistsError("Refusing to overwrite: " + str(path))


def metrics(shape):
    mesh = MeshPart.meshFromShape(Shape=shape.copy(), LinearDeflection=0.08,
                                  AngularDeflection=0.35, Relative=False)
    incidence = {}
    for facet in mesh.Facets:
        points = [tuple(round(float(value), 6) for value in point)
                  for point in facet.Points]
        for i, j in ((0, 1), (1, 2), (2, 0)):
            edge = tuple(sorted((points[i], points[j])))
            incidence[edge] = incidence.get(edge, 0) + 1
    box = shape.BoundBox
    return {
        "valid": bool(shape.isValid()),
        "solid_count": len(shape.Solids),
        "volume_mm3": shape.Volume,
        "area_mm2": shape.Area,
        "face_count": len(shape.Faces),
        "edge_count": len(shape.Edges),
        "bounds_mm": [box.XMin, box.XMax, box.YMin, box.YMax,
                      box.ZMin, box.ZMax],
        "mesh_closed": bool(mesh.isSolid()),
        "mesh_facets": len(mesh.Facets),
        "mesh_boundary_edges": sum(n == 1 for n in incidence.values()),
        "mesh_overincident_edges": sum(n > 2 for n in incidence.values()),
        "mesh_degenerate_facets": sum(f.Area < 1e-12 for f in mesh.Facets),
    }


def pocket_removal(feature):
    if feature is None or feature.BaseFeature is None:
        raise RuntimeError("Pocket clearance source is missing its BaseFeature")
    removed = feature.BaseFeature.Shape.cut(feature.Shape)
    if removed.isNull() or not removed.isValid():
        raise RuntimeError("Could not derive clearance from " + feature.Name)
    return removed


def find_edge(shape, signature):
    x0, x1, y0, y1, z, length = signature
    found = []
    for index, edge in enumerate(shape.Edges, 1):
        box = edge.BoundBox
        if (type(edge.Curve).__name__ == "Circle"
                and abs(box.XMin - x0) < 0.02 and abs(box.XMax - x1) < 0.02
                and abs(box.YMin - y0) < 0.02 and abs(box.YMax - y1) < 0.02
                and abs(box.ZMin - z) < 0.002 and abs(box.ZMax - z) < 0.002
                and abs(edge.Length - length) < 0.02):
            found.append("Edge%d" % index)
    return found


def close(doc):
    if doc is not None and App.getDocument(doc.Name):
        App.closeDocument(doc.Name)


shutil.copy2(str(SOURCE), str(OUTPUT))
component = monolith = None
try:
    component = App.openDocument(str(OUTPUT))
    monolith = App.openDocument(str(MONOLITH))
    body = component.getObject("RearShellStructuralFirstNoDuplicatePad")
    if body is None or body.Tip is None:
        raise RuntimeError("Expected native rear-shell candidate Body is missing")
    previous_tip = body.Tip
    before = previous_tip.Shape.copy()

    # SourceEdges were Edge1373 and Edge339 on the original loft output.
    # Their actual geometric signatures are matched against the new candidate.
    signatures = (
        (-22.2076, -20.0, 58.5, 63.6022, -25.0, 5.71689),
        (20.0, 26.1573, 51.5509, 63.6276, -25.0, 15.90498),
    )
    edges = [edge for signature in signatures
             for edge in find_edge(before, signature)]
    if len(edges) != 2 or len(set(edges)) != 2:
        raise RuntimeError("Expected exactly two geometrically matched source shoulder arcs; found %r" % edges)

    chamfer = body.newObject("PartDesign::Chamfer", "NativeUpperBossShoulderChamfer")
    chamfer.Label = "Upper boss underside transitions — 1 mm native chamfer"
    chamfer.Base = (previous_tip, edges)
    chamfer.Size = 1.0
    chamfer.Refine = True
    body.Tip = chamfer
    component.recompute([chamfer])
    after = chamfer.Shape.copy()
    pre_save = metrics(after)
    if (not pre_save["valid"] or pre_save["solid_count"] != 1
            or not pre_save["mesh_closed"] or pre_save["mesh_boundary_edges"]
            or pre_save["mesh_overincident_edges"] or pre_save["mesh_degenerate_facets"]):
        raise RuntimeError("Native shoulder chamfer did not produce one manifold solid")

    removed = before.cut(after)
    added = after.cut(before)
    if (removed.isNull() or not removed.isValid() or added.isNull()
            or not added.isValid() or added.Volume > 1e-5):
        raise RuntimeError("Could not localize the shoulder chamfer difference reliably")

    screw_clearance = pocket_removal(monolith.getObject("Pocket018"))
    magnet_clearance = pocket_removal(monolith.getObject("Pocket")).fuse(
        pocket_removal(monolith.getObject("Pocket015")))
    clearance = {
        "m2_before_mm3": before.common(screw_clearance).Volume,
        "m2_after_mm3": after.common(screw_clearance).Volume,
        "magnet_before_mm3": before.common(magnet_clearance).Volume,
        "magnet_after_mm3": after.common(magnet_clearance).Volume,
    }
    clearance["m2_delta_mm3"] = clearance["m2_after_mm3"] - clearance["m2_before_mm3"]
    clearance["magnet_delta_mm3"] = clearance["magnet_after_mm3"] - clearance["magnet_before_mm3"]
    if abs(clearance["m2_delta_mm3"]) > 1e-5 or abs(clearance["magnet_delta_mm3"]) > 1e-5:
        raise RuntimeError("Chamfer changed a screw or magnet clearance")

    component.recompute()
    component.save()
finally:
    close(component)
    close(monolith)

check = App.openDocument(str(OUTPUT))
try:
    check.recompute()
    body = check.getObject("RearShellStructuralFirstNoDuplicatePad")
    final_tip = body.Tip
    cold = metrics(final_tip.Shape)
    expected = metrics(after)
    if (final_tip.Name != "NativeUpperBossShoulderChamfer"
            or not cold["valid"] or cold["solid_count"] != 1
            or not cold["mesh_closed"] or cold["mesh_boundary_edges"]
            or cold["mesh_overincident_edges"] or cold["mesh_degenerate_facets"]
            or abs(cold["volume_mm3"] - expected["volume_mm3"]) > 1e-6):
        raise RuntimeError("Cold-open recomputation did not reproduce the validated chamfer")
    result = {
        "status": "disposable review candidate; not production-approved",
        "candidate": str(OUTPUT),
        "source_candidate": str(SOURCE),
        "protected_monolith_modified": False,
        "production_assembly_modified": False,
        "operation": "Native PartDesign Chamfer, 1.0 mm, on the two original upper-boss underside circular arcs",
        "edge_selection": {
            "method": "geometric match using curve type, global bounds, Z plane, and arc length",
            "matched_edges": edges,
            "source_feature_edges": ["Edge1373", "Edge339"],
            "global_z_mm": -25.0,
        },
        "before": metrics(before),
        "after": pre_save,
        "removed_material": {
            "volume_mm3": removed.Volume,
            "bounds_mm": [removed.BoundBox.XMin, removed.BoundBox.XMax,
                          removed.BoundBox.YMin, removed.BoundBox.YMax,
                          removed.BoundBox.ZMin, removed.BoundBox.ZMax],
            "valid": removed.isValid(),
            "solid_count": len(removed.Solids),
        },
        "added_material_mm3": added.Volume,
        "clearance_deltas": clearance,
        "cold_reopen_recompute": cold,
        "legacy_reference": {
            "feature": "RearBossShoulderTransitions",
            "source_design_note": "Local 45-degree bevels at two abrupt 90-degree boss underside junctions.",
            "legacy_net_volume_delta_mm3": -14.961449683135,
            "candidate_chamfer_volume_delta_mm3": after.Volume - before.Volume,
            "exact_brep_equivalence": False,
        },
    }
    REPORT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, separators=(",", ":")))
finally:
    close(check)
