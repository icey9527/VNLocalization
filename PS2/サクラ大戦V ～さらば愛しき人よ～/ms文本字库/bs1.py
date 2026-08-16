#!/usr/bin/env python3
"""BS1 容器提取/回写。

BS1 是一个多块容器，外层头记录块数量与块偏移表，内部顺序拼接若干子块，
末尾跟一个 EOFC 尾标。每个子块（无论 MSCR / GRO3 / GHSL）都遵循同一规则：

    块总大小 = u32(off+4) [data_size] + u32(off+8) [header_size]

只有 MSCR 子块里含有可翻译文本（CP932 字符串池 + 偏移表），其余子块是
二进制资源数据，原样保留。一个 BS1 通常含 3 个 MSCR 子块，必须全部处理，
否则会漏掉大量剧情对话。
"""
import sys, struct, re
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "msx"))
import char

char.MAP_PATH = Path('font/font.tbl')

u32 = lambda b, o: struct.unpack_from("<I", b, o)[0]
p32 = lambda v: struct.pack("<I", v)

BS1_MAGIC = b"BS1 "
MSCR_MAGIC = b"MSCR"
EOFC_MAGIC = b"EOFC"
BS1_HEADER_SIZE = 0x40
EOFC_SIZE = 0x10


# --------------------------------------------------------------------------
# MSCR 子块：字符串池提取 / 重建（与原 ms.py 语义一致，含去重 + 16 字节对齐）
# --------------------------------------------------------------------------

def mscr_parse(raw: bytes):
    """raw = 整个 MSCR 子块（含头）。返回 (py, so, sc, txts)。"""
    ds, hs = u32(raw, 4), u32(raw, 8)
    py = raw[hs:hs + ds]
    so, sc, mo, mc = u32(py, 8), u32(py, 12), u32(py, 16), u32(py, 20)
    # 安全检查：映射表位于 py[:so]，其字段不得指向字符串池区域（so 及以后），
    # 否则重建字符串池会破坏映射。原始文件均满足此约束。
    m_ref = max((max(u32(py, mo + i * 16 + 4), u32(py, mo + i * 16 + 12))
                 for i in range(mc)), default=0)
    if m_ref >= so:
        raise ValueError("Bad layout: mapping table references string pool")
    txts = [py[so + u32(py, so + i * 4):
               py.find(0, so + u32(py, so + i * 4))].decode("cp932", "ignore")
            for i in range(sc)]
    return py, so, sc, txts


def mscr_rebuild(raw: bytes, lines: list) -> bytes:
    """用新文本重建整个 MSCR 子块（含头）。保留 py[:so] 前缀与头部原样不动。"""
    ds, hs = u32(raw, 4), u32(raw, 8)
    py = raw[hs:hs + ds]
    so, sc = u32(py, 8), u32(py, 12)
    if len(lines) != sc:
        raise ValueError("Count mismatch: %d != %d" % (len(lines), sc))
    # 重建字符串池：偏移表(sc*4) + 去重后的字符串数据，偏移相对 so
    offs, uniq, t_dat, cur = [], {}, bytearray(), sc * 4
    for s in lines:
        enc = s.encode("cp932", "ignore") + b'\0'
        if enc not in uniq:
            uniq[enc] = cur
            t_dat += enc
            cur += len(enc)
        offs.append(uniq[enc])
    n_py = py[:so] + b"".join(p32(o) for o in offs) + t_dat
    # 保持 ds 为 16 的倍数（原始文件均如此，保证块起始偏移 16 对齐）
    if len(n_py) & 0xF:
        n_py += b"\0" * ((16 - (len(n_py) & 0xF)) & 0xF)
    out = bytearray(raw[:hs]) + n_py
    out[4:8] = p32(len(n_py))      # 更新 MSCR 的 ds
    return bytes(out)


def _post_extract(txts):
    # 始终删除 <SPD=...> 显示/速度标签（按用户要求），输出纯净可读文本
    txts = [re.sub(r"<SPD=[^>]+>", "", t) for t in txts]
    return [t.replace("//", "\\n") for t in txts]


# --------------------------------------------------------------------------
# BS1 容器：外层头 + 块偏移表 + 子块序列 + EOFC 尾标
# --------------------------------------------------------------------------

def bs1_parse(b: bytes):
    if b[:4] != BS1_MAGIC:
        raise ValueError("Not BS1")
    count = u32(b, 0x10)
    table_off = u32(b, 0x14)
    if table_off + count * 4 > BS1_HEADER_SIZE:
        raise ValueError("Block table overruns header")
    offsets = [u32(b, table_off + i * 4) for i in range(count)]
    blocks = []
    for i, off in enumerate(offsets):
        magic = b[off:off + 4]
        dsize = u32(b, off + 4)
        hsize = u32(b, off + 8)
        total = hsize + dsize
        blocks.append({
            "index": i, "off": off, "magic": magic,
            "hsize": hsize, "dsize": dsize, "total": total,
            "raw": b[off:off + total],
        })
    footer = b[len(b) - EOFC_SIZE:]
    if footer[:4] != EOFC_MAGIC:
        raise ValueError("Missing EOFC footer")
    return {"blob": b, "count": count, "table_off": table_off,
            "blocks": blocks, "footer": footer}


