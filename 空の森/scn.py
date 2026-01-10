from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Literal, Optional, Union


class SCNFormatError(ValueError):
    pass


def crc32_reflected(data: bytes) -> int:
    crc = 0xFFFFFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xEDB88320
            else:
                crc >>= 1
    return (~crc) & 0xFFFFFFFF


class Cursor:
    def __init__(self, data: bytes, offset: int = 0):
        self.data = data
        self.off = offset

    def tell(self) -> int:
        return self.off

    def remaining(self) -> int:
        return len(self.data) - self.off

    def read_u8(self) -> int:
        if self.off + 1 > len(self.data):
            raise SCNFormatError("unexpected EOF while reading u8")
        v = self.data[self.off]
        self.off += 1
        return v

    def read_u16be(self) -> int:
        if self.off + 2 > len(self.data):
            raise SCNFormatError("unexpected EOF while reading u16be")
        v = (self.data[self.off] << 8) | self.data[self.off + 1]
        self.off += 2
        return v

    def read_u32be(self) -> int:
        if self.off + 4 > len(self.data):
            raise SCNFormatError("unexpected EOF while reading u32be")
        v = (
            (self.data[self.off] << 24)
            | (self.data[self.off + 1] << 16)
            | (self.data[self.off + 2] << 8)
            | self.data[self.off + 3]
        )
        self.off += 4
        return v

    def read_bytes(self, n: int) -> bytes:
        if n < 0:
            raise ValueError("n must be >= 0")
        if self.off + n > len(self.data):
            raise SCNFormatError(f"unexpected EOF while reading {n} bytes")
        out = self.data[self.off : self.off + n]
        self.off += n
        return out

    def peek_u8(self) -> int:
        if self.off + 1 > len(self.data):
            raise SCNFormatError("unexpected EOF while peeking u8")
        return self.data[self.off]


@dataclass(slots=True)
class ParamString:
    tag: Literal[0] = 0
    raw: bytes = b""
    offset: Optional[int] = None

    def text(self, encoding: str = "cp932", errors: str = "replace") -> str:
        return self.raw.decode(encoding, errors=errors)

    @staticmethod
    def from_text(text: str, encoding: str = "cp932") -> "ParamString":
        return ParamString(raw=text.encode(encoding))


@dataclass(slots=True)
class ParamInt:
    tag: Literal[1] = 1
    value: int = 0


@dataclass(slots=True)
class ParamRaw1:
    tag: int = 0


Param = Union[ParamString, ParamInt, ParamRaw1]


@dataclass(slots=True)
class Block:
    start: int
    type: int
    subcount: int
    params: list[Param]


@dataclass(slots=True)
class SCNFile:
    header_u16: int
    blocks: list[Block]
    tail_table: list[int]
    tail_value: int
    remainder: bytes = b""
    parsed_end: Optional[int] = None
    code_end: Optional[int] = None
    tail_parsed: bool = True

    def to_bytes(self) -> bytes:
        out = bytearray()
        out += b"VNEG"
        out += self.header_u16.to_bytes(2, "big", signed=False)
        out += len(self.blocks).to_bytes(2, "big", signed=False)
        for blk in self.blocks:
            out += bytes([blk.type & 0xFF])
            out += (blk.subcount & 0xFFFF).to_bytes(2, "big", signed=False)
            out += bytes([len(blk.params) & 0xFF])
            for p in blk.params:
                if isinstance(p, ParamString):
                    out += b"\x00"
                    out += p.raw + b"\x00"
                elif isinstance(p, ParamInt):
                    out += b"\x01"
                    out += int(p.value & 0xFFFFFFFF).to_bytes(4, "big", signed=False)
                elif isinstance(p, ParamRaw1):
                    out += bytes([p.tag & 0xFF])
                else:
                    raise TypeError(f"unknown param type: {type(p)!r}")
        out += (len(self.tail_table) & 0xFFFF).to_bytes(2, "big", signed=False)
        for v in self.tail_table:
            out += int(v & 0xFFFFFFFF).to_bytes(4, "big", signed=False)
        out += int(self.tail_value & 0xFFFFFFFF).to_bytes(4, "big", signed=False)
        out += self.remainder
        return bytes(out)

    def computed_crc32(self) -> int:
        return crc32_reflected(self.to_bytes())


def _parse_param(cur: Cursor) -> Param:
    tag_offset = cur.tell()
    tag = cur.read_u8()
    if tag == 0:
        raw = bytearray()
        while True:
            b = cur.read_u8()
            if b == 0:
                break
            raw.append(b)
        return ParamString(raw=bytes(raw), offset=tag_offset)
    if tag == 1:
        v = cur.read_u32be()
        # 游戏代码里是把 u32_be 读出后当 int 塞进 double；这里保留原始 u32
        return ParamInt(value=v)
    return ParamRaw1(tag=tag)


def _parse_block(cur: Cursor) -> Block:
    # sub_427F80: type=u8, subcount=u16_be, paramCount=u8，然后 paramCount 次 sub_430400
    start = cur.tell()
    b_type = cur.read_u8()
    subcount = cur.read_u16be()
    param_count = cur.read_u8()
    params: list[Param] = []
    for _ in range(param_count):
        params.append(_parse_param(cur))
    return Block(start=start, type=b_type, subcount=subcount, params=params)


@dataclass(slots=True)
class ParseTrace:
    lines: list[str]

    def add(self, msg: str) -> None:
        self.lines.append(msg)


def parse_scn_with_trace(data: bytes, *, blocks_override: Optional[int] = None) -> tuple[SCNFile, ParseTrace]:
    trace = ParseTrace(lines=[])
    cur = Cursor(data, 0)

    trace.add(f"start=0x{cur.tell():X}")
    magic = cur.read_bytes(4)
    trace.add(f"magic={magic!r} off=0x{cur.tell():X}")
    if magic != b"VNEG":
        raise SCNFormatError(f"bad magic: {magic!r}")

    header_u16 = cur.read_u16be()
    trace.add(f"header_u16=0x{header_u16:04X} off=0x{cur.tell():X}")

    block_count_on_disk = cur.read_u16be()
    block_count = block_count_on_disk
    if blocks_override is not None:
        block_count = blocks_override
        trace.add(
            f"block_count(on_disk)={block_count_on_disk} block_count(override)={block_count} off=0x{cur.tell():X}"
        )
    else:
        trace.add(f"block_count={block_count} off=0x{cur.tell():X}")

    blocks: list[Block] = []
    for bi in range(block_count):
        b_start = cur.tell()
        blk = _parse_block(cur)
        b_end = cur.tell()
        blocks.append(blk)
        trace.add(
            f"block[{bi}] start=0x{b_start:X} end=0x{b_end:X} len=0x{(b_end-b_start):X} "
            f"type=0x{blk.type:02X} subcount={blk.subcount} param_count={len(blk.params)}"
        )

    code_end = cur.tell()
    trace.add(f"code_end=0x{code_end:X} (after blocks)")

    tail_table: list[int] = []
    tail_value = 0
    parsed_end: Optional[int] = None
    try:
        tail_count = cur.read_u16be()
        trace.add(f"tail_count={tail_count} off=0x{cur.tell():X}")

        for i in range(tail_count):
            v = cur.read_u32be()
            tail_table.append(v)
            if i < 20:
                trace.add(f"tail_table[{i}]=0x{v:X} off=0x{cur.tell():X}")
            elif i == 20:
                trace.add("tail_table[...] (truncated)")

        tail_value = cur.read_u32be()
        trace.add(f"tail_value=0x{tail_value:X} off=0x{cur.tell():X}")
        parsed_end = cur.tell()
    except SCNFormatError as e:
        trace.add(f"ERROR: {e} at off=0x{cur.tell():X}")
        parsed_end = cur.tell()

    remainder = cur.read_bytes(cur.remaining())
    trace.add(f"remainder_len=0x{len(remainder):X} file_size=0x{len(data):X}")

    return (
        SCNFile(
            header_u16=header_u16,
            blocks=blocks,
            tail_table=tail_table,
            tail_value=tail_value,
            remainder=remainder,
            parsed_end=parsed_end,
            code_end=code_end,
            tail_parsed=True,
        ),
        trace,
    )

