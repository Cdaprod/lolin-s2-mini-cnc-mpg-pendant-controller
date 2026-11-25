# Encoder Tip interface-cut map

Date: 2026-10-29  
Branch: `hardware-integration`  
Scope: read-only graph analysis of the saved encoder work candidate. No CAD document was modified.

## Source and method

The analysis consumes the two existing Tip-rooted JSON manifests for `pendant-encoder-fused-working.FCStd` (SHA-256 `c20e68fcc2a17782a37aecc9eac1ae7388192e94479077532331948ac01a6d30`). It deduplicates active boundary edges by source, property, target, subelement, and Tip path. It does not recompute geometry or prove physical equivalence. The categories in the machine-readable output are name-based triage only.

Recreate the map with:

```sh
python3 hardware/freecad/scripts/analyze_encoder_interface_cut.py \
  --json hardware/freecad/reports/encoder-interface-cut-map.json
```

## Findings

| Tip root | Expanded closure | Active boundary edges | Sketch external refs | Readiness |
|---|---:|---:|---:|---|
| `Body_EncoderFacePlate.EncoderFaceplateReceiverM2Hole` | 183 | 68 | 29 | BLOCKED |
| `Body_EncoderPocket.EncoderPocketShellM2Hole` | 183 | 68 | 29 | BLOCKED |

The two roots share **67 of their 68** deduplicated boundary-edge tuples. The sole root-specific edge for each is its final binder support:

- Faceplate: `EncoderFaceplateReceiverM2Binder.Support → EncoderPocketSliceZ0.Solid2`.
- Pocket: `EncoderPocketShellM2Binder.Support → EncoderPocketSliceZ0`.

This confirms that changing only the final split/binder selector cannot separate the two native histories. Nearly the entire boundary graph is common upstream construction, not two independent feature trees with a small shared split operation.

The common upstream boundary includes three distinct architectural regions:

1. **Faceplate/pocket reciprocal interface.** `EncoderFaceplateRetentionKeep.Base → Body_EncoderFacePlateLandSplit`, the `EncoderCaptureLipTransfer` base/tool pair, `EncoderPocketSourceBase.BaseFeature → Body_EncoderFacePlateFullWidthSeat`, and `EncoderShellTrimTool.Base → EncoderFaceplateSplitProfile`. These define real complementary retention and shell geometry.
2. **Front-shell construction inheritance.** The land-transfer chain reaches `FrontFullLandTransfer.Base → SmallHangerPocketBody`; the faceplate source also reaches `EncoderNutReliefs` in `Body003`. These are generated shell/faceplate construction inputs, not just a parameter link.
3. **Shared construction controls.** Envelope, hardware, seam, and pendant parameter objects plus their dependent profiles occur in the common closure. Their presence is not evidence that all should become master geometry; each needs a geometric-role and placement audit before rewiring.

The prior pocket-shell focused experiment remains a useful narrow hypothesis: supporting the pocket binder from `EncoderPocketShellReleaseNoFaceplateRetention` produced a valid one-solid target Body after save/reopen and reduced the measured candidate closure by four expanded objects. That candidate also reported 52 document-level errors in its scoped validation and remained transitively coupled to the faceplate and shell histories; it is therefore not promoted or counted as an accepted component boundary.

## Saved-shape interface inventory

A read-only FreeCADCmd probe loaded the same encoder candidate without recomputing or saving it. `EncoderFaceplateRetentionKeep` is a valid saved five-solid, 313.2627 mm³ tool with 62 faces: 45 B-spline, 6 cylindrical, and 11 planar. Its base is `Body_EncoderFacePlateLandSplit` (one solid, 300.1436 mm³, 40 faces: 33 B-spline, 2 cylindrical, 5 planar); its tool is `EncoderCaptureLipTransfer` (four solids, 13.0788 mm³, 22 faces: 12 B-spline, 4 cylindrical, 6 planar), whose inputs are `EncoderCaptureLedge` and `EncoderCrownGlassBackClearance`. The pocket-side `EncoderPocketShellReleaseNoFaceplateRetention` is a valid saved one-solid, 3,529.3816 mm³ shape with 28 faces.

This confirms that the reciprocal dependency supplies actual retention and clearance material, rather than an inert link. The high B-spline face count also means a compact sketch replacement is not established by these measurements. The probe describes saved shapes only; it did not recompute the document and does not prove equivalence after reconstruction. Reproduce it with `scripts/probe_shape_surface_families.py`; the raw per-face-family counts, bounds, volumes, object links, FreeCAD version, and source SHA are in `encoder-retention-interface-surface-inventory.json`.

The subsequent saved-shape surface provenance trace narrows one input: 90 B-spline support definitions in `FrontFullLandTransferRestricted` first appear in `FrontMatchedInnerCavity`, while 32 are associated with the loft cutter. This is a bounded replacement hypothesis only; no Base substitution has passed geometry comparison. See `encoder-land-transfer-provenance.md` and its machine-readable record.

## Engineering implication

The immediate encoder blocker is not the 110-face `SmallHangerPocketBody` alone, nor the two final binder supports. It is the broader shared upstream graph. A safe standalone encoder boundary needs a coordinated interface for the receiver/shell, retention keepout/capture lip, and front-shell land/nut-relief inputs. The current data does not establish that these can be reduced to a compact master sketch or datum without changing the native history.

Next work should select one physically meaningful interface source at a time, record its consumed subelements and coordinate frame, then test a disposable reconstruction with its immediate downstream consumers. Do not retry recursive extraction or promote the binder-only pocket candidate until the feature errors are understood and the boundary graph shows a meaningful reduction.

## Artifacts

- `encoder-interface-cut-map.json`: normalized active boundary edges and source hashes for both Tips.
- `scripts/analyze_encoder_interface_cut.py`: deterministic map generator.
- Existing source manifests and geometry caveats: `encoder-tip-boundary-audit-2026-10-29.md`.
