"""Rebuild the rear shell's four boss-to-wall supports from explicit profiles.

This reconstructs the non-manifold stored load-path BREP as a candidate shape.
It does not save a document or change Body.Tip; callers must apply the returned
shape to a disposable model and validate the target assembly before promotion.
The screw and magnet cut volumes are derived from the existing Pocket history.
"""
from __future__ import annotations

import FreeCAD as App
import Part


# (name, wall X, boss X, start Y, end Y, wall low Z, boss high Z)
# The upper dimensions follow the established 45-degree rear wall ramp.
# Lower dimensions follow the rear shell's sectioned wall/boss boundaries.
REAR_SUPPORT_PROFILES = (
    ("upper-left", -30.0, -24.8, 52.0, 65.0, -31.5, -26.3),
    ("upper-right", 30.0, 24.8, 52.0, 65.0, -31.5, -26.3),
    ("lower-left", -20.0, -16.0, -22.0, -13.5, -24.0, -20.0),
    ("lower-right", 20.0, 16.0, -22.0, -13.5, -24.0, -20.0),
)


def removed_volume(feature):
    """Return the material removed by a Pocket-like feature."""
    if feature is None or getattr(feature, "BaseFeature", None) is None:
        raise ValueError("clearance source must have a BaseFeature")
    base_shape = feature.BaseFeature.Shape
    cut_shape = feature.Shape
    if base_shape.isNull() or cut_shape.isNull():
        raise ValueError("clearance source contains a null shape")
    result = base_shape.cut(cut_shape)
    if result.isNull() or not result.isValid():
        raise ValueError("failed to derive clearance volume from " + feature.Name)
    return result


def reconstruct(base_shape, magnet_clearance, screw_clearance,
                profiles=REAR_SUPPORT_PROFILES):
    """Return (single-solid shape, diagnostics) for four fused support ribs."""
    if base_shape.isNull() or not base_shape.isValid() or len(base_shape.Solids) != 1:
        raise ValueError("rear-shell base must be one valid solid")
    if magnet_clearance.isNull() or screw_clearance.isNull():
        raise ValueError("clearance tools must be non-null shapes")

    base = base_shape.copy()
    current = base.copy()
    diagnostics = []
    for name, wall_x, boss_x, y0, y1, wall_low_z, boss_high_z in profiles:
        section = [
            App.Vector(wall_x, y0, wall_low_z),
            App.Vector(wall_x, y0, boss_high_z),
            App.Vector(boss_x, y0, boss_high_z),
            App.Vector(wall_x, y0, wall_low_z),
        ]
        wire = Part.Wire(Part.makePolygon(section).Edges)
        raw = Part.Face(wire).extrude(App.Vector(0, y1 - y0, 0))
        if raw.isNull() or not raw.isValid() or len(raw.Solids) != 1:
            raise ValueError(name + " support profile did not form one valid solid")

        screw_removed = raw.common(screw_clearance).Volume
        magnet_removed = raw.common(magnet_clearance).Volume
        rib = raw.cut(magnet_clearance).cut(screw_clearance)
        if rib.isNull() or not rib.isValid() or len(rib.Solids) != 1:
            raise ValueError(name + " support became invalid after clearance cuts")

        overlap = current.common(rib).Volume
        fused = current.fuse(rib)
        if fused.isNull() or not fused.isValid() or len(fused.Solids) != 1:
            raise ValueError(name + " support did not fuse into the shell")
        diagnostics.append({
            "name": name,
            "raw_volume_mm3": raw.Volume,
            "added_volume_mm3": fused.Volume - current.Volume,
            "base_overlap_mm3": overlap,
            "screw_clearance_removed_mm3": screw_removed,
            "magnet_clearance_removed_mm3": magnet_removed,
        })
        current = fused

    for axis in ("XMin", "YMin", "ZMin", "XMax", "YMax", "ZMax"):
        if abs(getattr(current.BoundBox, axis) - getattr(base.BoundBox, axis)) > 1e-5:
            raise ValueError("support reconstruction changed outer bound " + axis)
    if abs(current.common(screw_clearance).Volume - base.common(screw_clearance).Volume) > 1e-5:
        raise ValueError("support reconstruction obstructed an M2 screw passage")
    if abs(current.common(magnet_clearance).Volume - base.common(magnet_clearance).Volume) > 1e-5:
        raise ValueError("support reconstruction obstructed a magnet clearance")
    return current, diagnostics


def reconstruct_from_document(doc):
    """Build a candidate from the existing monolithic rear Body history."""
    base = doc.getObject("Body002FullWidthSeat")
    if base is None:
        raise ValueError("Body002FullWidthSeat is missing")
    magnet = removed_volume(doc.getObject("Pocket")).fuse(
        removed_volume(doc.getObject("Pocket015")))
    screw = removed_volume(doc.getObject("Pocket018"))
    return reconstruct(base.Shape, magnet, screw)