def parse_scn_blocks_only_with_trace(data: bytes, *, blocks_override: Optional[int] = None) -> tuple[SCNFile, ParseTrace]:
    trace = ParseTrace(lines=[])
    cur = Cursor(data, 0)
    trace.add(f"start=0x{cur.tell():X}")
    magic = cur.read_bytes(4)
    trace.add(f"magic={magic!r} off=0x{cur.tell():X}")
    if magic != b"VNEG":
        raise SCNFormatError(f"bad magic: {magic!r}")
    header_u16 = cur.read_u16be()
    trace.add(f"header_u16=0x{header_u16:04X} off=0x{cur.tell():X}")

    block_count_on_disk = cur.read_u16be()
    block_count = block_count_on_disk
    if blocks_override is not None:
        block_count = blocks_override
        trace.add(
            f"block_count(on_disk)={block_count_on_disk} block_count(override)={block_count} off=0x{cur.tell():X}"
        )
    else:
        trace.add(f"block_count={block_count} off=0x{cur.tell():X}")

    blocks: list[Block] = []
    for bi in range(block_count):
        b_start = cur.tell()
        blk = _parse_block(cur)
        b_end = cur.tell()
        blocks.append(blk)
        trace.add(
            f"block[{bi}] start=0x{b_start:X} end=0x{b_end:X} len=0x{(b_end-b_start):X} "
            f"type=0x{blk.type:02X} subcount={blk.subcount} param_count={len(blk.params)}"
        )

    code_end = cur.tell()
    trace.add(f"code_end=0x{code_end:X} (after blocks)")
    parsed_end = code_end
    remainder = cur.read_bytes(cur.remaining())
    trace.add(f"remainder_len=0x{len(remainder):X} file_size=0x{len(data):X}")

    return (
        SCNFile(
            header_u16=header_u16,
            blocks=blocks,
            tail_table=[],
            tail_value=0,
            remainder=remainder,
            parsed_end=parsed_end,
            code_end=code_end,
            tail_parsed=False,
        ),
        trace,
    )


def parse_scn_cut_with_trace(
    data: bytes,
    *,
    cut_at: int,
    blocks_override: Optional[int] = None,
) -> tuple[SCNFile, ParseTrace]:
    # 调试用：仍按 blockCount（或 override）解析 blocks，但不解析 tail；
    # 直接把 parsed_end 强制设为 cut_at，让 remainder 从 cut_at 开始。
    scn, trace = parse_scn_blocks_only_with_trace(data, blocks_override=blocks_override)
    if cut_at < 0 or cut_at > len(data):
        raise SCNFormatError(f"cut_at out of range: 0x{cut_at:X}")
    scn.parsed_end = cut_at
    scn.remainder = data[cut_at:]
    trace.add(f"cut_at=0x{cut_at:X} remainder_len=0x{len(scn.remainder):X}")
    return scn, trace


def parse_scn(data: bytes) -> SCNFile:
    cur = Cursor(data, 0)
    magic = cur.read_bytes(4)
    if magic != b"VNEG":
        raise SCNFormatError(f"bad magic: {magic!r}")
    header_u16 = cur.read_u16be()

    block_count = cur.read_u16be()
    blocks = [_parse_block(cur) for _ in range(block_count)]
    code_end = cur.tell()

    tail_count = cur.read_u16be()
    tail_table = [cur.read_u32be() for _ in range(tail_count)]
    tail_value = cur.read_u32be()
    parsed_end = cur.tell()
    remainder = cur.read_bytes(cur.remaining())
    return SCNFile(
        header_u16=header_u16,
        blocks=blocks,
        tail_table=tail_table,
        tail_value=tail_value,
        remainder=remainder,
        parsed_end=parsed_end,
        code_end=code_end,
    )


OPCODE_NAMES: dict[int, str] = {
    0x00: "VNString",
    0x01: "VNBoolean",
    0x02: "VNInteger",
    0x03: "VNString2",
    0x04: "VNFlag",
    0x05: "VNRegister",
    0x06: "VNEvent",
    0x07: "VNLayer",
    0x08: "VNTextWindow",
    0x09: "VNTextWindow2",
    0x0A: "VNSoundTrack",
    0x0B: "VNFile",
    0x0C: "VNButton",
    0x0D: "VNBytecodeEngineInfo",
    0x0E: "VNStringFlag",
    0x16: "VNScrollImages",
    0x17: "VNClickableMap",
}


def _scenario_path_from_str(base_dir: Path, s: str) -> list[Path]:
    # 复刻 sub_4315C0 的规则：无 / -> scenario/<s>.scn
    # 有 / -> 先 <s>.scn，失败再 scenario<从第一个/开始的后半截>.scn
    if "/" not in s:
        return [base_dir / "scenario" / f"{s}.scn"]
    first = base_dir / f"{s}.scn"
    slash_idx = s.find("/")
    second = base_dir / "scenario" / f"{s[slash_idx:]}.scn"
    return [first, second]


def load_scn_by_str(base_dir: Path, s: str) -> tuple[Path, SCNFile]:
    tried = _scenario_path_from_str(base_dir, s)
    for p in tried:
        if p.exists():
            return p, parse_scn(p.read_bytes())
    raise FileNotFoundError("not found, tried: " + ", ".join(str(p) for p in tried))


