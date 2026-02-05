import sys
from pathlib import Path
import unicodedata

u32 = lambda b: int.from_bytes(b, "little")
u16 = lambda b: int.from_bytes(b, "little")


# ---------- Common helpers ----------

def to_fullwidth_kana(s: str) -> str:
    return unicodedata.normalize("NFKC", s)


def yx_files(root: Path):
    yield from (p for p in root.rglob("*.yx") if p.is_file())


def parse_name_table(name_blob: bytes, count: int) -> dict[int, str]:
    off = 0
    m: dict[int, str] = {}
    for _ in range(count):
        end = name_blob.index(b"\x00", off)
        name = name_blob[off:end].decode("ascii")
        seg_id = u16(name_blob[end + 1:end + 3])
        m[seg_id] = name
        off = end + 3
    return m


def read_opval(buf: bytes, p: int, kind: int) -> tuple[int, int]:
    if kind < 2:
        return buf[p], 1
    else:
        return u16(buf[p:p + 2]), 2


def norm_text_for_dump(s: str) -> str:
    s = s.replace("\n", r"\n")
    s = to_fullwidth_kana(s)
    s = s.translate({ord(c): ord(fc) for c, fc in zip("!?~", "！？～")})
    return s


def cstr_at(blob: bytes, off: int) -> str:
    end = blob.index(b"\x00", off)
    return blob[off:end].decode("cp932")  # 严格，无错误处理


def is_str_start(blob: bytes, off: int) -> bool:
    if off < 0 or off >= len(blob):
        return False
    return off == 0 or blob[off - 1] == 0


def fmt_argA(k: int, v: int, v_str: str | None) -> str:
    if v_str is not None:
        return f'A(4,"{v_str}")'
    return f"A({k},{v:04X})"


def fmt_argB(k: int, v: int, v_str: str | None) -> str:
    if v_str is not None:
        return f'B(6,"{v_str}")'
    return f"B({k},{v:04X})"


def fmt_argC(k: int, v: int, v_str: str | None) -> str:
    if v_str is not None:
        return f'C(6,"{v_str}")'
    return f"C({k},{v:04X})"


# ---------- Disasm (d mode) ----------

def disasm_segment(op: bytes, str_blob: bytes, used_offsets: set[int]) -> list[str]:
    out: list[str] = []
    p = 0
    n = len(op)

    while p + 2 <= n:
        inst = u16(op[p:p + 2])
        cls = (inst >> 14) & 3
        op4 = (inst >> 10) & 0xF
        p += 2

        # 短指令：高两位 11，无参数
        if (inst & 0xC000) == 0xC000:
            if cls == 3 and (inst & 0x3FE0) != 0:
                group = (inst & 0x3FE0) >> 5
                sub = inst & 0x1F
                out.append(f"SYS({group},{sub})")
            else:
                out.append(f"C{cls}({op4})")
            continue

        args: list[tuple[str, int, int, str | None]] = []

        hasA = (inst & 0x0300) != 0
        hasB = ((inst & 0x03FF) >> 8) >= 2
        hasC = ((inst >> 8) & 0x3) == 3

        # A
        if hasA:
            kindA = 4 if (inst & 0xC000) == 0x8000 else ((inst & 0x00C0) >> 6)
            valA, c = read_opval(op, p, kindA)
            p += c
            sA: str | None = None
            # 特例：C2(2) 的 A(kind=4) 是入口/场景名字符串
            if cls == 2 and op4 == 2 and kindA == 4 and is_str_start(str_blob, valA):
                used_offsets.add(valA)
                sA = norm_text_for_dump(cstr_at(str_blob, valA))
            args.append(("A", kindA, valA, sA))

        # B
        if hasB:
            kindB = (inst & 0x0038) >> 3
            valB, c = read_opval(op, p, kindB)
            p += c
            sB: str | None = None
            # 一般规则：kind=6 且是串首 ⇒ 文本
            if kindB == 6 and is_str_start(str_blob, valB):
                used_offsets.add(valB)
                sB = norm_text_for_dump(cstr_at(str_blob, valB))
            args.append(("B", kindB, valB, sB))

        # C
        if hasC:
            kindC = inst & 0x0007
            valC, c = read_opval(op, p, kindC)
            p += c
            sC: str | None = None
            if kindC == 6 and is_str_start(str_blob, valC):
                used_offsets.add(valC)
                sC = norm_text_for_dump(cstr_at(str_blob, valC))
            args.append(("C", kindC, valC, sC))

        # 指令头
        if cls == 3 and (inst & 0x3FE0) != 0:
            group = (inst & 0x3FE0) >> 5
            sub = inst & 0x1F
            s = f"SYS({group},{sub})"
        else:
            s = f"C{cls}({op4})"

        if args:
            parts: list[str] = []
            for nm, k, v, vs in args:
                if nm == "A":
                    parts.append(fmt_argA(k, v, vs))
                elif nm == "B":
                    parts.append(fmt_argB(k, v, vs))
                else:
                    parts.append(fmt_argC(k, v, vs))
            s += " " + " ".join(parts)

        out.append(s)

    if p != n:
        raise ValueError(f"Segment decode mismatch: consumed={p}, size={n}, trailing={op[p:].hex()}")

    return out


