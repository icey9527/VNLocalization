# tool.py
import re
import sys
import struct
import argparse
from pathlib import Path
from typing import Dict, Tuple, List, Optional
from dataclasses import dataclass
from enum import Enum
from array import array


class ParamType(Enum):
    NONE = 0
    SINGLE = 1
    DOUBLE = 2
    TRIPLE = 3
    QUAD = 4
    VARIABLE = 5


@dataclass
class Command:
    name: str
    param_type: ParamType
    param_format: str = ''

    @property
    def param_size(self) -> int:
        return struct.calcsize(self.param_format) if self.param_format else 0

    @property
    def param_count(self) -> int:
        return self.param_size // 2


class TextCodec:
    COMMAND_THRESHOLD = 0xE000

    # 常量：特殊布局命令
    OP_FF55 = 0xFF55
    OP_FF79 = 0xFF79
    OP_FF7A = 0xFF7A
    OP_FF8A = 0xFF8A
    OP_FFA9 = 0xFFA9  # -0x57：4字节参数，分散在4个short的低字节
    OP_FFB1 = 0xFFB1  # -0x4F：1字节+1字节+1个short
    OP_FFF0 = 0xFFF0  # 脚本调用：直到0xFFFF终止

    COMMANDS: Dict[int, Command] = {
        # 无参
        0xFF8B: Command('FF8B', ParamType.NONE),
        0xFF8F: Command('FF8F', ParamType.NONE),
        0xFF8E: Command('FF8E', ParamType.NONE),
        0xFF8D: Command('FF8D', ParamType.NONE),
        0xFF8C: Command('FF8C', ParamType.NONE),
        0xFFE2: Command('FFE2', ParamType.NONE),
        0xFFE3: Command('FFE3', ParamType.NONE),
        0xFFE4: Command('FFE4', ParamType.NONE),
        0xFFDC: Command('FFDC', ParamType.NONE),
        0xFFDD: Command('FFDD', ParamType.NONE),
        0xFFDE: Command('FFDE', ParamType.NONE),
        0xFFDF: Command('FFDF', ParamType.NONE),
        0xFFE1: Command('FFE1', ParamType.NONE),
        0xFFE8: Command('FFE8', ParamType.NONE),
        0xFFEA: Command('FFEA', ParamType.NONE),
        0xFFEB: Command('FFEB', ParamType.NONE),
        0xFFED: Command('FFED', ParamType.NONE),
        0xFFEE: Command('FFEE', ParamType.NONE),
        0xFFFC: Command('FFFC', ParamType.NONE),
        0xFFFB: Command('FFFB', ParamType.NONE),
        0xFFFD: Command('FFFD', ParamType.NONE),
        0xFFFE: Command('FFFE', ParamType.NONE),
        0xFFFF: Command('FFFF', ParamType.NONE),
        0xFFF3: Command('FFF3', ParamType.NONE),
        0xFFF1: Command('FFF1', ParamType.NONE),
        0xFFF2: Command('FFF2', ParamType.NONE),
        0xFFBB: Command('FFBB', ParamType.NONE),
        0xFFA6: Command('FFA6', ParamType.NONE),
        0xFFB0: Command('FFB0', ParamType.NONE),
        0xFFB2: Command('FFB2', ParamType.NONE),
        0xFFB4: Command('FFB4', ParamType.NONE),
        0xFFB6: Command('FFB6', ParamType.NONE),
        0xFFB8: Command('FFB8', ParamType.NONE),
        0xFF88: Command('FF88', ParamType.NONE),
        0xFF89: Command('FF89', ParamType.NONE),
        0xFF83: Command('FF83', ParamType.NONE),
        0xFF82: Command('FF82', ParamType.NONE),

        # 单参（含修正：FF84 单参）
        0xFF62: Command('FF62', ParamType.SINGLE, '<H'),
        0xFF63: Command('FF63', ParamType.SINGLE, '<H'),
        0xFF64: Command('FF64', ParamType.SINGLE, '<H'),
        0xFF65: Command('FF65', ParamType.SINGLE, '<H'),
        0xFF66: Command('FF66', ParamType.SINGLE, '<H'),
        0xFF67: Command('FF67', ParamType.SINGLE, '<H'),
        0xFF6E: Command('FF6E', ParamType.SINGLE, '<H'),
        0xFF6F: Command('FF6F', ParamType.SINGLE, '<H'),
        0xFF70: Command('FF70', ParamType.SINGLE, '<H'),
        0xFF71: Command('FF71', ParamType.SINGLE, '<H'),
        0xFF72: Command('FF72', ParamType.SINGLE, '<H'),
        0xFF73: Command('FF73', ParamType.SINGLE, '<H'),
        0xFF74: Command('FF74', ParamType.SINGLE, '<H'),
        0xFF7F: Command('FF7F', ParamType.SINGLE, '<H'),
        0xFF87: Command('FF87', ParamType.SINGLE, '<H'),
        0xFF86: Command('FF86', ParamType.SINGLE, '<H'),
        0xFFC7: Command('FFC7', ParamType.SINGLE, '<H'),
        0xFFC3: Command('FFC3', ParamType.SINGLE, '<H'),
        0xFFC4: Command('FFC4', ParamType.SINGLE, '<H'),
        0xFFC5: Command('FFC5', ParamType.SINGLE, '<H'),
        0xFFC6: Command('FFC6', ParamType.SINGLE, '<H'),
        0xFFE9: Command('FFE9', ParamType.SINGLE, '<H'),
        0xFFEC: Command('FFEC', ParamType.SINGLE, '<H'),
        0xFFEF: Command('FFEF', ParamType.SINGLE, '<H'),
        0xFFF4: Command('FFF4', ParamType.SINGLE, '<H'),
        0xFFF5: Command('FFF5', ParamType.SINGLE, '<H'),
        0xFFF6: Command('FFF6', ParamType.SINGLE, '<H'),
        0xFFF7: Command('FFF7', ParamType.SINGLE, '<H'),
        0xFFF8: Command('FFF8', ParamType.SINGLE, '<H'),
        0xFFF9: Command('FFF9', ParamType.SINGLE, '<H'),
        0xFFB3: Command('FFB3', ParamType.SINGLE, '<H'),
        0xFFB5: Command('FFB5', ParamType.SINGLE, '<H'),
        0xFFB7: Command('FFB7', ParamType.SINGLE, '<H'),
        0xFFE5: Command('FFE5', ParamType.SINGLE, '<H'),
        0xFF84: Command('FF84', ParamType.SINGLE, '<H'),

        # 双参
        0xFF5E: Command('FF5E', ParamType.DOUBLE, '<HH'),
        0xFF5F: Command('FF5F', ParamType.DOUBLE, '<HH'),
        0xFF7B: Command('FF7B', ParamType.DOUBLE, '<HH'),
        0xFF7C: Command('FF7C', ParamType.DOUBLE, '<HH'),
        0xFF7D: Command('FF7D', ParamType.DOUBLE, '<HH'),
        0xFF7E: Command('FF7E', ParamType.DOUBLE, '<HH'),
        0xFF9C: Command('FF9C', ParamType.DOUBLE, '<HH'),
        0xFF9D: Command('FF9D', ParamType.DOUBLE, '<HH'),
        0xFFAA: Command('FFAA', ParamType.DOUBLE, '<HH'),
        0xFFAC: Command('FFAC', ParamType.DOUBLE, '<HH'),
        0xFFAD: Command('FFAD', ParamType.DOUBLE, '<HH'),
        0xFFAE: Command('FFAE', ParamType.DOUBLE, '<HH'),
        0xFFAF: Command('FFAF', ParamType.DOUBLE, '<HH'),
        0xFFBA: Command('FFBA', ParamType.DOUBLE, '<HH'),
        0xFFBC: Command('FFBC', ParamType.DOUBLE, '<HH'),
        0xFFBD: Command('FFBD', ParamType.DOUBLE, '<HH'),
        0xFFBE: Command('FFBE', ParamType.DOUBLE, '<HH'),
        0xFFBF: Command('FFBF', ParamType.DOUBLE, '<HH'),
        0xFFC1: Command('FFC1', ParamType.DOUBLE, '<HH'),
        0xFFC2: Command('FFC2', ParamType.DOUBLE, '<HH'),
        0xFFFA: Command('FFFA', ParamType.DOUBLE, '<HH'),
        0xFF85: Command('FF85', ParamType.DOUBLE, '<HH'),

        # 三参
        0xFFC0: Command('FFC0', ParamType.TRIPLE, '<HHH'),
        0xFFC8: Command('FFC8', ParamType.TRIPLE, '<HHH'),
        0xFFA7: Command('FFA7', ParamType.TRIPLE, '<HHH'),
        0xFFAB: Command('FFAB', ParamType.TRIPLE, '<HHH'),

        # 四参
        0xFFB9: Command('FFB9', ParamType.QUAD, '<HHHH'),

        # 变长
        0xFF55: Command('FF55', ParamType.VARIABLE),
        0xFF79: Command('FF79', ParamType.VARIABLE),
        0xFF7A: Command('FF7A', ParamType.VARIABLE),
        0xFF8A: Command('FF8A', ParamType.VARIABLE),
        0xFFF0: Command('FFF0', ParamType.VARIABLE),
    }

    def __init__(self, table_path: str):
        self.code_to_char: Dict[int, str] = self._load_code_table(table_path)
        self._build_reverse_and_trie()

    @staticmethod
    def _load_code_table(table_path: str) -> Dict[int, str]:
        code_table: Dict[int, str] = {}
        with open(table_path, 'r', encoding='utf-16') as f:
            for line in f:
                line = line.rstrip('\n\r')
                if not line or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                try:
                    code = int(k)
                except ValueError:
                    continue
                code_table[code] = v
        return code_table

    # ===== 编码用Trie =====
    def _build_reverse_and_trie(self):
        self.char_to_code: Dict[str, int] = {}
        for k, v in self.code_to_char.items():
            self.char_to_code[v] = k
        self.trie: Dict = {}
        self._TRIE_TERM = '_code'
        self._max_token_len = 0
        for text, code in self.char_to_code.items():
            node = self.trie
            self._max_token_len = max(self._max_token_len, len(text))
            for ch in text:
                node = node.setdefault(ch, {})
            node[self._TRIE_TERM] = code

    def _trie_match_longest(self, s: str, pos: int) -> Tuple[Optional[int], int]:
        node = self.trie
        matched_code = None
        matched_len = 0
        i = pos
        while i < len(s):
            ch = s[i]
            if ch not in node:
                break
            node = node[ch]
            i += 1
            if self._TRIE_TERM in node:
                matched_code = node[self._TRIE_TERM]
                matched_len = i - pos
        return matched_code, matched_len

    # ===== 解码 =====
    def _is_command(self, value: int) -> bool:
        return value > self.COMMAND_THRESHOLD

    def _scan_until_next_cmd(self, words: array, start: int, max_items: int = 64) -> Tuple[List[int], int]:
        n = len(words)
        out: List[int] = []
        i = start
        while i < n and len(out) < max_items:
            w = words[i]
            if self._is_command(w):
                break
            out.append(w)
            i += 1
        return out, (i - start)

    def decode_file(self, bin_path: Path) -> List[str]:
        data = bin_path.read_bytes()
        words = array('H')
        words.frombytes(data)
        if sys.byteorder != 'little':
            words.byteswap()

        n = len(words)
        i = 0
        out_lines: List[str] = []
        text_buf: List[str] = []
        code_to_char = self.code_to_char
        COMMANDS = self.COMMANDS

        def flush_text():
            if text_buf:
                out_lines.append(''.join(text_buf))
                text_buf.clear()

        while i < n:
            w = words[i]
            if not self._is_command(w):
                ch = code_to_char.get(w)
                text_buf.append(f"[{w:04X}]" if ch is None else ch)
                i += 1
                continue

            flush_text()
            cmd_val = w
            i += 1
            cmd = COMMANDS.get(cmd_val)

            # FFFF 文本块：仅识别两种头 0000/0004
            if cmd_val == 0xFFFF:
                header_parts: List[str] = []
                if i < n and not self._is_command(words[i]):
                    head = words[i]
                    if head == 0x0000:
                        i += 1
                        if i < n and not self._is_command(words[i]):
                            header_parts = ["0000", f"{words[i]:04X}"]
                            i += 1
                        else:
                            header_parts = ["0000", "[INCOMPLETE]"]
                    elif head == 0x0004:
                        i += 1
                        # 0004 需要两个参数
                        p1 = p2 = None
                        if i < n and not self._is_command(words[i]):
                            p1 = f"{words[i]:04X}"; i += 1
                        if i < n and not self._is_command(words[i]):
                            p2 = f"{words[i]:04X}"; i += 1
                        header_parts = ["0004", p1 if p1 else "[INCOMPLETE]", p2 if p2 else "[INCOMPLETE]"]

                out_lines.append(f"<FFFF {' '.join(header_parts)}>" if header_parts else "<FFFF>")


                # 收集正文（直到下一个 FFFF/命令；不消耗那个分隔符）
                line_chars: List[str] = []
                pos = i
                while pos < n:
                    v = words[pos]
                    if v == 0xFFFF or self._is_command(v):
                        break
                    line_chars.append(code_to_char.get(v, f"[{v:04X}]"))
                    pos += 1
                if line_chars:
                    out_lines.append(''.join(line_chars))
                i = pos
                continue

            # 特殊布局：FFA9
            if cmd_val == self.OP_FFA9:
                if i + 4 <= n:
                    b1 = words[i + 0] & 0x00FF
                    b2 = words[i + 1] & 0x00FF
                    b3 = words[i + 2] & 0x00FF
                    b4 = words[i + 3] & 0x00FF
                    out_lines.append(f"<FFA9 {b1:02X} {b2:02X} {b3:02X} {b4:02X}>")
                    i += 4
                else:
                    out_lines.append("<FFA9 [INCOMPLETE]>")
                continue

            # 特殊布局：FFB1
            if cmd_val == self.OP_FFB1:
                if i + 3 <= n:
                    b1 = words[i + 0] & 0x00FF
                    b2 = words[i + 1] & 0x00FF
                    w3 = words[i + 2]
                    out_lines.append(f"<FFB1 {b1:02X} {b2:02X} {w3:04X}>")
                    i += 3
                else:
                    out_lines.append("<FFB1 [INCOMPLETE]>")
                continue

            # 变长：FFF0（直到 0xFFFF）
            if cmd_val == self.OP_FFF0:
                params: List[str] = []
                if i < n:
                    params.append(f"{words[i]:04X}")
                    i += 1
                while i < n:
                    p = words[i]
                    i += 1
                    if p == 0xFFFF:
                        break
                    params.append(f"{p:04X}")
                out_lines.append(f"<FFF0 {' '.join(params)}>")
                continue

            # 严格解析：FF79/FF7A（target + ids... + 0xFFFF）
            if cmd_val in (self.OP_FF79, self.OP_FF7A):
                params: List[str] = []
                if i >= n:
                    out_lines.append(f"<{COMMANDS[cmd_val].name} [INCOMPLETE]>")
                    continue
                tgt = words[i]; i += 1
                params.append(f"{tgt:04X}")
                while i < n:
                    v = words[i]; i += 1
                    if v == 0xFFFF:
                        break
                    params.append(f"{v:04X}")
                out_lines.append(f"<{COMMANDS[cmd_val].name} {' '.join(params)}>")
                continue

            # 严格解析：FF55（var0 a0 b0 [idx var a b]* FFFF label）
            if cmd_val == self.OP_FF55:
                parts: List[str] = []
                if i + 3 > n:
                    out_lines.append("<FF55 [INCOMPLETE]>")
                    i = n
                    continue
                var0 = words[i]; a0 = words[i + 1]; b0 = words[i + 2]
                i += 3
                parts.extend([f"{var0:04X}", f"{a0:04X}", f"{b0:04X}"])
                while i < n:
                    idx = words[i]; i += 1
                    if idx == 0xFFFF:
                        if i < n:
                            label = words[i]; i += 1
                            parts.extend(["FFFF", f"{label:04X}"])
                        else:
                            parts.append("FFFF")
                            out_lines.append(f"<FF55 {' '.join(parts)} [INCOMPLETE]>")
                        break
                    if i + 3 > n:
                        parts.append(f"{idx:04X}")
                        out_lines.append(f"<FF55 {' '.join(parts)} [INCOMPLETE]>")
                        i = n
                        break
                    varx = words[i]; ax = words[i + 1]; bx = words[i + 2]; i += 3
                    parts.extend([f"{idx:04X}", f"{varx:04X}", f"{ax:04X}", f"{bx:04X}"])
                else:
                    out_lines.append(f"<FF55 {' '.join(parts)} [INCOMPLETE]>")
                    continue
                if parts and parts[-2] == "FFFF":
                    out_lines.append(f"<FF55 {' '.join(parts)}>")
                continue

            # 变长：FF8A（暂仍读到下一个命令为止）
            if cmd_val == self.OP_FF8A:
                table, used = self._scan_until_next_cmd(words, i, max_items=64)
                i += used
                out_lines.append(f"<FF8A {' '.join(f'{x:04X}' for x in table)}>")
                continue

            # 未知
            if cmd is None:
                out_lines.append(f"<UNKNOWN {cmd_val:04X}>")
                continue

            # 固定参数命令
            need = cmd.param_count
            if need == 0:
                out_lines.append(f"<{cmd.name}>")
                continue
            if i + need > n:
                out_lines.append(f"<{cmd.name} [INCOMPLETE]>")
                i = n
                continue
            params = words[i:i + need]
            i += need
            out_lines.append(f"<{cmd.name} {' '.join(f'{p:04X}' for p in params)}>")

        if text_buf:
            out_lines.append(''.join(text_buf))

        return out_lines

    # ===== 编译（txt -> bin）=====
    _CMD_LINE_RE = re.compile(r'^\s*<\s*([^>\s]+)(.*?)>\s*$')

    @staticmethod
    def _parse_hex_word(tok: str) -> int:
        tok = tok.strip()
        if tok.lower().startswith('0x'):
            return int(tok, 16)
        try:
            return int(tok, 16)
        except ValueError:
            return int(tok, 10)

    def _parse_command_line(self, line: str) -> Tuple[int, List[int]]:
        m = self._CMD_LINE_RE.match(line)
        if not m:
            raise ValueError(f"不是有效命令行: {line}")
        head = m.group(1).strip().upper()
        rest = m.group(2).strip()
        parts = [p for p in rest.split() if p]

        if head == 'UNKNOWN':
            if not parts:
                raise ValueError(f"UNKNOWN 缺少命令码: {line}")
            cmd_val = self._parse_hex_word(parts[0])
            params = [self._parse_hex_word(t) for t in parts[1:]]
            return cmd_val, params

        cmd_val = self._parse_hex_word(head)
        params = [self._parse_hex_word(t) for t in parts]
        return cmd_val, params

    def encode_text_line_to_words(self, line: str, strict: bool = True) -> List[int]:
        words: List[int] = []
        i = 0
        n = len(line)
        while i < n:
            ch = line[i]
            if ch == '[':
                j = line.find(']', i + 1)
                if j != -1:
                    token = line[i + 1:j]
                    try:
                        w = self._parse_hex_word(token)
                        if not (0 <= w <= 0xFFFF):
                            raise ValueError
                        words.append(w)
                        i = j + 1
                        continue
                    except Exception:
                        pass
            code, span = self._trie_match_longest(line, i)
            if code is not None and span > 0:
                words.append(code)
                i += span
            else:
                # 遇到无法编码的字符，直接用码表中的问号替换，不抛异常、不退出
                frag = line[i]
                print(f"提示：无法编码字符 '{frag}' (Unicode: U+{ord(frag):04X})，已替换为 '?'")
                # 直接获取问号的编码（假设码表中一定存在）
                words.append(self.char_to_code['？'])  # 这里直接用[]取值，省去判断
                i += 1
        return words

    def encode_command_line_to_words(self, line: str, strict: bool = True) -> List[int]:
        cmd_val, params = self._parse_command_line(line)
        words_out: List[int] = [cmd_val]
        cmd = self.COMMANDS.get(cmd_val)

        # 严格的 FFFF：仅支持 <FFFF>、<FFFF 0000 ID>、<FFFF 0004 P1 P2>
        if cmd_val == 0xFFFF:
            if len(params) == 0:
                return words_out
            if len(params) == 2 and (params[0] & 0xFFFF) == 0x0000:
                words_out.extend([params[0] & 0xFFFF, params[1] & 0xFFFF])
                return words_out
            if len(params) == 3 and (params[0] & 0xFFFF) == 0x0004:
                words_out.extend([params[0] & 0xFFFF, params[1] & 0xFFFF, params[2] & 0xFFFF])
                return words_out
            if strict:
                raise ValueError("FFFF 仅支持三种写法：<FFFF>、<FFFF 0000 ID>、<FFFF 0004 P1 P2>")
            # 非严格：尽量写入前3个
            words_out.extend([p & 0xFFFF for p in params[:3]])
            return words_out

        # 特殊布局 FFA9
        if cmd_val == self.OP_FFA9:
            if strict and len(params) != 4:
                raise ValueError("FFA9 需要 4 个字节参数")
            b = [(p & 0xFF) for p in (params + [0, 0, 0, 0])[:4]]
            words_out.extend([b[0], b[1], b[2], b[3]])
            return words_out

        # 特殊布局 FFB1
        if cmd_val == self.OP_FFB1:
            if strict and len(params) != 3:
                raise ValueError("FFB1 需要 3 个参数（B B H）")
            b1 = (params[0] & 0xFF) if len(params) > 0 else 0
            b2 = (params[1] & 0xFF) if len(params) > 1 else 0
            w3 = (params[2] & 0xFFFF) if len(params) > 2 else 0
            words_out.extend([b1, b2, w3])
            return words_out

        # 严格变长：FFF0、FF79、FF7A、FF55、FF8A
        if cmd_val in (self.OP_FFF0, self.OP_FF79, self.OP_FF7A, self.OP_FF55, self.OP_FF8A):
            if cmd_val == self.OP_FFF0:
                if strict and len(params) < 1:
                    raise ValueError("FFF0 至少需要 script_id")
                if not params:
                    params = [0]
                words_out.extend([p & 0xFFFF for p in params])
                words_out.append(0xFFFF)
                return words_out

            if cmd_val in (self.OP_FF79, self.OP_FF7A):
                if strict and len(params) < 1:
                    raise ValueError(f"{self.COMMANDS[cmd_val].name} 至少需要 target")
                words_out.extend([p & 0xFFFF for p in params])
                if not params or params[-1] != 0xFFFF:
                    words_out.append(0xFFFF)
                return words_out

            if cmd_val == self.OP_FF55:
                if strict and len(params) < 5:
                    raise ValueError("FF55 至少需要 var0 a0 b0 FFFF label（或包含若干四元组后再 FFFF label）")
                if len(params) < 3:
                    raise ValueError("FF55 缺少 var0/a0/b0")
                v0, a0, b0 = params[0] & 0xFFFF, params[1] & 0xFFFF, params[2] & 0xFFFF
                words_out.extend([v0, a0, b0])

                pos = 3
                label_found = False
                while pos < len(params):
                    x = params[pos] & 0xFFFF
                    pos += 1
                    if x == 0xFFFF:
                        if pos >= len(params):
                            if strict:
                                raise ValueError("FF55 缺少 label")
                            words_out.append(0xFFFF)
                            return words_out
                        label = params[pos] & 0xFFFF
                        pos += 1
                        words_out.extend([0xFFFF, label])
                        label_found = True
                        break
                    if pos + 2 >= len(params):
                        if strict:
                            raise ValueError("FF55 四元组参数不完整，应为 idx var a b")
                        remain = params[pos:pos+3]
                        for r in remain:
                            words_out.append(r & 0xFFFF)
                        words_out.append(0xFFFF)
                        return words_out
                    varx = params[pos] & 0xFFFF
                    ax = params[pos + 1] & 0xFFFF
                    bx = params[pos + 2] & 0xFFFF
                    pos += 3
                    words_out.extend([x, varx, ax, bx])

                if not label_found:
                    if strict:
                        raise ValueError("FF55 未找到 FFFF label 终止")
                    words_out.append(0xFFFF)
                return words_out

            if cmd_val == self.OP_FF8A:
                words_out.extend([p & 0xFFFF for p in params])
                return words_out

        # 未知命令：按半字写回
        if cmd is None:
            words_out.extend([p & 0xFFFF for p in params])
            return words_out

        # 固定参数命令
        if cmd.param_type == ParamType.NONE:
            if strict and len(params) != 0:
                raise ValueError(f"{cmd.name} 不需要参数，但实际提供 {len(params)} 个")
            return words_out

        if cmd.param_type in (ParamType.SINGLE, ParamType.DOUBLE, ParamType.TRIPLE, ParamType.QUAD):
            need = cmd.param_count
            if strict and len(params) != need:
                raise ValueError(f"{cmd.name} 需要 {need} 个参数，但实际 {len(params)}")
            params_fixed = (params + [0] * need)[:need]
            words_out.extend([p & 0xFFFF for p in params_fixed])
            return words_out

        words_out.extend([p & 0xFFFF for p in params])
        return words_out

    def encode_file(self, txt_path: Path, strict: bool = True) -> bytes:
        words_all: List[int] = []
        with open(txt_path, 'r', encoding='utf-8') as f:
            for raw in f:
                # 注意：我们不 strip 文本中的空格，只去掉换行符
                line = raw.rstrip('\n\r')
                stripped = line.strip()
                if stripped.startswith('<') and stripped.endswith('>'):
                    words_all.extend(self.encode_command_line_to_words(stripped, strict=strict))
                else:
                    words_all.extend(self.encode_text_line_to_words(line, strict=strict))
        arr = array('H', words_all)
        if sys.byteorder != 'little':
            arr.byteswap()
        return arr.tobytes()
    
    def generate_table_from_texts(self, txt_paths: List[Path]) -> Dict[int, str]:
        """从文本文件中提取所有唯一字符，生成码表"""
        chars = set()
        for txt_path in txt_paths:
            with open(txt_path, 'r', encoding='utf-8') as f:
                for raw in f:
                    line = raw.rstrip('\n\r')
                    stripped = line.strip()
                    # 跳过命令行
                    if stripped.startswith('<') and stripped.endswith('>'):
                        continue
                    # 收集字符（跳过[XXXX]格式）
                    i = 0
                    while i < len(line):
                        ch = line[i]
                        if ch == '[':
                            j = line.find(']', i + 1)
                            if j != -1:
                                i = j + 1
                                continue
                        chars.add(ch)
                        i += 1
        
        # 生成码表（从0x0000开始，跳过命令区域0xE000以上）
        code_table = {}
        code = 0
        for char in sorted(chars):
            while code >= self.COMMAND_THRESHOLD:
                code += 1
            code_table[code] = char
            code += 1
        return code_table

    def save_code_table(self, table_path: str, code_table: Dict[int, str]):
        """保存码表到文件"""
        with open(table_path, 'w', encoding='utf-16') as f:
            for code in sorted(code_table.keys()):
                f.write(f"{code}={code_table[code]}\n")    


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def decode_entry(input_path: Path, output_path: Path, table: Path):
    codec = TextCodec(str(table))

    def do_one(bin_path: Path, out_dir: Path):
        lines = codec.decode_file(bin_path)
        out_txt = out_dir / (bin_path.stem + '.txt')
        with open(out_txt, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        print(f"✓ {bin_path.name}")

    if input_path.is_file():
        ensure_dir(output_path)
        do_one(input_path, output_path)
        return

    ensure_dir(output_path)
    bins = sorted([p for p in input_path.glob('*.bin')])
    ok = 0
    for p in bins:
        try:
            do_one(p, output_path)
            ok += 1
        except Exception as e:
            print(f"✗ {p.name}: {e}")
    print(f"\n完成！成功处理 {ok}/{len(bins)} 个文件")


def encode_entry(input_path: Path, output_path: Path, table: Path, strict: bool = True, generate_table: bool = False, output_table: Path = None):
    # 收集txt文件列表
    if input_path.is_file():
        txt_files = [input_path]
    else:
        txt_files = sorted([p for p in input_path.glob('*.txt')])
    
    # 如果需要生成码表
    if generate_table:
        if not output_table:
            output_table = Path('generated.tbl')
        print(f"正在从 {len(txt_files)} 个文件生成码表...")
        temp_codec = TextCodec.__new__(TextCodec)
        temp_codec.COMMAND_THRESHOLD = TextCodec.COMMAND_THRESHOLD
        new_table = temp_codec.generate_table_from_texts(txt_files)
        temp_codec.save_code_table(str(output_table), new_table)
        print(f"✓ 码表已生成: {output_table}\n")
        codec = TextCodec(str(output_table))
    else:
        codec = TextCodec(str(table))
    
    def do_one(txt_path: Path, out_dir: Path):
        data = codec.encode_file(txt_path, strict=strict)
        out_bin = out_dir / (txt_path.stem + '.bin')
        out_bin.write_bytes(data)
        print(f"✓ {txt_path.name}")

    ensure_dir(output_path)
    if input_path.is_file():
        do_one(input_path, output_path)
        return

    ok = 0
    for p in txt_files:
        try:
            do_one(p, output_path)
            ok += 1
        except Exception as e:
            print(f"✗ {p.name}: {e}")
    print(f"\n完成！成功处理 {ok}/{len(txt_files)} 个文件")


def main():
    parser = argparse.ArgumentParser(description="Binary Text Decoder/Encoder")
    sub = parser.add_subparsers(dest='cmd', required=True)

    p_dec = sub.add_parser('decode', help='解码 bin -> txt')
    p_dec.add_argument('-i', '--input', required=True, help='输入目录或文件（.bin）')
    p_dec.add_argument('-o', '--output', required=True, help='输出目录')
    p_dec.add_argument('-t', '--table', default='FA_JIS.tbl', help='码表路径（默认 FA_JIS.tbl）')

    p_enc = sub.add_parser('encode', help='编译 txt -> bin')
    p_enc.add_argument('-i', '--input', required=True, help='输入目录或文件（.txt）')
    p_enc.add_argument('-o', '--output', required=True, help='输出目录')
    p_enc.add_argument('-t', '--table', default='FA_JIS.tbl', help='码表路径（默认 FA_JIS.tbl）')
    p_enc.add_argument('--no-strict', action='store_true', help='非严格模式：无法匹配的字符以?或跳过')
    p_enc.add_argument('--generate-table', action='store_true', help='自动生成码表（而非使用现有码表）')
    p_enc.add_argument('--output-table', help='生成码表的保存路径（默认 generated.tbl）')

    args = parser.parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    table_path = Path(args.table)

    if args.cmd == 'decode':
        decode_entry(input_path, output_path, table_path)
    elif args.cmd == 'encode':
        encode_entry(
            input_path, 
            output_path, 
            table_path, 
            strict=(not args.no_strict),
            generate_table=args.generate_table,
            output_table=Path(args.output_table) if args.output_table else None
        )


if __name__ == '__main__':
    main()