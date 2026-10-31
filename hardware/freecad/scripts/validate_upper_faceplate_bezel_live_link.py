"""Bounded validation for the disposable live upper-faceplate bezel candidate."""
import json
import os
from pathlib import Path

import FreeCAD as App

ROOT = Path(__file__).resolve().parents[1]
ASSEMBLY = ROOT / "master-driven-leadins-candidate" / "pendant-modular-assembly-live-bezel-candidate.FCStd"
REPORT = ROOT / "reports" / "upper-faceplate-live-bezel-candidate-validation-2026-10-31.json"


def metrics(shape):
    bb = shape.BoundBox
    return {"valid": bool(not shape.isNull() and shape.isValid()),
            "solids": len(shape.Solids), "volume_mm3": shape.Volume,
            "bounds_mm": [bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax]}


def symdiff(a, b):
    return a.cut(b).Volume + b.cut(a).Volume


doc = App.openDocument(str(ASSEMBLY))
root = doc.getObject("AssemblyRoot")
link = doc.getObject("Editable_UpperFaceplateBezel")
if root is None or link is None:
    raise RuntimeError("Candidate assembly is missing its root or live bezel link")
target = link.getLinkedObject(True)
if target is None:
    raise RuntimeError("Candidate bezel link failed to resolve")
component = target.Document
body = component.getObject("UpperFaceplateBezel")
fillet = component.getObject("DisplayBezelSoftEdge")
sheet = component.getObject("BezelParameters")
if body.Tip != fillet or fillet.ExpressionEngine != [("Radius", "BezelParameters.DisplayBezelFilletRadius")]:
    raise RuntimeError("Native bezel feature or radius expression is missing")

nominal_link = link.Shape.copy()
nominal_root = metrics(root.Shape)
if not fillet.Shape.isValid() or len(fillet.Shape.Solids) != 1:
    raise RuntimeError("Nominal native bezel Tip is invalid")

sheet.set("B2", "0.35 mm")
component.recompute()
doc.recompute()
perturbed_link = link.Shape.copy()
perturbed_root = metrics(root.Shape)
if abs(perturbed_link.Volume - nominal_link.Volume) < 1e-5:
    raise RuntimeError("Bezel parameter did not change the linked component")
if abs(perturbed_root["volume_mm3"] - nominal_root["volume_mm3"]) < 1e-5:
    raise RuntimeError("Bezel parameter did not propagate to the assembly root")

sheet.set("B2", "0.30 mm")
component.recompute()
doc.recompute()
restored_link = link.Shape.copy()
restored_root = metrics(root.Shape)
restored_link_diff = symdiff(restored_link, nominal_link)
if restored_link_diff > 1e-5:
    raise RuntimeError("Bezel link failed exact shape restoration")
if (abs(restored_root["volume_mm3"] - nominal_root["volume_mm3"]) > 1e-5 or
        restored_root["bounds_mm"] != nominal_root["bounds_mm"]):
    raise RuntimeError("Assembly root failed volume/bounds restoration")
if not root.Shape.isValid() or len(root.Shape.Solids) != 9:
    raise RuntimeError("Restored assembly root is invalid")

component.save()
doc.save()
result = {
    "status": "passed_parameter_refresh_and_restore",
    "component_file": os.path.relpath(component.FileName, str(ROOT)),
    "assembly_file": os.path.relpath(doc.FileName, str(ROOT)),
    "native_tip": fillet.Name,
    "radius_expression": "BezelParameters.DisplayBezelFilletRadius",
    "nominal_radius_mm": 0.30,
    "perturbed_radius_mm": 0.35,
    "nominal_link": metrics(nominal_link),
    "perturbed_link": metrics(perturbed_link),
    "restored_link_symdiff_mm3": restored_link_diff,
    "nominal_root": nominal_root,
    "perturbed_root": perturbed_root,
    "restored_root": restored_root,
    "links": sum(o.TypeId == "App::Link" for o in doc.Objects),
    "static_interim_shapes": sum(o.Name.startswith("Interim_") and o.TypeId != "App::Link" for o in doc.Objects),
    "assembly_root_solids": len(root.Shape.Solids),
    "cold_open_recompute": "verified separately in a fresh FreeCADCmd process",
    "production_documents_modified": False,
}
REPORT.write_text(json.dumps(result, indent=2) + "\n")
print("BEZEL_LIVE_VALIDATION=" + json.dumps(result, sort_keys=True), flush=True)
