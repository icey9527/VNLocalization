#!/usr/bin/env python3
import sys
import struct
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional


PLACEHOLDER_TO_CODE = {
    "[娘の名前]": 0xFFFF,
    "[娘の名字]": 0xFFFE,
    "[汎用文字列]": 0xFFFD,
    "[汎用数値]": 0xFFFC,
}
CODE_TO_PLACEHOLDER = {v: k for k, v in PLACEHOLDER_TO_CODE.items()}
RE_TOKEN = re.compile(r'(\[(?:娘の名前|娘の名字|汎用文字列|汎用数値|CODE:0x[0-9A-Fa-f]{1,4})\])')


COMMAND_VALUES = {
    0x00: ('LABEL', 'B'),
    0x01: ('GOTO', 'B'),
    0x02: ('FLAG', '<HB'),
    0x03: ('BG', '<H'),
    0x04: ('BG2', '<H'),
    0x05: ('CHAR', '<BH'),
    0x06: ('OFF_CHAR', 'B'),
    0x07: ('FACE', '<H'),
    0x08: ('VOICE', '<H'),
    0x09: ('MESSAGE_NAME', None),
    0x0A: ('MESSAGE', None),
    0x0B: ('LINE_FEED', ''),
    0x0C: ('KEY_WAIT', ''),
    0x0D: ('MESSAGE_WINDOW', 'B'),
    0x0E: ('DATE_WINDOW', 'B'),
    0x0F: ('OFF_FACE_WINDOW', ''),
    0x10: ('SELECT', None),
    0x11: ('SE_PLAY', 'B'),
    0x12: ('SE_WAIT', ''),
    0x13: ('SE_STOP', ''),
    0x14: ('BGM_PLAY', 'B'),
    0x15: ('ROOM_BGM_PLAY', ''),
    0x16: ('BGM_STOP', '<H'),
    0x17: ('TEXT_MODE', 'B'),
    0x18: ('SPECIAL', 'B'),
    0x19: ('QUAKE', ''),
    0x1A: ('GOLD', ''),
    0x1B: ('PARAM', ''),
    0x1C: ('END', 'B'),
    0x1D: ('UNKNOWN_0x1D', ''),
    0xFF: ('NOP', ''),
}
NAME_TO_OPCODE = {v[0]: k for k, v in COMMAND_VALUES.items()}


def usage() -> None:
    print("usage: python tool.py d|e input output tbl", file=sys.stderr)
    sys.exit(1)


def load_table(table_file: Path) -> Dict[int, str]:
    table: Dict[int, str] = {}
    with open(table_file, 'r', encoding='utf-16') as f:
        for lineno, line in enumerate(f, 1):
            line = line.rstrip('\r\n')
            if not line or '=' not in line:
                continue
            left, right = line.split('=', 1)
            try:
                idx = int(left.strip())
                table[idx] = right  # 右边直接是字符（可为空，但一般是1个字符）
            except Exception as e:
                print(f"table line {lineno} bad: {line} ({e})")
                continue
    if not table:
        raise ValueError("empty table")
    return table





def split_text_tokens(s: str) -> List[str]:
    if not s:
        return []
    parts = RE_TOKEN.split(s)
    return [p for p in parts if p]


def unescape_string(s: str) -> str:
    out = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch != '\\':
            out.append(ch)
            i += 1
            continue
        if i + 1 >= len(s):
            out.append('\\')
            break
        nx = s[i + 1]
        if nx == 'n':
            out.append('\n')
            i += 2
        elif nx == '\\':
            out.append('\\')
            i += 2
        elif nx == '"':
            out.append('"')
            i += 2
        else:
            out.append('\\')
            out.append(nx)
            i += 2
    return ''.join(out)


def escape_string(s: str) -> str:
    s = s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
    return f'"{s}"'


def unquote_string(token: str) -> str:
    token = token.strip()
    if len(token) >= 2 and token[0] == '"' and token[-1] == '"':
        return unescape_string(token[1:-1])
    raise ValueError(f"bad string: {token}")


def parse_int(tok: str) -> int:
    tok = tok.strip()
    return int(tok, 16) if tok.lower().startswith('0x') else int(tok, 10)


def encode_text_to_indices(s: str, char_to_index: Dict[str, int], fallback_idx: int) -> List[int]:
    indices: List[int] = []
    for t in split_text_tokens(s):
        if t in PLACEHOLDER_TO_CODE:
            indices.append(PLACEHOLDER_TO_CODE[t])
            continue

        if t.startswith("[CODE:0x") and t.endswith("]"):
            try:
                val = int(t[len("[CODE:"):-1], 16)
                indices.append(val & 0xFFFF)
            except Exception:
                MISSING['[BAD_CODE]'] = MISSING.get('[BAD_CODE]', 0) + 1
                indices.append(fallback_idx)
            continue

        for ch in t:
            code = char_to_index.get(ch)
            if code is None:
                MISSING[ch] = MISSING.get(ch, 0) + 1
                indices.append(fallback_idx)
            else:
                indices.append(code)

    return indices


