"""Render source/candidate top views of the two faceplate locators."""
import re
import struct
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path("/private/tmp/pendant-hardware-integration/hardware/freecad")
BEFORE = Path("/tmp/faceplate-locators-leadin-before.stl")
AFTER = Path("/tmp/faceplate-locators-leadin-after.stl")
OUT = ROOT / "reports/faceplate-locators-leadin-before-after.png"
W, H = 1280, 900
PART = (43, 147, 178)

def read_stl(path):
    text = path.read_text(errors="replace")
    verts = re.findall(r"vertex\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)", text)
    if not verts:
        raw = path.read_bytes()
        n = struct.unpack_from("<I", raw, 80)[0]
        a = np.empty((n, 3, 3), dtype=float)
        for i in range(n):
            rec = struct.unpack_from("<12fH", raw, 84 + 50*i)
            a[i] = np.asarray(rec[3:12]).reshape((3, 3))
        return a
    return np.asarray(verts, dtype=float).reshape((-1, 3, 3))

def font(size, bold=False):
    for p in (["/System/Library/Fonts/Supplemental/Arial Bold.ttf"] if bold else []) + ["/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Helvetica.ttc"]:
        try: return ImageFont.truetype(p, size)
        except OSError: pass
    return ImageFont.load_default()

def draw_top(img, tris, box, center, half=4.2):
    x0,y0,x1,y1=box
    normals=np.cross(tris[:,1]-tris[:,0],tris[:,2]-tris[:,0])
    normals/=np.maximum(np.linalg.norm(normals,axis=1)[:,None],1e-12)
    top=float(tris[:,:,2].max())
    keep=(normals[:,2]>.8)&(tris[:,:,2].min(axis=1)>top-1e-4)
    t=tris[keep]
    normals=normals[keep]
    cx,cy=center
    keep=((t[:,:,0].max(1)>=cx-half)&(t[:,:,0].min(1)<=cx+half)&(t[:,:,1].max(1)>=cy-half)&(t[:,:,1].min(1)<=cy+half))
    t=t[keep]
    normals=normals[keep]
    shade=np.clip(.78+.22*np.maximum(0,normals[:,2]),.78,1)
    colors=np.stack([PART[0]*shade,PART[1]*shade,PART[2]*shade],1).astype(int)
    scale=min((x1-x0-56)/(2*half),(y1-y0-64)/(2*half))
    px=(x1-x0)/2+(t[:,:,0]-cx)*scale
    py=(y1-y0)/2-(t[:,:,1]-cy)*scale
    layer=Image.new("RGB",(x1-x0,y1-y0),(255,255,255));d=ImageDraw.Draw(layer)
    order=np.argsort(t[:,:,2].mean(1))
    for i in order:
        pts=[(int(px[i,j]),int(py[i,j])) for j in range(3)]
        d.polygon(pts,fill=tuple(map(int,colors[i])))
    img.paste(layer,(x0,y0))

def main():
    before,after=read_stl(BEFORE),read_stl(AFTER)
    img=Image.new("RGB",(W,H),(246,248,251));d=ImageDraw.Draw(img)
    d.text((36,22),"Faceplate locators — screw-entry refinement",font=font(29,True),fill=(28,36,45))
    d.text((36,62),"Native tapered pockets: 0.15 mm radial × 0.15 mm deep at each exposed screw entry",font=font(17),fill=(74,86,98))
    panels=[(30,105,620,485),(660,105,1250,485),(30,515,620,895),(660,515,1250,895)]
    titles=["LOCATOR A — SOURCE","LOCATOR A — CANDIDATE","LOCATOR B — SOURCE","LOCATOR B — CANDIDATE"]
    centers=[(-28.76,26.5463),(26.0,65.0)]
    for b in panels:
        d.rounded_rectangle(b,radius=12,fill="white",outline=(205,214,222),width=2)
    for i,(box,center) in enumerate(zip((panels[0],panels[1],panels[2],panels[3]),(centers[0],centers[0],centers[1],centers[1]))):
        draw_top(img,before if i%2==0 else after,box,center)
    d=ImageDraw.Draw(img)
    for b,t in zip(panels,titles):
        d.text((b[0]+16,b[1]+12),t,font=font(18,True),fill=(37,48,60))
    img.save(OUT)
    print(OUT)
if __name__=="__main__": main()
