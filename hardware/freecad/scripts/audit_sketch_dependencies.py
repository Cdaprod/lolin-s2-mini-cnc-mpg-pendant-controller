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
import os
from pathlib import Path
import re
import zipfile
import xml.etree.ElementTree as ET

CONTAINERS = {"PartDesign::Body", "App::Part"}
CONTEXT_PROPERTIES = {"Context"}


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


def expression_targets(obj: ET.Element, known_objects: set[str]) -> list[dict[str, str]]:
    """Map document-object references in an object's expression engine."""
    targets = []
    for expr in expressions(obj):
        for name in sorted(known_objects):
            if re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}\.", expr["expression"]):
                targets.append({**expr, "target_object": name})
    return targets


def external_expression_refs(obj: ET.Element) -> list[dict[str, str]]:
    """Decode FreeCAD's Doc#<<Spreadsheet>>.Ident external expression syntax."""
    p = obj.find("./Properties/Property[@name='ExpressionEngine']")
    if p is None:
        return []
    doc_labels = {d.get("name", ""): d.get("label", "")
                  for d in p.findall(".//DocMap")}
    link_paths = {x.get("name", ""): x.get("file", "")
                  for x in p.findall(".//XLink")}
    pattern = re.compile(r"(?P<document>[A-Za-z_][A-Za-z0-9_]*)#<<(?P<object>[^>]+)>>\.(?P<alias>[A-Za-z_][A-Za-z0-9_]*)")
    refs = []
    for expr in expressions(obj):
        for match in pattern.finditer(expr["expression"]):
            doc_name = match.group("document")
            target = match.group("object")
            refs.append({"path": expr["path"], "expression": expr["expression"],
                         "document_internal_name": doc_name,
                         "document_label": doc_labels.get(doc_name, ""),
                         "target_object": target, "alias": match.group("alias"),
                         "external_file": link_paths.get(target, "")})
    return refs


def link_properties(obj: ET.Element) -> dict[str, str]:
    """Preserve serialized link/support properties, including XLink targets."""
    out = {}
    for p in obj.findall("./Properties/Property"):
        if "Link" in p.get("type", ""):
            out[p.get("name", "")] = ET.tostring(p, encoding="unicode")
    return out


