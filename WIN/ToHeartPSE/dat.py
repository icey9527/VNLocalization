from __future__ import annotations

import re
import struct
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent
TEXT_ENCODING = "cp932"

FULL_TEXT_SEQS = (
    ("family", tuple(range(0x44D, 0x453))),    # 姓氏
    ("name", tuple(range(0x457, 0x45D))),     # 名字
    ("nick", tuple(range(0x461, 0x467))),      # 昵称
    ("hira", tuple(range(0x46B, 0x471))),      # 平假名 (缩写)
    ("kata", tuple(range(0x475, 0x47B))),      # 片假名 (缩写)
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
    0x0003: "call",
    0x0005: "dat_call",
    0x0006: "jump",
    0x0007: "set_seen",
    0x0008: "test_seen",
    0x0009: "yield",
    0x0028: "mov",
    0x0029: "add",
    0x002A: "sub",
    0x002B: "mul",
    0x002C: "div",
    0x002D: "mod",
    0x002E: "and",
    0x002F: "or",
    0x0030: "xor",
    0x0031: "rand",
    0x0032: "cmp_eq",
    0x0033: "cmp_ne",
    0x0034: "cmp_lt",
    0x003C: "bg_load",
    0x003D: "bg_fade",
    0x003E: "bg_pos",
    0x003F: "bg_scroll",
    0x0040: "sprite_load",
    0x0041: "sprite_move",
    0x0042: "sprite_show",
    0x0043: "sprite_hide",
    0x0044: "sprite_anim",
    0x0045: "face_load",
    0x0046: "msg_open",
    0x0047: "msg_wait",
    0x0048: "msg_close",
    0x0049: "voice",
    0x004A: "sfx",
    0x0050: "select",
    0x005F: "bgm",
    0x0060: "if",
    0x0061: "if_not",
    0x0064: "menu",
    0x0065: "menu_end",
    0x0066: "sys",
    0x0067: "effect",
    0x0068: "wait",
    0x0069: "timer",
    0x006E: "stack_push",
    0x006F: "stack_pop",
    0x0070: "gosub",
    0x0071: "return",
    0x0072: "gosub_if",
    0x03F0: "text_speed",
    0x03FC: "msg_reset",
    0x03FD: "msg_wait_idle",
    0x03FE: "msg_sync",
    0x0400: "msg_flags",
    0x0406: "msg_voice_id",
    0x040A: "msg_layer_reset",
    0x040B: "msg_layer_wait",
    0x040C: "msg_layer_toggle",
    0x040D: "msg_layer_close",
    0x040E: "msg_layer_toggle_wait",
    0x047E: "choice_hook",
}

FLOW_OPS = {0x0003, 0x0070, 0x0072}
NAME_TO_OPCODE = {name: op for op, name in OP_NAMES.items()}


@dataclass
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


@dataclass
class Instr:
    offset_words: int
    op: int
    argc: int
    args: list[Arg]
    raw: list[int]
    issue: str = ""

    def is_text(self) -> bool:
        return self.op >= 0x8000 or 0x44D <= self.op <= 0x47A

    def name(self) -> str:
        if self.is_text():
            return "text"
        return OP_NAMES.get(self.op, f"op_{self.op:04X}")

    def render(self, refs: dict[int, str], text_refs: dict[int, int]) -> str:
        if self.is_text():
            body = f"text({text_refs[self.offset_words]})"
        else:
            parts = []
            for index, arg in enumerate(self.args):
                if self.op == 0x0006 and index == 0 and arg.kind == 0:
                    parts.append(str(arg.value))
                elif self.op in FLOW_OPS and index == 0 and arg.kind == 0:
                    parts.append(refs.get(arg.value, str(arg.value)))
                else:
                    parts.append(arg.render())
            body = f"{self.name()}({','.join(parts)})" if parts else f"{self.name()}()"
        if self.issue:
            return f"{body} ; !!! ALIGNMENT_ERROR: {self.issue} !!!"
        return body


@dataclass
class AsmCommand:
    block: int
    text: str


def encode_text_content(text: str) -> list[int]:
    words: list[int] = []
    pos = 0
    while pos < len(text):
        match = TEXT_TOKEN_RE.search(text, pos)
        if not match:
            words.extend(encode_text_plain(text[pos:]))
            break
        if match.start() > pos:
            words.extend(encode_text_plain(text[pos:match.start()]))
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


