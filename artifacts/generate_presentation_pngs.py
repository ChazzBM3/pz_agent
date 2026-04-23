import json
import math
import struct
import zlib
from pathlib import Path

ROOT = Path('/Users/chazzm3/.openclaw/workspace/pz_agent/artifacts/presentation_kg')
ROOT.mkdir(parents=True, exist_ok=True)
summary = json.loads((ROOT / 'phenothiazine_summary.json').read_text())
shortlist = json.loads((ROOT / 'phenothiazine_priority_shortlist.json').read_text())

W, H = 1400, 900

class Canvas:
    def __init__(self, w, h, bg=(255,255,255)):
        self.w=w; self.h=h
        self.p=[ [list(bg) for _ in range(w)] for __ in range(h)]
    def rect(self, x,y,w,h,c):
        x=max(0,int(x)); y=max(0,int(y)); w=int(w); h=int(h)
        for yy in range(max(0,y), min(self.h,y+h)):
            row=self.p[yy]
            for xx in range(max(0,x), min(self.w,x+w)):
                row[xx]=list(c)
    def vline(self,x,y0,y1,c,th=1):
        self.rect(x,y0,th,max(1,y1-y0),c)
    def hline(self,x0,x1,y,c,th=1):
        self.rect(x0,y,max(1,x1-x0),th,c)
    def save_png(self,path):
        raw=b''.join(b'\x00'+bytes([ch for px in row for ch in px]) for row in self.p)
        def chunk(tag,data):
            return struct.pack('!I',len(data))+tag+data+struct.pack('!I', zlib.crc32(tag+data)&0xffffffff)
        png=b'\x89PNG\r\n\x1a\n'
        png+=chunk(b'IHDR', struct.pack('!IIBBBBB', self.w, self.h, 8, 2, 0, 0, 0))
        png+=chunk(b'IDAT', zlib.compress(raw, 9))
        png+=chunk(b'IEND', b'')
        Path(path).write_bytes(png)

def draw_digit(cv, x, y, s, digit, color):
    segs={
      '0':'abcfed','1':'bc','2':'abged','3':'abgcd','4':'fgbc','5':'afgcd','6':'afgcde','7':'abc','8':'abcdefg','9':'abfgcd'
    }
    on=set(segs[str(digit)])
    t=max(2,s//6)
    if 'a' in on: cv.rect(x+t,y,s-2*t,t,color)
    if 'b' in on: cv.rect(x+s-t,y+t,t,s//2-t,color)
    if 'c' in on: cv.rect(x+s-t,y+s//2,t,s//2-t,color)
    if 'd' in on: cv.rect(x+t,y+s-t,s-2*t,t,color)
    if 'e' in on: cv.rect(x,y+s//2,t,s//2-t,color)
    if 'f' in on: cv.rect(x,y+t,t,s//2-t,color)
    if 'g' in on: cv.rect(x+t,y+s//2-t//2,s-2*t,t,color)

def draw_number(cv, x, y, s, text, color):
    dx=0
    for ch in text:
        if ch.isdigit():
            draw_digit(cv, x+dx, y, s, ch, color)
            dx += s + max(4, s//5)
        elif ch=='.':
            cv.rect(x+dx+s//3, y+s+4, max(2,s//6), max(2,s//6), color)
            dx += s//2
        elif ch==',':
            cv.rect(x+dx+s//3, y+s+4, max(2,s//6), max(2,s//6), color)
            cv.rect(x+dx+s//4, y+s+8, max(2,s//6), max(2,s//6), color)
            dx += s//2
        elif ch=='/':
            for i in range(s):
                xx=x+dx+i//2; yy=y+s-i
                if 0<=xx<cv.w and 0<=yy<cv.h: cv.rect(xx,yy,2,2,color)
            dx += s//2
        else:
            dx += s//2

def make_coverage_chart():
    cv=Canvas(W,H,(250,250,252))
    cv.rect(80,80,1240,740,(255,255,255))
    props=list(summary['property_coverage'].items())[:8]
    maxv=max(v for _,v in props)
    bar_x=220; bar_y=180; bar_h=52; gap=24; scale=900/maxv
    palette=[(64,99,216),(88,144,255),(90,200,250),(94,92,230),(172,142,255),(48,176,199),(53,132,228),(50,173,230)]
    for i,(name,val) in enumerate(props):
        y=bar_y+i*(bar_h+gap)
        cv.rect(bar_x,y,int(val*scale),bar_h,palette[i%len(palette)])
        draw_number(cv, 90, y+6, 34, str(val), (30,30,30))
    out=ROOT/'phenothiazine_property_coverage.png'
    cv.save_png(out)
    return out

def make_shortlist_chart():
    cv=Canvas(W,H,(250,250,252))
    cv.rect(80,80,1240,740,(255,255,255))
    vals=[r['oxidation_potential'] for r in shortlist[:5]]
    maxv=max(vals)
    base_y=700; x0=180; bw=140; gap=90; scale=420/maxv
    colors=[(64,99,216),(88,144,255),(90,200,250),(172,142,255),(48,176,199)]
    cv.hline(130,1240,700,(180,180,190),4)
    for i,row in enumerate(shortlist[:5]):
        h=int(row['oxidation_potential']*scale)
        x=x0+i*(bw+gap)
        cv.rect(x, base_y-h, bw, h, colors[i])
        draw_number(cv, x+20, base_y-h-60, 28, f"{row['oxidation_potential']:.3f}", (30,30,30))
        draw_number(cv, x+35, base_y+20, 22, str(i+1), (60,60,60))
    out=ROOT/'phenothiazine_shortlist_oxidation.png'
    cv.save_png(out)
    return out

cov=make_coverage_chart()
sho=make_shortlist_chart()
print(str(cov))
print(str(sho))