def bs1_rebuild(info: dict, new_blocks: dict) -> bytes:
    """new_blocks: {block_index: 新的子块字节}。重算块偏移表与外层大小。"""
    out = bytearray(info["blob"][:BS1_HEADER_SIZE])
    new_offsets = []
    cur = BS1_HEADER_SIZE
    for blk in info["blocks"]:
        new_offsets.append(cur)
        data = new_blocks.get(blk["index"], blk["raw"])
        out += data
        cur += len(data)
    out += info["footer"]
    t = info["table_off"]
    for i, o in enumerate(new_offsets):
        out[t + i * 4:t + i * 4 + 4] = p32(o)
    # 外层数据大小 = 所有子块大小之和 = 文件长 - 头(0x40) - EOFC(0x10)
    out[4:8] = p32(len(out) - BS1_HEADER_SIZE - EOFC_SIZE)
    return bytes(out)


# --------------------------------------------------------------------------
# extract / write
# --------------------------------------------------------------------------

def extract(src_d: Path, dst_d: Path):
    """BS1：每个 MSCR 子块输出 <stem>.<索引>.txt；裸 MSCR：输出 <stem>.txt。"""
    for f in src_d.rglob("*"):
        if f.suffix.lower() not in (".bs1", ".msb", ".msx"):
            continue
        try:
            b = f.read_bytes()
            if b[:4] == BS1_MAGIC:
                info = bs1_parse(b)
                for blk in info["blocks"]:
                    if blk["magic"] != MSCR_MAGIC:
                        continue
                    _, _, _, txts = mscr_parse(blk["raw"])
                    txts = _post_extract(txts)
                    out = dst_d / f.relative_to(src_d)
                    out = out.with_name(f.stem + ".%d.txt" % blk["index"])
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_text("\n".join(txts), "utf-8")
            elif b[:4] == MSCR_MAGIC:
                _, _, _, txts = mscr_parse(b)
                txts = _post_extract(txts)
                out = dst_d / f.relative_to(src_d).with_name(f.stem + ".txt")
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text("\n".join(txts), "utf-8")
        except Exception as e:
            print("E: %s - %s" % (f.name, e))


_MSCR_RE = re.compile(r"^(.+)\.(\d+)\.txt$")


def write(txt_d: Path, base_d: Path, out_d: Path):
    # 按基础文件分组：BS1 -> {块索引: txt}；裸 MSCR -> txt
    # 新命名：<stem>.<索引>.txt（BS1）/ <stem>.txt（裸 MSCR）
    groups, bare, seen = {}, {}, set()
    for f in txt_d.rglob("*.txt"):
        m = _MSCR_RE.match(f.name)
        rel = f.relative_to(txt_d)
        if m:
            # BS1：用 stem 还原成 <stem>.BS1
            rel_base = rel.with_name(m.group(1) + ".BS1")
            groups.setdefault(rel_base, {})[int(m.group(2))] = f
        else:
            bare[rel.with_suffix("")] = f

    # BS1 文件
    for rel_base, idx_map in groups.items():
        if rel_base in seen:
            continue
        base = base_d / rel_base
        if not base.exists():
            continue
        seen.add(rel_base)
        try:
            b = base.read_bytes()
            if b[:4] != BS1_MAGIC:
                continue
            info = bs1_parse(b)
            new_blocks = {}
            for blk in info["blocks"]:
                if blk["magic"] != MSCR_MAGIC:
                    continue
                tp = idx_map.get(blk["index"])
                if tp is None:
                    continue
                lines = [conv(x.replace("\\n", "//"))
                         for x in tp.read_text("utf-8").splitlines()]
                new_blocks[blk["index"]] = mscr_rebuild(blk["raw"], lines)
            out = bs1_rebuild(info, new_blocks)
            dst = out_d / rel_base
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(out)
        except Exception as e:
            print("E: %s - %s" % (base.name, e))

    # 裸 MSCR 文件
    for rel_base, tp in bare.items():
        if rel_base in seen:
            continue
        base = base_d / rel_base
        if not base.exists():
            continue
        try:
            raw = base.read_bytes()
            if raw[:4] != MSCR_MAGIC:
                continue
            seen.add(rel_base)
            lines = [conv(x.replace("\\n", "//"))
                     for x in tp.read_text("utf-8").splitlines()]
            out = mscr_rebuild(raw, lines)
            dst = out_d / rel_base
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(out)
        except Exception as e:
            print("E: %s - %s" % (base.name, e))


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(0)
    if a[0] == "e":
        extract(Path(a[1]), Path(a[2]))
    elif a[0] == "w":
        conv = char.make_translation_converter()
        write(Path(a[1]), Path(a[2]), Path(a[3]))
