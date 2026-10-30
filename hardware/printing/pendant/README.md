# CNC Pendant — OrcaSlicer manufacturing project

This directory contains an OrcaSlicer multi-plate project and the individual millimeter-scale meshes exported from the saved modular assembly. The FreeCAD monolith, master, and modular assembly were treated as read-only sources; this work did not edit the CAD documents.

## Project

Open `pendant-orcaslicer.3mf` in OrcaSlicer. It uses the configured Elegoo Neptune 2 0.4 mm nozzle, Panchroma PLA Matte, and 0.20 mm standard process profile. The shells are laid on their broad faces, with their existing CAD Z thickness oriented vertically. The project is intended for review and preparation; no print was started.

| Plate | Contents | Mesh status |
|---|---|---|
| 1 | Front shell | Closed mesh |
| 2 | Rear shell | **Open/non-manifold mesh warning** |
| 3 | Display retainer | Closed mesh |
| 4 | USB cover, faceplate locator A, faceplate locator B (three separate selectable objects) | Closed meshes; spaced apart |
| 5 | Encoder faceplate + pocket, preserved as one fused unsplit component | Closed mesh |
| 6 | Upper faceplate | Closed mesh |

The electronics board envelope, screws, sketches, datum objects, binders, and other construction geometry are excluded. The four shell/faceplate interim objects remain static source shapes in the modular assembly; the project exports their current saved shapes. The fused encoder faceplate/pocket is intentionally kept as one mesh.

## Mesh validation and current rear-shell blocker

The export uses 0.08 mm linear deflection and 0.20 rad angular deflection without mesh healing or repair. Seven generated meshes are closed according to FreeCAD's mesh solidity check. `rear-shell.stl` is not watertight/manifold and is **not print-ready**. A source audit traced the first non-solid tessellation to `Body002.RearBossToWallLoadPaths`, a stored-shape PartDesign feature with no regeneration method; its exact geometry must be reconstructed in FreeCAD while preserving the four boss-to-wall reinforcements. See [the rear-shell source audit](../../freecad/reports/rear-shell-nonmanifold-source-audit-2026-10-30.md). OrcaSlicer repair is not the remedy.

The mesh exporter now stages all outputs and refuses to promote any set containing a non-closed mesh. A failed export leaves the current meshes and the user's slicer project untouched.

All project objects are placed within the profile's 235 × 235 × 250 mm printable volume. That placement check does not override the rear-shell mesh warning. A whole-project slice was not accepted as a validation result while the rear shell mesh is invalid. OrcaSlicer opened the project and displayed the six named plates. No physical print was started.

Source BREP bounds are sometimes conservative because curved support surfaces extend beyond their trimmed faces. The mesh manifest records both the FreeCAD source bounds and the actual exported mesh bounds. The exported mesh is not claimed to reproduce those conservative support-surface bounds; dimensions and geometry should be checked against the trimmed part shape when editing the CAD.

## Regeneration

1. Run `build_meshes.py` with the installed FreeCADCmd to export the eight listed shapes and update `meshes/mesh-manifest.json`.
2. Open all eight STL files as separate objects in OrcaSlicer with the existing printer, filament, and process presets. Save that one-plate staging project as `pendant-orcaslicer-single-plate.3mf` in this directory.
3. Run:

   ```sh
   python3 hardware/printing/pendant/build_orca_project.py \
     --input hardware/printing/pendant/pendant-orcaslicer-single-plate.3mf \
     --output hardware/printing/pendant/pendant-orcaslicer.3mf
   ```

4. Validate the package and plate placements:

   ```sh
   python3 hardware/printing/pendant/validate_orca_project.py
   ```

The temporary one-plate staging project is not committed. Keep the final project and mesh exports together so future changes can be reviewed against the source assembly.