def dump_one(src: Path, out_asm: Path):
    data = src.read_bytes()
    if data[:4] != b"YX01":
        raise ValueError(f"Bad magic: {src}")

    idx_off = u32(data[0x08:0x0C])
    idx_cnt = u32(data[0x0C:0x10])
    name_off = u32(data[0x10:0x14])
    name_cnt = u32(data[0x14:0x18])
    op_off = u32(data[0x18:0x1C])
    op_size = u32(data[0x1C:0x20])
    str_off = u32(data[0x20:0x24])
    str_size = u32(data[0x24:0x28])

    # 段索引表
    idx: list[tuple[int, int]] = []
    p = idx_off
    for _ in range(idx_cnt):
        off = u32(data[p:p + 4])
        sz = u32(data[p + 4:p + 8])
        idx.append((off, sz))
        p += 8

    # 名称表
    name_blob = data[name_off:op_off]
    id2name = parse_name_table(name_blob, name_cnt)

    op_end = op_off + op_size
    if op_end > len(data):
        raise ValueError(f"Bad opcode size in {src}")

    # 字符区
    if str_off != 0 and str_size != 0:
        s_end = str_off + str_size
        if s_end > len(data):
            raise ValueError(f"Bad string size in {src}")
        str_blob = data[str_off:s_end]
    else:
        str_blob = b""

    out: list[str] = []
    used_offsets: set[int] = set()

    # 段：用 [id:名称] 格式
    for seg_id, (rel, sz) in enumerate(idx):
        name = id2name.get(seg_id)
        if name:
            header = f"[{seg_id}:{name}]"
        else:
            header = f"[{seg_id}:{seg_id}]"
        out.append(header)

        a = op_off + rel
        b = a + sz
        if b > op_end:
            raise ValueError(f"Bad segment {seg_id} in {src}")
        out.extend(disasm_segment(data[a:b], str_blob, used_offsets))
        out.append("")

    # 不再输出 [string] 段，字符区完全由 B(6,"…") / C2(2) A(4,"…") 重建
    out_asm.parent.mkdir(parents=True, exist_ok=True)
    out_asm.write_text("\n".join(out), encoding="utf-8", newline="\n")


# ---------- Encode (e mode): asm -> yx ----------

class AsmInstr:
    def __init__(self, cls: int, op4: int):
        self.cls = cls
        self.op4 = op4
        # args: list of ("A"/"B"/"C", kind, val_or_offset, is_str, text)
        self.args: list[tuple[str, int, int | None, bool, str | None]] = []


