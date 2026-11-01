"""Check whether the saved validation-only hook shape occupies the hanger cuts.

Run inside FreeCAD 1.1+ (for example, with FreeCADCmd and a macro that execs
this file). The script compares the saved ``Body_HookReference`` shape with
the material removed by the two active hanger Pocket features and with each
saved shell Body. It does not recompute or save the document. The helper is
labeled validation-only, so a mismatch does not prove that the user's actual
wall bracket fails to fit.

Set PENDANT_FCSTD to select a disposable candidate and PENDANT_AUDIT_JSON to
write results to a file. Otherwise the repository monolith is located from
the script path or current working directory.
"""

import hashlib
import json
import os

import FreeCAD as App


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

HOOK_BODY = "Body_HookReference"
POCKETS = (
    ("front", "Body", "SmallHangerPocketBody"),
    ("rear", "Body002", "SmallHangerPocketBody002"),
)


def _shape_record(shape):
    box = shape.BoundBox
    return {
        "valid": bool(shape.isValid()),
        "solid_count": len(shape.Solids),
        "volume_mm3": float(shape.Volume),
        "bbox_mm": [
            float(box.XMin),
            float(box.XMax),
            float(box.YMin),
            float(box.YMax),
            float(box.ZMin),
            float(box.ZMax),
        ],
    }


if not os.path.isfile(DOCUMENT_PATH):
    raise RuntimeError("FreeCAD document not found: %s" % DOCUMENT_PATH)
with open(DOCUMENT_PATH, "rb") as source_file:
    source_sha256 = hashlib.sha256(source_file.read()).hexdigest()

doc = App.openDocument(DOCUMENT_PATH)
try:
    hook_body = doc.getObject(HOOK_BODY)
    if hook_body is None:
        raise RuntimeError("Missing helper Body: %s" % HOOK_BODY)
    hook_shape = hook_body.Shape
    result_rows = []
    for side, body_name, pocket_name in POCKETS:
        body = doc.getObject(body_name)
        pocket = doc.getObject(pocket_name)
        if body is None or pocket is None or pocket.BaseFeature is None:
            raise RuntimeError("Incomplete %s shell/pocket chain" % side)
        removed_volume = pocket.BaseFeature.Shape.cut(pocket.Shape)
        final_overlap = hook_shape.common(body.Shape)
        cut_overlap = hook_shape.common(removed_volume)
        result_rows.append(
            {
                "side": side,
                "shell_body": body_name,
                "active_pocket": pocket_name,
                "pocket_base_feature": pocket.BaseFeature.Name,
                "shell_cached_shape": _shape_record(body.Shape),
                "pocket_removed_volume_shape": _shape_record(removed_volume),
                "fixture_overlap_with_shell_mm3": float(final_overlap.Volume),
                "fixture_overlap_with_pocket_cut_mm3": float(cut_overlap.Volume),
            }
        )

    result = {
        "schema_version": 1,
        "document": os.path.relpath(DOCUMENT_PATH, os.getcwd()),
        "source_sha256": source_sha256,
        "freecad_version": list(App.Version()),
        "recomputed": False,
        "saved": False,
        "fixture": {
            "body": HOOK_BODY,
            "label": hook_body.Label,
            "tip": hook_body.Tip.Name if hook_body.Tip else None,
            "cached_shape": _shape_record(hook_shape),
        },
        "shell_checks": result_rows,
        "interpretation_limit": "This checks the saved validation-only helper, not the actual physical bracket. Cached geometry, overlap, or zero overlap is not a strength or fit certification.",
    }
finally:
    App.closeDocument(doc.Name)

serialized = json.dumps(result, indent=2, sort_keys=True)
if OUTPUT_PATH:
    with open(OUTPUT_PATH, "w") as output_file:
        output_file.write(serialized + "\n")
else:
    print(serialized)
