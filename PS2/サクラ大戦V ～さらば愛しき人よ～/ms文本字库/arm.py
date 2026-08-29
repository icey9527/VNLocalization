#!/usr/bin/env python3
"""ARM (SlgArmsSystem) 文本提取/回写。

ARM 是链式块容器(战况界面资源), 按根块分 4 类:
    GTPA  根(块头 0x10): SLG_INFOMATION_00-13/99, 文本 516 条 + 贴图链
    HSPR  根(块头 0x10): SLG_HELPME(7条)/SLG_PROTECTS(8条)/SLG_TACTICS(纯图),
                         HSPR 内部还包 KSPR/POF0/EOFC 子链
    ABDA  根(头 0xA0):   SLG_SITUATION_*, 纯贴图
    SASN  根(头 0x90):   SLG_SMALL_NC_*, 纯贴图
链规则: GTPA/HSPR 根从 0 起、容器根从 [8] 起逐块走到 EOFC:
    块 = 魔数(4) + 数据长(4) + 头长(4) + 头 + 数据。
文本在 GTPA 块(与 GDR 同款): 数据区 = count(u32) + 偏移表 + 条目
    [子项数 n + n*4 参数 + CP932 文本 + 00], 头 +0x0E bit0 = 加密(+1)。
    15 个 INFOMATION 的 GTPA 内容完全相同, 翻一份复制成 15 个 txt 即可。
GTPA 变长时其后块顺序后移; 链无偏移表、EOFC 固定 16 字节, 其余原样。
SITUATION/SMALL_NC/TACTICS/EFFECT 无 GTPA, 纯贴图, 提取时跳过。

用法:
    python arm.py e <arm目录或单文件> <txt输出目录>
    python arm.py w <txt目录> <原始arm目录> <输出目录>
"""
import struct
import sys
from pathlib import Path

import char
from gdr import parse_gtpa, rebuild_gtpa

char.MAP_PATH = Path('font/font.tbl')

u32 = lambda b, o: struct.unpack_from("<I", b, o)[0]

GTPA_MAGIC = b"GTPA"
BLOCK_ROOTS = (b"GTPA", b"HSPR")


def walk(b: bytes):
    """逐块走链: [(偏移, 魔数, 头长, 数据长)]。走到无法继续为止。"""
    blocks = []
    o = 0 if b[:4] in BLOCK_ROOTS else u32(b, 8)
    while o + 12 <= len(b):
        magic = b[o:o + 4]
        ds, hs = u32(b, o + 4), u32(b, o + 8)
        if not all(0x20 <= c <= 0x7E for c in magic) or ds >= len(b) or not 0 < hs <= 0x2000:
            break
        blocks.append((o, magic, hs, ds))
        o += hs + ds
    return blocks


def parse(p: Path):
    b = p.read_bytes()
    for off, magic, hs, ds in walk(b):
        if magic == GTPA_MAGIC:
            ghead, entries, crypt = parse_gtpa(b[off:off + hs + ds])
            return b, off, hs, ds, crypt, (ghead, entries)
    raise ValueError("No GTPA block")


def extract(src: Path, dst: Path):
    files = [src] if src.is_file() else sorted(src.glob("*.ARM"))
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
        base = base_d / (txt.stem + ".ARM")
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
