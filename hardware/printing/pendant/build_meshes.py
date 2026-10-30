#!/usr/bin/env python3
"""Export validated printable shapes from the saved modular FreeCAD assembly.

This exporter opens the saved assembly read-only in practice: it does not call
recompute or save any CAD document. Each mesh is translated to center its XY
bounding box and place its minimum Z at the build plane. No rotation, repair,
or shape healing is performed.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]
ASSEMBLY = ROOT / "hardware/freecad/pendant-modular-assembly.FCStd"
DEFAULT_FREECADCMD = Path("/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd")
OUT = Path(__file__).resolve().parent

# Source assembly object names only. Body006 is an electronics/board envelope,
# not a printable enclosure part, and is intentionally excluded.
OBJECTS = [
    ("Interim_Body", "front-shell"),
    ("Interim_Body002", "rear-shell"),
    ("Interim_Body003", "upper-faceplate"),
    ("Interim_EncoderFaceplatePocketUnsplit", "encoder-faceplate-pocket-fused"),
    ("Editable_Body_DisplayRetainer_EditableV2", "display-retainer"),
    ("Editable_Body_USBTetheredCover", "usb-cover"),
    ("Editable_Body_FaceplateLocator_A", "faceplate-locator-a"),
    ("Editable_Body_FaceplateLocator_B", "faceplate-locator-b"),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--freecadcmd", type=Path, default=Path(os.environ.get("FREECADCMD", DEFAULT_FREECADCMD)))
    ap.add_argument("--linear-deflection", type=float, default=0.08, help="mesh chordal deviation, mm")
    ap.add_argument("--angular-deflection", type=float, default=0.20, help="mesh angular deviation, radians")
    ap.add_argument("--output-dir", type=Path, default=OUT)
    args = ap.parse_args()
    if not ASSEMBLY.is_file():
        ap.error(f"saved assembly not found: {ASSEMBLY}")
    if not args.freecadcmd.is_file():
        ap.error(f"FreeCADCmd not found: {args.freecadcmd}")
    if not (0.01 <= args.linear_deflection <= 0.5 and 0.05 <= args.angular_deflection <= 0.8):
        ap.error("deflections are outside the conservative supported range")
    outdir = args.output_dir.resolve()
    meshdir = outdir / "meshes"
    meshdir.mkdir(parents=True, exist_ok=True)
    expected = [{"object": n, "filename": f"{slug}.stl", "slug": slug} for n, slug in OBJECTS]
    cfg = {"assembly": str(ASSEMBLY.resolve()), "source_rel": str(ASSEMBLY.relative_to(ROOT)),
           "meshdir": str(meshdir), "objects": expected,
           "linear": args.linear_deflection, "angular": args.angular_deflection}
    macro = r'''import FreeCAD as App, MeshPart, json, os, traceback
C=json.loads(@@CFG@@); d=None; errors=[]; rows=[]
try:
 d=App.openDocument(C['assembly'])
 for item in C['objects']:
  obj=d.getObject(item['object'])
  if obj is None: raise RuntimeError('missing assembly object '+item['object'])
  shape=obj.Shape
  if shape.isNull() or not shape.isValid() or len(shape.Solids)!=1:
   raise RuntimeError('invalid/non-single-solid source '+obj.Name)
  b=shape.BoundBox
  # Move into a part-local frame while preserving orientation and dimensions.
  shape=shape.copy()
  shape.translate(App.Vector(-(b.XMin+b.XMax)/2.0, -(b.YMin+b.YMax)/2.0, -b.ZMin))
  mesh=MeshPart.meshFromShape(Shape=shape, LinearDeflection=C['linear'], AngularDeflection=C['angular'], Relative=False)
  if mesh.CountFacets==0: raise RuntimeError('empty tessellation '+obj.Name)
  p=os.path.join(C['meshdir'],item['filename'])
  mesh.write(p)
  mb=mesh.BoundBox
  rows.append({'object':obj.Name,'label':obj.Label,'filename':item['filename'],'source_type':obj.TypeId,
   'volume_mm3':obj.Shape.Volume,'source_bbox_mm':[b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax],
   'local_mesh_bbox_mm':[mb.XMin,mb.YMin,mb.ZMin,mb.XMax,mb.YMax,mb.ZMax],
   'facets':mesh.CountFacets,'vertices':mesh.CountPoints,'solid_mesh':mesh.isSolid()})
except Exception as e:
 errors=[str(e),traceback.format_exc()]
finally:
 if d is not None:
  try: App.closeDocument(d.Name)
  except Exception: pass
manifest={'source':C['source_rel'],'linear_deflection_mm':C['linear'],'angular_deflection_rad':C['angular'],'errors':errors,'parts':rows}
with open(os.path.join(C['meshdir'],'mesh-manifest.json'),'w') as f: json.dump(manifest,f,indent=2)
print('PENDANT_MESH_EXPORT='+json.dumps({'errors':errors,'parts':rows}))
'''.replace("@@CFG@@", repr(json.dumps(cfg)))
    with tempfile.TemporaryDirectory(prefix="pendant-print-export-") as td:
        m = Path(td) / "export.FCMacro"
        m.write_text(macro)
        proc = subprocess.run([str(args.freecadcmd), str(m)], text=True, capture_output=True, timeout=180)
    print(proc.stdout)
    if proc.returncode:
        print(proc.stderr)
        return proc.returncode
    manifest_path = meshdir / "mesh-manifest.json"
    if not manifest_path.is_file():
        print(proc.stderr)
        raise SystemExit("FreeCADCmd did not produce a mesh manifest")
    result = json.loads(manifest_path.read_text())
    if result["errors"] or len(result["parts"]) != len(OBJECTS):
        raise SystemExit("mesh export failed: " + json.dumps(result["errors"]))
    print(f"Exported {len(result['parts'])} one-solid source shapes to {meshdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
