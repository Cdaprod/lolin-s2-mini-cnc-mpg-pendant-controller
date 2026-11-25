"""Create disposable master-driven lead-in components and a linked assembly.

All edits are confined to hardware/freecad/master-driven-leadins-candidate.
The protected monolith, production assembly, and source components are opened
read-only and never saved.
"""
import json
import math
import os
import shutil
from pathlib import Path

import FreeCAD as App
import Part

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "master-driven-leadins-candidate"
BODY_DIR = OUT / "pendant-bodies"
REPORT = ROOT / "reports" / "master-driven-fastener-entry-validation.json"
BASELINE_ASSEMBLY = ROOT / "pendant-modular-locator-leadin-candidate.FCStd"
MASTER_SOURCE = ROOT / "pendant-master.FCStd"
RETAINER_SOURCE = ROOT / "pendant-bodies" / "display-retainer-mounting-leadin-candidate.FCStd"
LOCATOR_SOURCE = ROOT / "pendant-bodies" / "faceplate-locators-leadin-candidate.FCStd"
DEPTH = 0.15
PERTURBED = 0.20
PARAMETER = "FastenerEntryRadialDepth"
EXPR = "pendant_master#<<InternalHardware>>." + PARAMETER

if OUT.exists() and any(OUT.iterdir()):
    raise RuntimeError("Refusing to overwrite existing candidate directory: " + str(OUT))
BODY_DIR.mkdir(parents=True, exist_ok=True)

def copy(src, dst):
    if not Path(src).is_file():
        raise RuntimeError("Missing input: " + str(src))
    if Path(dst).exists():
        raise RuntimeError("Refusing to overwrite: " + str(dst))
    shutil.copy2(src, dst)

copy(MASTER_SOURCE, OUT / "pendant-master.FCStd")
copy(RETAINER_SOURCE, BODY_DIR / "display-retainer-mounting-leadin-candidate.FCStd")
copy(LOCATOR_SOURCE, BODY_DIR / "faceplate-locators-leadin-candidate.FCStd")
for name in ("usb-tethered-cover.FCStd", "breakout-board.FCStd", "rear-shell-loadpath-repair-candidate.FCStd"):
    copy(ROOT / "pendant-bodies" / name, BODY_DIR / name)
copy(BASELINE_ASSEMBLY, OUT / "pendant-modular-assembly.FCStd")

def metrics(shape):
    bb = shape.BoundBox
    return {"valid": bool(not shape.isNull() and shape.isValid()),
            "solids": len(shape.Solids), "volume_mm3": shape.Volume,
            "area_mm2": shape.Area,
            "bounds_mm": [bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax]}

def symdiff(a, b):
    return a.cut(b).Volume + b.cut(a).Volume

def require_one_solid(shape, label):
    if shape.isNull() or not shape.isValid() or len(shape.Solids) != 1:
        raise RuntimeError(label + " is not one valid solid")

master_path = OUT / "pendant-master.FCStd"
master = App.openDocument(str(master_path))
if master.Name != "pendant_master":
    raise RuntimeError("Master identity changed unexpectedly: " + master.Name)
sheet = master.getObject("InternalHardware")
if sheet is None:
    raise RuntimeError("InternalHardware sheet missing")
sheet.set("A9", "Fastener entry radial expansion and depth")
sheet.set("B9", str(DEPTH) + " mm")
sheet.setAlias("B9", PARAMETER)
master.recompute()
master.save()

ret = App.openDocument(str(BODY_DIR / "display-retainer-mounting-leadin-candidate.FCStd"))
loc = App.openDocument(str(BODY_DIR / "faceplate-locators-leadin-candidate.FCStd"))
master.recompute(); ret.recompute(); loc.recompute()
ret_body = ret.getObject("Body_DisplayRetainer_EditableV2")
ret_profile = ret.getObject("DisplayRetainerMountingLeadInProfile")
ret_pocket = ret.getObject("DisplayRetainerMountingLeadIns")
if None in (ret_body, ret_profile, ret_pocket) or ret_body.Tip != ret_pocket:
    raise RuntimeError("Retainer lead-in feature chain not found")
