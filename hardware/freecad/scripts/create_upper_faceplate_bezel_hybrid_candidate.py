"""Make a disposable live-link faceplate candidate with an editable bezel fillet.

The input upper-faceplate history is still static, so the output is explicitly
hybrid: a static comparison base plus a native PartDesign Fillet and a local
Spreadsheet parameter. No production document is saved or modified.
"""
import json
import os
import shutil
from pathlib import Path

import FreeCAD as App
import Part

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_ROOT = ROOT / "master-driven-leadins-candidate"
BODY_DIR = CANDIDATE_ROOT / "pendant-bodies"
ASSEMBLY_SOURCE = CANDIDATE_ROOT / "pendant-modular-assembly.FCStd"
SOURCE_ASSEMBLY = ROOT / "pendant-modular-assembly.FCStd"
COMPONENT = BODY_DIR / "upper-faceplate-bezel-hybrid-candidate.FCStd"
ASSEMBLY = CANDIDATE_ROOT / "pendant-modular-assembly-live-bezel-candidate.FCStd"
REPORT = ROOT / "reports" / "upper-faceplate-bezel-live-link-validation-2026-10-31.json"
RADIUS = 0.30
PERTURBED_RADIUS = 0.35

for path in (COMPONENT, ASSEMBLY):
    if path.exists():
        raise RuntimeError("Refusing to overwrite candidate: " + str(path))

def metrics(shape):
    bb = shape.BoundBox
    return {"valid": bool(not shape.isNull() and shape.isValid()),
            "solids": len(shape.Solids), "volume_mm3": shape.Volume,
            "area_mm2": shape.Area, "faces": len(shape.Faces),
            "bounds_mm": [bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax]}

def require_one(shape, label):
    if shape.isNull() or not shape.isValid() or len(shape.Solids) != 1:
        raise RuntimeError(label + " is not one valid solid")

def symdiff(a, b):
    return a.cut(b).Volume + b.cut(a).Volume

# The starting assembly contains the pre-fillet upper-faceplate shape and is
# the exact geometry source for the already validated bezel-edge treatment.
src = App.openDocument(str(SOURCE_ASSEMBLY))
source_obj = src.getObject("Interim_Body003")
if source_obj is None:
    raise RuntimeError("Source assembly upper faceplate interim shape is missing")
base_shape = source_obj.Shape.copy()
source_placement = source_obj.Placement
require_one(base_shape, "source upper faceplate")
source_metrics = metrics(base_shape)
App.closeDocument(src.Name)

# Build a compact hybrid component. The imported base remains explicitly
# identified as static; the edge treatment and its radius stay native/editable.
component = App.newDocument("UpperFaceplateBezelHybridCandidate")
body = component.addObject("PartDesign::Body", "UpperFaceplateBezel")
body.Label = "Upper faceplate — hybrid native bezel candidate"
body.Placement = source_placement
base = body.newObject("PartDesign::Feature", "ImportedUpperFaceplateBase")
base.Label = "Imported upper-faceplate comparison base — static"
base.Shape = base_shape
body.Tip = base
component.recompute()

center = (0.0, 2.99855, 4.0)
radii = (20.0, 22.5)
selected = {}
for index, edge in enumerate(base.Shape.Edges, 1):
    curve = getattr(edge, "Curve", None)
    if curve is None or curve.__class__.__name__ != "Circle":
        continue
    c = curve.Center
    if (abs(c.x-center[0]) < 1e-4 and abs(c.y-center[1]) < 1e-3 and
            abs(c.z-center[2]) < 1e-4 and abs(edge.BoundBox.ZMin-center[2]) < 1e-4 and
            abs(edge.BoundBox.ZMax-center[2]) < 1e-4):
        for radius in radii:
            if abs(curve.Radius-radius) < 1e-4:
                selected[radius] = "Edge%d" % index
if set(selected) != set(radii):
    raise RuntimeError("Could not identify both bezel rim edges geometrically: " + repr(selected))

params = component.addObject("Spreadsheet::Sheet", "BezelParameters")
params.Label = "Upper faceplate bezel parameters"
params.set("A1", "Parameter"); params.set("B1", "Value")
params.set("A2", "DisplayBezelFilletRadius"); params.set("B2", str(RADIUS) + " mm")
params.setAlias("B2", "DisplayBezelFilletRadius")
fillet = body.newObject("PartDesign::Fillet", "DisplayBezelSoftEdge")
fillet.Label = "Display bezel soft edge — native R0.30 mm"
fillet.Base = (base, [selected[r] for r in radii])
fillet.setExpression("Radius", "BezelParameters.DisplayBezelFilletRadius")
body.Tip = fillet
component.recompute()
require_one(fillet.Shape, "native bezel fillet")
fillet_shape = fillet.Shape.copy()
removed = base_shape.cut(fillet_shape)
added = fillet_shape.cut(base_shape)
if removed.Volume < 5.0 or removed.Volume > 5.3 or added.Volume > 1e-6:
    raise RuntimeError("Fillet changed unexpected material: removed=%r added=%r" % (removed.Volume, added.Volume))
