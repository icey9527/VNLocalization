#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sfo_view.py -- SFO 字库查看器（渲染成 PNG 检查用）

SFO 结构（详见 ..\\docs\\字库SFO格式.md）:
  +0x00 "SFO\\0"
  +0x04 u32 字形高度 H
  +0x08 u32 条目数 N
  +0x10 int16[256] 前导表 lead[]   (0x8001 = 无此块)
  +0x210 Entry[N]*4  { u8 lead; u8 width; u16 texslot }
  字形像素: 文件偏移 = texslot*16; 行字节 = 2*ceil(width/4); 高 = H; 4bpp 高半字节在左

查字: idx = lead[前导字节] + 后字节；要求 entry[idx].lead == 前导字节。
字符 -> 码位: 优先查 font.tbl（映射后的码表），查不到回退 cp932。

用法:
  python sfo_view.py glyph <sfo> <码位 或 字符> <out.png> [scale]
  python sfo_view.py sheet <sfo> <out.png> [count] [start]
  python sfo_view.py text  <sfo> "<文本>" <out.png> [scale]
  python sfo_view.py dump  <sfo> <outdir>
"""
import os
import struct
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
TBL = HERE / 'font.tbl'


def load_charmap(path=TBL):
    """字符 -> 码位（用映射后的码表；查不到回退 cp932）"""
    m = {}
    if Path(path).is_file():
        raw = Path(path).read_bytes()
        txt = raw.decode('utf-16') if raw[:2] in (b'\xff\xfe', b'\xfe\xff') \
            else raw.decode('utf-8-sig')
        for line in txt.splitlines():
            line = line.strip()
            if not line or line.startswith(('#', ';', '//')) or '=' not in line:
                continue
            key, val = line.split('=', 1)
            val = val.split(';', 1)[0].strip()
            if len(val) == 1:
                try:
                    m[val] = int(key.strip(), 16)
                except ValueError:
                    pass
    return m


CHARMAP = load_charmap()


def char_code(ch):
    """字符 -> 码位（int）；None = 无法定位"""
    if ch in CHARMAP:
        return CHARMAP[ch]
    try:
        b = ch.encode('cp932')
    except UnicodeEncodeError:
        return None
    return b[0] if len(b) == 1 else (b[0] << 8) | b[1]


def load(path):
    d = open(path, 'rb').read()
    assert d[:4] == b'SFO\x00', 'not SFO'
    H = struct.unpack_from('<I', d, 4)[0]
    N = struct.unpack_from('<I', d, 8)[0]
    lead = [struct.unpack_from('<h', d, 16 + 2 * i)[0] for i in range(256)]
    ents, order = {}, []
    for i in range(N):
        l = d[0x210 + 4 * i]
        if l == 0xff:
            continue
        w = d[0x210 + 4 * i + 1]
        ts = struct.unpack_from('<H', d, 0x210 + 4 * i + 2)[0]
        ents[i] = (l, w, ts)
        order.append(i)
    return d, H, N, lead, ents, order


def index_of(lead, code):
    """码位 -> 字形 index；-1 = 没有"""
    if code < 0x80:
        i = lead[0] + code
        return i if lead[0] != -32767 else -1
    b1, b2 = (code >> 8) & 0xff, code & 0xff
    base = lead[b1]
    if base == -32767:
        return -1
    return base + b2


def find(lead, ents, code):
    """码位 -> 条目；返回 None 表示查不到"""
    i = index_of(lead, code)
    if i < 0 or i not in ents:
        return None
    lb, w, ts = ents[i]
    if lb != ((code >> 8) & 0xff if code >= 0x80 else 0):
        return None
    return ents[i]


def glyph_img(d, H, w, ts):
    """返回 width×H 的 8bit 图像（值 0..15）。4bpp 小端: 低半字节 = 左像素。"""
    stride = 2 * ((w + 3) // 4)
    p = ts * 16
    img = Image.new('L', (stride * 2, H), 0)
    px = img.load()
    for r in range(H):
        for c in range(stride * 2):
            q = p + r * stride + c // 2
            v = 0
            if 0 <= q < len(d):
                v = (d[q] & 0xf) if c % 2 == 0 else (d[q] >> 4)
            px[c, r] = v * 17
    return img


def cmd_glyph(sfo, what, out, scale=4):
    d, H, N, lead, ents, order = load(sfo)
    code = int(what, 16) if what.lower().startswith('0x') or _is_hex(what) \
        else char_code(what)
    e = find(lead, ents, code)
    if e is None:
        print('码位 %04X (%s) 在原库里查不到' % (code, what))
        return
    lb, w, ts = e
    img = glyph_img(d, H, w, ts)
    img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    img.save(out)
    print('wrote %s %s  (码位 %04X, width=%d, ts=%d)' % (out, img.size, code, w, ts))


def _is_hex(s):
    try:
        int(s, 16)
        return len(s) >= 4
    except ValueError:
        return False


def cmd_sheet(sfo, out, count=256, start=0):
    d, H, N, lead, ents, order = load(sfo)
    order = order[start:start + int(count)]
    cw = max(2 * ((ents[i][1] + 3) // 4) * 2 for i in order) * 4 + 6
    ch_ = H * 4 + 6
    cols = 24
    rows = (len(order) + cols - 1) // cols
    sheet = Image.new('L', (cols * cw, rows * ch_), 20)
    for k, i in enumerate(order):
        lb, w, ts = ents[i]
        im = glyph_img(d, H, w, ts).resize((2 * ((w + 3) // 4) * 2 * 4, H * 4), Image.NEAREST)
        sheet.paste(im, ((k % cols) * cw + 3, (k // cols) * ch_ + 3))
    sheet.save(out)
    print('wrote %s %s' % (out, sheet.size))


def cmd_text(sfo, text, out, scale=4):
    d, H, N, lead, ents, order = load(sfo)
    segs = []
    for ch in text:
        if ch == '\n':
            segs.append(None)
            continue
        code = char_code(ch)
        segs.append(find(lead, ents, code) if code is not None else None)
    rows = [[]]
    for sgm in segs:
        if sgm is None:
            rows.append([])
            continue
        rows[-1].append(sgm)
    line_h = H * scale
    width = max((sum(8 if g is None else g[1] for g in r) for r in rows), default=1)
    img = Image.new('L', (max(1, width), max(1, line_h * len(rows))), 0)
    y = 0
    for r in rows:
        x = 0
        for g in r:
            if g is None:
                x += 8 * scale
                continue
            lb, w, ts = g
            im = glyph_img(d, H, w, ts).resize((w * scale, H * scale), Image.NEAREST)
            img.paste(im, (x, y))
            x += w * scale
        y += line_h
    img = img.resize((img.width * 2, img.height * 2), Image.NEAREST)
    img.save(out)
    print('wrote %s %s' % (out, img.size))


def cmd_dump(sfo, outdir):
    d, H, N, lead, ents, order = load(sfo)
    os.makedirs(outdir, exist_ok=True)
    for i in order:
        lb, w, ts = ents[i]
        glyph_img(d, H, w, ts).save(os.path.join(outdir, '%04d.png' % i))
    print('dumped %d glyphs to %s' % (len(order), outdir))


if __name__ == '__main__':
    a = sys.argv
    if len(a) < 3:
        print(__doc__)
        sys.exit(1)
    if a[1] == 'glyph' and len(a) >= 5:
        cmd_glyph(a[2], a[3], a[4], int(a[5]) if len(a) > 5 else 4)
    elif a[1] == 'sheet':
        cmd_sheet(a[2], a[3], a[4] if len(a) > 4 else 256, a[5] if len(a) > 5 else 0)
    elif a[1] == 'text':
        cmd_text(a[2], a[3], a[4], int(a[5]) if len(a) > 5 else 4)
    elif a[1] == 'dump':
        cmd_dump(a[2], a[3])
    else:
        print(__doc__)
