# Manufacturing Body dependency boundary audit

Date: 2026-10-30
Branch: `hardware-integration`
Source: `hardware/freecad/pendant.FCStd`
Source SHA-256: `dc2aeddf7be327c73022a1dc053bf8a27d5cf476e9cd68468a4ee73ab8264881`

## Purpose and method

This read-only audit roots reachability at each selected manufacturing Body's active Tip and combines serialized object/property links with Sketcher external-geometry references. It filters references by physical Body ownership. FreeCAD helper objects can have no manufacturing Body owner, so those rows are separately labeled as root-Tip-context inferences; they are boundary candidates, not direct owner-to-owner proof. Datum/origin ownership is propagated through Body Origin links and hidden Origin group properties. Ordinary feature dependency closure counts remain diagnostic and are not extraction-readiness verdicts.

The machine-readable output is `manufacturing-body-boundaries-2026-10-30.json`. Reproduce it with:

```sh
python3 hardware/freecad/scripts/audit_manufacturing_body_boundaries.py \
  hardware/freecad/pendant.FCStd \
  --json /tmp/manufacturing-body-boundaries.json
```

## Results

| Manufacturing Body | Active Tip | Expanded closure | Boundary-candidate records |
|---|---|---:|---:|
| `Body` (front shell) | `RestoreUpperFaceplateHoles` | 129 | 5 |
| `Body002` (rear shell) | `RearBossWallRamps45` | 166 | 8 |
| `Body003` (upper faceplate) | `Body003FullWidthSeat` | 200 | 26 |
| `Body_EncoderFacePlate` | `EncoderFaceplateReceiverM2Hole` | 183 | 34 |
| `Body_EncoderPocket` | `EncoderPocketShellM2Hole` | 183 | 40 |

The front Tip reaches rear-owned `WidthControlled_RearMatchedProfile0` through `RearFullLandProfile0.Support` and `RearFullLandProfile1.Support`. It also reaches the upper-faceplate outline through `FrontFullLandProfile0/1.Support`; those are helper-context records because the profile binders themselves are owned by the helper Body `FrontFullLandCutter`.

The rear Tip has an active `RearFullLandTransfer.Base → SmallHangerPocketBody` dependency into the front shell. It also reaches front-owned `Sketch020` through `RearScrewAlignmentBinder.Support`. `Binder016.Support → Sketch019` remains in the reachable object closure but its path includes suppressed historical Pads, so it is explicitly marked historical/suppressed-path rather than treated as an active manufactured-shape input. The audit also identifies helper-mediated references to front/rear envelope and USB-seat construction; see the JSON paths and source properties before selecting any replacement.

The upper faceplate and encoder Bodies retain multiple cross-Body dependencies. Their inflated record totals include helper-context links, shared features and Sketcher references; these totals should not be compared with extraction closure counts as though every row were a unique feature or a direct physical interface.

## Validation and limits

- Both audit scripts pass `py_compile`.
- Synthetic ownership checks cover same-Body references (excluded), direct cross-Body links, helper-context links, and in-Body/root-only links.
- The complete five-Body audit ran against the checksum-identified monolith and did not modify any CAD document.
- This report changes no CAD geometry and makes no claim that any additional Body is ready for extraction. The rear shell remains blocked by its active land-transfer dependency; the front shell still depends on rear/upper-faceplate profile inputs.
