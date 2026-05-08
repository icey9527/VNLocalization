from __future__ import annotations

import re
import struct
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import char


NOTES = """
SCRIPT.DAT current notes
========================

Source of truth so far:
- sub_108440: loads whole cdrom0:\\DATA\\SCRIPT.DAT into memory.
- sub_113730: resolves scene name by scanning a static 1198-entry table in ELF.
- sub_113850: resolves a scene/block using that static table plus SCRIPT.DAT data.
- sub_113BB0: selects an entry inside the current block.
- sub_108A50: interprets script units from a u16 pool.

What is confirmed
-----------------
1. SCRIPT.DAT is loaded as a whole file, not streamed.

2. The top-level directory is not stored in SCRIPT.DAT. It is a static 1198-entry
   table embedded in the ELF at symbol a0000:
   struct DirEntry {
       char name[8];
       u32  offset;
       u32  size;
   };

   sub_113730 scans exactly 1198 entries and compares scene names against entry.name.
   The third field is confirmed block size because:
   next.offset - cur.offset == cur.size
   and last.offset + last.size == file_size.

3. sub_113850 uses:
   block_ptr  = file_base + dir[idx].offset
   count1     = u16(block_ptr + 0)
   count2     = u16(block_ptr + 2)
   table1_ptr = block_ptr + 4
   table2_ptr = block_ptr + 4 + 2 * count1

4. sub_113BB0 and sub_108A50 together show:
   - table1 is an entry-selection table.
   - table2/script_pool is a u16 pool used for script-unit lookup and execution.

5. A script unit starts with:
   struct ScriptUnit {
       u16 opcode;
       u16 arg_words;
       u16 args[arg_words];
   };

   The next unit is reached with:
       next = cur + 2 * (arg_words + 2)

   This means PS2 script units are variable-length, but not arbitrary:
   the second u16 is the size field used to advance to the next unit.

6. Encoded arguments are often read as pairs:
   struct EncArg {
       u16 kind;
       u16 value;
   };

   These helpers are confirmed:
   - sub_113A50(ctx, arg_base, i): returns args[i].kind
   - sub_113A90(ctx, arg_base, i): returns args[i].value
   sub_113AD0 semantics:
   - kind == 0: immediate value
   - kind == 1: read from dword_454E80-derived variable area
   - kind == 2: read from dword_454A70-derived variable area

7. Several opcodes in sub_108A50 implement arithmetic/assignment on variable slots.
   Confirmed opcode -> behavior:
   - 0x28 ('('): assign
   - 0x29 (')'): add
   - 0x2A ('*'): sub
   - 0x2B ('+'): mul
   - 0x2C (','): div
   - 0x2D ('-'): mod
   - 0x2E ('.'): and
   - 0x2F ('/'): special modulo from global product
   - 0x30 ('0'): branch if equal
   - 0x31 ('1'): set bit
   - 0x32 ('2'): clear bit
   - 0x33 ('3'): xor/toggle bit
   - 0x34 ('4'): abs-write
   - 0x3C ('<'): unconditional jump
   - 0x3D ('='): jump if arg0 == arg1
   - 0x3E ('>'): jump if arg0 != arg1
   - 0x3F ('?'): jump if arg0 > arg1
   - 0x40 ('@'): jump if arg0 < arg1
   - 0x41 ('A'): jump if arg0 >= arg1
   - 0x42 ('B'): jump if arg0 <= arg1
   - 0x43 ('C'): jump if bit set
   - 0x44 ('D'): jump if bit clear
   - 0x45 ('E'): modulo jump selector
   - 0x46 ('F'): no-op / plain advance
   - 0x47 ('G'): no-op / plain advance
   - 0x48 ('H'): conditional jump driven by sub_117F10(ctx)
   - 0x49 ('I'): jump by (sub_1008E0() % argc)-selected target
   - 0x4A ('J'): timed wait / timeout gate
   - 0x50 ('P'): large modal system/UI state machine
   - 0x5A ('Z'): call_sub_114A80
   - 0x5B ('['): call_sub_114DB0
   - 0x5C ('\\'): ui_mode_exit_or_clear
   - 0x5D (']'): set_ui_flags_1_2
   - 0x5E ('^'): ui_wait_start
   - 0x5F ('_'): ui_wait_poll
   - 0x60 ('`'): set_454B6C
   - 0x61 ('a'): set_454B70
   - 0x64 ('d'): timed_modal_update_a
   - 0x65 ('e'): timed_modal_update_b
   - 0x66 ('f'): call_sub_136D70_mode5
   - 0x67 ('g'): call_sub_136D70_mode5_alt
   - 0x68 ('h'): call_sub_136D70_mode5_2
   - 0x69 ('i'): call_sub_136D70_mode5_2_alt

8. Low control-flow family:
   - 0x00 / 0x01 / 0xFF: set current seen-flag bit from dword_454A88
   - 0x03: push/save current script position
   - 0x04: pop/restore a saved script position
   - 0x05: switch block by id, then enter an entry inside that block
   - 0x06: enter an entry in the current block
   - 0x07: set seen-flag bit
   - 0x08: test seen-flag bit
   - 0x09: reset a small set of globals/ctx fields

9. PC opcode names cannot be trusted for PS2 semantics.
"""


