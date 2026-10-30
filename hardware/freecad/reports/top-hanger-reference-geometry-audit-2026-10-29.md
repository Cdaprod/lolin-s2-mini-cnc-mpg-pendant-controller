# Top hanger reference-geometry audit

Date: 2026-10-29
Branch: `hardware-integration`
Scope: read-only saved-shape inspection; no CAD documents were recomputed or saved.

## Key finding

The monolith contains a helper Body named `Body_HookReference`, labeled “Hook Reference — 2 mm Steel.” Its saved global bounding box is X `[-17, 17]`, Y `[55.5, 79.5]`, Z `[-36, 0]` mm. The active front and rear hanger sketches are fully constrained 35.6 × 3.0 mm obrounds with global XY bounds X `[-17.8, 17.8]`, Y `[80.5, 83.5]` mm.

The hook reference stops 1.0 mm below the active slot's lower edge by their global Y bounds. Its saved shape also has valid Boolean common-volume intersections of `1084.2444 mm³` with the saved front-shell Body, `2612.6610 mm³` with the rear-shell Body, and `4.9760 mm³` with the upper-faceplate Body. The helper is labeled validation-only and is not an assembly component. These measurements therefore do not show that the actual closed aperture fits or carries a real hanger; if this shape was intended as that fixture, its placement/role needs correction before it can be used for fit or load validation.

The live hanger requirement remains: a **closed hole through both shell bodies** that carries the pendant's weight. The current slot sketch and the previously identified thin shell webs remain unverified for strength. No profile, placement, or shell geometry was changed.

## Model-only printed-part volume

A read-only inventory of the current modular assembly found nine valid single-solid physical representations: four static interim parts (front shell, rear shell, upper faceplate, and fused unsplit encoder faceplate/pocket) and five live links (display retainer, USB cover, two locators, and breakout board). Their summed saved volume is `112191.4487 mm³` (`112.1914 cm³`). This is a model-only volume inventory, not a measured product weight. It excludes screws, display/electronics, wiring, and other unmodeled hardware. To estimate plastic mass, multiply `112.1914 cm³` by the chosen material's actual density, then add omitted component masses or preferably weigh the assembled pendant. The source BREP shapes were not recomputed in this measurement.

## Screening limit

A denser 0.5 mm X/Z section-grid run of `audit_top_hanger_sections.py` exceeded its 150-second limit and returned no report. The script terminated its owned FreeCADCmd worker; no source file was saved. The previous 1 mm section screen remains sparse diagnostic evidence only. Do not rerun the same 0.5 mm section method unchanged.

## Current state and next validation gate

- The monolithic pendant SHA-256 remains `dc2aeddf7be327c73022a1dc053bf8a27d5cf476e9cd68468a4ee73ab8264881`.
- The modular assembly SHA-256 remains `d727c69f3e3bc68857fc29aa29438fc2a6f7a59954a6f64b3766d466fa57bbdb`.
- No material, print orientation, or numeric proof load is recorded in project documentation. Use user-confirmed values or a measured assembled mass before claiming a structural margin.
- Before changing geometry, restore a trustworthy feature-to-Tip path in both shells, including the generic stored-shape load-path features. Then validate the real hanger contact/fixture, continuous closed aperture, minimum 3D ligament, screw/head-seat clearance, and both shell Tips after save/reopen/recompute. A structural calculation or physical proof test is still required; shape validity and a closed silhouette are not strength evidence.
