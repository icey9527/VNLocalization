from __future__ import annotations

import binascii
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree


MAGIC = b"GHP3"


def _align4(x: int) -> int:
    return (x + 3) & ~3


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _png_chunk(typ: bytes, data: bytes) -> bytes:
    crc = binascii.crc32(typ)
    crc = binascii.crc32(data, crc) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + typ + data + struct.pack(">I", crc)


def write_png_rgba(path: Path, w: int, h: int, rgba: bytes) -> None:
    raw = bytearray()
    row = w * 4
    for y in range(h):
        raw.append(0)
        raw += rgba[y * row : (y + 1) * row]
    comp = zlib.compress(bytes(raw), level=9)
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    out = bytearray(sig)
    out += _png_chunk(b"IHDR", ihdr)
    out += _png_chunk(b"IDAT", comp)
    out += _png_chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(out)


@dataclass(frozen=True)
class PngImage:
    width: int
    height: int
    rgba: bytes


@dataclass(frozen=True)
class Meta:
    w: int | None = None
    h: int | None = None
    flag: int | None = None


def _meta_key(name: str) -> str:
    return name.replace("\\", "/").upper()


def read_meta_xml(path: Path) -> dict[str, Meta]:
    if not path.exists():
        return {}
    root = ElementTree.parse(path).getroot()
    out: dict[str, Meta] = {}
    for e in root.findall("gh"):
        name = e.get("name")
        if not name:
            continue
        ww = e.get("w")
        hh = e.get("h")
        flag = e.get("f")
        out[_meta_key(name)] = Meta(
            w=int(ww, 0) if ww is not None else None,
            h=int(hh, 0) if hh is not None else None,
            flag=int(flag, 0) if flag is not None else None,
        )
    return out