def property_link_edges(obj: ET.Element, known_objects: set[str]) -> list[dict[str, str]]:
    """Decode saved link-like property values with the property name attached."""
    edges: list[dict[str, str]] = []
    for prop in obj.findall("./Properties/Property"):
        if "Link" not in prop.get("type", ""):
            continue
        pname = prop.get("name", "")
        for node in prop.iter():
            target = node.get("value") or node.get("obj")
            sub = node.get("sub", "")
            external_file = node.get("file", "")
            if node.tag in ("XLink", "XLinkSub"):
                # FreeCAD XLinks encode the document/object path in name/sub.
                path = node.get("sub", "")
                target = node.get("name", "")
                if path:
                    first = path.strip(".").split(".", 1)[0]
                    if first in known_objects:
                        target = first
                    sub = path
            if not target:
                continue
            if target not in known_objects and "." in target:
                first = target.split(".", 1)[0]
                if first in known_objects:
                    sub = target[len(first):] or sub
                    target = first
            if target in known_objects:
                edges.append({"property": pname, "target_object": target,
                              "subelement": sub, "external_file": external_file,
                              "serialized_tag": node.tag})
            elif node.tag in ("Link", "LinkSub", "XLink", "XLinkSub"):
                edges.append({"property": pname, "target_object": target,
                              "subelement": sub, "external_file": external_file,
                              "serialized_tag": node.tag})
    return edges


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
        geom_row = next((g for g in p.findall(".//GeometryList/Geometry")
                         if g.get("id", "") == geometry_id), None)
        geometry_node = next((child for child in (list(geom_row) if geom_row is not None else [])
                              if child.tag not in ("GeoExtensions", "Construction")), None)
        refs.append({"external_geometry_order": index, "serialized_geometry_id": geometry_id,
                     "sketcher_constraint_geometry_index": sketch_index,
                     "reference": ref, "source_object": target,
                     "source_subelement_token": subtoken, "flags": flags,
                     "projected_geometry_type": geom_row.get("type") if geom_row is not None else None,
                     "projected_geometry_data": geometry_node.attrib if geometry_node is not None else {},
                     "constraints": referenced_constraints,
                     "constraint_driving": bool(referenced_constraints)})
    return refs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("fcstd", type=Path, help="FreeCAD document to inspect")
    ap.add_argument("--body", default="Body002", help="PartDesign Body root (default: Body002)")
    ap.add_argument("--json", type=Path, help="output JSON path (default: stdout)")
    ap.add_argument("--allow-owner", action="append", default=[],
                    help="owner Body/App::Part permitted as a dependency; repeatable")
    ap.add_argument("--allow-object", action="append", default=[],
                    help="document object explicitly permitted as a dependency; repeatable")
    ap.add_argument("--allow-external-expression", action="append", default=[],
                    help="permit a cross-document expression source as internalName#objectName; repeatable")
    args = ap.parse_args()
    # Keep the caller's lexical path as well as its canonical path. FreeCAD
    # may serialize an external link relative to a /tmp symlink spelling;
    # resolving the component path before joining would resolve such links
    # against the wrong parent directory on macOS.
    source_argument = args.fcstd.expanduser().absolute()
    source = source_argument.resolve()
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
    # A Body's own expression engine can control its global placement even
    # though the Body container is deliberately excluded from the Tip feature
    # graph. Record those owner-level dependencies separately and include their
    # targets in reachability/readiness.
    root_body_expression_edges = expression_targets(root_body, set(object_headers))
    root_body_external_expressions = external_expression_refs(root_body)
    root_body_expression_targets = {e["target_object"] for e in root_body_expression_edges}

    # Compute ordinary object-dependency reachability independently from
    # Sketcher external-geometry reachability so the two closure counts remain
    # comparable and the omitted Sketcher boundary is visible.
    ordinary_visited: set[str] = set()
    ordinary_queue = [tip, *sorted(root_body_expression_targets)]
    while ordinary_queue:
        name = ordinary_queue.pop()
        if not name or name in ordinary_visited or name not in objects:
            continue
        ordinary_visited.add(name)
        typ = object_headers.get(name, "")
        if typ in CONTAINERS:
            # A linked helper Body contributes its active Tip geometry. Do not
            # expand the Body's entire Group/history as a container relation.
            if typ == "PartDesign::Body" and name != args.body:
                ordinary_queue.append(value_for(objects[name], "Tip"))
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
    property_edges_by_object: dict[str, list[dict[str, str]]] = {}
    queue = [tip, *sorted(root_body_expression_targets)]
    visited: set[str] = set()
    while queue:
        name = queue.pop()
        if not name or name in visited or name not in objects:
            continue
        visited.add(name)
        typ = object_headers.get(name, "")
        if typ in CONTAINERS:
            if typ == "PartDesign::Body" and name != args.body:
                body_tip = value_for(objects[name], "Tip")
                graph[name] = {body_tip} if body_tip else set()
                queue.append(body_tip)
            continue
        targets = set(deps.get(name, []))
        targets.discard(args.body)
        targets = {t for t in targets if object_headers.get(t, "") not in CONTAINERS}
        o = objects[name]
        property_edges = property_link_edges(o, set(object_headers))
        property_edges_by_object[name] = property_edges
        targets.update(edge["target_object"] for edge in property_edges
                       if edge["target_object"] in objects
                       and edge["property"] not in CONTEXT_PROPERTIES)
        refs = sketch_external_refs(o) if typ.startswith("Sketcher::") else []
        targets.update(r["source_object"] for r in refs if r["source_object"] in objects)
        # Expression references are ordinary document object names; keep these
        # explicit even if ObjectDeps omits them in a future serialization.
        for e in expressions(o):
            targets.update(n for n in object_headers if re.search(rf"(?<![A-Za-z0-9_]){re.escape(n)}\.", e["expression"]))
        graph[name] = targets
        queue.extend(targets)

    # Shortest Tip-to-object path gives a traceable downstream chain.
    paths = {tip: [tip]}
    q = [tip]
    for target in sorted(root_body_expression_targets):
        if target not in paths:
            paths[target] = [args.body, target]
            q.append(target)
    while q:
        n = q.pop(0)
        for target in graph.get(n, set()):
            if target not in paths:
                paths[target] = paths[n] + [target]
                q.append(target)

    # Owner and suppression metadata. Datum planes/axes live under an App::Origin
    # GeoFeatureGroupExtension, whose Group is serialized as a hidden _Property
    # in some FreeCAD versions. Propagate a PartDesign Body's ownership through
    # its Origin link and that datum group so sketch attachment to an in-body
    # plane is not misreported as an external component dependency.
    owners: dict[str, list[str]] = {}
    for owner_name, owner in objects.items():
        if object_headers.get(owner_name, "") not in CONTAINERS:
            continue
        group = owner.find("./Properties/Property[@name='Group']")
        if group is None:
            group = owner.find("./Properties/_Property[@name='Group']")
        if group is not None:
            for link in group.findall(".//Link"):
                owners.setdefault(link.get("value", ""), []).append(owner_name)

    body_owners = {name for name, typ in object_headers.items() if typ == "PartDesign::Body"}
    for body_name in body_owners:
        origin_name = value_for(objects[body_name], "Origin")
        if origin_name in objects:
            owners.setdefault(origin_name, []).append(body_name)
    changed = True
    while changed:
        changed = False
        for container_name, container in objects.items():
            inherited = set(owners.get(container_name, [])) & body_owners
            if not inherited:
                continue
            group = container.find("./Properties/Property[@name='Group']")
            if group is None:
                group = container.find("./Properties/_Property[@name='Group']")
            if group is None:
                continue
            for link in group.findall(".//Link"):
                child = link.get("value", "")
                if child not in objects:
                    continue
                existing = set(owners.get(child, []))
                missing = inherited - existing
                if missing:
                    owners.setdefault(child, []).extend(sorted(missing))
                    changed = True

    # Conservative readiness: only the root Body, explicitly allowed owners,
    # and explicitly allowed objects may supply geometry to an extraction.
    permitted_owners = {args.body, *args.allow_owner}
    permitted_objects = set(args.allow_object)
    blockers = []
    uncertain = []
    for name in sorted(visited):
        object_owners = set(owners.get(name, []))
        if object_owners and not (object_owners & permitted_owners) and name not in permitted_objects:
            blockers.append({"kind": "object_outside_permitted_owner", "object": name,
                             "owners": sorted(object_owners), "tip_path": paths.get(name, [])})
        elif not object_owners and name not in permitted_objects and name not in (args.body,):
            blockers.append({"kind": "unowned_document_object", "object": name,
                             "tip_path": paths.get(name, [])})
        for edge in property_edges_by_object.get(name, []):
            if edge["property"] in CONTEXT_PROPERTIES:
                continue
            target = edge["target_object"]
            if target not in objects:
                blockers.append({"kind": "unresolved_property_link", "object": name,
                                 **edge, "tip_path": paths.get(name, [])})
            elif edge["external_file"]:
                uncertain.append({"kind": "external_file_link", "object": name,
                                  **edge, "tip_path": paths.get(name, [])})
    def suppressed(name: str) -> bool:
        p = objects[name].find("./Properties/Property[@name='Suppressed']")
        if p is None:
            return False
        b = p.find(".//Bool")
        return bool(b is not None and b.get("value", "false").lower() == "true")

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

    # The sketch records are now complete; include external-geometry checks in
    # the readiness state after their exact source tokens have been recorded.
    for row in sketch_records:
        if not row["active_tip_reachable"]:
            continue
        for ref in row["external_geometry"]:
            target = ref["source_object"]
            if target not in objects:
                blockers.append({"kind": "unresolved_sketch_external_geometry",
                                 "object": row["name"], **ref})
            else:
                target_owners = set(owners.get(target, []))
                if not (target_owners & permitted_owners) and target not in permitted_objects:
                    blockers.append({"kind": "sketch_external_geometry_outside_permitted_owner",
                                     "object": row["name"], "target_object": target,
                                     "target_owners": sorted(target_owners),
                                     "subelement": ref["source_subelement_token"],
                                     "constraint_geometry_index": ref["sketcher_constraint_geometry_index"],
                                     "constraints": ref["constraints"],
                                     "tip_to_consumer_path": row["tip_to_sketch_path"]})
                if "#" in ref["source_subelement_token"]:
                    uncertain.append({"kind": "opaque_generated_subelement", "object": row["name"],
                                      "target_object": target,
                                      "subelement": ref["source_subelement_token"],
                                      "constraint_driving": ref["constraint_driving"]})

    external_expression_references = []
    for name in sorted(visited | {args.body}):
        o = objects.get(name)
        if o is None:
            continue
        refs = external_expression_refs(o)
        for ref in refs:
            external_path = Path(ref["external_file"]) if ref["external_file"] else None
            source_path = (Path(os.path.normpath(str(source_argument.parent / external_path))).resolve()
                           if external_path and not external_path.is_absolute()
                           else external_path.resolve() if external_path else None)
            key = ref["document_internal_name"] + "#" + ref["target_object"]
            allowed = key in set(args.allow_external_expression)
            row = {"consumer_object": name, "consumer_owners": owners.get(name, []),
                   **ref, "allow_key": key, "explicitly_allowed": allowed,
                   "resolved_external_file": str(source_path) if source_path else None,
                   "external_file_exists": bool(source_path and source_path.is_file()),
                   "external_file_is_relative": bool(ref["external_file"] and not Path(ref["external_file"]).is_absolute()),
                   "consumer_active_tip_reachable": name == args.body or name in paths,
                   "tip_to_consumer_path": ([args.body] if name == args.body else paths.get(name, []))}
            external_expression_references.append(row)
            if not allowed:
                blockers.append({"kind": "unpermitted_external_expression", **row})
            elif not row["external_file_exists"]:
                blockers.append({"kind": "missing_external_expression_document", **row})
            elif not row["external_file_is_relative"]:
                uncertain.append({"kind": "nonportable_external_expression_path", **row})

    external_edges = []
    for row in sketch_records:
        for ref in row["external_geometry"]:
            source_name = ref["source_object"]
            source_placement = objects[source_name].find(
                "./Properties/Property[@name='Placement']/PropertyPlacement") if source_name in objects else None
            ref["source_object_placement"] = source_placement.attrib if source_placement is not None else None
            ref["source_owner_placements"] = {
                owner: (objects[owner].find("./Properties/Property[@name='Placement']/PropertyPlacement").attrib
                        if objects[owner].find("./Properties/Property[@name='Placement']/PropertyPlacement") is not None
                        else None)
                for owner in owners.get(source_name, []) if owner in objects
            }
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

    property_edges = []
    for consumer, edges in property_edges_by_object.items():
        if consumer not in paths:
            continue
        for edge in edges:
            target = edge["target_object"]
            property_edges.append({"consumer_object": consumer, **edge,
                                   "consumer_owners": owners.get(consumer, []),
                                   "target_owners": owners.get(target, []),
                                   "dependency_role": ("container_context" if edge["property"] in CONTEXT_PROPERTIES
                                                       else "geometry_or_parameter_link"),
                                   "tip_to_consumer_path": paths.get(consumer, []),
                                   "active_tip_reachable": True})
    for edge in external_expression_references:
        if not edge["consumer_active_tip_reachable"]:
            continue
        property_edges.append({"consumer_object": edge["consumer_object"],
                               "property": edge["path"],
                               "target_object": edge["target_object"],
                               "target_document": edge["document_internal_name"],
                               "target_alias": edge["alias"],
                               "external_file": edge["external_file"],
                               "subelement": "", "serialized_tag": "Expression",
                               "expression": edge["expression"],
                               "consumer_owners": edge["consumer_owners"],
                               "target_owners": [],
                               "dependency_role": "external_expression",
                               "tip_to_consumer_path": edge["tip_to_consumer_path"],
                               "active_tip_reachable": True})
    for edge in root_body_expression_edges:
        target = edge["target_object"]
        property_edges.append({"consumer_object": args.body,
                               "property": edge["path"],
                               "target_object": target,
                               "subelement": "",
                               "external_file": "",
                               "serialized_tag": "Expression",
                               "expression": edge["expression"],
                               "consumer_owners": owners.get(args.body, []),
                               "target_owners": owners.get(target, []),
                               "dependency_role": "body_owner_expression",
                               "tip_to_consumer_path": [args.body],
                               "active_tip_reachable": True})

    # Summarize every direct object-graph edge that crosses a component-owner
    # boundary. Property links carry exact source properties; ObjectDeps-only
    # links remain explicit as graph edges without inventing a property name.
    boundary_crossings = []
    for consumer, targets in graph.items():
        if consumer not in paths:
            continue
        source_owners = owners.get(consumer, [])
        for target in sorted(targets):
            if target not in paths:
                continue
            target_owners = owners.get(target, [])
            if set(source_owners) == set(target_owners):
                continue
            matching = [e for e in property_edges
                        if e["consumer_object"] == consumer and e["target_object"] == target]
            if matching:
                for edge in matching:
                    boundary_crossings.append({"source_object": consumer,
                                               "source_owners": source_owners,
                                               "target_object": target,
                                               "target_owners": target_owners,
                                               "edge_kind": "property_link",
                                               "property": edge["property"],
                                               "subelement": edge["subelement"],
                                               "tip_to_source_path": paths.get(consumer, [])})
            else:
                boundary_crossings.append({"source_object": consumer,
                                           "source_owners": source_owners,
                                           "target_object": target,
                                           "target_owners": target_owners,
                                           "edge_kind": "ObjectDeps_or_expression",
                                           "tip_to_source_path": paths.get(consumer, [])})
    # Body-owner expressions are outside the feature graph above, so expose
    # their component-boundary crossings explicitly.
    for edge in root_body_expression_edges:
        target = edge["target_object"]
        source_owners = owners.get(args.body, [])
        target_owners = owners.get(target, [])
        if set(source_owners) != set(target_owners):
            boundary_crossings.append({"source_object": args.body,
                                       "source_owners": source_owners,
                                       "target_object": target,
                                       "target_owners": target_owners,
                                       "edge_kind": "body_owner_expression",
                                       "property": edge["path"],
                                       "expression": edge["expression"],
                                       "tip_to_source_path": [args.body]})
    for edge in external_expression_references:
        if not edge["consumer_active_tip_reachable"]:
            continue
        boundary_crossings.append({"source_object": edge["consumer_object"],
                                   "source_owners": edge["consumer_owners"],
                                   "target_object": edge["target_object"],
                                   "target_document": edge["document_internal_name"],
                                   "target_owners": [],
                                   "edge_kind": "external_expression",
                                   "property": edge["path"],
                                   "expression": edge["expression"],
                                   "subelement": "",
                                   "tip_to_source_path": edge["tip_to_consumer_path"]})

    readiness = {
        "status": "BLOCKED" if blockers else ("INDETERMINATE" if uncertain else "READY"),
        "root_body": args.body,
        "permitted_owners": sorted(permitted_owners),
        "permitted_objects": sorted(permitted_objects),
        "blockers": blockers,
        "uncertainties": uncertain,
        "policy": "READY requires every active dependency to resolve to the root Body or an explicitly permitted owner/object, with no unknown Sketcher references or external-file links."
    }

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
        "schema_version": 2,
        "source": {"filename": source.name, "sha256": digest,
                   "document_internal_name": "remove_warp_bypass",
                   "freecad_version_observed": "1.1.1 (0108fd4b4850cc46e625b60e53cea7a7bbe69f8d)"},
        "root": {"body": args.body, "tip": tip},
        "root_body_expressions": root_body_expression_edges + root_body_external_expressions,
        "external_expression_references": external_expression_references,
        "method": {
            "ordinary_edges": "Saved Document.xml ObjectDeps plus serialized property-link and expression targets, excluding non-geometric Context links and PartDesign::Body/App::Part ownership containers; a referenced helper PartDesign::Body contributes its active Tip only. Root Body expressions are recorded as owner-level dependencies because they can control global placement. Cross-document spreadsheet expressions are recorded separately and must be explicitly allowed.",
            "sketch_edges": "Sketcher::ExternalGeometryExtension Ref values in each Sketcher ExternalGeo GeometryList, expanded recursively",
            "constraints": "External geometry order i maps to Sketcher geometry index -(i+3); constraint First/Second/Third fields are checked",
            "note": "This is a saved-document audit. Referenced helper Bodies are traversed through Tip, not their complete Group. Validate with target FreeCAD before geometry-changing repairs."
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
        "property_link_edges": property_edges,
        "component_boundary_crossings": boundary_crossings,
        "extraction_readiness": readiness,
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
