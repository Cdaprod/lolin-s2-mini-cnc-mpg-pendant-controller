#!/usr/bin/env python3
"""Summarize Tip-rooted cross-manufacturing-Body dependencies in a FCStd.

This read-only wrapper runs ``audit_sketch_dependencies.py`` for the selected
PartDesign Bodies, then extracts directed links between the named physical
Bodies from ordinary property dependencies and Sketcher external geometry.
The underlying per-Body manifests remain the authoritative detailed record.

No FreeCAD process is started and no document is modified. The reported
closure/readiness counts are diagnostic only: the extractor's conservative
allowlist can count master sheets, helper Bodies, and retained history as
blockers even when they are intended to move together into a component file.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile


SCRIPT = Path(__file__).resolve()
AUDITOR = SCRIPT.with_name("audit_sketch_dependencies.py")
DEFAULT_BODIES = (
    "Body", "Body002", "Body003", "Body_EncoderFacePlate",
    "Body_EncoderPocket",
)
PARAMETER_OBJECTS = {
    "PendantDimensions", "InternalHardware", "ExteriorEnvelope",
    "HangerParameters", "DualSided_OpposedWedge_Seam",
}


def _owners(value: object) -> list[str]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _run_audit(source: Path, body: str, python: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="pendant-body-boundary-") as temp:
        output = Path(temp) / f"{body}.json"
        proc = subprocess.run(
            [python, str(AUDITOR), str(source), "--body", body,
             "--json", str(output)],
            capture_output=True, text=True, check=False,
        )
        if proc.returncode:
            raise RuntimeError(
                f"Tip audit failed for {body}:\n{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}"
            )
        return json.loads(output.read_text(encoding="utf-8"))


def _physical_crossings(manifest: dict, physical_bodies: set[str]) -> list[dict]:
    root = manifest["root"]["body"]
    objects = {x["name"]: x for x in manifest["expanded_dependency_objects"]}
    sketches = {x["name"]: x for x in manifest["sketches"]}

    def suppressed_on_path(path: list[str]) -> list[str]:
        return [name for name in path if objects.get(name, {}).get("suppressed", False)]

    def boundary_pairs(source_owners: set[str], target_owners: set[str]) -> tuple[list[list[str]], str]:
        """Return definite crossings, or an explicitly contextual inference.

        Helper features often have no PartDesign Body owner. If just one side
        has a physical owner, the active Tip root provides context for the
        helper side; mark that pair as inferred so it is not mistaken for a
        direct owner-to-owner reference.
        """
        source_physical = source_owners & physical_bodies
        target_physical = target_owners & physical_bodies
        direct = sorted([source, target] for source in source_physical
                        for target in target_physical if source != target)
        if direct:
            return direct, "direct_physical_owner_crossing"
        # A link entirely owned by one foreign Body is internal to that Body.
        if source_physical and target_physical:
            return [], "same_physical_owner_or_no_crossing"
        known = source_physical | target_physical
        contextual = sorted([root, owner] for owner in known if owner != root)
        return contextual, "root_tip_context_for_helper_or_unowned_endpoint"

    found: list[dict] = []

    for edge in manifest["component_boundary_crossings"]:
        source_owners = set(_owners(edge.get("source_owners")))
        target_owners = set(_owners(edge.get("target_owners")))
        pairs, pair_basis = boundary_pairs(source_owners, target_owners)
        if not pairs or edge.get("source_object") in PARAMETER_OBJECTS or edge.get("target_object") in PARAMETER_OBJECTS:
            continue
        source = edge.get("source_object", "")
        target = edge.get("target_object", "")
        source_obj = objects.get(source, {})
        target_obj = objects.get(target, {})
        found.append({
            "kind": "object_property_or_dependency",
            "root_body": root,
            "manufacturing_body_boundary_pairs": pairs,
            "boundary_pair_basis": pair_basis,
            "source_object": source,
            "source_owners": sorted(source_owners),
            "property": edge.get("property", ""),
            "target_object": target,
            "target_owners": sorted(target_owners),
            "subelement": edge.get("subelement", ""),
            "edge_kind": edge.get("edge_kind", ""),
            "source_suppressed": bool(source_obj.get("suppressed", False)),
            "target_suppressed": bool(target_obj.get("suppressed", False)),
            "tip_to_source_path": edge.get("tip_to_source_path", []),
            "suppressed_objects_on_tip_path": suppressed_on_path(edge.get("tip_to_source_path", [])),
        })

    for edge in manifest["external_geometry_references"]:
        if not edge.get("consumer_active_tip_reachable"):
            continue
        consumer = edge.get("consumer_sketch", "")
        sketch = sketches.get(consumer, {})
        source_owners = set(_owners(edge.get("source_owners")))
        target_owners = set(_owners(sketch.get("owners")))
        pairs, pair_basis = boundary_pairs(source_owners, target_owners)
        if not pairs or edge.get("source_object") in PARAMETER_OBJECTS:
            continue
        found.append({
            "kind": "sketcher_external_geometry",
            "root_body": root,
            "manufacturing_body_boundary_pairs": pairs,
            "boundary_pair_basis": pair_basis,
            "source_object": edge.get("source_object", ""),
            "source_owners": sorted(source_owners),
            "property": "ExternalGeometry",
            "target_object": consumer,
            "target_owners": sorted(target_owners),
            "external_geometry_order": edge.get("external_geometry_order"),
            "sketcher_geometry_index": edge.get("sketcher_constraint_geometry_index"),
            "subelement": edge.get("source_subelement_token", ""),
            "constraints": edge.get("constraints", []),
            "source_suppressed": bool(edge.get("source_suppressed", False)),
            "target_suppressed": bool(sketch.get("suppressed", False)),
            "tip_to_source_path": edge.get("tip_to_consumer_path", []),
            "suppressed_objects_on_tip_path": suppressed_on_path(edge.get("tip_to_consumer_path", [])),
        })

    unique: dict[str, dict] = {}
    for row in found:
        key = json.dumps(row, sort_keys=True, separators=(",", ":"))
        unique[key] = row
    return sorted(unique.values(), key=lambda x: (
        x["source_owners"], x["target_owners"], x["source_object"],
        x.get("property", ""), x["target_object"],
        x.get("external_geometry_order") if isinstance(x.get("external_geometry_order"), int) else -1,
    ))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="monolithic or candidate FCStd")
    parser.add_argument("--body", action="append", dest="bodies",
                        help="physical Body root to audit; repeatable (default: known major Bodies)")
    parser.add_argument("--json", type=Path, help="write summary JSON (default: stdout)")
    parser.add_argument("--python", default=sys.executable,
                        help="Python interpreter used for the underlying auditor")
    args = parser.parse_args()
    source = args.source.expanduser().resolve()
    if not source.is_file():
        parser.error(f"source document not found: {source}")
    if not AUDITOR.is_file():
        parser.error(f"underlying auditor not found: {AUDITOR}")

    bodies = args.bodies or list(DEFAULT_BODIES)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    manifests = [_run_audit(source, body, args.python) for body in bodies]
    physical = set(bodies)
    records = []
    all_edges = []
    for manifest in manifests:
        edges = _physical_crossings(manifest, physical)
        all_edges.extend(edges)
        readiness = manifest["extraction_readiness"]
        records.append({
            "body": manifest["root"]["body"],
            "tip": manifest["root"]["tip"],
            "ordinary_dependency_count": manifest["object_dependency_closure_count"],
            "expanded_dependency_count": manifest["expanded_dependency_closure_count"],
            "conservative_readiness": readiness["status"],
            "conservative_blocker_count": len(readiness["blockers"]),
            "uncertainty_count": len(readiness["uncertainties"]),
            "active_sketcher_external_reference_count": sum(
                bool(x.get("consumer_active_tip_reachable"))
                for x in manifest["external_geometry_references"]
            ),
            "cross_manufacturing_body_edge_count": len(edges),
            "cross_manufacturing_body_edges": edges,
        })

    output = {
        "schema_version": 1,
        "source": {"filename": source.name, "sha256": digest},
        "physical_body_roots": bodies,
        "method": (
            "Runs the Tip-rooted object and Sketcher external-geometry auditor "
            "for each manufacturing Body, then reports either directed edges "
            "whose endpoints have distinct physical Body owners or contextual "
            "root-to-foreign-Body edges where a helper/unowned endpoint prevents "
            "direct owner assignment. The basis is recorded for every edge."
        ),
        "readiness_caveat": (
            "Conservative readiness is not an extraction verdict without a "
            "component-specific allowlist. It may count intended helper groups, "
            "master parameters, and suppressed/historical dependencies. Edge "
            "records include suppression flags and Tip paths for review."
        ),
        "bodies": records,
    }
    text = json.dumps(output, indent=2, sort_keys=True) + "\n"
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
