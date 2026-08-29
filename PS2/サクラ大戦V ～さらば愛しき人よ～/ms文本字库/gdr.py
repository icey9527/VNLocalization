#!/usr/bin/env python3
"""GDR (GDEN) 文本提取/回写。

GDEN 是 BS1 同款多块容器(SLG 战斗关卡数据):
    [0x10] 块数量, [0x14] 块表偏移, 块大小 = u32(off+4) + u32(off+8)
    头 0x50, 外层 [4] = 文件长 - 头 - EOFC
文本在 GTPA 块:
    数据区 = count(u32) + 偏移表(count*4, 相对块内 0x10) + 条目
    条目 = [子项数 n (u32)] + [n * 4 字节参数] + CP932 文本 + 00
    头 +0x0E bit0 = 加密标志(文本每字节+1 存储, 读取时减1)
条目参数区原样保留; 文本变长时重算偏移表、块表与外层大小。
注意: GTPA 并非全同 —— 26 个标准文件共用一份(282 条, 0x7760),
SLG_GARDEN_09_01/09_02 是另一份(310 条, 0x88F0, 含大量独有对话)。
每个 GDR 必须翻译自己的 txt, 不能一份套全部。

用法:
    python gdr.py e <gdr目录或单文件> <txt输出目录>
    python gdr.py w <txt目录> <原始gdr目录> <输出目录>
"""
import struct
import sys
from pathlib import Path

import char

char.MAP_PATH = Path('font/font.tbl')

u32 = lambda b, o: struct.unpack_from("<I", b, o)[0]
p32 = lambda v: struct.pack("<I", v)

GTPA_MAGIC = b"GTPA"
EOFC_SIZE = 0x10


def find_blocks(b: bytes):
    count, tbl = u32(b, 0x10), u32(b, 0x14)
    return [(u32(b, tbl + i * 4), b[u32(b, tbl + i * 4):u32(b, tbl + i * 4) + 4],
             u32(b, u32(b, tbl + i * 4) + 8), u32(b, u32(b, tbl + i * 4) + 4))
            for i in range(count)], tbl


def parse_gtpa(gb: bytes):
    """GTPA 块 -> (块头 0x14, [(参数区bytes, text)], crypt)。"""
    crypt = struct.unpack_from("<H", gb, 0x0E)[0] & 1
    count = u32(gb, 0x10)
    offs = [u32(gb, 0x14 + i * 4) + 0x10 for i in range(count)]
    entries = []
    for i, off in enumerate(offs):
        end = offs[i + 1] if i + 1 < count else len(gb)
        e = gb[off:end]
        n = u32(e, 0)
        tstart = 4 * (n + 1)
        nul = e.find(0, tstart)
        if nul < 0:
            raise ValueError(f"Entry {i} missing NUL")
        raw = e[tstart:nul]
        if crypt:
            raw = bytes((c - 1) & 0xFF for c in raw)
        entries.append((e[:tstart], raw.decode("cp932", "ignore")))
    return gb[:0x14], entries, crypt


def rebuild_gtpa(head: bytes, entries, crypt: bool) -> bytes:
    """按新文本重建 GTPA 块(参数区原样, 偏移表/条目重排, 加密保持)。"""
    out = bytearray(head)
    out += b"\0" * (len(entries) * 4)
    for i, (prefix, text) in enumerate(entries):
        out[0x14 + i * 4:0x18 + i * 4] = p32(len(out) - 0x10)
        enc = text.encode("cp932", "ignore")
        if crypt:
            enc = bytes((c + 1) & 0xFF for c in enc)
        body = prefix + enc + b"\0"
        out += body + b"\0" * (-len(body) % 4)
    out += b"\0" * (-len(out) % 16)
    out[4:8] = p32(len(out) - 0x10)
    return bytes(out)


def parse(p: Path):
    b = p.read_bytes()
    for off, magic, hs, ds in find_blocks(b)[0]:
        if magic == GTPA_MAGIC:
            ghead, entries, crypt = parse_gtpa(b[off:off + hs + ds])
            return b, off, crypt, (ghead, entries)
    raise ValueError("No GTPA block")


def extract(src: Path, dst: Path):
    files = [src] if src.is_file() else sorted(src.glob("*.GDR"))
    dst.mkdir(parents=True, exist_ok=True)
    for f in files:
        try:
            *_, (_, entries) = parse(f)
            out = dst / (f.stem + ".txt")
            out.write_text("\n".join(t.replace("\n", "\\n") for _, t in entries), "utf-8")
            print(f"{f.name}: {len(entries)} 条 -> {out.name}")
        except Exception as e:
            print(f"E: {f.name} - {e}")


def write_one(txt: Path, base: Path, out_d: Path):
    b, g_off, crypt, (ghead, entries) = parse(base)
    lines = [conv(x.replace("\\n", "\n")) for x in txt.read_text("utf-8").splitlines()]
    if len(lines) != len(entries):
        raise ValueError("Count mismatch")
    new_gtpa = rebuild_gtpa(ghead, list(zip([p for p, _ in entries], lines)), crypt)

    hdr = u32(b, 8)
    blocks, tbl = find_blocks(b)
    out = bytearray(b[:hdr])
    new_offs, cur = [], hdr
    for off, magic, h2, d2 in blocks:
        new_offs.append(cur)
        data = new_gtpa if off == g_off else b[off:off + h2 + d2]
        out += data
        cur += len(data)
    out += b[-EOFC_SIZE:]
    for i, o in enumerate(new_offs):
        out[tbl + i * 4:tbl + i * 4 + 4] = p32(o)
    out[4:8] = p32(len(out) - hdr - EOFC_SIZE)
    dst = out_d / base.name
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(out)
    print(f"{base.name}: 回写 {len(lines)} 条")


def write(txt_d: Path, base_d: Path, out_d: Path):
    for txt in sorted(txt_d.glob("*.txt")):
        base = base_d / (txt.stem + ".GDR")
        if not base.exists():
            continue
        try:
            write_one(txt, base, out_d)
        except Exception as e:
            print(f"E: {txt.name} - {e}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(0)
    if a[0] == "e":
        extract(Path(a[1]), Path(a[2]))
    elif a[0] == "w":
        conv = char.make_translation_converter()
        write(Path(a[1]), Path(a[2]), Path(a[3]))