def decode_indices_to_text(indices: List[int], table: Dict[int, str]) -> str:
    out: List[str] = []
    for code in indices:
        if code in CODE_TO_PLACEHOLDER:
            out.append(CODE_TO_PLACEHOLDER[code])
            continue
        ch = table.get(code)
        if ch is None:
            out.append(f"[CODE:0x{code:04X}]")
        else:
            out.append(ch)
    return ''.join(out)


class ScriptReader:
    def __init__(self, data: bytes, table: Dict[int, str]):
        self.data = data
        self.pos = 0
        self.table = table

    def eof(self) -> bool:
        return self.pos >= len(self.data)

    def rb(self) -> int:
        if self.pos >= len(self.data):
            raise EOFError
        b = self.data[self.pos]
        self.pos += 1
        return b

    def rs(self, fmt: str):
        n = struct.calcsize(fmt)
        if self.pos + n > len(self.data):
            raise EOFError
        v = struct.unpack(fmt, self.data[self.pos:self.pos + n])
        self.pos += n
        return v

    def read_indices(self, count: int) -> List[int]:
        return [self.rs('<H')[0] for _ in range(count)]

    def parse_message(self) -> str:
        n = self.rb()
        return decode_indices_to_text(self.read_indices(n), self.table)

    def parse_select(self) -> List[Tuple[int, str]]:
        count = self.rb()
        out: List[Tuple[int, str]] = []
        for _ in range(count):
            label = self.rb()
            n = self.rb()
            text = decode_indices_to_text(self.read_indices(n), self.table)
            out.append((label, text))
        return out

    def parse_all(self) -> Optional[List[dict]]:
        cmds: List[dict] = []
        while not self.eof():
            try:
                op = self.rb()
                spec = COMMAND_VALUES.get(op)
                if not spec:
                    return None

                name, fmt = spec
                if op in (0x09, 0x0A):
                    cmds.append({'name': name, 'text': self.parse_message()})
                elif op == 0x10:
                    cmds.append({'name': name, 'choices': self.parse_select()})
                else:
                    if fmt == '' or fmt is None:
                        cmds.append({'name': name, 'params': []})
                    else:
                        cmds.append({'name': name, 'params': list(self.rs(fmt))})
            except EOFError:
                return None
        return cmds


def format_asm(cmds: List[dict]) -> str:
    lines: List[str] = []
    i = 0
    while i < len(cmds):
        c = cmds[i]
        name = c['name']

        if name == 'MESSAGE':
            parts = [c.get('text', '')]
            j = i
            while j + 2 < len(cmds) and cmds[j + 1]['name'] == 'LINE_FEED' and cmds[j + 2]['name'] == 'MESSAGE':
                parts.append(cmds[j + 2].get('text', ''))
                j += 2
            merged = '\n'.join(parts)
            lines.append(f'MESSAGE {escape_string(merged)}')
            i = j + 1
            continue

        if name == 'MESSAGE_NAME':
            lines.append(f'MESSAGE_NAME {escape_string(c.get("text",""))}')
        elif name == 'SELECT':
            cs = c.get('choices', [])
            parts = [str(len(cs))]
            for label, text in cs:
                parts.append(str(label))
                parts.append(escape_string(text))
            lines.append("SELECT " + ", ".join(parts))
        else:
            ps = c.get('params', [])
            lines.append(name if not ps else f"{name} " + ", ".join(str(x) for x in ps))
        i += 1

    return "\n".join(lines)


def remove_comment(line: str) -> str:
    out = []
    in_str = False
    esc = False
    i = 0
    while i < len(line):
        ch = line[i]
        if in_str:
            out.append(ch)
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            out.append(ch)
            i += 1
            continue
        if ch == '/' and i + 1 < len(line) and line[i + 1] == '/':
            break
        if ch in ('#', ';'):
            break
        out.append(ch)
        i += 1
    return ''.join(out).strip()


def split_params(s: str) -> List[str]:
    res = []
    cur = []
    in_str = False
    esc = False
    for ch in s:
        if in_str:
            cur.append(ch)
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            cur.append(ch)
            continue
        if ch == ',':
            tok = ''.join(cur).strip()
            if tok:
                res.append(tok)
            cur = []
        else:
            cur.append(ch)
    tok = ''.join(cur).strip()
    if tok:
        res.append(tok)
    return res


