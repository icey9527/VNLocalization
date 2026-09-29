#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
font.py -- 按码表从零生成 SFO 字库

和女皇之刃的 font/font.py 同一个角色（码表 + 字符集 -> 字库），只是目标格式不同：
  女皇 : font.tbl -> 4bpp 平铺字库 0002.bin
  我们 : font.tbl -> PS2 的 SFO 字库 0CFC.sfo

流程（不依赖原版字库）:
  1) 从 charset.txt（tqjs 收集的全文本）取出用到的字符集
  2) 每个字符按 char.py 的规则算码位（和写回文本用的是同一套映射）
  3) 排 lead[]/条目表
  4) FreeType 渲 4bpp 字形 -> 写全新 SFO
  5) 字体里没有的字形 -> 统一指向"全角问号"那一格，最后一起打印出来

用法:
    python font.py <码表 font.tbl> <字符集 charset.txt> <输出 0CFC.sfo>
                   [--font TTF] [--size 20] [--h 22] [--w 22] [--gamma 0.85]

SFO 结构（详见 ..\\docs\\字库SFO格式.md）:
  +0x00 "SFO\\0"      +0x04 u32 字形高 H     +0x08 u32 条目数 N
  +0x10 i16[256] lead[]      (0x8001 = 无此块)
  +0x210 Entry[N] { u8 lead; u8 width; u16 texslot }
  字形区: 偏移 = texslot*16, 行字节 = 2*ceil(width/4), 高 = H
引擎查字: idx = lead[首字节] + 后字节; 校验 entry[idx].lead == 首字节
          单字节: idx = lead[0] + b, 要求 entry[idx].lead == 0
