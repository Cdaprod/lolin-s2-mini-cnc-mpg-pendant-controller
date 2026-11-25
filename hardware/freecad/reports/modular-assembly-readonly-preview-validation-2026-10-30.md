# Modular assembly read-only preview validation

Date: 2026-10-30  
Branch: `hardware-integration`  
Assembly: `pendant-modular-assembly.FCStd`

## Result

The saved modular assembly opened and exported through `FreeCADCmd` without starting the FreeCAD GUI. The preview validator completed in 7.03 seconds and checked five live `App::Link` objects plus four static interim solids. All nine displayed shapes were valid, single-solid shapes with non-empty tessellations at 0.2 mm deflection. For each live link, its source Body matched the linked shape's volume and bounding box within the validator's 1e-6 tolerance.

The exporter produced top and bottom orthographic assembly views and an underside sheet of the four static interim shapes. The sheet shows the encoder faceplate and pocket as one fused solid, `Interim_EncoderFaceplatePocketUnsplit`; it does not present the two as separate split pieces. This checks the current saved display geometry and one-solid topology, not native PartDesign editability of that interim shape.

## Source preservation

The preview ran in a separate FreeCADCmd process and did not recompute or save CAD documents. Source hashes before and after the run were unchanged:

| File | SHA-256 |
|---|---|
| `pendant.FCStd` | `dc2aeddf7be327c73022a1dc053bf8a27d5cf476e9cd68468a4ee73ab8264881` |
| `pendant-master.FCStd` | `a2990a24c9b4fa140e25c1c5ef721fe65a6cb36f48a55cc168a11778421e56cb` |
| `pendant-modular-assembly.FCStd` | `d727c69f3e3bc68857fc29aa29438fc2a6f7a59954a6f64b3766d466fa57bbdb` |

Rendered PNGs and the run manifest were written outside the repository at `/tmp/pendant-preview-audit-20261030/` to avoid overwriting the existing checked-in previews.

## Limits

This is a saved-shape and visual inspection check. It does not test native feature recomputation, physical fit, or shell strength. The front shell, rear shell, upper faceplate, and fused encoder faceplate/pocket remain static interim representations; only the five linked components are live editable sources. The encoder interim is intentionally a fused starting shape for the user's own sketch and split.