def write_meta_xml(path: Path, items: list[tuple[str, Meta]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n')
        f.write("<gh3meta>\n")
        for name, m in items:
            attrs = [f'name="{name}"']
            if m.w is not None:
                attrs.append(f'w="{m.w}"')
            if m.h is not None:
                attrs.append(f'h="{m.h}"')
            if m.flag is not None:
                attrs.append(f'f="{m.flag}"')
            f.write("  <gh " + " ".join(attrs) + " />\n")
        f.write("</gh3meta>\n")


def read_png_rgba(path: Path) -> PngImage:
    b = path.read_bytes()
    if b[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not png")
    off = 8
    w = h = None
    bd = ct = il = None
    plte = None
    trns = None
    idat = bytearray()
    while off + 8 <= len(b):
        ln = struct.unpack_from(">I", b, off)[0]
        off += 4
        typ = b[off : off + 4]
        off += 4
        data = b[off : off + ln]
        off += ln + 4
        if typ == b"IHDR":
            w, h, bd, ct, _cm, _fm, il = struct.unpack(">IIBBBBB", data)
        elif typ == b"PLTE":
            plte = data
        elif typ == b"tRNS":
            trns = data
        elif typ == b"IDAT":
            idat += data
        elif typ == b"IEND":
            break
    if w is None or h is None or bd is None or ct is None or il is None:
        raise ValueError("bad ihdr")
    if bd != 8 or il != 0:
        raise NotImplementedError("only bit_depth=8 non-interlaced")
    if ct == 6:
        bpp = 4
    elif ct == 2:
        bpp = 3
    elif ct == 3:
        if plte is None:
            raise ValueError("indexed png missing PLTE")
        bpp = 1
    else:
        raise NotImplementedError("need ct=2/3/6")
    raw = zlib.decompress(bytes(idat))
    stride = w * bpp
    scan = stride + 1
    if len(raw) != scan * h:
        raise ValueError("bad png raw size")
    out = bytearray(h * stride)
    for y in range(h):
        f = raw[y * scan]
        src = raw[y * scan + 1 : y * scan + 1 + stride]
        dst = y * stride
        prev = (y - 1) * stride
        if f == 0:
            out[dst : dst + stride] = src
        elif f == 1:
            for i in range(stride):
                left = out[dst + i - bpp] if i >= bpp else 0
                out[dst + i] = (src[i] + left) & 0xFF
        elif f == 2:
            for i in range(stride):
                up = out[prev + i] if y > 0 else 0
                out[dst + i] = (src[i] + up) & 0xFF
        elif f == 3:
            for i in range(stride):
                left = out[dst + i - bpp] if i >= bpp else 0
                up = out[prev + i] if y > 0 else 0
                out[dst + i] = (src[i] + ((left + up) // 2)) & 0xFF
        elif f == 4:
            for i in range(stride):
                left = out[dst + i - bpp] if i >= bpp else 0
                up = out[prev + i] if y > 0 else 0
                up_left = out[prev + i - bpp] if (y > 0 and i >= bpp) else 0
                out[dst + i] = (src[i] + _paeth(left, up, up_left)) & 0xFF
        else:
            raise ValueError("bad filter")
    rgba = bytearray(w * h * 4)
    if ct == 6:
        rgba[:] = out
    elif ct == 2:
        for i in range(w * h):
            r, g, bb = out[i * 3 : i * 3 + 3]
            rgba[i * 4 + 0] = r
            rgba[i * 4 + 1] = g
            rgba[i * 4 + 2] = bb
            rgba[i * 4 + 3] = 255
    else:
        pal = plte
        for i in range(w * h):
            idx = out[i]
            rgba[i * 4 + 0] = pal[idx * 3 + 0]
            rgba[i * 4 + 1] = pal[idx * 3 + 1]
            rgba[i * 4 + 2] = pal[idx * 3 + 2]
            rgba[i * 4 + 3] = trns[idx] if (trns is not None and idx < len(trns)) else 255
    return PngImage(w, h, bytes(rgba))


def _rgb555_key(r: int, g: int, b: int) -> int:
    return ((r >> 3) << 10) | ((g >> 3) << 5) | (b >> 3)


def _rgb555_to_rgb(key: int) -> tuple[int, int, int]:
    r5 = (key >> 10) & 31
    g5 = (key >> 5) & 31
    b5 = key & 31
    return (r5 << 3) | (r5 >> 2), (g5 << 3) | (g5 >> 2), (b5 << 3) | (b5 >> 2)


@dataclass
class _Box:
    keys: list[int]
    cnts: list[int]
    rmin: int
    rmax: int
    gmin: int
    gmax: int
    bmin: int
    bmax: int
    total: int


def _make_box(keys: list[int], cnts: list[int]) -> _Box:
    rmin = gmin = bmin = 31
    rmax = gmax = bmax = 0
    total = 0
    for k, c in zip(keys, cnts):
        r = (k >> 10) & 31
        g = (k >> 5) & 31
        b = k & 31
        rmin = min(rmin, r)
        rmax = max(rmax, r)
        gmin = min(gmin, g)
        gmax = max(gmax, g)
        bmin = min(bmin, b)
        bmax = max(bmax, b)
        total += c
    return _Box(keys, cnts, rmin, rmax, gmin, gmax, bmin, bmax, total)


def _split_box(box: _Box) -> tuple[_Box, _Box] | None:
    if len(box.keys) <= 1:
        return None
    rr = box.rmax - box.rmin
    gr = box.gmax - box.gmin
    br = box.bmax - box.bmin
    if rr >= gr and rr >= br:
        chan = 0
    elif gr >= br:
        chan = 1
    else:
        chan = 2
    items = list(zip(box.keys, box.cnts))
    if chan == 0:
        items.sort(key=lambda t: (t[0] >> 10) & 31)
    elif chan == 1:
        items.sort(key=lambda t: (t[0] >> 5) & 31)
    else:
        items.sort(key=lambda t: t[0] & 31)
    half = box.total // 2
    acc = 0
    split_at = 0
    for i, (_k, c) in enumerate(items):
        acc += c
        if acc >= half:
            split_at = i + 1
            break
    if split_at <= 0 or split_at >= len(items):
        split_at = len(items) // 2
        if split_at <= 0 or split_at >= len(items):
            return None
    a = items[:split_at]
    b = items[split_at:]
    ak, ac = zip(*a)
    bk, bc = zip(*b)
    return _make_box(list(ak), list(ac)), _make_box(list(bk), list(bc))


def quantize_rgba(img: PngImage, alpha_thresh: int = 128) -> tuple[list[tuple[int, int, int]], bytearray, bytearray]:
    w, h = img.width, img.height
    rgba = img.rgba
    alpha = bytearray(w * h)
    exact: dict[tuple[int, int, int], int] = {}
    has_t = False
    for i in range(w * h):
        r = rgba[i * 4 + 0]
        g = rgba[i * 4 + 1]
        b = rgba[i * 4 + 2]
        a = rgba[i * 4 + 3]
        alpha[i] = 255 if a >= alpha_thresh else 0
        if alpha[i] == 0:
            has_t = True
            r = g = b = 0
        exact[(r, g, b)] = exact.get((r, g, b), 0) + 1
    if has_t and (0, 0, 0) not in exact:
        exact[(0, 0, 0)] = 1
    if len(exact) <= 256:
        items = sorted(exact.items(), key=lambda t: t[1], reverse=True)
        colors = [rgb for (rgb, _c) in items]
        if has_t:
            if (0, 0, 0) in colors:
                colors.remove((0, 0, 0))
            colors.insert(0, (0, 0, 0))
        colors = colors[:256]
        lut_rgb = {rgb: i for i, rgb in enumerate(colors)}
        pal = colors
        idx = bytearray(w * h)
        for i in range(w * h):
            r = rgba[i * 4 + 0]
            g = rgba[i * 4 + 1]
            b = rgba[i * 4 + 2]
            if alpha[i] == 0:
                r = g = b = 0
            idx[i] = lut_rgb.get((r, g, b), 0) & 0xFF
        return pal, idx, alpha
    hist: dict[int, int] = {}
    for i in range(w * h):
        r = rgba[i * 4 + 0]
        g = rgba[i * 4 + 1]
        b = rgba[i * 4 + 2]
        if alpha[i] == 0:
            r = g = b = 0
        k = _rgb555_key(r, g, b)
        hist[k] = hist.get(k, 0) + 1
    if has_t:
        k0 = _rgb555_key(0, 0, 0)
        hist[k0] = hist.get(k0, 0) + 1
    items = sorted(hist.items(), key=lambda t: t[1], reverse=True)
    keys = [k for k, _c in items]
    cnts = [c for _k, c in items]
    boxes: list[_Box] = [_make_box(keys, cnts)]
    while len(boxes) < 256:
        boxes.sort(key=lambda b: (-(b.rmax - b.rmin + b.gmax - b.gmin + b.bmax - b.bmin), -b.total))
        sp = _split_box(boxes[0])
        if sp is None:
            break
        boxes = [sp[0], sp[1]] + boxes[1:]
    pal = []
    for bx in boxes:
        tot = bx.total
        sr = sg = sb = 0
        for k, c in zip(bx.keys, bx.cnts):
            r = (k >> 10) & 31
            g = (k >> 5) & 31
            b = k & 31
            sr += r * c
            sg += g * c
            sb += b * c
        r5 = (sr + tot // 2) // tot
        g5 = (sg + tot // 2) // tot
        b5 = (sb + tot // 2) // tot
        pal.append(_rgb555_to_rgb((r5 << 10) | (g5 << 5) | b5))
    if has_t:
        if pal:
            pal[0] = (0, 0, 0)
        else:
            pal = [(0, 0, 0)]
    lut: dict[int, int] = {}
    for k in hist.keys():
        rr, gg, bb = _rgb555_to_rgb(k)
        best = 0
        best_d = 1 << 60
        for i, (pr, pg, pb) in enumerate(pal):
            dr = rr - pr
            dg = gg - pg
            db = bb - pb
            d = dr * dr + dg * dg + db * db
            if d < best_d:
                best_d = d
                best = i
        lut[k] = best
    idx = bytearray(w * h)
    for i in range(w * h):
        r = rgba[i * 4 + 0]
        g = rgba[i * 4 + 1]
        b = rgba[i * 4 + 2]
        if alpha[i] == 0:
            r = g = b = 0
        idx[i] = lut.get(_rgb555_key(r, g, b), 0) & 0xFF
    return pal, idx, alpha


def _bleed_indices(w: int, h: int, idx: bytearray, alpha: bytearray) -> None:
    for y in range(h):
        last = 0
        base = y * w
        for x in range(w):
            p = base + x
            if alpha[p]:
                last = idx[p]
            else:
                idx[p] = last


@dataclass(frozen=True)
class GH:
    file_size: int
    width: int
    height: int
    u16_10: int
    u16_12: int
    u16_14: int
    u16_16: int
    pal_off: int
    colors: int
    opaque_count: int
    data_off: int


def parse_gh(b: bytes) -> GH:
    if len(b) < 0x28 or b[:4] != MAGIC:
        raise ValueError("not GHP3")
    (
        _m,
        fs,
        _z,
        w,
        h,
        u10,
        u12,
        u14,
        u16,
        pal_off,
        colors_u32,
        oc,
        data_off,
    ) = struct.unpack_from("<4sIIHHHHHHIIII", b, 0)
    if not (0x28 <= pal_off <= data_off <= len(b)):
        raise ValueError("bad offsets")
    pal_colors = (data_off - pal_off) // 3
    colors = pal_colors if 1 <= pal_colors <= 4096 else colors_u32
    if not (1 <= colors <= 4096):
        colors = u10 if 1 <= u10 <= 4096 else colors_u32
    return GH(fs, w, h, u10, u12, u14, u16, pal_off, colors, oc, data_off)


class BR:
    def __init__(self, b: bytes, off: int):
        self.b = b
        self.i = off // 4
        self.buf = 0
        self.left = 0

    def _refill(self) -> None:
        off = self.i * 4
        if off >= len(self.b):
            self.buf = 0
            self.left = 32
            return
        v = 0
        shift = 0
        for k in range(4):
            j = off + k
            if j >= len(self.b):
                break
            v |= self.b[j] << shift
            shift += 8
        self.buf = v & 0xFFFFFFFF
        self.i += 1
        self.left = 32

    def get(self, n: int) -> int:
        if n <= 0:
            return 0
        if self.left == 0:
            self._refill()
        if n <= self.left:
            out = (self.buf >> (32 - n)) & ((1 << n) - 1)
            self.buf = (self.buf << n) & 0xFFFFFFFF
            self.left -= n
            return out
        left = self.left
        hi = self.get(left)
        lo = self.get(n - left)
        return (hi << (n - left)) | lo

    def unary1(self) -> int:
        c = 0
        while True:
            if self.get(1) == 0:
                return c
            c += 1


class BW:
    def __init__(self) -> None:
        self.cur = 0
        self.filled = 0
        self.words: list[int] = []

    def put(self, n: int, v: int) -> None:
        for i in range(n - 1, -1, -1):
            bit = (v >> i) & 1
            pos = 31 - self.filled
            if bit:
                self.cur |= 1 << pos
            self.filled += 1
            if self.filled == 32:
                self.words.append(self.cur & 0xFFFFFFFF)
                self.cur = 0
                self.filled = 0

    def unary1(self, ones: int) -> None:
        if ones:
            self.put(ones, (1 << ones) - 1)
        self.put(1, 0)

    def finish(self) -> bytes:
        if self.filled:
            self.words.append(self.cur & 0xFFFFFFFF)
        out = bytearray()
        for w in self.words:
            out += struct.pack("<I", w)
        return bytes(out)


PA_A40 = [(0, 0), (2, 0), (4, 4), (6, 20), (8, 84), (12, 340), (16, 4436), (18, 69972), (1, 2), (4, 8), (16, 32), (64, 128)]
PA_AE0 = [(2, 0), (4, 4), (6, 20), (8, 84), (12, 340), (16, 4436), (18, 69972), (1, 2), (4, 8), (16, 32), (64, 128)]


def clog2(n: int) -> int:
    if n <= 1:
        return 0
    p = 1
    b = 0
    while p < n and b < 24:
        p <<= 1
        b += 1
    return b


def rd_a40(br: BR) -> int:
    idx = br.unary1()
    if idx == 0:
        return 3
    bits, base = PA_A40[idx]
    return base + br.get(bits) + 4


def rd_ae0(br: BR) -> int:
    idx = br.unary1()
    bits, base = PA_AE0[idx]
    return base + br.get(bits) + 1


def wr_a40(wr: BW, val: int) -> None:
    if val == 3:
        wr.unary1(0)
        return
    z = val - 4
    for i in range(1, len(PA_A40)):
        bits, base = PA_A40[i]
        if base <= z < base + (1 << bits):
            wr.unary1(i)
            if bits:
                wr.put(bits, z - base)
            return
    raise ValueError("a40")


def wr_ae0(wr: BW, val: int) -> None:
    z = val - 1
    for i in range(0, len(PA_AE0)):
        bits, base = PA_AE0[i]
        if base <= z < base + (1 << bits):
            wr.unary1(i)
            if bits:
                wr.put(bits, z - base)
            return
    raise ValueError("ae0")


def wr_step(wr: BW, step: int) -> None:
    v14 = step // 2
    b = step & 1
    wr.put(2, v14)
    wr.put(1, b)


def decode_one(gh_path: Path, out_dir: Path) -> None:
    b = gh_path.read_bytes()
    h = parse_gh(b)
    pal = b[h.pal_off : h.pal_off + h.colors * 3]
    bits = clog2(h.u16_10) if h.u16_10 else clog2(h.colors)
    stride = (h.width + 3) & ~3
    pix = bytearray(stride * h.height)
    mw = (h.width * h.height + 31) // 32
    mask = bytearray(mw * 4)
    br = BR(b, h.data_off)
    x = y = 0
    bx = by = 0
    rep = 0
    step = 5
    ev = 0
    try:
        cur = br.get(bits) if bits else 0
        while ev < h.opaque_count:
            if rep <= 0:
                v14 = br.get(2)
                if v14 > 2:
                    rep = rd_a40(br) - 2
                else:
                    step = br.get(1) + 2 * v14
            else:
                rep -= 1
            if 0 <= x < h.width and 0 <= y < h.height:
                pix[y * stride + x] = cur & 0xFF
                p = y * h.width + x
                w = p // 32
                bit = p & 31
                word = struct.unpack_from("<I", mask, w * 4)[0] | (1 << bit)
                struct.pack_into("<I", mask, w * 4, word)
            if step >= 5:
                d = rd_ae0(br) + bx
                by += d // h.width
                bx = d % h.width
                x, y = bx, by
                cur = br.get(bits) if bits else 0
                ev += 1
            else:
                x += step - 2
                y += 1
    except EOFError:
        if not (ev + 1 == h.opaque_count and by >= h.height):
            raise
    last = 0
    for yy in range(h.height):
        row = yy * stride
        for xx in range(h.width):
            p = yy * h.width + xx
            word = struct.unpack_from("<I", mask, (p // 32) * 4)[0]
            if (word >> (p & 31)) & 1:
                last = pix[row + xx]
            else:
                pix[row + xx] = last
    out = bytearray(h.width * h.height * 4)
    for yy in range(h.height):
        for xx in range(h.width):
            p = yy * h.width + xx
            idx = pix[yy * stride + xx]
            rr, gg, bb = pal[idx * 3 : idx * 3 + 3]
            off = p * 4
            out[off + 0] = rr
            out[off + 1] = gg
            out[off + 2] = bb
            out[off + 3] = 255
    write_png_rgba(out_dir / (gh_path.name + ".png"), h.width, h.height, bytes(out))


@dataclass(frozen=True)
class Node:
    x: int
    y: int
    idx: int


def _mcmf_match(left_x: list[int], right_x: list[int]) -> dict[int, int]:
    if not left_x or not right_x:
        return {}

    nL = len(left_x)
    nR = len(right_x)
    s = 0
    L0 = 1
    R0 = L0 + nL
    t = R0 + nR
    g: list[list[list[int]]] = [[] for _ in range(t + 1)]

    def add(u: int, v: int, cap: int, cost: int) -> None:
        g[u].append([v, cap, cost, len(g[v])])
        g[v].append([u, 0, -cost, len(g[u]) - 1])

    for i in range(nL):
        add(s, L0 + i, 1, 0)
    for j in range(nR):
        add(R0 + j, t, 1, 0)

    right_pos = {x: j for j, x in enumerate(right_x)}
    for i, x in enumerate(left_x):
        for dx in (0, 1, -1, 2, -2):
            j = right_pos.get(x + dx)
            if j is not None:
                add(L0 + i, R0 + j, 1, abs(dx))

    inf = 10**18
    pot = [0] * (t + 1)

    import heapq

    while True:
        dist = [inf] * (t + 1)
        prev: list[tuple[int, int] | None] = [None] * (t + 1)
        dist[s] = 0
        pq: list[tuple[int, int]] = [(0, s)]
        while pq:
            d, u = heapq.heappop(pq)
            if d != dist[u]:
                continue
            for ei, e in enumerate(g[u]):
                v, cap, cost, rev = e
                if cap <= 0:
                    continue
                nd = d + cost + pot[u] - pot[v]
                if nd < dist[v]:
                    dist[v] = nd
                    prev[v] = (u, ei)
                    heapq.heappush(pq, (nd, v))
        if prev[t] is None:
            break
        for v in range(t + 1):
            if dist[v] < inf:
                pot[v] += dist[v]
        v = t
        while v != s:
            u, ei = prev[v]
            e = g[u][ei]
            e[1] -= 1
            ru = e[0]
            rev = e[3]
            g[ru][rev][1] += 1
            v = u

    out: dict[int, int] = {}
    for i in range(nL):
        u = L0 + i
        for e in g[u]:
            v, cap, cost, rev = e
            if R0 <= v < R0 + nR and cap == 0:
                out[i] = v - R0
                break
    return out


def _build_payload(w: int, colors: int, nodes: list[Node]) -> tuple[bytes, int]:
    bits = clog2(colors)
    by_row_idx: dict[tuple[int, int], list[int]] = {}
    max_y = 0
    for i, n in enumerate(nodes):
        by_row_idx.setdefault((n.y, n.idx), []).append(i)
        if n.y > max_y:
            max_y = n.y

    for k in list(by_row_idx.keys()):
        by_row_idx[k].sort(key=lambda i: nodes[i].x)

    succ: list[int | None] = [None] * len(nodes)
    pred: list[int | None] = [None] * len(nodes)

    for y in range(max_y):
        idxs = {idx for (yy, idx) in by_row_idx.keys() if yy == y}
        for idx in idxs:
            L = by_row_idx.get((y, idx))
            R = by_row_idx.get((y + 1, idx))
            if not L or not R:
                continue
            left_x = [nodes[i].x for i in L]
            right_x = [nodes[i].x for i in R]
            m = _mcmf_match(left_x, right_x)
            for li, rj in m.items():
                a = L[li]
                b = R[rj]
                succ[a] = b
                pred[b] = a
    def lin(i: int) -> int:
        n = nodes[i]
        return n.y * w + n.x
    starts = [i for i, p in enumerate(pred) if p is None]
    starts.sort(key=lin)
    chains: list[list[int]] = []
    for s in starts:
        ch = [s]
        cur = s
        nxt = succ[cur]
        while nxt is not None:
            cur = nxt
            ch.append(cur)
            nxt = succ[cur]
        chains.append(ch)
    if lin(chains[0][0]) != 0:
        raise ValueError("need opaque at (0,0)")
    wr = BW()
    if bits:
        wr.put(bits, nodes[chains[0][0]].idx)
    step_codes: list[int] = []
    payload: list[tuple[int, int]] = []
    chain_starts = [lin(ch[0]) for ch in chains]
    for ci, ch in enumerate(chains):
        is_last_chain = (ci + 1 == len(chains))
        chain_base = chain_starts[ci]
        for j, nid in enumerate(ch):
            is_last = (j + 1 == len(ch))
            if not is_last:
                a = nodes[nid]
                b = nodes[ch[j + 1]]
                dx = b.x - a.x
                step_codes.append(dx + 2)
                payload.append((0, 0))
            else:
                step_codes.append(5)
                if not is_last_chain:
                    nxt_base = chain_starts[ci + 1]
                    d = nxt_base - chain_base
                    payload.append((d, nodes[chains[ci + 1][0]].idx))
                else:
                    payload.append((1, 0))
    cur_step = 5
    i = 0
    ev = 0
    while i < len(step_codes):
        s = step_codes[i]
        run = 1
        while i + run < len(step_codes) and step_codes[i + run] == s:
            run += 1
        def one(step: int, at: int) -> None:
            nonlocal ev
            wr_step(wr, step)
            if step == 5:
                d, nxt = payload[at]
                wr_ae0(wr, d)
                if bits:
                    wr.put(bits, nxt)
                ev += 1
        def rep(step: int, at: int, ln: int) -> None:
            nonlocal ev
            wr.put(2, 3)
            wr_a40(wr, ln + 1)
            if step == 5:
                for k in range(ln):
                    d, nxt = payload[at + k]
                    wr_ae0(wr, d)
                    if bits:
                        wr.put(bits, nxt)
                    ev += 1
        if s != cur_step:
            one(s, i)
            cur_step = s
            i += 1
            run -= 1
            if run <= 0:
                continue
        if run >= 2:
            rep(s, i, run)
            i += run
        else:
            one(s, i)
            i += 1
    return wr.finish(), ev


def encode_one(png_path: Path, out_dir: Path) -> None:
    raise RuntimeError("encode_one requires meta")
    pal, idx, alpha = quantize_rgba(img)
    alpha[0] = 255
    _bleed_indices(img.width, img.height, idx, alpha)

    used = sorted(set(idx))
    if len(used) < len(pal):
        remap = {v: i for i, v in enumerate(used)}
        pal = [pal[v] for v in used]
        idx = bytearray(remap[v] for v in idx)

    nodes: list[Node] = []
    last = 0
    for y in range(img.height):
        base = y * img.width
        for x in range(img.width):
            v = idx[base + x]
            if v != last:
                nodes.append(Node(x, y, v))
                last = v
    if not nodes or nodes[0].x != 0 or nodes[0].y != 0:
        nodes.insert(0, Node(0, 0, idx[0]))
    payload, oc = _build_payload(img.width, len(pal), nodes)

    base_name = png_path.name
    base_name = base_name[:-7] if base_name.lower().endswith(".gh.png") else png_path.stem
    base_upper = base_name.upper()
    if "EYE" in base_upper or "MOUTH" in base_upper:
        ex = struct.pack("<IHHI", 0x0C, (img.width // 2) & 0xFFFF, img.height & 0xFFFF, 2)
    elif "BODY" in base_upper:
        ex = struct.pack("<II", 0x08, 0)
    else:
        ex = b""
    pal_off = 0x28 + len(ex)
    pal_bytes = len(pal) * 3
    data_off = _align4(pal_off + pal_bytes)
    out = bytearray()
    out += MAGIC
    out += b"\x00\x00\x00\x00"
    out += struct.pack("<I", 0)
    out += struct.pack("<HH", img.width, img.height)
    colors32 = len(pal) & 0xFFFF
    colors16_b = colors32
    colors16 = colors32
    if colors32 in (3, 253):
        colors16 = colors32 + 1
    out += struct.pack("<HHHH", colors16, colors16_b, 0, 0x75)
    out += struct.pack("<I", pal_off)
    out += struct.pack("<I", len(pal))
    out += struct.pack("<I", oc)
    out += struct.pack("<I", data_off)
    out += ex
    for r, g, b in pal:
        out += bytes((r & 0xFF, g & 0xFF, b & 0xFF))
    out += b"\x00" * (data_off - (pal_off + pal_bytes))
    out += payload
    struct.pack_into("<I", out, 0x04, len(out))
    out_path = out_dir / (base_name + ".GH")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(out)


def _iter_files(inp: Path, suffix: str) -> list[Path]:
    if not inp.exists():
        raise SystemExit(f"not found: {inp}")
    if inp.is_dir():
        return sorted([p for p in inp.rglob("*") if p.is_file() and p.suffix.lower() == suffix])
    if inp.suffix.lower() != suffix:
        raise SystemExit(f"expected *{suffix}: {inp}")
    return [inp]


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["d", "e"])
    ap.add_argument("input_path", type=Path)
    ap.add_argument("output_dir", type=Path)
    args = ap.parse_args()
    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.mode == "d":
        root_in = args.input_path if args.input_path.is_dir() else args.input_path.parent
        files = _iter_files(args.input_path, ".gh")
        meta_items: list[tuple[str, Meta]] = []
        for p in files:
            b = p.read_bytes()
            h = parse_gh(b)
            ex_len = max(0, h.pal_off - 0x28)
            if ex_len:
                if ex_len > 0x0C:
                    import sys

                    print(f"warn: {p.name} ex_len=0x{ex_len:X}", file=sys.stderr)
                ex = b[0x28 : 0x28 + ex_len]
                if len(ex) >= 4 and struct.unpack_from("<I", ex, 0)[0] == ex_len:
                    if ex_len == 8:
                        _ln, ww, hh = struct.unpack_from("<IHH", ex, 0)
                        meta_items.append((_meta_key(p.relative_to(root_in).as_posix()), Meta(w=ww, h=hh)))
                    elif ex_len == 12:
                        _ln, ww, hh, flag = struct.unpack_from("<IHHI", ex, 0)
                        meta_items.append((_meta_key(p.relative_to(root_in).as_posix()), Meta(w=ww, h=hh, flag=flag)))
            rel = p.relative_to(root_in) if p.is_relative_to(root_in) else Path(p.name)
            decode_one(p, out_dir / rel.parent)
        if meta_items:
            write_meta_xml(out_dir / "list.xml", sorted(meta_items, key=lambda t: t[0]))
    else:
        root_in = args.input_path if args.input_path.is_dir() else args.input_path.parent
        meta_path = root_in / "list.xml"
        meta = read_meta_xml(meta_path)
        files = _iter_files(args.input_path, ".png")
        for p in files:
            img = read_png_rgba(p)
            pal, idx, alpha = quantize_rgba(img)
            alpha[0] = 255
            _bleed_indices(img.width, img.height, idx, alpha)

            used = sorted(set(idx))
            if len(used) < len(pal):
                remap = {v: i for i, v in enumerate(used)}
                pal = [pal[v] for v in used]
                idx = bytearray(remap[v] for v in idx)

            nodes: list[Node] = []
            last = 0
            for y in range(img.height):
                base = y * img.width
                for x in range(img.width):
                    v = idx[base + x]
                    if v != last:
                        nodes.append(Node(x, y, v))
                        last = v
            if not nodes or nodes[0].x != 0 or nodes[0].y != 0:
                nodes.insert(0, Node(0, 0, idx[0]))

            payload, oc = _build_payload(img.width, len(pal), nodes)

            name = p.name
            base = name[:-7] if name.lower().endswith(".gh.png") else p.stem
            rel = p.relative_to(root_in) if p.is_relative_to(root_in) else Path(p.name)
            gh_rel = rel.with_name(base + ".GH")
            gh_key = _meta_key(gh_rel.as_posix())
            m = meta.get(gh_key)
            ex = b""
            if m is not None:
                if m.w is not None and m.h is not None and m.flag is not None:
                    ex = struct.pack("<IHHI", 12, m.w & 0xFFFF, m.h & 0xFFFF, m.flag)
                elif m.w is not None and m.h is not None:
                    ex = struct.pack("<IHH", 8, m.w & 0xFFFF, m.h & 0xFFFF)

            pal_off = 0x28 + len(ex)
            pal_bytes = len(pal) * 3
            data_off = _align4(pal_off + pal_bytes)
            out = bytearray()
            out += MAGIC
            out += b"\x00\x00\x00\x00"
            out += struct.pack("<I", 0)
            out += struct.pack("<HH", img.width, img.height)
            colors32 = len(pal) & 0xFFFF
            colors16_b = colors32
            colors16 = colors32
            if colors32 in (3, 253):
                colors16 = colors32 + 1
            out += struct.pack("<HHHH", colors16, colors16_b, 0, 0x75)
            out += struct.pack("<I", pal_off)
            out += struct.pack("<I", len(pal))
            out += struct.pack("<I", oc)
            out += struct.pack("<I", data_off)
            out += ex
            for r, g, bb in pal:
                out += bytes((r & 0xFF, g & 0xFF, bb & 0xFF))
            out += b"\x00" * (data_off - (pal_off + pal_bytes))
            out += payload
            struct.pack_into("<I", out, 0x04, len(out))
            out_path = out_dir / gh_rel
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
