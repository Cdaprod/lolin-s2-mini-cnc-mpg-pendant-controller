"""Compare cached shell shapes near the closed hanger opening.

Run inside FreeCAD 1.1+ (for example, with FreeCADCmd and a macro that execs
this file). This bounded audit clips each stored base/output shape to two
regions around the hanger and compares the clipped solids with valid Boolean
differences. It does not recompute or save the document. Results describe
stored shapes only, not strength or a freshly recomputed feature history.

Set PENDANT_FCSTD to select a disposable candidate and PENDANT_AUDIT_JSON to
write the result to a file. Otherwise the script locates the repository's
hardware/freecad/pendant.FCStd from its path or the current working directory.
"""

import hashlib
import json
import os

import FreeCAD as App
import Part


SCRIPT_FILE = globals().get("__file__", "")
SCRIPT_DIR = (
    os.path.dirname(os.path.abspath(SCRIPT_FILE))
    if SCRIPT_FILE
    else os.getcwd()
)
DEFAULT_CANDIDATES = (
    os.path.normpath(os.path.join(SCRIPT_DIR, "..", "pendant.FCStd")),
    os.path.join(os.getcwd(), "hardware", "freecad", "pendant.FCStd"),
    os.path.join(os.getcwd(), "pendant.FCStd"),
)
DEFAULT_DOCUMENT = next(
    (candidate for candidate in DEFAULT_CANDIDATES if os.path.isfile(candidate)),
    DEFAULT_CANDIDATES[0],
)
DOCUMENT_PATH = os.path.realpath(os.environ.get("PENDANT_FCSTD", DEFAULT_DOCUMENT))
if not os.path.isabs(DOCUMENT_PATH):
    DOCUMENT_PATH = os.path.realpath(os.path.join(os.getcwd(), DOCUMENT_PATH))
OUTPUT_PATH = os.environ.get("PENDANT_AUDIT_JSON")

# Box coordinates are global model coordinates, in millimeters. The broader
# region includes the top of the shell wall around the hole; the narrow region
# isolates the current nominal slot envelope (Y=80.5..83.5 mm) with tolerance.
REGIONS = (
    ("hanger_annulus", -20.0, 78.0, -37.0, 40.0, 10.0, 38.0),
    ("upper_slot_band", -19.0, 80.4, -37.0, 38.0, 3.2, 38.0),
)
FEATURE_PAIRS = (
    ("front", "FrontFullWidthReceiver", "FrontBossToWallLoadPaths"),
    ("rear", "Body002FullWidthSeat", "RearBossToWallLoadPaths"),
)

if not os.path.isfile(DOCUMENT_PATH):
    raise RuntimeError("FreeCAD document not found: %s" % DOCUMENT_PATH)

with open(DOCUMENT_PATH, "rb") as source_file:
    source_sha256 = hashlib.sha256(source_file.read()).hexdigest()

doc = App.openDocument(DOCUMENT_PATH)
try:
    region_records = []
    for name, x, y, z, dx, dy, dz in REGIONS:
        box = Part.makeBox(dx, dy, dz, App.Vector(x, y, z))
        region = {
            "name": name,
            "bbox_mm": [x, x + dx, y, y + dy, z, z + dz],
            "comparisons": [],
        }
        for side, base_name, feature_name in FEATURE_PAIRS:
            base_obj = doc.getObject(base_name)
            feature_obj = doc.getObject(feature_name)
            if base_obj is None or feature_obj is None:
                raise RuntimeError(
                    "Missing source feature(s): %s / %s"
                    % (base_name, feature_name)
                )
            base_shape = base_obj.Shape.common(box)
            feature_shape = feature_obj.Shape.common(box)
            comparison = {
                "side": side,
                "base_feature": base_name,
                "loadpath_feature": feature_name,
                "base_clipped_valid": bool(base_shape.isValid()),
                "loadpath_clipped_valid": bool(feature_shape.isValid()),
                "base_clipped_solid_count": len(base_shape.Solids),
                "loadpath_clipped_solid_count": len(feature_shape.Solids),
                "base_clipped_volume_mm3": float(base_shape.Volume),
                "loadpath_clipped_volume_mm3": float(feature_shape.Volume),
            }
            added = feature_shape.cut(base_shape)
            removed = base_shape.cut(feature_shape)
            comparison.update(
                {
                    "feature_only_valid": bool(added.isValid()),
                    "base_only_valid": bool(removed.isValid()),
                    "feature_only_volume_mm3": float(added.Volume),
                    "base_only_volume_mm3": float(removed.Volume),
                    "symmetric_difference_volume_mm3": float(
                        added.Volume + removed.Volume
                    ),
                }
            )
            region["comparisons"].append(comparison)
        region_records.append(region)

    result = {
        "schema_version": 1,
        "document": os.path.relpath(DOCUMENT_PATH, os.getcwd()),
        "source_sha256": source_sha256,
        "freecad_version": list(App.Version()),
        "recomputed": False,
        "saved": False,
        "method": "Clip stored base and feature shapes to bounded regions, then compare with Boolean differences.",
        "interpretation_limit": "Zero local difference means no cached material change in the tested boxes. It does not rule out remote load transfer, establish global equivalence, validate recomputation, or prove strength.",
        "regions": region_records,
    }
finally:
    App.closeDocument(doc.Name)

serialized = json.dumps(result, indent=2, sort_keys=True)
if OUTPUT_PATH:
    with open(OUTPUT_PATH, "w") as output_file:
        output_file.write(serialized + "\n")
else:
    print(serialized)
