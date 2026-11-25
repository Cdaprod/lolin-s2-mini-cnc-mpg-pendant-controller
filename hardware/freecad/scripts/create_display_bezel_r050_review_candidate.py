"""Create a disposable R0.50 mm native display-bezel review candidate.

Run under FreeCAD's Python runtime. The script copies the validated R0.30
hybrid candidate and its linked review assembly to new paths, changes only the
spreadsheet-driven fillet radius, retargets the assembly App::Link, and performs
cold-open checks. It refuses to overwrite either output.
"""
import json
import os
import shutil

import FreeCAD as App
import MeshPart


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SOURCE_DIR = os.path.join(ROOT, "master-driven-leadins-candidate")
SOURCE_COMPONENT = os.path.join(
    SOURCE_DIR, "pendant-bodies", "upper-faceplate-bezel-hybrid-candidate.FCStd"
)
SOURCE_ASSEMBLY = os.path.join(
    SOURCE_DIR, "pendant-modular-assembly-live-bezel-candidate.FCStd"
)
OUT_COMPONENT = os.path.join(
    SOURCE_DIR, "pendant-bodies", "upper-faceplate-bezel-hybrid-r0p50-review.FCStd"
)
OUT_ASSEMBLY = os.path.join(
    SOURCE_DIR, "pendant-modular-assembly-bezel-r0p50-review.FCStd"
)


def metrics(shape):
    box = shape.BoundBox
    return {
        "valid": bool(shape.isValid()),
        "solids": len(shape.Solids),
        "volume_mm3": shape.Volume,
        "area_mm2": shape.Area,
        "faces": len(shape.Faces),
        "bounds_mm": [box.XMin, box.XMax, box.YMin, box.YMax, box.ZMin, box.ZMax],
    }


def close(doc):
    if doc and App.getDocument(doc.Name):
        App.closeDocument(doc.Name)


if os.path.exists(OUT_COMPONENT) or os.path.exists(OUT_ASSEMBLY):
    raise RuntimeError("Refusing to overwrite an existing review candidate")
shutil.copy2(SOURCE_COMPONENT, OUT_COMPONENT)
shutil.copy2(SOURCE_ASSEMBLY, OUT_ASSEMBLY)

component = App.openDocument(OUT_COMPONENT)
component.recompute()
body = component.getObject("UpperFaceplateBezel")
fillet = component.getObject("DisplayBezelSoftEdge")
params = component.getObject("BezelParameters")
if not (body and fillet and params and body.Tip == fillet):
    raise RuntimeError("Source hybrid bezel structure is incomplete")
before = fillet.Shape.copy()
params.set("B2", "0.5 mm")
component.recompute()
after = fillet.Shape.copy()
if not after.isValid() or len(after.Solids) != 1:
    raise RuntimeError("R0.50 mm native fillet did not produce one valid solid")
if any(abs(a - b) > 1e-7 for a, b in zip(
    (before.BoundBox.XMin, before.BoundBox.XMax, before.BoundBox.YMin,
     before.BoundBox.YMax, before.BoundBox.ZMin, before.BoundBox.ZMax),
    (after.BoundBox.XMin, after.BoundBox.XMax, after.BoundBox.YMin,
     after.BoundBox.YMax, after.BoundBox.ZMin, after.BoundBox.ZMax),
)):
    raise RuntimeError("Fillet changed the component envelope")
removed = before.cut(after)
added = after.cut(before)
if not removed.isValid() or not added.isValid() or removed.Volume <= 0 or added.Volume > 1e-5:
    raise RuntimeError("Unexpected material difference from the fillet")
mesh = MeshPart.meshFromShape(
    Shape=after, LinearDeflection=0.12, AngularDeflection=0.25, Relative=False
)
if not mesh.isSolid():
    raise RuntimeError("R0.50 mesh is not closed")
component.save()
close(component)

component = App.openDocument(OUT_COMPONENT)
component.recompute()
body = component.getObject("UpperFaceplateBezel")
fillet = component.getObject("DisplayBezelSoftEdge")
if body.Tip != fillet or abs(fillet.Radius.Value - 0.5) > 1e-9:
    raise RuntimeError("Cold-open component did not retain the native R0.50 feature")
cold_shape = fillet.Shape.copy()
if not cold_shape.isValid() or len(cold_shape.Solids) != 1:
    raise RuntimeError("Cold-open component is not one valid solid")

assembly = App.openDocument(OUT_ASSEMBLY)
assembly.recompute()
link = assembly.getObject("Editable_UpperFaceplateBezel")
if link is None:
    raise RuntimeError("Review assembly does not contain the bezel link")
placement = link.LinkPlacement
link.LinkedObject = body
link.LinkPlacement = placement
assembly.recompute()
if not link.Shape.isValid() or len(link.Shape.Solids) != 1:
    raise RuntimeError("Retargeted assembly link is invalid")
assembly.save()
close(assembly)
close(component)

assembly = App.openDocument(OUT_ASSEMBLY)
assembly.recompute()
link = assembly.getObject("Editable_UpperFaceplateBezel")
links = [obj for obj in assembly.Objects if obj.TypeId == "App::Link"]
broken = [obj.Name for obj in links if not obj.LinkedObject or obj.Shape.isNull()]
if broken or not link or not link.Shape.isValid() or abs(link.Shape.Volume - cold_shape.Volume) > 1e-7:
    raise RuntimeError("Cold-open assembly link validation failed: " + repr(broken))

print("BEZEL_R050_REVIEW=" + json.dumps({
    "component": OUT_COMPONENT,
    "assembly": OUT_ASSEMBLY,
    "native_parameter": "BezelParameters.DisplayBezelFilletRadius",
    "before_R0p30": metrics(before),
    "after_R0p50": metrics(cold_shape),
    "removed_volume_mm3": removed.Volume,
    "added_volume_mm3": added.Volume,
    "closed_mesh": bool(mesh.isSolid()),
    "assembly_links": len(links),
    "broken_links": broken,
    "cold_open_recompute": "passed",
    "production_documents_modified": False,
}, sort_keys=True))
close(assembly)