ENTRY_COUNT = 1198
ENTRY_SIZE = 16
ENTRY_TABLE_EA = 0x288CD0
TEXT_ENCODING = "cp932"
TEXT_CONVERTER = None
DEFAULT_ELF = Path("SLPS_254.12")
DEFAULT_TBL = Path("font") / "font.tbl"

FULL_TEXT_SEQS = (
    ("family", tuple(range(0x44D, 0x453))),
    ("name", tuple(range(0x457, 0x45D))),
    ("nick", tuple(range(0x461, 0x467))),
    ("hira", tuple(range(0x46B, 0x471))),
    ("kata", tuple(range(0x475, 0x47B))),
)

FULL_TEXT_SEQ_MAP = {label: set(seq) for label, seq in FULL_TEXT_SEQS}
PARTIAL_TEXT_MAP = {
    word: f"<{label}:{index}>"
    for label, seq in FULL_TEXT_SEQS
    for index, word in enumerate(seq, start=1)
}
FULL_TEXT_SEQ_LOOKUP = {label: seq for label, seq in FULL_TEXT_SEQS}
PARTIAL_TEXT_LOOKUP = {
    f"{label}:{index}": word
    for label, seq in FULL_TEXT_SEQS
    for index, word in enumerate(seq, start=1)
}
TEXT_TOKEN_RE = re.compile(r"<([a-z0-9]+(?::[0-9]+)?)>")

OP_NAMES = {
    0x0000: "seen_set_0",
    0x0001: "seen_set_1",
    0x0003: "push_pos",
    0x0004: "pop_pos",
    0x0005: "switch_block",
    0x0006: "enter_entry",
    0x0007: "set_seen",
    0x0008: "test_seen",
    0x0009: "reset_ctx",
    0x0028: "assign",
    0x0029: "add",
    0x002A: "sub",
    0x002B: "mul",
    0x002C: "div",
    0x002D: "mod",
    0x002E: "and",
    0x002F: "mod_global",
    0x0030: "branch_eq",
    0x0031: "bit_set",
    0x0032: "bit_clear",
    0x0033: "bit_xor",
    0x0034: "abs_write",
    0x003C: "jump",
    0x003D: "jump_eq",
    0x003E: "jump_ne",
    0x003F: "jump_gt",
    0x0040: "jump_lt",
    0x0041: "jump_ge",
    0x0042: "jump_le",
    0x0043: "jump_bit_set",
    0x0044: "jump_bit_clear",
    0x0045: "jump_mod",
    0x0046: "nop_46",
    0x0047: "nop_47",
    0x0048: "jump_cond_h",
    0x0049: "jump_rand_i",
    0x004A: "timed_wait",
    0x0050: "ui_modal",
    0x005A: "call_114A80",
    0x005B: "call_114DB0",
    0x005C: "ui_mode_exit_or_clear",
    0x005D: "set_ui_flags_1_2",
    0x005E: "ui_wait_start",
    0x005F: "ui_wait_poll",
    0x0060: "set_454B6C",
    0x0061: "set_454B70",
    0x0064: "timed_modal_update_a",
    0x0065: "timed_modal_update_b",
    0x0066: "call_136D70_mode5",
    0x0067: "call_136D70_mode5_alt",
    0x0068: "call_136D70_mode5_2",
    0x0069: "call_136D70_mode5_2_alt",
    0x00FF: "seen_set_ff",
}

