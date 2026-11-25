#!/usr/bin/env python3
"""Cold-open validation for the disposable rear-shell receiver assembly.

Run with the configured FreeCAD command-line Python runner. This script opens
only the review assembly and its linked sources, performs read-only geometry
checks plus a reversible in-memory parameter probe, then closes the documents
without saving any CAD file.
"""
from __future__ import annotations

import json
from pathlib import Path

import FreeCAD as App
import MeshPart
import Part


FREECAD_DIR = Path(__file__).resolve().parents[1]
ASSEMBLY = FREECAD_DIR / "pendant-modular-rear-loadpath-receiver-r0p4-review-2026-11-01.FCStd"
BASELINE_ASSEMBLY = FREECAD_DIR / "pendant-modular-assembly.FCStd"
REPORT = FREECAD_DIR / "reports" / "rear-shell-loadpath-receiver-review-2026-11-01.json"


def mesh_incidence(shape):
    mesh = MeshPart.meshFromShape(
        Shape=shape, LinearDeflection=0.12, AngularDeflection=0.18, Relative=False
    )
    incidence = {}
    for facet in mesh.Facets:
        ids = facet.PointIndices
        for i in range(3):
            edge = tuple(sorted((ids[i], ids[(i + 1) % 3])))
            incidence[edge] = incidence.get(edge, 0) + 1
    return {
        "triangles": len(mesh.Facets),
        "boundary_edges": sum(count == 1 for count in incidence.values()),
        "overincident_edges": sum(count > 2 for count in incidence.values()),
    }


def bbox_values(shape):
    box = shape.BoundBox
    return [box.XMin, box.XMax, box.YMin, box.YMax, box.ZMin, box.ZMax]


