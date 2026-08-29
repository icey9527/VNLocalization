from __future__ import annotations

import re
import struct
import sys
from dataclasses import dataclass
from functools import lru_cache
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
HEX_TOKEN_RE = re.compile(r"<([0-9a-f]{1,4})(?::([0-9]+(?:,[0-9]+)*))?>")
FURI_TOKEN_RE = re.compile(r"<f:([^|<>]*)\|([^|<>]*)>")

FURI_MARK_OP = 0x04B0        # 振り仮名结构: [4B0]汉字[4B1]假名[4B2]
FURI_READ_OP = 0x04B1
FURI_END_OP = 0x04B2

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
    0x0070: "trans",           # 画面过渡效果 (sub_411800 转场状态机, 阻塞至完成)
    0x0071: "return",
    0x0072: "trans2",          # 画面过渡效果变体 (初始化后立即返回)
    0x03E8: "br",              # 换行: x 回行首 + 下移一行
    0x03E9: "br_keep_x",       # 换行变体: 仅下移一行
    0x03EA: "click_wait",      # 等待点击 (显示继续箭头)
    0x03EB: "click_wait_bare", # 等待点击 (无箭头/无图标)
    0x03EC: "click_wait_auto", # 等待点击 (自动播放图标)
    0x03F0: "text_speed",
    0x03F1: "auto_off",        # 自动播放关闭
    0x03F2: "auto_on",         # 自动播放开启
    0x03F3: "pos_x",           # 设置文本 x 坐标
    0x03F4: "pos_y",           # 设置文本 y 坐标
    0x03F5: "page_wait",       # 翻页等待点击
    0x03FC: "msg_reset",
    0x03FD: "msg_wait_idle",
    0x03FE: "msg_sync",
    0x0400: "msg_flags",
    0x0401: "voice_play",      # 语音播放 (变长等待)
    0x0402: "voice_check",     # 语音比对 (同 ID 不重播)
    0x0403: "wait_frame",      # 按参数计算等待帧数
    0x0406: "msg_voice_id",
    0x040A: "msg_layer_reset",
    0x040B: "msg_layer_wait",
    0x040C: "msg_layer_toggle",
    0x040D: "msg_layer_close",
    0x040E: "msg_layer_toggle_wait",
    0x047E: "voiced",         # 带语音对话段开始: 4 参数, 播语音 + 文本段直到 click_wait
    0x047F: "voice_wait",     # 等待语音结束
    0x0480: "nop",
    0x04B0: "furi_mark",      # 振り仮名开始 (后跟基准汉字文本)
    0x04B1: "furi_read",      # 基准结束, 后跟注音假名文本
    0x04B2: "furi_end",       # 注音结束
}

# 引擎静态跳转目标只有入口表 (entry_offsets)。
# 0x0003/0x0005 的参数是 (脚本号, 入口号), 0x0006 的参数是入口号,
# 0x0070/0x0072 是画面过渡效果命令 (sub_411800 转场状态机), 参数为效果类型号。
# 以上参数均非代码区 word 偏移, 不得作为切分文本的跳转目标。
FLOW_OPS: set[int] = set()
NAME_TO_OPCODE = {name: op for op, name in OP_NAMES.items()}
NAME_TO_OPCODE["choice_hook"] = 0x047E  # 旧名兼容 (实为 voiced)


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
    # segs: 混合文本行内容. 元素: ('t', 字数) | ('f', 基准words, 注音words)
    segs: list | None = None
    # 单独一条全角空格文本指令 → 渲染为 indent() 命令, 编码时按当前编码动态取空格 word
    indent: bool = False

    def is_text(self) -> bool:
        if self.indent:
            return False
        if self.segs is not None:
            return True
        return self.op >= 0x8000 or 0x44D <= self.op <= 0x47A

    def name(self) -> str:
        if self.indent:
            return "indent"
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


@lru_cache(maxsize=None)
def encode_text_content(text: str) -> tuple[int, ...]:
    words: list[int] = []
    pos = 0
    while pos < len(text):
        match = FURI_TOKEN_RE.search(text, pos)
        if not match:
            words.extend(encode_text_tokens(text[pos:]))
            break
        if match.start() > pos:
            words.extend(encode_text_tokens(text[pos : match.start()]))
        base = encode_text_tokens(match.group(1))
        anno = encode_text_tokens(match.group(2))
        words.append(FURI_MARK_OP)
        words.append(0)
        words.extend(base)
        words.append(FURI_READ_OP)
        words.append(0)
        words.extend(anno)
        words.append(FURI_END_OP)
        words.append(0)
        pos = match.end()
    return tuple(words)


def encode_text_tokens(text: str) -> list[int]:
    words: list[int] = []
    pos = 0
    while pos < len(text):
        hex_match = HEX_TOKEN_RE.search(text, pos)
        match = TEXT_TOKEN_RE.search(text, pos)
        if hex_match and (not match or hex_match.start() <= match.start()):
            match = hex_match
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
        elif re.fullmatch(r"[0-9a-f]{1,4}", token):
            op = int(token, 16)
            args = [int(x) for x in match.group(2).split(",")] if match.group(2) else []
            words.append(op)
            words.append(len(args))
            for value in args:
                words.extend((0, value))
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


