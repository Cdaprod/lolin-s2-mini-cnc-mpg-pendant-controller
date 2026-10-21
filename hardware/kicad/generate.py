#!/usr/bin/env python3
"""Reproducible KiCad project packaging and lightweight inventory checks.

The checked-in .kicad_sch is the canonical editable source. This helper
validates it and builds an export directory without changing the source.
For symbol/net edits, use KiCad, then commit the edited .kicad_sch.
"""
from pathlib import Path
import argparse
import csv
import json
import shutil

ROOT = Path(__file__).resolve().parent
STEM = "CNC_MPG_Pendant_Master"
SYMBOL_REFS = ("U1", "U2", "DS1", "ENC1", "PCB1", "J1", "J2", "J3", "SW8")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    sch = ROOT / (STEM + ".kicad_sch")
    csv_path = ROOT / "component_inventory.csv"
    content = sch.read_text(encoding="utf-8")
    if not content.startswith("(kicad_sch "):
        raise SystemExit("Not a KiCad schematic")
    if "LOGICAL HARNESS SCHEMATIC" not in content:
        raise SystemExit("Refusing to package schematic missing logical-only warning")
    with csv_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit("Component inventory is empty")
    missing = [ref for ref in SYMBOL_REFS
               if ('(property "Reference" "' + ref + '"') not in content]
    if missing:
        raise SystemExit("Missing schematic references: " + ", ".join(missing))
    dest = args.out.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(sch, dest / sch.name)
    shutil.copy2(csv_path, dest / csv_path.name)
    (dest / (STEM + ".kicad_pro")).write_text("{}\n", encoding="utf-8")
    (dest / "build_manifest.json").write_text(
        json.dumps({"source": str(sch.relative_to(ROOT)),
                    "inventory_rows": len(rows),
                    "symbol_references": SYMBOL_REFS,
                    "status": "logical_harness_not_manufacturing_ready"}, indent=2) + "\n",
        encoding="utf-8")
    print("Validated and packaged:", dest)

if __name__ == "__main__":
    main()
