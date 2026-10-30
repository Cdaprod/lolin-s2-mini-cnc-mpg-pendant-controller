# Top-hanger load-path locality check

Date: 2026-10-29 (local)  
Branch: `hardware-integration`  
Source: `hardware/freecad/pendant.FCStd`  
Source SHA-256: `dc2aeddf7be327c73022a1dc053bf8a27d5cf476e9cd68468a4ee73ab8264881`

## Scope and method

Ran `scripts/audit_hanger_loadpath_locality.py` through FreeCAD 1.1.1 `FreeCADCmd`. It opened the monolith, clipped each saved base/output shape to two bounded global-coordinate regions around the closed hanger, compared the clipped shapes with valid Boolean differences, and closed the document without recomputing or saving.

## Results

| Region (mm) | Shell | Base clipped volume (mm³) | Load-path clipped volume (mm³) | Added/removed local material (mm³) | Boolean checks |
|---|---|---:|---:|---:|---|
| Hanger annulus: X −20..20, Y 78..88, Z −37..1 | Front | 1770.677546 | 1770.677546 | 0 / 0 | Valid |
| Hanger annulus: same | Rear | 1929.491184 | 1929.491184 | 0 / 0 | Valid |
| Slot band: X −19..19, Y 80.4..83.6, Z −37..1 | Front | 118.883287 | 118.883287 | 0 / 0 | Valid |
| Slot band: same | Rear | 129.661657 | 129.661657 | 0 / 0 | Valid |

Both regions show a zero symmetric-difference volume between each saved receiver/seat base and its corresponding stored boss-to-wall load-path output. The differences were valid Booleans. This means those features add no cached material inside the sampled hanger annulus or slot band. They may still affect remote load transfer; this local check does not rule that out.

## Limits and implication

This is a localized comparison of saved shapes, not a full-history recomputation, global geometry equivalence proof, stress analysis, or strength certification. It does not establish that the current aperture is adequate, and a closed outline alone is not proof of safety. It does establish that the two features named as boss-to-wall load paths cannot be counted as local reinforcement around the opening in these regions.

The user specified PLA, both shells printed flat on their broad faces, and a physical proof load of 5× complete assembled weight. Actual assembled mass is still unknown. Next work should identify the real hanger-to-opening contact and the load path through both shell walls, then restore a trustworthy feature chain and assess the local section before any geometry change. Require a physical proof test at the specified load before describing the design as safe.

Machine-readable results: `top-hanger-loadpath-locality-2026-10-29.json`.
