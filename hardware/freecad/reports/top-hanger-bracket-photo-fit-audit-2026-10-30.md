# Top hanger: wall-bracket photo fit audit

Date: 2026-10-30  
Branch: `hardware-integration`  
Source CAD: `hardware/freecad/pendant.FCStd`  
Source SHA-256: `dc2aeddf7be327c73022a1dc053bf8a27d5cf476e9cd68468a4ee73ab8264881`

## User-confirmed requirements

- The hanger opening is closed and passes through both shell Bodies.
- It must carry the pendant's weight; design proof target is 5× complete pendant weight.
- Material: PLA.
- Shells print flat on their broad faces.
- Preserve the existing modularization work and use the original monolith as the geometry baseline.

The complete assembled mass is not yet recorded, so the proof load cannot yet be converted to a force.

## Photo-derived bracket envelope (approximate)

The three user photos show a wall-mounted steel hanger bracket with a vertical mounting plate, two upper fasteners, and a projecting lower ledge. Approximate image measurements, calibrated against visible ruler marks, are:

| Bracket detail | Photo estimate | Confidence / limitation |
|---|---:|---|
| Vertical plate width | about 29–30 mm | Moderate; ruler is in the same image plane, with perspective |
| Fastener center spacing | about 14 mm | Low to moderate; screw centers are visually estimated |
| Vertical plate height above ledge | about 25 mm | Low; photo perspective and the ledge boundary obscure the datum |
| Ledge projection from plate | about 18–20 mm | Low; side photo has oblique perspective |
| Metal thickness | Not established | The photos do not provide a reliable edge-on measurement |

These values describe only a rough envelope. They are not manufacturing dimensions and must not be used as final sketch constraints without measuring the physical bracket directly.

## Comparison with saved CAD

The active paired shell openings are fully constrained obround profiles measuring 35.6 × 3.0 mm, centered at global Y=81 mm, with X bounds ±17.8 mm. The nominal 35.6 mm span exceeds the photo-estimated 29–30 mm plate width by roughly 5.6–6.6 mm total. The 3.0 mm slot height cannot be declared a fit until the bracket feature that actually enters it and its thickness are measured, its insertion direction is established, and print clearance is specified.

The current saved `Body_HookReference` is explicitly labeled validation-only. Its 34 × 24 × 36 mm bounding box is not a verified representation of the photographed bracket. The previous read-only contact audit found it has zero overlap with either active hanger cut volume and overlaps material in the saved shell shapes. That only rejects this helper as a current fit fixture; it does not show that the real bracket fails to fit.

The opening's through-Z cut direction and paired shell cuts must be compared with the bracket's ledge engagement direction in a common assembly coordinate frame. The photographs suggest a ledge-style support, but do not establish the exact insertion path or contact faces. No fit or load-capacity claim is made.

## Structural and validation status

The saved active opening is a 35.6 × 3.0 mm obround through both shell Bodies. Earlier sparse sections found local residual material as low as approximately 0.164 mm front and 0.240 mm rear near its upper edge; those are diagnostic samples from saved geometry, not a complete wall-thickness map or stress analysis. A previous 3.1 mm candidate did not propagate through stored generic load-path features to the final Tips and was rejected.

No geometry was changed for this audit. No candidate has passed full native downstream recomputation, save/reopen validation, bracket contact validation, or a 5× load assessment. PLA strength also depends on print process, orientation, temperature, aging, and stress concentration; geometry inspection alone cannot certify the requested proof load.

## Next engineering steps

1. Obtain or measure bracket metal thickness, exact lip width/projection, plate dimensions, and the intended insertion path.
2. Record the complete pendant mass and convert 5× mass to a proof force.
3. Build an accurately placed bracket fixture in a disposable CAD candidate and verify contact/clearance against both freshly recomputed shell Tips.
4. Restore a trustworthy regeneration path from the active hanger pockets through both shell Tips before any opening or reinforcement change.
5. Evaluate a closed reinforced load path across both shells, maintaining screw-seat clearance and manufacturable PLA walls; validate geometry and load assumptions before promotion.

