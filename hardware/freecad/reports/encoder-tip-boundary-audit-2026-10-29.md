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
