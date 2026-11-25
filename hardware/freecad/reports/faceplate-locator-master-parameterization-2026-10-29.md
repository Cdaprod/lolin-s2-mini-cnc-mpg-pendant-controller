# Faceplate locator master parameterization — 2026-10-29

The two native faceplate locator Bodies now use master-owned X/Y aliases to drive the centers of their passage, upper-seat, and lower-seat profile sketches. Each of the six sketches remains fully constrained; local radii and existing pad depths remain component-owned.

The initial disposable replacement preserved both locator Bodies exactly by symmetric BREP difference (0.0 mm³). The cold-start tests then changed each center coordinate by 0.1 mm, refreshed only the locator component, validated the complete saved assembly link inventory, reopened the assembly, and restored the original coordinates.

- Locator A: `FaceplateLocatorA_X`, −28.76 → −28.66 → −28.76 mm. Its bounding box translated +0.10 mm in X while volume/area remained stable.
- Locator B: `FaceplateLocatorB_Y`, 65.0 → 65.1 → 65.0 mm. Its bounding box translated +0.10 mm in Y while volume/area remained stable.
- Both live links matched their source Bodies at baseline, changed, and restored states. Restored forward and reverse BREP differences were 0.0 mm³.
- Headless bottom and top assembly previews rendered successfully; the existing closed hanger opening remains visible through the paired shell representation. No hanger geometry was changed or strength certification attempted.

`refresh_modular_assembly.py --only-component <filename>` now supports a bounded refresh for one editable component. It still checks all assembly links and interim solids and saves/reopens the assembly. The default behavior continues to refresh all editable components. The propagation test harness now writes negative spreadsheet dimensions as formulas (rather than text) and passes an integer timeout to the refresh CLI.

This milestone does not modularize the static shell and faceplate representations, validate hanger load capacity, or prove the full assembly is structurally safe. See the machine-readable test metrics in this directory.
