#!/usr/bin/env python3
"""Render read-only top/bottom assembly previews without opening FreeCAD GUI.

Requires the Python packages NumPy and Pillow in the Python used to run this
script, plus FreeCADCmd. Geometry is tessellated from the saved modular
assembly and its relative App::Link sources. No CAD document is recomputed or
saved by this workflow.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time

try:
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:
    raise SystemExit('Preview rendering requires numpy and Pillow: ' + str(exc))

SCRIPT = Path(__file__).resolve()
FREECAD_DIR = SCRIPT.parents[1]
DEFAULT_CMD = Path('/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd')
ASSEMBLY = FREECAD_DIR / 'pendant-modular-assembly.FCStd'
EXPECTED_LINKS = 5
EXPECTED_INTERIM = 5
PALETTE = {
    'Interim_Body': (48, 134, 104),
    'Interim_Body002': (49, 107, 155),
    'Interim_Body003': (216, 156, 61),
    'Interim_Body_EncoderFacePlate': (143, 101, 178),
    'Interim_Body_EncoderPocket': (45, 154, 170),
    'Interim_Body006': (136, 145, 151),
    'Editable_Body_DisplayRetainer_EditableV2': (225, 112, 78),
    'Editable_Body_USBTetheredCover': (111, 171, 103),
    'Editable_Body_FaceplateLocator_A': (217, 94, 116),
    'Editable_Body_FaceplateLocator_B': (217, 94, 116),
    'Editable_Body006': (136, 145, 151),
}


def macro_source(assembly: Path, export_path: Path, deflection: float) -> str:
    cfg = json.dumps({'assembly': str(assembly.resolve()),
                      'export': str(export_path.resolve()),
                      'deflection': deflection,
                      'expected_links': EXPECTED_LINKS,
                      'expected_interim': EXPECTED_INTERIM})
    return r'''import FreeCAD as App, json, gzip, traceback
C=json.loads(@@CFG@@); out={'errors':[],'objects':[]}
opened=[]
def info(obj):
    s=obj.Shape; b=s.BoundBox
    return {'valid':bool(s and not s.isNull() and s.isValid()),'solids':len(s.Solids),
            'volume':s.Volume,'bbox':[b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]}
try:
    d=App.openDocument(C['assembly']); opened.append(d.Name)
    links=[o for o in d.Objects if o.TypeId=='App::Link']
    interim=[o for o in d.Objects if o.Name.startswith('Interim_')]
    if len(links)!=C['expected_links'] or len(interim)!=C['expected_interim']:
        raise RuntimeError('unexpected assembly inventory: %d links, %d interim shapes'%(len(links),len(interim)))
    objects=interim+links
    colors={}
    for obj in objects:
        a=info(obj)
        if not a['valid'] or a['solids']!=1: raise RuntimeError('invalid/non-single-solid preview shape: '+obj.Name)
        if obj.TypeId=='App::Link':
            target=obj.LinkedObject
            b=info(target)
            if not b['valid'] or abs(a['volume']-b['volume'])>1e-6 or any(abs(x-y)>1e-6 for x,y in zip(a['bbox'],b['bbox'])):
                raise RuntimeError('link/source shape mismatch: '+obj.Name)
        vertices,facets=obj.Shape.tessellate(C['deflection'])
        if not vertices or not facets: raise RuntimeError('empty tessellation: '+obj.Name)
        out['objects'].append({'name':obj.Name,'label':obj.Label,'kind':'live link' if obj.TypeId=='App::Link' else 'static interim BREP',
            'color':None,'shape':a,'vertices':[[v.x,v.y,v.z] for v in vertices],
            'triangles':[list(f) for f in facets]})
    with gzip.open(C['export'],'wt',encoding='utf-8') as f: json.dump(out,f,separators=(',',':'))
except Exception as e:
    out['errors']=[str(e),traceback.format_exc()]
    with gzip.open(C['export'],'wt',encoding='utf-8') as f: json.dump(out,f)
finally:
    for n in reversed(opened):
        if n in App.listDocuments():
            try: App.closeDocument(n)
            except Exception: pass
print('MODULAR_PREVIEW_EXPORT='+json.dumps({'errors':out['errors'],'objects':[{k:o[k] for k in ('name','label','kind','shape')} for o in out['objects']]}))
'''.replace('@@CFG@@', repr(cfg))


def load_font(size: int):
    for p in ('/System/Library/Fonts/Supplemental/Arial.ttf',
              '/System/Library/Fonts/Supplemental/Helvetica.ttf',
              '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
        if Path(p).is_file():
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                pass
    return ImageFont.load_default()


def shade_color(color: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    amount = max(0.28, min(1.0, amount))
    return tuple(round(channel * amount) for channel in color)


def draw_mesh(canvas: Image.Image, zbuffer: np.ndarray, vertices, triangles,
              color: tuple[int, int, int], bounds, view: str, region,
              lighting=True) -> None:
    x0, y0, x1, y1 = region
    width, height = x1 - x0, y1 - y0
    xmin, ymin, xmax, ymax = bounds
    dx, dy = max(xmax - xmin, 1e-9), max(ymax - ymin, 1e-9)
    scale = min((width - 24) / dx, (height - 24) / dy)
    ox = x0 + (width - dx * scale) / 2
    oy = y0 + (height - dy * scale) / 2
    verts = np.asarray(vertices, dtype=np.float64)
    px = ox + (verts[:, 0] - xmin) * scale
    py = oy + (ymax - verts[:, 1]) * scale
    pz = verts[:, 2] if view == 'top' else -verts[:, 2]
    pix = np.column_stack((px, py, pz))
    light = np.array([0.25, 0.35, 1.0 if view == 'top' else -1.0], dtype=np.float64)
    light /= np.linalg.norm(light)
    image_array = np.asarray(canvas).copy()
    for tri in triangles:
        p = pix[np.asarray(tri, dtype=np.int64)]
        xa = max(x0, int(np.floor(p[:, 0].min())))
        xb = min(x1 - 1, int(np.ceil(p[:, 0].max())))
        ya = max(y0, int(np.floor(p[:, 1].min())))
        yb = min(y1 - 1, int(np.ceil(p[:, 1].max())))
        if xa > xb or ya > yb:
            continue
        a, b, c = p[:, :2]
        den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(den) < 1e-12:
            continue
        xs = np.arange(xa, xb + 1, dtype=np.float64) + 0.5
        ys = np.arange(ya, yb + 1, dtype=np.float64) + 0.5
        xx, yy = np.meshgrid(xs, ys)
        w0 = ((b[1] - c[1]) * (xx - c[0]) + (c[0] - b[0]) * (yy - c[1])) / den
        w1 = ((c[1] - a[1]) * (xx - c[0]) + (a[0] - c[0]) * (yy - c[1])) / den
        w2 = 1.0 - w0 - w1
        inside = (w0 >= -1e-7) & (w1 >= -1e-7) & (w2 >= -1e-7)
        if not inside.any():
            continue
        depth = w0 * p[0, 2] + w1 * p[1, 2] + w2 * p[2, 2]
        zslice = zbuffer[ya:yb + 1, xa:xb + 1]
        visible = inside & (depth > zslice)
        if not visible.any():
            continue
        normal = np.cross(verts[tri[1]] - verts[tri[0]], verts[tri[2]] - verts[tri[0]])
        norm = np.linalg.norm(normal)
        diffuse = abs(float(np.dot(normal / norm, light))) if norm > 1e-12 else 0.0
        amount = 0.40 + 0.60 * diffuse if lighting else 0.88
        rgb = shade_color(color, amount)
        zslice[visible] = depth[visible]
        patch = image_array[ya:yb + 1, xa:xb + 1]
        patch[visible] = rgb
    canvas.paste(Image.fromarray(image_array))


def component_bounds(vertices):
    v = np.asarray(vertices, dtype=np.float64)
    return (float(v[:, 0].min()), float(v[:, 1].min()),
            float(v[:, 0].max()), float(v[:, 1].max()))


def render_assembly(objects, view: str, path: Path) -> None:
    width, height = 1500, 1050
    image = Image.new('RGB', (width, height), (247, 249, 251))
    draw = ImageDraw.Draw(image)
    draw.text((38, 24), f'Current modular pendant assembly — {view} view',
              fill=(24, 35, 47), font=load_font(32))
    draw.text((40, 68), 'Orthographic projection • current saved component links and interim solids',
              fill=(75, 88, 101), font=load_font(17))
    x0, y0, x1, y1 = 60, 115, width - 60, height - 55
    all_verts = [np.asarray(o['vertices'], dtype=np.float64) for o in objects]
    all_points = np.vstack(all_verts)
    bounds = component_bounds(all_points)
    zbuffer = np.full((height, width), -np.inf, dtype=np.float64)
    palette = {o['name']: tuple(o['color']) for o in objects}
    for obj in objects:
        draw_mesh(image, zbuffer, obj['vertices'], obj['triangles'], palette[obj['name']], bounds, view, (x0, y0, x1, y1))
    draw.rectangle((x0, y0, x1, y1), outline=(187, 196, 205), width=2)
    image.save(path)


def render_interim_sheet(objects, path: Path) -> None:
    width, height = 1440, 1050
    image = Image.new('RGB', (width, height), (247, 249, 251))
    draw = ImageDraw.Draw(image)
    draw.text((30, 22), 'Static interim components — underside inspection',
              fill=(24, 35, 47), font=load_font(28))
    draw.text((32, 60), 'Each component is shown separately, normalized to its own XY bounds; global +X right, +Y up.',
              fill=(75, 88, 101), font=load_font(16))
    items = [o for o in objects if o['kind'] == 'static interim BREP']
    margin, gap, cell_w, cell_h = 24, 16, 448, 465
    for i, obj in enumerate(items):
        col, row = i % 3, i // 3
        x0 = margin + col * (cell_w + gap)
        y0 = 96 + row * (cell_h + gap)
        x1, y1 = x0 + cell_w, y0 + cell_h
        draw.rounded_rectangle((x0, y0, x1, y1), radius=14, fill=(255, 255, 255), outline=(199, 207, 215), width=2)
        label = obj['label'].replace('INTERIM — ', '')
        draw.text((x0 + 15, y0 + 12), label, fill=(29, 42, 55), font=load_font(18))
        volume = obj['shape']['volume']
        draw.text((x0 + 15, y0 + 40), f"Static BREP • {volume:.1f} mm³",
                  fill=(92, 105, 118), font=load_font(14))
        region = (x0 + 16, y0 + 74, x1 - 16, y1 - 18)
        zbuffer = np.full((height, width), -np.inf, dtype=np.float64)
        draw_mesh(image, zbuffer, obj['vertices'], obj['triangles'], tuple(obj['color']),
                  component_bounds(obj['vertices']), 'bottom', region)
    image.save(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assembly', type=Path, default=ASSEMBLY)
    parser.add_argument('--output-dir', type=Path, default=FREECAD_DIR / 'reports' / 'modular-preview')
    parser.add_argument('--freecadcmd', default=os.environ.get('FREECADCMD'))
    parser.add_argument('--deflection', type=float, default=0.2)
    parser.add_argument('--timeout', type=int, default=170)
    args = parser.parse_args()
    if not args.assembly.is_file():
        parser.error('assembly file not found: ' + str(args.assembly))
    if not 0.02 <= args.deflection <= 2.0:
        parser.error('--deflection must be between 0.02 and 2.0 mm')
    if not 1 <= args.timeout <= 180:
        parser.error('--timeout must be between 1 and 180 seconds')
    cmd = args.freecadcmd or (str(DEFAULT_CMD) if DEFAULT_CMD.is_file() else None)
    if not cmd:
        parser.error('freecadcmd not found; pass --freecadcmd or set FREECADCMD')
    gui = subprocess.run(['pgrep', '-x', 'FreeCAD'], capture_output=True, text=True)
    if gui.returncode == 0 and gui.stdout.strip():
        raise SystemExit('FreeCAD GUI process detected; close it before preview export (PID(s): ' + gui.stdout.strip() + ')')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='pendant-preview-') as td:
        export_path = Path(td) / 'assembly-meshes.json.gz'
        macro = Path(td) / 'export_preview.FCMacro'
        macro.write_text(macro_source(args.assembly, export_path, args.deflection), encoding='utf-8')
        start = time.monotonic()
        proc = subprocess.Popen([cmd, str(macro)], cwd=args.assembly.resolve().parent,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, start_new_session=True)
        try:
            output, _ = proc.communicate(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait(timeout=5)
            output, _ = proc.communicate()
            print(output[-2000:])
            raise SystemExit('Preview export timed out; owned FreeCADCmd process was terminated')
        export_seconds = time.monotonic() - start
        if proc.returncode:
            raise SystemExit(f'FreeCADCmd exited {proc.returncode}:\n{output[-3000:]}')
        marker = next((line.split('MODULAR_PREVIEW_EXPORT=', 1)[1]
                       for line in output.splitlines() if 'MODULAR_PREVIEW_EXPORT=' in line), None)
        if marker is None:
            raise SystemExit('FreeCADCmd returned no preview manifest:\n' + output[-3000:])
        manifest = json.loads(marker)
        if manifest.get('errors'):
            raise SystemExit('Preview geometry validation failed: ' + '; '.join(manifest['errors']))
        with gzip.open(export_path, 'rt', encoding='utf-8') as f:
            data = json.load(f)
    for obj in data['objects']:
        obj['color'] = PALETTE.get(obj['name'], (120, 135, 150))
    assembly_img = args.output_dir / 'pendant-modular-assembly-bottom.png'
    top_img = args.output_dir / 'pendant-modular-assembly-top.png'
    interim_img = args.output_dir / 'static-interim-components-bottom.png'
    render_assembly(data['objects'], 'bottom', assembly_img)
    render_assembly(data['objects'], 'top', top_img)
    render_interim_sheet(data['objects'], interim_img)
    try:
        assembly_name = args.assembly.resolve().relative_to(FREECAD_DIR.resolve()).as_posix()
    except ValueError:
        assembly_name = args.assembly.name
    summary = {
        'assembly': assembly_name,
        'freecadcmd_export_seconds': round(export_seconds, 3),
        'deflection_mm': args.deflection,
        'link_count': sum(o['kind'] == 'live link' for o in data['objects']),
        'static_interim_count': sum(o['kind'] == 'static interim BREP' for o in data['objects']),
        'validated_shapes': sum(o['shape']['valid'] and o['shape']['solids'] == 1 for o in data['objects']),
        'images': [assembly_img.name, top_img.name, interim_img.name],
    }
    manifest_path = args.output_dir / 'preview-manifest.json'
    manifest_path.write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