def dump_txt(
    scn: SCNFile,
    *,
    data: Optional[bytes] = None,
    trace: Optional[ParseTrace] = None,
    encoding: str = "cp932",
    include_crc32: bool = False,
    include_tail: bool = True,
    simple: bool = False,
    include_text_stream: bool = True,
    mixed: bool = False,
) -> str:
    lines: list[str] = []
    name_candidates = _build_name_id_map_from_blocks(scn, encoding=encoding)
    lines.append("# SCN-TXT v2")
    lines.append(f"# strings_encoding: {encoding}")
    lines.append(f"# header_u16 = 0x{scn.header_u16:04X}")
    if data is not None and scn.parsed_end is not None:
        lines.append(f"# file_size = 0x{len(data):X}")
        if scn.code_end is not None:
            lines.append(f"# code_end = 0x{scn.code_end:X}  (after blocks)")
        tail_note = " (tail ends here)" if scn.tail_parsed else " (after blocks; tail skipped)"
        lines.append(f"# parsed_end = 0x{scn.parsed_end:X}{tail_note}")
        lines.append(f"# remainder_len = 0x{len(scn.remainder):X}")
    lines.append("")
    if trace is not None:
        lines.append("[trace]")
        lines.extend(trace.lines)
        lines.append("")
    lines.append("[code]")
    for blk in scn.blocks:
        opname = OPCODE_NAMES.get(blk.type, f"op_{blk.type:02X}")
        rendered_params: list[str] = []
        for p in blk.params:
            if isinstance(p, ParamString):
                rendered_params.append(
                    p.text(encoding=encoding, errors="replace")
                    .replace("\r", "\\r")
                    .replace("\n", "\\n")
                    .__repr__()
                )
            elif isinstance(p, ParamInt):
                rendered_params.append(f"0x{p.value:08X}")
            elif isinstance(p, ParamRaw1):
                rendered_params.append(f"tag(0x{p.tag:02X})")
            else:
                raise TypeError(f"unknown param type: {type(p)!r}")
        args = ", ".join(rendered_params)
        # 按你的建议：一个函数就是一个块 -> name(args...)
        lines.append(f"0x{blk.start:04X}: {opname}({args})  # subcount={blk.subcount}")
    lines.append("")

    if data is not None and not simple:
        lines.append("[strings]")
        lines.append("# heuristically extracted strings (cp932), offsets are file offsets; '*' means referenced by tag=0 params")
        referenced = {p.offset for blk in scn.blocks for p in blk.params if isinstance(p, ParamString) and p.offset is not None}
        for off, s in scan_strings_loose(data, encoding=encoding):
            mark = "*" if off in referenced else " "
            lines.append(f"{mark} 0x{off:04X} {s!r}")
        lines.append("")

    if include_tail and scn.tail_parsed:
        # 末尾表：目前只能确认“u16 count + u32_be * count + u32_be value”，语义未知（可能是索引/偏移）
        lines.append("[tail]")
        # IDA: sub_431860(this, idx) -> this[19] + *(this[17] + 8*idx)
        # 说明 tail_table 的每个值是“相对于 this[19]（即 parsed_end 指针）”的偏移。
        base = scn.parsed_end or 0
        lines.append(f"# tail_base = 0x{base:X}  (this[19] / parsed_end)")
        lines.append(f"# tail_value = 0x{scn.tail_value:08X}  (often equals remainder_len)")
        if data is not None and scn.parsed_end is not None:
            lines.append(f"# remainder_len = 0x{len(scn.remainder):X}")
            lines.append(f"# tail_base + tail_value = 0x{(base + scn.tail_value):X}")
        lines.append("tail_table = [" + ", ".join(f"0x{v:08X}" for v in scn.tail_table) + "]")
        if scn.tail_table:
            lines.append("# tail_table as file offsets:")
            for i, v in enumerate(scn.tail_table[:50]):
                lines.append(f"#   [{i}] 0x{v:08X} -> 0x{(base + v):X}")
            if len(scn.tail_table) > 50:
                lines.append(f"#   ... ({len(scn.tail_table) - 50} more)")
        lines.append("")

    if data is not None and scn.tail_parsed and scn.parsed_end is not None:
        segs = split_remainder_by_tail(scn)
        if segs:
            base = scn.parsed_end
            if not simple:
                lines.append("[remainder]")
                lines.append("# segments split by tail_table offsets (relative to tail_base)")
            lines.append("[script]")
            lines.append("# Script timeline: ops then following text stream (best-effort).")

            for seg in segs[:200]:
                abs_start = base + seg.rel_start
                abs_end = base + seg.rel_end
                seg_bytes = data[abs_start:abs_end]

                if mixed:
                    items = decode_remainder_mixed(seg_bytes, encoding=encoding, max_items=20000)
                    stop_at = 0
                    first_text_off = None
                    bc = []
                else:
                    # Detect likely text stream start
                    first_text_off: Optional[int] = None
                    text_candidates = scan_strings_loose(seg_bytes, encoding=encoding, min_chars=4)
                    if text_candidates:
                        cand = min(off for off, _ in text_candidates)
                        # Only accept if it looks like a real boundary: candidate should be
                        # close to where bytecode naturally stops.
                        bc_probe = decode_remainder_bytecode(seg_bytes, max_items=5000)
                        stop_at_probe = (bc_probe[-1].rel_off + bc_probe[-1].size) if bc_probe else 0
                        if cand >= stop_at_probe and cand - stop_at_probe <= 0x40:
                            first_text_off = cand

                    # Decode bytecode, hard-stopping at detected text stream start (if any)
                    bc = decode_remainder_bytecode(
                        seg_bytes,
                        max_items=5000,
                        stop_at=first_text_off,
                    )
                    stop_at = (bc[-1].rel_off + bc[-1].size) if bc else 0

                # Segment header (only once per segment)
                lines.append(
                    f"# seg[{seg.index}] rel=0x{seg.rel_start:X}..0x{seg.rel_end:X} abs=0x{abs_start:X}..0x{abs_end:X} len=0x{seg.length:X}"
                )
                if mixed:
                    lines.append("#   mixed_mode=1")
                    for it in items[:4000]:
                        if it.kind == "op":
                            op_str = f"OP_{it.op:02X}"
                            if it.args:
                                args = " ".join(f"0x{x:X}" for x in it.args)
                                lines.append(f"@+0x{it.rel_off:X} {op_str} {args}")
                            else:
                                lines.append(f"@+0x{it.rel_off:X} {op_str}")
                        elif it.kind == "text":
                            lines.append(f"@+0x{it.rel_off:X} TEXT \"{escape_script_string(it.text)}\"")
                        else:
                            lines.append(f"@+0x{it.rel_off:X} BYTE {it.raw.hex(' ')}")
                    if len(items) > 4000:
                        lines.append(f"#   ... ({len(items) - 4000} more items)")
                else:
                    if bc:
                        lines.append(f"#   bytecode_stop_at=0x{stop_at:X}")
                    if first_text_off is not None:
                        lines.append(f"#   text_stream_at=0x{first_text_off:X}")
                        if stop_at < first_text_off:
                            gap = seg_bytes[stop_at:first_text_off]
                            # Keep it compact; this area is often padding/unknown tables.
                            gap_hex = gap.hex(" ")
                            if len(gap_hex) > 200:
                                gap_hex = gap_hex[:200] + " ..."
                            lines.append(f"#   gap_bytes=0x{(first_text_off - stop_at):X}")
                            lines.append(f"@+0x{stop_at:X} DATA {gap_hex}")

                    # Emit bytecode items (compact, no raw hex by default)
                    for it in bc[:1000]:
                        if first_text_off is not None and it.rel_off >= first_text_off:
                            break
                        op_str = f"OP_{it.op:04X}" if it.op > 0xFF else f"OP_{it.op:02X}"
                        if it.args:
                            args = " ".join(f"0x{x:X}" for x in it.args)
                            lines.append(f"@+0x{it.rel_off:X} {op_str} {args}")
                        else:
                            lines.append(f"@+0x{it.rel_off:X} {op_str}")
                    if bc and len(bc) > 1000:
                        lines.append(f"#   ... ({len(bc) - 1000} more ops)")

                    # Emit text stream lines as TEXT items
                    if include_text_stream and first_text_off is not None:
                        ts = parse_text_stream(seg_bytes, first_text_off)
                        if ts:
                            # Map observed name IDs (from control strings) to likely speaker names
                            # by first-appearance order. This is heuristic but works well for VN scripts.
                            observed_name_ids: list[int] = []
                            for _, raw in ts:
                                if len(raw) == 6 and raw[:4] == b"\x0f\x33\x01\x10" and raw[5] == 0x01:
                                    nid = raw[4]
                                    if nid not in observed_name_ids:
                                        observed_name_ids.append(nid)
                            name_id_to_name: dict[int, str] = {}
                            for nid, nm in zip(observed_name_ids, name_candidates):
                                name_id_to_name[nid] = nm

                            lines.append(f"@+0x{first_text_off:X} TEXT_STREAM_BEGIN")
                            for ti, (toff, raw) in enumerate(ts):
                                raw_s = decode_text_with_controls(raw, encoding=encoding)
                                # Number each string to make later opcode<->text binding possible.
                                tag = _tag_text_control(raw)
                                suffix = ""
                                if tag:
                                    suffix = f"  # {tag}"
                                    if tag.startswith("SET_NAME_ID=0x"):
                                        nid = raw[4] if len(raw) >= 5 else None
                                        if nid is not None and nid in name_id_to_name:
                                            suffix += f" name={name_id_to_name[nid]!r}"
                                lines.append(f"@+0x{toff:X} TEXT#{ti} \"{escape_script_string(raw_s)}\"{suffix}")
                            lines.append(f"@+0x{(ts[-1][0] + len(ts[-1][1])):X} TEXT_STREAM_END")

            if len(segs) > 200:
                lines.append(f"# ... ({len(segs) - 200} more segments)")
            lines.append("")

    if include_crc32:
        lines.append(f"# crc32 = 0x{scn.computed_crc32():08X}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def dump_dialogue(
    scn: SCNFile,
    *,
    data: bytes,
    encoding: str = "cp932",
    with_offsets: bool = False,
    keep_controls: bool = False,
    with_names: bool = False,
    vn_format: bool = False,
    normalize_for_translation: bool = False,
) -> str:
    # A minimal, translation-friendly extractor.
    # It looks for the same "text_stream_starts_at" heuristic and returns only dialogue-like lines.
    if not (scn.tail_parsed and scn.parsed_end is not None):
        return ""
    out: list[str] = []
    base = scn.parsed_end
    segs = split_remainder_by_tail(scn)
    name_candidates = _build_name_id_map_from_blocks(scn, encoding=encoding) if with_names else []
    obj_table = _build_object_table_from_blocks(scn, encoding=encoding) if with_names else []

    def _escape_textfile_controls(s: str) -> str:
        out: list[str] = []
        for ch in s:
            o = ord(ch)
            if o < 0x20:
                out.append(f"\\{o:02X}")
            else:
                out.append(ch)
        return "".join(out)

    def _compress_hex_escapes(s: str) -> str:
        # Convert runs of \HH\HH... into a single <HHHH...> blob for translators.
        out: list[str] = []
        i = 0
        n = len(s)
        while i < n:
            if i + 3 <= n and s[i] == "\\" and all(c in "0123456789abcdefABCDEF" for c in s[i + 1 : i + 3]):
                hexes: list[str] = []
                while i + 3 <= n and s[i] == "\\" and all(c in "0123456789abcdefABCDEF" for c in s[i + 1 : i + 3]):
                    hexes.append(s[i + 1 : i + 3].upper())
                    i += 3
                out.append("<" + "".join(hexes) + ">")
                continue
            out.append(s[i])
            i += 1
        return "".join(out)

    def _normalize_text(s: str) -> str:
        if not normalize_for_translation:
            return s

        # 1) Common narration wrapper: \01\10\06 <text> \04\7F
        if s.startswith("\\01\\10\\06") and s.endswith("\\04\\7F") and len(s) > len("\\01\\10\\06") + len("\\04\\7F"):
            s = s[len("\\01\\10\\06") : -len("\\04\\7F")]

        # 2) Leading fullwidth space (SJIS 0x8140) often used for narration indentation.
        if s.startswith("　"):
            s = s[1:]

        # 3) Dialogue wrapper inside quotes: 「 \7A \01 \10 \02 ... 」 \25
        if s.startswith("「\\7A\\01\\10\\02"):
            s = "「" + s[len("「\\7A\\01\\10\\02") :]
        if s.endswith("\\25"):
            s = s[: -len("\\25")]

        # 4) Escaped ASCII: \80\21 looks like '!' and \80\3F looks like '?'
        # Hypothesis: engine stores certain halfwidth punctuation as 0x80-prefixed bytes.
        # For translation, expose them as plain ASCII; writeback can re-escape.
        out: list[str] = []
        i = 0
        while i < len(s):
            if i + 6 <= len(s) and s[i : i + 4] == "\\80\\":
                hh = s[i + 4 : i + 6]
                try:
                    b = int(hh, 16)
                except Exception:
                    b = -1
                if 0x20 <= b <= 0x7E:
                    out.append(chr(b))
                    i += 6
                    continue
            out.append(s[i])
            i += 1
        s = "".join(out)
        return s

    def emit_entry(*, addr: int, raw_len: int, kind: str, speaker: str, original: str) -> None:
        original = _normalize_text(original)
        original = _escape_textfile_controls(original)
        original = _compress_hex_escapes(original)
        if vn_format:
            sep = "*" if kind == "block" else "#"
            out.append(f"#{addr:X}{sep}{raw_len:X}")
            # Emit speaker if present for this entry.
            if speaker:
                out.append(f"#{speaker}")
            out.append(f"◇{original}")
            out.append(f"◆{original}")
            out.append("")
            return
        prefix = ""
        if speaker:
            prefix = f"[{speaker}] "
        if with_offsets:
            out.append(f"@0x{addr:X} {prefix}{original}")
        else:
            out.append(f"{prefix}{original}")

    if vn_format:
        for blk in scn.blocks:
            if OPCODE_NAMES.get(blk.type, "") != "VNString2":
                continue
            if not blk.params or not isinstance(blk.params[0], ParamString):
                continue
            p = blk.params[0]
            if p.offset is None:
                continue
            txt = p.text(encoding=encoding, errors="replace")
            if not _contains_jp(txt):
                continue
            emit_entry(addr=int(p.offset) + 1, raw_len=len(p.raw), kind="block", speaker="", original=txt)
    for seg in segs:
        seg_bytes = data[base + seg.rel_start : base + seg.rel_end]
        bc = decode_remainder_bytecode(seg_bytes, max_items=2000)
        if not bc:
            continue
        stop_at = bc[-1].rel_off + bc[-1].size
        text_candidates = scan_strings_loose(seg_bytes, encoding=encoding, min_chars=4)
        if not text_candidates:
            continue
        first_text_off = min(off for off, _ in text_candidates)
        if not (first_text_off >= stop_at and first_text_off - stop_at <= 0x40):
            continue
        ts = parse_text_stream(seg_bytes, first_text_off)
        # Name-id applies to exactly one subsequent emitted text entry (then is cleared).
        pending_speaker: str = ""

        for toff, raw in ts:
            # Update speaker context when encountering name-id control.
            if with_names and len(raw) == 6 and raw[:4] == b"\x0f\x33\x01\x10" and raw[5] == 0x01:
                nid = raw[4]
                mapped = ""
                if nid < len(obj_table) and obj_table[nid][0] == "str":
                    cand = str(obj_table[nid][1])
                    if _is_name_like(cand):
                        mapped = cand
                pending_speaker = mapped or f"ID_0x{nid:02X}"
                continue
            if keep_controls:
                s = decode_text_with_controls(raw, encoding=encoding)
            else:
                s = raw.decode(encoding, errors="replace").replace("\r", "\\r").replace("\n", "\\n")
                s = s.replace("\x7f", "")  # common line marker
            if vn_format:
                if not _contains_jp(s):
                    continue
            else:
                if not looks_like_dialogue(s):
                    continue
            abs_off = base + seg.rel_start + toff
            speaker_for_this = pending_speaker if with_names else ""
            if speaker_for_this:
                pending_speaker = ""
            emit_entry(addr=abs_off, raw_len=len(raw), kind="text", speaker=speaker_for_this, original=s)
    return "\n".join(out).rstrip() + ("\n" if out else "")


