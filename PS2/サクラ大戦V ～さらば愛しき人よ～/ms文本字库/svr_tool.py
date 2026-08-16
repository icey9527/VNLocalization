#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
svr_tool.py - 樱花大战 V (.dia / SVR / PVRT) 贴图双向转换工具

用法:
    python svr_tool.py e <dia目录> <png目录>        # .dia -> PNG (直接出图)
    python svr_tool.py i <原始dia目录> <png目录> <输出目录>   # PNG -> .dia

.dia 容器结构:
    [8B 块头: parent_magic(4)+hdr_size(4)][PVRT块]...
PVRT块: [可选GBIX 16B][PVRT头16B][可选内嵌调色板][纹理]
PVRT头: 'PVRT'(4) payload(u32) pixfmt(u8) datfmt(u8) rsvd(2) w(u16) h(u16)

codec 内核对齐 PuyoTools.Core.Textures.Svr (C#)。
依赖: numpy, Pillow, imagequant (pip install imagequant)
量化走 libimagequant (业界顶级, 原生支持 alpha), 对齐参考代码 QuantizeTo8bppWu:
  无抖动; alpha 参与量化, 透明与不透明天然分离。
"""

import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image
import imagequant

PVRT_MAGIC = b"PVRT"
GBIX_MAGIC = b"GBIX"

# ---------------------------------------------------------------------
# 格式枚举 (PVRT 偏移 0x08 像素格式 / 0x09 数据格式)
# ---------------------------------------------------------------------

def pixfmt_bpp(v):
    """直彩时每像素位深; Index 编码下不用。"""
    return {0x08: 16, 0x09: 32}.get(v)


def datafmt_bpp(df):
    """根据数据格式得 bpp。Rectangle=跟随pixfmt(返回None交调用方)。"""
    if df == 0x60:
        return None
    if df in (0x62, 0x66, 0x67, 0x68, 0x69):
        return 4
    if df in (0x64, 0x6A, 0x6B, 0x6C, 0x6D):
        return 8
    return None


def datafmt_palette_entries(df):
    if df in (0x62, 0x66, 0x67, 0x68, 0x69):
        return 16
    if df in (0x64, 0x6A, 0x6B, 0x6C, 0x6D):
        return 256
    return 0


def datafmt_is_index4(df):
    return df in (0x62, 0x66, 0x67, 0x68, 0x69)


def datafmt_is_index8(df):
    return df in (0x64, 0x6A, 0x6B, 0x6C, 0x6D)


def datafmt_needs_external_palette(df):
    return df in (0x62, 0x64)


# ---------------------------------------------------------------------
# Swizzler (DataSwizzler.cs 移植, numpy 向量化)
#   Swizzle  : dst[pos] = src[linear]
#   UnSwizzle: dst[linear] = src[pos]
#   仅当尺寸达标才生效: 4bpp W&H>=128; 8bpp W>=128&H>=64; 16bpp W&H>=64; 32bpp 永不
# ---------------------------------------------------------------------

class Swizzler:
    @staticmethod
    def _needs(w, h, bpp):
        if bpp == 4:
            return w >= 128 and h >= 128
        if bpp == 8:
            return w >= 128 and h >= 64
        if bpp == 16:
            return w >= 64 and h >= 64
        return False

    @staticmethod
    def _pos4(w, h):
        x = np.arange(w, dtype=np.int64)
        y = np.arange(h, dtype=np.int64)
        X, Y = np.meshgrid(x, y)
        pageX, pageY = X & ~0x7f, Y & ~0x7f
        pagesH = pagesV = (w + 127) // 128
        pageNum = (pageY // 128) * pagesH + (pageX // 128)
        pagePos = (pageNum // pagesV) * 32 * w * 2 + (pageNum % pagesV) * 64 * 4
        locX, locY = X & 0x7f, Y & 0x7f
        blockPos = ((locX & ~0x1f) >> 1) * w + (locY & ~0xf) * 2
        swapSel = (((Y + 2) >> 2) & 0x1) * 4
        yPos = (((Y & ~3) >> 1) + (Y & 1)) & 0x7
        coloumPos = yPos * w * 2 + ((X + swapSel) & 0x7) * 4
        byteNum = (X >> 3) & 3
        return (pagePos + blockPos + coloumPos + byteNum).ravel()

    @staticmethod
    def _pos8(w, h):
        x = np.arange(w, dtype=np.int64)
        y = np.arange(h, dtype=np.int64)
        X, Y = np.meshgrid(x, y)
        blockPos = (Y & ~0xf) * w + (X & ~0xf) * 2
        swapSel = (((Y + 2) >> 2) & 0x1) * 4
        yPos = (((Y & ~3) >> 1) + (Y & 1)) & 0x7
        coloumPos = yPos * w * 2 + ((X + swapSel) & 0x7) * 4
        byteNum = ((Y >> 1) & 1) + ((X >> 2) & 2)
        return (blockPos + coloumPos + byteNum).ravel()

    @staticmethod
    def _pos16(w, h):
        x = np.arange(w, dtype=np.int64)
        y = np.arange(h, dtype=np.int64)
        X, Y = np.meshgrid(x, y)
        pageX, pageY = X & ~0x3f, Y & ~0x3f
        pagesH = pagesV = (w + 63) // 64
        pageNum = (pageY // 64) * pagesH + (pageX // 64)
        pagePos = ((pageNum // pagesV) * 32 * w + (pageNum % pagesV) * 64) * 2
        locX, locY = X & 0x3f, Y & 0x3f
        blockPos = (locX & ~0xf) * w + (locY & ~0x7) * 2
        coloumPos = ((Y & 0x7) * w + (X & 0x7)) * 2
        byteNum = (X >> 3) & 1
        return (pagePos + blockPos + coloumPos + byteNum) * 2

    @staticmethod
    def swizzle(data, w, h, bpp):
        if not Swizzler._needs(w, h, bpp):
            return data
        a = np.frombuffer(data, dtype=np.uint8).copy()
        if bpp == 8:
            out = np.empty_like(a); out[Swizzler._pos8(w, h)] = a; return out.tobytes()
        if bpp == 16:
            out = np.empty_like(a); out[Swizzler._pos16(w, h)] = a; return out.tobytes()
        # 4bpp: 每像素独立字节偏移+位移
        x = np.arange(w, dtype=np.int64); y = np.arange(h, dtype=np.int64)
        X, Y = np.meshgrid(x, y); X = X.ravel(); Y = Y.ravel()
        pix = (a[(Y * w + X) // 2] >> ((X & 1) * 4)) & 0x0F           # 源: 线性字节, (x&1)*4 位移
        out = np.zeros(w * h // 2, dtype=np.uint8)
        np.bitwise_or.at(out, Swizzler._pos4(w, h), (pix << (((Y >> 1) & 1) * 4)).astype(np.uint8))
        return out.tobytes()

    @staticmethod
    def unswizzle(data, w, h, bpp):
        if not Swizzler._needs(w, h, bpp):
            return data
        a = np.frombuffer(data, dtype=np.uint8).copy()
        if bpp == 8:
            return a[Swizzler._pos8(w, h)].tobytes()
        if bpp == 16:
            return a[Swizzler._pos16(w, h)].tobytes()
        x = np.arange(w, dtype=np.int64); y = np.arange(h, dtype=np.int64)
        X, Y = np.meshgrid(x, y); X = X.ravel(); Y = Y.ravel()
        pix = (a[Swizzler._pos4(w, h)] >> (((Y >> 1) & 1) * 4)) & 0x0F  # 源: swizzled 字节
        out = np.zeros(w * h // 2, dtype=np.uint8)
        np.bitwise_or.at(out, (Y * w + X) // 2, (pix << ((X & 1) * 4)).astype(np.uint8))
        return out.tobytes()


# ---------------------------------------------------------------------
# Pixel codecs: 输入/输出统一 BGRA8888 (B,G,R,A), numpy 向量化
# ---------------------------------------------------------------------

def _rgb5a3_decode(words):
    """words: (N,) uint32 (已读出的16位字). 返回 (N,4) uint8 BGRA。"""
    is_rgb555 = (words & 0x8000) != 0
    R = np.where(is_rgb555, ((words >> 10) & 0x1F) * 0xFF // 0x1F,
                 ((words >> 8) & 0x0F) * 0xFF // 0x0F).astype(np.uint8)
    G = np.where(is_rgb555, ((words >> 5) & 0x1F) * 0xFF // 0x1F,
                 ((words >> 4) & 0x0F) * 0xFF // 0x0F).astype(np.uint8)
    B = np.where(is_rgb555, (words & 0x1F) * 0xFF // 0x1F,
                 (words & 0x0F) * 0xFF // 0x0F).astype(np.uint8)
    A = np.where(is_rgb555, 0xFF, ((words >> 12) & 0x07) * 0xFF // 0x07).astype(np.uint8)
    out = np.empty((words.size, 4), dtype=np.uint8)
    out[:, 0], out[:, 1], out[:, 2], out[:, 3] = B, G, R, A
    return out


def _rgb5a3_encode(bgra):
    """bgra: (N,4) BGRA. 返回 (N,) uint16 (待 .astype('<u2').tobytes())。"""
    B, G, R, A = (bgra[:, i].astype(np.uint32) for i in range(4))
    use3444 = A <= 0xDA  # 与 C# 一致
    p3444 = ((A >> 5) << 12) | ((R >> 4) << 8) | ((G >> 4) << 4) | (B >> 4)
    p555 = np.uint32(0x8000) | ((R >> 3) << 10) | ((G >> 3) << 5) | (B >> 3)
    return np.where(use3444, p3444, p555).astype(np.uint16)


def _argb8888_decode(arr):
    """arr: (N,4) 源字节序 (源按 R,G,B,A 存, A高位决定模式). 返回 BGRA。"""
    sR, sG, sB, sA = (arr[:, i].astype(np.uint32) for i in range(4))
    is_rgb = (sA & 0x80) != 0
    A = np.where(is_rgb, 0xFF, (sA << 1) & 0xFF).astype(np.uint8)
    out = np.empty_like(arr)
    out[:, 0], out[:, 1], out[:, 2], out[:, 3] = sB, sG, sR, A
    return out


def _argb8888_encode(bgra):
    """bgra: BGRA. 返回源字节序 (R,G,B,A)。"""
    B, G, R, A = (bgra[:, i].astype(np.uint32) for i in range(4))
    A_out = np.where(A < 0xFF, (A >> 1) & 0x7F, np.uint32(0x80)).astype(np.uint8)
    out = np.empty_like(bgra)
    out[:, 0], out[:, 1], out[:, 2], out[:, 3] = R, G, B, A_out
    return out


def decode_palette(raw, pixfmt):
    """raw调色板字节 -> (entries,4) BGRA。"""
    if pixfmt == 0x08:
        n = len(raw) // 2
        return _rgb5a3_decode(np.frombuffer(raw, dtype="<u2", count=n).astype(np.uint32))
    if pixfmt == 0x09:
        n = len(raw) // 4
        return _argb8888_decode(np.frombuffer(raw, dtype=np.uint8, count=n * 4).reshape(-1, 4).copy())
    raise ValueError(f"不支持调色板像素格式 0x{pixfmt:02X}")


def encode_palette(bgra, pixfmt):
    """(entries,4) BGRA -> 原始字节。"""
    if pixfmt == 0x08:
        return _rgb5a3_encode(bgra).astype("<u2").tobytes()
    if pixfmt == 0x09:
        return _argb8888_encode(bgra).tobytes()
    raise ValueError(f"不支持调色板像素格式 0x{pixfmt:02X}")


# ---------------------------------------------------------------------
# 量化: 精确调色板优先, 否则 libimagequant
#   对齐参考代码 QuantizeTo8bppWu: 无抖动; alpha 参与量化, 透明与不透明分离;
#   palette 不足补 0
# ---------------------------------------------------------------------

def _swap_index8_bits(idx):
    """Index8 bit3<->bit4 (C# AAABCAAA -> AAACBAAA)。"""
    return ((idx & 0xE7) | ((idx & 0x10) >> 1) | ((idx & 0x08) << 1)).astype(np.uint8)


def _liq_quantize(bgra, max_colors):
    """调 libimagequant 量化。bgra: (N,4) BGRA。
    返回 (indices(N,)u8, palette(K,4) BGRA)。

    对齐参考代码 QuantizeTo8bppWu:
      - dithering_level=0.0  (无抖动, 对应参考 Dither=null)
      - max_colors = 目标项数
      - libimagequant 原生支持 alpha, 透明/不透明/半透明各自独立, 不会合并
    用 quantize_raw_rgba_bytes: 返回的调色板含 alpha, 无需自己猜。
    """
    n = bgra.shape[0]
    if n == 0:
        return np.zeros((0,), dtype=np.uint8), np.zeros((max_colors, 4), dtype=np.uint8)
    
    # libimagequant 需要二维图像 (w*h >= n); 用近似正方形, 末尾补透明像素凑整
    h = int(np.floor(np.sqrt(n)))
    w = n // h
    # 确保 w*h >= n，否则补了像素但 w*h 对不上会报错
    if w * h < n:
        w += 1
    while w * h < n:
        w += 1
    
    pad_len = w * h - n
    if pad_len > 0:
        pad = np.zeros((pad_len, 4), dtype=np.uint8)
        bgra = np.concatenate([bgra, pad])
    rgba = np.ascontiguousarray(bgra[:, [2, 1, 0, 3]])  # BGRA->RGBA

    out_bytes, pal_flat = imagequant.quantize_raw_rgba_bytes(
        rgba.tobytes(), w, h,
        dithering_level=0.0, max_colors=max_colors)
    # libimagequant 返回的调色板数组固定 256 项; 实际用到前 max_colors 项,
    # 多余项是空槽。按 max_colors 截断 (调用方会再补 0)。
    indices = np.frombuffer(out_bytes, dtype=np.uint8)[:n]
    # 安全: 取实际用到的范围 (索引可能 < max_colors)
    used = int(indices.max()) + 1 if indices.size else 0
    cnt = min(max_colors, max(used, len(pal_flat) // 4))
    pal_rgba = np.array(pal_flat[:cnt * 4], dtype=np.uint8).reshape(-1, 4)
    pal_bgra = pal_rgba[:, [2, 1, 0, 3]].copy()
    return indices, pal_bgra


def quantize(bgra, max_colors):
    """bgra: (N,4) BGRA. 返回 (indices(N,)u8, palette(max_colors,4) BGRA, quantized(bool))。
    先精确(颜色数<=max直接建表, quantized=False), 否则 Wu (quantized=True)。
    精确路径用"像素首次出现顺序"建表, 以最大程度保留原始调色板顺序。"""
    keys = (bgra[:, 3].astype(np.uint64) << 24 | bgra[:, 2].astype(np.uint64) << 16
            | bgra[:, 1].astype(np.uint64) << 8 | bgra[:, 0].astype(np.uint64))
    uniq = np.unique(keys)
    if uniq.size <= max_colors:
        # 按像素首次出现顺序建表 (dict 保证唯一且保留插入顺序)
        seen = {}
        pal_list = []
        for k in keys:
            k = int(k)
            if k not in seen:
                seen[k] = len(pal_list)
                pal_list.append(k)
        indices = np.array([seen[int(k)] for k in keys], dtype=np.uint8)
        pal = np.zeros((max_colors, 4), dtype=np.uint8)
        pk = np.array(pal_list, dtype=np.uint64)
        pal[:pk.size, 0] = (pk & 0xFF).astype(np.uint8)
        pal[:pk.size, 1] = ((pk >> 8) & 0xFF).astype(np.uint8)
        pal[:pk.size, 2] = ((pk >> 16) & 0xFF).astype(np.uint8)
        pal[:pk.size, 3] = ((pk >> 24) & 0xFF).astype(np.uint8)
        return indices, pal, False

    indices, pal = _liq_quantize(bgra, max_colors)
    full = np.zeros((max_colors, 4), dtype=np.uint8)
    full[:pal.shape[0]] = pal
    return indices.astype(np.uint8), full, True


# ---------------------------------------------------------------------
# SVR 贴图: 解析/解码/编码
# ---------------------------------------------------------------------

class Svr:
    def __init__(self):
        self.global_index = None
        self.pixfmt = 0
        self.datafmt = 0
        self.width = 0
        self.height = 0
        self.palette_raw = b""
        self.texture_raw = b""

    @property
    def bpp(self):
        return datafmt_bpp(self.datafmt) or pixfmt_bpp(self.pixfmt)

    @property
    def palette_entries(self):
        return datafmt_palette_entries(self.datafmt)

    @property
    def needs_external_palette(self):
        return datafmt_needs_external_palette(self.datafmt)

    @classmethod
    def from_blob(cls, blob):
        """blob = 一个 PVRT 块的完整字节 (可含 GBIX, 长度 = 8+payload)。"""
        self = cls()
        off = 0
        if blob[:4] == GBIX_MAGIC:
            off = struct.unpack_from("<I", blob, 4)[0] + 8
            self.global_index = struct.unpack_from("<I", blob, 8)[0]
        if blob[off:off + 4] != PVRT_MAGIC:
            raise ValueError("缺 PVRT magic")
        payload = struct.unpack_from("<I", blob, off + 4)[0]
        self.pixfmt = blob[off + 8]
        self.datafmt = blob[off + 9]
        self.width = struct.unpack_from("<H", blob, off + 12)[0]
        self.height = struct.unpack_from("<H", blob, off + 14)[0]
        ds = off + 16
        bpp = self.bpp
        if self.palette_entries and not self.needs_external_palette:
            pal_bpp = pixfmt_bpp(self.pixfmt)
            n = self.palette_entries * pal_bpp // 8
            self.palette_raw = blob[ds:ds + n]
            ds += n
        need = self.width * self.height * bpp // 8
        self.texture_raw = blob[ds:ds + need]
        if len(self.texture_raw) != need:
            raise ValueError(f"纹理长度不足: 需{need} 实{len(self.texture_raw)}")
        return self

    def decode_rgba(self):
        """返回 (H,W,4) uint8 RGBA (PIL 直接可用)。"""
        tex = Swizzler.unswizzle(self.texture_raw, self.width, self.height, self.bpp)
        if self.datafmt == 0x60:  # 直彩
            flat = self._decode_direct(tex)
        elif datafmt_is_index4(self.datafmt) or datafmt_is_index8(self.datafmt):
            pal = decode_palette(self.palette_raw, self.pixfmt)
            if datafmt_is_index4(self.datafmt):
                a = np.frombuffer(tex, np.uint8)
                idx = np.empty(self.width * self.height, np.uint8)
                idx[0::2] = a & 0x0F; idx[1::2] = (a >> 4) & 0x0F
            else:
                idx = _swap_index8_bits(np.frombuffer(tex, np.uint8).copy())
            flat = pal[idx]
        else:
            raise ValueError(f"不支持解码 datafmt 0x{self.datafmt:02X}")
        bgra = flat.reshape(self.height, self.width, 4)
        return bgra[..., [2, 1, 0, 3]]  # BGRA->RGBA

    def _decode_direct(self, tex):
        if self.pixfmt == 0x08:
            n = self.width * self.height
            return _rgb5a3_decode(np.frombuffer(tex, "<u2", count=n).astype(np.uint32))
        if self.pixfmt == 0x09:
            n = self.width * self.height
            return _argb8888_decode(np.frombuffer(tex, np.uint8, count=n * 4).reshape(-1, 4).copy())
        raise ValueError(f"不支持直彩 pixfmt 0x{self.pixfmt:02X}")

    def to_png(self, out_path):
        Image.fromarray(self.decode_rgba(), "RGBA").save(out_path)

    @classmethod
    def from_png(cls, png_path, pixfmt, datafmt, global_index=None):
        img = Image.open(png_path).convert("RGBA")
        w, h = img.size
        rgba = np.asarray(img, np.uint8)
        bgra = rgba[..., [2, 1, 0, 3]].reshape(-1, 4).copy()
        self = cls()
        self.width, self.height = w, h
        self.pixfmt, self.datafmt = pixfmt, datafmt
        self.global_index = global_index
        self._bgra = bgra
        return self

    def encode_blob(self):
        """编码回完整 PVRT 块字节 (含 GBIX 若有)。
        返回 (blob, quantized) — quantized=True 表示走了 Wu 量化(有损)。"""
        bpp = self.bpp
        quantized = False

        if self.datafmt == 0x60:
            tex = self._encode_direct(self._bgra)
            pal_bytes = b""
        else:
            entries = self.palette_entries
            idx, pal, quantized = quantize(self._bgra, entries)
            pal_bytes = encode_palette(pal, self.pixfmt)
            if datafmt_is_index4(self.datafmt):
                # 每字节含两像素: 偶像素低4位, 奇像素高4位
                idx = (idx & 0x0F).astype(np.uint8)
                tex = (idx[0::2] | (idx[1::2] << 4)).tobytes()
            else:
                tex = _swap_index8_bits(idx).tobytes()

        tex = Swizzler.swizzle(tex, self.width, self.height, bpp)

        out = bytearray()
        if self.global_index is not None:
            out += GBIX_MAGIC + struct.pack("<III", 8, self.global_index, 0)
        out += PVRT_MAGIC
        out += struct.pack("<I", 8 + len(pal_bytes) + len(tex))
        out += struct.pack("<BB", self.pixfmt, self.datafmt)
        out += struct.pack("<HHH", 0, self.width, self.height)
        out += pal_bytes + tex
        return bytes(out), quantized

    def _encode_direct(self, bgra):
        if self.pixfmt == 0x08:
            return _rgb5a3_encode(bgra).astype("<u2").tobytes()
        if self.pixfmt == 0x09:
            return _argb8888_encode(bgra).tobytes()
        raise ValueError(f"不支持直彩 pixfmt 0x{self.pixfmt:02X}")


# ---------------------------------------------------------------------
# DIA 容器 (沿用 extract_pvrt.py 的扫描/回写结构, 直接对接 PNG)
# ---------------------------------------------------------------------

def u16le(buf, off): return struct.unpack_from("<H", buf, off)[0]
def u32le(buf, off): return struct.unpack_from("<I", buf, off)[0]


def find_all(buf, pat):
    out = []; start = 0
    while True:
        i = buf.find(pat, start)
        if i < 0:
            return out
        out.append(i); start = i + 1


def scan_pvrt(buf):
    """扫描 buf 中所有 PVRT 块, 返回 entry 列表 (含解码所需元数据)。"""
    entries = []
    for i, off in enumerate(find_all(buf, PVRT_MAGIC)):
        if off < 8:
            continue
        payload = u32le(buf, off + 4)
        end = off + 8 + payload
        if end > len(buf):
            continue
        try:
            svr = Svr.from_blob(buf[off:end])
        except Exception:
            continue
        entries.append({
            "index": i,
            "pvrt_off": off,
            "block_hdr_off": off - 8,
            "hdr_size": u32le(buf, off - 8),
            "payload": payload,
            "pixfmt": svr.pixfmt,
            "datafmt": svr.datafmt,
            "width": svr.width,
            "height": svr.height,
            "end": end,
            "bpp": svr.bpp,
            "palette_entries": svr.palette_entries,
            "needs_external_palette": svr.needs_external_palette,
            "global_index": svr.global_index,
        })
    return entries


def _indent(elem, level=0):
    ind = "\n" + "  " * level
    if len(elem):
        if not (elem.text and elem.text.strip()):
            elem.text = ind + "  "
        for c in elem:
            _indent(c, level + 1)
        if not (c.tail and c.tail.strip()):
            c.tail = ind
    elif level and not (elem.tail and elem.tail.strip()):
        elem.tail = ind


def export_one_dia(src, out_root, xml_root):
    data = src.read_bytes()
    entries = scan_pvrt(data)
    if not entries:
        print(f"{src.name}: 无 PVRT 块, 跳过 (不创建空目录)")
        return 0

    folder = src.stem.lower()
    out_dir = out_root / folder
    out_dir.mkdir(parents=True, exist_ok=True)

    dia_el = ET.SubElement(xml_root, "dia", {
        "name": folder, "source": str(src.as_posix()), "count": str(len(entries))})

    ok = 0
    for ent in entries:
        rel = f"{folder}/{ent['index']}.png"
        try:
            Svr.from_blob(data[ent["pvrt_off"]:ent["end"]]).to_png(out_dir / f"{ent['index']}.png")
        except Exception as e:
            print(f"  警告: {src.name}#{ent['index']} 解码失败 ({e}), 跳过")
            continue
        ok += 1
        # parent_magic 探测 (仅元数据展示)
        parent = ""
        bh = ent["block_hdr_off"]
        if bh >= 8:
            m = data[bh - 8:bh - 4]
            if all(0x20 <= b <= 0x7E for b in m):
                parent = m.decode("ascii", "ignore")

        attrs = {
            "index": str(ent["index"]),
            "path": rel,
            "offset": f"0x{ent['pvrt_off']:X}",
            "blockHdrOff": f"0x{ent['block_hdr_off']:X}",
            "hdrSize": f"0x{ent['hdr_size']:X}",
            "payloadSize": f"0x{ent['payload']:X}",
            "pixelFormat": f"0x{ent['pixfmt']:02X}",
            "dataFormat": f"0x{ent['datafmt']:02X}",
            "width": str(ent["width"]),
            "height": str(ent["height"]),
            "bpp": str(ent["bpp"]),
            "paletteEntries": str(ent["palette_entries"]),
            "needsExternalPalette": str(ent["needs_external_palette"]).lower(),
            "parent": parent,
        }
        if ent["global_index"] is not None:
            attrs["globalIndex"] = str(ent["global_index"])
        ET.SubElement(dia_el, "image", attrs)

    print(f"{src.name}: 解码 {ok} 张 -> {folder}/")
    return ok


def export_all(src_root, out_root):
    xml_root = ET.Element("textures")
    n = 0
    for src in sorted(p for p in src_root.rglob("*.dia") if p.is_file()):
        n += export_one_dia(src, out_root, xml_root)
    _indent(xml_root)
    ET.ElementTree(xml_root).write(out_root / "list.xml", encoding="utf-8", xml_declaration=True)
    print(f"写出 list.xml, 共 {n} 张图")
    return n


def _pi(text):
    return int(text, 0)


def import_all(orig_root, png_root, out_root):
    """读 PNG -> 编码 -> 回写进原始 .dia -> 输出新 .dia。"""
    list_path = png_root / "list.xml"
    if not list_path.exists():
        raise SystemExit(f"缺少 list.xml: {list_path}")
    root = ET.parse(list_path).getroot()
    out_root.mkdir(parents=True, exist_ok=True)
    total = 0

    for dia_el in root.findall("dia"):
        src_attr = dia_el.get("source")
        name = dia_el.get("name") or ""
        if not src_attr:
            raise SystemExit(f"dia 缺 source: {name}")
        src_path = Path(src_attr)
        if not src_path.is_absolute():
            src_path = orig_root / src_path
        if not src_path.exists():
            alt = orig_root / (name + ".DIA")
            if alt.exists():
                src_path = alt
            else:
                raise SystemExit(f"找不到原始 dia: {src_path}")

        data = bytearray(src_path.read_bytes())
        replaced = 0
        dia_quantized = []
        for img in dia_el.findall("image"):
            rel = img.get("path")
            if not rel:
                continue
            png_path = png_root / rel
            if not png_path.exists():
                continue
            pixfmt = _pi(img.get("pixelFormat"))
            datafmt = _pi(img.get("dataFormat"))
            gi = img.get("globalIndex")
            gi = int(gi) if gi else None
            
            # 🔍 调试：打印当前处理的图片
            print(f"处理: {rel}", end=" ", flush=True)
            
            try:
                blob, quantized = Svr.from_png(png_path, pixfmt, datafmt, gi).encode_blob()
                print("✅")
            except Exception as e:
                print(f"❌ 报错: {e}")
                print(f"   图片路径: {png_path.absolute()}")
                print(f"   尺寸: {Image.open(png_path).size}")
                print(f"   像素格式: 0x{pixfmt:02X}, 数据格式: 0x{datafmt:02X}")
                raise  # 重新抛出异常，停在出错位置

            off = _pi(img.get("offset"))
            payload = _pi(img.get("payloadSize"))
            w = int(img.get("width")); h = int(img.get("height"))
            exp_len = 8 + payload

            if blob[:4] != PVRT_MAGIC:
                raise SystemExit(f"{rel} 编码后缺 PVRT magic")
            if u32le(blob, 4) != payload:
                raise SystemExit(f"{rel} payload 变化 (原 {payload} 现 {u32le(blob, 4)})")
            if len(blob) != exp_len:
                raise SystemExit(f"{rel} 长度变化 (原 {exp_len} 现 {len(blob)})")
            if u16le(blob, 12) != w or u16le(blob, 14) != h:
                raise SystemExit(f"{rel} 尺寸变化")

            data[off:off + exp_len] = blob
            replaced += 1; total += 1
            if quantized:
                dia_quantized.append(rel)

        (out_root / src_path.name).write_bytes(data)
        if dia_quantized:
            print(f"{src_path.name}: 回写 {replaced} 张  [量化 {len(dia_quantized)} 张: {', '.join(dia_quantized)}]")
        else:
            print(f"{src_path.name}: 回写 {replaced} 张  (全部精确还原, 无量化)")

        (out_root / src_path.name).write_bytes(data)
    return total


def main(argv):
    if len(argv) >= 4 and argv[1].lower() == "e":
        out = Path(argv[3]); out.mkdir(parents=True, exist_ok=True)
        export_all(Path(argv[2]), out)
        return 0
    if len(argv) >= 5 and argv[1].lower() == "i":
        total = import_all(Path(argv[2]), Path(argv[3]), Path(argv[4]))
        print(f"回写完成, 共 {total} 张")
        return 0
    print("用法:\n"
          "  python svr_tool.py e <dia目录> <png输出目录>\n"
          "  python svr_tool.py i <原始dia目录> <png目录> <输出dia目录>")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
