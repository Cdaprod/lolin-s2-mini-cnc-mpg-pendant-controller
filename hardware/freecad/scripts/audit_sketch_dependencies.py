#!/usr/bin/env python3
"""Audit a FreeCAD FCStd's Tip-rooted object and Sketcher external geometry dependencies.

The FCStd Document.xml archive records ExternalGeometryExtension Ref tokens and
constraint geometry indices that are not consistently exposed through ordinary
OutList/ObjectDeps relationships. This script reads that saved native data and
emits a reproducible JSON manifest without opening or modifying the CAD file.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile
import xml.etree.ElementTree as ET

CONTAINERS = {"PartDesign::Body", "App::Part"}


def value_for(obj: ET.Element, prop: str) -> str | None:
    p = obj.find(f"./Properties/Property[@name='{prop}']")
    if p is None:
        return None
    link = p.find(".//Link")
    return link.get("value") if link is not None else None


def expressions(obj: ET.Element) -> list[dict[str, str]]:
    p = obj.find("./Properties/Property[@name='ExpressionEngine']")
    if p is None:
        return []
    return [{"path": e.get("path", ""), "expression": e.get("expression", "")}
            for e in p.findall(".//Expression")]


def link_properties(obj: ET.Element) -> dict[str, str]:
    """Preserve serialized link/support properties, including XLink targets."""
    out = {}
    for p in obj.findall("./Properties/Property"):
        if "Link" in p.get("type", ""):
            out[p.get("name", "")] = ET.tostring(p, encoding="unicode")
    return out


def sketch_external_refs(obj: ET.Element) -> list[dict]:
    p = obj.find("./Properties/Property[@name='ExternalGeo']")
    constraints_prop = obj.find("./Properties/Property[@name='Constraints']")
    constraints = constraints_prop.findall(".//Constrain") if constraints_prop is not None else []
    refs = []
    if p is None:
        return refs
    external_rows = []
    for geom in p.findall(".//GeometryList/Geometry"):
        ext = geom.find("./GeoExtensions/GeoExtension[@type='Sketcher::ExternalGeometryExtension']")
        if ext is not None and ext.get("Ref", ""):
            external_rows.append((geom.get("id", ""), ext.get("Ref", ""), ext.get("Flags", "")))
    for index, (geometry_id, ref, flags) in enumerate(external_rows):
        # Sketcher addresses external geometry using -3, -4, ... in constraints.
        sketch_index = -(index + 3)
        referenced_constraints = []
        for cindex, c in enumerate(constraints):
            indices = {int(c.get(k, "-2000")) for k in ("First", "Second", "Third")}
            if sketch_index in indices:
                referenced_constraints.append({"index": cindex, "type": c.get("Type"),
                                               "name": c.get("Name", "")})
        target = ref.split(".", 1)[0] if "." in ref else ref
        subtoken = ref[len(target) + 1:] if target and ref.startswith(target + ".") else ""
        refs.append({"external_geometry_order": index, "serialized_geometry_id": geometry_id,
                     "sketcher_constraint_geometry_index": sketch_index,
                     "reference": ref, "source_object": target,
                     "source_subelement_token": subtoken, "flags": flags,
                     "constraints": referenced_constraints,
                     "constraint_driving": bool(referenced_constraints)})
    return refs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("fcstd", type=Path, help="FreeCAD document to inspect")
    ap.add_argument("--body", default="Body002", help="PartDesign Body root (default: Body002)")
    ap.add_argument("--json", type=Path, help="output JSON path (default: stdout)")
    args = ap.parse_args()
    source = args.fcstd.resolve()
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    with zipfile.ZipFile(source) as archive:
        xml = ET.fromstring(archive.read("Document.xml"))
    object_headers = {o.get("name"): o.get("type", "") for o in xml.findall("./Objects/Object")}
    objects = {o.get("name"): o for o in xml.findall("./ObjectData/Object")}
    deps = {}
    for row in xml.iter("ObjectDeps"):
        deps[row.get("Name")] = [d.get("Name") for d in row.findall("Dep")]
    root_body = objects.get(args.body)
    if root_body is None:
        ap.error(f"Body {args.body!r} not found in {source.name}")
    tip = value_for(root_body, "Tip")
    if not tip:
        ap.error(f"Body {args.body!r} has no saved Tip link")

    # Compute ordinary object-dependency reachability independently from
    # Sketcher external-geometry reachability so the two closure counts remain
    # comparable and the omitted Sketcher boundary is visible.
    ordinary_visited: set[str] = set()
    ordinary_queue = [tip]
    while ordinary_queue:
        name = ordinary_queue.pop()
        if not name or name in ordinary_visited or name not in objects:
            continue
        ordinary_visited.add(name)
        if object_headers.get(name, "") in CONTAINERS:
            continue
        ordinary_targets = set(deps.get(name, []))
        ordinary_targets.discard(args.body)
        ordinary_targets = {t for t in ordinary_targets
                            if object_headers.get(t, "") not in CONTAINERS}
        for e in expressions(objects[name]):
            ordinary_targets.update(n for n in object_headers
                                    if re.search(rf"(?<![A-Za-z0-9_]){re.escape(n)}\.", e["expression"]))
        ordinary_queue.extend(ordinary_targets)

    # Ordinary object dependencies, then Sketcher external-reference edges.
    graph: dict[str, set[str]] = {}
    queue = [tip]
    visited: set[str] = set()
    while queue:
        name = queue.pop()
        if not name or name in visited or name not in objects:
            continue
        visited.add(name)
        typ = object_headers.get(name, "")
        if typ in CONTAINERS:
            continue
        targets = set(deps.get(name, []))
        targets.discard(args.body)
        targets = {t for t in targets if object_headers.get(t, "") not in CONTAINERS}
        o = objects[name]
        refs = sketch_external_refs(o) if typ.startswith("Sketcher::") else []
        targets.update(r["source_object"] for r in refs if r["source_object"] in objects)
        # Expression references are ordinary document object names; keep these
        # explicit even if ObjectDeps omits them in a future serialization.
        for e in expressions(o):
            targets.update(n for n in object_headers if re.search(rf"(?<![A-Za-z0-9_]){re.escape(n)}\.", e["expression"]))
        graph[name] = targets
        queue.extend(targets)

    # Owner and suppression metadata.
    owners: dict[str, list[str]] = {}
    for owner_name, owner in objects.items():
        if object_headers.get(owner_name, "") not in CONTAINERS:
            continue
        group = owner.find("./Properties/Property[@name='Group']")
        if group is not None:
            for link in group.findall(".//Link"):
                owners.setdefault(link.get("value", ""), []).append(owner_name)
    def suppressed(name: str) -> bool:
        p = objects[name].find("./Properties/Property[@name='Suppressed']")
        if p is None:
            return False
        b = p.find(".//Bool")
        return bool(b is not None and b.get("value", "false").lower() == "true")

    # Shortest Tip-to-object path gives a traceable downstream chain.
    paths = {tip: [tip]}
    q = [tip]
    while q:
        n = q.pop(0)
        for target in graph.get(n, set()):
            if target not in paths:
                paths[target] = paths[n] + [target]
                q.append(target)

    body_group = root_body.find("./Properties/Property[@name='Group']")
    body_sketches = ({link.get("value", "") for link in body_group.findall(".//Link")}
                     if body_group is not None else set())
    body_sketches = {n for n in body_sketches if object_headers.get(n, "").startswith("Sketcher::")}
    # Include inactive rear-body sketches with external references as explicit
    # history records, without expanding them into the active Tip closure.
    relevant_sketch_names = {n for n in visited if object_headers.get(n, "").startswith("Sketcher::")}
    relevant_sketch_names.update(body_sketches)
    sketch_records = []
    for name in sorted(relevant_sketch_names):
        typ = object_headers.get(name, "")
        o = objects[name]
        exts = sketch_external_refs(o)
        if name not in paths and not exts:
            continue
        constraint_prop = o.find("./Properties/Property[@name='Constraints']")
        sketch_records.append({
            "name": name, "type": typ, "owners": owners.get(name, []),
            "active_tip_reachable": name in paths,
            "body_history_status": "active_tip_dependency" if name in paths else "inactive_body_history",
            "suppressed": suppressed(name),
            "placement": (lambda p: p.attrib if p is not None else None)(o.find("./Properties/Property[@name='Placement']/PropertyPlacement")),
            "constraint_count": len(constraint_prop.findall(".//Constrain")) if constraint_prop is not None else 0,
            "expressions": expressions(o), "external_geometry": exts,
            "external_geometry_count": len(exts),
            "tip_to_sketch_path": paths.get(name, []),
        })

    external_edges = []
    for row in sketch_records:
        for ref in row["external_geometry"]:
            source_name = ref["source_object"]
            external_edges.append({
                "consumer_sketch": row["name"], **ref,
                "source_type": object_headers.get(source_name, "unknown"),
                "source_owners": owners.get(source_name, []),
                "source_suppressed": suppressed(source_name) if source_name in objects else None,
                "consumer_active_tip_reachable": row["active_tip_reachable"],
                "reached_from_active_tip": bool(row["active_tip_reachable"] and source_name in paths),
                "tip_to_consumer_path": row["tip_to_sketch_path"],
                "consumer_to_source_path": [row["name"], source_name],
            })

    referenced_binders = {r["source_object"] for r in external_edges
                          if "Binder" in object_headers.get(r["source_object"], "")}
    binder_records = []
    for name in sorted(visited | referenced_binders):
        typ = object_headers.get(name, "")
        if "Binder" not in typ:
            continue
        o = objects[name]
        props = {}
        for propname in ("Support", "TraceSupport", "Context", "Placement", "AttachmentSupport"):
            p = o.find(f"./Properties/Property[@name='{propname}']")
            if p is not None:
                props[propname] = ET.tostring(p, encoding="unicode")
        binder_records.append({"name": name, "type": typ, "owners": owners.get(name, []), "properties_xml": props})

    manifest = {
        "schema_version": 1,
        "source": {"filename": source.name, "sha256": digest,
                   "document_internal_name": "remove_warp_bypass",
                   "freecad_version_observed": "1.1.1 (0108fd4b4850cc46e625b60e53cea7a7bbe69f8d)"},
        "root": {"body": args.body, "tip": tip},
        "method": {
            "ordinary_edges": "Saved Document.xml ObjectDeps, excluding PartDesign::Body/App::Part ownership containers",
            "sketch_edges": "Sketcher::ExternalGeometryExtension Ref values in each Sketcher ExternalGeo GeometryList, expanded recursively",
            "constraints": "External geometry order i maps to Sketcher geometry index -(i+3); constraint First/Second/Third fields are checked",
            "note": "This is a saved-document audit. Validate with the target FreeCAD build before geometry-changing repairs."
        },
        "object_dependency_closure_count": len(ordinary_visited),
        "expanded_dependency_closure_count": len(visited),
        "ordinary_dependency_objects": sorted(ordinary_visited),
        "expanded_dependency_objects": [{"name": n, "type": object_headers.get(n, "unknown"),
                                          "owners": owners.get(n, []), "suppressed": suppressed(n),
                                          "dependencies": sorted(graph.get(n, set())),
                                          "link_properties_xml": link_properties(objects[n]),
                                          "expressions": expressions(objects[n]),
                                          "tip_path": paths.get(n, [])}
                                         for n in sorted(visited)],
        "sketches": sketch_records,
        "external_geometry_references": external_edges,
        "binders": binder_records,
        "app_links": [{"name": n, "type": object_headers.get(n, ""),
                       "owners": owners.get(n, []),
                       "link_properties_xml": link_properties(objects[n]),
                       "tip_path": paths.get(n, [])}
                      for n in sorted(visited) if "App::Link" in object_headers.get(n, "")],
        "limitations": [
            "FreeCAD 1.1.1 exposes ExternalGeometry (PropertyLinkSubList) and ExternalGeo (PropertyGeometryList), but the former can be empty while ExternalGeometryExtension Ref tokens are present in ExternalGeo serialization.",
            "This manifest reports exact serialized subelement tokens. Human-readable Edge/Face names may not exist for persistent element-map references.",
            "App::Link and ShapeBinder/XLink property payloads are preserved in link_properties_xml; resolve their targets in FreeCAD before treating external paths as portable."
        ]
    }
    text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
