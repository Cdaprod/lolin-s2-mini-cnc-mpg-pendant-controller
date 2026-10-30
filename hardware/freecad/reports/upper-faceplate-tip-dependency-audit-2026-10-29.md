# Upper faceplate Tip dependency audit

Date: 2026-10-29 (local)

## Scope and method

Read-only audit of `Body003` (active Tip `Body003FullWidthSeat`) in `hardware/freecad/pendant.FCStd`. The manifest was generated from the saved FCStd `Document.xml` using `scripts/audit_sketch_dependencies.py`; the CAD file was not opened, recomputed, or saved. The source SHA-256 was `dc2aeddf7be327c73022a1dc053bf8a27d5cf476e9cd68468a4ee73ab8264881`.

This is a Tip-rooted reachability audit that follows ordinary dependencies, serialized property links and expressions, and Sketcher external geometry. It traverses referenced helper Bodies through their active Tips, not their entire Groups. The results describe saved dependencies; FreeCAD-side recompute is still required to validate any candidate edits.

## Result

- Ordinary object closure: **81 objects**.
- Expanded closure including property links and Sketcher external geometry: **200 objects**.
- Sketches reached: **85**; serialized Sketcher external-geometry references: **29**.
- Extraction readiness: **BLOCKED**, with 159 policy blockers and 19 uncertainties. The blocker count includes many helper/history objects outside a permitted owner; it is not a count of independent physical components.
- No App::Link objects were found in this saved Tip closure.

## Significant dependency paths

1. The faceplate Tip reaches `Body003FullLandTransferTool → Body003LandSplit → BaseFeature002 → FrontFullLandTransferRestricted → FrontFullLandTransfer → SmallHangerPocketBody`. `FrontFullLandTransfer.Base` references `SmallHangerPocketBody`; this is an active dependency on front-shell construction geometry.
2. The front full-land branch also consumes `FrontOriginalMatingLand.Support → SmallHangerPocketBody.Face13` and returns to profiles supported by `Body003` (`WidthControlled_StableFaceplateBaseOutline`). This forms a shared construction loop across the intended component boundary.
3. Later faceplate features reach `Body005` and a `Clone` based on `FrontMatchedInnerCavity`, so encoder-related construction also enters the Tip ancestry.
4. `Sketch014` in the faceplate history has four active external references to `Sketch` in owner `Body` (Edge1–Edge4). `Sketch016` has an active external reference to `Sketch.Edge5` in `Body`. Six other active-tip-reachable external references in `Sketch020` point to suppressed `Pocket016`; those six are unconstrained. There are 20 other active-tip-reachable external geometry references in the manifest, including 8 constrained references; see the JSON for exact tokens, indices, and paths.
5. Several width-controlled faceplate/envelope profiles depend on `ExteriorEnvelope`, with downstream front/rear envelope helper features also present in the closure. These must be distinguished from true shell-to-shell dependencies before any extraction work.

The 61 recorded component-boundary crossings are property/dependency edges, not 61 independent cross-component sources. The machine-readable manifest preserves each source, property, target, subelement token, and Tip path.

## Mechanical requirement retained

The top hanger is a **closed, load-bearing opening through both shell Bodies**, intended to support the full pendant weight. The user explicitly confirmed that the opening must remain closed and strong enough for that load. This audit makes no hanger geometry or strength claim; no geometry was changed.

## Next safe step

Do not recursively copy `Body003` yet. First classify the full-land transfer loop and the encoder/helper-body inputs by their contribution to the upper faceplate Tip. Any attempt to break the loop must be made in a disposable FreeCAD candidate and validated by native recomputation, save/reopen/recompute, and geometry comparison. Separately, the hanger work remains blocked on recovering the stored load-path feature inputs and defining a load/print validation case.

Machine-readable results: `upper-faceplate-tip-dependency-audit-2026-10-29.json`.
