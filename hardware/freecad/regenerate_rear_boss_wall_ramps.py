"""Regenerate the localized 45-degree rear screw-pad-to-wall ramps.

Run this file from FreeCAD's Python console with hardware/freecad/pendant.FCStd
open. The saved feature is a PartDesign::Feature because a native Pad/Pocket
recompute was invalid on this complex BRep. This script rebuilds its shape from
the explicit section dimensions below and the document's actual magnet and M2
clearance volumes.
"""
import Part
from FreeCAD import Vector


doc = App.ActiveDocument
assert doc is not None and doc.FileName.endswith("hardware/freecad/pendant.FCStd"), \
    "Open the authoritative hardware/freecad/pendant.FCStd document first."
body = doc.getObject("Body002")
base_feature = doc.getObject("RearBossShoulderTransitions")
assert body is not None and base_feature is not None

# Section vertices are (X, Z), with equal run and rise for a 45-degree face.
Y_START = 52.0
RAMP_WIDTH = 13.0
WALL_Z = -31.5
BOSS_Z = -26.3
WALL_X_LEFT, BOSS_X_LEFT = -30.0, -24.8
WALL_X_RIGHT, BOSS_X_RIGHT = 30.0, 24.8


def removed_volume(feature_name):
    feature = doc.getObject(feature_name)
    assert feature is not None and feature.BaseFeature is not None
    return feature.BaseFeature.Shape.cut(feature.Shape)


# Use the actual removal volumes already present in the CAD history.
magnet_clearance = removed_volume("Pocket").fuse(removed_volume("Pocket015"))
screw_clearance = removed_volume("Pocket018")
base_shape = base_feature.Shape
assert base_shape.isValid() and len(base_shape.Solids) == 1
base_magnet_intersection = base_shape.common(magnet_clearance).Volume
base_screw_intersection = base_shape.common(screw_clearance).Volume


def make_ramp(wall_x, boss_x):
    points = [
        Vector(wall_x, Y_START, WALL_Z),
        Vector(wall_x, Y_START, BOSS_Z),
        Vector(boss_x, Y_START, BOSS_Z),
        Vector(wall_x, Y_START, WALL_Z),
    ]
    section = Part.Face(Part.Wire(Part.makePolygon(points).Edges))
    raw = section.extrude(Vector(0, RAMP_WIDTH, 0))
    assert raw.isValid() and len(raw.Solids) == 1
    assert raw.common(magnet_clearance).Volume < 1e-6, \
        "Ramp intersects an existing magnet clearance volume."
    ramp = raw.cut(screw_clearance)
    assert ramp.isValid() and len(ramp.Solids) == 1
    assert ramp.common(magnet_clearance).Volume < 1e-6
    assert ramp.common(screw_clearance).Volume < 1e-6
    return ramp


left_ramp = make_ramp(WALL_X_LEFT, BOSS_X_LEFT)
right_ramp = make_ramp(WALL_X_RIGHT, BOSS_X_RIGHT)
result = base_shape.fuse(left_ramp).fuse(right_ramp)
assert result.isValid() and len(result.Solids) == 1
assert result.Volume > base_shape.Volume
assert abs(result.common(magnet_clearance).Volume - base_magnet_intersection) < 1e-5
assert abs(result.common(screw_clearance).Volume - base_screw_intersection) < 1e-5
for axis in ("XMin", "XMax", "YMin", "YMax", "ZMin", "ZMax"):
    assert abs(getattr(result.BoundBox, axis) - getattr(base_shape.BoundBox, axis)) < 1e-5, \
        "Ramp changed the shell's exterior bounding envelope."

feature = doc.getObject("RearBossWallRamps45")
if feature is None:
    feature = body.newObject("PartDesign::Feature", "RearBossWallRamps45")
feature.Label = "Rear screw-pad to wall ramps (45 degrees)"
feature.BaseFeature = base_feature
feature.Shape = result

properties = [
    ("App::PropertyAngle", "RampAngle", "Ramp", "Target ramp angle from horizontal."),
    ("App::PropertyLength", "RampRun", "Ramp", "Horizontal run of each sloped section."),
    ("App::PropertyLength", "RampRise", "Ramp", "Vertical rise of each sloped section."),
    ("App::PropertyLength", "RampWidth", "Ramp", "Extrusion width along Y."),
    ("App::PropertyLength", "StartY", "Ramp", "Start of ramp extrusion along Y."),
    ("App::PropertyLength", "WallLowerZ", "Ramp", "Lower wall-side section elevation."),
    ("App::PropertyLength", "BossUpperZ", "Ramp", "Upper boss-side section elevation."),
    ("App::PropertyLength", "LeftWallX", "Ramp", "Left inner-wall section X coordinate."),
    ("App::PropertyLength", "LeftBossX", "Ramp", "Left boss-side section X coordinate."),
    ("App::PropertyLength", "RightWallX", "Ramp", "Right inner-wall section X coordinate."),
    ("App::PropertyLength", "RightBossX", "Ramp", "Right boss-side section X coordinate."),
    ("App::PropertyString", "ClearanceSources", "Ramp", "Existing CAD features used to preserve clearances."),
    ("App::PropertyString", "RegenerationMethod", "Ramp", "Script used to regenerate this generated shape."),
    ("App::PropertyString", "DesignNote", "Ramp", "Purpose and validation notes."),
]
for type_id, name, group, doc_text in properties:
    if name not in feature.PropertiesList:
        feature.addProperty(type_id, name, group, doc_text)
feature.RampAngle = 45.0
feature.RampRun = abs(BOSS_X_LEFT - WALL_X_LEFT)
feature.RampRise = abs(BOSS_Z - WALL_Z)
feature.RampWidth = RAMP_WIDTH
feature.StartY = Y_START
feature.WallLowerZ = WALL_Z
feature.BossUpperZ = BOSS_Z
feature.LeftWallX = WALL_X_LEFT
feature.LeftBossX = BOSS_X_LEFT
feature.RightWallX = WALL_X_RIGHT
feature.RightBossX = BOSS_X_RIGHT
feature.ClearanceSources = "Pocket, Pocket015 (magnet wells); Pocket018 (M2 passages)"
feature.RegenerationMethod = "hardware/freecad/regenerate_rear_boss_wall_ramps.py"
feature.DesignNote = "Localized 45-degree triangular transitions from rear screw-pad regions toward the inner wall. Ramp material is cut by the actual M2 passage volume. The magnet clearance tool does not intersect either ramp."
body.Tip = feature
doc.recompute()
assert feature.Shape.isValid() and len(feature.Shape.Solids) == 1
assert abs(feature.Shape.Volume - result.Volume) < 1e-5
print("RearBossWallRamps45 regenerated:", len(feature.Shape.Solids), "solid; volume", feature.Shape.Volume)
print("Run/rise:", feature.RampRun, feature.RampRise, "mm; angle", feature.RampAngle)
print("Magnet interference delta:", feature.Shape.common(magnet_clearance).Volume - base_magnet_intersection)
print("M2 passage interference delta:", feature.Shape.common(screw_clearance).Volume - base_screw_intersection)
