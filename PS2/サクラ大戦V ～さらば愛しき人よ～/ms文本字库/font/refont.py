import sys
import os
import freetype
from dataclasses import dataclass
from pathlib import Path

def u16le(b, o): return int.from_bytes(b[o:o+2], "little")
def u32le(b, o): return int.from_bytes(b[o:o+4], "little")

@dataclass
class Chunk:
    off: int; tag: bytes; size: int; data_off: int
    @property
    def data_start(self): return self.off + self.data_off
    @property
    def end(self): return self.off + self.data_off + self.size

@dataclass
class Core:
    sfnt: Chunk; mfnt0: Chunk; mfnt1: Chunk; mfnt2: Chunk; mfgt: Chunk
    glyph_count: int; w1: int; h1: int; m1: int; tbl0: int; tbl1: int

def read_chunk(b, off):
    return Chunk(off, b[off:off+4], u32le(b, off+4), u32le(b, off+8))

def parse_sfnt(b, start_off):
    sfnt = read_chunk(b, start_off)
    p, inner = sfnt.data_start, []
    while p < sfnt.end:
        c = read_chunk(b, p)
        inner.append(c)
        p = c.end
        if c.tag == b"EOFC": break
    m0, m1, m2, mg = inner[0], inner[1], inner[2], inner[3]
    gc = 224 if (u16le(b, m0.off + 0x0E) & 2) else 96
    return Core(sfnt, m0, m1, m2, mg, gc,
                u16le(b, m1.off+0x12), u16le(b, m1.off+0x10), u32le(b, m1.off+0x1C),
                u32le(b, m1.off+0x14), u32le(b, m1.off+0x18))

def mfnt1_ptr(c, code, s1):
    if 0x8140 <= code < 0x83A0: return c.mfnt1.off + 0x20 + (code - 0x8140) * s1 - (((code - 0x8140) >> 8) << 6) * s1
    if 0x8890 <= code < 0x9000: return c.mfnt1.off + c.tbl0 + (code & 0xFF) * s1 + 192 * (((code - 0x8800) >> 8)) * s1 - 144 * s1
    if 0x9040 <= code < 0x9880: return c.mfnt1.off + c.tbl1 + (code & 0xFF) * s1 + 192 * (((code - 0x9000) >> 8)) * s1 - 64 * s1
    return None

def get_mfgt_mapping(b, mfgt):
    pairs = {}
    for i in range(mfgt.size // 8):
        cp = u32le(b, mfgt.data_start + i * 8)
        of = u32le(b, mfgt.data_start + i * 8 + 4)
        if cp == 0 and of == 0: break
        pairs[cp] = of
    return pairs

def encode_tile(px, w, h, mode):
    if mode == 16:
        out = bytearray((w * h + 1) // 2)
        for i in range(0, w * h, 2): out[i//2] = ((max(0, min(15, px[i])) & 0xF) << 4) | (max(0, min(15, px[i + 1])) & 0xF)
        return bytes(out)
    if mode == 8:
        out = bytearray((w * h + 1) // 2)
        for i in range(0, w * h, 2): out[i//2] = (max(0, min(7, round(px[i]*7/15))) << 4) | max(0, min(7, round(px[i+1]*7/15)))
        return bytes(out)
    if mode == 4:
        out, j = bytearray((w * h + 3) // 4), 0
        for y in range(h):
            for x0 in range(0, w, 4):
                bb = 0
                for k in range(4): bb |= (max(0, min(3, round(px[y*w+x0+k]*3/15))) & 3) << (6 - 2 * k)
                out[j] = bb; j += 1
        return bytes(out)
    if mode == 2:
        out, j = bytearray((w * h + 7) // 8), 0
        for y in range(h):
            for x0 in range(0, w, 8):
                bb = 0
                for k in range(8): bb |= (1 if px[y*w+x0+k] >= 8 else 0) << (7 - k)
                out[j] = bb; j += 1
        return bytes(out)

def render_encoded(face, ch, w, h, mode):
    face.load_char(ch, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_NORMAL)
    bmp = face.glyph.bitmap
    tile = [0] * (w * h)
    asc, desc = face.size.ascender >> 6, face.size.descender >> 6
    x0 = 0 if bmp.width >= w else max(0, min(int(face.glyph.bitmap_left), w - int(bmp.width)))
    y0 = (h - (asc - desc)) // 2 + asc - int(face.glyph.bitmap_top)
    bw, bh, pitch, buf = int(bmp.width), int(bmp.rows), int(bmp.pitch), bmp.buffer
    
    for y in range(bh):
        ty = y0 + y
        if 0 <= ty < h:
            ro = ((bh - 1 - y) * (-pitch)) if pitch < 0 else y * pitch
            for x in range(bw):
                tx = x0 + x
                if 0 <= tx < w: tile[ty * w + tx] = max(0, min(15, round((buf[ro + x] / 255) * 15)))
    return encode_tile(tile, w, h, mode)

def parse_tbl(path):
    out = {}
    for line in path.read_text(encoding="utf-16", errors="ignore").splitlines():
        if "=" in line:
            l, r = line.split("=", 1)
            if l.strip() and r.strip():
                try: out[int(l.strip(), 16)] = r.strip()[0]
                except ValueError: pass
    return out

def main():
    if len(sys.argv) != 4:
        sys.exit("Usage: python sfnt_builder.py <input.bin> <in.tbl> <output.bin>")

    in_bin, tbl_path, out_bin = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    font_path = Path(os.getenv("LOCALAPPDATA")) / "Microsoft/Windows/Fonts/SOURCEHANSANSCN-MEDIUM.OTF"
    size_px = 24

    d = bytearray(in_bin.read_bytes())
    if d[:4] != b"GFRD":
        sys.exit("Error: 魔法头不是 GFRD")
        
    c = parse_sfnt(d, u32le(d, 0x08))
    
    face = freetype.Face(str(font_path))
    face.set_pixel_sizes(0, size_px)
    code_to_char = parse_tbl(tbl_path)
    
    s1 = (c.w1 * c.h1 * c.m1) >> 4
    mapping = get_mfgt_mapping(d, c.mfgt)

    count = 0
    for code, ch in code_to_char.items():
        if 0x20 <= code < 0x20 + c.glyph_count: continue
        
        ptr = mfnt1_ptr(c, code, s1)
        if ptr is None and code in mapping:
            # 【修复核心】：严格套用原版 GUI 作者测试通过的硬编码 + 0x10 偏移量
            ptr = c.mfnt2.off + 0x10 + mapping[code]
            
        if ptr and ptr + s1 <= len(d):
            d[ptr:ptr+s1] = render_encoded(face, ch, c.w1, c.h1, c.m1)
            count += 1
            
    out_bin.write_bytes(d)
    print(f"完成! 成功原地覆盖了 {count} 个字符的数据。")

if __name__ == "__main__":
    main()