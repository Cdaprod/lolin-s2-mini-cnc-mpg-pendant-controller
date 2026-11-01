"""Read-only metadata audit for the pendant's hanger-related feature history.

Run inside FreeCAD 1.1+ with ``exec(open(path).read())`` or through a small
FreeCADCmd macro. The document is opened for inspection only: this script does
not recompute, modify, or save it. Set ``PENDANT_FCSTD`` to audit a disposable
candidate instead of the repository's authoritative monolith. Set
``PENDANT_AUDIT_JSON`` to write the JSON result to a file; otherwise it is
printed to stdout.
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

FEATURE_NAMES = (
    "FrontBossToWallLoadPaths",
    "RearBossToWallLoadPaths",
    "RearBossShoulderTransitions",
    "FrontHighToLowTransitions",
    "RearBossWallRamps45",
)
SKETCH_NAME_TOKENS = (
    "hanger",
    "supporttransition",
    "boss",
    "loadpath",
    "wallramp",
)


def _object_names(values):
    result = []
    for value in values or []:
        result.append(getattr(value, "Name", str(value)))
    return result


def _owners(doc, obj):
    return [
        parent.Name
        for parent in doc.Objects
        if obj in getattr(parent, "Group", [])
    ]


def _shape_metadata(obj):
    shape = getattr(obj, "Shape", None)
    if shape is None or shape.isNull():
        return {"null": True}
    box = shape.BoundBox
    return {
        "is_valid_cached_shape": bool(shape.isValid()),
        "solid_count_cached_shape": len(shape.Solids),
        "volume_mm3_cached_shape": float(shape.Volume),
        "face_count_cached_shape": len(shape.Faces),
        "edge_count_cached_shape": len(shape.Edges),
        "vertex_count_cached_shape": len(shape.Vertexes),
        "bbox_mm_cached_shape": [
            float(box.XMin),
            float(box.XMax),
            float(box.YMin),
            float(box.YMax),
            float(box.ZMin),
            float(box.ZMax),
        ],
    }


def _property(obj, name):
    if name not in obj.PropertiesList:
        return None
    value = getattr(obj, name)
    if name in ("BaseFeature", "Profile", "Support", "AttachmentSupport"):
        if isinstance(value, (tuple, list)):
            return [
                _object_names(item) if isinstance(item, (tuple, list)) else
                getattr(item, "Name", str(item))
                for item in value
            ]
        return getattr(value, "Name", str(value))
    if isinstance(value, (tuple, list)):
        return list(value)
    return str(value)


def _feature_record(doc, name):
    obj = doc.getObject(name)
    if obj is None:
        return {"name": name, "missing": True}

    properties = {}
    for prop in (
        "BaseFeature",
        "Profile",
        "Support",
        "AttachmentSupport",
        "MapMode",
        "Placement",
        "Length",
        "Suppressed",
        "RegenerationScript",
        "RegenerationMethod",
        "DesignNote",
        "SourceEdges",
    ):
        if prop in obj.PropertiesList:
            properties[prop] = _property(obj, prop)

    return {
        "name": obj.Name,
        "label": obj.Label,
        "type_id": obj.TypeId,
        "owners": _owners(doc, obj),
        "saved_state_flags": list(obj.State),
        "properties": properties,
        "shape": _shape_metadata(obj),
    }


def _sketch_record(doc, obj):
    geometry = []
    constraints = []
    try:
        geometry = [str(item) for item in obj.Geometry]
        constraints = [
            {
                "index": index,
                "type": constraint.Type,
                "value": getattr(constraint, "Value", None),
                "first": getattr(constraint, "First", None),
                "second": getattr(constraint, "Second", None),
                "third": getattr(constraint, "Third", None),
            }
            for index, constraint in enumerate(obj.Constraints)
        ]
    except Exception as error:
        geometry = ["inspection error: %s" % error]
    return {
        "name": obj.Name,
        "label": obj.Label,
        "owners": _owners(doc, obj),
        "saved_state_flags": list(obj.State),
        "geometry": geometry,
        "constraints": constraints,
        "fully_constrained": getattr(obj, "FullyConstrained", None),
        "degrees_of_freedom": getattr(obj, "DoF", None),
    }


if not os.path.isfile(DOCUMENT_PATH):
    raise RuntimeError("FreeCAD document not found: %s" % DOCUMENT_PATH)

with open(DOCUMENT_PATH, "rb") as document_file:
    source_sha256 = hashlib.sha256(document_file.read()).hexdigest()

doc = App.openDocument(DOCUMENT_PATH)
try:
    records = []
    related_sketches = []
    for name in FEATURE_NAMES:
        records.append(_feature_record(doc, name))

    for obj in doc.Objects:
        if "Sketcher::SketchObject" not in obj.TypeId:
            continue
        text = (obj.Name + " " + obj.Label).lower()
        if any(token in text for token in SKETCH_NAME_TOKENS):
            related_sketches.append(_sketch_record(doc, obj))

    result = {
        "schema_version": 1,
        "document": os.path.relpath(DOCUMENT_PATH, os.getcwd()),
        "source_sha256": source_sha256,
        "freecad_version": list(App.Version()),
        "method": "Read-only document inspection; no recompute or save performed.",
        "shape_caveat": "Shape validity and metrics describe stored cached shapes only; they are not recomputation or strength evidence.",
        "features": records,
        "related_sketches": related_sketches,
    }
finally:
    App.closeDocument(doc.Name)

serialized = json.dumps(result, indent=2, sort_keys=True, default=str)
if OUTPUT_PATH:
    with open(OUTPUT_PATH, "w") as output_file:
        output_file.write(serialized + "\n")
else:
    print(serialized)
