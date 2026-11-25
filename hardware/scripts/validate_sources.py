#!/usr/bin/env python3
"""Check the approved CAD inventory and saved dependency layout, not geometry."""
from pathlib import Path
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
CAD = 'hardware/freecad/'
APPROVED = {
    CAD + name for name in (
        'pendant.FCStd', 'pendant-master.FCStd',
        'pendant-modular-assembly.FCStd',
        'encoder-faceplate-pocket-unsplit-user-split.FCStd',
        'pendant-bodies/breakout-board.FCStd',
        'pendant-bodies/display-retainer.FCStd',
        'pendant-bodies/faceplate-locators.FCStd',
        'pendant-bodies/usb-tethered-cover.FCStd',
    )
}
# Existing accepted baseline, deliberately retained without another binary copy.
LARGE_BINARY_EXCEPTIONS = {CAD + 'pendant.FCStd'}
BINARY = {'.fcstd', '.step', '.stp', '.stl', '.3mf', '.png', '.pdf', '.jpg', '.zip'}

def main():
    tracked = subprocess.check_output(
        ['git', 'ls-files', '-z'], cwd=ROOT
    ).decode().split('\0')
    tracked = [p for p in tracked if p]
    errors, warnings = [], []
    actual = {p for p in tracked if p.lower().endswith('.fcstd')}
    if actual != APPROVED:
        errors.append({'unexpected_CAD': sorted(actual - APPROVED),
                       'missing_CAD': sorted(APPROVED - actual)})
    required = APPROVED | {
        'hardware/kicad/CNC_MPG_Pendant_Master.kicad_sch',
        'hardware/kicad/CNC_MPG_Pendant_Master.kicad_pro',
    }
    for rel in sorted(required):
        path = ROOT / rel
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f'missing or empty source: {rel}')
            continue
        if path.suffix.lower() == '.fcstd':
            try:
                with ZipFile(path) as archive:
                    bad = archive.testzip()
                    if bad:
                        errors.append(f'corrupt ZIP member: {rel}: {bad}')
                    xml = ET.fromstring(archive.read('Document.xml'))
                    for link in xml.iter():
                        target = link.get('file', '')
                        if target.lower().endswith('.fcstd'):
                            resolved = (path.parent / target).resolve()
                            if not resolved.is_relative_to(ROOT) or not resolved.is_file():
                                errors.append(f'unresolved/external dependency: {rel}: {target}')
            except Exception as exc:
                errors.append(f'unreadable CAD archive: {rel}: {exc}')
    for rel in tracked:
        path = ROOT / rel
        low = rel.lower()
        if low.endswith(('.fcbak', '.fcstd1', '.fcstd2', '.fcstd3', '.fcstd~', '.fcstd.autosave', '.step', '.stp', '.stl')) or '/.history/' in low or rel.startswith(('.workbench/', 'build/')):
            errors.append(f'tracked transient or generated artifact: {rel}')
        if path.is_file() and path.suffix.lower() in BINARY:
            size = path.stat().st_size
            if size > 25 * 1024**2 and rel not in LARGE_BINARY_EXCEPTIONS:
                errors.append(f'binary exceeds 25 MiB: {rel}')
            elif size > 5 * 1024**2:
                warnings.append(f'{rel}: {size / 1024**2:.2f} MiB; review storage justification')
    schematic = ROOT / 'hardware/kicad/CNC_MPG_Pendant_Master.kicad_sch'
    if schematic.exists() and not schematic.read_text().lstrip().startswith('(kicad_sch'):
        errors.append('invalid schematic header')
    print(json.dumps({'status': 'FAIL' if errors else 'PASS_SOURCE_LAYOUT',
        'scope': 'tracked inventory, archive integrity and saved file dependencies only; not FreeCAD recompute, shape validity, KiCad ERC, or physical fit',
        'errors': errors, 'warnings': warnings}, indent=2))
    return bool(errors)

if __name__ == '__main__':
    sys.exit(main())