"""
import os
import struct
import sys
import base64
from pathlib import Path

try:
    import freetype
except ImportError:                                   # pragma: no cover
    print('需要 freetype-py，请先安装:  pip install freetype-py')
    raise SystemExit(2)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))                         # 根目录的 char.py
import char                                           # noqa: E402  码位映射（和写回共用）

# bat 里设了 PYTHONIOENCODING=gbk（cmd 936 码页），缺字清单里有日文汉字，
# 直接 print 会报 UnicodeEncodeError，这里兜一下底。
try:
    sys.stdout.reconfigure(errors='replace')
except Exception:
    pass

# ============================== 可调参数 ==============================
FONT_PATH    = 'C:/Users/Administrator/AppData/Local/Microsoft/Windows/Fonts/HuaKangFangYuanTiStdW7.ttf'
FONT_INDEX   = 0        # TTC 内的字体序号
FONT_SIZE_PX = 20       # 光栅化像素字号
TILE_H       = 22       # 字形高（= SFO 头 +0x04，和原版一致）
TILE_W       = 22       # 双字节字符宽度（原版就是 22）
GAMMA        = 0.85     # 灰度 -> 4bpp 的 gamma
MISSING_CH   = '？'     # 缺字替身（全角问号）
BASIC_ASCII  = ''.join(chr(c) for c in range(0x20, 0x7F))
MISSING_OUT  = HERE / 'missing.txt'    # 缺字清单
# =====================================================================

# 内置字形：字体文件里没有、但原版字库（backup/0CFC.sfo）里有的字符。
# 数据是原版 22x22 / stride12 / 4bpp 的字形原文（base64），
# 渲染时按当前 tile_w x tile_h 最近邻缩放，改字号也不用作废。
# 取字形用的是「标准 cp932 码位」：♪=81F4 †=81F5 ‡=81F6
# （注意别再用 8194/8195/8384——那是 ＃/＆/ヤ 的格子，取错过一次）
BUILTIN_GLYPHS = {
    '†': dict(w=22, stride=12, h=22,
              b64='AAAAAAAAAAAAAAAAAAAAIQEAACEBAAAAAADF7t4E1O7OBQAAAIDOR9ee3kfHjgAAAOMJAAD6CgAA6QMAANsAAACQAAAA0AsAAJ0AAAAAAAAAkA0AEF4AAAAAAAAAUB4AEF4AAAAAAAAAUB4AAJ0AAAAAAAAAkA0AANsAAAAAAAAA0AsAAOUBAAAAAAAA4QUAAOALAAAAAAAA6wAAAFBeAAAAAABQXgAAAADrAQAAAADhCwAAAADgDQAAAADtAAAAAAAgngAAAJAuAAAAAAAA5gsAAOsGAAAAAAAAYN4B0W4AAAAAAAAAANKu3gIAAAAAAAAAAADqCgAAAAAAAAAAAAAAAAAAAAAA'),
    '‡': dict(w=22, stride=12, h=22,
              b64='AAAAAAAAAAAAAAAAAAAAEAEAABEAAAAAAACz7s4ExO6+AwAAAGD+//99/f//bgAAAOL////P////7wIAAPn//////////wkAAPz//////////wwAAP7//////////w4AAP7//////////w4AAPz//////////wwAAPj//////////wgAAPT//////////wQAAND/////////3wAAAED/////////TwAAAAD5////////CQAAAADA///////PAAAAAAAg/v////8uAAAAAAAA5P///+8EAAAAAAAAQP7//04AAAAAAAAAANL/3wIAAAAAAAAAAADpCQAAAAAAAAAAAAAAAAAAAAAA'),
    '♪': dict(w=22, stride=12, h=22,
              b64='AAAAAAAAAAAAAAAAAAAAABACAAAAAAAAAAAAAEALAAAAAAAAAAAAAEBvAAAAAAAAAAAAAED/BgAAAAAAAAAAAED/bwAAAAAAAAAAAED//wYAAAAAAAAAAEBf/08AAAAAAAAAAEAP0v8BAAAAAAAAAEAPEP0KAAAAAAAAAEAPAPQPAAAAAAAAAEAPAPAPAAAAAAAAAEAPAPANAAAAAAAAAEAPAPMIAAAAAAAAAEAPAOkBAAAAAAAAAEAPID8AAAAAAAAAAIMP0AYAAAAAAAAAwf8PUgAAAAAAAAAA/f8NAAAAAAAAAAAw//8FAAAAAAAAAAAA/Y8AAAAAAAAAAAAAQQEAAAAAAAAA'),
}


def die(msg):
    print('错误: ' + msg)
    raise SystemExit(1)


def align16(x):
    return (x + 15) & ~15


def ch_to_code(ch, rhs_to_proxy):
    """字符 -> 码位；None = 码表里没有、cp932 也编不出来。

    规则和 char.py 完全一致：
      码位 < 0x889F 的字符（ASCII/假名/标点）直接用它的 cp932 码位；
      其余查码表，取"该码位的日文等值字符"再编回字节 —— 编出来就是码位。
    """
    if not char.is_cp932_proxy_char(ch):
        c = char.cp932_code(ch)
        if c is not None:
            return c
    proxy = rhs_to_proxy.get(ch)
    if proxy is None:
        return None
    b = proxy.encode("cp932")
    return b[0] if len(b) == 1 else (b[0] << 8) | b[1]


def read_text(path):
    raw = Path(path).read_bytes()
    if raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
        return raw.decode('utf-16')
    return raw.decode('utf-8-sig')


# ---------------------------------------------------------------- 布局

def layout(singles, doubles):
    """
    排 lead[]/条目表。引擎约束: idx = lead[b1] + b2，要求 idx >= 0 且
    entry[idx].lead == b1。lead[b1] 可以自由取值，所以不同前导字节的块
    可以共用槽位空间，只要各自用到的 idx 不撞。做法: 逐块找最靠前的
    不冲突位置塞进去。
    """
    lead = [-32767] * 256
    slot = {}          # idx -> 字符
    occupied = set()

    if singles:                                   # 单字节块: lead[0]=0
        lead[0] = 0
        for b, ch in singles:
            slot[b] = ch
        occupied |= set(slot)

    by_b1 = {}
    for b1, b2, ch in doubles:
        by_b1.setdefault(b1, []).append((b2, ch))
    blocks = []
    for b1, items in by_b1.items():
        b2s = sorted(b for b, _ in items)
        lo = b2s[0]
        shape = tuple(b - lo for b in b2s)
        blocks.append((len(shape), shape[-1], b1, items, lo, shape))
    blocks.sort(key=lambda x: (-x[0], -x[1], x[2]))

    for n, span, b1, items, lo, shape in blocks:
        base = 0
        while any((base + o) in occupied for o in shape):
            base += 1
        lead[b1] = base - lo
        for b2, ch in items:
            idx = base + (b2 - lo)
            slot[idx] = ch
            occupied.add(idx)

    return lead, slot


# ---------------------------------------------------------------- 渲染

class Renderer:
    def __init__(self, path, index, size_px, tile_w, tile_h, gamma):
        if not os.path.isfile(path):
            die('找不到字体文件: ' + path)
        # 工程路径带中文时 freetype-py 吃路径会失败，所以给它文件对象
        self._fh = open(path, 'rb')
        self.face = freetype.Face(self._fh, index=index)
        self.face.set_pixel_sizes(0, size_px)
        self.tile_w = tile_w
        self.tile_h = tile_h
        self.gamma = gamma
        asc = self.face.size.ascender >> 6
        desc = self.face.size.descender >> 6
        self.baseline = (tile_h - (asc - desc)) // 2 + asc

    def render(self, ch, force_full=False):
        """-> (width, 4bpp 字节, 有没有字形)。4bpp 小端: 低半字节 = 左像素。

        有没有字形看 get_char_index，**不能**看 bitmap 是不是空的 ——
        空格 / 全角空格 / 制表符这类本来就没像素，但它们是正经字形，
        按 bitmap 判会被误报成缺字。
        """
        if self.face.get_char_index(ord(ch)) == 0:
            if ch in BUILTIN_GLYPHS:                     # 原版字库抠来的内置字形
                return self._render_builtin(ch)
            return self.tile_w, bytes(2 * ((self.tile_w + 3) // 4) * self.tile_h), False

        self.face.load_char(ch, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_NORMAL)
        g = self.face.glyph
        bmp = g.bitmap
        rows, width, pitch = int(bmp.rows), int(bmp.width), int(bmp.pitch)

        aw = int(round(g.advance.x / 64.0))
        w = self.tile_w if force_full else max(1, aw)
        need = int(g.bitmap_left) + width
        if need > w:
            w = need
        w = max(1, min(self.tile_w, w))

        gray = bytearray(self.tile_h * w)
        try:
            buf = bmp.buffer
        except Exception:
            buf = None
        if buf:
            x0 = int(g.bitmap_left)
            y0 = self.baseline - int(g.bitmap_top)
            for y in range(rows):
                ty = y0 + y
                if ty < 0 or ty >= self.tile_h:
                    continue
                ro = (rows - 1 - y) * (-pitch) if pitch < 0 else y * pitch
                base = ty * w
                for x in range(width):
                    tx = x0 + x
                    if 0 <= tx < w:
                        gray[base + tx] = buf[ro + x]

        q = bytearray(min(15, int(((v / 255.0) ** self.gamma) * 15 + 0.5)) for v in gray)
        stride = 2 * ((w + 3) // 4)
        out = bytearray(stride * self.tile_h)
        for y in range(self.tile_h):
            gb, ob = y * w, y * stride
            for x in range(stride * 2):
                v = q[gb + x] if x < w else 0
                if x & 1:
                    out[ob + (x >> 1)] |= (v & 0xF) << 4
                else:
                    out[ob + (x >> 1)] |= v & 0xF
        return w, bytes(out), True

    def _render_builtin(self, ch):
        """内置字形（原版字库抠来的 4bpp 原文）-> 按当前格子尺寸最近邻缩放。

        原版数据已经是 4bpp 成品灰阶（0-15），所以这里不做 gamma ——
        gamma 只用于 freetype 的 8bpp 渲染结果。
        """
        info = BUILTIN_GLYPHS[ch]
        src = base64.b64decode(info['b64'])
        sw, sh, sst = info['w'], info['h'], info['stride']
        # 解包成 0-15 灰度矩阵
        gray = [[0] * sw for _ in range(sh)]
        for y in range(sh):
            row = gray[y]
            for xb in range(sst):
                v = src[y * sst + xb]
                x = xb * 2
                if x < sw:
                    row[x] = v & 0xF
                if x + 1 < sw:
                    row[x + 1] = (v >> 4) & 0xF
        # 最近邻缩放到 tile_h x tile_w
        w = self.tile_w
        q = bytearray(self.tile_h * w)
        for ty in range(self.tile_h):
            srow = gray[ty * sh // self.tile_h]
            base = ty * w
            for tx in range(w):
                q[base + tx] = srow[tx * sw // w]
        stride = 2 * ((w + 3) // 4)
        out = bytearray(stride * self.tile_h)
        for y in range(self.tile_h):
            gb, ob = y * w, y * stride
            for x in range(stride * 2):
                v = q[gb + x] if x < w else 0
                if x & 1:
                    out[ob + (x >> 1)] |= (v & 0xF) << 4
                else:
                    out[ob + (x >> 1)] |= v & 0xF
        return w, bytes(out), True


# ---------------------------------------------------------------- 组装

def build_sfo(lead, slot, rend, H, code_of, rep):
    N = max(slot) + 1 if slot else 0
    data_off = align16(0x210 + 4 * N)
    blob = bytearray()
    ents = {}

    def append(packed):
        nonlocal blob
        while (data_off + len(blob)) % 16:
            blob += b'\x00'
        ts = (data_off + len(blob)) // 16
        blob += packed
        return ts

    # 缺字替身: 全角问号的格子，缺字一律指到这儿
    w_q, pk_q, _ = rend.render(MISSING_CH, force_full=True)
    ts_q = append(pk_q)

    for idx in sorted(slot):
        ch = slot[idx]
        code = code_of[ch]
        full = code > 0xFF
        w, packed, ok = rend.render(ch, force_full=full)
        if not ok:
            rep['missing_font'].append(ch)
            w, ts = w_q, ts_q
        else:
            ts = append(packed)
        ents[idx] = (0 if code <= 0xFF else (code >> 8) & 0xFF, w, ts)

    out = bytearray(data_off)
    out[0:4] = b'SFO\x00'
    struct.pack_into('<I', out, 4, H)
    struct.pack_into('<I', out, 8, N)
    struct.pack_into('<I', out, 12, 0)
    for i in range(256):
        struct.pack_into('<h', out, 0x10 + 2 * i, lead[i])
    for idx in range(N):
        p = 0x210 + 4 * idx
        if idx in ents:
            lb, w, ts = ents[idx]
            out[p] = lb
            out[p + 1] = w
            struct.pack_into('<H', out, p + 2, ts)
        else:
            out[p] = 0xFF
    out += blob
    rep['N'] = N
    rep['glyphs'] = len(slot) + 1
    return bytes(out)


def verify(data, slot, code_of):
    N = struct.unpack_from('<I', data, 8)[0]
    lead = [struct.unpack_from('<h', data, 0x10 + 2 * i)[0] for i in range(256)]
    failed = 0
    for idx, ch in slot.items():
        e = code_of[ch]
        lb, b = (0, e) if e <= 0xFF else ((e >> 8) & 0xFF, e & 0xFF)
        i2 = lead[lb] + b
        if not (0 <= i2 < N) or data[0x210 + 4 * i2] != lb:
            failed += 1
    return failed


# ---------------------------------------------------------------- 主流程

def main():
    argv = sys.argv[1:]

    def opt(name, default):
        if name in argv:
            i = argv.index(name)
            v = argv[i + 1]
            del argv[i:i + 2]
            return v
        return default

    font_path = opt('--font', FONT_PATH)
    size_px = int(opt('--size', FONT_SIZE_PX))
    tile_h = int(opt('--h', TILE_H))
    tile_w = int(opt('--w', TILE_W))
    gamma = float(opt('--gamma', GAMMA))

    if len(argv) < 3:
        print(__doc__)
        return 1
    tbl_path, charset_path, out_sfo = argv[0], argv[1], argv[2]

    rep = dict(missing_font=[])
    print('=' * 62)
    print('SFO 字库生成（从零生成）')
    print('=' * 62)

    # 码位映射表：和写回文本共用 char.py 的同一份（根目录 font.tbl）
    rhs_to_proxy = char.load_map(char.MAP_PATH)
    code_of = {}
    chars = set(BASIC_ASCII)
    for ch in read_text(charset_path):
        if ord(ch) >= 0x20:
            # 和写回用同一套等价替换（·→・、—→─ 等），两边必须完全一致，
            # 否则字库里没有这个字形的格子，游戏里会显示空白
            chars.add(char.apply_replace_rules(ch))
    no_code = []
    for ch in chars:
        c = ch_to_code(ch, rhs_to_proxy)
        if c is None:
            no_code.append(ch)
        else:
            code_of[ch] = c
    # 码表里没码位的字没法排格子，直接不进字库
    chars = sorted(set(code_of))
    print('码表    : %s' % tbl_path)
    print('字符集  : %s -> 用到的字符 %d 个（%d 个没码位）'
          % (charset_path, len(chars), len(no_code)))

    singles = sorted((c & 0xFF, ch) for ch, c in code_of.items() if c <= 0xFF)
    doubles = sorted(((c >> 8) & 0xFF, c & 0xFF, ch)
                     for ch, c in code_of.items() if c > 0xFF)
    lead, slot = layout(singles, doubles)
    N = max(slot) + 1 if slot else 0
    data_off = align16(0x210 + 4 * N)
    print('布局    : 条目 %d 个（单字节 %d + 双字节 %d），字形区起点 %#x'
          % (N, len(singles), len(doubles), data_off))

    print('光栅化  : %s (%dpx) -> %dx%d' % (font_path, size_px, tile_w, tile_h))
    rend = Renderer(font_path, FONT_INDEX, size_px, tile_w, tile_h, gamma)
    data = build_sfo(lead, slot, rend, tile_h, code_of, rep)

    if rep['missing_font']:
        miss = sorted(set(rep['missing_font']))
        print('  字体里没有的字形 %d 个 -> 全部指向全角问号那一格:'
              % len(miss))
        print('    ' + ''.join(miss))

    failed = verify(data, slot, code_of)
    out = Path(out_sfo)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    print()
    print('已写出 %s  (%d 字节, %.0f KB, 字形 %d 个)'
          % (out_sfo, len(data), len(data) / 1024.0, rep['glyphs']))

    miss_all = sorted(set(rep['missing_font']) | set(no_code))
    MISSING_OUT.write_text(''.join(miss_all) + '\n', encoding='utf-8')
    if no_code:
        print('码表里没码位的字 %d 个（字库放不进去）: %s'
              % (len(no_code), ''.join(sorted(no_code))))
    print('缺字清单 -> %s (%d 个)' % (MISSING_OUT, len(miss_all)))
    if failed:
        print('注意: 有 %d 个字符查不回来' % failed)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
