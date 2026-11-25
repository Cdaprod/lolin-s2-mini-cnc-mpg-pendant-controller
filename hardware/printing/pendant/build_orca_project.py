#!/usr/bin/env python3
"""Partition an OrcaSlicer single-plate project into the pendant plate plan.

The input must be an OrcaSlicer-saved project containing the eight individually
named mesh objects from build_meshes.py. The output preserves its active
printer, filament, process, object meshes, and plate transforms, while assigning
objects to six named build plates. USB cover and locators are placed apart on
their shared plate. This only edits project/package metadata and placements.
"""
from __future__ import annotations

import argparse
import copy
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET
import zipfile

# Preserve the prefixes referenced by 3MF's requiredextensions attribute.
ET.register_namespace("", "http://schemas.microsoft.com/3dmanufacturing/core/2015/02")
ET.register_namespace("BambuStudio", "http://schemas.bambulab.com/package/2021")
ET.register_namespace("p", "http://schemas.microsoft.com/3dmanufacturing/production/2015/06")

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT = Path(__file__).resolve().parent / "pendant-orcaslicer-single-plate.3mf"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "pendant-orcaslicer.3mf"
PLATES = [
    ("Front shell", ["front-shell.stl"]),
    ("Rear shell", ["rear-shell.stl"]),
    ("Display retainer", ["display-retainer.stl"]),
    ("USB cover + faceplate locators", ["usb-cover.stl", "faceplate-locator-a.stl", "faceplate-locator-b.stl"]),
    ("Fused encoder faceplate + pocket", ["encoder-faceplate-pocket-fused.stl"]),
    ("Upper faceplate", ["upper-faceplate.stl"]),
]
REQUIRED = {name for _, names in PLATES for name in names}
PLATE4_XY = {"usb-cover.stl": (117.5, 117.5),
             "faceplate-locator-a.stl": (95.0, 95.0),
             "faceplate-locator-b.stl": (140.0, 95.0)}


def read_transform(text: str) -> list[float]:
    vals = [float(v) for v in text.split()]
    if len(vals) != 12:
        raise ValueError(f"expected 12-value transform, got {text!r}")
    return vals


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = ap.parse_args()
    if not args.input.is_file():
        ap.error(f"single-plate OrcaSlicer project not found: {args.input}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.input, "r") as src:
        names = set(src.namelist())
        needed = {"3D/3dmodel.model", "Metadata/model_settings.config"}
        if not needed <= names:
            ap.error("input is not an OrcaSlicer-saved 3MF project")
        model = ET.fromstring(src.read("3D/3dmodel.model"))
        settings = ET.fromstring(src.read("Metadata/model_settings.config"))
        object_names: dict[str, str] = {}
        settings_objects: dict[str, ET.Element] = {}
        for obj in settings.findall("object"):
            oid = obj.get("id")
            meta = next((m for m in obj.findall("metadata") if m.get("key") == "name"), None)
            if oid and meta is not None:
                object_names[oid] = meta.get("value", "")
                settings_objects[oid] = obj
        by_name = {v: k for k, v in object_names.items()}
        missing = REQUIRED - by_name.keys()
        if missing:
            ap.error("input lacks named objects: " + ", ".join(sorted(missing)))

        root = settings
        old_plates = root.findall("plate")
        if len(old_plates) != 1:
            ap.error(f"expected one source plate, found {len(old_plates)}")
        old_plate = old_plates[0]
        parent = next((p for p in root.iter() if old_plate in list(p)), None)
        if parent is None:
            ap.error("could not locate plate parent")
        pos = list(parent).index(old_plate)
        parent.remove(old_plate)
        for plate_id, (label, filenames) in enumerate(PLATES, 1):
            plate = copy.deepcopy(old_plate)
            plate.find("metadata[@key='plater_id']").set("value", str(plate_id))
            plate.find("metadata[@key='plater_name']").set("value", label)
            thumb_keys = {"thumbnail_file": f"Metadata/plate_{plate_id}.png",
                          "thumbnail_no_light_file": f"Metadata/plate_no_light_{plate_id}.png",
                          "top_file": f"Metadata/top_{plate_id}.png",
                          "pick_file": f"Metadata/pick_{plate_id}.png"}
            for key, value in thumb_keys.items():
                plate.find(f"metadata[@key='{key}']").set("value", value)
            for item in list(plate.findall("model_instance")):
                plate.remove(item)
            for filename in filenames:
                oid = by_name[filename]
                orig = next((i for i in old_plate.findall("model_instance")
                             if i.find("metadata[@key='object_id']").get("value") == oid), None)
                if orig is None:
                    ap.error("object missing original plate instance: " + filename)
                inst = copy.deepcopy(orig)
                plate.append(inst)
            parent.insert(pos + plate_id - 1, plate)

        # Orca writes the standard 3MF core namespace on every model element.
        # Locate by local name so both namespaced and namespace-free packages work.
        build = next((element for element in model.iter()
                      if element.tag.rsplit("}", 1)[-1] == "build"), None)
        if build is None:
            ap.error("3MF model has no build section")
        for item in (element for element in build
                     if element.tag.rsplit("}", 1)[-1] == "item"):
            oid = item.get("objectid")
            filename = object_names.get(oid, "")
            if filename in PLATE4_XY:
                transform = read_transform(item.get("transform", ""))
                transform[9], transform[10] = PLATE4_XY[filename]
                item.set("transform", " ".join(f"{x:.9g}" for x in transform))
        # Bed placement belongs in the 3MF build-item transform. Keep Orca's
        # assemble_item transforms untouched: they describe object/assembly
        # transforms and combining both translations moves parts twice.

        model_bytes = ET.tostring(model, encoding="utf-8", xml_declaration=True)
        settings_bytes = ET.tostring(settings, encoding="utf-8", xml_declaration=True)
        with tempfile.NamedTemporaryFile(dir=args.output.parent, suffix=".3mf", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as dst:
                for name in src.namelist():
                    if name == "3D/3dmodel.model":
                        data = model_bytes
                    elif name == "Metadata/model_settings.config":
                        data = settings_bytes
                    else:
                        data = src.read(name)
                    dst.writestr(name, data)
                # Orca expects preview files for every plate. Initial copies are
                # replaced by Orca when the project is opened and saved there.
                for plate_id in range(2, len(PLATES) + 1):
                    for out_name, source_name in [
                        (f"Metadata/plate_{plate_id}.png", "Metadata/plate_1.png"),
                        (f"Metadata/plate_{plate_id}_small.png", "Metadata/plate_1_small.png"),
                        (f"Metadata/plate_no_light_{plate_id}.png", "Metadata/plate_no_light_1.png"),
                        (f"Metadata/top_{plate_id}.png", "Metadata/top_1.png"),
                        (f"Metadata/pick_{plate_id}.png", "Metadata/pick_1.png"),
                    ]:
                        if source_name in names:
                            dst.writestr(out_name, src.read(source_name))
            tmp_path.replace(args.output)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise
    print(f"Wrote {args.output} with {len(PLATES)} plates and {len(REQUIRED)} distinct meshes")


if __name__ == "__main__":
    main()