@dataclass(slots=True)
class ExtractEntry:
    addr: int
    kind: Literal["block", "text"]
    raw_len: int
    speaker: str
    original: str
    translated: str


_ADDR_LINE_RE = re.compile(r"^#([0-9A-Fa-f]+)([*#])([0-9A-Fa-f]+)$")


def parse_extract_txt(text: str) -> list[ExtractEntry]:
    # VN translation format:
    #   #ADDR*LEN   (block) or #ADDR#LEN (text stream)
    #   #SPEAKER    (optional)
    #   ◇original
    #   ◆translated
    #   (blank line)
    lines = text.splitlines()
    i = 0
    out: list[ExtractEntry] = []
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        m = _ADDR_LINE_RE.match(line)
        if not m:
            raise ValueError(f"bad entry header line: {lines[i]!r}")
        addr = int(m.group(1), 16)
        sep = m.group(2)
        raw_len = int(m.group(3), 16)
        kind: Literal["block", "text"] = "block" if sep == "*" else "text"
        i += 1

        speaker = ""
        if i < len(lines) and lines[i].startswith("#") and not _ADDR_LINE_RE.match(lines[i].strip()):
            speaker = lines[i][1:].strip()
            i += 1

        if i >= len(lines) or not lines[i].startswith("◇"):
            raise ValueError(f"missing ◇ line for entry at 0x{addr:X}")
        original = lines[i][1:]
        i += 1

        if i >= len(lines) or not lines[i].startswith("◆"):
            raise ValueError(f"missing ◆ line for entry at 0x{addr:X}")
        translated = lines[i][1:]
        i += 1

        # consume optional blank separator
        if i < len(lines) and lines[i].strip() == "":
            i += 1

        out.append(
            ExtractEntry(
                addr=addr,
                kind=kind,
                raw_len=raw_len,
                speaker=speaker,
                original=original,
                translated=translated,
            )
        )
    return out


