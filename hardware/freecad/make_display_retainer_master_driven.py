"""Make the display retainer's active working form entirely sketch-driven.

The legacy fitted retainer is preserved as a hidden reference.  The editable
body is promoted to the visible working retainer and gains a through-pocket
whose rectangular profile clears the XIAO ESP32-S3 header envelope.
"""

import os
import FreeCAD as App
import Part
import Sketcher


DEFAULT_DOC = os.path.join(os.path.dirname(__file__), "pendant.FCStd")
DOC_PATH = os.environ.get("PENDANT_FCSTD", DEFAULT_DOC)

HEADER_X_MIN = -2.0
HEADER_X_MAX = 23.0
HEADER_Y_MIN = -11.0
HEADER_Y_MAX = -6.5
CLEARANCE_NOTE = (
    "Editable through-clearance for the XIAO ESP32-S3 female-header envelope. "
    "Bounds include nominal 1.3 mm side clearance and 0.8 mm fore/aft clearance."
)


def add_property(obj, kind, name, group, description):
    if name not in obj.PropertiesList:
        obj.addProperty(kind, name, group, description)


def set_string(obj, name, value, description):
    add_property(obj, "App::PropertyString", name, "Manual Editing", description)
    setattr(obj, name, value)


doc = App.openDocument(DOC_PATH)
legacy = doc.getObject("Body_DisplayRetainer")
editable = doc.getObject("Body_DisplayRetainer_EditSource")
master = doc.getObject("DisplayRetainer_MasterOutline")
pad = doc.getObject("DisplayRetainer_MasterPad")
if None in (legacy, editable, master, pad):
    raise RuntimeError("Run restore_display_retainer_editability.py before this script")

before_legacy = legacy.Tip.Shape.copy()

sketch = doc.getObject("DisplayRetainer_HeaderClearanceSketch")
if sketch is None:
    sketch = editable.newObject("Sketcher::SketchObject", "DisplayRetainer_HeaderClearanceSketch")
    z = pad.Shape.BoundBox.ZMin
    sketch.Placement.Base = App.Vector(0, 0, z)
    points = [
        App.Vector(HEADER_X_MIN, HEADER_Y_MIN, 0),
        App.Vector(HEADER_X_MAX, HEADER_Y_MIN, 0),
        App.Vector(HEADER_X_MAX, HEADER_Y_MAX, 0),
        App.Vector(HEADER_X_MIN, HEADER_Y_MAX, 0),
    ]
    for i in range(4):
        sketch.addGeometry(Part.LineSegment(points[i], points[(i + 1) % 4]), False)
    for i in range(4):
        sketch.addConstraint(Sketcher.Constraint("Coincident", i, 2, (i + 1) % 4, 1))
sketch.Label = "EDIT — XIAO ESP32-S3 Header Clearance"
set_string(sketch, "DesignIntent", CLEARANCE_NOTE, "Purpose of the editable clearance profile")

pocket = doc.getObject("DisplayRetainer_HeaderClearancePocket")
if pocket is None:
    pocket = editable.newObject("PartDesign::Pocket", "DisplayRetainer_HeaderClearancePocket")
    pocket.Profile = sketch
pocket.Label = "XIAO ESP32-S3 Header Clearance — Through Pocket"
pocket.Length = 3.2
pocket.Reversed = True
pocket.Refine = True
set_string(pocket, "DesignIntent", CLEARANCE_NOTE, "Purpose of the native pocket")

legacy.Label = "Display Retainer — archived fitted BRep (reference)"
set_string(legacy, "EditInstructions",
           "Archived reference only. Edit the master-driven Body_DisplayRetainer — EDITABLE instead.",
           "How to edit the retainer")
editable.Label = "Body_DisplayRetainer — EDITABLE (master-driven)"
set_string(editable, "EditInstructions",
           "Edit MASTER — Display Retainer Outline for the retainer footprint, then edit EDIT — XIAO ESP32-S3 Header Clearance for the electronics opening. Both update this body's native Pad/Pocket chain.",
           "How to edit the retainer")

doc.recompute()
final_shape = pocket.Shape
if not final_shape.isValid() or len(final_shape.Solids) != 1:
    raise RuntimeError("Header-clearance pocket did not form one valid retainer solid")
if not legacy.Tip.Shape.isValid() or len(legacy.Tip.Shape.Solids) != 1:
    raise RuntimeError("Archived fitted retainer was unexpectedly modified")
delta = before_legacy.cut(legacy.Tip.Shape).Volume + legacy.Tip.Shape.cut(before_legacy).Volume
if delta > 1e-7:
    raise RuntimeError(f"Archived fitted retainer changed by {delta:.9f} mm^3")

legacy.Visibility = False
editable.Visibility = True
master.Visibility = False
pad.Visibility = False
sketch.Visibility = False
pocket.Visibility = True
doc.recompute()
doc.saveAs(DOC_PATH)

print("saved", DOC_PATH)
print("editable_tip", pocket.Name, final_shape.isValid(), len(final_shape.Solids), final_shape.Volume)
print("legacy_preserved_delta_mm3", delta)
print("header_clearance", HEADER_X_MIN, HEADER_X_MAX, HEADER_Y_MIN, HEADER_Y_MAX)