def parse_arg(token: str) -> tuple[str, int, int | None, bool, str | None]:
    # A(4,"...") / B(6,"...") / C(6,"...") or A(0,0040)
    if "(" not in token:
        raise ValueError(f"Bad token (missing '('): {token!r}")
    name, rest = token.split("(", 1)
    name = name
    rest = rest.rstrip(")")
    k_str, v_str = rest.split(",", 1)
    kind = int(k_str)
    v_str = v_str
    if v_str.startswith('"') and v_str.endswith('"'):
        text = v_str[1:-1]
        text = text.replace(r'\n', '\n')
        return name, kind, None, True, text
    else:
        val = int(v_str, 16)
        return name, kind, val, False, None


def parse_instr(line: str) -> AsmInstr | None:
    # 不要 strip 整行，避免破坏首尾空格（尤其是字符串里的）
    # 只用于判断/解析的临时视图：跳过左边空白
    s = line.lstrip()
    if not s:
        return None
    if s.startswith("#") or s.startswith(";"):
        return None

    if s.startswith("SYS("):
        inside = s[4:].rstrip(")")
        g_str, sub_str = inside.split(",", 1)
        group = int(g_str)
        sub = int(sub_str)
        inst = AsmInstr(3, 0)
        inst.sys_group = group
        inst.sys_sub = sub
        return inst

    if s.startswith("C"):
        # 1) 解析头：只取第一个“非空白字段”作为 head
        #    这里等价于原来的 head = line.split()[0]，但不会把字符串拆碎
        parts = s.split(None, 1)
        head = parts[0]

        # C1(0)
        hname, rest = head.split("(", 1)
        cls = int(hname[1:])
        op4 = int(rest.rstrip(")"))
        inst = AsmInstr(cls, op4)

        # 2) 从整行 s 中“扫描提取” A(...)/B(...)/C(...) 参数块
        i = 0
        n = len(s)
        while i < n:
            ch = s[i]
            if ch in ("A", "B", "C") and i + 1 < n and s[i + 1] == "(":
                start = i
                i += 2  # skip X(
                depth = 1
                in_str = False
                esc = False
                while i < n and depth > 0:
                    c = s[i]
                    if in_str:
                        if esc:
                            esc = False
                        elif c == "\\":
                            esc = True
                        elif c == '"':
                            in_str = False
                    else:
                        if c == '"':
                            in_str = True
                        elif c == "(":
                            depth += 1
                        elif c == ")":
                            depth -= 1
                    i += 1
                if depth != 0:
                    raise ValueError(f"Unclosed arg block: {s[start:]!r}")

                tok = s[start:i]
                nm, k, v, is_str, txt = parse_arg(tok)
                inst.args.append((nm, k, v, is_str, txt))
                continue
            i += 1

        return inst

    return None


def encode_instr(inst: AsmInstr, str_off_lookup: dict[tuple[int, str], int]) -> bytes:
    if hasattr(inst, "sys_group") and hasattr(inst, "sys_sub") and not inst.args:
        g = int(inst.sys_group)
        sub = int(inst.sys_sub)
        if not (0 <= g <= 0x1FF and 0 <= sub <= 0x1F):
            raise ValueError(f"Bad SYS({g},{sub})")
        inst16 = 0xC000 | ((g & 0x1FF) << 5) | (sub & 0x1F)
        return inst16.to_bytes(2, "little")

    cls = inst.cls & 3
    op4 = inst.op4 & 0xF

    argA = next((a for a in inst.args if a[0] == "A"), None)
    argB = next((a for a in inst.args if a[0] == "B"), None)
    argC = next((a for a in inst.args if a[0] == "C"), None)

    hasA = argA is not None
    hasB = argB is not None
    hasC = argC is not None

    if hasC and not hasB:
        raise ValueError("C present but B missing")
    if hasB and not hasA:
        raise ValueError("B present but A missing")

    if not hasA:
        mode = 0
    elif not hasB:
        mode = 1
    elif not hasC:
        mode = 2
    else:
        mode = 3

    kindA = argA[1] if hasA else 0
    kindB = argB[1] if hasB else 0
    kindC = argC[1] if hasC else 0

    inst16 = (cls << 14) | (op4 << 10) | (mode << 8)
    if hasA:
        if kindA == 4:
            if cls != 2:
                raise ValueError("A kind=4 requires class=2")
        else:
            inst16 |= (kindA & 3) << 6
    if hasB:
        inst16 |= (kindB & 7) << 3
    if hasC:
        inst16 |= (kindC & 7)

    out = bytearray()
    out.extend(inst16.to_bytes(2, "little"))

    def emit(kind: int, v: int):
        if kind < 2:
            out.append(v & 0xFF)
        else:
            out.extend(int(v).to_bytes(2, "little"))

    def value_for(arg, kind):
        nm, k, v, is_str, txt = arg
        if is_str:
            return str_off_lookup[(kind, txt)]
        return int(v)

    if hasA:
        emit(kindA, value_for(argA, kindA))
    if hasB:
        emit(kindB, value_for(argB, kindB))
    if hasC:
        emit(kindC, value_for(argC, kindC))

    return bytes(out)


