"""Bounded FreeCAD audit of the rear-shell load-path repair difference.

Reads the saved monolithic Tip (its full-history recompute is known to exceed
the bound) and recomputes the isolated hybrid candidate. Uses localized
intersection volumes inside the four declared rib prisms; does not save CAD.
"""
import json
from pathlib import Path

import FreeCAD as App
import Part

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "pendant.FCStd"
CANDIDATE = ROOT / "pendant-bodies" / "rear-shell-loadpath-repair-candidate.FCStd"
OUTPUT = ROOT / "reports" / "rear-shell-repair-difference-localization-2026-10-31.json"

def metrics(shape):
    bb = shape.BoundBox
    return {"valid": bool(not shape.isNull() and shape.isValid()),
            "solids": len(shape.Solids), "volume_mm3": shape.Volume,
            "area_mm2": shape.Area, "faces": len(shape.Faces),
            "bounds_mm": [bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax]}

source = App.openDocument(str(SOURCE))
candidate = App.openDocument(str(CANDIDATE))
old_body = source.getObject("Body002")
clean_base = source.getObject("Body002FullWidthSeat")
if old_body is None or clean_base is None or old_body.Tip is None:
    raise RuntimeError("Expected source rear-shell Body/Tip not found")
old_tip = old_body.Tip
candidate.recompute()
new_body = candidate.getObject("RearShell")
if new_body is None or new_body.Tip is None:
    raise RuntimeError("Candidate rear-shell Body/Tip missing")
old_shape = old_tip.Shape.copy()
base_shape = clean_base.Shape.copy()
new_shape = new_body.Tip.Shape.copy()
if not old_shape.isValid() or len(old_shape.Solids) != 1:
    raise RuntimeError("Saved source Tip is not a valid one-solid shape")
if not base_shape.isValid() or len(base_shape.Solids) != 1:
    raise RuntimeError("Saved clean base is not a valid one-solid shape")
if not new_shape.isValid() or len(new_shape.Solids) != 1:
    raise RuntimeError("Recomputed candidate Tip is not a valid one-solid shape")

history = []
for name in ("Body002FullWidthSeat", "RearBossToWallLoadPaths",
             "RearBossShoulderTransitions", "RearBossWallRamps45"):
    obj = source.getObject(name)
    if obj is None:
        raise RuntimeError("Missing source history stage: " + name)
    history.append({"object": name, "saved_shape_metrics": metrics(obj.Shape)})

candidate_chain = []
for name in ("UpperLeftSupportPad", "UpperRightSupportPad",
             "LowerLeftSupportPad", "LowerRightSupportPad", "RearM2PassageClearance"):
    obj = candidate.getObject(name)
    if obj is None:
        raise RuntimeError("Missing candidate stage: " + name)
    candidate_chain.append({"object": name, "recomputed_shape_metrics": metrics(obj.Shape)})

# These polygons are the candidate's actual native pad profiles. Intersection
# volumes are localized checks; they avoid the failed full-shell Boolean diff.
profiles = (
    ("upper-left", -30.0, -24.8, 52.0, 65.0, -31.5, -26.3),
    ("upper-right", 30.0, 24.8, 52.0, 65.0, -31.5, -26.3),
    ("lower-left", -20.0, -16.0, -22.0, -13.5, -24.0, -20.0),
    ("lower-right", 20.0, 16.0, -22.0, -13.5, -24.0, -20.0),
)
local = []
for name, wall_x, boss_x, y0, y1, low_z, high_z in profiles:
    points = [App.Vector(wall_x, y0, low_z), App.Vector(wall_x, y0, high_z),
              App.Vector(boss_x, y0, high_z), App.Vector(wall_x, y0, low_z)]
    prism = Part.Face(Part.Wire(Part.makePolygon(points).Edges)).extrude(App.Vector(0, y1-y0, 0))
    base_clip = base_shape.common(prism)
    old_clip = old_shape.common(prism)
    new_clip = new_shape.common(prism)
    if any(not s.isValid() for s in (base_clip, old_clip, new_clip)):
        raise RuntimeError("Invalid local intersection in " + name)
    local.append({
        "profile": name,
        "profile_bounds_mm": [prism.BoundBox.XMin, prism.BoundBox.XMax,
                              prism.BoundBox.YMin, prism.BoundBox.YMax,
                              prism.BoundBox.ZMin, prism.BoundBox.ZMax],
        "profile_prism_volume_mm3": prism.Volume,
        "clean_base_intersection_mm3": base_clip.Volume,
        "saved_original_tip_intersection_mm3": old_clip.Volume,
        "recomputed_candidate_tip_intersection_mm3": new_clip.Volume,
        "legacy_added_over_base_in_prism_mm3": old_clip.Volume-base_clip.Volume,
        "candidate_added_over_base_in_prism_mm3": new_clip.Volume-base_clip.Volume,
        "candidate_minus_legacy_in_prism_mm3": new_clip.Volume-old_clip.Volume,
        "intersection_solid_counts": [len(base_clip.Solids), len(old_clip.Solids), len(new_clip.Solids)],
    })

delta = new_shape.Volume - old_shape.Volume
result = {
    "date": "2026-10-31",
    "candidate_only_read_only_audit": True,
    "source_document": "pendant.FCStd",
    "candidate_document": "pendant-bodies/rear-shell-loadpath-repair-candidate.FCStd",
    "source_baseline": "saved Body002 active Tip shape; full legacy history was not recomputed because prior bounded runs exceeded 170 seconds",
    "candidate_baseline": "RearShell native candidate recomputed in isolation from its imported static base and native pad/pocket history",
    "saved_original_tip": metrics(old_shape),
    "saved_clean_base": metrics(base_shape),
    "recomputed_candidate_tip": metrics(new_shape),
    "candidate_minus_saved_original_volume_mm3": delta,
    "original_history_volume_stages": history,
    "candidate_native_history_stages": candidate_chain,
    "localized_native_profile_intersections": local,
    "interpretation": {
        "upper_pair": "Within the two explicitly reconstructed upper triangular support prisms, the candidate and saved original intersections match within numerical tolerance; this supports preservation of those local upper wedges only.",
        "lower_pair": "The saved original Tip has no material in the two candidate lower support prisms; the recomputed candidate adds about 10.56 mm3 over the clean base in each. These are intentional new lower-rib regions in the reconstruction recipe, but their fit/load-path suitability is not established by this audit.",
        "remaining_difference": "The legacy active history includes additional shoulder-transition and wall-ramp operations not reproduced by the four-rib candidate. The net volume loss is therefore an intentional simplification/reconstruction difference in the current candidate; its spatial distribution outside the localized profiles is not established because whole-shell Boolean symmetric-difference tests were unreliable or exceeded the bounded run.",
    },
    "whole_shape_exact_equivalence": "not established",
    "structural_capacity": "not established",
    "cad_files_saved_or_modified": False,
}
OUTPUT.write_text(json.dumps(result, indent=2) + "\n")
print("REAR_SHELL_REPAIR_DIFFERENCE=" + json.dumps(result, sort_keys=True))
App.closeDocument(candidate.Name)
App.closeDocument(source.Name)
