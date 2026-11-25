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


def macro_source(document: Path, names: list[str], digest: str,
                 match_object: str | None, against: list[str], tolerance: float,
                 angular_tolerance: float) -> str:
    cfg = json.dumps({'document': str(document.resolve()), 'objects': names, 'sha256': digest,
                      'match_object': match_object, 'against': against,
                      'tolerance': tolerance, 'angular_tolerance': angular_tolerance})
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
def nested_close(a,b,tol):
    if isinstance(a,(tuple,list)) and isinstance(b,(tuple,list)):
        return len(a)==len(b) and all(nested_close(x,y,tol) for x,y in zip(a,b))
    if hasattr(a,'x') and hasattr(b,'x'):
        return max(abs(a.x-b.x),abs(a.y-b.y),abs(a.z-b.z))<=tol
    try: return abs(float(a)-float(b))<=tol
    except Exception: return a==b
def same_bspline_definition(a,b,tol):
    if type(a).__name__!='BSplineSurface' or type(b).__name__!='BSplineSurface': return False
    keys=('UDegree','VDegree','getUKnots','getVKnots','getUMultiplicities','getVMultiplicities','getPoles','getWeights')
    for key in keys:
        av=getattr(a,key); bv=getattr(b,key)
        av=av() if callable(av) else av; bv=bv() if callable(bv) else bv
        if not nested_close(av,bv,tol): return False
    return True
try:
    d=App.openDocument(C['document']); opened.append(d.Name)
    shapes={}
    for name in C['objects']:
        obj=d.getObject(name)
        if obj is None:
            report['errors'].append('missing object: '+name); continue
        row=shape_info(obj)
        shapes[name]=obj.Shape
        row['links']={p:link_value(getattr(obj,p)) for p in obj.PropertiesList
                      if 'Link' in obj.getTypeIdOfProperty(p)}
        report['objects'][name]=row
    if C['match_object']:
        target_name=C['match_object']
        if target_name not in shapes:
            report['errors'].append('surface-match object must also be listed with --object: '+target_name)
        else:
            target=shapes[target_name]; by_source={}; skipped={}; exceptions=[]; fallback_matches=0
            for source_name in C['against']:
                if source_name not in shapes:
                    report['errors'].append('surface-match source must also be listed with --object: '+source_name)
                    continue
                source=shapes[source_name]; matched=[]
                for ti,tf in enumerate(target.Faces,1):
                    indices=[]
                    for si,sf in enumerate(source.Faces,1):
                        left,right=tf.Surface,sf.Surface
                        if type(left).__name__ != type(right).__name__:
                            key=type(left).__name__+' vs '+type(right).__name__
                            skipped[key]=skipped.get(key,0)+1
                            continue
                        try:
                            if left.isSame(right,C['tolerance'],C['angular_tolerance']): indices.append(si)
                        except Exception as exc:
                            exceptions.append({'target_face':ti,'source_object':source_name,
                                               'source_face':si,'surface_type':type(left).__name__,
                                               'error':repr(exc)})
                            if same_bspline_definition(left,right,C['tolerance']):
                                indices.append(si); fallback_matches+=1
                    if indices: matched.append({'target_face':ti,'source_faces':indices,
                                                'surface_type':type(tf.Surface).__name__,'area_mm2':tf.Area})
                by_source[source_name]={'matched_target_face_count':len(matched),'matches':matched}
            union=sorted({m['target_face'] for row in by_source.values() for m in row['matches']})
            report['surface_provenance']={'target_object':target_name,'sources':by_source,
                'matched_target_face_union_count':len(union),
                'unmatched_target_face_indices':sorted(set(range(1,len(target.Faces)+1))-set(union)),
                'comparison':{'support_surface_isSame':True,'linear_tolerance':C['tolerance'],
                    'angular_tolerance':C['angular_tolerance'],'same_python_surface_type_only':True,
                    'skipped_different_type_pair_count':sum(skipped.values()),
                    'skipped_different_type_pairs':skipped,'exception_count':len(exceptions),
                    'bspline_definition_fallback_match_count':fallback_matches,
                    'unresolved_exception_count':len(exceptions)-fallback_matches,
                    'exceptions':exceptions,'complete_without_unresolved_exceptions':len(exceptions)==fallback_matches}}
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
    ap.add_argument('--match-object',help='optionally map this object’s support surfaces to other listed objects')
    ap.add_argument('--against',action='append',default=[],help='source object for support-surface matching; repeatable')
    ap.add_argument('--surface-tolerance',type=float,default=1e-7)
    ap.add_argument('--angular-tolerance',type=float,default=1e-7)
    ap.add_argument('--freecadcmd',default=os.environ.get('FREECADCMD'))
    ap.add_argument('--timeout',type=int,default=170)
    args=ap.parse_args()
    if not args.document.is_file(): ap.error(f'document not found: {args.document}')
    if not 1 <= args.timeout <= 180: ap.error('--timeout must be between 1 and 180 seconds')
    if args.match_object and not args.against: ap.error('--match-object requires at least one --against source')
    if args.against and not args.match_object: ap.error('--against requires --match-object')
    if args.surface_tolerance <= 0 or args.angular_tolerance <= 0: ap.error('surface tolerances must be positive')
    cmd=args.freecadcmd or (str(DEFAULT_CMD) if DEFAULT_CMD.is_file() else None)
    if not cmd: ap.error('freecadcmd not found; pass --freecadcmd or set FREECADCMD')
    gui=subprocess.run(['pgrep','-x','FreeCAD'],capture_output=True,text=True)
    if gui.returncode==0 and gui.stdout.strip(): raise SystemExit('FreeCAD GUI process detected; close it before probing (PID(s): '+gui.stdout.strip()+')')
    digest=hashlib.sha256(args.document.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix='freecad-surface-probe-') as td:
        macro=Path(td)/'probe.FCMacro'; macro.write_text(macro_source(args.document,args.objects,digest,
            args.match_object,args.against,args.surface_tolerance,args.angular_tolerance),encoding='utf-8')
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
    summary={'json':str(args.json),'objects':{k:{'valid':v.get('valid'),'solid_count':v.get('solid_count'),'face_count':v.get('face_count'),'volume_mm3':v.get('volume_mm3')} for k,v in record['objects'].items()},'sha256':digest}
    if 'surface_provenance' in record:
        sp=record['surface_provenance']
        summary['surface_provenance']={'target_object':sp['target_object'],
            'matched_target_face_union_count':sp['matched_target_face_union_count'],
            'unmatched_target_face_indices':sp['unmatched_target_face_indices'],
            'matched_target_face_count_by_source':{k:v['matched_target_face_count'] for k,v in sp['sources'].items()},
            'exception_count':sp['comparison']['exception_count'],
            'bspline_definition_fallback_match_count':sp['comparison']['bspline_definition_fallback_match_count'],
            'unresolved_exception_count':sp['comparison']['unresolved_exception_count']}
    print(json.dumps(summary,sort_keys=True))
    return 0

if __name__=='__main__': raise SystemExit(main())
