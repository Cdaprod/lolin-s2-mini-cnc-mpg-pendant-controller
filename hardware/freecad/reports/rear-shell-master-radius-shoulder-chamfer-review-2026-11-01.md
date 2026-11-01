# Rear-shell shoulder chamfer on the master-radius review candidate — 2026-11-01

## Candidate

This review copy starts from the master-radius-driven native rear-shell candidate and adds a native 1.0 mm PartDesign chamfer to the two upper screw-boss underside arcs. The source was selected by its measured circle geometry, global bounds, Z plane, and arc length; the matched candidate edges were `Edge1189` and `Edge232`.

![Rear-shell underside context showing screw bosses, reconstructed support paths, bottom fillet, and crescent seats](images/rear-shell-native-loadpaths-2026-11-01/rear-shell-bottom.png)

This preview shows the surrounding underside design. It is not a close-up of the small chamfer itself.

## Validation

- The native chamfer candidate cold-opened and recomputed with a valid single-solid rear-shell Body and no invalid feature states.
- The chamfer removes 15.524314 mm³ relative to the source review candidate. The candidate volume is 41,065.369933 mm³.
- At 0.12 mm linear mesh deflection, the mesh is closed with 31,304 facets, zero boundary edges, zero overincident edges, and zero degenerate facets.
- The FreeCAD BOP error-line count falls from 28 to 26. Remaining curve-on-surface findings mean the BRep is not fully topology-clean.
- The M2 clearance keep-out intersection is 0 mm³ before and after the chamfer.
- The master-driven middle-support radius remains editable: 7.00→7.05→7.00 mm recomputes a valid one-solid Body and restores its baseline volume within 7.3×10⁻¹² mm³.
- A disposable assembly copy links to the chamfer component. It cold-opens with nine resolved links, a valid 11-solid assembly root, and preserved rear-link placement. The pre-save front/rear common-volume check passed at the 1×10⁻⁵ mm³ tolerance.

## Limits and use

This is a review candidate, not the canonical rear-shell source. The stored-shape base and remaining BOP findings are still present; no FEM or physical proof-load test was performed. The 1 mm chamfer was not promoted into the protected monolith or the production assembly.

Open the component directly from `hardware/freecad/pendant-bodies/` to inspect or edit its feature tree. Open the linked review assembly to inspect the assembled result. Keep the protected `pendant.FCStd` baseline unchanged.

Machine-readable values are in the [validation record](rear-shell-master-radius-shoulder-chamfer-review-2026-11-01.json).