loc_profiles = [loc.getObject("LocatorScrewLeadInProfile_" + i) for i in ("0", "1")]
loc_pockets = [loc.getObject("LocatorScrewLeadIn_" + i) for i in ("0", "1")]
loc_bodies = [loc.getObject("Body_FaceplateLocator_" + i) for i in ("A", "B")]
if any(x is None for x in loc_profiles + loc_pockets + loc_bodies):
    raise RuntimeError("Locator lead-in feature chain not found")

# Save original candidate shapes in memory before introducing expressions.
ret_before = ret_body.Shape.copy()
loc_before = {b.Name: b.Shape.copy() for b in loc_bodies}
require_one_solid(ret_before, "retainer baseline")
for b in loc_bodies:
    require_one_solid(loc_before[b.Name], b.Name + " baseline")

# Profile constraint order is Radius/X/Y for locators and X/Y/Radius for the
# retainer. Preserve each nominal passage radius as a local additive constant.
ret_constraints = []
for i in range(5):
    ci = i * 3 + 2
    base_radius = ret_profile.Geometry[i].Radius - DEPTH
    ret_profile.setExpression("Constraints[{}]".format(ci),
                              "{:.9f} mm + {}".format(base_radius, EXPR))
    ret_constraints.append({"constraint_index": ci, "nominal_radius_mm": base_radius,
                            "expression": "{:.9f} mm + {}".format(base_radius, EXPR)})
ret_pocket.setExpression("Length", EXPR)
for i, (profile, pocket) in enumerate(zip(loc_profiles, loc_pockets)):
    base_radius = profile.Geometry[0].Radius - DEPTH
    profile.setExpression("Constraints[0]", "{:.9f} mm + {}".format(base_radius, EXPR))
    pocket.setExpression("Length", EXPR)
    profile.Label = "Locator screw entry profile — master-driven radial/depth"
ret_profile.Label = "M2 passage lead-in profiles — master-driven radial/depth"
ret.recompute()
loc.recompute()
if not ret_profile.FullyConstrained or any(not s.FullyConstrained for s in loc_profiles):
    raise RuntimeError("A lead-in profile is no longer fully constrained")
require_one_solid(ret_body.Shape, "master-driven retainer")
for b in loc_bodies:
    require_one_solid(b.Shape, "master-driven " + b.Name)

def passage_gauge(shape, x, y, r, z0, length):
    gauge = Part.makeCylinder(r, length, App.Vector(x, y, z0), App.Vector(0, 0, 1))
    return shape.common(gauge).Volume

# Nominal cylindrical passages remain unobstructed in all six lead-in locations.
gauge_checks = []
ret_holes = [(-25.8, -10.5, 1.15), (25.8, -10.5, 1.15),
             (-11.811, -12.605, 1.10), (11.811, -12.605, 1.10),
             (0.0, 22.449, 1.10)]
for x, y, r in ret_holes:
    v = passage_gauge(ret_body.Shape, x, y, r, -20.0, 40.0)
    gauge_checks.append({"component": "display-retainer", "center_mm": [x, y],
                         "nominal_radius_mm": r, "interference_mm3": v})
    if v > 1e-6:
        raise RuntimeError("Retainer nominal passage gauge obstructed")
for b, profile in zip(loc_bodies, loc_profiles):
    circle = profile.Geometry[0]
    v = passage_gauge(b.Shape, circle.Center.x, circle.Center.y, 1.15, -20.0, 40.0)
    gauge_checks.append({"component": b.Name, "center_mm": [circle.Center.x, circle.Center.y],
                         "nominal_radius_mm": 1.15, "interference_mm3": v})
    if v > 1e-6:
        raise RuntimeError("Locator nominal passage gauge obstructed: " + b.Name)

baseline_metrics = {"display_retainer": metrics(ret_before),
                    "locators": {n: metrics(s) for n, s in loc_before.items()}}
master.save(); ret.save(); loc.save()

# Controlled, reversible change: at -45 degrees, equal radial expansion and
# pocket depth preserve the nominal bore at the bottom of each conical entry.
sheet.set("B9", str(PERTURBED) + " mm")
master.recompute(); ret.recompute(); loc.recompute()
perturbed = {"display_retainer": metrics(ret_body.Shape), "locators": {}}
if abs(ret_body.Shape.Volume - ret_before.Volume) < 1e-5:
    raise RuntimeError("Retainer did not respond to master parameter perturbation")
