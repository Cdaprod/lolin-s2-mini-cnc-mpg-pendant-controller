# Rear-shell master-driven support radius — review candidate

## Change

The reconstructed middle support roots now reference the existing master `InternalHardware.MiddleSupportRadius` alias. The left and right root-circle radii are driven by master expressions; their center positions remain dimensioned at the stored base's current coordinates. The R0.25 mm bottom fillet, four native load-path lofts, M2 passages, and crescent seats remain in the Body history.

![Rear shell underside with reconstructed supports, bottom fillet, and crescent seats](images/rear-shell-native-loadpaths-2026-11-01/rear-shell-bottom.png)

## Validation

- Both root sketches remain fully constrained. The component stores its master reference as repo-relative `../pendant-master.FCStd`.
- Cold-open/recompute returns a valid single-solid Tip. At the 7.00 mm baseline it has volume 41080.8942465 mm³, area 30697.5139877 mm², and unchanged shell bounds. Its 0.12 mm test mesh is closed with zero boundary, overincident, and degenerate edges.
- The candidate retains 28 BOP findings, all `BOPAlgo_InvalidCurveOnSurface`.
- A reversible 7.00→7.05→7.00 mm change altered the component volume by +14.588653 mm³ and restored it within 2.91×10⁻¹¹ mm³. The Tip stayed a valid one-solid shape during the changed state.
- A new review assembly cold-opened with nine live links and retained the rear `LinkPlacement`. The same master-radius probe changed the linked rear volume by +14.588653 mm³ and restored it within 5.83×10⁻¹¹ mm³.
- The front/rear shell common result in this assembly was valid with 0 mm³ common volume and 0 mm minimum distance. This shows no volume overlap; touching/coincident regions remain, and positive clearance/contact area were not measured. Two interim faceplate representations remain static.

## Parameter boundary and limits

A separate +0.05 mm test of the master screw half-spacing moved the support roots relative to the stored shell base. `LowerLeftNativeLoadPath` and downstream features then reported invalid shapes. Restoring 27.00 mm returned the valid baseline. That positional coupling is excluded from this candidate. The center locations and the wall/lower profiles remain explicit fixed sketch dimensions until the base shell itself can regenerate.

This review component still uses a stored-shape shell base and retains the 28 BOP findings. A Boolean comparison against the previous rear candidate failed volume conservation, so exact BRep equivalence remains unverified. There is no FEM or physical 5× proof-load result. Keep this as a review-only editable component and assembly; the protected monolith, production master, and production assembly were not modified.

The reusable cold-open and parameter validator is [validate_rear_shell_master_radius_review.py](../scripts/validate_rear_shell_master_radius_review.py). Full metrics are in the [JSON validation record](rear-shell-master-driven-radius-review-2026-11-01.json).
