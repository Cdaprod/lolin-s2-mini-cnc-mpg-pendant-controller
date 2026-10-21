# Vendor and Created Models

Keep third-party CAD footprints and STEP models on the `hardware/kicad` Git branch, under `hardware/models/vendor/`.
Keep original FreeCAD/STEP design outputs under `hardware/models/created/`.

For each vendor model, record:

| File | Manufacturer | Part number | Source URL | License | Units | SHA-256 | Retrieved (UTC) | Notes |
|---|---|---|---|---|---|---|---|---|

Do not commit third-party assets if their licensing prohibits redistribution. Link the upstream source instead. Prefer lightweight native STEP files or reproducible download scripts; do not add huge duplicate exports. Verify the model's dimensions against the part datasheet before constraining enclosure geometry.