for b in loc_bodies:
    perturbed["locators"][b.Name] = metrics(b.Shape)
    if abs(b.Shape.Volume - loc_before[b.Name].Volume) < 1e-5:
        raise RuntimeError(b.Name + " did not respond to master parameter perturbation")
sheet.set("B9", str(DEPTH) + " mm")
master.recompute(); ret.recompute(); loc.recompute()
restored = {"display_retainer": metrics(ret_body.Shape), "locators": {}}
ret_d = symdiff(ret_body.Shape, ret_before)
if ret_d > 1e-5:
    raise RuntimeError("Retainer geometry did not restore; symmetric difference=" + str(ret_d))
restored["retainer_symdiff_mm3"] = ret_d
for b in loc_bodies:
    d = symdiff(b.Shape, loc_before[b.Name])
    restored["locators"][b.Name] = {"metrics": metrics(b.Shape), "symdiff_mm3": d}
    if d > 1e-5:
        raise RuntimeError(b.Name + " geometry did not restore; symmetric difference=" + str(d))
    if b.Tip != loc.getObject("LocatorScrewLeadIn_" + ("0" if b.Name.endswith("A") else "1")):
        raise RuntimeError(b.Name + " active Tip unexpectedly changed")

master.save(); ret.save(); loc.save()
for d in (ret, loc, master):
    App.closeDocument(d.Name)

# Cold start in dependency order and verify stored expressions still resolve.
master = App.openDocument(str(master_path))
ret = App.openDocument(str(BODY_DIR / "display-retainer-mounting-leadin-candidate.FCStd"))
loc = App.openDocument(str(BODY_DIR / "faceplate-locators-leadin-candidate.FCStd"))
master.recompute(); ret.recompute(); loc.recompute()
ret_body = ret.getObject("Body_DisplayRetainer_EditableV2")
ret_profile = ret.getObject("DisplayRetainerMountingLeadInProfile")
ret_pocket = ret.getObject("DisplayRetainerMountingLeadIns")
loc_profiles = [loc.getObject("LocatorScrewLeadInProfile_" + i) for i in ("0", "1")]
loc_pockets = [loc.getObject("LocatorScrewLeadIn_" + i) for i in ("0", "1")]
loc_bodies = [loc.getObject("Body_FaceplateLocator_" + i) for i in ("A", "B")]
if any(not x for x in (ret_body, ret_profile, ret_pocket) + tuple(loc_profiles + loc_pockets + loc_bodies)):
    raise RuntimeError("Cold reopen lost a required feature")
require_one_solid(ret_body.Shape, "cold-reopened retainer")
for b in loc_bodies: require_one_solid(b.Shape, "cold-reopened " + b.Name)
for obj in [ret_profile, ret_pocket] + loc_profiles + loc_pockets:
    if not obj.ExpressionEngine:
        raise RuntimeError("Cold-reopened expression missing on " + obj.Name)
expression_count = sum(len(o.ExpressionEngine) for o in [ret_profile, ret_pocket] + loc_profiles + loc_pockets)