def build_string_blob_from_asm(all_insts: list[AsmInstr]) -> tuple[bytes, dict[tuple[int, str], int]]:
    """
    收集所有 is_str=True 的参数文本，cp936 编码，去重合并，生成 blob。
    返回:
      - blob: bytes
      - lookup: {(kind,text) -> offset}
    """
    # 收集所有字符串
    texts: list[tuple[int, str]] = []  # (kind, text)
    for inst in all_insts:
        for nm, k, v, is_str, txt in inst.args:
            if is_str and txt is not None:
                texts.append((k, txt))

    # 去重(保持顺序)
    seen: set[tuple[int, str]] = set()
    uniq: list[tuple[int, str]] = []
    for item in texts:
        if item not in seen:
            seen.add(item)
            uniq.append(item)

    # 构建 blob
    blob = bytearray()
    lookup: dict[tuple[int, str], int] = {}
    for kind, txt in uniq:
        off = len(blob)
        b = txt.encode("cp936",errors="replace")
        blob += b + b"\x00"
        lookup[(kind, txt)] = off

    return bytes(blob), lookup


def build_yx_from_asm(asm_path: Path, out_yx: Path):
    lines = asm_path.read_text(encoding="utf-8").splitlines()

    # 1) 解析段头 [id:名称] 和段内指令
    segments: dict[int, tuple[str, list[AsmInstr]]] = {}
    cur_id: int | None = None
    cur_name: str | None = None
    cur_instrs: list[AsmInstr] | None = None

    for line in lines:
        s = line
        if not s:
            continue
        if s.startswith("[") and s.endswith("]"):
            # new segment
            body = s[1:-1]
            if ":" in body:
                id_str, name = body.split(":", 1)
            else:
                id_str, name = body, body
            seg_id = int(id_str)
            if cur_id is not None:
                segments[cur_id] = (cur_name if cur_name is not None else str(cur_id),
                                    cur_instrs or [])
            cur_id = seg_id
            cur_name = name
            cur_instrs = []
            continue
        inst = parse_instr(s)
        if inst is not None:
            if cur_instrs is None:
                raise ValueError(f"Instruction before any segment in {asm_path}")
            cur_instrs.append(inst)

    if cur_id is not None:
        segments[cur_id] = (cur_name if cur_name is not None else str(cur_id),
                            cur_instrs or [])

    if not segments:
        raise ValueError(f"No segments found in {asm_path}")

    # 确保按 id 排序
    seg_ids = sorted(segments.keys())
    seg_list: list[tuple[int, str, list[AsmInstr]]] = []
    all_insts: list[AsmInstr] = []

    for sid in seg_ids:
        name, instrs = segments[sid]
        seg_list.append((sid, name, instrs))
        all_insts.extend(instrs)

    # 2) 从所有指令中收集字符串，构建字符串 blob（去重合并）
    str_blob, str_lookup = build_string_blob_from_asm(all_insts)

    # 3) 编码指令为 opcode 字节流，并记录每段的 (off,size)
    seg_bytes: list[bytes] = []
    seg_off_size: list[tuple[int, int]] = []
    cur_off = 0
    for sid, name, instrs in seg_list:
        b_seg = bytearray()
        for inst in instrs:
            b_seg += encode_instr(inst, str_lookup)
        seg_bytes.append(bytes(b_seg))
        seg_off_size.append((cur_off, len(b_seg)))
        cur_off += len(b_seg)

    opcode_blob = b"".join(seg_bytes)

    # 4) 构建 name table: name\0 + u16(id)
    name_entries: list[tuple[str, int]] = []
    for sid, name, instrs in seg_list:
        # 名称和 id 不同才写名字；如果你希望都写，可以去掉这个 if
        if name != str(sid):
            name_entries.append((name, sid))

    # 修正为小端（上一行覆盖）：
    name_blob = bytearray()
    for nm, sid in name_entries:
        b = nm.encode("ascii")
        name_blob += b + b"\x00" + sid.to_bytes(2, "little")

    # 5) 组装整个 yx 文件
    # Header(0x28):
    # 0x00: "YX01"
    # 0x04: file_size
    # 0x08: idx_off
    # 0x0C: idx_cnt
    # 0x10: name_off
    # 0x14: name_cnt
    # 0x18: op_off
    # 0x1C: op_size
    # 0x20: str_off
    # 0x24: str_size

    idx_cnt = len(seg_list)
    header_size = 0x28
    idx_off = header_size
    idx_size = idx_cnt * 8
    name_off = idx_off + idx_size
    name_size = len(name_blob)
    op_off = name_off + name_size
    op_size = len(opcode_blob)
    str_off = op_off + op_size
    str_size = len(str_blob)
    file_size = str_off + str_size

    data = bytearray(b"\x00" * file_size)
    data[0:4] = b"YX01"
    data[4:8] = file_size.to_bytes(4, "little")
    data[8:12] = idx_off.to_bytes(4, "little")
    data[12:16] = idx_cnt.to_bytes(4, "little")
    data[16:20] = name_off.to_bytes(4, "little")
    data[20:24] = len(name_entries).to_bytes(4, "little")
    data[24:28] = op_off.to_bytes(4, "little")
    data[28:32] = op_size.to_bytes(4, "little")
    data[32:36] = str_off.to_bytes(4, "little")
    data[36:40] = str_size.to_bytes(4, "little")

    # 写索引表
    p = idx_off
    for off, sz in seg_off_size:
        data[p:p + 4] = off.to_bytes(4, "little")
        data[p + 4:p + 8] = sz.to_bytes(4, "little")
        p += 8

    # 写 name table
    data[name_off:name_off + name_size] = name_blob

    # 写 opcode
    data[op_off:op_off + op_size] = opcode_blob

    # 写 string blob
    data[str_off:str_off + str_size] = str_blob

    out_yx.parent.mkdir(parents=True, exist_ok=True)
    out_yx.write_bytes(bytes(data))


# ---------- Main ----------

def main(argv):
    if len(argv) < 4:
        print(
            "Usage:\n"
            "  python yx.py d <input_yx_dir> <output_asm_dir>\n"
            "  python yx.py e <asm_dir> <output_yx_dir>"
        )
        return 2

    mode = argv[1].lower()

    if mode == "d" and len(argv) == 4:
        in_dir, out_dir = map(Path, argv[2:4])
        for src in yx_files(in_dir):
            rel = src.relative_to(in_dir)
            out_asm = (out_dir / rel).with_suffix(".asm")
            dump_one(src, out_asm)
        return 0

    if mode == "e" and len(argv) == 4:
        asm_dir, out_dir = map(Path, argv[2:4])
        for asm_path in asm_dir.rglob("*.asm"):
            if not asm_path.is_file():
                continue
            rel = asm_path.relative_to(asm_dir)
            out_yx = (out_dir / rel).with_suffix(".yx")
            build_yx_from_asm(asm_path, out_yx)
        return 0

    print(
        "Bad args. Use:\n"
        "  python yx.py d <input_yx_dir> <output_asm_dir>\n"
        "  python yx.py e <asm_dir> <output_yx_dir>"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))