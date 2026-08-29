#!/usr/bin/env python3
"""BF1 文本提取/回写。

BF1 是链式块容器(资料库/查看器等 LD_* 模块):
    根块头 [8]=头长(ABDA 0x30 / LTHM 0x10), 之后顺序块直到 EOFC(0x10), 无块表。
    块 = 魔数(4) + 数据长(4) + 头长(4) + 头 + 数据, 逐块相接。
    ABDT/POF0=场景数据, ABRS/LTHM/HTEX=贴图容器, GTPA=文本。
文本在 GTPA 块(与 GDR 同款): 数据区 = count(u32) + 偏移表 + 条目
    [子项数 n + n*4 参数 + CP932 文本 + 00], 头 +0x0E bit0 = 加密(+1)。
文本含真实换行(0x0A), 提取时转 \\n。
GTPA 变长时其后块顺序后移即可: 链无偏移表, EOFC 固定 16 字节无尺寸字段。
SYS_EXPLANATION01-08 无 GTPA, 文字烤在 256x256 贴图里, 不归本工具管。

用法:
    python bf1.py e <bf1目录或单文件> <txt输出目录>
    python bf1.py w <txt目录> <原始bf1目录> <输出目录>
"""
import struct
import sys
from pathlib import Path

import char
from gdr import parse_gtpa, rebuild_gtpa

char.MAP_PATH = Path('font/font.tbl')

u32 = lambda b, o: struct.unpack_from("<I", b, o)[0]

GTPA_MAGIC = b"GTPA"


def walk(b: bytes):
    """从根头之后逐块走链: [(偏移, 魔数, 头长, 数据长)]。"""
    blocks = []
    o = u32(b, 8)
    while o + 12 <= len(b):
        magic = b[o:o + 4]
        ds, hs = u32(b, o + 4), u32(b, o + 8)
        if not all(0x20 <= c <= 0x7E for c in magic) or ds >= len(b) or hs > 0x2000:
            raise ValueError(f"Bad block @{o:#x}: {magic!r} ds={ds:#x} hs={hs:#x}")
        blocks.append((o, magic, hs, ds))
        o += hs + ds
    if o != len(b):
        raise ValueError(f"Chain ends at {o:#x} != file end {len(b):#x}")
    return blocks


def parse(p: Path):
    b = p.read_bytes()
    for off, magic, hs, ds in walk(b):
        if magic == GTPA_MAGIC:
            ghead, entries, crypt = parse_gtpa(b[off:off + hs + ds])
            return b, off, hs, ds, crypt, (ghead, entries)
    raise ValueError("No GTPA block")


def extract(src: Path, dst: Path):
    files = [src] if src.is_file() else sorted(src.glob("*.BF1"))
    dst.mkdir(parents=True, exist_ok=True)
    for f in files:
        try:
            *_, (_, entries) = parse(f)
            out = dst / (f.stem + ".txt")
            out.write_text("\n".join(t.replace("\n", "\\n") for _, t in entries), "utf-8")
            print(f"{f.name}: {len(entries)} 条 -> {out.name}")
        except ValueError as e:
            print(f"- {f.name}: {e}")
        except Exception as e:
            print(f"E: {f.name} - {e}")


def write_one(txt: Path, base: Path, out_d: Path):
    b, g_off, hs, ds, crypt, (ghead, entries) = parse(base)
    lines = [conv(x.replace("\\n", "\n")) for x in txt.read_text("utf-8").splitlines()]
    if len(lines) != len(entries):
        raise ValueError("Count mismatch")
    new_gtpa = rebuild_gtpa(ghead, list(zip([p for p, _ in entries], lines)), crypt)
    out = b[:g_off] + new_gtpa + b[g_off + hs + ds:]
    dst = out_d / base.name
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(out)
    print(f"{base.name}: 回写 {len(lines)} 条")


def write(txt_d: Path, base_d: Path, out_d: Path):
    for txt in sorted(txt_d.glob("*.txt")):
        base = base_d / (txt.stem + ".BF1")
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
