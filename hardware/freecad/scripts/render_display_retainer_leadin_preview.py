"""Render before/after STL previews for the retainer M2 lead-in candidate.

Uses only Python's standard library, NumPy and Pillow. Source and candidate
meshes are exported by create_display_retainer_mounting_leadin_candidate.py.
"""
import math
import struct
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path("/private/tmp/pendant-hardware-integration/hardware/freecad")
BEFORE = Path("/private/tmp/display-retainer-leadin-before.stl")
AFTER = Path("/private/tmp/display-retainer-leadin-after.stl")
OUT = ROOT / "reports/display-retainer-mounting-leadin-before-after.png"
W, H = 1440, 1040
BG = (246, 248, 251)
PART = (41, 147, 179)


def read_stl(path):
    raw = path.read_bytes()
    n = struct.unpack_from("<I", raw, 80)[0]
    if len(raw) != 84 + 50*n:
        raise RuntimeError("Expected binary STL: " + str(path))
    triangles = np.empty((n, 3, 3), dtype=float)
    for i in range(n):
        record = struct.unpack_from("<12fH", raw, 84 + i*50)
        triangles[i] = np.asarray(record[3:12], dtype=float).reshape((3, 3))
    return triangles


def font(size, bold=False):
    paths = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Helvetica.ttc",
    ]
    for path in paths:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            pass
    return ImageFont.load_default()


def draw_mesh(image, tris, box, crop=None):
    x0, y0, x1, y1 = box
    pad = 24
    normals = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    normals /= np.maximum(np.linalg.norm(normals, axis=1)[:, None], 1e-12)
    # Orthographic top view: the actual outer face carries the hole mouths and
    # keeps this detail image legible instead of hiding it behind the thin plate.
    top_z = float(tris[:, :, 2].max())
    top_faces = (normals[:, 2] > 0.8) & (tris[:, :, 2].min(axis=1) > top_z - 1e-4)
    tris, normals = tris[top_faces], normals[top_faces]
    shade = np.clip(0.78 + 0.22*np.maximum(0, normals[:, 2]), 0.78, 1.0)
    colors = np.stack([PART[0]*shade, PART[1]*shade, PART[2]*shade], axis=1).astype(int)
    sx, sy = tris[:, :, 0].copy(), tris[:, :, 1].copy()
    depth = tris[:, :, 2].mean(axis=1)
    if crop is not None:
        cx, cy, half = crop
        # Retain the top-face facets around the selected entry mouth.
        keep = ((tris[:, :, 0].max(axis=1) >= cx-half) &
                (tris[:, :, 0].min(axis=1) <= cx+half) &
                (tris[:, :, 1].max(axis=1) >= cy-half) &
                (tris[:, :, 1].min(axis=1) <= cy+half))
        tris, sx, sy, depth, colors = tris[keep], sx[keep], sy[keep], depth[keep], colors[keep]
        if len(tris) == 0:
            raise RuntimeError("Empty local preview crop")
        xlim, ylim = (cx-half, cx+half), (cy-half, cy+half)
    else:
        xlim = (float(sx.min()), float(sx.max()))
        ylim = (float(sy.min()), float(sy.max()))
    plot_top, plot_bottom = y0 + 52, y1 - 18
    avail_w, avail_h = (x1-x0-2*pad), (plot_bottom-plot_top)
    scale = min(avail_w/max(1e-6, xlim[1]-xlim[0]), avail_h/max(1e-6, ylim[1]-ylim[0]))
    cxp = (xlim[0]+xlim[1])/2
    cyp = (ylim[0]+ylim[1])/2
    px = x0 + (x1-x0)/2 + (sx-cxp)*scale
    py = (plot_top+plot_bottom)/2 - (sy-cyp)*scale
    order = np.argsort(depth)
    layer = Image.new("RGB", (x1-x0, y1-y0), (255, 255, 255))
    draw = ImageDraw.Draw(layer)
    for i in order:
        pts = [(int(px[i, j]-x0), int(py[i, j]-y0)) for j in range(3)]
        c = tuple(int(v) for v in colors[i])
        draw.polygon(pts, fill=c)
    crop = layer.crop((pad, plot_top-y0, x1-x0-pad, plot_bottom-y0))
    image.paste(crop, (x0+pad, plot_top))


def main():
    before = read_stl(BEFORE)
    after = read_stl(AFTER)
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    title = font(30, True)
    subtitle = font(18)
    panel_title = font(20, True)
    d.text((40, 24), "Display retainer — mounting entry refinement", font=title, fill=(28, 36, 45))
    d.text((40, 66), "Native tapered-pocket lead-ins: 0.15 mm radial × 0.15 mm deep, 45°", font=subtitle, fill=(74, 86, 98))
    panels = [(36, 112, 704, 572), (736, 112, 1404, 572),
              (36, 594, 704, 1002), (736, 594, 1404, 1002)]
    names = ["SOURCE — complete component", "CANDIDATE — complete component",
             "SOURCE — M2 mouth detail", "CANDIDATE — M2 mouth detail"]
    for box, name in zip(panels, names):
        d.rounded_rectangle(box, radius=14, fill=(255, 255, 255), outline=(205, 214, 222), width=2)
        d.text((box[0]+18, box[1]+14), name, font=panel_title, fill=(37, 48, 60))
    draw_mesh(img, before, panels[0])
    draw_mesh(img, after, panels[1])
    draw_mesh(img, before, panels[2], crop=(-25.8, -10.5, 2.7))
    draw_mesh(img, after, panels[3], crop=(-25.8, -10.5, 2.7))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT)
    print(str(OUT))


if __name__ == "__main__":
    main()
