#!/usr/bin/env python3
"""Validate the pendant Orca 3MF plate inventory and printer-bed placements."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

HERE = Path(__file__).resolve().parent
PROJECT = HERE / "pendant-orcaslicer.3mf"
MANIFEST = HERE / "meshes/mesh-manifest.json"
EXPECTED = {
    "Front shell": ["front-shell.stl"],
    "Rear shell": ["rear-shell.stl"],
    "Display retainer": ["display-retainer.stl"],
    "USB cover + faceplate locators": ["usb-cover.stl", "faceplate-locator-a.stl", "faceplate-locator-b.stl"],
    "Fused encoder faceplate + pocket": ["encoder-faceplate-pocket-fused.stl"],
    "Upper faceplate": ["upper-faceplate.stl"],
}
CORE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
PROD = "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
NS = {"c": CORE}


def metadata(element: ET.Element) -> dict[str, str]:
    return {m.get("key", ""): m.get("value", "") for m in element.findall("metadata")}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", type=Path, default=PROJECT)
    ap.add_argument("--manifest", type=Path, default=MANIFEST)
    args = ap.parse_args()
    manifest = json.loads(args.manifest.read_text())
    parts = {p["filename"]: p for p in manifest["parts"]}
    errors: list[str] = []
    warnings: list[str] = []
    with zipfile.ZipFile(args.project) as z:
        settings = ET.fromstring(z.read("Metadata/model_settings.config"))
        project = json.loads(z.read("Metadata/project_settings.config"))
        model = ET.fromstring(z.read("3D/3dmodel.model"))
        obj_names = {
            o.get("id"): metadata(o).get("name", "")
            for o in settings.findall("object")
        }
        by_name = {name: oid for oid, name in obj_names.items()}
        plates = settings.findall("plate")
        plate_map: dict[str, list[str]] = {}
        for plate in plates:
            md = metadata(plate)
            label = md.get("plater_name", "")
            filenames = []
            for instance in plate.findall("model_instance"):
                oid = metadata(instance).get("object_id", "")
                filenames.append(obj_names.get(oid, ""))
            plate_map[label] = filenames
            for key in ("thumbnail_file", "thumbnail_no_light_file", "top_file", "pick_file"):
                thumb = md.get(key, "")
                if thumb and thumb not in z.namelist():
                    errors.append(f"plate {label}: missing preview {thumb}")
        if plate_map != EXPECTED:
            errors.append(f"plate membership mismatch: {plate_map}")
        if set(by_name) != {p["filename"] for p in manifest["parts"]}:
            errors.append("project mesh inventory does not match mesh manifest")
        if project.get("printer_model") != "Elegoo Neptune 2":
            errors.append("unexpected printer model")
        if project.get("printer_settings_id") != "Elegoo Neptune 2 0.4 nozzle":
            errors.append("unexpected printer preset")
        if project.get("print_settings_id") != "0.20mm Standard @Elegoo Neptune 0.4 nozzle":
            errors.append("unexpected process preset")
        if project.get("filament_settings_id") != ["Panchroma PLA Matte @System"]:
            errors.append("unexpected filament preset")

        bed = project.get("printable_area", [])
        pts = [tuple(map(float, p.split("x"))) for p in bed]
        xlo, xhi = min(x for x, _ in pts), max(x for x, _ in pts)
        ylo, yhi = min(y for _, y in pts), max(y for _, y in pts)
        zhi = float(project.get("printable_height", 0))
        resources = model.find("c:resources", NS)
        model_objects = {o.get("id"): o for o in resources.findall("c:object", NS)}
        build = model.find("c:build", NS)
        placed = set()
        for item in build.findall("c:item", NS):
            oid = item.get("objectid", "")
            filename = obj_names.get(oid, "")
            if filename not in parts:
                errors.append(f"build item has unknown mesh object id {oid}")
                continue
            if filename in placed:
                errors.append(f"duplicate build item for {filename}")
            placed.add(filename)
            obj = model_objects.get(oid)
            component = obj.find("c:components/c:component", NS) if obj is not None else None
            if component is None:
                errors.append(f"missing mesh component for {filename}")
                continue
            path = component.get(f"{{{PROD}}}path", "").lstrip("/")
            child = ET.fromstring(z.read(path))
            verts = child.findall(".//c:vertex", NS)
            if not verts:
                errors.append(f"no vertices for {filename}")
                continue
            xs = [float(v.get("x")) for v in verts]
            ys = [float(v.get("y")) for v in verts]
            zs = [float(v.get("z")) for v in verts]
            transform = [float(v) for v in item.get("transform", "").split()]
            if len(transform) != 12:
                errors.append(f"invalid transform for {filename}")
                continue
            dx, dy, dz = transform[9:12]
            bounds = (min(xs)+dx, max(xs)+dx, min(ys)+dy, max(ys)+dy, min(zs)+dz, max(zs)+dz)
            if bounds[0] < xlo or bounds[1] > xhi or bounds[2] < ylo or bounds[3] > yhi or bounds[4] < -0.01 or bounds[5] > zhi:
                errors.append(f"{filename} outside bed: {bounds}")
            expected_box = parts[filename]["local_mesh_bbox_mm"]
            dims = (bounds[1]-bounds[0], bounds[3]-bounds[2], bounds[5]-bounds[4])
            expected_dims = (expected_box[3]-expected_box[0], expected_box[4]-expected_box[1], expected_box[5]-expected_box[2])
            if any(abs(a-b) > 0.03 for a, b in zip(dims, expected_dims)):
                errors.append(f"{filename} dimensions differ from mesh manifest: {dims} vs {expected_dims}")
            print(f"{plate_map_for(filename, plate_map)}: {filename} bounds {tuple(round(v, 2) for v in bounds)}")
        if placed != set(parts):
            errors.append(f"build items differ from manifest: {placed}")
    for name, part in parts.items():
        if not part.get("solid_mesh", False):
            warnings.append(f"{name}: source export reports a non-solid/non-watertight mesh")
    print(f"plates={len(plate_map)} objects={len(parts)} printer=Elegoo Neptune 2 235x235x{zhi:g} mm")
    for warning in warnings:
        print("WARNING:", warning)
    for error in errors:
        print("ERROR:", error)
    return 1 if errors else 0


def plate_map_for(filename: str, mapping: dict[str, list[str]]) -> str:
    return next((plate for plate, files in mapping.items() if filename in files), "Unassigned")


if __name__ == "__main__":
    raise SystemExit(main())
