"""Cold-open the master-driven lead-in assembly after relocating its folder.

The trial copy is created in a temporary directory and never saved. Run with
FreeCADCmd; this checks relative App::Link paths and reversible master updates.
"""
import json
import os
import shutil
import tempfile
from pathlib import Path

import FreeCAD as App

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "master-driven-leadins-candidate"
temp_root = Path(tempfile.mkdtemp(prefix="pendant-master-driven-relocation-"))
RELOCATED = temp_root / "cad-candidate"
shutil.copytree(str(SOURCE), str(RELOCATED))

master = App.openDocument(str(RELOCATED / "pendant-master.FCStd"))
assembly = App.openDocument(str(RELOCATED / "pendant-modular-assembly.FCStd"))
master.recompute()
assembly.recompute()
root = assembly.getObject("AssemblyRoot")
if root is None or not root.Shape.isValid() or len(root.Shape.Solids) != 9:
    raise RuntimeError("Relocated assembly root is invalid")

link_names = ["Editable_Body_DisplayRetainer_EditableV2",
              "Editable_Body_USBTetheredCover",
              "Editable_Body_FaceplateLocator_A",
              "Editable_Body_FaceplateLocator_B",
              "Editable_Body006", "Interim_Body002"]
links = []
for name in link_names:
    link = assembly.getObject(name)
    target = link.getLinkedObject(True) if link else None
    if target is None or target.Shape.isNull() or not target.Shape.isValid() or len(target.Shape.Solids) != 1:
        raise RuntimeError("Relocated App::Link unresolved or invalid: " + name)
    if not os.path.realpath(target.Document.FileName).startswith(os.path.realpath(str(RELOCATED)) + os.sep):
        raise RuntimeError("Link did not resolve inside relocated candidate: " + name)
    links.append({"link": name, "target": target.Name,
                  "document_file": os.path.relpath(target.Document.FileName, str(RELOCATED))})

sheet = master.getObject("InternalHardware")
retainer = assembly.getObject("Editable_Body_DisplayRetainer_EditableV2").getLinkedObject(True)
baseline = retainer.Shape.Volume
sheet.set("B9", "0.20 mm")
master.recompute()
assembly.recompute()
perturbed = retainer.Shape.Volume
if abs(perturbed - baseline) < 1e-5:
    raise RuntimeError("Master change did not propagate in relocated assembly")
sheet.set("B9", "0.15 mm")
master.recompute()
assembly.recompute()
restored = retainer.Shape.Volume
if abs(restored - baseline) > 1e-5:
    raise RuntimeError("Relocated assembly did not restore baseline volume")

result = {"relocated_candidate_directory": "temporary copy of master-driven-leadins-candidate",
          "assembly_root_valid": root.Shape.isValid(), "assembly_root_solids": len(root.Shape.Solids),
          "resolved_links": links, "retainer_volume_mm3":
          {"baseline_0_15_mm": baseline, "perturbed_0_20_mm": perturbed,
           "restored_0_15_mm": restored},
          "master_parameter_propagation": "passed", "documents_saved": False}
print("MASTER_DRIVEN_RELOCATION=" + json.dumps(result, sort_keys=True))

for doc_name in list(App.listDocuments().keys()):
    try:
        App.closeDocument(doc_name)
    except Exception:
        pass
shutil.rmtree(str(temp_root))