def decode_script_escapes_to_bytes(
    s: str,
    *,
    encoding: str = "cp932",
    ascii80: bool = False,
) -> bytes:
    # Convert a mixed string containing "\HH" escapes + Unicode into bytes.
    out = bytearray()
    i = 0
    while i < len(s):
        if s[i] == "<":
            j = s.find(">", i + 1)
            if j != -1:
                hex_blob = s[i + 1 : j].strip()
                if hex_blob and all(ch in "0123456789abcdefABCDEF" for ch in hex_blob) and len(hex_blob) % 2 == 0:
                    for k in range(0, len(hex_blob), 2):
                        out.append(int(hex_blob[k : k + 2], 16))
                    i = j + 1
                    continue
        if s[i] == "\\" and i + 2 < len(s):
            hh = s[i + 1 : i + 3]
            try:
                b = int(hh, 16)
            except Exception:
                b = -1
            if 0 <= b <= 0xFF:
                out.append(b)
                i += 3
                continue
        ch = s[i]
        o = ord(ch)
        # Engine convention (observed): halfwidth ASCII is stored as 0x80-prefixed bytes.
        # Keep '<' and '>' as literal characters (so the text format remains usable).
        if ascii80 and 0x20 <= o <= 0x7E and ch not in "<>":
            out.append(0x80)
            out.append(o)
        else:
            out += ch.encode(encoding, errors="replace")
        i += 1
    return bytes(out)


def encode_ascii_as_80_prefixed(s: str) -> str:
    # Convert halfwidth ASCII (0x20..0x7E) to "\80\HH" escapes.
    out: list[str] = []
    for ch in s:
        o = ord(ch)
        if 0x20 <= o <= 0x7E:
            out.append(f"\\80\\{o:02X}")
        else:
            out.append(ch)
    return "".join(out)


def apply_translation_to_scn(
    src_bytes: bytes,
    txt: str,
    *,
    encoding: str = "cp932",
) -> bytes:
    entries = parse_extract_txt(txt)

    # Splice-based patching:
    # - Replace the original bytes at [addr, addr+raw_len) with the new bytes.
    # - This allows the file size to change (insert/delete).
    # - Addresses in the TXT are treated as original-file addresses; we apply patches in
    #   increasing order and maintain a running delta to map them into the current buffer.
    buf = bytearray(src_bytes)
    entries_sorted = sorted(entries, key=lambda e: (e.addr, 0 if e.kind == "block" else 1))
    delta = 0
    for e in entries_sorted:
        new_text = e.translated if e.translated else e.original
        if "\uFFFD" in new_text:
            continue
        new_raw = decode_script_escapes_to_bytes(new_text, encoding=encoding, ascii80=(e.kind == "text"))
        start = e.addr + delta
        end = start + e.raw_len
        if start < 0 or start > len(buf) or end < 0:
            continue
        if end > len(buf):
            end = len(buf)
        buf[start:end] = new_raw
        delta += len(new_raw) - (end - start)
    return bytes(buf)


def scan_c_strings(data: bytes, *, encoding: str = "cp932", min_len: int = 2) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    i = 0
    n = len(data)
    while i < n:
        if data[i] == 0:
            i += 1
            continue
        j = i
        while j < n and data[j] != 0:
            j += 1
        if j < n:
            raw = data[i:j]
            if len(raw) >= min_len:
                try:
                    s = raw.decode(encoding, errors="strict")
                except Exception:
                    s = raw.decode(encoding, errors="replace")
                # 过滤掉明显不是文本的垃圾：太多控制字符
                if any(ord(ch) < 0x20 and ch not in "\t" for ch in s):
                    pass
                else:
                    out.append((i, s))
        i = j + 1
    return out


def scan_strings_loose(
    data: bytes,
    *,
    encoding: str = "cp932",
    min_chars: int = 2,
    max_replace_ratio: float = 0.25,
) -> list[tuple[int, str]]:
    # 很多脚本把控制字节夹在文本附近；这里用更宽松的启发式：
    # 1) 以 0x00 分割候选片段
    # 2) 去掉片段里的明显控制字节（<0x20），再按 cp932 解码
    # 3) 过滤掉替换字符过多/太短的结果
    out: list[tuple[int, str]] = []
    n = len(data)
    i = 0
    while i < n:
        if data[i] == 0:
            i += 1
            continue
        start = i
        j = i
        while j < n and data[j] != 0:
            j += 1
        chunk = data[start:j]
        # 过滤控制字节，让“夹杂控制码的文本”也能还原出来
        cleaned = bytes(b for b in chunk if b >= 0x20 or b in (0x09,))
        if len(cleaned) >= 1:
            decoded = cleaned.decode(encoding, errors="replace")
            decoded = decoded.replace("\r", "\\r").replace("\n", "\\n")
            if len(decoded) >= min_chars:
                repl = decoded.count("\uFFFD")
                if repl / max(1, len(decoded)) <= max_replace_ratio:
                    out.append((start, decoded))
        i = j + 1
    return out


@dataclass(slots=True)
class RemainderSegment:
    index: int
    rel_start: int
    rel_end: int

    @property
    def length(self) -> int:
        return max(0, self.rel_end - self.rel_start)


def split_remainder_by_tail(scn: SCNFile) -> list[RemainderSegment]:
    if not scn.tail_parsed or scn.parsed_end is None:
        return []
    base = scn.parsed_end
    end = base + (scn.tail_value & 0xFFFFFFFF)
    rel = []
    for v in scn.tail_table:
        vv = int(v) & 0xFFFFFFFF
        if vv <= (scn.tail_value & 0xFFFFFFFF):
            rel.append(vv)
    rel = sorted(set(rel))
    # 确保包含 0 和末尾
    if 0 not in rel:
        rel.insert(0, 0)
    if (scn.tail_value & 0xFFFFFFFF) not in rel:
        rel.append(scn.tail_value & 0xFFFFFFFF)
    segs: list[RemainderSegment] = []
    for i in range(len(rel) - 1):
        segs.append(RemainderSegment(index=i, rel_start=rel[i], rel_end=rel[i + 1]))
    return segs


