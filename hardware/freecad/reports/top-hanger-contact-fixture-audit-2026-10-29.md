# Top-hanger contact-fixture audit

Date: 2026-10-29 (local)  
Branch: `hardware-integration`  
Source: `hardware/freecad/pendant.FCStd`  
Source SHA-256: `dc2aeddf7be327c73022a1dc053bf8a27d5cf476e9cd68468a4ee73ab8264881`

## Method

Ran `scripts/audit_hanger_contact_fixture.py` in a separate FreeCAD 1.1.1 `FreeCADCmd` process. It opened the source read-only, calculated the saved material removed by each active hanger Pocket from its BaseFeature and Pocket shapes, then intersected that cut volume and the final shell Body with the saved `Body_HookReference` shape. The document was not recomputed or saved; the source checksum remained unchanged.

## Findings

The helper Body is labeled `Body_HookReference (validation only)` and its Tip is `HookReferenceSolid`, labeled “Hook Reference — 2 mm Steel.” Its cached shape is one valid solid, volume `4828 mm³`, bounds X `[-17,17]`, Y `[55.5,79.5]`, Z `[-36,0]` mm.

| Shell | Active hanger Pocket base | Removed cut volume (mm³) | Helper overlap with cut volume (mm³) | Helper overlap with saved shell (mm³) |
|---|---|---:|---:|---:|
| Front | `PreserveOriginalFrontExterior` | 964.0672 | 0 | 1084.2444 |
| Rear | `USBConformalCoverSeatBody002` | 929.4303 | 0 | 2612.6610 |

The saved helper does not occupy either hanger cutout, and it intersects material in both saved shell Bodies. It therefore cannot serve as a fit/contact fixture in its current saved position.

## Interpretation

This is evidence about the **validation-only CAD helper**, not the actual steel bracket shown in the user's photos. It does not prove the physical bracket fails to fit, nor does it validate load capacity. It means the CAD currently lacks a correctly placed, verified model of the physical hanger/bracket engagement. Treat the real contact surface as unverified until the actual mating geometry and dimensions are established and checked against freshly recomputed shell features.

The design target remains a closed opening through both shell Bodies, printed in PLA with both shells flat on their broad faces, and a physical proof load of 5× complete assembled weight. The complete assembled mass is still unknown.