def space_word() -> int:
    """全角空格 (U+3000) 在当前 TEXT_ENCODING 下的 word 值。
    cp932 → 0x8140, cp936 → 0xA1A1。不写死, 随编码动态计算。"""
    data = "\u3000".encode(TEXT_ENCODING)
    if len(data) != 2:
        raise ValueError(f"cannot encode U+3000 under {TEXT_ENCODING}")
    return (data[0] << 8) | data[1]


def mark_indent(instrs: list[Instr]) -> list[Instr]:
    """把单独一条全角空格文本指令标记为 indent 伪命令。
    仅匹配整条指令只有一个字且为 U+3000 的情况; 句首带空格的正常文本不受影响。"""
    for instr in instrs:
        if (
            not instr.indent
            and instr.segs is None
            and not instr.issue
            and instr.is_text()
            and len(instr.raw) == 1
            and decode_text_word(instr.raw[0]) == "\u3000"
        ):
            instr.indent = True
    return instrs


def render_segs(words: list[int], segs: list) -> str:
    out: list[str] = []
    off = 0
    for seg in segs:
        if seg[0] == "t":
            out.append(render_text_content(words[off : off + seg[1]]))
            off += seg[1]
        else:  # ('f', 基准words, 注音words)
            _, base, anno = seg
            out.append(f"<f:{render_text_content(base)}|{render_text_content(anno)}>")
            off += 2 + len(base) + 2 + len(anno) + 2
    return "".join(out)


def render_text_content(words: list[int], segs: list | None = None) -> str:
    if segs:
        return render_segs(words, segs)
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
    return code, fold_ruby(instrs), entries, issues


def match_furi(instrs: list[Instr], j: int) -> tuple[list[int], list[int], int] | None:
    """匹配振り仮名结构: [4B0][基准汉字text][4B1][注音假名text][4B2], 返回 (基准words, 注音words, 消耗指令数)"""
    n = len(instrs)
    if (
        j + 4 < n
        and instrs[j].op == FURI_MARK_OP
        and instrs[j].argc == 0
        and not instrs[j].issue
        and instrs[j + 1].is_text()
        and instrs[j + 1].segs is None
        and not instrs[j + 1].issue
        and instrs[j + 2].op == FURI_READ_OP
        and instrs[j + 2].argc == 0
        and not instrs[j + 2].issue
        and instrs[j + 3].is_text()
        and instrs[j + 3].segs is None
        and not instrs[j + 3].issue
        and instrs[j + 4].op == FURI_END_OP
        and instrs[j + 4].argc == 0
        and not instrs[j + 4].issue
    ):
        return instrs[j + 1].raw, instrs[j + 3].raw, 5
    return None


def fold_ruby(instrs: list[Instr]) -> list[Instr]:
    """相邻的 文本/振り仮名 合并成一个混合文本行 (不换行, 振り仮名以 <f:汉字|假名> 内联表示).
    voiced/click_wait 等控制命令保留在 asm 中, 不进入文本."""
    n = len(instrs)
    out: list[Instr] = []
    i = 0
    while i < n:
        ins = instrs[i]

        def plain_text(x: Instr) -> bool:
            return x.is_text() and x.segs is None and not x.issue

        if plain_text(ins) or ins.op == FURI_MARK_OP:
            segs: list[tuple] = []
            raw_all: list[int] = []
            start = ins.offset_words
            j = i
            has_furi = False
            while j < n:
                cur = instrs[j]
                if plain_text(cur):
                    segs.append(("t", len(cur.raw)))
                    raw_all.extend(cur.raw)
                    j += 1
                    continue
                furi = match_furi(instrs, j)
                if furi is not None:
                    base, anno, used = furi
                    segs.append(("f", base, anno))
                    raw_all.extend([FURI_MARK_OP, 0])
                    raw_all.extend(base)
                    raw_all.extend([FURI_READ_OP, 0])
                    raw_all.extend(anno)
                    raw_all.extend([FURI_END_OP, 0])
                    j += used
                    has_furi = True
                    continue
                break
            if has_furi and j > i:
                merged = Instr(start, raw_all[0], len(raw_all), [], raw_all)
                merged.segs = segs
                out.append(merged)
                i = j
                continue
        out.append(ins)
        i += 1
    return out


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
        text_lines.append(render_text_content(instr.raw, instr.segs))
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
    if command.text == "indent()":
        return 1
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
    if command.text == "indent()":
        return [space_word()]
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
    output_dir.mkdir(parents=True, exist_ok=True)
    entries, code, code_words = split_dat(src)
    if len(code) != code_words:
        raise ValueError(f"{src.name}: code_words mismatch")
    code, instrs, entries, issues = parse(src)
    instrs = split_text_blocks(instrs, collect_targets(entries, instrs, code_words))
    instrs = mark_indent(instrs)
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
