# Mechanical CAD candidate improvements — 2026-10-31

## Display bezel soft edge

A disposable copy of `pendant.FCStd` now has a native `PartDesign::Fillet` named `DisplayBezelSoftEdge` on the two top-facing circular rim edges of `Body003` (`Body003FullWidthSeat`). The two concentric edges were identified geometrically at center `(0, 2.99855, 4.0) mm`, radii `20.0` and `22.5 mm`; the feature uses `R = 0.3 mm`.

The resulting top flat annulus is about `1.9 mm` wide instead of `2.5 mm`. The glass-relief sketch radius is `21.7 mm`, leaving about `0.5 mm` between that relief radius and the post-fillet top outer rim at `22.2 mm`. This is a CAD clearance estimate; no physical glass model or hardware was installed.

The original upper-faceplate Tip and filleted candidate are each one valid solid. Recomputing the original `Body003FullWidthSeat` first reproduced its saved shape exactly (symmetric difference `0 mm³`). The candidate then recomputed, saved, closed, reopened, and recomputed successfully. Its tessellated mesh is closed. Filleting removes `5.157565 mm³`, adds no material, and leaves the overall faceplate bounds unchanged. The before/after preview is `display-bezel-fillet-before-after.png`.

A disposable full assembly candidate, `pendant-modular-design-improvements-candidate.FCStd`, replaces only the upper-faceplate interim shape with the filleted result and uses the existing rear load-path candidate. After save/reopen/recompute, the assembly root is valid with nine solids; component placements are unchanged and the five independently editable links resolve. The bezel remains an interim static shape in this assembly candidate; the native feature is preserved in the separate monolith-derived candidate.

The protected monolith SHA-256 remains `dc2aeddf7be327c73022a1dc053bf8a27d5cf476e9cd68468a4ee73ab8264881`.

## Rear-shell non-manifold redesign candidate

The defect is not at the old seam tongue-and-groove alignment grooves. The existing audit locates it at the four rear screw-boss-to-wall reinforcement paths (`RearBossToWallLoadPaths`). The tracked `rear-shell.stl` reports `335` boundary edges and `12` edges with more than two incident facets at `1e-5 mm` vertex-weld tolerance.

The existing hybrid candidate `pendant-bodies/rear-shell-loadpath-repair-candidate.FCStd` replaces the non-manifold stored-shape load-path feature with four native PartDesign Pads and restores six M2 passages with a native Pocket. It is one valid solid, preserves the source outer bounds, and its FreeCAD export has `19,076` facets with zero boundary edges, zero over-incident edges, and zero degenerate facets. The M2 and magnet clearances are unchanged in the candidate construction.

This is a deliberate redesign candidate, not an exact geometry-preserving repair: candidate rear-shell volume is `40,609.693 mm³` versus `40,961.359 mm³` in the defective original Tip, a reduction of `351.666 mm³` (`0.858%`). The candidate base is a static BREP and the old shoulder/ramp history is not reproduced. It is therefore **not promoted as a fully editable shell or as structurally proven**. A combined assembly candidate is supplied for review, but the protected production monolith and production assembly remain unchanged. The five-times-pendant-weight load target still requires mass, boundary-condition and physical-load validation.

## Candidate files

- `../pendant-modular-design-improvements-candidate.FCStd` — combined assembly candidate, saved beside its relative component links.
- `pendant-display-bezel-fillet-candidate.FCStd` — full monolith-derived native bezel-filleting candidate (local disposable file; regenerate using `../scripts/create_display_bezel_candidate.py`).
- `display-bezel-fillet-before-after.png` — preview.
- `rear-shell-loadpath-repair-candidate.stl` — exported mesh for candidate edge-incidence comparison.

No production CAD or STL was overwritten.