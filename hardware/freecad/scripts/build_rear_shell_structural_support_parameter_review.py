"""Unify lower-web and boss-to-wall controls in a disposable local sheet.

Run inside FreeCAD's Python environment. The source is already a validated
disposable reconstruction candidate. The protected monolith and production
assembly are not modified. Existing outputs are never overwritten.
"""
import json
import os
import shutil
from pathlib import Path

import FreeCAD as App
import MeshPart


REPO = Path(__file__).resolve().parents[3]
SOURCE = REPO / "hardware/freecad/pendant-bodies/rear-shell-lower-web-named-parameter-review-2026-10-31.FCStd"
DEFAULT_OUTPUT = REPO / "hardware/freecad/pendant-bodies/rear-shell-structural-support-parameter-review-2026-11-01.FCStd"
OUTPUT = Path(os.environ.get("PENDANT_SUPPORT_PARAMETER_OUTPUT", str(DEFAULT_OUTPUT))).expanduser().resolve()
if OUTPUT.exists():
    raise FileExistsError("Refusing to overwrite candidate: %s" % OUTPUT)
if not SOURCE.exists():
    raise FileNotFoundError(SOURCE)

shutil.copy2(str(SOURCE), str(OUTPUT))
doc = App.openDocument(str(OUTPUT))
body = doc.getObject("RearShellStructuralFirstNoDuplicatePad")
old_sheet = doc.getObject("LowerWebParameters")
if body is None or old_sheet is None:
    raise RuntimeError("Expected parameterized source candidate is incomplete")

sheet = doc.addObject("Spreadsheet::Sheet", "StructuralSupportParameters")
sheet.Label = "Rear support and web parameters"
sheet.set("A1", "Parameter")
sheet.set("B1", "Value (mm)")
parameters = [
    ("LowerWebP0XAbs", 13.9), ("LowerWebP0ZAbs", 18.6),
    ("LowerWebP1XAbs", 13.4), ("LowerWebP1ZAbs", 21.15),
    ("LowerWebP2XAbs", 9.9), ("LowerWebP2ZAbs", 25.0),
    ("LowerWebP3XAbs", 9.9), ("LowerWebP3ZAbs", 28.7),
    ("LowerWebP4XAbs", 13.9), ("LowerWebP4ZAbs", 28.7),
    ("LowerWebPadSpan", 8.5),
    ("UpperWallXAbs", 30.0), ("UpperWallBottomZAbs", 31.5),
    ("UpperBossXAbs", 24.8), ("UpperBossTopZAbs", 26.3),
    ("UpperSupportPadSpan", 13.0),
    ("LowerWallXAbs", 20.0), ("LowerWallBottomZAbs", 24.0),
    ("LowerBossXAbs", 16.0), ("LowerBossTopZAbs", 20.0),
    ("LowerSupportPadSpan", 8.5),
]
for row, (alias, value) in enumerate(parameters, 2):
    sheet.set("A%d" % row, alias)
    sheet.set("B%d" % row, "%.12g" % value)
    sheet.setAlias("B%d" % row, alias)

doc.recompute()
ref = "<<Rear support and web parameters>>."

# Move the previous lower-web expressions onto the unified parameter sheet.
for sketch_name, side in (
    ("FinishOrder_LowerLeftInnerWebPadProfile", "left"),
    ("FinishOrder_LowerRightInnerWebPadProfile", "right"),
):
    sketch = doc.getObject(sketch_name)
    for point in range(5):
        x_expr = ref + "LowerWebP%dXAbs" % point
        if side == "left":
            x_expr = "-" + x_expr
        sketch.setExpression("Constraints.WebP%dX" % point, x_expr)
        sketch.setExpression("Constraints.WebP%dZ" % point,
                             "-" + ref + "LowerWebP%dZAbs" % point)
for name in ("FinishOrder_LowerLeftInnerWebPad", "FinishOrder_LowerRightInnerWebPad"):
    doc.getObject(name).setExpression("Length", ref + "LowerWebPadSpan")

# Rebind the four 45-degree boss support profiles through shared mirrored
# dimensions. Sketch constraints and orientation are retained.
support_defs = (
    ("FinishOrder_UpperLeftSupportPad", "upper", "left"),
    ("FinishOrder_UpperRightSupportPad", "upper", "right"),
    ("FinishOrder_LowerLeftSupportPad", "lower", "left"),
    ("FinishOrder_LowerRightSupportPad", "lower", "right"),
)
support_expressions = 0
for pad_name, region, side in support_defs:
    pad = doc.getObject(pad_name)
    profile = pad.Profile[0] if isinstance(pad.Profile, tuple) else pad.Profile
    prefix = "Upper" if region == "upper" else "Lower"
    sign = "-" if side == "left" else ""
    profile.setExpression("Constraints.WallX", sign + ref + prefix + "WallXAbs")
    profile.setExpression("Constraints.WallBottomZ", "-" + ref + prefix + "WallBottomZAbs")
    profile.setExpression("Constraints.BossTopZ", "-" + ref + prefix + "BossTopZAbs")
    profile.setExpression("Constraints.BossX", sign + ref + prefix + "BossXAbs")
    pad.setExpression("Length", ref + prefix + "SupportPadSpan")
    support_expressions += 5