def encode_text_plain(text: str) -> list[int]:
    words: list[int] = []
    for ch in text:
        if ord(ch) < 0x80 or 0xFF61 <= ord(ch) <= 0xFF9F:
            raise ValueError(f"halfwidth character is not allowed: {ch!r}")
    encoded = text.encode(TEXT_ENCODING, errors="ignore")
    if len(encoded) % 2:
        raise ValueError("text encoded to odd byte length")
    for i in range(0, len(encoded), 2):
        word = (encoded[i] << 8) | encoded[i + 1]
        if word == 0x849F:
            word = 0x86A2
        words.append(word)
    return words


def decode_text_word(word: int) -> str:
    if word in {0x0000, 0xFFFF}:
        return ""
    if word == 0x86A2:
        word = 0x849F
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


def split_dat(path: Path) -> tuple[list[int], list[int], int]:
    data = path.read_bytes()
    if len(data) < 4 or len(data) % 2:
        raise ValueError("invalid DAT size")
    words = list(struct.unpack(f"<{len(data) // 2}H", data))
    entry_count = words[0]
    code_words = words[1]
    entries = words[2 : 2 + entry_count]
    code = words[2 + entry_count :]
    if len(code) != code_words:
        raise ValueError(f"{path.name}: header size mismatch")
    return entries, code, code_words


def parse(path: Path) -> tuple[list[int], list[Instr], list[int], list[str]]:
    entries, code, _code_words = split_dat(path)
    issues: list[str] = []
    instrs: list[Instr] = []
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
            issues.append(f"{path.name}:{i:04X}:{issue}")
            instrs.append(Instr(i, op, 0, [], [op], issue))
            break
        argc = code[i + 1]
        end = i + 2 + argc * 2
        if end > len(code):
            issue = f"argument area out of range argc={argc}"
            issues.append(f"{path.name}:{i:04X}:{issue}")
            instrs.append(Instr(i, op, argc, [], code[i:], issue))
            break
        raw = code[i:end]
        args = [Arg(code[i + 2 + j * 2], code[i + 3 + j * 2]) for j in range(argc)]
        instrs.append(Instr(i, op, argc, args, raw))
        i = end
    return code, instrs, entries, issues


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


def collect_targets(entries: list[int], instrs: list[Instr], code_words: int) -> set[int]:
    targets = {offset for offset in entries if 0 <= offset < code_words}
    for instr in instrs:
        if instr.op not in FLOW_OPS or not instr.args:
            continue
        arg = instr.args[0]
        if arg.kind == 0 and 0 <= arg.value < code_words:
            targets.add(arg.value)
    return targets


def build_ref_map(entries: list[int], instrs: list[Instr], code_words: int) -> dict[int, str]:
    entry_offsets = sorted((offset, idx) for idx, offset in enumerate(entries) if 0 <= offset < code_words)
    refs: dict[int, str] = {}
    current_block = -1
    current_cmd = 0
    entry_pos = 0
    for instr in sorted(instrs, key=lambda item: item.offset_words):
        while entry_pos < len(entry_offsets) and instr.offset_words >= entry_offsets[entry_pos][0]:
            current_block = entry_offsets[entry_pos][1]
            current_cmd = 0
            entry_pos += 1
        if current_block < 0:
            continue
        refs[instr.offset_words] = f"{current_block}:{current_cmd}"
        current_cmd += 1
    return refs


def render_header(issues: list[str]) -> list[str]:
    lines: list[str] = []
    if issues:
        lines.append("; !!! alignment errors detected, inspect these locations first !!!")
        for issue in issues:
            lines.append(f"; !!! {issue} !!!")
        lines.append("")
    return lines


def build_text_table(instrs: list[Instr]) -> tuple[dict[int, int], list[str]]:
    text_refs: dict[int, int] = {}
    text_lines: list[str] = []
    for instr in sorted(instrs, key=lambda item: item.offset_words):
        if not instr.is_text():
            continue
        text_refs[instr.offset_words] = len(text_lines) + 1
        text_lines.append(render_text_content(instr.raw))
    return text_refs, text_lines


def write_asm(dst: Path, code_words: int, entries: list[int], instrs: list[Instr], issues: list[str]) -> list[str]:
    refs = build_ref_map(entries, instrs, code_words)
    text_refs, text_lines = build_text_table(instrs)
    lines = render_header(issues)
    entry_index_by_offset = {offset: idx for idx, offset in enumerate(entries) if 0 <= offset < code_words}
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
        lines.append(instr.render(refs, text_refs))
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


def command_length(command: AsmCommand, text_lines: list[str]) -> int:
    if command.text.startswith("text(") and command.text.endswith(")"):
        line_no = int(command.text[5:-1])
        if line_no < 1 or line_no > len(text_lines):
            raise ValueError(f"{command.text}: text line does not exist")
        return len(encode_text_content(text_lines[line_no - 1]))
    _, args = parse_call(command.text)
    return 2 + len(args) * 2


