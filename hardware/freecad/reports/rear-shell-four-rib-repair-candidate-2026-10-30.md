# Rear shell four-rib mesh repair candidate

Date: 2026-10-30 · Branch: `hardware-integration`

The user asked for the rear shell's non-manifold edges to be fixed in the FreeCAD model, not patched in OrcaSlicer. This candidate replaces the static rear-shell interim shape in `pendant-modular-repair-candidate.FCStd`; it does not modify the protected monolith, production modular assembly, production STL, or saved OrcaSlicer 3MF.

## Reconstructed shape

`regenerate_rear_boss_wall_loadpaths.py` rebuilds four triangular ribs from the `Body002FullWidthSeat` base. The upper pair uses the existing 45-degree ramp run/rise and width. The lower pair follows sectioned boss and wall boundaries. The exact `Pocket`/`Pocket015` magnet-clearance and `Pocket018` screw-passage removal volumes are subtracted before fusing each rib.

Each rib fused into the current rear base as one valid solid. After all four, the candidate has one valid solid, 471 faces, volume 40,609.693637 mm³, and the same six bounding-box coordinates as the base. The screw-clearance and magnet-clearance intersections are unchanged from the base (zero added obstruction). The candidate rear shape has zero volumetric intersection with the front shell in the saved assembly coordinate frame.

The current assembly shell is 40,961.359008 mm³, so the candidate differs by −351.665371 mm³. The BREP Boolean checks on the original defective load-path history are not reliable enough to claim exact geometric equivalence. This is an intentional reconstruction candidate and needs mechanical review; no load capacity is inferred.

## File and mesh validation

The candidate assembly is saved beside its component directory so relative links remain portable. After close/reopen, all five live links resolve. The repaired rear interim shape is one valid solid and FreeCAD reports a closed mesh. The complete eight-part exporter succeeds into a disposable output directory; all eight meshes are closed. The rear mesh has 19,640 facets. An independent welded-vertex triangle-edge count at 0.00001 mm tolerance found 29,460 edges, all with exactly two incident facets (zero boundary or over-incident edges).

The candidate shape remains a static `Part::Feature`, matching the existing interim assembly architecture; it is not represented as a native editable rear-shell history. A monolithic `Body002` recompute through the full history did not complete within the bounded run, so that feature-history gate remains open. The candidate assembly avoids that Body recompute path and validates the actual static shape used by the current modular assembly.

Use:

```sh
python3 hardware/printing/pendant/build_meshes.py \
  --assembly hardware/freecad/pendant-modular-repair-candidate.FCStd \
  --output-dir /tmp/pendant-repair-mesh-review
```

Do not replace the current production assembly or user 3MF until the changed support geometry has been reviewed. A future editable shell extraction still needs its own native recomputation and load-path validation.
