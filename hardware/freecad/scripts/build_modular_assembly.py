#!/usr/bin/env python3
"""Build a portable linked assembly without recomputing the legacy monolith.

Migrated component Bodies are App::Links to their editable source documents.
Bodies whose dependency histories are not yet safe to migrate are embedded as
explicitly labeled static BREP snapshots extracted from pendant.FCStd.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import zipfile

SCRIPT = Path(__file__).resolve()
FREECAD_DIR = SCRIPT.parents[1]
ROOT = next((p for p in SCRIPT.parents if (p / ".git").exists()), None)
if ROOT is None:
    raise SystemExit("Could not locate repository root")

DEFAULT_CMD = Path("/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd")
SOURCE_DOC = FREECAD_DIR / "pendant.FCStd"
OUTPUT_DOC = FREECAD_DIR / "pendant-modular-assembly.FCStd"
COMPONENTS = {
    "display-retainer.FCStd": ["Body_DisplayRetainer_EditableV2"],
    "usb-tethered-cover.FCStd": ["Body_USBTetheredCover"],
    "faceplate-locators.FCStd": ["Body_FaceplateLocator_A", "Body_FaceplateLocator_B"],
}
INTERIM = {
    "Body": "Front shell",
    "Body002": "Rear shell",
    "Body003": "Upper faceplate",
    "Body_EncoderFacePlate": "Encoder faceplate",
    "Body_EncoderPocket": "Encoder pocket",
    "Body006": "Breakout board",
}


def find_freecadcmd(override: str | None) -> str:
    command = override or os.environ.get("FREECADCMD")
    if command:
        return command
    if DEFAULT_CMD.is_file():
        return str(DEFAULT_CMD)
    raise SystemExit("freecadcmd not found; pass --freecadcmd or set FREECADCMD")


def macro_source(freecad_dir: Path, brep_dir: Path, output: Path, source_hash: str) -> str:
    cfg = json.dumps({
        "freecad_dir": str(freecad_dir),
        "brep_dir": str(brep_dir),
        "output": str(output),
        "source_hash": source_hash,
        "components": COMPONENTS,
        "interim": INTERIM,
    })
    return r'''import FreeCAD as App, Part, json, traceback, os
from pathlib import Path
CFG=json.loads(@@CFG@@)
base=Path(CFG['freecad_dir']); report={'errors':[],'interim':[],'links':[]}
opened=[]
def open_doc(path):
    path=Path(path).resolve()
    for d in App.listDocuments().values():
        if d.FileName and Path(d.FileName).resolve()==path: return d
    d=App.openDocument(str(path)); opened.append(d.Name); return d
def shape_info(obj):
    s=obj.Shape; b=s.BoundBox
    return {'valid':bool(s and not s.isNull() and s.isValid()),'solids':len(s.Solids),
            'volume':s.Volume,'bbox':[b.XMin,b.XMax,b.YMin,b.YMax,b.ZMin,b.ZMax]}
def close_opened():
    names=list(opened)
    for name in reversed(names):
        if name in App.listDocuments():
            try: App.closeDocument(name)
            except Exception: pass
def validate_link(obj):
    target=obj.LinkedObject
    a,b=shape_info(obj),shape_info(target)
    if not a['valid'] or not b['valid']: raise RuntimeError('invalid link shape: '+obj.Name)
    if abs(a['volume']-b['volume'])>1e-6: raise RuntimeError('link volume mismatch: '+obj.Name)
    if any(abs(x-y)>1e-6 for x,y in zip(a['bbox'],b['bbox'])): raise RuntimeError('link bounding box mismatch: '+obj.Name)
    return {'name':obj.Name,'target_file':target.Document.FileName,'target':target.Name,'link':a,'source':b}
try:
    # Cross-document expressions in the locator source require the master first.
    master=open_doc(base/'pendant-master.FCStd'); master.recompute()
    component_docs={}
    for filename in CFG['components']:
        component_docs[filename]=open_doc(base/'pendant-bodies'/filename)
    for filename,doc in component_docs.items():
        doc.recompute()
        bodies=[o for o in doc.Objects if o.TypeId=='PartDesign::Body' and getattr(o,'Tip',None)]
        if not bodies: raise RuntimeError('no tipped PartDesign Body in '+filename)
        for body in bodies:
            if not shape_info(body)['valid'] or not shape_info(body.Tip)['valid']:
                raise RuntimeError('invalid Body or Tip: '+filename+'/'+body.Name)
            if 'Invalid' in body.State or 'Invalid' in body.Tip.State:
                raise RuntimeError('Body or Tip has Invalid state: '+filename+'/'+body.Name)
    d=App.newDocument('PendantModularAssembly','Pendant Modular Assembly — Interim Linked Candidate')
    opened.append(d.Name)
    d.saveAs(CFG['output'])
    d.addProperty('App::PropertyString','MigrationStatus','Migration')
    d.MigrationStatus='PARTIAL: four editable Bodies are linked; six legacy Bodies are static BREP interim representations.'
    d.addProperty('App::PropertyString','MonolithicSource','Migration')
    d.MonolithicSource='pendant.FCStd SHA256='+CFG['source_hash']+' (retained unchanged; this candidate does not replace it)'
    d.addProperty('App::PropertyString','RefreshInstructions','Migration')
    d.RefreshInstructions='Save edited component docs, close the assembly in the GUI, then run scripts/refresh_modular_assembly.py.'
    assembly=d.addObject('App::Part','AssemblyRoot'); assembly.Label='Pendant — Modular Linked Assembly'
    editable=d.addObject('App::DocumentObjectGroup','EditableComponents'); editable.Label='Editable source component links'
    interim=d.addObject('App::DocumentObjectGroup','InterimBrepComponents')
    interim.Label='INTERIM static BREP — legacy histories not independently migrated'
    assembly.addObject(editable); assembly.addObject(interim)
    for name,label in CFG['interim'].items():
        s=Part.Shape(); s.read(str(Path(CFG['brep_dir'])/(name+'.brep')))
        obj=d.addObject('Part::Feature','Interim_'+name)
        obj.Label='INTERIM — '+label+' (static source BREP)'; obj.Shape=s; interim.addObject(obj)
        obj.addProperty('App::PropertyString','RepresentationStatus','Migration')
        obj.RepresentationStatus='Static, nonparametric BREP snapshot. Edit the original Body in pendant.FCStd; rebuild this assembly after migration.'
        obj.addProperty('App::PropertyString','SourceDocument','Migration'); obj.SourceDocument='pendant.FCStd'
        obj.addProperty('App::PropertyString','SourceObjectName','Migration'); obj.SourceObjectName=name
        obj.addProperty('App::PropertyString','SourceSHA256','Migration'); obj.SourceSHA256=CFG['source_hash']
        info=shape_info(obj)
        if not info['valid'] or info['solids']!=1: raise RuntimeError('invalid interim source BREP: '+name)
        report['interim'].append({'source':name,'label':label,'shape':info})
    index=0
    for filename,names in CFG['components'].items():
        doc=component_docs[filename]
        for body_name in names:
            target=doc.getObject(body_name)
            if target is None: raise RuntimeError('missing component Body: '+filename+'/'+body_name)
            link=d.addObject('App::Link','Editable_'+body_name)
            link.Label=target.Label+' — editable source link'
            link.setLink(target); link.LinkPlacement=target.Placement; editable.addObject(link)
            report['links'].append(validate_link(link)); index+=1
    if len(report['links'])!=4 or len(report['interim'])!=6:
        raise RuntimeError('unexpected component count in assembly')
    d.recompute()
    # Validate all links again after the assembly recompute.
    report['links']=[validate_link(d.getObject(x['name'])) for x in report['links']]
    d.save()
    report['assembly_path']=d.FileName
    report['assembly_shape']=shape_info(assembly)
    # Save/close/reopen all documents in dependency order and revalidate links.
    close_opened(); opened=[]
    master=open_doc(base/'pendant-master.FCStd')
    for filename in CFG['components']: component_docs[filename]=open_doc(base/'pendant-bodies'/filename)
    d=open_doc(CFG['output']); d.recompute()
    links=[o for o in d.Objects if o.TypeId=='App::Link']
    report['reopened_links']=[validate_link(o) for o in links]
    interim_objs=[o for o in d.Objects if o.Name.startswith('Interim_')]
    report['reopened_interim']=[{'name':o.Name,'shape':shape_info(o)} for o in interim_objs]
    if len(links)!=4 or any(not x['shape']['valid'] for x in report['reopened_interim']):
        raise RuntimeError('assembly failed save/reopen validation')
    report['reopen_ok']=True
except Exception as exc:
    report['errors']=[str(exc),traceback.format_exc()]
finally:
    close_opened()
print('MODULAR_ASSEMBLY_BUILD='+json.dumps(report))
'''.replace('@@CFG@@', repr(cfg))


def terminate_group(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=5)


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=OUTPUT_DOC)
    parser.add_argument('--freecadcmd')
    parser.add_argument('--timeout',type=int,default=170)
    parser.add_argument('--replace',action='store_true',help='back up and replace an existing assembly output')
    args=parser.parse_args()
    if args.timeout<1 or args.timeout>180: parser.error('--timeout must be between 1 and 180 seconds')
    output=args.output.resolve()
    if output.exists():
        if not args.replace: raise SystemExit(f'{output} exists; pass --replace to back it up and rebuild')
        backup=FREECAD_DIR/'backups'/f'assembly-rebuild-{__import__("datetime").datetime.now().strftime("%Y%m%d-%H%M%S")}'
        backup.mkdir(parents=True,exist_ok=False); shutil.copy2(output,backup/output.name)
    if not SOURCE_DOC.is_file() or not (FREECAD_DIR/'pendant-master.FCStd').is_file():
        raise SystemExit('Missing source or master document')
    for filename in COMPONENTS:
        if not (FREECAD_DIR/'pendant-bodies'/filename).is_file(): raise SystemExit('Missing component: '+filename)
    source_hash=hashlib.sha256(SOURCE_DOC.read_bytes()).hexdigest()
    command=find_freecadcmd(args.freecadcmd)
    with tempfile.TemporaryDirectory(prefix='pendant-assembly-build-') as td:
        td_path=Path(td); brep_dir=td_path/'brep'; brep_dir.mkdir()
        with zipfile.ZipFile(SOURCE_DOC) as archive:
            for name in INTERIM:
                member=name+'.Shape.brp'
                if member not in archive.namelist(): raise SystemExit('Missing saved source BREP: '+member)
                (brep_dir/(name+'.brep')).write_bytes(archive.read(member))
        macro=td_path/'build_modular_assembly.FCMacro'
        macro.write_text(macro_source(FREECAD_DIR,brep_dir,output,source_hash),encoding='utf-8')
        proc=subprocess.Popen([command,str(macro)],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                              text=True,start_new_session=True)
        try:
            stdout,_=proc.communicate(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            terminate_group(proc); stdout,_=proc.communicate(); print(stdout,end='')
            print(f'FreeCAD worker exceeded {args.timeout}s and was terminated'); return 124
        print(stdout,end='')
        if proc.returncode: return proc.returncode
        marker=next((line.split('MODULAR_ASSEMBLY_BUILD=',1)[1] for line in stdout.splitlines()
                     if 'MODULAR_ASSEMBLY_BUILD=' in line),None)
        if marker is None: print('No structured FreeCAD validation report'); return 1
        result=json.loads(marker); print(json.dumps(result,indent=2))
        return 0 if result.get('reopen_ok') and not result.get('errors') else 1


if __name__=='__main__':
    raise SystemExit(main())
