#!/usr/bin/env python3
"""Refresh and validate the modular pendant assembly in dependency order.

Close the assembly in the FreeCAD GUI first. This bounded worker loads the
master, recomputes editable component sources, saves changed components with
backups, then recomputes and validates the linked assembly.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile

SCRIPT = Path(__file__).resolve()
FREECAD_DIR = SCRIPT.parents[1]
DEFAULT_CMD = Path('/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd')
MASTER = FREECAD_DIR / 'pendant-master.FCStd'
ASSEMBLY = FREECAD_DIR / 'pendant-modular-assembly.FCStd'
COMPONENTS = (
    'display-retainer.FCStd', 'usb-tethered-cover.FCStd', 'faceplate-locators.FCStd',
    'breakout-board.FCStd',
)


def worker_source(assembly: Path | None = None) -> str:
    cfg = json.dumps({'base': str(FREECAD_DIR), 'master': str(MASTER),
                      'assembly': str(assembly or ASSEMBLY), 'components': COMPONENTS})
    return r'''import FreeCAD as App, json, traceback, os, shutil, time
from pathlib import Path
C=json.loads(@@CFG@@); report={'errors':[],'components':[],'links':[],'interim':[]}
opened=[]
def open_doc(path):
    path=Path(path).resolve()
    for d in App.listDocuments().values():
        if d.FileName and Path(d.FileName).resolve()==path: return d
    d=App.openDocument(str(path)); opened.append(d.Name); return d
def info(obj):
    s=obj.Shape; b=s.BoundBox
    return {'valid':bool(s and not s.isNull() and s.isValid()),'solids':len(s.Solids),
            'volume':s.Volume,'bbox':[b.XMin,b.XMax,b.YMin,b.YMax,b.ZMin,b.ZMax]}
def backup(path):
    dest=Path(C['base'])/'backups'/('refresh-'+time.strftime('%Y%m%d-%H%M%S'))
    dest.mkdir(parents=True,exist_ok=True); shutil.copy2(path,dest/Path(path).name)
try:
    if not Path(C['assembly']).is_file(): raise RuntimeError('assembly file is missing')
    master=open_doc(C['master']); master.recompute()
    docs={}
    for fn in C['components']: docs[fn]=open_doc(Path(C['base'])/'pendant-bodies'/fn)
    for fn,d in docs.items():
        # External spreadsheet expressions can remain cached after reopening
        # the master with changed values. Re-assigning each serialized
        # cross-document expression forces FreeCAD to resolve the live source
        # before recomputing the component.
        refreshed_expressions=[]
        for obj in d.Objects:
            for expression_path, expression_text in getattr(obj,'ExpressionEngine',[]):
                if '#<<' in expression_text:
                    obj.touch()
                    obj.setExpression(expression_path,expression_text)
                    refreshed_expressions.append({'object':obj.Name,'path':expression_path})
        d.recompute()
        bodies=[o for o in d.Objects if o.TypeId=='PartDesign::Body' and getattr(o,'Tip',None)]
        if not bodies: raise RuntimeError('no tipped PartDesign Body in '+fn)
        invalid=[]
        for b in bodies:
            if not info(b)['valid'] or not info(b.Tip)['valid'] or 'Invalid' in b.State or 'Invalid' in b.Tip.State:
                invalid.append(b.Name)
        if invalid: raise RuntimeError('invalid Body/Tip in '+fn+': '+','.join(invalid))
        # Reject invalid feature states after recompute. Expression errors are
        # surfaced by FreeCAD as Invalid states on the dependent feature/body.
        for obj in d.Objects:
            if 'Invalid' in getattr(obj,'State',[]):
                raise RuntimeError('invalid feature state in '+fn+'/'+obj.Name+': '+obj.getStatusString())
        # Persist any source whose geometry/placement consumes a master
        # expression. Otherwise a fresh process can reopen its cached Tip
        # before the external expression has caused a recompute, leaving the
        # assembly link stale. Back up each source before saving it.
        if refreshed_expressions:
            backup(d.FileName); d.save()
        report['components'].append({'file':fn,'bodies':[{'name':b.Name,'shape':info(b)} for b in bodies],
                                     'saved':bool(refreshed_expressions),
                                     'refreshed_external_expressions':refreshed_expressions})
    assembly=open_doc(C['assembly']); assembly.recompute()
    links=[o for o in assembly.Objects if o.TypeId=='App::Link']
    for link in links:
        target=link.LinkedObject
        # These links are generated with LinkPlacement equal to the source
        # Body's placement. Reapply that placement after recomputing source
        # documents so master-driven Body placement changes reach the assembly.
        link.LinkPlacement=target.Placement
    assembly.recompute()
    for link in links:
        target=link.LinkedObject
        a,b=info(link),info(target)
        if not a['valid'] or not b['valid'] or abs(a['volume']-b['volume'])>1e-6 or any(abs(x-y)>1e-6 for x,y in zip(a['bbox'],b['bbox'])):
            raise RuntimeError('linked shape invalid or mismatched: '+link.Name)
        report['links'].append({'name':link.Name,'target':target.Name,'file':target.Document.FileName,'shape':a})
    static=[o for o in assembly.Objects if o.Name.startswith('Interim_')]
    for obj in static:
        if not info(obj)['valid'] or info(obj)['solids']!=1: raise RuntimeError('invalid static interim shape '+obj.Name)
        report['interim'].append({'name':obj.Name,'shape':info(obj)})
    if len(links)!=5 or len(static)!=5: raise RuntimeError('unexpected assembly inventory')
    # Save only the assembly, backing it up before any overwrite.
    backup(assembly.FileName); assembly.save()
    assembly_name=assembly.Name
    App.closeDocument(assembly_name); opened.remove(assembly_name)
    assembly=App.openDocument(C['assembly']); opened.append(assembly.Name); assembly.recompute()
    again=[o for o in assembly.Objects if o.TypeId=='App::Link']
    reopened_links=[]
    for link in again:
        target=link.LinkedObject
        a,b=info(link),info(target)
        if not a['valid'] or not b['valid'] or abs(a['volume']-b['volume'])>1e-6 or any(abs(x-y)>1e-6 for x,y in zip(a['bbox'],b['bbox'])):
            raise RuntimeError('reopened link/source mismatch: '+link.Name)
        reopened_links.append({'name':link.Name,'target':target.Name,'file':target.Document.FileName,'shape':a})
    if len(again)!=5: raise RuntimeError('assembly failed save/reopen inventory validation')
    report['reopened_links']=reopened_links
    report['reopen_ok']=True
except Exception as e: report['errors']=[str(e),traceback.format_exc()]
finally:
    for n in reversed(opened):
        if n in App.listDocuments():
            try: App.closeDocument(n)
            except Exception: pass
print('MODULAR_ASSEMBLY_REFRESH='+json.dumps(report))
'''.replace('@@CFG@@', repr(cfg))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--freecadcmd', default=os.environ.get('FREECADCMD'))
    p.add_argument('--assembly', type=Path, default=ASSEMBLY,
                   help='assembly document to refresh (defaults to the production modular assembly)')
    p.add_argument('--timeout', type=int, default=170)
    a = p.parse_args()
    if not 1 <= a.timeout <= 180: p.error('--timeout must be between 1 and 180 seconds')
    cmd = a.freecadcmd or (str(DEFAULT_CMD) if DEFAULT_CMD.is_file() else None)
    if not cmd: raise SystemExit('freecadcmd not found; pass --freecadcmd or set FREECADCMD')
    # Never race the interactive application against a save/recompute worker.
    ps = subprocess.run(['pgrep','-afil','FreeCAD.app/Contents/MacOS/FreeCAD'],capture_output=True,text=True)
    if ps.returncode == 0 and ps.stdout.strip():
        raise SystemExit('FreeCAD GUI process detected; close the assembly and GUI before refresh:\n'+ps.stdout.strip())
    assembly = a.assembly.resolve()
    if not assembly.is_file():
        raise SystemExit(f'assembly file does not exist: {assembly}')
    with tempfile.TemporaryDirectory(prefix='pendant-assembly-refresh-') as td:
        macro=Path(td)/'refresh.FCMacro'; macro.write_text(worker_source(assembly),encoding='utf-8')
        proc=subprocess.Popen([cmd,str(macro)],cwd=FREECAD_DIR,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                              text=True,start_new_session=True)
        try: out,_=proc.communicate(timeout=a.timeout)
        except subprocess.TimeoutExpired:
            try: os.killpg(proc.pid,signal.SIGTERM)
            except ProcessLookupError: pass
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try: os.killpg(proc.pid,signal.SIGKILL)
                except ProcessLookupError: pass
                proc.wait(timeout=5)
            out,_=proc.communicate(); print(out,end=''); print('Refresh worker timed out and was terminated'); return 124
    print(out,end='')
    marker=next((line.split('MODULAR_ASSEMBLY_REFRESH=',1)[1] for line in out.splitlines() if 'MODULAR_ASSEMBLY_REFRESH=' in line),None)
    if marker is None: return proc.returncode or 1
    result=json.loads(marker); print(json.dumps(result,indent=2))
    return 0 if result.get('reopen_ok') and not result.get('errors') else 1


if __name__ == '__main__': raise SystemExit(main())
