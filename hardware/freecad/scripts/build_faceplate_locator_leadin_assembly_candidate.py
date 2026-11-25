"""Repoint both locator links in a disposable assembly and cold-validate it."""
import FreeCAD as App
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSEMBLY_SOURCE = os.path.join(ROOT, "pendant-modular-retainer-leadin-candidate.FCStd")
ASSEMBLY_CANDIDATE = os.path.join(ROOT, "pendant-modular-locator-leadin-candidate.FCStd")
LOCATOR_SOURCE = os.path.join(ROOT, "pendant-bodies", "faceplate-locators-leadin-candidate.FCStd")
RETAINER_SOURCE = os.path.join(ROOT, "pendant-bodies", "display-retainer-mounting-leadin-candidate.FCStd")
REPORT = os.path.join(ROOT, "reports", "faceplate-locator-assembly-link-validation.json")

if os.path.exists(ASSEMBLY_CANDIDATE):
    raise RuntimeError("Refusing to overwrite existing candidate: " + ASSEMBLY_CANDIDATE)

locators = App.openDocument(LOCATOR_SOURCE)
retainer = App.openDocument(RETAINER_SOURCE)
assembly = App.openDocument(ASSEMBLY_SOURCE)
for link_name, body_name in (("Editable_Body_FaceplateLocator_A", "Body_FaceplateLocator_A"),
                             ("Editable_Body_FaceplateLocator_B", "Body_FaceplateLocator_B")):
    link = assembly.getObject(link_name)
    original = link.Placement
    link.LinkedObject = locators.getObject(body_name)
    assembly.recompute()
    if link.LinkedObject is None or link.LinkedObject.Name != body_name:
        raise RuntimeError("Link did not resolve to " + body_name)
    if (link.Placement.Base - original.Base).Length > 1e-8 or link.Placement.Rotation.Angle > 1e-8:
        raise RuntimeError("Placement changed for " + link_name)
assembly.recompute()
assembly.saveAs(ASSEMBLY_CANDIDATE)
App.closeDocument(assembly.Name)
App.closeDocument(locators.Name)
App.closeDocument(retainer.Name)

# A separate open after save proves that stored link paths and geometry reload.
assembly = App.openDocument(ASSEMBLY_CANDIDATE)
assembly.recompute()
links = []
for obj in assembly.Objects:
    if obj.TypeId != "App::Link":
        continue
    target = obj.LinkedObject
    if target is None or target.Shape.isNull() or not target.Shape.isValid() or len(target.Shape.Solids) != 1:
        raise RuntimeError("Unresolved or invalid component link: " + obj.Name)
    links.append({"name": obj.Name, "target": target.Name,
                  "document": target.Document.FileName,
                  "placement_mm": [obj.Placement.Base.x, obj.Placement.Base.y, obj.Placement.Base.z],
                  "volume_mm3": target.Shape.Volume, "solids": len(target.Shape.Solids)})
root = assembly.getObject("AssemblyRoot")
if root is None or root.Shape.isNull() or not root.Shape.isValid() or len(root.Shape.Solids) != 9:
    raise RuntimeError("AssemblyRoot is invalid or has an unexpected solid count")
bb = root.Shape.BoundBox
result = {"candidate": ASSEMBLY_CANDIDATE, "links": links,
          "root": {"valid": root.Shape.isValid(), "solids": len(root.Shape.Solids),
                   "volume_mm3": root.Shape.Volume,
                   "bounds_mm": [bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax]}}
with open(REPORT, "w") as f:
    json.dump(result, f, indent=2)
    f.write("\n")
assembly.save()
App.closeDocument(assembly.Name)
print(json.dumps(result, indent=2))
