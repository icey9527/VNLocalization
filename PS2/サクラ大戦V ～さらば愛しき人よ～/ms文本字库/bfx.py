#!/usr/bin/env python3
"""BFX 文本提取/回写(ADV 界面/特效资源, 链式块容器同 BF1/ARM)。

根: HSPR(块头0x10, ADV_* 界面) / ABDA(头0x30, MRS_EFF 特效) / ABRS。
链: GTPA/HSPR 根从 0 起; ABDA 根的首段数据(压缩/无魔数)由 [0x18] 指出结束,
之后接常规块链; 部分特效文件主体整段压缩, 链不可走 —— 本工具不依赖完整链,
直接在全文定位合法 GTPA 文本块(魔数+尺寸+可解析), 逐字节替换回写。
注意: GTPA 块有"文本"和"参数表"两种用途; 参数表 count 非法解析自动失败跳过。
块头 u16@0x0C & 0x400 = IZ 压缩(iz.iz_decompress), 两个压缩 GTPA:
    ADV_LOGWIN(103 条, 对话回放说话人名表) / LD_SOUND_VIEWER(52 条, 曲名)。
压缩块回写为明文并清 0x400(游戏运行时同样先解压, 见 sub_20E020 case10)。
ADV_* 的 5 个 GTPA 是 LIPS 倒计时数字模板"１２３４５..."(字体映射, 不要翻译)。
HTEX/ABRS 等其余压缩块内容为贴图/模型, 见 bfxtex.py。

用法:
    python bfx.py e <bfx目录或单文件> <txt输出目录>
    python bfx.py w <txt目录> <原始bfx目录> <输出目录>
"""
import struct
import sys
from pathlib import Path

import char
from gdr import parse_gtpa, rebuild_gtpa

char.MAP_PATH = Path('font/font.tbl')

u16 = lambda b, o: struct.unpack_from("<H", b, o)[0]
u32 = lambda b, o: struct.unpack_from("<I", b, o)[0]
p16 = lambda v: struct.pack("<H", v)

GTPA_MAGIC = b"GTPA"


def iz_decompress(data: bytes) -> bytes:
    """IZ 位流 LZ77 解压(块头 u16@0x0C & 0x400 标志, ELF sub_20DCA0 逆向)。
    16字节头按位反转读([0]=解压尺寸 [1]=0x100); 数据位从取反字节 LSB 取:
    1=字面量(取反), 0 0 b b=短匹配(长2..5, 距1..256), 0 1 A B=长匹配/结束
    (FF FF 结束, 否则 距=32*B+(A>>3)-0x2000, 长=(A&7)+2, A&7==0 再取1字节+1)。"""
    rev8 = lambda v: int(f"{v:08b}"[::-1], 2)
    if sum(rev8(data[4 + i]) << (8 * i) for i in range(4)) != 256:
        raise ValueError("not IZ stream")
    out, win, pos = bytearray(), bytearray(0x2000), 0
    src, cur, cnt = 16, 0, 1

    def gb():
        nonlocal cur, cnt, src
        cnt -= 1
        if cnt == 0:
            cur = (~data[src]) & 0xFF
            src += 1
            cnt = 8
        b = cur & 1
        cur >>= 1
        return b

    while True:
        while gb():  # 字面量
            lit = (~data[src]) & 0xFF
            src += 1
            win[pos & 0x1FFF] = lit
            out.append(lit)
            pos += 1
        if gb():  # 长匹配/结束
            A = (~data[src]) & 0xFF
            src += 1
            B = (~data[src]) & 0xFF
            src += 1
            if A | B == 0:
                break
            if A & 7 == 0:
                ln = ((~data[src]) & 0xFF) + 1
                src += 1
            else:
                ln = (A & 7) + 2
            off = 32 * B + (A >> 3) - 0x2000
        else:  # 短匹配
            b3, b4 = gb(), gb()
            ln = 2 * b3 + b4 + 2
            off = ((~data[src]) & 0xFF) - 256
            src += 1
        j = pos + off
        for _ in range(ln):
            b = win[j & 0x1FFF]
            win[pos & 0x1FFF] = b
            out.append(b)
            pos += 1
            j += 1
    return bytes(out)


def find_gtpa(b: bytes):
    """全文定位可解析的 GTPA 文本块 -> [(偏移, 头长, 数据长, 原块是否压缩, crypt, 条目)]。
    压缩块(头 u16@0x0C & 0x400, IZ 流)先解压再解析。"""
    out = []
    pos = 0
    while True:
        o = b.find(GTPA_MAGIC, pos)
        if o < 0:
            return out
        pos = o + 1
        if o + 12 > len(b):
            continue
        ds, hs = u32(b, o + 4), u32(b, o + 8)
        if ds >= len(b) or not 0 < hs <= 0x2000 or o + hs + ds > len(b):
            continue
        comp = bool(u16(b, o + 0xC) & 0x400)
        if comp:
            try:
                gb = b[o:o + hs] + iz_decompress(b[o + hs:o + hs + ds])
            except Exception:
                continue
        else:
            gb = b[o:o + hs + ds]
        try:
            ghead, entries, crypt = parse_gtpa(gb)
        except Exception:
            continue  # 参数表变体(count 非法)自动排除
        if any(any(ord(c) < 0x20 for c in t) for _, t in entries):
            continue  # 含控制字符 → 二进制噪音
        out.append((o, hs, ds, comp, crypt, (ghead, entries)))


def extract(src: Path, dst: Path):
    files = [src] if src.is_file() else sorted(src.glob("*.BFX"))
    dst.mkdir(parents=True, exist_ok=True)
    for f in files:
        try:
            hits = find_gtpa(f.read_bytes())
            if len(hits) != 1:
                print(f"- {f.name}: {len(hits)} 个文本块, 跳过")
                continue
            *_, (_, entries) = hits[0]
            if not any(t for _, t in entries):
                print(f"- {f.name}: 文本全空, 跳过")
                continue
            out = dst / (f.stem + ".txt")
            out.write_text("\n".join(t.replace("\n", "\\n") for _, t in entries) + "\n", "utf-8")
            print(f"{f.name}: {len(entries)} 条 -> {out.name}")
        except Exception as e:
            print(f"E: {f.name} - {e}")


def write_one(txt: Path, base: Path, out_d: Path):
    b = base.read_bytes()
    hits = find_gtpa(b)
    if len(hits) != 1:
        raise ValueError(f"{len(hits)} 个文本块")
    g_off, hs, ds, comp, crypt, (ghead, entries) = hits[0]
    lines = [conv(x.replace("\\n", "\n")) for x in txt.read_text("utf-8").splitlines()]
    if not lines:
        lines = [""]  # 单条空文本的 txt 是空文件
    if len(lines) != len(entries):
        raise ValueError("Count mismatch")
    new_gtpa = bytearray(rebuild_gtpa(ghead, list(zip([p for p, _ in entries], lines)), crypt))
    if comp:  # 原块是 IZ 压缩 → 回写为明文(游戏运行时同样先解压, 见 sub_20E020 case10)
        new_gtpa[0xC:0xE] = p16(u16(new_gtpa, 0xC) & ~0x400)
    out = b[:g_off] + bytes(new_gtpa) + b[g_off + hs + ds:]
    dst = out_d / base.name
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(out)
    print(f"{base.name}: 回写 {len(lines)} 条{' (压缩→明文)' if comp else ''}")


def write(txt_d: Path, base_d: Path, out_d: Path):
    for txt in sorted(txt_d.glob("*.txt")):
        base = base_d / (txt.stem + ".BFX")
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
