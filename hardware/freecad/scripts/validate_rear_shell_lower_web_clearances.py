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
        "web_prisms": {side: summary(shape) for side, shape in profiles.items()},
        "clearances": checks,
        "scope": "geometric keep-out validation only; not structural certification or full legacy equivalence",
    }
    print("REAR_SHELL_LOWER_WEB_CLEARANCE_AUDIT=" + json.dumps(result, sort_keys=True))
finally:
    for doc in reversed(opened):
        try:
            App.closeDocument(doc.Name)
        except Exception:
            pass
