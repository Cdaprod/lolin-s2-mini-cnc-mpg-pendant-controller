"""Restore an obvious, editable master for the display-retainer footprint.

The fitted retainer tip is a validated generated BRep.  This script preserves it
and creates a native Sketch + Pad source body from the exact pre-clearance pad
profile, then links the production body to that editable source.
"""

import os
import FreeCAD as App
import Draft


DEFAULT_DOC = os.path.join(os.path.dirname(__file__), "pendant.FCStd")
DOC_PATH = os.environ.get("PENDANT_FCSTD", DEFAULT_DOC)


def add_property(obj, kind, name, group, description):
    if name not in obj.PropertiesList:
        obj.addProperty(kind, name, group, description)


doc = App.openDocument(DOC_PATH)
production = doc.getObject("Body_DisplayRetainer")
source_pad = doc.getObject("DisplayRetainerFlatPrintablePad")
if production is None or source_pad is None:
    raise RuntimeError("Display-retainer production body or flat pad is missing")

before = production.Tip.Shape.copy()

editable = doc.getObject("Body_DisplayRetainer_EditSource")
if editable is None:
    editable = doc.addObject("PartDesign::Body", "Body_DisplayRetainer_EditSource")
editable.Label = "Display Retainer — EDITABLE SOURCE"
part = doc.getObject("Part")
if part is not None and editable not in part.Group:
    part.addObject(editable)

master = doc.getObject("DisplayRetainer_MasterOutline")
if master is None:
    horizontal = []
    for face in source_pad.Shape.Faces:
        try:
            normal = face.normalAt(0, 0)
        except Exception:
            continue
        if normal.z < -0.999999 and abs(face.BoundBox.ZLength) < 1e-6:
            horizontal.append(face)
    if not horizontal:
        raise RuntimeError("Could not locate the flat pad's lower profile face")
    profile_face = max(horizontal, key=lambda face: face.Area)
    master = Draft.makeSketch(profile_face.Wires, autoconstraints=True, name="DisplayRetainer_MasterOutline")
    editable.addObject(master)
    master.Placement.Base.z = profile_face.BoundBox.ZMin
master.Label = "MASTER — Display Retainer Outline (EDIT THIS SKETCH)"

pad = doc.getObject("DisplayRetainer_MasterPad")
if pad is None:
    pad = editable.newObject("PartDesign::Pad", "DisplayRetainer_MasterPad")
    pad.Profile = master
pad.Label = "Editable Display Retainer Pad"
pad.Length = 3.0
pad.Refine = True

add_property(editable, "App::PropertyString", "EditInstructions", "Manual Editing",
             "How to edit the display-retainer source")
editable.EditInstructions = (
    "Double-click MASTER — Display Retainer Outline, edit the footprint and holes, "
    "then recompute. The fitted production output remains preserved until its shell-clearance step is regenerated."
)
add_property(production, "App::PropertyString", "EditInstructions", "Manual Editing",
             "How to edit this generated display retainer")
production.EditInstructions = (
    "Edit Body_DisplayRetainer_EditSource / MASTER — Display Retainer Outline. "
    "This body's last four stages are generated clearance shapes and intentionally remain the validated output."
)
add_property(production, "App::PropertyString", "EditableSource", "Manual Editing",
             "Names of the native editable source body and sketch")
production.EditableSource = "Body_DisplayRetainer_EditSource / DisplayRetainer_MasterOutline"

doc.recompute()
if not pad.Shape.isValid() or len(pad.Shape.Solids) != 1:
    raise RuntimeError("Editable master pad did not recompute as one valid solid")
after = production.Tip.Shape
if not after.isValid() or len(after.Solids) != 1:
    raise RuntimeError("Production display retainer is no longer one valid solid")
delta = before.cut(after).Volume + after.cut(before).Volume
if delta > 1e-7:
    raise RuntimeError(f"Production display-retainer geometry changed by {delta:.9f} mm^3")

master.Visibility = True
pad.Visibility = True
editable.Visibility = True
production.Visibility = False

doc.recompute()
doc.saveAs(DOC_PATH)
print("saved", DOC_PATH)
print("production", production.Tip.Name, after.isValid(), len(after.Solids), after.Volume)
print("editable", master.Name, master.GeometryCount, pad.Shape.isValid(), len(pad.Shape.Solids), pad.Shape.Volume)
print("production_delta_mm3", delta)