def _is_sjis_lead(b: int) -> bool:
    return (0x81 <= b <= 0x9F) or (0xE0 <= b <= 0xFC)


def _looks_like_text_run(data: bytes, i: int, *, window: int = 16) -> bool:
    # Very rough: if within next few bytes we see enough SJIS lead bytes, treat as "text-ish".
    n = len(data)
    j_end = min(n, i + window)
    leads = 0
    for j in range(i, j_end):
        if _is_sjis_lead(data[j]):
            leads += 1
    return leads >= 2


@dataclass(slots=True)
class BytecodeItem:
    rel_off: int
    size: int
    op: int
    args: tuple[int, ...]
    raw: bytes
    text_refs: tuple[tuple[int, str], ...] = ()


def _u16be_at(b: bytes, off: int) -> int:
    return (b[off] << 8) | b[off + 1]


def decode_remainder_bytecode(
    seg_bytes: bytes,
    *,
    max_items: int = 500,
    stop_at: Optional[int] = None,
) -> list[BytecodeItem]:
    # Bytecode tokenizer (confirmed by IDA: sub_425F40, dispatch 0..0x2F + extended ranges).
    #
    # Notes:
    # - Opcodes are the first byte. If > 0x2F, execution goes to a secondary dispatcher:
    #   - 0x50..0x5F / 0x60..0x6F / 0x70..0x7F: similar forms (count + u16 list)
    #   - >= 0x80: reads an extra byte and forms a 16-bit opcode (op<<8 | lo)
    #
    # Goal: stable structural parsing for reverse engineering (not full semantics yet).
    items: list[BytecodeItem] = []
    i = 0
    n = len(seg_bytes)

    def need(k: int) -> bool:
        return i + k <= n

    def read_u8() -> int:
        nonlocal i
        v = seg_bytes[i]
        i += 1
        return v

    def read_u16be() -> int:
        nonlocal i
        v = (seg_bytes[i] << 8) | seg_bytes[i + 1]
        i += 2
        return v

    def read_u32be() -> int:
        nonlocal i
        v = (
            (seg_bytes[i] << 24)
            | (seg_bytes[i + 1] << 16)
            | (seg_bytes[i + 2] << 8)
            | seg_bytes[i + 3]
        )
        i += 4
        return v

    def _looks_like_text_stream_at(off: int) -> bool:
        # Heuristic boundary detection:
        # - text stream is a sequence of null-terminated cp932 strings
        # - bytecode can contain bytes that look like SJIS leads (not safe to stop purely on that)
        #
        # We only treat it as "text starts here" if we can decode a plausible string that
        # terminates soon (within max_len) and isn't mostly replacement characters.
        if off >= n:
            return False
        b0 = seg_bytes[off]
        # Fast reject: unlikely text starts with NUL
        if b0 == 0:
            return False
        # Find next NUL within a small window; text strings are short-ish.
        max_len = 0x80
        j = off
        while j < n and j - off < max_len and seg_bytes[j] != 0:
            j += 1
        if j >= n or seg_bytes[j] != 0:
            return False
        raw = seg_bytes[off:j]
        # Filter obvious control bytes (keep 0x7F etc.)
        cleaned = bytes(b for b in raw if b >= 0x20 or b in (0x09,))
        if not cleaned:
            return False
        decoded = cleaned.decode("cp932", errors="replace")
        if len(decoded) < 2:
            return False
        repl = decoded.count("\uFFFD")
        if repl / max(1, len(decoded)) > 0.25:
            return False
        # If first byte is SJIS lead or common ASCII printable, treat as text.
        if _is_sjis_lead(b0) or (0x20 <= b0 <= 0x7E):
            return True
        return False

    # Formats derived from your pasted disasm of sub_425F40 (cases 0..25),
    # focusing on correct cursor advancement to avoid desync.
    def _decode_main_op(op8: int) -> tuple[int, ...] | None:
        nonlocal i
        # return tuple args, or None if need more bytes (stop)
        if op8 == 0x00:
            return ()
        if op8 in (0x01, 0x02):
            if not need(2 + 1 + 1):
                return None
            a = read_u16be()
            b = read_u8()
            count = read_u8()
            if not need(2 * count):
                return None
            arr = tuple(read_u16be() for _ in range(count))
            return (a, b, count, *arr)
        if op8 == 0x03:
            if not need(2 + 1):
                return None
            a = read_u16be()
            b = read_u8()
            return (a, b)
        if op8 == 0x04:
            return ()
        if op8 == 0x0A:
            if not need(2 + 4):
                return None
            a = read_u16be()
            b = read_u32be()
            return (a, b)
        if op8 in (0x0B, 0x0C, 0x0D):
            if not need(4):
                return None
            return (read_u16be(), read_u16be())
        if 0x0E <= op8 <= 0x19:
            if not need(2):
                return None
            return (read_u16be(),)
        if op8 in (0x1A, 0x1B):
            # case 26/27: u16, then sub_425C80 + sub_425D20
            if not need(2):
                return None
            return (read_u16be(),)
        if op8 in (0x1C, 0x1D, 0x1E):
            # case 28/29/30: u8 count, then count*u16
            if not need(1):
                return None
            count = read_u8()
            if count <= 0:
                return (count,)
            if not need(2 * count):
                return None
            arr = tuple(read_u16be() for _ in range(count))
            return (count, *arr)
        if op8 == 0x1F:
            # case 31: no operands (sub_431180)
            return ()
        if op8 in (0x20, 0x21):
            # case 32/33: u32be
            if not need(4):
                return None
            return (read_u32be(),)
        if op8 in (0x22, 0x23):
            # case 34/35: u8
            if not need(1):
                return None
            return (read_u8(),)
        if op8 in (0x24, 0x25):
            # case 36/37: u16
            if not need(2):
                return None
            return (read_u16be(),)
        if op8 == 0x26:
            # case 38: u32be + u16
            if not need(4 + 2):
                return None
            a = read_u32be()
            b = read_u16be()
            return (a, b)
        if op8 == 0x27:
            # case 39: u8 + u16
            if not need(1 + 2):
                return None
            a = read_u8()
            b = read_u16be()
            return (a, b)
        if op8 == 0x28:
            # case 40: u32be + u16
            if not need(4 + 2):
                return None
            a = read_u32be()
            b = read_u16be()
            return (a, b)
        if op8 == 0x29:
            # case 41: u8 + u16
            if not need(1 + 2):
                return None
            a = read_u8()
            b = read_u16be()
            return (a, b)
        if 0x2A <= op8 <= 0x2F:
            # case 42..47: no operands (engine calls other subs and returns)
            return ()
        # Unknown opcode in 0..0x2F: don't guess operands (guessing desyncs quickly).
        return ()

    hard_end = n if stop_at is None else max(0, min(n, int(stop_at)))

    while i < hard_end and len(items) < max_items:
        # Prefer treating remaining bytes as text if a plausible string starts here.
        # If caller already provided an exact stop boundary (e.g., detected text_stream_at),
        # don't early-break: let the caller decide what happens between bytecode and text.
        if stop_at is None and _looks_like_text_stream_at(i):
            break
        start = i
        op = read_u8()

        args: tuple[int, ...] = ()
        # Main dispatcher 0..0x2F:
        if op <= 0x2F:
            decoded = _decode_main_op(op)
            if decoded is None:
                break
            args = decoded
        else:
            # Extended dispatcher (op > 0x2F):
            if 0x30 <= op < 0x50:
                # Best guess (from partial disasm notes): many of these look like single-u16 operands.
                if not need(2):
                    break
                a = read_u16be()
                args = (a,)
            elif 0x50 <= op < 0x80:
                # 0x50..0x7F: reads u8 count, then count*u16be
                if not need(1):
                    break
                count = read_u8()
                if not need(2 * count):
                    break
                arr = tuple(read_u16be() for _ in range(count))
                args = (count, *arr)
            elif op >= 0x80:
                # >= 0x80: reads u8 and forms u16 opcode
                if not need(1):
                    break
                lo = read_u8()
                op16 = ((op & 0xFF) << 8) | lo
                op = op16
                args = ()
            else:
                # 0x30..0x4F: unknown extended group; just keep opcode as-is
                args = ()

        raw = seg_bytes[start:i]
        items.append(BytecodeItem(rel_off=start, size=i - start, op=op, args=args, raw=raw))

    return items


