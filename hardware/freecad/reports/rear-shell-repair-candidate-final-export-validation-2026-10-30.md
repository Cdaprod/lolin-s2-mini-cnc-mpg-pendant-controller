# Repair-candidate final export validation

Date: 2026-10-30 · Branch: `hardware-integration` · FreeCAD 1.1.1

## Result

Reopened the saved disposable `pendant-modular-repair-candidate.FCStd` through the repository's model-based mesh exporter and generated all eight printable component meshes into `/tmp/pendant-final-validation-20261030`. The export passed the CAD single-solid checks. A separate binary-STL edge-incidence audit, welding vertices at 0.00001 mm, found zero boundary edges, zero edges incident to more than two facets, and zero degenerate triangles in every exported component.

| Part | Triangles | Boundary edges | >2 incidence | Degenerate triangles | Result |
|---|---:|---:|---:|---:|---|
| `front-shell.stl` | 31,638 | 0 | 0 | 0 | PASS |
| `rear-shell.stl` | 19,126 | 0 | 0 | 0 | PASS |
| `upper-faceplate.stl` | 13,850 | 0 | 0 | 0 | PASS |
| `encoder-faceplate-pocket-fused.stl` | 7,356 | 0 | 0 | 0 | PASS |
| `display-retainer.stl` | 1,856 | 0 | 0 | 0 | PASS |
| `usb-cover.stl` | 1,854 | 0 | 0 | 0 | PASS |
| `faceplate-locator-a.stl` | 884 | 0 | 0 | 0 | PASS |
| `faceplate-locator-b.stl` | 884 | 0 | 0 | 0 | PASS |

The repaired rear-shell candidate has 19,126 facets and a closed two-manifold tessellation. This confirms that the candidate model file can produce a watertight rear-shell mesh without slicer repair.

## Candidate-only disposition

This remains a review candidate. The rear component is hybrid: an imported BREP base with native editable support Pads and an M2 clearance Pocket. The front shell, upper faceplate, and fused encoder-faceplate/pocket remain static interim geometry in the candidate assembly. The rear candidate has not been proven exactly equivalent to the previously defective shell, and its modified load paths have not passed structural analysis or physical testing. The user's PLA / flat-face print requirement and 5× complete pendant weight proof target remain; complete assembly mass and verified hanger/bracket contact are not yet available.

No production assembly, monolith, source STL, 3MF, backup, or recovery file was changed. The OrcaSlicer 3MF remains as it was before this validation. The complete machine-readable result and source hashes are in `rear-shell-repair-candidate-final-export-validation-2026-10-30.json`.

## Cold-open component edit propagation

A second disposable copy mirrored the relative `pendant-bodies/` and master layout. `UpperLeftSupportPad.Length` was changed from 13.0 to 13.2 mm and saved. The assembly rear link changed from 40,609.693012 to 40,609.873274 mm³; the same edited value survived closing and reopening the assembly, and restoring the pad to 13.0 mm returned the exact baseline volume. All six candidate assembly links resolved. This verifies the rear-link edit/refresh path for this parameter only.