if metrics(fillet_shape)["bounds_mm"] != source_metrics["bounds_mm"]:
    raise RuntimeError("Native bezel fillet changed the upper-faceplate bounds")

# Reversible native parameter test before saving the restored nominal candidate.
params.set("B2", str(PERTURBED_RADIUS) + " mm")
component.recompute()
require_one(fillet.Shape, "perturbed native bezel fillet")
perturbed_shape = fillet.Shape.copy()
if abs(perturbed_shape.Volume-fillet_shape.Volume) < 1e-5:
    raise RuntimeError("Bezel radius did not propagate through the native feature")
params.set("B2", str(RADIUS) + " mm")
component.recompute()
restored_component_diff = symdiff(fillet.Shape, fillet_shape)
if restored_component_diff > 1e-5:
    raise RuntimeError("Bezel radius did not restore: symdiff=" + str(restored_component_diff))
component.recompute()
component.saveAs(str(COMPONENT))
component_name = component.Name
App.closeDocument(component_name)

# Cold-open the component and verify its native Tip and spreadsheet expression.
component = App.openDocument(str(COMPONENT))
component.recompute()
body = component.getObject("UpperFaceplateBezel")
fillet = component.getObject("DisplayBezelSoftEdge")
params = component.getObject("BezelParameters")
if body.Tip != fillet or not fillet.ExpressionEngine:
    raise RuntimeError("Cold-opened hybrid component lost its native fillet expression")
require_one(fillet.Shape, "cold-opened native bezel fillet")
cold_component_shape = fillet.Shape.copy()
if symdiff(cold_component_shape, fillet_shape) > 1e-5:
    raise RuntimeError("Cold-opened hybrid component differs from its saved native Tip")

# Work on a copy of the six-link, master-driven lead-in assembly.
shutil.copy2(str(ASSEMBLY_SOURCE), str(ASSEMBLY))
for filename in ("pendant-master.FCStd", "pendant-bodies/display-retainer-mounting-leadin-candidate.FCStd",
                 "pendant-bodies/faceplate-locators-leadin-candidate.FCStd",
                 "pendant-bodies/usb-tethered-cover.FCStd", "pendant-bodies/breakout-board.FCStd",
                 "pendant-bodies/rear-shell-loadpath-repair-candidate.FCStd"):
    path = CANDIDATE_ROOT / filename
    name = path.stem.replace("-", "_")
    if name not in App.listDocuments():
        App.openDocument(str(path))
assembly = App.openDocument(str(ASSEMBLY))
old = assembly.getObject("Interim_Body003")
module = assembly.getObject("FaceplateModule")
root = assembly.getObject("AssemblyRoot")
if old is None or module is None or root is None:
    raise RuntimeError("Assembly faceplate module/root not found")
old_shape = old.Shape.copy()
old_placement = old.Placement
if symdiff(old_shape, cold_component_shape) > 1e-5:
    raise RuntimeError("Hybrid component fillet does not match the existing validated assembly faceplate shape")

link = assembly.addObject("App::Link", "Editable_UpperFaceplateBezel")
link.Label = "Upper faceplate — live hybrid bezel component link"
link.LinkedObject = body
link.LinkPlacement = old_placement
module.addObject(link)
if symdiff(link.Shape, old_shape) > 1e-5:
    raise RuntimeError("Live bezel component link does not match the original assembly faceplate")
assembly.removeObject(old.Name)
assembly.recompute()
if not root.Shape.isValid() or len(root.Shape.Solids) != 9:
    raise RuntimeError("Assembly root invalid or changed solid count after live-link replacement")
root_nominal = root.Shape.copy()
root_nominal_metrics = metrics(root_nominal)
if abs(root_nominal.Volume-111841.7739735076) > 1e-5:
    raise RuntimeError("Replacing the interim faceplate changed assembled volume unexpectedly")
assembly.save()
App.closeDocument(assembly.Name)

# Test assembly-level refresh through the editable component link, then restore.
assembly = App.openDocument(str(ASSEMBLY))
root = assembly.getObject("AssemblyRoot")
link = assembly.getObject("Editable_UpperFaceplateBezel")
target = link.getLinkedObject(True)
if target is None or target.Document.FileName != str(COMPONENT):
    raise RuntimeError("Saved assembly link did not resolve to the candidate component file")