@dataclass(slots=True)
class MixedItem:
    rel_off: int
    size: int
    kind: Literal["op", "text", "byte"]
    text: str = ""
    op: int = 0
    args: tuple[int, ...] = ()
    raw: bytes = b""


def decode_remainder_mixed(seg_bytes: bytes, *, encoding: str = "cp932", max_items: int = 10000) -> list[MixedItem]:
    # Experimental per user hypothesis:
    # - if byte >= 0x80: treat as text (2-byte SJIS, with 0xA1..0xDF as 1-byte halfwidth kana)
    # - else: treat as opcode and parse operands
    out: list[MixedItem] = []
    i = 0
    n = len(seg_bytes)

    def need(k: int) -> bool:
        return i + k <= n

    def read_u8() -> int:
        nonlocal i
        v = seg_bytes[i]
        i += 1
        return v

    def read_u16be() -> int:
        nonlocal i
        v = (seg_bytes[i] << 8) | seg_bytes[i + 1]
        i += 2
        return v

    def read_u32be() -> int:
        nonlocal i
        v = (
            (seg_bytes[i] << 24)
            | (seg_bytes[i + 1] << 16)
            | (seg_bytes[i + 2] << 8)
            | seg_bytes[i + 3]
        )
        i += 4
        return v

    def parse_op(op8: int) -> tuple[int, ...] | None:
        if op8 == 0x00:
            return ()
        if op8 in (0x01, 0x02):
            if not need(2 + 1 + 1):
                return None
            a = read_u16be()
            b = read_u8()
            count = read_u8()
            if not need(2 * count):
                return None
            arr = tuple(read_u16be() for _ in range(count))
            return (a, b, count, *arr)
        if op8 == 0x03:
            if not need(2 + 1):
                return None
            return (read_u16be(), read_u8())
        if op8 == 0x04:
            return ()
        if op8 == 0x0A:
            if not need(2 + 4):
                return None
            return (read_u16be(), read_u32be())
        if op8 in (0x0B, 0x0C, 0x0D):
            if not need(4):
                return None
            return (read_u16be(), read_u16be())
        if 0x0E <= op8 <= 0x19:
            if not need(2):
                return None
            return (read_u16be(),)
        if op8 in (0x1A, 0x1B):
            if not need(2):
                return None
            return (read_u16be(),)
        if op8 in (0x1C, 0x1D, 0x1E):
            if not need(1):
                return None
            count = read_u8()
            if count <= 0:
                return (count,)
            if not need(2 * count):
                return None
            arr = tuple(read_u16be() for _ in range(count))
            return (count, *arr)
        if op8 == 0x1F:
            return ()
        if op8 in (0x20, 0x21):
            if not need(4):
                return None
            return (read_u32be(),)
        if op8 in (0x22, 0x23):
            if not need(1):
                return None
            return (read_u8(),)
        if op8 in (0x24, 0x25):
            if not need(2):
                return None
            return (read_u16be(),)
        if op8 == 0x26:
            if not need(4 + 2):
                return None
            return (read_u32be(), read_u16be())
        if op8 == 0x27:
            if not need(1 + 2):
                return None
            return (read_u8(), read_u16be())
        if op8 == 0x28:
            if not need(4 + 2):
                return None
            return (read_u32be(), read_u16be())
        if op8 == 0x29:
            if not need(1 + 2):
                return None
            return (read_u8(), read_u16be())
        if 0x2A <= op8 <= 0x2F:
            return ()
        return ()

    def flush_text(start: int, buf: bytearray) -> None:
        if not buf:
            return
        txt = decode_text_with_controls(bytes(buf), encoding=encoding)
        out.append(MixedItem(rel_off=start, size=len(buf), kind="text", text=txt, raw=bytes(buf)))
        buf.clear()

    text_buf = bytearray()
    text_start = 0

    while i < n and len(out) < max_items:
        b = seg_bytes[i]
        if b >= 0x80:
            if not text_buf:
                text_start = i
            if 0xA1 <= b <= 0xDF:
                text_buf.append(read_u8())
            else:
                if not need(2):
                    break
                text_buf += seg_bytes[i : i + 2]
                i += 2
            continue

        flush_text(text_start, text_buf)
        start = i
        op = read_u8()
        args = parse_op(op)
        if args is None:
            out.append(MixedItem(rel_off=start, size=1, kind="byte", raw=seg_bytes[start : start + 1]))
            break
        out.append(MixedItem(rel_off=start, size=i - start, kind="op", op=op, args=args, raw=seg_bytes[start:i]))

    flush_text(text_start, text_buf)
    return out


def parse_text_stream(seg_bytes: bytes, start_off: int) -> list[tuple[int, bytes]]:
    # Parse consecutive null-terminated byte strings starting at start_off.
    out: list[tuple[int, bytes]] = []
    i = start_off
    n = len(seg_bytes)
    while i < n:
        j = i
        while j < n and seg_bytes[j] != 0:
            j += 1
        if j == i:
            i += 1
            continue
        raw = seg_bytes[i:j]
        out.append((i, raw))
        if j >= n:
            break
        i = j + 1
    return out


def decode_text_with_controls(raw: bytes, *, encoding: str = "cp932") -> str:
    # Decode cp932 but keep/visualize control bytes.
    #
    # Output uses "\HH" (two-digit hex) for ALL single-byte (<0x80) bytes, so halfwidth
    # characters like 't', 'z', '%' are not interpreted as text but preserved as byte
    # markers. Non-ASCII characters (e.g. fullwidth spaces) are kept as-is.
    out: list[str] = []
    i = 0
    n = len(raw)
    while i < n:
        b = raw[i]
        if b < 0x80:
            out.append(f"\\{b:02X}")
            i += 1
            continue
        if 0xA1 <= b <= 0xDF:
            out.append(bytes([b]).decode(encoding, errors="replace"))
            i += 1
            continue
        if _is_sjis_lead(b) and i + 1 < n:
            chunk = raw[i : i + 2]
            try:
                out.append(chunk.decode(encoding, errors="strict"))
            except Exception:
                out.append(chunk.decode(encoding, errors="replace"))
            i += 2
            continue
        out.append(f"\\{b:02X}")
        i += 1
    return "".join(out)


