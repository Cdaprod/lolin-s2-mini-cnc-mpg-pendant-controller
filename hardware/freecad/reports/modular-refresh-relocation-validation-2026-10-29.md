# Modular refresh and relocated-checkout validation

Date: 2026-10-29  
Branch and source revision: `hardware-integration` at `08de94d`  
Scope: disposable Git worktree at `/tmp/pendant-modular-validation-08de94d`; no CAD document in the authoritative checkout was opened for saving or modified.

## Result

`scripts/update_modular_project.py` completed successfully from the relocated checkout. It opened the master first, recomputed and saved the four canonical editable component documents, refreshed their external master expressions, then recomputed and saved the assembly candidate.

All editable manufacturing Bodies were valid and one solid after refresh. The validated Body Tips were:

| Component document | Manufacturing Body Tip | Volume (mm³) |
|---|---|---:|
| `breakout-board.FCStd` | `Pad023` | 2,660.545384 |
| `display-retainer.FCStd` | `RetainerShellClearancePocketV3` | 2,050.792480 |
| `faceplate-locators.FCStd` | `LocatorScrewPassage0`, `LocatorScrewPassage1` | 88.294960 each |
| `usb-tethered-cover.FCStd` | `USBPlugLeadIn` | 665.220690 |

The refreshed assembly contained five valid live links and four valid static interim solids. A second, fresh FreeCADCmd process opened that assembly from the relocated checkout and exported its geometry. All nine shapes passed validity and single-solid checks; each live link matched its source Body by volume and bounds. This confirmed that the relative component/master references resolved outside the original checkout after saving and reopening.

The top, bottom, and static underside component previews from the relocated checkout were byte-identical to the corresponding previews from the original checkout. Their SHA-256 values were respectively:

| Preview | SHA-256 |
|---|---|
| Assembly bottom | `c4329c7d256252c7c1156492ca6adaac93ba11b832ca9658f1c81e0c90a77be8` |
| Assembly top | `ce37cbfa68afe42cfd1e6ec3c34f24554632dfd70b4f732a69dda9396d60d1a5` |
| Static component underside sheet | `6c2d6937d7e06c30fe0b5fae8b36654a7f392a79edb13f8c9f416463011a531a` |

## Limits and protection

This verifies the refresh workflow and link portability for the current architecture; it does not complete modularization. The front shell, rear shell, upper faceplate, and fused unsplit encoder faceplate/pocket remain static interim representations in the assembly. The source monolith was not opened for modification and retains SHA-256 `dc2aeddf7be327c73022a1dc053bf8a27d5cf476e9cd68468a4ee73ab8264881`. The temporary worktree was removed after the cold-start preview check; generated preview images remain under `/tmp/pendant-modular-validation-08de94d-preview/` for this session.