def main():
    opened = []
    try:
        assembly = App.openDocument(str(ASSEMBLY))
        opened.append(assembly.Name)
        assembly.recompute()
        front_link = assembly.getObject("Editable_FrontShell_Receiver")
        rear_link = assembly.getObject("Editable_RearShell_Loadpaths")
        shell_module = assembly.getObject("ShellModule")
        if not front_link or not rear_link or not shell_module:
            raise RuntimeError("Review shell links or ShellModule are missing")
        front_doc = front_link.LinkedObject.Document
        rear_doc = rear_link.LinkedObject.Document
        if front_doc.Name not in opened:
            opened.append(front_doc.Name)
        if rear_doc.Name not in opened:
            opened.append(rear_doc.Name)

        front = front_link.Shape
        rear = rear_link.Shape
        front_body = front_link.LinkedObject
        rear_body = rear_link.LinkedObject
        front_base = front_doc.getObject("ImportedFrontBaseline").Shape
        shell_common = front.common(rear)

        clearances = front_doc.getObject("Parameters")
        old_middle = str(clearances.get("B2"))
        old_lower = str(clearances.get("B3"))
        old_wall = str(clearances.get("B4"))
        before_probe = front_link.Shape.Volume
        clearances.set("B2", "0.45 mm")
        front_doc.recompute()
        assembly.recompute()
        changed = front_link.Shape.Volume
        clearances.set("B2", old_middle)
        clearances.set("B3", old_lower)
        clearances.set("B4", old_wall)
        front_doc.recompute()
        assembly.recompute()
        restored = front_link.Shape.Volume

        screw_tools = Part.makeCompound(
            [
                Part.makeCylinder(1.15, 14, App.Vector(x, y, -14), App.Vector(0, 0, 1))
                for x, y in [(-27, 58.5), (27, 58.5), (-18, -17.7566), (18, -17.7566)]
            ]
        )
        screw_zone = {
            "z_from_mm": -14.0,
            "radius_mm": 1.15,
            "length_mm": 14.0,
            "baseline_intersection_mm3": front_base.common(screw_tools).Volume,
            "candidate_intersection_mm3": front.common(screw_tools).Volume,
        }

        receivers = [
            "MiddleLeftReceiver",
            "MiddleRightReceiver",
            "LowerLeftReceiver",
            "LowerRightReceiver",
        ]
        sketches = [
            "MiddleLeftEntrance", "MiddleLeftWallEnd",
            "MiddleRightEntrance", "MiddleRightWallEnd",
            "LowerLeftEntrance", "LowerLeftWallEnd",
            "LowerRightEntrance", "LowerRightWallEnd",
        ]
        receiver_status = {
            name: {
                "state": list(front_doc.getObject(name).State),
                "valid": front_doc.getObject(name).Shape.isValid(),
                "solids": len(front_doc.getObject(name).Shape.Solids),
            }
            for name in receivers
        }
        sketch_status = {
            name: {
                "fully_constrained": bool(front_doc.getObject(name).FullyConstrained),
                "geometry_count": front_doc.getObject(name).GeometryCount,
                "expression_count": len(front_doc.getObject(name).ExpressionEngine),
            }
            for name in sketches
        }

        result = {
            "status": "PASS_REVIEW_CANDIDATE",
            "assembly": str(ASSEMBLY.relative_to(FREECAD_DIR)),
            "front_component": str(Path(front_doc.FileName).resolve().relative_to(FREECAD_DIR)),
            "rear_component": str(Path(rear_doc.FileName).resolve().relative_to(FREECAD_DIR)),
            "links": {
                "count": sum(obj.TypeId == "App::Link" for obj in assembly.Objects),
                "front_target": f"{front_doc.Name}#{front_body.Name}",
                "rear_target": f"{rear_doc.Name}#{rear_body.Name}",
                "shell_group_children": [obj.Name for obj in shell_module.Group],
                "static_shell_placeholders_remaining": [
                    name for name in ("Interim_Body", "Interim_Body002")
                    if assembly.getObject(name)
                ],
                "placements": [str(front_link.LinkPlacement), str(rear_link.LinkPlacement)],
            },
            "front_shell": {
                "valid": front.isValid(),
                "solids": len(front.Solids),
                "baseline_volume_mm3": front_base.Volume,
                "candidate_volume_mm3": front.Volume,
                "receiver_cut_volume_mm3": front_base.Volume - front.Volume,
                "baseline_bounds": bbox_values(front_base),
                "candidate_bounds": bbox_values(front),
                "bounds_delta_mm": max(
                    abs(a - b) for a, b in zip(bbox_values(front_base), bbox_values(front))
                ),
                "baseline_mesh": mesh_incidence(front_base),
                "candidate_mesh": mesh_incidence(front),
                "screw_engagement_zone": screw_zone,
                "receivers": receiver_status,
                "sketches": sketch_status,
            },
            "rear_shell": {
                "valid": rear.isValid(),
                "solids": len(rear.Solids),
                "volume_mm3": rear.Volume,
                "bounds": bbox_values(rear),
                "mesh": mesh_incidence(rear),
                "tip": rear_body.Tip.Name,
                "included_finishes": ["R0.25 mm native bottom perimeter fillet", "0.10 mm crescent seat pocket"],
                "body_history_limitation": "The base is a stored fused BREP; the support and finishing steps are native PartDesign features.",
                "bop_check_limitation": "The rear BREP retains the BOP findings recorded in the native load-path review; this is not a BOP-clean production shell.",
            },
            "mating": {
                "rear_front_common_mm3": shell_common.Volume,
                "common_solids": len(shell_common.Solids),
            },
            "assembly_refresh_probe": {
                "parameter": "MiddleBossRootClearance",
                "baseline_volume_mm3": before_probe,
                "changed_volume_mm3": changed,
                "restored_volume_mm3": restored,
                "change_mm3": changed - before_probe,
                "restore_error_mm3": restored - before_probe,
                "values_restored_in_memory": True,
                "CAD_files_saved_by_validator": False,
            },
        }

        assertions = [
            front.isValid() and len(front.Solids) == 1,
            rear.isValid() and len(rear.Solids) == 1,
            shell_common.Volume < 0.01,
            result["front_shell"]["bounds_delta_mm"] < 1e-5,
            result["front_shell"]["candidate_mesh"]["boundary_edges"] == result["front_shell"]["baseline_mesh"]["boundary_edges"],
            result["front_shell"]["candidate_mesh"]["overincident_edges"] == result["front_shell"]["baseline_mesh"]["overincident_edges"],
            result["rear_shell"]["mesh"]["boundary_edges"] == 0,
            result["rear_shell"]["mesh"]["overincident_edges"] == 0,
            abs(screw_zone["candidate_intersection_mm3"] - screw_zone["baseline_intersection_mm3"]) < 1e-5,
            abs(changed - before_probe) > 0.01,
            abs(restored - before_probe) < 1e-5,
            all(item["valid"] and item["solids"] == 1 for item in receiver_status.values()),
            all(item["fully_constrained"] for item in sketch_status.values()),
            not result["links"]["static_shell_placeholders_remaining"],
        ]
        if not all(assertions):
            result["status"] = "FAIL"
            result["failed_assertions"] = [index for index, ok in enumerate(assertions) if not ok]
            raise RuntimeError(json.dumps(result, indent=2))

        if not REPORT.exists():
            REPORT.parent.mkdir(parents=True, exist_ok=True)
            REPORT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        else:
            print(f"Existing evidence preserved; not overwriting {REPORT}")
        print(json.dumps(result, indent=2))
    finally:
        for name in reversed(opened):
            if name in App.listDocuments():
                try:
                    App.closeDocument(name)
                except Exception:
                    pass


main()
