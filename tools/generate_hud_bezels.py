#!/usr/bin/env python3
"""Generate deterministic, luminous 240px bezels for the round MPG display.

Pillow and NumPy are host-only tools. The firmware receives a compact set of
row-major 4-bit indexed raw bitmaps and generated palette constants.
"""
import argparse
import json
import math
from pathlib import Path
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SIZE = 240
SCALE = 8
CENTER = 120.0
INNER, OUTER = 87.0, 119.0
LEVELS = (0.012, 0.035, 0.075, 0.15, 0.28, 0.5, 0.78)
# A tiny GC9A01 photographed or viewed at close range blooms brighter than
# desktop sRGB previews. Keep decorative bezel luminance below status text so
# the readout remains the visual focal point; the separate status palettes
# retain their full brightness.
# The GC9A01 is viewed at close range behind a glossy lens. Keep decorative
# strokes well below text luminance; phone-camera exposure otherwise merges
# the carefully separated 4-bit colors into a broad, noisy white annulus.
BEZEL_LUMINANCE = 0.55
THEMES = (
    ("cyan_reactor", "Cyan segmented reactor", (28,221,255), (2,95,168), "segments"),
    ("green_instrument", "Green illuminated instrumentation", (68,255,158), (11,125,84), "ticks"),
    ("amber_precision", "Amber precision gauge", (255,190,58), (166,80,14), "gauge"),
    ("red_alarm", "Red alarm ring", (255,67,80), (142,13,32), "alarm"),
    ("ice_optical", "Ice-white optical ring", (220,248,255), (71,154,204), "optical"),
    ("blue_scanner", "Electric-blue concentric scanner", (34,138,255), (14,55,164), "scanner"),
    ("turquoise_energy", "Turquoise segmented energy ring", (22,238,215), (3,112,156), "energy"),
    ("cyan_amber", "Cyan-and-amber dual-status ring", (25,221,255), (255,176,38), "dual"),
    ("violet_hologram", "Violet holographic ring", (196,104,255), (80,42,189), "hologram"),
    ("spectral", "Multicolor spectral ring", (15,213,255), (255,61,186), "spectral"),
    ("cyan_reticle", "Minimal cyan targeting reticle", (62,235,255), (18,130,207), "reticle"),
    ("blue_violet_aura", "Blue-violet energy aura", (35,147,255), (166,86,255), "aura"),
)


def _rgb(c):
    return (int(c[0]) << 16) | (int(c[1]) << 8) | int(c[2])


def orbit_phase_data():
    """Return a 36px atlas of 16 supersampled 9px subpixel orb phases."""
    tile, phases, samples = 9, 4, 4
    atlas = np.zeros((tile * phases, tile * phases), dtype=np.uint8)
    yy, xx = np.mgrid[0:tile*samples, 0:tile*samples]
    xx = (xx + 0.5) / samples
    yy = (yy + 0.5) / samples
    for phase_y in range(phases):
        center_y = 4.0 + phase_y / float(phases)
        for phase_x in range(phases):
            center_x = 4.0 + phase_x / float(phases)
            distance = np.hypot(xx-center_x, yy-center_y)
            light = np.zeros(distance.shape, dtype=np.float32)
            light[distance <= 1.8] = 1.0
            mid = (distance > 1.8) & (distance <= 3.0)
            light[mid] = 0.72
            falloff = (distance > 3.0) & (distance < 4.3)
            light[falloff] = 0.72 * (4.3-distance[falloff]) / 1.3
            coverage = light.reshape(tile, samples, tile, samples).mean(
                axis=(1, 3))
            indices = np.rint(coverage * 15).astype(np.uint8)
            x0, y0 = phase_x * tile, phase_y * tile
            atlas[y0:y0+tile, x0:x0+tile] = indices
    packed = (atlas[:, 0::2] | (atlas[:, 1::2] << 4)).astype(np.uint8)
    return packed.tobytes()