doc.recompute()
doc.removeObject(old_sheet.Name)
doc.recompute()


def shape_summary(shape):
    box = shape.BoundBox
    return {
        "volume_mm3": shape.Volume,
        "area_mm2": shape.Area,
        "faces": len(shape.Faces),
        "edges": len(shape.Edges),
        "bounds_mm": [box.XMin, box.XMax, box.YMin, box.YMax, box.ZMin, box.ZMax],
        "valid": shape.isValid(),
        "solids": len(shape.Solids),
    }


profiles = [doc.getObject(name) for name in (
    "FinishOrder_LowerLeftInnerWebPadProfile", "FinishOrder_LowerRightInnerWebPadProfile",
    "FinishOrder_UpperLeftSupportPadProfile", "FinishOrder_UpperRightSupportPadProfile",
    "FinishOrder_LowerLeftSupportPadProfile", "FinishOrder_LowerRightSupportPadProfile",
)]
if not all(sketch.FullyConstrained for sketch in profiles):
    raise RuntimeError("One or more reinforcement sketches lost full constraint")
profile_status = {sketch.Name: sketch.FullyConstrained for sketch in profiles}
baseline = shape_summary(body.Shape)
if not baseline["valid"] or baseline["solids"] != 1:
    raise RuntimeError("Parameter wiring did not leave one valid shell solid")

# Reversible profile edit and extrusion-span edit, each propagated to Tip.
sheet.set("B15", "24.9")  # UpperBossXAbs, row 15
doc.recompute()
profile_probe = shape_summary(body.Shape)
sheet.set("B15", "24.8")
doc.recompute()
profile_restored = shape_summary(body.Shape)
if (abs(profile_probe["volume_mm3"] - baseline["volume_mm3"]) < 1e-4
        or abs(profile_restored["volume_mm3"] - baseline["volume_mm3"]) > 1e-7):
    raise RuntimeError("Upper boss profile parameter did not propagate and restore")

sheet.set("B17", "13.1")  # UpperSupportPadSpan, row 17
doc.recompute()
span_probe = shape_summary(body.Shape)
sheet.set("B17", "13.0")
doc.recompute()
span_restored = shape_summary(body.Shape)
if (abs(span_probe["volume_mm3"] - baseline["volume_mm3"]) < 1e-4
        or abs(span_restored["volume_mm3"] - baseline["volume_mm3"]) > 1e-7):
    raise RuntimeError("Upper support span parameter did not propagate and restore")

doc.recompute()
doc.save()
App.closeDocument(doc.Name)

check = App.openDocument(str(OUTPUT))
check.recompute()
check_body = check.getObject("RearShellStructuralFirstNoDuplicatePad")
final_summary = shape_summary(check_body.Shape)
mesh = MeshPart.meshFromShape(Shape=check_body.Shape.copy(), LinearDeflection=0.08,
                              AngularDeflection=0.35, Relative=False)
if not final_summary["valid"] or final_summary["solids"] != 1 or not mesh.isSolid():
    raise RuntimeError("Cold-open shell failed valid-solid or manifold-mesh checks")

result = {
    "candidate": str(OUTPUT),
    "source_candidate": str(SOURCE),
    "tip": check_body.Tip.Name,
    "parameter_count": len(parameters),
    "expression_count": 22 + support_expressions,
    "profile_status": profile_status,
    "baseline": baseline,
    "reversible_profile_probe": {
        "parameter": "UpperBossXAbs", "from_mm": 24.8, "to_mm": 24.9,
        "probe": profile_probe, "restored": profile_restored,
    },
    "reversible_span_probe": {
        "parameter": "UpperSupportPadSpan", "from_mm": 13.0, "to_mm": 13.1,
        "probe": span_probe, "restored": span_restored,
    },
    "cold_reopen": {**final_summary, "mesh_closed": mesh.isSolid(), "mesh_facets": len(mesh.Facets)},
    "protected_monolith_modified": False,
    "production_assembly_modified": False,
}
print(json.dumps(result, indent=2))
App.closeDocument(check.Name)
