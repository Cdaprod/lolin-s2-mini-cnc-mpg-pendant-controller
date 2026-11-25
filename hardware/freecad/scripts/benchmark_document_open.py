#!/usr/bin/env python3
"""Measure saved-document open latency without recomputing or saving CAD files.

Each measurement uses a fresh bounded FreeCADCmd process. The modular
assembly is opened through its relative App::Link sources; the monolith is
opened directly. Runs are interleaved to reduce ordering and filesystem-cache
bias. The result measures document loading only, not recomputation, viewport
rendering, or interactive editing.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import statistics
import subprocess
import tempfile
import time

SCRIPT = Path(__file__).resolve()
FREECAD_DIR = SCRIPT.parents[1]
DEFAULT_CMD = Path('/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd')
DOCUMENTS = {
    'modular_assembly': FREECAD_DIR / 'pendant-modular-assembly.FCStd',
    'monolith': FREECAD_DIR / 'pendant.FCStd',
}


def macro_source(path: Path) -> str:
    cfg = json.dumps({'path': str(path.resolve())})
    return r'''import FreeCAD as App, json, time
C=json.loads(@@CFG@@)
t=time.perf_counter(); target=App.openDocument(C['path']); elapsed=time.perf_counter()-t
opened=list(App.listDocuments().values())
r={'path':C['path'],'open_seconds':elapsed,'documents':[{'name':d.Name,'file':d.FileName,'objects':len(d.Objects)} for d in opened],
   'target_objects':len(target.Objects),'loaded_documents':len(opened),'total_loaded_objects':sum(len(d.Objects) for d in opened)}
print('DOCUMENT_OPEN_BENCH='+json.dumps(r,sort_keys=True))
for d in reversed(opened): App.closeDocument(d.Name)
'''.replace('@@CFG@@', repr(cfg))


def run_one(cmd: str, path: Path, timeout: int) -> dict:
    with tempfile.TemporaryDirectory(prefix='pendant-open-bench-') as td:
        macro = Path(td) / 'open_benchmark.FCMacro'
        macro.write_text(macro_source(path), encoding='utf-8')
        start = time.monotonic()
        proc = subprocess.Popen([cmd, str(macro)], cwd=FREECAD_DIR,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, start_new_session=True)
        try:
            output, _ = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait(timeout=5)
            output, _ = proc.communicate()
            raise RuntimeError(f'FreeCADCmd timed out opening {path.name}; owned worker terminated.\n{output[-2000:]}')
        wall = time.monotonic() - start
    if proc.returncode:
        raise RuntimeError(f'FreeCADCmd exited {proc.returncode} opening {path.name}.\n{output[-3000:]}')
    marker = next((line.split('DOCUMENT_OPEN_BENCH=', 1)[1]
                   for line in output.splitlines() if 'DOCUMENT_OPEN_BENCH=' in line), None)
    if marker is None:
        raise RuntimeError(f'FreeCADCmd returned no benchmark record for {path.name}.\n{output[-3000:]}')
    result = json.loads(marker)
    result.pop('path', None)
    result['document'] = path.resolve().relative_to(FREECAD_DIR.resolve()).as_posix()
    for doc in result.get('documents', []):
        file_path = Path(doc.pop('file')).resolve()
        try:
            doc['document'] = file_path.relative_to(FREECAD_DIR.resolve()).as_posix()
        except ValueError:
            doc['document'] = file_path.name
    result['process_wall_seconds'] = wall
    result['file_size_bytes'] = path.stat().st_size
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freecadcmd', default=os.environ.get('FREECADCMD'))
    parser.add_argument('--runs', type=int, default=3)
    parser.add_argument('--timeout', type=int, default=170)
    parser.add_argument('--json', type=Path, help='also save the benchmark record as JSON')
    args = parser.parse_args()
    if args.runs < 1 or args.runs > 10:
        parser.error('--runs must be between 1 and 10')
    if args.timeout < 1 or args.timeout > 180:
        parser.error('--timeout must be between 1 and 180 seconds')
    cmd = args.freecadcmd or (str(DEFAULT_CMD) if DEFAULT_CMD.is_file() else None)
    if not cmd:
        parser.error('freecadcmd not found; pass --freecadcmd or set FREECADCMD')
    missing = [str(p) for p in DOCUMENTS.values() if not p.is_file()]
    if missing:
        raise SystemExit('Missing CAD document(s): ' + ', '.join(missing))
    gui = subprocess.run(['pgrep', '-x', 'FreeCAD'], capture_output=True, text=True)
    if gui.returncode == 0 and gui.stdout.strip():
        raise SystemExit('FreeCAD GUI process detected; close it before benchmarking (PID(s): ' + gui.stdout.strip() + ')')

    results = {name: [] for name in DOCUMENTS}
    order = list(DOCUMENTS)
    for run in range(args.runs):
        sequence = order if run % 2 == 0 else list(reversed(order))
        for name in sequence:
            results[name].append(run_one(cmd, DOCUMENTS[name], args.timeout))
    bundle_files = [DOCUMENTS['modular_assembly'], FREECAD_DIR / 'pendant-master.FCStd'] + [
        FREECAD_DIR / 'pendant-bodies' / name for name in
        ('display-retainer.FCStd', 'usb-tethered-cover.FCStd', 'faceplate-locators.FCStd',
         'breakout-board.FCStd')]
    summary = {
        'runs_per_document': args.runs,
        'modular_source_bundle_bytes': sum(p.stat().st_size for p in bundle_files),
        'measurement': 'App.openDocument only; no explicit recompute or save',
        'warm_cache_control': 'fresh FreeCADCmd process per run; document order alternated; OS cache not flushed',
        'documents': {
            name: {
                'median_open_seconds': statistics.median(x['open_seconds'] for x in values),
                'file_size_bytes': DOCUMENTS[name].stat().st_size,
                'runs': values,
            } for name, values in results.items()
        },
    }
    mono = summary['documents']['monolith']['median_open_seconds']
    assembly = summary['documents']['modular_assembly']['median_open_seconds']
    summary['monolith_to_assembly_open_time_ratio'] = mono / assembly if assembly else None
    rendered = json.dumps(summary, indent=2, sort_keys=True) + '\n'
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(rendered, encoding='utf-8')
    print(rendered, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
