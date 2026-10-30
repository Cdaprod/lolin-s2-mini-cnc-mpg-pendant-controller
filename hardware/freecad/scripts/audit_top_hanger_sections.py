#!/usr/bin/env python3
"""Read-only top-hanger opening/material section audit for a FreeCAD document.

The probe reads the saved pre-hanger shell shapes and intersects them with
lines parallel to global Y. It does not recompute or save the CAD document.
The output is a sparse section audit, not a global wall-thickness or stress
analysis. Run with FreeCAD closed so the source is not concurrently edited.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile


SCRIPT = Path(__file__).resolve()
FREECAD_DIR = SCRIPT.parents[1]
DEFAULT_DOCUMENT = FREECAD_DIR / "pendant.FCStd"
DEFAULT_CMD = Path("/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd")


def macro_source(document: Path, digest: str, cut_y: list[float]) -> str:
    cfg = json.dumps({"document": str(document.resolve()), "sha256": digest, "cut_y": cut_y})
    return r'''import FreeCAD as App, Part, json, traceback
C=json.loads(@@CFG@@)
report={'document':C['document'],'sha256':C['sha256'],'freecad_version':App.Version(),
        'source_recomputed':False,'sections':{},'sketches':{},'errors':[]}
opened=[]
def intervals(shape,x,z):
    line=Part.makeLine(App.Vector(x,60,z),App.Vector(x,90,z))
    sec=shape.section(line)
    pts=sorted(set(round(v.Point.y,7) for v in sec.Vertexes))
    return [[pts[i],pts[i+1]] for i in range(0,len(pts)-1,2)]
def residual(spans,y):
    containing=[(a,b) for a,b in spans if a-1e-6<=y<=b+1e-6]
    if containing:
        a,b=containing[0]
        return {'state':'inside-shell','outer_surface_y_mm':b,'remaining_web_mm':round(max(0.0,b-y),7)}
    if spans and y>max(b for _,b in spans):
        return {'state':'profile-edge-outside-shell','outer_surface_y_mm':max(b for _,b in spans),'remaining_web_mm':None}
    return {'state':'no-containing-section','outer_surface_y_mm':None,'remaining_web_mm':None}
try:
    d=App.openDocument(C['document']); opened.append(d.Name)
    p=d.getObject('HangerParameters')
    report['parameters_mm']={k:float(getattr(p,k).Value) for k in ('SlotCenterY','SlotLength','SlotWidth')}
    hanger_sketches=['SmallHangerProfileBody','SmallHangerProfileBody002','Sketch015']
    for name in hanger_sketches:
        o=d.getObject(name)
        if o is None:
            report['errors'].append('missing sketch '+name); continue
        b=o.Shape.BoundBox
        report['sketches'][name]={'label':o.Label,'fully_constrained':getattr(o,'FullyConstrained',None),
            'placement':str(o.Placement),'global_bbox_mm':[b.XMin,b.XMax,b.YMin,b.YMax],
            'geometry':[str(g) for g in getattr(o,'Geometry',[])],
            'constraints':[str(c) for c in getattr(o,'Constraints',[])],
            'downstream_consumers':[x.Name for x in o.OutList]}
    cases=[('front','PreserveOriginalFrontExterior',[-14.0,-15.0],[-12.0,0.0,12.0]),
           ('rear','USBConformalCoverSeatBody002',[-24.0,-25.0],[-12.0,0.0,12.0])]
    for role,objname,zs,xs in cases:
        obj=d.getObject(objname)
        if obj is None:
            report['errors'].append('missing shell base '+objname); continue
        shape=obj.Shape
        if shape.isNull() or not shape.isValid():
            report['errors'].append('invalid shell base '+objname); continue
        rows=[]
        for z in zs:
            for x in xs:
                spans=intervals(shape,x,z)
                rows.append({'x_mm':x,'z_mm':z,'shell_intervals_y_mm':spans,
                    'cut_edges':[{'y_mm':y,**residual(spans,y)} for y in C['cut_y']]})
        report['sections'][role]={'source_object':objname,'valid':shape.isValid(),
            'solid_count':len(shape.Solids),'volume_mm3':shape.Volume,'samples':rows}
except Exception as e:
    report['errors'].append(repr(e)); report['traceback']=traceback.format_exc()
print('TOP_HANGER_AUDIT='+json.dumps(report,sort_keys=True))
for name in opened:
    try: App.closeDocument(name)
    except Exception: pass
'''.replace("@@CFG@@", repr(cfg))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--document", type=Path, default=DEFAULT_DOCUMENT)
    ap.add_argument("--cut-y", type=float, action="append", default=None,
                    help="global Y of a proposed upper cut edge; repeatable (default: 83.5 and 84.1278678)")
    ap.add_argument("--json", type=Path, required=True, help="report output path")
    ap.add_argument("--freecadcmd", default=os.environ.get("FREECADCMD"))
    ap.add_argument("--timeout", type=int, default=150)
    args = ap.parse_args()
    if not args.document.is_file(): ap.error(f"document not found: {args.document}")
    if not 1 <= args.timeout <= 180: ap.error("--timeout must be between 1 and 180 seconds")
    cut_y = args.cut_y if args.cut_y is not None else [83.5, 84.12786781815633]
    cmd = args.freecadcmd or (str(DEFAULT_CMD) if DEFAULT_CMD.is_file() else None)
    if not cmd: ap.error("freecadcmd not found; pass --freecadcmd or set FREECADCMD")
    gui = subprocess.run(["pgrep", "-x", "FreeCAD"], capture_output=True, text=True)
    if gui.returncode == 0 and gui.stdout.strip():
        raise SystemExit("FreeCAD GUI process detected; close it before auditing (PID(s): " + gui.stdout.strip() + ")")
    digest = hashlib.sha256(args.document.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix="freecad-hanger-audit-") as td:
        macro = Path(td) / "audit.FCMacro"
        macro.write_text(macro_source(args.document, digest, cut_y), encoding="utf-8")
        proc = subprocess.Popen([cmd, str(macro)], stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, start_new_session=True)
        try:
            output, _ = proc.communicate(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            try: os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError: pass
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try: os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                proc.wait(timeout=5)
            output, _ = proc.communicate()
            raise RuntimeError(f"hanger audit timed out after {args.timeout}s; owned worker terminated\n{output[-2000:]}")
    if proc.returncode:
        raise RuntimeError(f"FreeCADCmd exited {proc.returncode}\n{output[-3000:]}")
    record_line = next((line for line in output.splitlines() if "TOP_HANGER_AUDIT=" in line), None)
    if record_line is None: raise RuntimeError("FreeCADCmd returned no audit report\n" + output[-3000:])
    record = json.loads(record_line.split("TOP_HANGER_AUDIT=", 1)[1])
    if record["errors"]: raise RuntimeError("hanger audit failed: " + json.dumps(record["errors"]))
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {role: [{"x_mm": s["x_mm"], "z_mm": s["z_mm"], "cut_edges": s["cut_edges"]}
                      for s in data["samples"]] for role, data in record["sections"].items()}
    print(json.dumps({"json": str(args.json), "sha256": digest, "sections": summary}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
