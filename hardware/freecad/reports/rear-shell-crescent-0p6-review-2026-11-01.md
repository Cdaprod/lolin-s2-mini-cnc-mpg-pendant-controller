# Rear-shell crescent pad 0.6 mm review variant

Date: 2026-11-01

Status: **Validated disposable design variant; physical grip and durability remain unverified.**

## Visual reference

The 0.6 mm variant retains the existing upper/lower swept-crescent outlines and rear-shell seats. The preview shows the contact locations and the shared tilted contact plane; the reduced proud height is a side-profile change:

![Rear-shell underside with upper and lower swept-crescent anti-slip pad locations](images/rear-shell-fresh-fuse-structural-review-bottom-2026-11-01.png)

## Change and validation

The native pad Bodies retain their fully constrained profiles and 0.10 mm seat engagement. The proud height was reduced from 0.80 mm to 0.60 mm, so each pad has a 0.70 mm total length and is 0.20 mm closer to the shell's magnet-to-steel plane. The upper pad volume is `120.760708 mm³`; the lower pad is `45.918154 mm³`.

| Check | Result |
|---|---:|
| Upper and lower pad Bodies | Valid, one solid each |
| Upper and lower sketches | Fully constrained, closed |
| Shell intersection | 0 mm³ for both pads |
| Contact-face normal difference | 0° |
| Contact-plane offset | < 3×10⁻¹⁴ mm |
| Rear shell after assembly cold reopen | Valid, one solid |
| Rear-shell mesh at 0.08 mm / 0.35 rad | 16,050 facets; 0 boundary, 0 over-incident edges |
| Assembly links after cold reopen | 8, all valid |
| `UpperPadProtrusion` 0.60 → 0.70 → 0.60 mm | Component and live link changed by the expected 17.251530 mm³ and restored within 3×10⁻¹⁴ mm³ |
| Relocated assembly with prior 0.80 mm pad source omitted | Re-linked to 0.60 mm component and cold-opened successfully |

This variant reduces magnet stand-off by 0.20 mm relative to the 0.80 mm baseline while retaining the same planform. The thinner pad may reduce compliance, wear life, or grip. The comparison is a geometric candidate only; TPU grade, adhesion/retention, magnet holding force, complete pendant mass, and physical testing remain unresolved.

A relocated copy of the source review assembly was also opened without the former 0.80 mm pad document. Its pad and rear-shell links were reassigned to the 0.60 mm component and fresh-fuse shell, then saved and cold-opened successfully. This confirms the new assembly does not require the old untracked pad file.

## Disposition

The 0.6 mm variant is a separately saved native component and review assembly. The 0.80 mm baseline remains untouched. The assembly still uses the fresh-fuse hybrid rear-shell candidate, which has 42 BOPCheck warnings; it is not a production assembly replacement and structural load capacity is not verified.

## Files

- [Native 0.6 mm crescent pad component](https://github.com/Cdaprod/lolin-s2-mini-cnc-mpg-pendant-controller/blob/hardware-integration/hardware/freecad/pendant-bodies/rear-shell-anti-slip-crescent-pads-parametric-0p6-review-2026-11-01.FCStd)
- [Disposable 0.6 mm review assembly](https://github.com/Cdaprod/lolin-s2-mini-cnc-mpg-pendant-controller/blob/hardware-integration/hardware/freecad/pendant-modular-fresh-fuse-tpu-crescent-0p6-review-2026-11-01.FCStd)
- [Reproducible builder and cold-open validator](../scripts/build_rear_shell_fresh_fuse_crescent_0p6_review.py)
- [Machine-readable validation](rear-shell-crescent-0p6-review-2026-11-01.json)
