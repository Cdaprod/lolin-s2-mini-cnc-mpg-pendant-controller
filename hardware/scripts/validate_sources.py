#!/usr/bin/env python3
"""Validate tracked hardware source layout without claiming electrical signoff."""
from pathlib import Path
import json,sys
root=Path(__file__).resolve().parents[2]
required=["hardware/freecad/pendant.FCStd","hardware/freecad/pendant_assembly.step","hardware/kicad/CNC_MPG_Pendant_Master.kicad_sch","hardware/kicad/CNC_MPG_Pendant_Master.kicad_pro"]
errors=[f"missing: {p}" for p in required if not (root/p).is_file()]
for p in required:
    if (root/p).is_file() and (root/p).stat().st_size==0: errors.append(f"empty: {p}")
sch=root/required[2]
if sch.exists():
    s=sch.read_text(encoding="utf-8")
    if not s.lstrip().startswith("(kicad_sch"): errors.append("invalid schematic header")
    if "LOGICAL HARNESS SCHEMATIC" in s: print("WARNING: schematic is marked logical/provisional, not build verified")
    if "LM393" in s: print("REVIEW: legacy comparator text appears; inspect context before drawing conclusions")
report={"status":"PASS_SOURCE_LAYOUT" if not errors else "FAIL","scope":"source presence/structure only; not KiCad ERC or physical validation","errors":errors}
print(json.dumps(report,indent=2))
sys.exit(bool(errors))
