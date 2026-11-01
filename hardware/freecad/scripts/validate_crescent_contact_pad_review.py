"""Cold-open and reversible parameter validation for the crescent pad review.

Run inside FreeCADCmd/FreeCAD Python with the repository paths unchanged:
    FreeCADCmd validate_crescent_contact_pad_review.py

The script does not save CAD documents. It opens the review assembly, checks
the dedicated two-Body pad source and live links, probes PadProudHeight in
memory, restores the stored value, then closes and cold-opens the assembly.
"""
import json
import os
import FreeCAD as App


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ASSEMBLY = os.path.join(
    ROOT, "pendant-modular-rear-loadpath-crescents-independent-review-2026-11-01.FCStd"
)
PAD_SOURCE = os.path.join(
    ROOT, "pendant-bodies", "crescent-contact-pads-native-review-2026-11-01.FCStd"
)
EXPECTED = {
    "Editable_UpperAntiSlipCrescent": ("UpperCrescentContactPad", 57.782881303977035),
    "Editable_LowerAntiSlipCrescent": ("LowerCrescentContactPad", 21.17606442735022),
}


def close_if_open(name):
    if App.getDocument(name):
        App.closeDocument(name)


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


check(os.path.isfile(ASSEMBLY), "review assembly missing: " + ASSEMBLY)
check(os.path.isfile(PAD_SOURCE), "pad source missing: " + PAD_SOURCE)
assembly = App.openDocument(ASSEMBLY)
assembly.recompute()
links = [obj for obj in assembly.Objects if obj.TypeId == "App::Link"]
check(len(links) == 9, "expected nine live links, got %d" % len(links))

pad_doc = App.getDocument("crescent_contact_pads_native_review_2026_11_01")
if pad_doc is None:
    pad_doc = App.openDocument(PAD_SOURCE)
pad_doc.recompute()
pad_bodies = [obj for obj in pad_doc.Objects if obj.TypeId == "PartDesign::Body"]
check(len(pad_bodies) == 2, "pad source must contain exactly two Bodies")
check(set(obj.Name for obj in pad_bodies) == {"UpperCrescentContactPad", "LowerCrescentContactPad"},
      "unexpected Body set in dedicated pad source")
check(not any("Shell" in obj.Name for obj in pad_bodies), "pad source unexpectedly includes a shell")

for link_name, (source_name, expected_volume) in EXPECTED.items():
    link = assembly.getObject(link_name)
    check(link is not None and link.TypeId == "App::Link", "missing pad link " + link_name)
    check(link.LinkedObject.Name == source_name, "%s targets %s" % (link_name, link.LinkedObject.Name))
    shape = link.Shape
    check(shape.isValid() and len(shape.Solids) == 1, "invalid linked Body: " + link_name)
    check(abs(shape.Volume - expected_volume) < 1e-8, "baseline volume mismatch: " + link_name)

sheet = pad_doc.getObject("AntiSlipParameters")
baseline = sheet.getContents("B3")
check(abs(sheet.B3.Value - 0.25) < 1e-9, "unexpected saved PadProudHeight")
base_volumes = [assembly.getObject(name).Shape.Volume for name in EXPECTED]
try:
    sheet.set("B3", "0.35 mm")
    pad_doc.recompute()
    assembly.recompute()
    raised_volumes = [assembly.getObject(name).Shape.Volume for name in EXPECTED]
    check(all(raised_volumes[i] > base_volumes[i] for i in range(2)),
          "PadProudHeight edit did not increase both live link volumes")
finally:
    sheet.set("B3", baseline)
    pad_doc.recompute()
    assembly.recompute()

restored_volumes = [assembly.getObject(name).Shape.Volume for name in EXPECTED]
check(all(abs(restored_volumes[i] - base_volumes[i]) < 1e-8 for i in range(2)),
      "restoring PadProudHeight did not restore both link volumes")
assembly_name = assembly.Name
pad_doc_name = pad_doc.Name
close_if_open(assembly_name)
close_if_open(pad_doc_name)

cold = App.openDocument(ASSEMBLY)
cold.recompute()
check(len([obj for obj in cold.Objects if obj.TypeId == "App::Link"]) == 9,
      "cold-open assembly link count changed")
for link_name, (source_name, expected_volume) in EXPECTED.items():
    link = cold.getObject(link_name)
    check(link.LinkedObject.Name == source_name, "cold-open source target changed: " + link_name)
    check(link.Shape.isValid() and len(link.Shape.Solids) == 1, "cold-open invalid link: " + link_name)
    check(abs(link.Shape.Volume - expected_volume) < 1e-8, "cold-open volume mismatch: " + link_name)
print(json.dumps({
    "status": "PASS",
    "assembly": ASSEMBLY,
    "pad_source": PAD_SOURCE,
    "links": 9,
    "pad_bodies": 2,
    "parameter_probe_mm": [0.25, 0.35, 0.25],
    "baseline_volumes_mm3": base_volumes,
    "raised_volumes_mm3": raised_volumes,
    "restored_volumes_mm3": restored_volumes,
    "cold_open": True,
    "cad_files_saved": False,
}, indent=2))
close_if_open(cold.Name)
