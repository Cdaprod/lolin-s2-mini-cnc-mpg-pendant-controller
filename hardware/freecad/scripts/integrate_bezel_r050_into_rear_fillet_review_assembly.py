"""Combine the R0.50 bezel with the structural rear-shell review assembly.

Run inside FreeCAD's Python runtime. The script copies a review assembly to a
new file, replaces its static upper-faceplate member with an App::Link to the
R0.50 hybrid component, and cold-opens the saved result. Existing output files
are never overwritten; the protected monolith and production assembly are not
opened for writing.
"""
import json
import os
import shutil

import FreeCAD as App


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SOURCE_ASSEMBLY = os.path.join(
    ROOT, "pendant-modular-structural-first-fillet-no-duplicate-review-assembly-2026-10-31.FCStd"
)
SOURCE_COMPONENT = os.path.join(
    ROOT, "master-driven-leadins-candidate", "pendant-bodies",
    "upper-faceplate-bezel-hybrid-r0p50-review.FCStd"
)
OUTPUT = os.path.join(
    ROOT, "pendant-modular-structural-first-fillet-bezel-r0p50-review-assembly-2026-10-31.FCStd"
)


def close(doc):
    if doc and App.getDocument(doc.Name):
        App.closeDocument(doc.Name)


def metrics(shape):
    box = shape.BoundBox
    return {
        "valid": bool(shape.isValid()),
        "solids": len(shape.Solids),
        "volume_mm3": shape.Volume,
        "bounds_mm": [box.XMin, box.XMax, box.YMin, box.YMax, box.ZMin, box.ZMax],
    }


if os.path.exists(OUTPUT):
    raise FileExistsError("Refusing to overwrite review assembly: " + OUTPUT)
if not os.path.isfile(SOURCE_ASSEMBLY) or not os.path.isfile(SOURCE_COMPONENT):
    raise FileNotFoundError("A saved source review document is missing")
shutil.copy2(SOURCE_ASSEMBLY, OUTPUT)

assembly = App.openDocument(OUTPUT)
assembly.recompute()
root = assembly.getObject("AssemblyRoot")
faceplate_group = assembly.getObject("FaceplateModule")
old_faceplate = assembly.getObject("Interim_Body003")
if not (root and faceplate_group and old_faceplate):
    raise RuntimeError("Expected review assembly objects are missing")
root_before = metrics(root.Shape)
old_shape = old_faceplate.Shape.copy()
source = App.openDocument(SOURCE_COMPONENT)
source.recompute()
bezel_body = source.getObject("UpperFaceplateBezel")
if not bezel_body or not bezel_body.Tip or not bezel_body.Tip.Shape.isValid():
    raise RuntimeError("R0.50 bezel component failed recompute")

link = assembly.addObject("App::Link", "Editable_UpperFaceplateBezelR050")
link.Label = "Upper faceplate — hybrid native R0.50 bezel review link"
link.LinkedObject = bezel_body
link.LinkPlacement = old_faceplate.Placement
faceplate_group.removeObject(old_faceplate)
faceplate_group.addObject(link)
assembly.recompute()
if not link.Shape.isValid() or len(link.Shape.Solids) != 1:
    raise RuntimeError("Faceplate App::Link is invalid")
if len(root.Shape.Solids) != root_before["solids"]:
    raise RuntimeError("Assembly solid count changed")

neighbor_names = (
    "Interim_EncoderFaceplatePocketUnsplit", "Editable_Body_FaceplateLocator_A",
    "Editable_Body_FaceplateLocator_B", "Editable_Body_DisplayRetainer_EditableV2",
    "Editable_Body_USBTetheredCover", "Editable_Body006", "Interim_Body002",
    "Review_AntiSlipPadUpper", "Review_AntiSlipPadLower", "Interim_Body",
)
intersections = []
for name in neighbor_names:
    other = assembly.getObject(name)
    if not other or other.Shape.isNull():
        continue
    baseline = old_shape.common(other.Shape)
    candidate = link.Shape.common(other.Shape)
    delta = candidate.Volume - baseline.Volume
    if not baseline.isValid() or not candidate.isValid() or abs(delta) > 1e-5:
        raise RuntimeError("Faceplate change alters intersection with " + name)
    intersections.append({
        "neighbor": name,
        "baseline_intersection_mm3": baseline.Volume,
        "candidate_intersection_mm3": candidate.Volume,
        "delta_mm3": delta,
    })

expected_volume_delta = link.Shape.Volume - old_shape.Volume
root_after = metrics(root.Shape)
root_volume_delta = root_after["volume_mm3"] - root_before["volume_mm3"]
if abs(root_volume_delta - expected_volume_delta) > 0.02:
    raise RuntimeError("Assembly aggregate volume delta exceeds tolerance")
assembly.recompute()
assembly.save()
close(assembly)
close(source)

assembly = App.openDocument(OUTPUT)
assembly.recompute()
root = assembly.getObject("AssemblyRoot")
link = assembly.getObject("Editable_UpperFaceplateBezelR050")
links = [obj for obj in assembly.Objects if obj.TypeId == "App::Link"]
broken = [obj.Name for obj in links if not obj.LinkedObject or obj.Shape.isNull()]
if broken or not root.Shape.isValid() or len(root.Shape.Solids) != root_before["solids"]:
    raise RuntimeError("Cold-open assembly validation failed: " + repr(broken))

print("COMBINED_REVIEW_ASSEMBLY=" + json.dumps({
    "assembly": OUTPUT,
    "component": SOURCE_COMPONENT,
    "root_before": root_before,
    "root_after_reopen": metrics(root.Shape),
    "root_volume_delta_mm3": root_volume_delta,
    "expected_faceplate_delta_mm3": expected_volume_delta,
    "faceplate": metrics(link.Shape),
    "app_link_count": len(links),
    "broken_links": broken,
    "neighbor_intersections": intersections,
    "cold_open_recompute": "passed",
    "production_documents_modified": False,
}, sort_keys=True))
close(assembly)