def rotor_segment_data():
    """Return a supersampled curved-arc atlas for the fixed outer rotor.

    Each 33px tile contains a longer, visibly curved ~30px arc on a 110px
    track. Twenty-four tangent orientations align with the fixed positions;
    subpixel placement is precomputed. Firmware only changes palette levels,
    so the geometry never pivots or rotates during animation.
    """
    tile, phases, orientations, samples = 33, 4, 24, 8
    track_radius, half_length = 110.0, 14.5
    atlas = np.zeros((tile * orientations * phases, tile * phases),
                     dtype=np.uint8)
    grid = (np.arange(tile * samples, dtype=np.float32) + .5) / samples
    xx, yy = np.meshgrid(grid, grid)
    for orientation in range(orientations):
        angle = 2.0 * math.pi * orientation / orientations
        ux, uy = math.cos(angle), math.sin(angle)
        vx, vy = -uy, ux
        for phase_y in range(phases):
            center_y = 16.0 + phase_y / float(phases)
            for phase_x in range(phases):
                center_x = 16.0 + phase_x / float(phases)
                dx, dy = xx - center_x, yy - center_y
                along = dx * ux + dy * uy
                across = dx * vx + dy * vy
                # In tangent coordinates a circle curves inward by s²/(2R).
                # Bake that gentle curvature into each tile so the accents
                # read as ring arcs instead of bars spinning on their axes.
                arc_inward = (along * along) / (2.0 * track_radius)
                cap = np.maximum(np.abs(along) - half_length, 0.0)
                distance = np.hypot(cap, across - arc_inward)
                light = np.zeros(distance.shape, dtype=np.float32)
                light[distance <= .85] = 1.0
                soft = (distance > .85) & (distance < 1.8)
                light[soft] = .72 + .28 * (1.8-distance[soft])/.95
                glow = (distance >= 1.8) & (distance < 3.2)
                light[glow] = .20 * (3.2-distance[glow])/1.4
                coverage = light.reshape(tile, samples, tile, samples).mean(
                    axis=(1, 3))
                y0 = (orientation * phases + phase_y) * tile
                x0 = phase_x * tile
                atlas[y0:y0+tile, x0:x0+tile] = np.rint(
                    coverage * 15).astype(np.uint8)
    packed = (atlas[:, 0::2] | (atlas[:, 1::2] << 4)).astype(np.uint8)
    return packed.tobytes()


def _point(r, a, scale):
    theta = math.radians(a)
    return (round((CENTER + r*math.cos(theta))*scale),
            round((CENTER + r*math.sin(theta))*scale))


