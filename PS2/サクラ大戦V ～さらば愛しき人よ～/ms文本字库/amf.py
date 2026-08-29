#!/usr/bin/env python3
"""AM_INI001.AMF 文本提取/回写。

AMF 外层是 BS1 同款多块容器:
    [0x10] 块数量, [0x14] 块表偏移, 块大小 = u32(off+4) + u32(off+8)
文本在 GTPA 块内:
    GTPA 头 0x10 + count(u32) + 偏移表(count*4, 值相对 0x10)
    条目 = 0x50 字节头 + CP932 文本 + 00 + 4 字节对齐
    条目头 [4] = 文本字节数(不含 NUL), 回写时需同步更新
其余块(HSPR/HTEX)原样保留; 文本变长时重算 GTPA 偏移表、
AMF 块偏移表与外层数据区大小。

用法:
    python amf.py e <amf目录或单文件> <txt输出目录>
    python amf.py w <txt目录> <原始amf目录> <输出目录>
"""
import struct
import sys
from pathlib import Path

import char

char.MAP_PATH = Path('font/font.tbl')

u32 = lambda b, o: struct.unpack_from("<I", b, o)[0]
p32 = lambda v: struct.pack("<I", v)

GTPA_MAGIC = b"GTPA"
ENTRY_HEADER_SIZE = 0x50
EOFC_SIZE = 0x10


def find_blocks(b: bytes):
    """AMF 块表 -> [(off, magic, hsize, dsize)]。"""
    count, tbl = u32(b, 0x10), u32(b, 0x14)
    blocks = []
    for i in range(count):
        off = u32(b, tbl + i * 4)
        blocks.append((off, b[off:off + 4], u32(b, off + 8), u32(b, off + 4)))
    return blocks, tbl


def parse_gtpa(gb: bytes):
    """GTPA 块 -> (块头 0x14, 条目列表 [(head 0x50, text)])。
    头 +0x0E bit0 = 文本加密标志(每字节+1 存储, 读取时减1)。
    """
    crypt = struct.unpack_from("<H", gb, 0x0E)[0] & 1
    count = u32(gb, 0x10)
    offs = [u32(gb, 0x14 + i * 4) + 0x10 for i in range(count)]
    entries = []
    for i, off in enumerate(offs):
        end = offs[i + 1] if i + 1 < count else len(gb)
        e = gb[off:end]
        nul = e.find(0, ENTRY_HEADER_SIZE)
        if nul < 0:
            raise ValueError(f"Entry {i} missing NUL")
        raw = e[ENTRY_HEADER_SIZE:nul]
        if crypt:
            raw = bytes((c - 1) & 0xFF for c in raw)
        entries.append((e[:ENTRY_HEADER_SIZE], raw.decode("cp932", "ignore")))
    return gb[:0x14], entries, crypt


def rebuild_gtpa(head: bytes, entries, crypt: bool) -> bytes:
    """按新文本重建 GTPA 块。
    条目头 0x50 原样保留([4]/[8] 为 UI 布局常量, 与文本长度无关); 加密保持原样。
    """
    out = bytearray(head)
    out += b"\0" * (len(entries) * 4)  # 偏移表占位
    for i, (ehead, text) in enumerate(entries):
        out[0x14 + i * 4:0x18 + i * 4] = p32(len(out) - 0x10)
        enc = text.encode("cp932", "ignore")
        if crypt:
            enc = bytes((c + 1) & 0xFF for c in enc)
        body = bytes(ehead) + enc + b"\0"
        out += body + b"\0" * (-len(body) % 4)
    out += b"\0" * (-len(out) % 16)   # GTPA 块总长保持 16 对齐
    out[4:8] = p32(len(out) - 0x10)
    return bytes(out)


def parse(p: Path):
    b = p.read_bytes()
    blocks, _ = find_blocks(b)
    for off, magic, hs, ds in blocks:
        if magic == GTPA_MAGIC:
            ghead, entries, crypt = parse_gtpa(b[off:off + hs + ds])
            return b, off, crypt, (ghead, entries)
    raise ValueError("No GTPA block")


def extract_one(p: Path, out: Path):
    try:
        *_, (_, entries) = parse(p)
        out.write_text("\n".join(t.replace("\n", "\\n") for _, t in entries), "utf-8")
        print(f"{p.name}: {len(entries)} 条 -> {out.name}")
    except Exception as e:
        print(f"E: {p.name} - {e}")


def extract(src: Path, dst: Path):
    files = [src] if src.is_file() else sorted(src.glob("*.AMF"))
    dst.mkdir(parents=True, exist_ok=True)
    for f in files:
        extract_one(f, dst / (f.stem + ".txt"))


def write_one(txt: Path, base: Path, out_d: Path):
    b, g_off, crypt, (ghead, entries) = parse(base)
    lines = [conv(x.replace("\\n", "\n")) for x in txt.read_text("utf-8").splitlines()]
    if len(lines) != len(entries):
        raise ValueError("Count mismatch")
    new_gtpa = rebuild_gtpa(ghead, list(zip([h for h, _ in entries], lines)), crypt)

    # 重组 AMF: GTPA 换新, 其余块原样, 重算块表; [4] 保持与文件长的原差值平移
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
    out[4:8] = p32(u32(b, 4) + (len(out) - len(b)))
    dst = out_d / base.name
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(out)
    print(f"{base.name}: 回写 {len(lines)} 条")


def write(txt_d: Path, base_d: Path, out_d: Path):
    for txt in sorted(txt_d.glob("*.txt")):
        base = base_d / (txt.stem + ".AMF")
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
