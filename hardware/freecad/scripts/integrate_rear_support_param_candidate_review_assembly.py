"""Link the parameterized rear-support study into a disposable review assembly.

This does not overwrite the existing review assembly or the production
assembly. Set PENDANT_SUPPORT_ASSEMBLY_OUTPUT to a new destination if needed.
"""
import json
import os
import shutil
from pathlib import Path

import FreeCAD as App


REPO = Path(__file__).resolve().parents[3]
SOURCE_ASSEMBLY = REPO / "hardware/freecad/pendant-modular-rear-shell-tpu-parametric-crescent-review-assembly-2026-10-31.FCStd"
SUPPORT_COMPONENT = REPO / "hardware/freecad/pendant-bodies/rear-shell-structural-support-parameter-review-2026-11-01.FCStd"
DEFAULT_OUTPUT = REPO / "hardware/freecad/pendant-modular-rear-shell-structural-support-param-review-assembly-2026-11-01.FCStd"
OUTPUT = Path(os.environ.get("PENDANT_SUPPORT_ASSEMBLY_OUTPUT", str(DEFAULT_OUTPUT))).expanduser().resolve()

for required in (SOURCE_ASSEMBLY, SUPPORT_COMPONENT):
    if not required.is_file():
        raise FileNotFoundError(required)
if OUTPUT.exists():
    raise FileExistsError("Refusing to overwrite review assembly: %s" % OUTPUT)
shutil.copy2(str(SOURCE_ASSEMBLY), str(OUTPUT))

assembly = App.openDocument(str(OUTPUT))
component = App.openDocument(str(SUPPORT_COMPONENT))
component.recompute()
assembly.recompute()
link = assembly.getObject("Interim_Body002")
body = component.getObject("RearShellStructuralFirstNoDuplicatePad")
if link is None or body is None:
    raise RuntimeError("Expected shell link or parameterized support Body is missing")
original_placement = link.LinkPlacement
link.LinkedObject = body
link.LinkPlacement = original_placement
assembly.recompute()


def shape_summary(shape):
    box = shape.BoundBox
    return {
        "volume_mm3": shape.Volume,
        "area_mm2": shape.Area,
        "faces": len(shape.Faces),
        "bounds_mm": [box.XMin, box.XMax, box.YMin, box.YMax, box.ZMin, box.ZMax],
        "valid": shape.isValid(),
        "solids": len(shape.Solids),
    }


baseline_link = shape_summary(link.Shape)
if not baseline_link["valid"] or baseline_link["solids"] != 1:
    raise RuntimeError("Updated review shell link is invalid")

# Verify that an individual component edit reaches the assembly link.
parameters = component.getObject("StructuralSupportParameters")
if parameters is None:
    raise RuntimeError("Unified support parameter sheet is missing")
parameters.set("B15", "24.9")
component.recompute()
assembly.recompute()
edited_link = shape_summary(link.Shape)
if abs(edited_link["volume_mm3"] - baseline_link["volume_mm3"]) < 1e-4:
    raise RuntimeError("Component parameter edit did not reach the assembly link")
parameters.set("B15", "24.8")
component.recompute()
assembly.recompute()
restored_link = shape_summary(link.Shape)
if abs(restored_link["volume_mm3"] - baseline_link["volume_mm3"]) > 1e-7:
    raise RuntimeError("Restored component parameter did not restore assembly link")

pad_intersections = {}
for pad_name in ("Review_AntiSlipPadUpper", "Review_AntiSlipPadLower"):
    pad = assembly.getObject(pad_name)
    if pad is None or pad.Shape.isNull() or not pad.Shape.isValid():
        raise RuntimeError("An anti-slip pad review link is missing or invalid")
    pad_intersections[pad_name] = link.Shape.common(pad.Shape).Volume

links = [obj for obj in assembly.Objects if obj.TypeId == "App::Link"]
bad_links = []
for item in links:
    if item.Shape.isNull() or not item.Shape.isValid() or len(item.Shape.Solids) < 1:
        bad_links.append(item.Name)
if bad_links:
    raise RuntimeError("Invalid links before save: %s" % bad_links)

assembly.recompute()
assembly.save()
output_path = str(OUTPUT)
assembly_name = assembly.Name
component_name = component.Name
App.closeDocument(assembly_name)
App.closeDocument(component_name)

# Cold-open the saved assembly and allow FreeCAD to resolve all its links.
check = App.openDocument(output_path)
check.recompute()
check_link = check.getObject("Interim_Body002")
if check_link is None or check_link.Shape.isNull() or not check_link.Shape.isValid():
    raise RuntimeError("Cold-open assembly shell link did not resolve")
if len(check_link.Shape.Solids) != 1:
    raise RuntimeError("Cold-open assembly shell link is not one solid")
cold = shape_summary(check_link.Shape)
if abs(cold["volume_mm3"] - baseline_link["volume_mm3"]) > 1e-6:
    raise RuntimeError("Cold-open assembly shell differs from saved baseline")
if check_link.LinkedObject.Document.FileName != str(SUPPORT_COMPONENT):
    raise RuntimeError("Cold-open shell link resolved to an unexpected source document")

check_links = [obj for obj in check.Objects if obj.TypeId == "App::Link"]
if len(check_links) != len(links):
    raise RuntimeError("Cold-open assembly link count changed")
if any(obj.Shape.isNull() or not obj.Shape.isValid() for obj in check_links):
    raise RuntimeError("Cold-open review assembly contains a broken link")

result = {
    "assembly_candidate": str(OUTPUT),
    "source_assembly": str(SOURCE_ASSEMBLY),
    "linked_component": str(SUPPORT_COMPONENT),
    "shell_link": "Interim_Body002",
    "link_placement_preserved": check_link.LinkPlacement == original_placement,
    "baseline_shell_link": baseline_link,
    "reversible_component_edit": {
        "parameter": "UpperBossXAbs",
        "from_mm": 24.8,
        "to_mm": 24.9,
        "edited_assembly_link": edited_link,
        "restored_assembly_link": restored_link,
        "restoration_error_mm3": restored_link["volume_mm3"] - baseline_link["volume_mm3"],
    },
    "anti_slip_link_common_mm3": pad_intersections,
    "cold_reopen_shell": cold,
    "cold_reopen_link_count": len(check_links),
    "production_assembly_modified": False,
    "status": "review only; rear shell structural equivalence remains unresolved",
}
print(json.dumps(result, indent=2))
App.closeDocument(check.Name)
