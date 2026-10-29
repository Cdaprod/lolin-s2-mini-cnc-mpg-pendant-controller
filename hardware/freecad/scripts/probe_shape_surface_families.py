#!/usr/bin/env python3
"""Read saved FreeCAD shapes and report topology/surface-family baselines.

This is an inspection tool only: it opens a document, reads saved Shape data,
does not recompute or save, and closes documents opened by its worker.
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
DEFAULT_CMD = Path('/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd')


def macro_source(document: Path, names: list[str], digest: str) -> str:
    cfg = json.dumps({'document': str(document.resolve()), 'objects': names, 'sha256': digest})
    return r'''import FreeCAD as App, json, traceback
C=json.loads(@@CFG@@)
report={'document':C['document'],'sha256':C['sha256'],'freecad_version':App.Version(),'objects':{},'errors':[]}
opened=[]
def link_value(v):
    if hasattr(v,'Name'): return {'object':v.Name,'document':getattr(getattr(v,'Document',None),'Name',None)}
    if isinstance(v,(tuple,list)): return [link_value(x) for x in v]
    return str(v)
def shape_info(obj):
    s=getattr(obj,'Shape',None)
    if s is None or s.isNull(): return {'valid':False,'type':obj.TypeId,'null_shape':True}
    b=s.BoundBox; families={}
    for f in s.Faces:
        surf=f.Surface; name=type(surf).__name__
        row=families.setdefault(name,{'face_count':0,'area_mm2':0.0,'parameters':{}})
        row['face_count']+=1; row['area_mm2']+=f.Area
        for key in ('Radius','MajorRadius','MinorRadius'):
            try: val=round(float(getattr(surf,key)),9)
            except Exception: continue
            k=key+'='+str(val); row['parameters'][k]=row['parameters'].get(k,0)+1
    return {'type':obj.TypeId,'valid':bool(s.isValid()),'solid_count':len(s.Solids),
            'face_count':len(s.Faces),'edge_count':len(s.Edges),'volume_mm3':s.Volume,
            'surface_area_mm2':s.Area,'bounds_mm':[b.XMin,b.XMax,b.YMin,b.YMax,b.ZMin,b.ZMax],
            'surface_families':families,'placement':str(getattr(obj,'Placement',''))}
try:
    d=App.openDocument(C['document']); opened.append(d.Name)
    for name in C['objects']:
        obj=d.getObject(name)
        if obj is None:
            report['errors'].append('missing object: '+name); continue
        row=shape_info(obj)
        row['links']={p:link_value(getattr(obj,p)) for p in ('Base','Tool','BaseFeature','Profile','Support','Group') if p in obj.PropertiesList}
        report['objects'][name]=row
except Exception as exc:
    report['errors'].append(repr(exc)); report['traceback']=traceback.format_exc()
finally:
    for name in reversed(opened):
        try: App.closeDocument(name)
        except Exception: pass
print('SHAPE_SURFACE_PROBE='+json.dumps(report,sort_keys=True))
'''.replace('@@CFG@@', repr(cfg))


def main() -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('document',type=Path)
    ap.add_argument('--object',dest='objects',action='append',required=True,help='object internal name; repeat for multiple objects')
    ap.add_argument('--json',type=Path,required=True,help='write machine-readable output here')
    ap.add_argument('--freecadcmd',default=os.environ.get('FREECADCMD'))
    ap.add_argument('--timeout',type=int,default=170)
    args=ap.parse_args()
    if not args.document.is_file(): ap.error(f'document not found: {args.document}')
    if not 1 <= args.timeout <= 180: ap.error('--timeout must be between 1 and 180 seconds')
    cmd=args.freecadcmd or (str(DEFAULT_CMD) if DEFAULT_CMD.is_file() else None)
    if not cmd: ap.error('freecadcmd not found; pass --freecadcmd or set FREECADCMD')
    gui=subprocess.run(['pgrep','-x','FreeCAD'],capture_output=True,text=True)
    if gui.returncode==0 and gui.stdout.strip(): raise SystemExit('FreeCAD GUI process detected; close it before probing (PID(s): '+gui.stdout.strip()+')')
    digest=hashlib.sha256(args.document.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix='freecad-surface-probe-') as td:
        macro=Path(td)/'probe.FCMacro'; macro.write_text(macro_source(args.document,args.objects,digest),encoding='utf-8')
        proc=subprocess.Popen([cmd,str(macro)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,start_new_session=True)
        try: output,_=proc.communicate(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            try: os.killpg(proc.pid,signal.SIGTERM)
            except ProcessLookupError: pass
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try: os.killpg(proc.pid,signal.SIGKILL)
                except ProcessLookupError: pass
                proc.wait(timeout=5)
            output,_=proc.communicate()
            raise RuntimeError(f'FreeCADCmd surface probe timed out after {args.timeout}s; worker terminated.\n{output[-2000:]}')
    if proc.returncode: raise RuntimeError(f'FreeCADCmd exited {proc.returncode}.\n{output[-3000:]}')
    marker=next((line.split('SHAPE_SURFACE_PROBE=',1)[1] for line in output.splitlines() if 'SHAPE_SURFACE_PROBE=' in line),None)
    if marker is None: raise RuntimeError('FreeCADCmd returned no probe record.\n'+output[-3000:])
    record=json.loads(marker)
    if record['errors']: raise RuntimeError('Probe failed: '+json.dumps(record['errors']))
    args.json.parent.mkdir(parents=True,exist_ok=True)
    args.json.write_text(json.dumps(record,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({'json':str(args.json),'objects':{k:{'valid':v.get('valid'),'solid_count':v.get('solid_count'),'face_count':v.get('face_count'),'volume_mm3':v.get('volume_mm3')} for k,v in record['objects'].items()},'sha256':digest},sort_keys=True))
    return 0

if __name__=='__main__': raise SystemExit(main())
