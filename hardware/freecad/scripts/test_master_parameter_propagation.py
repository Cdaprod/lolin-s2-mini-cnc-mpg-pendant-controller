#!/usr/bin/env python3
"""Cold-start test for one master spreadsheet alias through the live assembly.

The test copies the modular project to a disposable directory, records the
baseline shape, refreshes the assembly at a test value, then restores the
original value and requires the reopened shape to match the baseline BREP.
No source document in the repository is opened for writing.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path


SCRIPT = Path(__file__).resolve()
FREECAD_DIR = SCRIPT.parents[1]
REFRESH_SCRIPT = FREECAD_DIR / "scripts" / "refresh_modular_assembly.py"
DEFAULT_FREECADCMD = Path("/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd")


def read_refresh_module():
    spec = importlib.util.spec_from_file_location("pendant_refresh", REFRESH_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load refresh workflow at {REFRESH_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_freecad(command: Path, macro: Path, timeout: float) -> str:
    result = subprocess.run(
        [str(command), str(macro)], capture_output=True, text=True,
        timeout=timeout, check=False,
    )
    output = result.stdout + result.stderr
    if result.returncode:
        raise RuntimeError(
            f"FreeCADCmd exited {result.returncode} running {macro.name}:\n{output[-4000:]}"
        )
    return output


def extract_record(output: str, marker: str) -> dict:
    for line in output.splitlines():
        if line.startswith(marker + "="):
            return json.loads(line.split("=", 1)[1])
    raise RuntimeError(f"FreeCADCmd returned no {marker} record:\n{output[-3000:]}")


def write_macro(path: Path, source: str, config: dict) -> None:
    path.write_text("CONFIG = " + repr(json.dumps(config)) + "\n" + source)


ALIAS_READ_MACRO = r'''import FreeCAD as App,json,traceback
C=json.loads(CONFIG);r={'errors':[]}
try:
 d=App.openDocument(C['master']);s=d.getObject(C['sheet'])
 cell=s.getCellFromAlias(C['alias'])
 if not cell: raise RuntimeError('master alias not found: '+C['alias'])
 r.update({'cell':cell,'value':str(s.get(cell))})
except Exception as e:r.update({'errors':[repr(e)],'traceback':traceback.format_exc()})
print('PARAM_ALIAS='+json.dumps(r,sort_keys=True))
for d in list(App.listDocuments().values()):App.closeDocument(d.Name)
'''

ALIAS_SET_MACRO = r'''import FreeCAD as App,json,traceback
C=json.loads(CONFIG);r={'errors':[]}
try:
 d=App.openDocument(C['master']);s=d.getObject(C['sheet']);cell=s.getCellFromAlias(C['alias'])
 if not cell: raise RuntimeError('master alias not found: '+C['alias'])
 s.set(cell,C['value']);d.recompute();d.save();r.update({'cell':cell,'value':str(s.get(cell))})
except Exception as e:r.update({'errors':[repr(e)],'traceback':traceback.format_exc()})
print('PARAM_ALIAS_SET='+json.dumps(r,sort_keys=True))
for d in list(App.listDocuments().values()):App.closeDocument(d.Name)
'''

ASSEMBLY_CHECK_MACRO = r'''import FreeCAD as App,Part,json,traceback
C=json.loads(CONFIG);r={'errors':[]}
def info(o):
 s=o.Shape;b=s.BoundBox
 return {'valid':bool(s and not s.isNull() and s.isValid()),'solids':len(s.Solids),'volume':s.Volume,'area':s.Area,'bbox':[b.XMin,b.XMax,b.YMin,b.YMax,b.ZMin,b.ZMax]}
try:
 a=App.openDocument(C['assembly']);a.recompute();link=a.getObject(C['link'])
 if link is None: raise RuntimeError('assembly link not found: '+C['link'])
 body=link.LinkedObject;tip=body.Tip
 if body.Name!=C['body']: raise RuntimeError('assembly link targets unexpected Body: '+body.Name)
 r.update({'documents':{d.Name:d.FileName for d in App.listDocuments().values()},
           'link':info(link),'body':info(body),'tip':tip.Name,'body_state':list(body.State),'tip_state':list(tip.State)})
 m=App.getDocument('pendant_master');sheet=m.getObject(C['sheet']);cell=sheet.getCellFromAlias(C['alias'])
 r['master_value']=str(sheet.get(cell));exprs=[]
 for d in App.listDocuments().values():
  if d==body.Document:
   for o in d.Objects:
    for prop,expr in getattr(o,'ExpressionEngine',[]):
     if C['alias'] in expr: exprs.append({'object':o.Name,'property':prop,'expression':expr,'status':o.getStatusString()})
 r['expressions']=exprs
 r['link_matches_body']=bool(r['link']['valid'] and r['body']['valid'] and r['link']['solids']==r['body']['solids'] and abs(r['link']['volume']-r['body']['volume'])<1e-6 and all(abs(x-y)<1e-6 for x,y in zip(r['link']['bbox'],r['body']['bbox'])))
 if C.get('export_brep'): body.Shape.exportBrep(C['export_brep'])
 if not r['link']['valid'] or not r['body']['valid'] or r['body']['solids']!=1 or 'Invalid' in r['body_state'] or 'Invalid' in r['tip_state'] or not r['link_matches_body']:
  r['errors'].append('assembly link/source shape validation failed')
 if not exprs: r['errors'].append('no active expression consumes the requested master alias')
 if any(x['status']!='Valid' for x in exprs): r['errors'].append('a consuming object reports an invalid expression status')
except Exception as e:r.update({'errors':[repr(e)],'traceback':traceback.format_exc()})
print('ASSEMBLY_CHECK='+json.dumps(r,sort_keys=True))
for d in list(App.listDocuments().values()):App.closeDocument(d.Name)
'''


def run_refresh(script: Path, assembly: Path, command: Path, timeout: float) -> dict:
    proc = subprocess.run(
        ["python3", str(script), "--freecadcmd", str(command),
         "--assembly", str(assembly), "--timeout", str(timeout)],
        capture_output=True, text=True, timeout=timeout + 10, check=False,
    )
    output = proc.stdout + proc.stderr
    if proc.returncode:
        raise RuntimeError(f"Assembly refresh failed:\n{output[-4000:]}")
    record = extract_record(output, "MODULAR_ASSEMBLY_REFRESH")
    if record.get("errors"):
        raise RuntimeError(f"Assembly refresh reported errors: {record['errors']}")
    return record


def near(a: float, b: float, tolerance: float) -> bool:
    return abs(a - b) <= tolerance


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--component", required=True, help="component filename in pendant-bodies")
    ap.add_argument("--body", required=True, help="PartDesign Body name in the component")
    ap.add_argument("--link", required=True, help="App::Link name in pendant-modular-assembly.FCStd")
    ap.add_argument("--sheet", required=True, help="master spreadsheet object name")
    ap.add_argument("--alias", required=True, help="master alias to perturb")
    ap.add_argument("--test-value", required=True, help="temporary value, including units if needed")
    ap.add_argument("--freecadcmd", type=Path, default=DEFAULT_FREECADCMD)
    ap.add_argument("--timeout", type=float, default=170)
    ap.add_argument("--json", type=Path, help="write the test result to this path")
    ap.add_argument("--keep-workdir", action="store_true", help="retain disposable project and logs")
    args = ap.parse_args()

    refresh_module = read_refresh_module()
    if args.component not in refresh_module.COMPONENTS:
        ap.error(f"{args.component!r} is not in the modular refresh component list")
    source_files = [FREECAD_DIR / "pendant-master.FCStd",
                    FREECAD_DIR / "pendant-modular-assembly.FCStd"]
    source_files += [FREECAD_DIR / "pendant-bodies" / name for name in refresh_module.COMPONENTS]
    missing = [str(path) for path in source_files if not path.is_file()]
    if missing:
        ap.error("missing modular project source(s): " + ", ".join(missing))
    if not args.freecadcmd.is_file():
        ap.error(f"FreeCADCmd not found: {args.freecadcmd}")

    work = Path(tempfile.mkdtemp(prefix="pendant-master-propagation-"))
    (work / "pendant-bodies").mkdir()
    (work / "scripts").mkdir()
    (work / "backups").mkdir()
    shutil.copy2(FREECAD_DIR / "pendant-master.FCStd", work / "pendant-master.FCStd")
    shutil.copy2(FREECAD_DIR / "pendant-modular-assembly.FCStd", work / "pendant-modular-assembly.FCStd")
    for name in refresh_module.COMPONENTS:
        shutil.copy2(FREECAD_DIR / "pendant-bodies" / name, work / "pendant-bodies" / name)
    shutil.copy2(REFRESH_SCRIPT, work / "scripts" / "refresh_modular_assembly.py")

    master = work / "pendant-master.FCStd"
    assembly = work / "pendant-modular-assembly.FCStd"
    result = {
        "schema_version": 1,
        "component": args.component,
        "body": args.body,
        "assembly_link": args.link,
        "master_sheet": args.sheet,
        "master_alias": args.alias,
        "test_value": args.test_value,
        "source_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in source_files
        },
        "workdir_retained": False,
    }

    try:
        read_macro = work / "read_alias.FCMacro"
        write_macro = work / "set_alias.FCMacro"
        check_macro = work / "check_assembly.FCMacro"
        read_cfg = {"master": str(master), "sheet": args.sheet, "alias": args.alias}
        write_macro_cfg = dict(read_cfg)
        read_macro.write_text("CONFIG=" + repr(json.dumps(read_cfg)) + "\n" + ALIAS_READ_MACRO)
        write_macro.write_text("CONFIG=" + repr(json.dumps(write_macro_cfg)) + "\n" + ALIAS_SET_MACRO)

        original = extract_record(run_freecad(args.freecadcmd, read_macro, args.timeout), "PARAM_ALIAS")
        if original.get("errors"):
            raise RuntimeError(f"Could not read original master alias: {original['errors']}")
        result["original_value"] = original["value"]
        result["master_cell"] = original["cell"]

        def set_value(value: str) -> dict:
            write_macro.write_text(
                "CONFIG=" + repr(json.dumps({**read_cfg, "value": value})) + "\n" + ALIAS_SET_MACRO
            )
            row = extract_record(run_freecad(args.freecadcmd, write_macro, args.timeout), "PARAM_ALIAS_SET")
            if row.get("errors") or not row.get("value"):
                raise RuntimeError(f"Could not set master alias to {value!r}: {row}")
            return row

        def refresh_and_check(label: str, export_brep: Path | None = None) -> tuple[dict, dict]:
            refresh = run_refresh(work / "scripts" / "refresh_modular_assembly.py", assembly,
                                  args.freecadcmd, args.timeout)
            cfg = {"assembly": str(assembly), "link": args.link, "body": args.body, "sheet": args.sheet,
                   "alias": args.alias,
                   "export_brep": str(export_brep) if export_brep else None}
            check_macro.write_text("CONFIG=" + repr(json.dumps(cfg)) + "\n" + ASSEMBLY_CHECK_MACRO)
            fresh = extract_record(run_freecad(args.freecadcmd, check_macro, args.timeout), "ASSEMBLY_CHECK")
            if fresh.get("errors"):
                raise RuntimeError(f"Fresh assembly validation failed ({label}): {fresh['errors']}")
            return refresh, fresh

        baseline_brep = work / "baseline.brep"
        baseline_refresh, baseline = refresh_and_check("baseline", baseline_brep)
        if baseline["master_value"] != result["original_value"]:
            raise RuntimeError("Baseline fresh process did not read the original master value")
        result["baseline"] = baseline
        result["baseline_refresh_errors"] = baseline_refresh.get("errors", [])

        changed_alias = set_value(args.test_value)
        resolved_test_value = changed_alias["value"]
        result["resolved_test_value"] = resolved_test_value
        changed_refresh, changed = refresh_and_check("changed")
        if changed["master_value"] != resolved_test_value:
            raise RuntimeError("Changed fresh process did not read the temporary master value")
        before, after = baseline["body"], changed["body"]
        metrics_changed = (
            not near(before["volume"], after["volume"], 1e-7)
            or not near(before["area"], after["area"], 1e-7)
            or any(not near(x, y, 1e-7) for x, y in zip(before["bbox"], after["bbox"]))
        )
        if not metrics_changed:
            raise RuntimeError("The requested alias change did not alter target Body geometry metrics")
        result["changed"] = changed
        result["changed_refresh_errors"] = changed_refresh.get("errors", [])

        set_value(result["original_value"])
        restored_refresh, restored = refresh_and_check("restored")
        if restored["master_value"] != result["original_value"]:
            raise RuntimeError("Restored fresh process did not read the original master value")
        result["restored"] = restored
        result["restored_refresh_errors"] = restored_refresh.get("errors", [])

        if not near(before["volume"], restored["body"]["volume"], 1e-7) or any(
            not near(x, y, 1e-7) for x, y in zip(before["bbox"], restored["body"]["bbox"])
        ):
            raise RuntimeError("Restored Body volume/bounds do not match the fresh baseline")
        compare = work / "compare_restored.FCMacro"
        compare_cfg = {"baseline": str(baseline_brep), "assembly": str(assembly), "link": args.link}
        compare.write_text("CONFIG=" + repr(json.dumps(compare_cfg)) + "\n" + r'''import FreeCAD as App,Part,json,traceback
C=json.loads(CONFIG);r={'errors':[]}
try:
 a=App.openDocument(C['assembly']);link=a.getObject(C['link']);base=Part.Shape();base.read(C['baseline']);shape=link.Shape
 x=base.cut(shape);y=shape.cut(base);r.update({'baseline_valid':base.isValid(),'link_valid':shape.isValid(),'forward_valid':x.isValid(),'reverse_valid':y.isValid(),'forward_mm3':x.Volume,'reverse_mm3':y.Volume,'sum_mm3':x.Volume+y.Volume})
 if not r['baseline_valid'] or not r['link_valid'] or not x.isValid() or not y.isValid() or x.Volume>1e-7 or y.Volume>1e-7:r['errors'].append('restored BREP differs from baseline or Boolean comparison is invalid')
except Exception as e:r.update({'errors':[repr(e)],'traceback':traceback.format_exc()})
print('BREP_COMPARE='+json.dumps(r,sort_keys=True))
for d in list(App.listDocuments().values()):App.closeDocument(d.Name)
''')
        comparison = extract_record(run_freecad(args.freecadcmd, compare, args.timeout), "BREP_COMPARE")
        if comparison.get("errors"):
            raise RuntimeError(f"Restored BREP comparison failed: {comparison['errors']}")
        result["restored_brep_comparison"] = comparison
        result["result"] = "PASS"
    except Exception as exc:
        result["result"] = "FAIL"
        result["error"] = repr(exc)
        result["workdir"] = str(work)
        result["workdir_retained"] = True
        args.keep_workdir = True
    finally:
        if args.keep_workdir:
            result["workdir"] = str(work)
            result["workdir_retained"] = True
        else:
            shutil.rmtree(work, ignore_errors=True)

    output = json.dumps(result, indent=2) + "\n"
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(output)
    print("MASTER_PROPAGATION_TEST=" + json.dumps(result, sort_keys=True))
    return 0 if result.get("result") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
