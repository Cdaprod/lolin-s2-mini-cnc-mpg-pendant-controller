#!/usr/bin/env python3
"""Summarize active encoder Tip boundary edges into a focused interface-cut map.

Consumes the serialized Tip-root manifests emitted by audit_sketch_dependencies.py.
This is graph analysis only: it does not inspect or alter CAD geometry.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

DEFAULTS = {
    "faceplate": "hardware/freecad/reports/encoder-faceplate-tip-boundary-manifest.json",
    "pocket": "hardware/freecad/reports/encoder-pocket-tip-boundary-manifest.json",
}


def classify(edge: dict) -> str:
    names = " ".join((edge.get("source_object", ""), edge.get("target_object", ""),
                      *edge.get("source_owners", []), *edge.get("target_owners", []))).lower()
    if any(s in names for s in ("pendantdimensions", "internalhardware", "hangerparameters", "dualsided", "exteriorenvelope")):
        return "shared-parameter-or-datum"
    if any(s in names for s in ("encoder", "rc16", "faceplate")):
        return "encoder-interface-or-encoder-feature"
    if any(s in names for s in ("smallhanger", "front", "body003", "exteriorenvelope", "usbseat", "rear")):
        return "shell-or-upper-assembly-construction"
    return "other-active-boundary"


def summarize(path: Path, role: str) -> dict:
    data = json.loads(path.read_text())
    edges = data["component_boundary_crossings"]
    normalized = []
    seen = set()
    for row in edges:
        key = (row.get("source_object", ""), row.get("property", ""),
               row.get("target_object", ""), row.get("subelement", ""),
               tuple(row.get("tip_to_source_path", [])))
        if key in seen:
            continue
        seen.add(key)
        normalized.append({
            "source_object": key[0], "property": key[1],
            "source_owners": row.get("source_owners", []),
            "target_object": key[2], "target_owners": row.get("target_owners", []),
            "subelement": key[3], "tip_to_source_path": list(key[4]),
            "category": classify(row),
        })
    return {
        "body": data["root"]["body"], "tip": data["root"]["tip"],
        "expanded_dependency_closure_count": data["expanded_dependency_closure_count"],
        "boundary_crossing_count": len(normalized),
        "sketch_external_reference_count": len(data.get("external_geometry_references", [])),
        "readiness": data.get("extraction_readiness", {}).get("status", "unknown"),
        "source": data.get("source", {}),
        "manifest": str(path),
        "manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "edges": normalized,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--faceplate", type=Path, default=Path(DEFAULTS["faceplate"]))
    ap.add_argument("--pocket", type=Path, default=Path(DEFAULTS["pocket"]))
    ap.add_argument("--json", type=Path, required=True)
    args = ap.parse_args()
    roots = [summarize(args.faceplate, "faceplate"), summarize(args.pocket, "pocket")]
    payload = {
        "schema_version": 1,
        "method": "Deduplicated active Tip-root component-boundary edges from existing serialized audit manifests; categories are name-based triage only, not geometric conclusions.",
        "roots": roots,
        "shared_edges": sorted(set((e["source_object"], e["property"], e["target_object"], e["subelement"])
                                    for e in roots[0]["edges"]) &
                                set((e["source_object"], e["property"], e["target_object"], e["subelement"])
                                    for e in roots[1]["edges"])),
    }
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps({"json": str(args.json), "roots": [{k: r[k] for k in
          ("body", "tip", "expanded_dependency_closure_count", "boundary_crossing_count",
           "sketch_external_reference_count", "readiness")} for r in roots],
          "shared_edge_count": len(payload["shared_edges"])}))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
