#!/usr/bin/env python3
"""Read-only FreeCADCmd validation of lower-web magnet and screw clearances."""
import hashlib
import json
import os
from pathlib import Path

import FreeCAD as App
import Part

ROOT = Path(os.environ.get("PENDANT_REPO_ROOT", Path(__file__).resolve().parents[3]))
MONOLITH = ROOT / "hardware/freecad/pendant.FCStd"
CANDIDATE = ROOT / "hardware/freecad/pendant-bodies/rear-shell-webs-dimensioned-sketches-review-candidate.FCStd"


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def removed(before, after):
    shape = before.cut(after)
    if shape.isNull() or not shape.isValid():
        raise RuntimeError("could not construct valid removed-volume tool")
    return shape


def profile_prism(sketch, pad):
    wires = list(sketch.Shape.Wires)
    if len(wires) != 1:
        raise RuntimeError("{} has {} profile wires; expected one".format(sketch.Name, len(wires)))
    return Part.Face(wires[0]).extrude(pad.Direction * pad.Length.Value)


def summary(shape):
    return {"valid": bool(shape.isValid()), "solid_count": len(shape.Solids), "volume_mm3": float(shape.Volume)}


def mesh_topology(shape, linear_deflection=0.1, merge_tolerance=1e-6):
    points, triangles = shape.tessellate(linear_deflection)
    vertex_ids = {}
    ids = []
    for point in points:
        key = (round(point.x / merge_tolerance), round(point.y / merge_tolerance), round(point.z / merge_tolerance))
        if key not in vertex_ids:
            vertex_ids[key] = len(vertex_ids)
        ids.append(vertex_ids[key])
    incidence = {}
    degenerate_triangles = 0
    for a, b, c in triangles:
        tri = (ids[a], ids[b], ids[c])
        if len(set(tri)) < 3:
            degenerate_triangles += 1
        for u, v in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            edge = (u, v) if u < v else (v, u)
            incidence[edge] = incidence.get(edge, 0) + 1
    counts = {}
    for uses in incidence.values():
        counts[uses] = counts.get(uses, 0) + 1
    return {
        "linear_deflection_mm": linear_deflection,
        "vertex_merge_tolerance_mm": merge_tolerance,
        "triangle_count": len(triangles),
        "unique_vertex_count": len(vertex_ids),
        "edge_incidence_counts": {str(k): v for k, v in sorted(counts.items())},
        "boundary_edges": counts.get(1, 0),
        "over_incident_edges": sum(v for k, v in counts.items() if k > 2),
        "degenerate_triangles": degenerate_triangles,
    }


def contact_plane(body):
    if body is None or body.Tip is None or not body.Shape.isValid() or len(body.Shape.Solids) != 1:
        raise RuntimeError("anti-slip pad Body is missing or invalid")
    candidates = []
    for face in body.Shape.Faces:
        if "Plane" not in str(type(face.Surface)):
            continue
        center = face.CenterOfMass
        normal = face.normalAt(0, 0)
        if normal.z < -0.9:
            normal.normalize()
            candidates.append((face.Area, normal, center, normal.dot(center)))
    if not candidates:
        raise RuntimeError(body.Name + " has no downward-facing planar contact face")
    area, normal, center, offset = max(candidates, key=lambda item: item[0])
    return {"contact_area_mm2": float(area), "normal": [float(normal.x), float(normal.y), float(normal.z)],
            "plane_offset_mm": float(offset), "center_mm": [float(center.x), float(center.y), float(center.z)]}


def clearance(prism, tool):
    common = prism.common(tool)
    if common.isNull() or not common.isValid():
        raise RuntimeError("invalid common result")
    return {"common_volume_mm3": float(common.Volume), "minimum_distance_mm": float(prism.distToShape(tool)[0])}


opened = []
try:
    source = App.openDocument(str(MONOLITH))
    opened.append(source)
    candidate = App.openDocument(str(CANDIDATE))
    opened.append(candidate)
    candidate.recompute()

    cutters = {
        "magnet_clearance": removed(source.getObject("Pad007").Shape, source.getObject("Pocket").Shape),
        "magnet_slot": removed(source.getObject("Pad019").Shape, source.getObject("Pocket015").Shape),
        "m2_passages": removed(source.getObject("RearTaperedSeats").Shape, source.getObject("Pocket018").Shape),
    }
    body = candidate.getObject("RearShell")
    if body is None or body.Tip is None:
        raise RuntimeError("RearShell Body or active Tip is missing")
    if not body.Tip.Shape.isValid() or len(body.Tip.Shape.Solids) != 1:
        raise RuntimeError("recomputed RearShell Tip is not one valid solid")
    topology = mesh_topology(body.Tip.Shape)
    if topology["boundary_edges"] or topology["over_incident_edges"] or topology["degenerate_triangles"]:
        raise RuntimeError("recomputed RearShell Tip mesh is not manifold: {}".format(topology))
    upper_contact = contact_plane(candidate.getObject("AntiSlipPadUpper"))
    lower_contact = contact_plane(candidate.getObject("AntiSlipPadLower"))
    normal_dot = sum(a * b for a, b in zip(upper_contact["normal"], lower_contact["normal"]))
    plane_offset_delta = abs(upper_contact["plane_offset_mm"] - lower_contact["plane_offset_mm"])
    if normal_dot < 1.0 - 1e-8 or plane_offset_delta > 0.01:
        raise RuntimeError("upper/lower anti-slip contact planes are not coplanar")
    profiles = {
        "left": profile_prism(candidate.getObject("LowerLeftInnerWebProfile"), candidate.getObject("LowerLeftInnerWebPad")),
        "right": profile_prism(candidate.getObject("LowerRightInnerWebProfile"), candidate.getObject("LowerRightInnerWebPad")),
    }
    checks = {}
    for side, prism in profiles.items():
        if not prism.isValid() or len(prism.Solids) != 1:
            raise RuntimeError("{} web prism is not one valid solid".format(side))
        checks[side] = {name: clearance(prism, cutter) for name, cutter in cutters.items()}
        if any(x["common_volume_mm3"] > 1e-7 or x["minimum_distance_mm"] <= 1e-7 for x in checks[side].values()):
            raise RuntimeError("{} web prism intersects or touches a reserved cut volume".format(side))

    result = {
        "status": "PASS",
        "candidate": CANDIDATE.name,
        "candidate_sha256": digest(CANDIDATE),
        "monolith_sha256": digest(MONOLITH),
        "candidate_tip": summary(body.Tip.Shape),
        "candidate_tip_mesh_topology": topology,
        "anti_slip_contact_planes": {"upper": upper_contact, "lower": lower_contact,
                                     "normal_dot": normal_dot, "offset_difference_mm": plane_offset_delta,
                                     "coplanar_within_0p01_mm": True},
        "web_prisms": {side: summary(shape) for side, shape in profiles.items()},
        "clearances": checks,
        "scope": "local keep-outs, candidate mesh topology, and anti-slip contact-plane geometry only; not structural certification or full legacy equivalence",
    }
    print("REAR_SHELL_LOWER_WEB_CLEARANCE_AUDIT=" + json.dumps(result, sort_keys=True))
finally:
    for doc in reversed(opened):
        try:
            App.closeDocument(doc.Name)
        except Exception:
            pass