NAME_TO_OPCODE = {name: op for op, name in OP_NAMES.items()}


def u16(data: bytes, off: int) -> int:
    return struct.unpack_from("<H", data, off)[0]


def u32(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


@dataclass(frozen=True)
class DirEntry:
    index: int
    name: str
    offset: int
    size: int


@dataclass(frozen=True)
class Block:
    entry_offsets: list[int]
    code_words: list[int]


@dataclass(frozen=True)
class Arg:
    kind: int
    value: int

    def render(self) -> str:
        if self.kind == 0:
            return str(self.value)
        if self.kind == 1:
            return f"f{self.value}"
        if self.kind == 2:
            return f"v{self.value}"
        return f"t{self.kind}({self.value})"


@dataclass(frozen=True)
class Instr:
    offset_words: int
    op: int
    argc: int
    args: list[Arg]
    raw: list[int]
    issue: str = ""

    def is_text(self) -> bool:
        return is_text_word(self.op)

    def name(self) -> str:
        if self.is_text():
            return "text"
        return OP_NAMES.get(self.op, f"op_{self.op:04X}")

    def render(self, text_refs: dict[int, int]) -> str:
        if self.is_text():
            body = f"text({text_refs[self.offset_words]})"
        else:
            parts = [arg.render() for arg in self.args]
            body = f"{self.name()}({','.join(parts)})" if parts else f"{self.name()}()"
        if self.issue:
            return f"{body} ; !!! ALIGNMENT_ERROR: {self.issue} !!!"
        return body


@dataclass(frozen=True)
class AsmCommand:
    block: int
    text: str


def export_stem(name: str, seen: dict[str, int], totals: dict[str, int]) -> str:
    count = seen.get(name, 0)
    seen[name] = count + 1
    if totals.get(name, 0) <= 1:
        return name
    return f"{name}_{count:02d}"


def source_map(in_dir: Path, entries: list[DirEntry]) -> list[tuple[Path, Path | None]]:
    totals = Counter(entry.name for entry in entries)
    used: dict[str, int] = {}
    sources: list[tuple[Path, Path | None]] = []
    for entry in entries:
        stem = export_stem(entry.name, used, totals)
        asm_path = in_dir / f"{stem}.asm"
        txt_path = in_dir / f"{stem}.txt"
        if not asm_path.exists():
            raise ValueError(f"missing asm source: {asm_path.name}")
        sources.append((asm_path, txt_path if txt_path.exists() else None))
    return sources


def encode_text_plain(text: str) -> list[int]:
    words: list[int] = []
    if TEXT_CONVERTER is not None:
        text = TEXT_CONVERTER(text)
    encoded = text.encode(TEXT_ENCODING, errors="ignore")
    if len(encoded) % 2:
        raise ValueError("text encoded to odd byte length")
    for i in range(0, len(encoded), 2):
        word = (encoded[i] << 8) | encoded[i + 1]
        words.append(word)
    return words


def encode_text_content(text: str) -> list[int]:
    words: list[int] = []
    pos = 0
    while pos < len(text):
        match = TEXT_TOKEN_RE.search(text, pos)
        if not match:
            words.extend(encode_text_plain(text[pos:]))
            break
        if match.start() > pos:
            words.extend(encode_text_plain(text[pos : match.start()]))
        token = match.group(1)
        if token in FULL_TEXT_SEQ_LOOKUP:
            for word in FULL_TEXT_SEQ_LOOKUP[token]:
                words.append(word)
                words.append(0)
        elif token in PARTIAL_TEXT_LOOKUP:
            words.append(PARTIAL_TEXT_LOOKUP[token])
            words.append(0)
        else:
            raise ValueError(f"unknown text token: <{token}>")
        pos = match.end()
    return words


def decode_text_word(word: int) -> str:
    if word in {0x0000, 0xFFFF}:
        return ""
    if word in PARTIAL_TEXT_MAP:
        return PARTIAL_TEXT_MAP[word]
    data = bytes((word >> 8, word & 0xFF))
    return data.decode(TEXT_ENCODING, errors="ignore")


def render_text_content(words: list[int]) -> str:
    parts: list[str] = []
    i = 0
    while i < len(words):
        matched = False
        for label, seq in FULL_TEXT_SEQS:
            j = i
            seen: list[int] = []
            seq_set = FULL_TEXT_SEQ_MAP[label]
            while j < len(words) and (words[j] in seq_set or words[j] == 0):
                if words[j] in seq_set:
                    seen.append(words[j])
                j += 1
            if tuple(seen) == seq:
                parts.append(f"<{label}>")
                i = j
                matched = True
                break
        if matched:
            continue
        parts.append(decode_text_word(words[i]))
        i += 1
    return "".join(parts)


def is_text_word(word: int) -> bool:
    return word >= 0x8000 or 0x44D <= word <= 0x47A


def split_block(chunk: bytes) -> Block:
    if len(chunk) < 4 or len(chunk) % 2:
        raise ValueError("invalid block size")
    entry_count = u16(chunk, 0)
    code_count = u16(chunk, 2)
    expected_size = 4 + entry_count * 2 + code_count * 2
    if expected_size != len(chunk):
        raise ValueError(
            f"block size mismatch: header says 0x{expected_size:X}, actual 0x{len(chunk):X}"
        )
    entry_offsets = list(struct.unpack_from(f"<{entry_count}H", chunk, 4)) if entry_count else []
    code_off = 4 + entry_count * 2
    code_words = list(struct.unpack_from(f"<{code_count}H", chunk, code_off)) if code_count else []
    return Block(entry_offsets=entry_offsets, code_words=code_words)


def build_block(entry_offsets: list[int], code_words: list[int]) -> bytes:
    words = [len(entry_offsets), len(code_words), *entry_offsets, *code_words]
    return struct.pack(f"<{len(words)}H", *words)


def parse_block(block: Block, name: str) -> tuple[list[Instr], list[str]]:
    issues: list[str] = []
    instrs: list[Instr] = []
    code = block.code_words
    i = 0
    while i < len(code):
        op = code[i]
        if is_text_word(op):
            start = i
            raw = [op]
            i += 1
            while i < len(code):
                nxt = code[i]
                if not is_text_word(nxt) and nxt != 0:
                    break
                raw.append(nxt)
                i += 1
            instrs.append(Instr(start, op, len(raw), [], raw))
            continue
        if i + 1 >= len(code):
            issue = "missing argc at instruction tail"
            issues.append(f"{name}:{i:04X}:{issue}")
            instrs.append(Instr(i, op, 0, [], [op], issue))
            break
        argc = code[i + 1]
        end = i + 2 + argc * 2
        if end > len(code):
            issue = f"argument area out of range argc={argc}"
            issues.append(f"{name}:{i:04X}:{issue}")
            instrs.append(Instr(i, op, argc, [], code[i:], issue))
            break
        raw = code[i:end]
        args = [Arg(code[i + 2 + j * 2], code[i + 3 + j * 2]) for j in range(argc)]
        instrs.append(Instr(i, op, argc, args, raw))
        i = end
    return instrs, issues


def split_text_blocks(instrs: list[Instr], targets: set[int]) -> list[Instr]:
    out: list[Instr] = []
    for instr in instrs:
        if not instr.is_text() or len(instr.raw) <= 1:
            out.append(instr)
            continue
        cuts = [instr.offset_words]
        for target in sorted(targets):
            if instr.offset_words < target < instr.offset_words + len(instr.raw):
                cuts.append(target)
        cuts.append(instr.offset_words + len(instr.raw))
        if len(cuts) == 2:
            out.append(instr)
            continue
        for start, end in zip(cuts, cuts[1:]):
            base = start - instr.offset_words
            raw = instr.raw[base : base + (end - start)]
            out.append(Instr(start, raw[0], len(raw), [], raw, instr.issue))
    return out


def build_text_table(instrs: list[Instr]) -> tuple[dict[int, int], list[str]]:
    text_refs: dict[int, int] = {}
    text_lines: list[str] = []
    for instr in sorted(instrs, key=lambda item: item.offset_words):
        if not instr.is_text():
            continue
        text_refs[instr.offset_words] = len(text_lines) + 1
        text_lines.append(render_text_content(instr.raw))
    return text_refs, text_lines


def render_header(issues: list[str]) -> list[str]:
    lines: list[str] = []
    if issues:
        lines.append("; !!! alignment errors detected, inspect these locations first !!!")
        for issue in issues:
            lines.append(f"; !!! {issue} !!!")
        lines.append("")
    return lines


def write_asm(dst: Path, block: Block, instrs: list[Instr], issues: list[str]) -> list[str]:
    entry_index_by_offset = {
        offset: idx for idx, offset in enumerate(block.entry_offsets) if 0 <= offset < len(block.code_words)
    }
    text_refs, text_lines = build_text_table(instrs)
    lines = render_header(issues)
    current_block: int | None = None
    for instr in sorted(instrs, key=lambda item: item.offset_words):
        if instr.offset_words in entry_index_by_offset:
            if current_block is not None:
                lines.append("}")
                lines.append("")
            current_block = entry_index_by_offset[instr.offset_words]
            lines.append(f"{current_block}:{{")
        elif current_block is None:
            current_block = -1
            lines.append("-1:{")
        lines.append(instr.render(text_refs))
    if current_block is not None:
        lines.append("}")
    dst.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return text_lines


def write_txt(dst: Path, text_lines: list[str]) -> None:
    dst.write_text("\n".join(text_lines) + ("\n" if text_lines else ""), encoding="utf-8")


def read_text_lines(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [line.rstrip("\r\n") for line in handle]


def parse_asm(path: Path) -> list[AsmCommand]:
    commands: list[AsmCommand] = []
    current_block = -1
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split(";", 1)[0].rstrip()
        if not line:
            continue
        if line.endswith(":{"):
            current_block = int(line[:-2])
            continue
        if line == "}":
            continue
        commands.append(AsmCommand(current_block, line))
    return commands


def parse_call(text: str) -> tuple[str, list[str]]:
    if not text.endswith(")"):
        raise ValueError(f"invalid command syntax: {text}")
    left = text.find("(")
    if left < 0:
        raise ValueError(f"invalid command syntax: {text}")
    name = text[:left]
    body = text[left + 1 : -1]
    args = [] if body == "" else body.split(",")
    return name, args


def parse_arg(token: str) -> Arg:
    if re.fullmatch(r"f[0-9]+", token):
        return Arg(1, int(token[1:]))
    if re.fullmatch(r"v[0-9]+", token):
        return Arg(2, int(token[1:]))
    match = re.fullmatch(r"t([0-9]+)\(([0-9]+)\)", token)
    if match:
        return Arg(int(match.group(1)), int(match.group(2)))
    return Arg(0, int(token))


def command_length(command: AsmCommand, text_lines: list[str]) -> int:
    if command.text.startswith("text(") and command.text.endswith(")"):
        line_no = int(command.text[5:-1])
        if line_no < 1 or line_no > len(text_lines):
            raise ValueError(f"{command.text}: text line does not exist")
        return len(encode_text_content(text_lines[line_no - 1]))
    _, args = parse_call(command.text)
    return 2 + len(args) * 2


def build_entry_offsets(
    commands: list[AsmCommand], text_lines: list[str]
) -> tuple[dict[int, int], dict[tuple[int, int], int]]:
    entries: dict[int, int] = {}
    refs: dict[tuple[int, int], int] = {}
    offset = 0
    current_block = None
    current_cmd = 0
    for command in commands:
        if command.block != current_block:
            current_block = command.block
            current_cmd = 0
            if current_block >= 0:
                entries[current_block] = offset
        refs[(command.block, current_cmd)] = offset
        offset += command_length(command, text_lines)
        current_cmd += 1
    return entries, refs


def encode_command(command: AsmCommand, text_lines: list[str]) -> list[int]:
    if command.text.startswith("text(") and command.text.endswith(")"):
        line_no = int(command.text[5:-1])
        if line_no < 1 or line_no > len(text_lines):
            raise ValueError(f"{command.text}: text line does not exist")
        return encode_text_content(text_lines[line_no - 1])
    name, raw_args = parse_call(command.text)
    opcode = int(name[3:], 16) if name.startswith("op_") else NAME_TO_OPCODE[name]
    args = [parse_arg(token) for token in raw_args]
    words = [opcode, len(args)]
    for arg in args:
        words.extend((arg.kind, arg.value))
    return words


def encode_block_from_sources(asm_path: Path, txt_path: Path | None) -> bytes:
    commands = parse_asm(asm_path)
    text_lines = read_text_lines(txt_path) if txt_path and txt_path.exists() else []
    entries_map, _refs = build_entry_offsets(commands, text_lines)
    code_words: list[int] = []
    for command in commands:
        code_words.extend(encode_command(command, text_lines))
    if entries_map:
        entry_count = max(entries_map) + 1
        entry_offsets = [entries_map[index] for index in range(entry_count)]
    else:
        entry_offsets = []
    return build_block(entry_offsets, code_words)


def patch_elf_entries(src_elf_path: Path, dst_elf_path: Path, entries: list[DirEntry]) -> None:
    data = bytearray(src_elf_path.read_bytes())
    base = elf_table_offset(src_elf_path)
    for entry in entries:
        off = base + entry.index * ENTRY_SIZE
        raw_name = entry.name.encode("ascii")
        if len(raw_name) > 8:
            raise ValueError(f"entry name too long: {entry.name}")
        data[off : off + 8] = raw_name.ljust(8, b"\x00")
        struct.pack_into("<I", data, off + 8, entry.offset)
        struct.pack_into("<I", data, off + 12, entry.size)
    dst_elf_path.parent.mkdir(parents=True, exist_ok=True)
    dst_elf_path.write_bytes(data)


def elf_table_offset(elf_path: Path) -> int:
    data = elf_path.read_bytes()
    if data[:4] != b"\x7FELF" or data[4] != 1 or data[5] != 1:
        raise ValueError(f"{elf_path}: expected 32-bit little-endian ELF")
    phoff = u32(data, 0x1C)
    entsz = u16(data, 0x2A)
    phnum = u16(data, 0x2C)
    for i in range(phnum):
        off = phoff + i * entsz
        if u32(data, off) != 1:
            continue
        file_off = u32(data, off + 4)
        vaddr = u32(data, off + 8)
        filesz = u32(data, off + 0x10)
        memsz = u32(data, off + 0x14)
        if vaddr <= ENTRY_TABLE_EA < vaddr + max(filesz, memsz):
            return file_off + (ENTRY_TABLE_EA - vaddr)
    raise ValueError(f"{elf_path}: could not map entry table address 0x{ENTRY_TABLE_EA:X}")


def load_dir_entries(elf_path: Path) -> list[DirEntry]:
    data = elf_path.read_bytes()
    base = elf_table_offset(elf_path)
    entries: list[DirEntry] = []
    for index in range(ENTRY_COUNT):
        off = base + index * ENTRY_SIZE
        raw_name = data[off : off + 8]
        name = raw_name.split(b"\x00", 1)[0].decode("ascii")
        entries.append(
            DirEntry(
                index=index,
                name=name,
                offset=u32(data, off + 8),
                size=u32(data, off + 12),
            )
        )
    return entries


def validate_entries(entries: list[DirEntry], data_size: int) -> None:
    if len(entries) != ENTRY_COUNT:
        raise ValueError("entry table length mismatch")
    expected = 0
    for entry in entries:
        if entry.offset != expected:
            raise ValueError(
                f"entry {entry.index} {entry.name}: expected offset 0x{expected:X}, got 0x{entry.offset:X}"
            )
        expected += entry.size
    if expected != data_size:
        raise ValueError(f"entry sizes sum to 0x{expected:X}, file size is 0x{data_size:X}")


def extract_text(script_path: Path, out_dir: Path, elf_path: Path) -> None:
    data = script_path.read_bytes()
    entries = load_dir_entries(elf_path)
    totals = Counter(entry.name for entry in entries)
    validate_entries(entries, len(data))
    out_dir.mkdir(parents=True, exist_ok=True)
    used: dict[str, int] = {}
    for entry in entries:
        chunk = data[entry.offset : entry.offset + entry.size]
        if len(chunk) != entry.size:
            raise ValueError(f"truncated chunk for entry {entry.index} {entry.name}")
        block = split_block(chunk)
        instrs, issues = parse_block(block, f"{entry.index:04X}_{entry.name}")
        instrs = split_text_blocks(instrs, set(block.entry_offsets))
        stem = export_stem(entry.name, used, totals)
        asm_path = out_dir / f"{stem}.asm"
        txt_path = out_dir / f"{stem}.txt"
        text_lines = write_asm(asm_path, block, instrs, issues)
        if text_lines:
            write_txt(txt_path, text_lines)
        elif txt_path.exists():
            txt_path.unlink()


def rebuild_text(in_dir: Path, out_file: Path, elf_path: Path, elf_out_path: Path | None) -> None:
    elf_entries = load_dir_entries(elf_path)
    sources = source_map(in_dir, elf_entries)
    out = bytearray()
    new_entries: list[DirEntry] = []
    for (asm_path, txt_path), elf_entry in zip(sources, elf_entries):
        chunk = encode_block_from_sources(asm_path, txt_path)
        new_entries.append(
            DirEntry(
                index=elf_entry.index,
                name=elf_entry.name,
                offset=len(out),
                size=len(chunk),
            )
        )
        out.extend(chunk)
    validate_entries(new_entries, len(out))
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_bytes(out)
    final_elf_out = elf_out_path if elf_out_path is not None else out_file.with_name(elf_path.name)
    patch_elf_entries(elf_path, final_elf_out, new_entries)


def usage() -> int:
    print("usage: python scn.py d script.dat out_dir [elf]")
    print("   or: python scn.py e in_dir out_script.dat [elf] [elf_out] [tbl]")
    return 1


def main(argv: list[str]) -> int:
    global TEXT_CONVERTER, TEXT_ENCODING
    TEXT_ENCODING = "cp932"
    TEXT_CONVERTER = None
    if len(argv) < 4:
        return usage()
    mode = argv[1].lower()
    if mode == "d":
        script_path = Path(argv[2])
        out_dir = Path(argv[3])
        elf_path = Path(argv[4]) if len(argv) >= 5 else DEFAULT_ELF
        extract_text(script_path, out_dir, elf_path)
        return 0
    if mode == "e":
        in_dir = Path(argv[2])
        out_file = Path(argv[3])
        elf_path = Path(argv[4]) if len(argv) >= 5 else DEFAULT_ELF
        elf_out_path = Path(argv[5]) if len(argv) >= 6 else None
        tbl_path = Path(argv[6]) if len(argv) >= 7 else DEFAULT_TBL
        char.MAP_PATH = tbl_path
        TEXT_CONVERTER = char.make_translation_converter()
        rebuild_text(in_dir, out_file, elf_path, elf_out_path)
        return 0
    return usage()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