# Retarget all six live links in a disposable copy of the full assembly. The
# remaining linked sources are also copied beside this candidate for portability.
usb = App.openDocument(str(BODY_DIR / "usb-tethered-cover.FCStd"))
breakout = App.openDocument(str(BODY_DIR / "breakout-board.FCStd"))
rear = App.openDocument(str(BODY_DIR / "rear-shell-loadpath-repair-candidate.FCStd"))
assembly_path = OUT / "pendant-modular-assembly.FCStd"
master = App.openDocument(str(master_path))
assembly = App.openDocument(str(assembly_path))
link_map = {
    "Editable_Body_DisplayRetainer_EditableV2": (ret, "Body_DisplayRetainer_EditableV2"),
    "Editable_Body_USBTetheredCover": (usb, "Body_USBTetheredCover"),
    "Editable_Body_FaceplateLocator_A": (loc, "Body_FaceplateLocator_A"),
    "Editable_Body_FaceplateLocator_B": (loc, "Body_FaceplateLocator_B"),
    "Editable_Body006": (breakout, "Body006"),
    "Interim_Body002": (rear, "RearShell"),
}
link_records = []
for name, (target_doc, target_name) in link_map.items():
    if target_doc is None:
        raise RuntimeError("Expected candidate linked source document is not open for " + name)
    link = assembly.getObject(name)
    target = target_doc.getObject(target_name)
    if link is None or target is None:
        raise RuntimeError("Missing assembly link/target: " + name + " -> " + target_name)
    prior = link.LinkPlacement
    link.LinkedObject = target
    link.LinkPlacement = prior
    require_one_solid(target.Shape, "assembly target " + name)
    link_records.append({"link": name, "target_document": target_doc.Name,
                         "target_file": os.path.relpath(target_doc.FileName, str(OUT)), "target_object": target.Name,
                         "placement": str(link.LinkPlacement), "target_metrics": metrics(target.Shape)})
assembly.recompute()
root = assembly.getObject("AssemblyRoot")
if root is None or not root.Shape.isValid() or len(root.Shape.Solids) != 9:
    raise RuntimeError("Combined candidate assembly root is invalid or changed solid count")
assembly_metrics = metrics(root.Shape)
assembly.save()
assembly_name = assembly.Name
App.closeDocument(assembly_name)

# Close and cold-reopen assembly to verify the saved six live links.
for n in (ret.Name, loc.Name, master.Name, usb.Name, breakout.Name, rear.Name):
    if n in App.listDocuments(): App.closeDocument(n)
assembly = App.openDocument(str(assembly_path))
assembly.recompute()
root = assembly.getObject("AssemblyRoot")
if root is None or not root.Shape.isValid() or len(root.Shape.Solids) != 9:
    raise RuntimeError("Cold-reopened assembly root invalid")
cold_links = []
for name in link_map:
    link = assembly.getObject(name)
    target = link.getLinkedObject(True) if link else None
    if target is None or target.Shape.isNull() or not target.Shape.isValid() or len(target.Shape.Solids) != 1:
        raise RuntimeError("Cold-reopened assembly link unresolved/invalid: " + name)
    cold_links.append({"link": name, "target_object": target.Name,
                       "target_document": target.Document.Name,
                       "target_file": os.path.relpath(target.Document.FileName, str(OUT)),
                       "placement": str(link.LinkPlacement)})
if assembly_metrics["bounds_mm"] != metrics(root.Shape)["bounds_mm"]:
    raise RuntimeError("Assembly bounds changed on cold reopen")
assembly.save()

result = {
    "candidate_root": "master-driven-leadins-candidate/", "protected_monolith_modified": False,
    "production_assembly_modified": False,
    "master_parameter": {"sheet": "InternalHardware", "alias": PARAMETER,
                          "cell": "B9", "baseline_mm": DEPTH,
                          "perturbed_mm": PERTURBED,
                          "profile_and_pocket_relation": "radial expansion equals depth; fixed -45 deg taper preserves nominal bore at the lead-in bottom"},
    "expressions": {"sketch_constraint_indices_retainer": ret_constraints,
                    "locator_constraint_indices": [0, 0],
                    "pocket_length": EXPR,
                    "taper_angle_deg": -45.0},
    "baseline_component_metrics": baseline_metrics,
    "perturbed_component_metrics": perturbed,
    "restored_component_metrics": restored,
    "nominal_clearance_gauge_checks": gauge_checks,
    "cold_reopen_component_expression_count": expression_count,
    "assembly_live_links_before_cold_reopen": link_records,
    "assembly_live_links_after_cold_reopen": cold_links,
    "assembly_root_before_cold_reopen": assembly_metrics,
    "assembly_root_after_cold_reopen": metrics(root.Shape),
    "save_close_reopen_recompute": "passed",
    "qualification": "Parametric interface validated for lead-in radial/depth only; this does not establish screw preload, structural strength, or full assembly design readiness."
}
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text(json.dumps(result, indent=2) + "\n")
print("MASTER_DRIVEN_FASTENER_ENTRY=" + json.dumps(result, sort_keys=True))