body = target
fillet = component.getObject("DisplayBezelSoftEdge")
params = component.getObject("BezelParameters")
params.set("B2", str(PERTURBED_RADIUS) + " mm")
component.recompute(); assembly.recompute()
perturbed_assembly_shape = root.Shape.copy()
if abs(perturbed_assembly_shape.Volume-root_nominal.Volume) < 1e-5:
    raise RuntimeError("Bezel parameter change did not propagate into linked assembly")
perturbed_link_shape = link.Shape.copy()
params.set("B2", str(RADIUS) + " mm")
component.recompute(); assembly.recompute()
restored_link_diff = symdiff(link.Shape, cold_component_shape)
if restored_link_diff > 1e-5:
    raise RuntimeError("Linked bezel component did not restore after parameter reset")
restored_root_metrics = metrics(root.Shape)
if (abs(restored_root_metrics["volume_mm3"]-root_nominal_metrics["volume_mm3"]) > 1e-5 or
        restored_root_metrics["bounds_mm"] != root_nominal_metrics["bounds_mm"]):
    raise RuntimeError("Assembly root volume/bounds did not restore after parameter reset")
assembly.save(); component.save()
final_link_metrics = metrics(link.Shape)
final_root_metrics = metrics(root.Shape)

# Cold-open both files to confirm link and native feature state persist.
for n in (assembly.Name, component.Name):
    if n in App.listDocuments(): App.closeDocument(n)
component = App.openDocument(str(COMPONENT))
assembly = App.openDocument(str(ASSEMBLY))
component.recompute(); assembly.recompute()
body = component.getObject("UpperFaceplateBezel")
fillet = component.getObject("DisplayBezelSoftEdge")
if body.Tip != fillet or not fillet.Shape.isValid() or len(fillet.Shape.Solids) != 1:
    raise RuntimeError("Cold-opened live component native feature history is invalid")
root = assembly.getObject("AssemblyRoot")
link = assembly.getObject("Editable_UpperFaceplateBezel")
target = link.getLinkedObject(True)
if target is None or not root.Shape.isValid() or len(root.Shape.Solids) != 9:
    raise RuntimeError("Cold-opened assembly link/root validation failed")
if target.Document.FileName != str(COMPONENT):
    raise RuntimeError("Cold-opened faceplate link points to an unexpected document")
if abs(root.Shape.Volume-root_nominal.Volume) > 1e-5:
    raise RuntimeError("Cold-opened assembly volume differs from the restored nominal candidate")

result = {
    "candidate_component": os.path.relpath(str(COMPONENT), str(ROOT)),
    "candidate_assembly": os.path.relpath(str(ASSEMBLY), str(ROOT)),
    "candidate_type": "hybrid: imported static pre-fillet base plus native PartDesign Fillet and Spreadsheet radius parameter",
    "source_geometry": "saved Interim_Body003 shape from pendant-modular-assembly.FCStd",
    "native_feature": {"name": "DisplayBezelSoftEdge", "type": fillet.TypeId,
                       "radius_mm": RADIUS, "perturbed_radius_mm": PERTURBED_RADIUS,
                       "selected_edges": [selected[r] for r in radii],
                       "expression": "BezelParameters.DisplayBezelFilletRadius",
                       "base": source_metrics, "nominal_tip": metrics(cold_component_shape),
                       "removed_volume_mm3": removed.Volume, "added_volume_mm3": added.Volume,
                       "component_restore_symdiff_mm3": restored_component_diff},
    "assembly": {"old_static_faceplate_removed": True,
                  "new_live_link": "Editable_UpperFaceplateBezel",
                  "link_target_file": os.path.relpath(str(COMPONENT), str(CANDIDATE_ROOT)),
                  "link_shape": final_link_metrics,
                  "nominal_root": root_nominal_metrics,
                  "cold_reopened_root": metrics(root.Shape),
                  "nominal_replacement_symdiff_mm3": 0.0,
                  "link_parameter_change_propagated": True,
                  "restored_bezel_link_symdiff_mm3": restored_link_diff,
                  "restored_root_volume_bounds_match": True,
                  "cold_reopen_recompute": "passed",
                  "live_link_count": sum(o.TypeId == "App::Link" for o in assembly.Objects),
                  "static_interim_count": sum(o.Name.startswith("Interim_") and o.TypeId != "App::Link" for o in assembly.Objects)},
    "protected_monolith_and_production_assembly_modified": False,
    "limitation": "The faceplate base is imported static geometry, so this is not a complete native faceplate history or fully independent source component. Only the bezel treatment is native and parameter-editable.",
}
REPORT.write_text(json.dumps(result, indent=2) + "\n")
print("UPPER_FACEPLATE_BEZEL_HYBRID=" + json.dumps(result, sort_keys=True))
