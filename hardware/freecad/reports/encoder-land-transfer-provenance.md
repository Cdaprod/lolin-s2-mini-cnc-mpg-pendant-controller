# Encoder land-transfer surface provenance

Date: 2026-10-29  
Branch: `hardware-integration`  
Document inspected: `pendant-encoder-fused-working.FCStd`  
Document SHA-256: `c20e68fcc2a17782a37aecc9eac1ae7388192e94479077532331948ac01a6d30`

## Scope

This was a read-only inspection of saved shapes. It did not recompute, save, or modify the encoder candidate, authoritative monolith, master, or assembly. The purpose was to trace the geometric support surfaces in `FrontFullLandTransferRestricted` to their source feature families before attempting to change `FrontFullLandTransfer.Base`.

The reusable probe is `scripts/probe_shape_surface_families.py`; raw face-level matches, object-link properties, counts, comparison tolerances, and source digest are in `encoder-land-transfer-surface-provenance.json`.

## Findings

`FrontFullLandTransferRestricted` is a valid saved one-solid shape with 145 faces and volume `1090.513489 mm³`. Its construction chain is:

```text
SmallHangerPocketBody ─┐
                       ├─ FrontFullLandTransfer ─┐
FrontFullLandCutter ───┘                         ├─ FrontFullLandTransferRestricted
FrontMatingLandProjection ──────────────────────┘
```

The saved output's supporting surfaces map as follows:

| Source surface family | Matched output faces | Interpretation |
| --- | ---: | --- |
| `SmallHangerPocketBody` | 90 | Shell-derived retained support surfaces |
| `FrontFullLandCutter` | 32 | Loft/cutter-derived retained support surfaces |
| `FrontFullLandTransfer` | 122 | Intermediate transfer surfaces also retained in the restricted output |
| `FrontMatingLandProjection` | 0 | No output face has a matching support surface; this is consistent with a trimming role, but does not establish that the tool can be removed |

The per-source counts overlap; they are not additive. The union of mapped output face indices is 122 of 145. The 23 unmatched faces are 15 cylindrical and 8 planar supports. A prior feature-history trace found all 90 B-spline support definitions that match `SmallHangerPocketBody` first appearing at `FrontMatchedInnerCavity` (front Body group index 46). This makes that feature a focused substitution hypothesis, not a proven replacement: matching support surfaces does not establish equal trimmed faces, volumes, edges, placements, or downstream topological naming.

Surface matching was restricted to the same Python surface class at `1e-7` linear and angular tolerances. Eight B-spline `isSame` calls raised exceptions; an exact comparison of degrees, knots, multiplicities, poles, and weights resolved all eight, with no unresolved exceptions. Exact support-definition matches identify candidate provenance, not face identity.

## Replacement test result: rejected

In a disposable copy, `FrontFullLandTransfer.Base` was changed from `SmallHangerPocketBody` to `FrontMatchedInnerCavity`. The transfer and restricted output were recomputed (17 objects), and the two outputs were compared against freshly recomputed baseline shapes. Both candidate outputs remained valid and up-to-date, but the geometry did not match:

| Output | Baseline solids / volume | Candidate solids / volume | Symmetric-difference volume | Mesh match |
| --- | --- | --- | ---: | --- |
| `FrontFullLandTransfer` | 4 / `1093.925648 mm³` | 1 / `564.732835 mm³` | `576.468606 mm³` | No |
| `FrontFullLandTransferRestricted` | 1 / `1090.513489 mm³` | 1 / `541.284703 mm³` | `549.579811 mm³` | No |

The Boolean residuals were valid. For the restricted output, baseline-only material measured `549.420771 mm³` and candidate-only material `0.159040 mm³`. Thus the shared B-spline support definitions do not reproduce the trimmed shell geometry or its disconnected solids. The candidate was saved only in `/tmp/encoder-frontmatched-cut-test/candidate_frontmatched.FCStd` to retain the failed experiment; it was not reopened for acceptance, promoted, or added to the repository.

The earlier baseline recompute also showed that `FrontFullLandTransfer` and `FrontFullLandTransferRestricted` retained saved bounds to floating-point tolerance, while `BaseFeature003` and `Body_EncoderFacePlateLandSplit` retained volume but reported changed bounds. This is a separate coordinate/placement behavior and remains under investigation; it was not used to excuse the large, valid Boolean difference above.

## Engineering conclusion

`FrontMatchedInnerCavity` is not a safe drop-in replacement for `SmallHangerPocketBody`. The provenance result is useful for locating the surfaces, but an equivalent independent interface would need to reproduce their trimmed geometry and multi-solid topology, not just reuse the same support surfaces. Keep the existing cross-shell dependency. Do not retry this substitution or extract the encoder Bodies through it. A future approach needs a purpose-built shared interface with demonstrated exact-enough transfer geometry before downstream reconstruction is attempted.

