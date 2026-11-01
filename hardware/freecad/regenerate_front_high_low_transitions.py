"""Regenerate the front-shell high-to-low mounting transitions.

Run with FreeCADCmd or the FreeCAD Python console.  The script deliberately
leaves the four legacy AdditiveLoft features suppressed.  It derives stable
coordinates from their source sketches, builds downstream closed loft solids,
and uses a 0.10 mm radial overlap to avoid coincident-face Boolean failures on
the right side.
"""

import math
import os

import FreeCAD as App
import Part


DEFAULT_PATH = "/private/tmp/pendant-hardware-integration/hardware/freecad/pendant.FCStd"
DOC_PATH = os.environ.get("PENDANT_FCSTD", DEFAULT_PATH)
FEATURE_NAME = "FrontHighToLowTransitions"
BASE_NAME = "FrontBossToWallLoadPaths"


def circle_wire(x, y, z, radius):
    edge = Part.makeCircle(radius, App.Vector(x, y, z), App.Vector(0, 0, 1))
    return Part.Wire([edge])


def loft(a, b, radial_overlap=0.0):
    aw = circle_wire(a[0], a[1], a[2], a[3] + radial_overlap)
    bw = circle_wire(b[0], b[1], b[2], b[3] + radial_overlap)
    return Part.makeLoft([aw, bw], True, False)


def removed_volume(feature):
    if not feature or not getattr(feature, "BaseFeature", None):
        return None
    base_shape = feature.BaseFeature.Shape
    if base_shape.isNull() or feature.Shape.isNull():
        return None
    return base_shape.cut(feature.Shape)


def cut_clearances(shape, document):
    result = shape
    for name in ("Hole", "FaceplateM2ReceivingHoles", "DisplayBracketM2Threads"):
        cutter = removed_volume(document.getObject(name))
        if cutter and not cutter.isNull():
            result = result.cut(cutter)
    return result


def add_property(obj, prop_type, name, value):
    if name not in obj.PropertiesList:
        obj.addProperty(prop_type, name, "Transition parameters")
    setattr(obj, name, value)


doc = App.openDocument(DOC_PATH) if not App.ActiveDocument else App.ActiveDocument
if os.path.realpath(doc.FileName) != os.path.realpath(DOC_PATH):
    doc = App.openDocument(DOC_PATH)

body = doc.getObject("Body")
base_obj = doc.getObject(BASE_NAME)
if not body or not base_obj:
    raise RuntimeError("Body_FrontShell or its validated tip is missing")
if body.Tip not in (base_obj, doc.getObject(FEATURE_NAME)):
    raise RuntimeError("Unexpected Body_FrontShell tip: %s" % body.Tip.Name)

for legacy_name in (
    "MiddleLeftSupportTransition",
    "MiddleRightSupportTransition",
    "LowerLeftSupportTransition",
    "LowerRightSupportTransition",
):
    legacy = doc.getObject(legacy_name)
    if not legacy or not legacy.Suppressed:
        raise RuntimeError("Legacy transition must remain suppressed: %s" % legacy_name)

base = base_obj.Shape.Solids[0]
if not base.isValid() or len(base.Solids) != 1:
    raise RuntimeError("Validated front baseline is not one valid solid")

# Existing sketch coordinates: lower screw support to taller faceplate boss.
pairs = (
    ("left", (-27.0, 58.5, -14.0, 7.0), (-26.0, 65.0, -10.0, 5.1)),
    ("right", (27.0, 58.5, -14.0, 7.0), (26.0, 65.0, -10.0, 5.1)),
)

current = base
added_volumes = []
for side, low, high in pairs:
    exact = loft(low, high)
    expanded = loft(low, high, 0.10)
    # The full 0.10 mm overlap is below normal FDM dimensional tolerance and
    # makes the coincident cylindrical interface Boolean-stable.  Hole tools
    # are applied afterward, so mounting passages retain their exact geometry.
    candidate = expanded
    candidate = cut_clearances(candidate, doc)
    before = current.Volume
    fused = current.fuse(candidate)
    print(
        side,
        "exact/overlap-delta/candidate/common/solids:",
        exact.Volume,
        expanded.Volume - exact.Volume,
        candidate.Volume,
        candidate.common(current).Volume,
        len(fused.Solids),
        flush=True,
    )
    if not fused.isValid() or len(fused.Solids) != 1:
        raise RuntimeError("%s transition did not fuse into one valid solid" % side)
    added_volumes.append(fused.Volume - before)
    current = fused

feature = doc.getObject(FEATURE_NAME)
if not feature:
    feature = body.newObject("PartDesign::Feature", FEATURE_NAME)
feature.Label = "Front high-to-low mounting transitions"
feature.Shape = current

rise = abs(pairs[0][2][2] - pairs[0][1][2])
run = math.dist(pairs[0][1][:2], pairs[0][2][:2])
angle = math.degrees(math.atan2(rise, run))
wall_facing_run = run - abs(pairs[0][1][3] - pairs[0][2][3])
wall_facing_angle = math.degrees(math.atan2(rise, wall_facing_run))
add_property(feature, "App::PropertyLength", "TransitionRise", rise)
add_property(feature, "App::PropertyLength", "TransitionRun", run)
add_property(feature, "App::PropertyAngle", "TransitionAngle", angle)
add_property(feature, "App::PropertyLength", "WallFacingRun", wall_facing_run)
add_property(feature, "App::PropertyAngle", "WallFacingAngle", wall_facing_angle)
add_property(feature, "App::PropertyLength", "BooleanOverlap", 0.10)
add_property(feature, "App::PropertyFloatList", "AddedVolumes", added_volumes)
add_property(feature, "App::PropertyString", "RegenerationScript", "hardware/freecad/regenerate_front_high_low_transitions.py")
add_property(
    feature,
    "App::PropertyString",
    "DesignNote",
    "Downstream closed lofts joining the front middle screw supports to the taller adjacent faceplate bosses. Legacy AdditiveLofts remain suppressed; actual hole volumes are subtracted before fusion.",
)

body.Tip = feature
base_obj.Visibility = False
feature.Visibility = True
doc.recompute()

if not body.Shape.isValid() or len(body.Shape.Solids) != 1:
    raise RuntimeError("Body_FrontShell failed final solid validation")

for name in ("Hole", "FaceplateM2ReceivingHoles", "DisplayBracketM2Threads"):
    cutter = removed_volume(doc.getObject(name))
    if cutter:
        baseline_clearance = base.common(cutter).Volume
        final_clearance = body.Shape.common(cutter).Volume
        if final_clearance - baseline_clearance > 1e-5:
            raise RuntimeError("Clearance obstruction introduced at %s" % name)

doc.recompute()
doc.saveAs(DOC_PATH)
print("Front transitions regenerated")
print("Added volumes:", added_volumes)
print("Center run/rise/angle:", run, rise, angle)
print("Wall-facing run/angle:", wall_facing_run, wall_facing_angle)
print("Front solid:", body.Shape.isValid(), len(body.Shape.Solids), body.Shape.Volume)
print("Saved:", DOC_PATH)