def build_block_offsets(commands: list[AsmCommand], text_lines: list[str]) -> tuple[dict[int, int], dict[tuple[int, int], int]]:
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


def parse_arg(token: str, refs: dict[tuple[int, int], int], flow_target: bool) -> Arg:
    if re.fullmatch(r"f[0-9]+", token):
        return Arg(1, int(token[1:]))
    if re.fullmatch(r"v[0-9]+", token):
        return Arg(2, int(token[1:]))
    match = re.fullmatch(r"t([0-9]+)\(([0-9]+)\)", token)
    if match:
        return Arg(int(match.group(1)), int(match.group(2)))
    if flow_target and ":" in token:
        block_text, cmd_text = token.split(":", 1)
        key = (int(block_text), int(cmd_text))
        if key not in refs:
            raise ValueError(f"unknown flow target: {token}")
        return Arg(0, refs[key])
    return Arg(0, int(token))


def encode_command(command: AsmCommand, text_lines: list[str], refs: dict[tuple[int, int], int]) -> list[int]:
    if command.text.startswith("text(") and command.text.endswith(")"):
        line_no = int(command.text[5:-1])
        if line_no < 1 or line_no > len(text_lines):
            raise ValueError(f"{command.text}: text line does not exist")
        return encode_text_content(text_lines[line_no - 1])
    name, raw_args = parse_call(command.text)
    if name.startswith("op_"):
        opcode = int(name[3:], 16)
    else:
        if name not in NAME_TO_OPCODE:
            raise ValueError(f"unknown opcode name: {name}")
        opcode = NAME_TO_OPCODE[name]
    args = [
        parse_arg(token, refs, opcode in FLOW_OPS and index == 0)
        for index, token in enumerate(raw_args)
    ]
    words = [opcode, len(args)]
    for arg in args:
        words.extend((arg.kind, arg.value))
    return words


def encode_one(input_dir: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for asm_path in sorted(input_dir.glob("*.asm")):
        txt_path = asm_path.with_suffix(".txt")
        commands = parse_asm(asm_path)
        text_lines = read_text_lines(txt_path) if txt_path.exists() else []
        entries_map, refs = build_block_offsets(commands, text_lines)
        code: list[int] = []
        for command in commands:
            code.extend(encode_command(command, text_lines, refs))
        if entries_map:
            entry_count = max(entries_map) + 1
            entries = [entries_map[index] for index in range(entry_count)]
        else:
            entry_count = 0
            entries = []
        words = [entry_count, len(code), *entries, *code]
        data = struct.pack(f"<{len(words)}H", *words)
        (output_dir / f"{asm_path.stem}.DAT").write_bytes(data)


def collect_sources(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    return sorted(p for p in input_path.glob("*.DAT") if p.is_file())


def decode_one(src: Path, output_dir: Path) -> list[str]:
    entries, code, code_words = split_dat(src)
    if len(code) != code_words:
        raise ValueError(f"{src.name}: code_words mismatch")
    code, instrs, entries, issues = parse(src)
    instrs = split_text_blocks(instrs, collect_targets(entries, instrs, code_words))
    dst_base = output_dir / src.stem.upper()
    text_lines = write_asm(dst_base.with_suffix(".asm"), code_words, entries, instrs, issues)
    if text_lines:
        write_txt(dst_base.with_suffix(".txt"), text_lines)
    return issues


def decode_all(input_path: Path, output_dir: Path) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    total_issues = 0
    for src in collect_sources(input_path):
        issues = decode_one(src, output_dir)
        total_issues += len(issues)
    return total_issues


def usage() -> int:
    print("usage: python dat.py mode input_dir output_dir [-e encoding]")
    print("example: python dat.py d scn test -e cp932")
    return 1


def main(argv: list[str]) -> int:
    global TEXT_ENCODING
    if len(argv) not in {4, 6}:
        return usage()
    if len(argv) == 6:
        if argv[4] != "-e":
            return usage()
        TEXT_ENCODING = argv[5]
    mode = argv[1].lower()
    input_path = Path(argv[2])
    output_path = Path(argv[3])
    if not input_path.is_absolute():
        input_path = ROOT / input_path
    if not output_path.is_absolute():
        output_path = ROOT / output_path
    if mode == "e":
        encode_one(input_path, output_path)
        print(f"output: {output_path}")
        return 0
    if mode != "d":
        return usage()
    if not input_path.exists():
        print(f"input does not exist: {input_path}")
        return 3
    total_issues = decode_all(input_path, output_path)
    print(f"output: {output_path}")
    print(f"alignment_errors: {total_issues}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