def _geometry(kind, a, b, scale):
    """Draw design-specific crisp masks at supersampled resolution."""
    d1, d2 = ImageDraw.Draw(a), ImageDraw.Draw(b)
    def arc(draw, r, start, end, width=1):
        rr, c = r*scale, CENTER*scale
        draw.arc((c-rr,c-rr,c+rr,c+rr), start, end,
                 fill=255, width=max(1, round(width*scale)))
    def line(draw, r1, a1, r2, a2, width=.6):
        draw.line((_point(r1,a1,scale),_point(r2,a2,scale)), fill=255,
                  width=max(1,round(width*scale)))
    def ticks(draw, n, inner, outer, major_every=5):
        for i in range(n):
            angle=-90+i*360/n
            major=i%major_every==0
            line(draw,inner,angle,outer+(2 if major else 0),angle,
                 .8 if major else .38)
    def dot(draw, r, angle, size=1):
        x,y=_point(r,angle,scale); q=size*scale/2
        draw.ellipse((round(x-q),round(y-q),round(x+q),round(y+q)),fill=255)
    def blocks(count, radius, extent, width, phase=0):
        for i in range(count):
            c=-90+phase+i*360/count
            arc(d1,radius,c-extent/2,c+extent/2,width)
            # A short inner echo makes each illuminated segment read as a unit.
            arc(d2,radius-7,c-extent/2+3,c+extent/2-3,.65)
    if kind == "segments":
        # Keep a recognizable circular instrument silhouette while leaving
        # the center clear for telemetry. A hairline guide ring carries a set
        # of twelve wider illuminated sectors; alternating inner echoes and
        # sparse graduations add depth without the dense dotted field that
        # bloomed through the physical lens at 240 px.
        arc(d2,116,-180,180,.55)
        for i in range(12):
            c=-90+i*30
            arc(d1,113,c-10,c+10,1.8)
            if i % 2 == 0:
                arc(d2,106,c-6,c+6,.7)
        ticks(d2,48,101,105,6)
    elif kind == "ticks":
        arc(d1,114,-155,155,.8); arc(d2,107,-160,160,.45)
        ticks(d2,120,96,101,10); ticks(d1,60,93,104,10)
        for i in range(6): dot(d1,110,-130+i*52,1.4)
    elif kind == "gauge":
        for r in (114,107,96): arc(d1 if r!=107 else d2,r,-225,45,1.2 if r==114 else .55)
        for i in range(5):
            c=-202.5+i*67.5; arc(d1,112,c-18,c+18,1.8)
            line(d2,94,c,100,c,.85)
        ticks(d2,54,93,103,9)
    elif kind == "alarm":
        blocks(12,113,19,2.4)
        arc(d2,100,-180,180,.55); ticks(d1,48,97,101,4)
        for i in range(4): dot(d1,110,-90+i*90,1.7)
    elif kind == "optical":
        for r,w,draw in ((116,.7,d1),(113,.38,d2),(104,.42,d1),(91,.35,d2)):
            c=CENTER*scale; rr=r*scale
            draw.ellipse((round(c-rr),round(c-rr),round(c+rr),round(c+rr)),outline=255,width=max(1,round(w*scale)))
        ticks(d2,48,99,104,4)
        for ang in (-90,0,90,180): line(d1,108,ang,119,ang,.65)
    elif kind == "scanner":
        for r in (91,98,108,115): arc(d1 if r in (98,115) else d2,r,-180,180,.85 if r in (98,115) else .4)
        blocks(16,112,10,1.3,phase=5)
        ticks(d2,72,101,104,12)
        arc(d1,88,-38,8,.7)
    elif kind == "energy":
        blocks(12,112,19,2.3)
        ticks(d2,60,100,103,5)
        for i in range(24): dot(d1,93,-90+i*15,.8)
        for i in range(12): arc(d1,99,-88+i*30,-80+i*30,.7)
    elif kind == "dual":
        for r,start,end,draw in ((114,-171,-9,d1),(114,9,171,d2),(105,-160,-20,d2),(105,20,160,d1)):
            arc(draw,r,start,end,1.8 if r==114 else .65)
        ticks(d1,48,97,103,4); ticks(d2,48,97,101,4)
        for i in range(8): dot(d1 if i<4 else d2,111,-157.5+i*45,1.5)
    elif kind == "hologram":
        for i in range(9):
            c=-90+i*40; arc(d1,114,c+3,c+23,1.3); arc(d2,103,c+7,c+20,.65)
            line(d1,94,c+12,99,c+12,.8)
        ticks(d2,54,101,105,9)
        for i in range(18): dot(d2,90,-90+i*20,.75)
    elif kind == "spectral":
        for i in range(36):
            c=-90+i*10; arc(d1 if i%3 else d2,112,c+1,c+7,2 if i%3==0 else 1.2)
        arc(d2,105,-180,180,.45); ticks(d1,60,99,104,6)
        for i in range(24): dot(d2 if i%2 else d1,93,-90+i*15,.9)
    elif kind == "reticle":
        for start,end in ((-76,-14),(14,76),(104,166),(194,256)): arc(d1,112,start,end,.8)
        for start,end in ((-61,-29),(29,61),(119,151),(209,241)): arc(d2,98,start,end,.45)
        ticks(d2,32,101,106,4)
        for ang in (-90,0,90,180): line(d1,108,ang,119,ang,.8)
    elif kind == "aura":
        arc(d1,114,-170,-10,1.35); arc(d2,114,10,170,1.35)
        arc(d2,107,-170,-10,.65); arc(d1,107,10,170,.65)
        arc(d1,97,-150,150,.5); ticks(d2,96,101,104,12)
        for i in range(16): dot(d1 if i%2 else d2,91,-90+i*22.5,.9)
    else:
        raise ValueError(kind)


def _palette(primary, secondary):
    out=[0]
    for color in (primary,secondary):
        out.extend(_rgb(tuple(round(x*k*BEZEL_LUMINANCE) for x in color))
                   for k in LEVELS)
    out.append(_rgb(tuple(round(x * BEZEL_LUMINANCE)
                          for x in (244, 252, 255))))
    return out


