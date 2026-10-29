# Encoder handoff Tip-boundary audit

Date: 2026-10-29  
Source inspected read-only: `hardware/freecad/pendant-encoder-fused-working.FCStd`  
No CAD files were modified.

## Result

The saved encoder handoff is not a small standalone encoder source. It contains 819 objects and 35 PartDesign Bodies. Its two current encoder Bodies have separate saved Tips, but both Tip-rooted dependency manifests show substantial active links to other Bodies and construction history:

| Active Body | Saved Tip | Expanded dependency objects | Boundary-crossing edges | Sketch external refs |
| --- | --- | ---: | ---: | ---: |
| `Body_EncoderFacePlate` | `EncoderFaceplateReceiverM2Hole` | 183 | 68 | 29 |
| `Body_EncoderPocket` | `EncoderPocketShellM2Hole` | 183 | 68 | 29 |

These counts come from the existing serialized-dependency audit. They describe each root separately and must not be summed as a unique-object total. The audit follows saved Tip dependencies and serialized Sketcher external geometry; it does not prove runtime shape validity or recomputation.

## Cross-component paths that prevent separate extraction

The faceplate Tip reaches into the pocket split through `EncoderFaceplateReceiverM2Binder.Support → EncoderPocketSliceZ0.Solid2`. Its downstream land-transfer chain also reaches `FrontFullLandTransfer.Base → SmallHangerPocketBody`, so the saved faceplate still consumes front-shell construction geometry.

The pocket Tip reaches back into the faceplate through `EncoderFaceplateRetentionKeep.Base → Body_EncoderFacePlateLandSplit` and `EncoderCaptureLipTransfer.Base/Tool → EncoderCaptureLedge / EncoderCrownGlassBackClearance`. It also reaches `Body003` through `EncoderFaceplateSource.BaseFeature → EncoderNutReliefs`, and the front shell through `FrontOriginalMatingLand.Support → SmallHangerPocketBody`.

Thus the two encoder parts are coupled to each other and also to front-shell and upper-faceplate construction. Treating each current Body as independently extractable would leave unresolved upstream geometry. Copying the whole closure or rerunning the prior 60-expression redirection would repeat a known unstable approach: the earlier `FaceplateThickness` 2.5 → 2.6 mm experiment split the pocket into two solids and did not restore the one-solid state when returned to 2.5 mm.

## Next extraction gate

Do not attempt another recursive copy from these Body roots yet. First identify the smallest coherent interface that severs the reciprocal encoder slice/retention dependencies and the front-shell/upper-faceplate construction paths. Any candidate interface must be independent of both shells and the upper-faceplate Body, preserve the source coordinate frames and generated subelement consumers, and keep local dimensions local unless a master-driven change passes a reversible full-feature test.

The complete machine-readable manifests are `encoder-faceplate-tip-boundary-manifest.json` and `encoder-pocket-tip-boundary-manifest.json`. They preserve the object/property edges, subelements, sketch references, and active Tip paths for a later targeted cut analysis.

## Pocket-shell split-boundary experiment (2026-10-29)

The serialized and runtime audits show a likely component-boundary error in the saved encoder handoff:

* `EncoderPocketSliceZ0.Base` is `RC16NativeFaceplateWithLand` and its `Tools` contains `EncoderPocketShellReleaseNoFaceplateRetention`.
* The slice result is two valid solids: `Solid1` is 3,506.1080 mm³, 36 faces, bounds `(-60, -89.4782, -27.5)` to `(60, -13.4854, 2.5)`; `Solid2` is 11,102.5437 mm³, 83 faces, bounds `(-39.9097, -88.6191, -19)` to `(39.8792, -4.7424, 0.8)`.
* `EncoderFaceplateReceiverM2Binder.Support` explicitly selects `EncoderPocketSliceZ0.Solid2`, while `EncoderPocketShellM2Binder.Support` selects the entire split result (no subelement).
* Consequently the saved `Body_EncoderPocket` Tip contains two solids and has 14,607.6999 mm³ volume. Its second solid is the faceplate-receiver partition also represented by `Body_EncoderFacePlate`; the pocket Body's support is not scoped to the pocket shell.

A disposable in-memory candidate redirected only `EncoderPocketShellM2Binder.Support` to the existing native one-solid `EncoderPocketShellReleaseNoFaceplateRetention` feature. The binder, Hole, and `Body_EncoderPocket` each recomputed to a valid, up-to-date one-solid shape of 3,529.3816 mm³, 28 faces, and bounds `(-60, -89.4782, -27.5)` to `(60, -13.4854, 2.5)`. The Hole output matched its source release feature within 0.000007 mm³, indicating the three 2.2 mm pilot bores are already present in the release geometry and the downstream 1.6 mm Hole removes no further material. This is evidence that the current two-solid binder can be replaced with a direct pocket-shell source without a generated `Solid1`/`Solid2` selector; it is not yet an accepted production repair.

On the saved shapes, the native release shell and the faceplate Body Tip have zero common volume and a minimum distance of 0 mm. This supports a touching, non-interfering mating boundary for the current saved shapes; it does not establish contact area or printable tolerance. The direct release shell preserves about 23.27 mm³ that lies outside the faceplate base and would be lost by selecting only the split's common `Solid1`.

The candidate was not saved, extracted, or integrated. Its scoped binder/Hole/Body recompute returned 52 document-level errors, including known suppressed/history and cross-scope warnings, although the three targeted objects were valid and up-to-date. A separate exploratory full recompute on the Solid1-only variant returned 163 errors and took 219 seconds, exceeding the repository's recommended 180-second bound; do not repeat that broad recompute. No save/reopen test was performed for the changed candidate. Therefore the candidate does not pass the migration promotion gate.

The direct release feature still depends on `EncoderFaceplateRetentionKeep` (through its `Tool`) and on the existing pocket-wall hole feature (through its `Base`). The front-shell and faceplate construction paths therefore remain in the transitive dependency graph. Next, audit the exact geometry and constraints consumed by `EncoderFaceplateRetentionKeep` and confirm the pocket-wall pilot positions/diameters, then test a disposable candidate save/reopen before considering extraction. Keep the production handoff, modular assembly, master, and static interim assembly representations unchanged until those checks pass.