def _tag_text_control(raw: bytes) -> str:
    # Heuristic tags for common control-only text entries inside the text stream.
    # These are NOT confirmed semantics yet; they exist to help reverse-engineering.
    if raw == b"\x74":
        return "CTRL_T"
    if raw == b"\x7f":
        return "CTRL_7F"
    if raw == b"\x1f\x04\x7f":
        return "CTRL_1F_04_7F"
    if raw == b"\x1f\x02":
        return "CTRL_1F_02"
    if raw == b"\x0f\x32":
        return "CTRL_0F_32"
    if raw == b"\x0f\x34":
        return "CTRL_0F_34"
    # Pattern seen right before dialogue lines in multiple scripts:
    #   0F 33 01 10 XX 01
    if len(raw) == 6 and raw[:4] == b"\x0f\x33\x01\x10" and raw[5] == 0x01:
        return f"SET_NAME_ID=0x{raw[4]:02X}"
    return ""


def _is_name_like(s: str) -> bool:
    if not s:
        return False
    if "_" in s:
        return False
    # Speaker names are typically very short (e.g. '貴志', '？？？').
    # Keep this strict to avoid picking titles like '森の中の洋館'.
    if len(s) > 4:
        return False
    # Avoid typical resource tokens
    if all(("0" <= ch <= "9") or ("a" <= ch.lower() <= "z") for ch in s):
        return False
    return True


def _build_name_id_map_from_blocks(
    scn: "SCNFile",
    *,
    encoding: str = "cp932",
) -> list[str]:
    # Best-effort: collect candidate speaker names from the header blocks.
    # These are usually short (e.g. '貴志', '？？？') and not resource-like.
    out: list[str] = []
    for blk in scn.blocks:
        if OPCODE_NAMES.get(blk.type) != "VNString2":
            continue
        if not blk.params:
            continue
        p = blk.params[0]
        if not isinstance(p, ParamString):
            continue
        s = p.text(encoding=encoding, errors="replace")
        if _is_name_like(s):
            out.append(s)
    return out


def _build_object_table_from_blocks(
    scn: "SCNFile",
    *,
    encoding: str = "cp932",
) -> list[tuple[str, Any]]:
    # Build an indexable table of "objects" referenced by scripts.
    # Observed: name-id bytes (e.g. 0x12) match the index in this table.
    #
    # We include VNString2 and VNInteger, in appearance order.
    out: list[tuple[str, Any]] = []
    for blk in scn.blocks:
        t = OPCODE_NAMES.get(blk.type, "")
        if t == "VNString2":
            if blk.params and isinstance(blk.params[0], ParamString):
                out.append(("str", blk.params[0].text(encoding=encoding, errors="replace")))
        elif t == "VNInteger":
            if blk.params and isinstance(blk.params[0], ParamInt):
                out.append(("int", int(blk.params[0].value) & 0xFFFFFFFF))
    return out


JP_RE = re.compile(
    r"["
    r"\u4e00-\u9fff"
    r"\u3040-\u30ff"
    r"\u31f0-\u31ff"
    r"\uff61-\uff9f"
    r"\uff01-\uff60"
    r"\uffe0-\uffe6"
    r"]"
)


def _contains_jp(s: str) -> bool:
    return bool(JP_RE.search(s))


def looks_like_dialogue(s: str) -> bool:
    if not s:
        return False
    if "「" in s or "」" in s:
        return True
    for ch in s:
        o = ord(ch)
        if (0x3040 <= o <= 0x30FF) or (0x4E00 <= o <= 0x9FFF) or (0xFF00 <= o <= 0xFFEF):
            return True
    return False


def escape_script_string(s: str) -> str:
    # Keep Unicode (including fullwidth spaces) and escape only what breaks the script line.
    # Control bytes should already be rendered as "\HH" by decode_text_with_controls.
    # Do NOT double backslashes: the output format uses a single "\" prefix.
    # Avoid embedding literal quotes.
    return s.replace('"', "\\22")


def opcode_histogram(items: list[BytecodeItem]) -> list[tuple[int, int]]:
    counts: dict[int, int] = {}
    for it in items:
        counts[it.op] = counts.get(it.op, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


def annotate_text_refs(items: list[BytecodeItem], seg_bytes: bytes, *, encoding: str = "cp932") -> list[BytecodeItem]:
    # Build a map of known text starts (relative offsets) -> decoded text (best-effort)
    starts = {}
    for off, s in scan_strings_loose(seg_bytes, encoding=encoding, min_chars=4):
        starts[off] = s

    out: list[BytecodeItem] = []
    for it in items:
        refs: list[tuple[int, str]] = []
        # 1) direct args match
        for a in it.args:
            if isinstance(a, int) and a in starts:
                refs.append((a, starts[a]))
        # 2) scan raw for embedded u16be values that match string starts
        #    (many opcodes pass offsets as packed u16 without us fully decoding the operand list yet)
        raw = it.raw
        for j in range(0, max(0, len(raw) - 1)):
            v = (raw[j] << 8) | raw[j + 1]
            if v in starts:
                refs.append((v, starts[v]))
        # keep unique, stable order
        if refs:
            seen = set()
            uniq: list[tuple[int, str]] = []
            for off, s in refs:
                if off not in seen:
                    seen.add(off)
                    uniq.append((off, s))
            refs = uniq
        out.append(
            BytecodeItem(
                rel_off=it.rel_off,
                size=it.size,
                op=it.op,
                args=it.args,
                raw=it.raw,
                text_refs=tuple(refs),
            )
        )
    return out


def main(argv: Optional[list[str]] = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        raise SystemExit(
            "usage:\n"
            "  scn.py d <in_scn_dir> <out_txt_dir> [encoding]\n"
            "  scn.py e <in_scn_dir> <in_txt_dir> <out_scn_dir> [encoding]\n"
        )
    cmd = args[0].lower()
    if cmd == "d":
        if len(args) not in (3, 4):
            raise SystemExit("usage: scn.py d <in_scn_dir> <out_txt_dir> [encoding]")
        in_dir = Path(args[1])
        out_dir = Path(args[2])
        enc = args[3] if len(args) == 4 else "cp932"
        for scn_path in sorted(in_dir.rglob("*.scn")):
            rel = scn_path.relative_to(in_dir)
            out_path = out_dir / rel.with_suffix(".txt")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            data = scn_path.read_bytes()
            scn = parse_scn(data)
            s = dump_dialogue(
                scn,
                data=data,
                encoding=enc,
                with_offsets=False,
                keep_controls=True,
                with_names=True,
                vn_format=True,
                normalize_for_translation=False,
            )
            if s.strip():
                out_path.write_text(s, encoding="utf-8")
        return 0
    if cmd == "e":
        if len(args) not in (4, 5):
            raise SystemExit("usage: scn.py e <in_scn_dir> <in_txt_dir> <out_scn_dir> [encoding]")
        in_scn_dir = Path(args[1])
        in_txt_dir = Path(args[2])
        out_scn_dir = Path(args[3])
        enc = args[4] if len(args) == 5 else "cp932"
        for scn_path in sorted(in_scn_dir.rglob("*.scn")):
            rel = scn_path.relative_to(in_scn_dir)
            txt_path = in_txt_dir / rel.with_suffix(".txt")
            if not txt_path.exists():
                continue
            out_path = out_scn_dir / rel
            out_path.parent.mkdir(parents=True, exist_ok=True)
            src = scn_path.read_bytes()
            txt = txt_path.read_text(encoding="utf-8")
            rebuilt = apply_translation_to_scn(src, txt, encoding=enc)
            out_path.write_bytes(rebuilt)
        return 0
    raise SystemExit(f"unknown cmd: {cmd!r}")


if __name__ == "__main__":
    raise SystemExit(main())
