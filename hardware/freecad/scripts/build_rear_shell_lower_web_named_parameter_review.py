"""Create a disposable, named-parameter version of the rear lower-web study.

Run inside FreeCAD's Python environment. The protected monolith and modular
assembly are not opened or saved. Set PENDANT_LOWER_WEB_OUTPUT to a new path
when a different candidate filename is needed; existing files are never
overwritten.
"""
import json
import os
import shutil
from pathlib import Path

import FreeCAD as App
import MeshPart


REPO = Path(__file__).resolve().parents[3]
SOURCE = REPO / "hardware/freecad/pendant-bodies/rear-shell-structural-first-fillet-no-duplicate-pad-2026-10-31.FCStd"
DEFAULT_OUTPUT = REPO / "hardware/freecad/pendant-bodies/rear-shell-lower-web-named-parameter-review-2026-10-31.FCStd"
OUTPUT = Path(os.environ.get("PENDANT_LOWER_WEB_OUTPUT", str(DEFAULT_OUTPUT))).expanduser().resolve()

if OUTPUT.exists():
    raise FileExistsError("Refusing to overwrite candidate: %s" % OUTPUT)
if not SOURCE.exists():
    raise FileNotFoundError(SOURCE)

shutil.copy2(str(SOURCE), str(OUTPUT))
doc = App.openDocument(str(OUTPUT))
body = doc.getObject("RearShellStructuralFirstNoDuplicatePad")
if body is None:
    raise RuntimeError("Expected rear-shell candidate Body was not found")

sheet = doc.addObject("Spreadsheet::Sheet", "LowerWebParameters")
sheet.Label = "Lower rear web parameters"
sheet.set("A1", "Parameter")
sheet.set("B1", "Value (mm)")
parameters = [
    ("WebP0XAbs", 13.9), ("WebP0ZAbs", 18.6),
    ("WebP1XAbs", 13.4), ("WebP1ZAbs", 21.15),
    ("WebP2XAbs", 9.9), ("WebP2ZAbs", 25.0),
    ("WebP3XAbs", 9.9), ("WebP3ZAbs", 28.7),
    ("WebP4XAbs", 13.9), ("WebP4ZAbs", 28.7),
    ("LowerWebPadSpan", 8.5),
]
for row, (alias, value) in enumerate(parameters, 2):
    sheet.set("A%d" % row, alias)
    sheet.set("B%d" % row, "%.12g" % value)
    sheet.setAlias("B%d" % row, alias)

doc.recompute()
parameter_ref = "<<Lower rear web parameters>>."
left = doc.getObject("FinishOrder_LowerLeftInnerWebPadProfile")
right = doc.getObject("FinishOrder_LowerRightInnerWebPadProfile")
for sketch, side in ((left, "left"), (right, "right")):
    for point in range(5):
        x_expression = parameter_ref + "WebP%dXAbs" % point
        if side == "left":
            x_expression = "-" + x_expression
        z_expression = "-" + parameter_ref + "WebP%dZAbs" % point
        sketch.setExpression("Constraints.WebP%dX" % point, x_expression)
        sketch.setExpression("Constraints.WebP%dZ" % point, z_expression)

for pad_name in ("FinishOrder_LowerLeftInnerWebPad", "FinishOrder_LowerRightInnerWebPad"):
    doc.getObject(pad_name).setExpression("Length", parameter_ref + "LowerWebPadSpan")


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


doc.recompute()
if not left.FullyConstrained or not right.FullyConstrained:
    raise RuntimeError("A named-parameter web profile is no longer fully constrained")
profile_constraint_status = {"left": left.FullyConstrained, "right": right.FullyConstrained}
for pad_name in ("FinishOrder_LowerLeftInnerWebPad", "FinishOrder_LowerRightInnerWebPad"):
    if abs(doc.getObject(pad_name).Length.Value - 8.5) > 1e-8:
        raise RuntimeError("Named baseline Pad span did not resolve")

baseline = shape_summary(body.Tip.Shape)
if not baseline["valid"] or baseline["solids"] != 1:
    raise RuntimeError("Baseline is not one valid solid")

# Reversible feature-propagation check. Do not save the perturbed value.
sheet.set("B12", "8.6")
doc.recompute()
perturbed = shape_summary(body.Tip.Shape)
if abs(perturbed["volume_mm3"] - baseline["volume_mm3"]) < 1e-4:
    raise RuntimeError("The changed span did not propagate to the Body Tip")
sheet.set("B12", "8.5")
doc.recompute()
restored = shape_summary(body.Tip.Shape)
if (abs(restored["volume_mm3"] - baseline["volume_mm3"]) > 1e-7
        or restored["faces"] != baseline["faces"]
        or restored["bounds_mm"] != baseline["bounds_mm"]):
    raise RuntimeError("Restoring the span did not restore baseline descriptors")

doc.recompute()
doc.save()
App.closeDocument(doc.Name)

# Cold-open and recompute. MeshPart consumes/mutates the passed Shape wrapper in
# this FreeCAD build, so mesh a copy and take final CAD metrics from Body.Shape.
check = App.openDocument(str(OUTPUT))
check.recompute()
check_body = check.getObject("RearShellStructuralFirstNoDuplicatePad")
final_shape = check_body.Shape.copy()
mesh = MeshPart.meshFromShape(Shape=final_shape.copy(), LinearDeflection=0.08,
                              AngularDeflection=0.35, Relative=False)
final_summary = shape_summary(check_body.Shape)
if not final_summary["valid"] or final_summary["solids"] != 1 or not mesh.isSolid():
    raise RuntimeError("Cold-open candidate failed solid or mesh closure checks")

result = {
    "candidate": str(OUTPUT),
    "source": str(SOURCE),
    "tip": check_body.Tip.Name,
    "parameters": [{"alias": alias, "baseline_mm": value} for alias, value in parameters],
    "profiles_fully_constrained": profile_constraint_status,
    "baseline": baseline,
    "reversible_span_change": {
        "from_mm": 8.5,
        "to_mm": 8.6,
        "perturbed_tip": perturbed,
        "volume_delta_mm3": perturbed["volume_mm3"] - baseline["volume_mm3"],
        "restored_tip": restored,
    },
    "cold_reopen": {
        **final_summary,
        "mesh_closed": mesh.isSolid(),
        "mesh_facets": len(mesh.Facets),
    },
    "expression_count": 22,
    "production_documents_modified": False,
}
print(json.dumps(result, indent=2))
App.closeDocument(check.Name)