def render(theme, supersample=8):
    name,label,primary,secondary,kind=theme
    hi=SIZE*supersample
    first=Image.new("L",(hi,hi)); second=Image.new("L",(hi,hi))
    _geometry(kind,first,second,supersample)
    x=(np.arange(hi,dtype=np.float32)+.5)/supersample-CENTER
    xx,yy=np.meshgrid(x,x); radius=np.sqrt(xx*xx+yy*yy)
    angle=np.arctan2(yy,xx)
    pa=np.asarray(first,dtype=np.float32)/255
    sa=np.asarray(second,dtype=np.float32)/255
    def blur(image,r): return np.asarray(image.filter(ImageFilter.GaussianBlur(r*supersample)),dtype=np.float32)/255
    # Keep illumination attached to the drawn strokes. Wide Gaussian fields
    # merge adjacent arcs into a solid annulus at 240px, especially after the
    # GC9A01's RGB565 conversion. A restrained sub-2px halo preserves a crisp
    # optical line while leaving the gaps genuinely transparent.
    p_glow=blur(first,.55); p_halo=blur(first,1.8)
    s_glow=blur(second,.5); s_halo=blur(second,1.6)
    pa=np.clip(pa*.94+p_glow*.20+p_halo*.16,0,1)
    sa=np.clip(sa*.90+s_glow*.18+s_halo*.14,0,1)
    edge=(radius>=INNER)&(radius<=OUTER)
    weighted=pa[...,None]*np.asarray(primary)+sa[...,None]*np.asarray(secondary)
    total=np.maximum(pa+sa,1e-8)
    hue=np.clip(weighted/total[...,None],0,255)
    intensity=np.clip(np.max(weighted,axis=2)/255,0,1)
    intensity=np.where(edge,intensity,0)
    hue=np.where(edge[...,None],hue,0)
    resampling=Image.Resampling.LANCZOS
    rgb=Image.fromarray(np.uint8(np.clip(hue*intensity[...,None],0,255)),"RGB").resize((SIZE,SIZE),resampling)
    alpha=Image.fromarray(np.uint8(intensity*255),"L").resize((SIZE,SIZE),resampling)
    native_radius=np.hypot(np.arange(SIZE)[None,:]-CENTER,
                           np.arange(SIZE)[:,None]-CENTER)
    alpha_values=np.array(alpha,dtype=np.uint8)
    alpha_values[(native_radius<INNER)|(native_radius>OUTER)]=0
    alpha=Image.fromarray(alpha_values,"L")
    display_rgb=Image.fromarray(np.uint8(hue),"RGB").resize((SIZE,SIZE),resampling)
    rgba=display_rgb.convert("RGBA"); rgba.putalpha(alpha)
    palette=_palette(primary,secondary)
    # Squared RGB distances can exceed signed 16-bit range (3*255^2).
    # int16 wrapped negative values and selected unrelated palette entries,
    # which rendered the hardware bezel as noisy white/multicolor pixels.
    pal=np.array([((v>>16)&255,(v>>8)&255,v&255) for v in palette[1:]],dtype=np.int32)
    # Keep the pixel values in the same luminance range as the deliberately
    # dimmed device palette; otherwise nearest-color selection can collapse
    # saturated cyan toward the pale neutral entry.
    pixels=(np.asarray(rgb,dtype=np.float32) * BEZEL_LUMINANCE).astype(np.int32)
    # Avoid materializing a 240x240x15x3 intermediate array.
    chosen=np.ones((SIZE,SIZE),dtype=np.uint8)
    # Initialize with first palette distance.
    diff=pixels-pal[0]; best=np.sum(diff*diff,axis=2); chosen[:]=1
    for index,color in enumerate(pal[1:],2):
        diff=pixels-color; err=np.sum(diff*diff,axis=2); update=err<best
        chosen[update]=index; best=np.where(update,err,best)
    rs=native_radius
    mask=(rs>=INNER)&(rs<=OUTER)&(np.asarray(alpha)>=3)
    chosen[~mask]=0
    packed=(chosen[:,0::2] | (chosen[:,1::2]<<4)).astype(np.uint8).tobytes()
    # Development PNGs and contact sheets must represent the selected
    # firmware palette, not a higher-luminance intermediate that the device
    # never displays.
    palette_rgb=np.array([((v>>16)&255,(v>>8)&255,v&255)
                          for v in palette],dtype=np.uint8)
    device_rgb=palette_rgb[chosen]
    device_rgba=np.empty((SIZE,SIZE,4),dtype=np.uint8)
    device_rgba[:,:,:3]=device_rgb
    device_rgba[:,:,3]=np.where(chosen==0,0,255)
    rgba=Image.fromarray(device_rgba,"RGBA")
    return rgba,packed,palette


def _write_palette_module(palettes,path):
    lines=['"""Generated by tools/generate_hud_bezels.py; do not edit."""','PALETTES = {']
    for name,values in palettes.items():
        lines.append("    {!r}: ({}),".format(name,", ".join("0x%06X"%v for v in values)))
    lines.extend(["}","DEFAULT_BEZEL = 'cyan_reactor'",""])
    path.write_text("\n".join(lines),encoding="utf-8")


