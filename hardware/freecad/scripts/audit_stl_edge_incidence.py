#!/usr/bin/env python3
"""Check welded triangle-edge incidence in binary STL files.

This is a mesh watertightness check, not a CAD BREP validity test or a strength
analysis. Vertices are quantized to a configurable tolerance before edges are
counted so duplicated STL vertices at shared triangle boundaries are welded.
"""
from __future__ import annotations

import argparse
import json
import math
import struct
from collections import Counter
from pathlib import Path


def inspect(path: Path, tolerance: float) -> dict:
    data = path.read_bytes()
    if len(data) < 84:
        raise ValueError(f"{path}: too short to be a binary STL")
    triangle_count = struct.unpack_from("<I", data, 80)[0]
    expected = 84 + triangle_count * 50
    if expected != len(data):
        raise ValueError(
            f"{path}: expected binary STL size {expected}, got {len(data)}")

    edge_incidence: Counter[tuple[tuple[int, int, int], tuple[int, int, int]]] = Counter()
    degenerate = 0
    for i in range(triangle_count):
        values = struct.unpack_from("<12fH", data, 84 + 50 * i)
        vertices = []
        for offset in (3, 6, 9):
            xyz = values[offset:offset + 3]
            if not all(math.isfinite(v) for v in xyz):
                raise ValueError(f"{path}: non-finite vertex in triangle {i}")
            vertices.append(tuple(round(v / tolerance) for v in xyz))
        if len(set(vertices)) != 3:
            degenerate += 1
        for a, b in ((vertices[0], vertices[1]),
                     (vertices[1], vertices[2]),
                     (vertices[2], vertices[0])):
            edge_incidence[tuple(sorted((a, b)))] += 1

    boundary = sum(n == 1 for n in edge_incidence.values())
    overincident = sum(n > 2 for n in edge_incidence.values())
    return {
        "file": str(path),
        "triangles": triangle_count,
        "unique_welded_edges": len(edge_incidence),
        "boundary_edges": boundary,
        "edges_with_more_than_two_incident_facets": overincident,
        "degenerate_triangles": degenerate,
        "weld_tolerance_mm": tolerance,
        "closed_two_manifold_mesh": boundary == 0 and overincident == 0 and degenerate == 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path, help="Binary STL files")
    parser.add_argument("--tolerance", type=float, default=1e-5,
                        help="Vertex weld tolerance in mm (default: 1e-5)")
    parser.add_argument("--output", type=Path,
                        help="Optional JSON output path")
    args = parser.parse_args()
    if args.tolerance <= 0:
        parser.error("--tolerance must be positive")
    results = [inspect(path, args.tolerance) for path in args.paths]
    payload = {"results": results, "all_closed_two_manifold": all(
        item["closed_two_manifold_mesh"] for item in results)}
    rendered = json.dumps(payload, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n")
    print(rendered)
    return 0 if payload["all_closed_two_manifold"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