def assemble_commands(lines: List[str], char_to_index: Dict[str, int], fallback_idx: int) -> bytes:
    out = bytearray()

    def emit_message(text: str):
        idxs = encode_text_to_indices(text, char_to_index, fallback_idx)
        if len(idxs) > 255:
            raise ValueError("MESSAGE too long (>255)")
        out.append(NAME_TO_OPCODE['MESSAGE'])
        out.append(len(idxs))
        for code in idxs:
            out.extend(struct.pack('<H', code))

    def emit_message_name(text: str):
        idxs = encode_text_to_indices(text, char_to_index, fallback_idx)
        if len(idxs) > 255:
            raise ValueError("MESSAGE_NAME too long (>255)")
        out.append(NAME_TO_OPCODE['MESSAGE_NAME'])
        out.append(len(idxs))
        for code in idxs:
            out.extend(struct.pack('<H', code))

    for lineno, raw in enumerate(lines, 1):
        line = remove_comment(raw)
        if not line:
            continue

        sp = line.split(None, 1)
        name = sp[0].strip()
        if name not in NAME_TO_OPCODE:
            raise ValueError(f"line {lineno}: unknown cmd {name}")

        if name == 'MESSAGE':
            if len(sp) == 1:
                raise ValueError(f"line {lineno}: MESSAGE needs string")
            text = unquote_string(sp[1].strip())
            parts = text.split('\n')
            for k, part in enumerate(parts):
                if k > 0:
                    out.append(NAME_TO_OPCODE['LINE_FEED'])
                emit_message(part)
            continue

        if name == 'MESSAGE_NAME':
            if len(sp) == 1:
                raise ValueError(f"line {lineno}: MESSAGE_NAME needs string")
            text = unquote_string(sp[1].strip())
            emit_message_name(text)
            continue

        opcode = NAME_TO_OPCODE[name]
        fmt = COMMAND_VALUES[opcode][1]
        out.append(opcode)

        if name == 'SELECT':
            if len(sp) == 1:
                raise ValueError(f"line {lineno}: SELECT needs params")
            ps = split_params(sp[1])
            if not ps:
                raise ValueError(f"line {lineno}: SELECT empty")
            count = parse_int(ps[0])
            if not (0 <= count <= 255):
                raise ValueError(f"line {lineno}: bad SELECT count")
            out.append(count)
            expect = 1 + count * 2
            if len(ps) != expect:
                raise ValueError(f"line {lineno}: SELECT needs {expect} params, got {len(ps)}")
            p = 1
            for _ in range(count):
                label = parse_int(ps[p]); p += 1
                text = unquote_string(ps[p]); p += 1
                if not (0 <= label <= 255):
                    raise ValueError(f"line {lineno}: SELECT label out of range")
                out.append(label)
                idxs = encode_text_to_indices(text, char_to_index, fallback_idx)
                if len(idxs) > 255:
                    raise ValueError(f"line {lineno}: SELECT text too long (>255)")
                out.append(len(idxs))
                for code in idxs:
                    out.extend(struct.pack('<H', code))
            continue

        if fmt == '' or fmt is None:
            continue

        if len(sp) == 1:
            raise ValueError(f"line {lineno}: {name} needs params")
        ps = split_params(sp[1])

        if fmt == 'B':
            if len(ps) != 1:
                raise ValueError(f"line {lineno}: {name} needs 1 param")
            out += struct.pack('B', parse_int(ps[0]) & 0xFF)
        elif fmt == '<H':
            if len(ps) != 1:
                raise ValueError(f"line {lineno}: {name} needs 1 param")
            out += struct.pack('<H', parse_int(ps[0]) & 0xFFFF)
        elif fmt == '<HB':
            if len(ps) != 2:
                raise ValueError(f"line {lineno}: {name} needs 2 params")
            out += struct.pack('<H', parse_int(ps[0]) & 0xFFFF)
            out += struct.pack('B', parse_int(ps[1]) & 0xFF)
        elif fmt == '<BH':
            if len(ps) != 2:
                raise ValueError(f"line {lineno}: {name} needs 2 params")
            out += struct.pack('B', parse_int(ps[0]) & 0xFF)
            out += struct.pack('<H', parse_int(ps[1]) & 0xFFFF)
        else:
            raise ValueError(f"line {lineno}: unsupported fmt {fmt}")

    return bytes(out)





if __name__ == '__main__':
    if len(sys.argv) != 5:
        usage()

    MISSING = {}

    mode = sys.argv[1].lower()
    ip = Path(sys.argv[2])
    op = Path(sys.argv[3])
    tbl = Path(sys.argv[4])

    if mode not in ('d', 'e'):
        usage()

    table = load_table(tbl)

    char_to_index = {}
    for idx, ch in table.items():
        char_to_index.setdefault(ch, idx)

    fallback_idx = char_to_index.get('？')
    if fallback_idx is None:
        fallback_idx = char_to_index.get('?')
    if fallback_idx is None:
        fallback_idx = 218

    files = sorted(ip.glob('*.bin' if mode == 'd' else '*.asm'))
    if not files:
        raise SystemExit('no input files')

    op.mkdir(parents=True, exist_ok=True)
    for f in files:
        out = op / (f.stem + ('.asm' if mode == 'd' else '.bin'))
        if mode == 'd':
            cmds = ScriptReader(f.read_bytes(), table).parse_all()
            if not cmds:
                continue
            out.write_text(format_asm(cmds), encoding='utf-8')
        else:
            out.write_bytes(assemble_commands(f.read_text(encoding='utf-8').splitlines(),  char_to_index, fallback_idx))
    if mode == 'e' and MISSING:
        print(MISSING)