def _contact_sheet(directory,destination):
    sheet=Image.new("RGB",(960,990),(8,12,20)); draw=ImageDraw.Draw(sheet)
    dark=Image.new("RGB",(960,990),(1,3,8)); dark_draw=ImageDraw.Draw(dark)
    try: font=ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf",13)
    except OSError: font=ImageFont.load_default()
    for i,(name,label,*_) in enumerate(THEMES):
        x=20+(i%4)*240; y=14+(i//4)*320
        panel=Image.new("RGB",(SIZE,SIZE),(5,8,14)); d=ImageDraw.Draw(panel)
        for yy in range(0,SIZE,12):
            for xx in range(0,SIZE,12):
                if ((xx+yy)//12)%2: d.rectangle((xx,yy,xx+11,yy+11),fill=(15,20,29))
        art=Image.open(directory/(name+".png")).convert("RGBA")
        panel=Image.alpha_composite(panel.convert("RGBA"),art).convert("RGB")
        sheet.paste(panel,(x,y))
        draw.text((x,y+245),label,font=font,fill=(224,237,248))
        draw.text((x,y+264),name,font=font,fill=(117,164,198))
        black_panel=Image.new("RGBA",(SIZE,SIZE),(1,3,8,255))
        black_panel=Image.alpha_composite(black_panel,art).convert("RGB")
        dark.paste(black_panel,(x,y))
        dark_draw.text((x,y+245),label,font=font,fill=(224,237,248))
        dark_draw.text((x,y+264),name,font=font,fill=(117,164,198))
    sheet.save(destination,optimize=True)
    dark.save(destination.with_name("contact-sheet-black.png"),optimize=True)


def generate(output,supersample=8,overrides=None):
    output=Path(output); runtime=output/"runtime"; dev=output/"development"
    runtime.mkdir(parents=True,exist_ok=True); dev.mkdir(parents=True,exist_ok=True)
    start=time.perf_counter(); palettes={}; entries=[]
    orbit_file = runtime / "orbit_phases.4bpp"
    orbit_data = orbit_phase_data()
    orbit_file.write_bytes(orbit_data)
    rotor_file = runtime / "rotor_segment_phases.4bpp"
    rotor_data = rotor_segment_data()
    rotor_file.write_bytes(rotor_data)
    for item in THEMES:
        name,label,primary,secondary,kind=item
        if overrides and name in overrides:
            primary,secondary=overrides[name]
        item=(name,label,primary,secondary,kind)
        image,data,palette=render(item,supersample)
        image.save(dev/(name+".png"),optimize=True)
        (runtime/(name+".4bpp")).write_bytes(data); palettes[name]=palette
        entries.append({"name":name,"label":label,"file":"assets/round_hud/runtime/{}.4bpp".format(name),
                        "development_png":"assets/round_hud/development/{}.png".format(name),
                        "width":SIZE,"height":SIZE,"format":"row-major indexed 4bpp, least-significant nibble first",
                        "transparent_index":0,"palette_entries":16,
                        "palette_rgb888":["#%06x"%value for value in palette],
                        "bytes":len(data)})
    _write_palette_module(palettes,ROOT/"src/display/round_ui/bezel_palette.py")
    _contact_sheet(dev,output/"contact-sheet.png")
    manifest={"generator":"tools/generate_hud_bezels.py","generator_version":6,"target":[SIZE,SIZE],
              "supersampling":supersample,"palette_entries":16,
              "bezel_palette_luminance":BEZEL_LUMINANCE,
              "default":"cyan_reactor","themes":entries,
              "sprite_assets":[{"name":"orbit_phases","file":"assets/round_hud/runtime/orbit_phases.4bpp",
                                "width":36,"height":36,"tile_size":9,"tiles":16,
                                "palette_entries":16,"transparent_index":0,"bytes":len(orbit_data)},
                               {"name":"rotor_segment_phases","file":"assets/round_hud/runtime/rotor_segment_phases.4bpp",
                                "width":132,"height":3168,"tile_size":33,"tiles":384,
                                "orientations":24,"subpixel_phases":16,
                               "instances":12,"track_radius_px":110,
                               "arc_length_px":29,"angular_offset_degrees":29,
                                "palette_entries":16,"transparent_index":0,"bytes":len(rotor_data)}],
              "generation_seconds":round(time.perf_counter()-start,3)}
    (output/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=ROOT/"assets/round_hud")
    parser.add_argument("--supersample",type=int,choices=(4,8),default=8)
    parser.add_argument("--palette-json",type=Path,
                        help="optional JSON mapping theme names to primary/secondary hex colors")
    args=parser.parse_args()
    overrides=None
    if args.palette_json:
        raw=json.loads(args.palette_json.read_text(encoding="utf-8"))
        overrides={name:(tuple(int(raw[name][key].lstrip("#")[i:i+2],16)
                              for i in (0,2,4)) for key in ("primary","secondary"))
                   for name in raw}
    manifest=generate(args.output,args.supersample,overrides)
    print("Generated {} 240x240 themes in {:.3f}s; {} bytes/theme".format(
        len(manifest["themes"]),manifest["generation_seconds"],manifest["themes"][0]["bytes"]))
    print(args.output/"contact-sheet.png")


if __name__=="__main__": main()
