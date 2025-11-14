#!/usr/bin/env python3
import sys
import struct
import argparse
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# ----------------------------
# 码表加载与文本编码/解码工具
# ----------------------------

def load_table(table_file: Path) -> Dict[int, bytes]:
    """
    加载码表: 行格式 "index = HEXBYTES"
    例如: 123 = 8140
    文件编码: utf-16
    返回: {index(int): sjis_bytes(bytes)}
    """
    table: Dict[int, bytes] = {}
    with open(table_file, 'r', encoding='utf-16') as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line or '=' not in line:
                continue
            left, right = line.split('=', 1)
            try:
                index = int(left.strip())
                sjis_hex = right.strip().replace(' ', '')
                table[index] = bytes.fromhex(sjis_hex)
            except Exception as e:
                raise ValueError(f"码表第{lineno}行格式错误: {line} ({e})")
    if not table:
        raise ValueError("码表为空或加载失败")
    return table


class SjisTrie:
    """
    用码表构建SJIS字节前缀Trie，便于把字符串(cp932字节)最长匹配映射回索引。
    """
    __slots__ = ('root',)
    def __init__(self, reverse_map: Dict[bytes, int]):
        self.root = {}
        for sjis_bytes, idx in reverse_map.items():
            node = self.root
            for b in sjis_bytes:
                node = node.setdefault(b, {})
            node['_code'] = idx

    def match_longest(self, data: bytes, start: int) -> Optional[Tuple[int, int]]:
        """
        从 data[start:] 开始最长匹配，返回 (index, length) 或 None
        """
        node = self.root
        best = None
        pos = start
        while pos < len(data) and data[pos] in node:
            node = node[data[pos]]
            pos += 1
            if '_code' in node:
                best = (node['_code'], pos - start)
        return best


PLACEHOLDER_TO_CODE = {
    "[娘の名前]": 0xFFFF,
    "[娘の名字]": 0xFFFE,
    "[汎用文字列]": 0xFFFD,
    "[汎用数値]": 0xFFFC,
}
# 捕获占位符或 [CODE:0x1234]
RE_TOKEN = re.compile(r'(\[(?:娘の名前|娘の名字|汎用文字列|汎用数値|CODE:0x[0-9A-Fa-f]{1,4})\])')

def split_text_tokens(s: str) -> List[str]:
    """
    把文本拆成普通片段与占位符片段（占位符保留为独立项）
    """
    if not s:
        return []
    parts = RE_TOKEN.split(s)
    return [p for p in parts if p]

def encode_text_to_indices(s: str, reverse_map: Dict[bytes, int], trie: SjisTrie) -> List[int]:
    """
    把字符串（包含占位符）编码为索引序列。
    使用 cp936 编码并按码表Trie最长匹配。
    """
    indices: List[int] = []
    tokens = split_text_tokens(s)
    for t in tokens:
        if t in PLACEHOLDER_TO_CODE:
            indices.append(PLACEHOLDER_TO_CODE[t])
            continue
        if t.startswith("[CODE:0x") and t.endswith("]"):
            try:
                val = int(t[6:-1].split(':')[1], 16)
                indices.append(val & 0xFFFF)
            except Exception:
                raise ValueError(f"非法占位符: {t}")
            continue
        
        # 普通片段：cp936 -> 索引流，使用replace处理不支持的字符
        try:
            raw = t.encode('cp936', errors='strict')
        except UnicodeEncodeError as e:
            print(f"警告: 文本 '{t}' 包含GBK不支持的字符，使用问号替换")
            # 找到不支持的字符并替换
            cleaned_text = ""
            for char in t:
                try:
                    char.encode('cp936')
                    cleaned_text += char
                except UnicodeEncodeError:
                    print(f"  不支持字符: '{char}' (U+{ord(char):04X})，替换为问号")
                    cleaned_text += "?"
            raw = cleaned_text.encode('cp936', errors='strict')
        
        i = 0
        while i < len(raw):
            m = trie.match_longest(raw, i)
            if not m:
                # 码表中不存在的字符，替换为问号
                snippet = raw[i:i+2].hex()
                try:
                    problem_char = raw[i:i+2].decode('cp936')
                    print(f"警告: 码表中不存在字符 '{problem_char}' (字节: {snippet})，替换为问号")
                except:
                    print(f"警告: 码表中不存在字节序列 {snippet}，替换为问号")
                
                # 使用问号字符的索引
                question_mark_bytes = '?'.encode('cp936')
                m_question = trie.match_longest(question_mark_bytes, 0)
                if m_question:
                    code, used = m_question
                    indices.append(code)
                    print(f"  已替换为问号 (索引: 0x{code:04X})")
                else:
                    # 如果问号也不在码表中，使用默认索引 219
                    print(f"  警告: 问号字符也不在码表中，使用默认索引 219")
                    indices.append(219)
                
                i += 2  # GBK字符通常是2字节
                continue
                
            code, used = m
            indices.append(code)
            i += used
    return indices

def decode_indices_to_text(indices: List[int], table: Dict[int, bytes]) -> str:
    """
    把索引序列解码为可读字符串（cp932），占位符映射回标签。
    """
    out: List[str] = []
    sjis_buf = bytearray()
    def flush():
        nonlocal sjis_buf, out
        if sjis_buf:
            try:
                out.append(sjis_buf.decode('cp932'))
            except Exception:
                out.append(f"[RAW:{sjis_buf.hex()}]")
            sjis_buf = bytearray()

    for code in indices:
        if code in PLACEHOLDER_TO_CODE.values():
            flush()
            # 反向映射回占位符字符串
            for k, v in PLACEHOLDER_TO_CODE.items():
                if v == code:
                    out.append(k)
                    break
        else:
            if code in table:
                sjis_buf.extend(table[code])
            else:
                flush()
                out.append(f"[CODE:0x{code:04X}]")
    flush()
    return ''.join(out)

def quote_string(s: str) -> str:
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'

def unquote_string(token: str) -> str:
    if len(token) >= 2 and token[0] == '"' and token[-1] == '"':
        body = token[1:-1]
        return body.replace('\\"', '"').replace('\\\\', '\\')
    raise ValueError(f"不是合法字符串字面量: {token}")

def parse_int(token: str) -> int:
    token = token.strip()
    if token.lower().startswith('0x'):
        return int(token, 16)
    return int(token, 10)

# ----------------------------
# 指令表（与引擎对齐）
# ----------------------------

# opcode -> (name, fmt)
# fmt: '' 无参；'<H' 2字节小端；'B' 1字节；None 表示专用解析（文本或可变）
COMMAND_VALUES = {
    0x00: ('LABEL', 'B'),
    0x01: ('GOTO', 'B'),
    0x02: ('FLAG', '<HB'),
    0x03: ('BG', '<H'),
    0x04: ('BG2', '<H'),              # 修正：只有一个 16 位参数
    0x05: ('CHAR', '<BH'),
    0x06: ('OFF_CHAR', 'B'),
    0x07: ('FACE', '<H'),
    0x08: ('VOICE', '<H'),
    0x09: ('MESSAGE_NAME', None),     # 文本：len(1) + len*2 索引
    0x0A: ('MESSAGE', None),          # 文本：len(1) + len*2 索引
    0x0B: ('LINE_FEED', ''),
    0x0C: ('KEY_WAIT', ''),
    0x0D: ('MESSAGE_WINDOW', 'B'),    # 1=ON, 其他=OFF
    0x0E: ('DATE_WINDOW', 'B'),       # 1=ON, 其他=OFF
    0x0F: ('OFF_FACE_WINDOW', ''),    # 无参
    0x10: ('SELECT', None),           # count + [label, len, len*2字索引]×count
    0x11: ('SE_PLAY', 'B'),
    0x12: ('SE_WAIT', ''),
    0x13: ('SE_STOP', ''),
    0x14: ('BGM_PLAY', 'B'),
    0x15: ('ROOM_BGM_PLAY', ''),
    0x16: ('BGM_STOP', '<H'),
    0x17: ('TEXT_MODE', 'B'),         # 0/窗口 1/全屏
    0x18: ('SPECIAL', 'B'),
    0x19: ('QUAKE', ''),
    0x1A: ('GOLD', ''),               # 引擎空壳，保留无参
    0x1B: ('PARAM', ''),              # 引擎空壳，保留无参
    0x1C: ('END', 'B'),               # 结束码
    0x1D: ('UNKNOWN_0x1D', ''),       # 暂无实现
    0xFF: ('NOP', ''),                # 防御：填充
}
NAME_TO_OPCODE = {v[0]: k for k, v in COMMAND_VALUES.items()}
VALID_OPCODES = set(COMMAND_VALUES.keys())

# ----------------------------
# 反汇编（bin -> asm）
# ----------------------------

class ScriptReader:
    def __init__(self, data: bytes, offset: int = 0, table: Dict[int, bytes] = None):
        self.data = data
        self.pos = offset
        self.table = table or {}

    def eof(self) -> bool:
        return self.pos >= len(self.data)

    def read_byte(self) -> int:
        if self.pos >= len(self.data):
            raise EOFError("读取超出数据")
        b = self.data[self.pos]
        self.pos += 1
        return b

    def read_struct(self, fmt: str):
        size = struct.calcsize(fmt)
        if self.pos + size > len(self.data):
            raise EOFError("读取结构越界")
        vals = struct.unpack(fmt, self.data[self.pos:self.pos+size])
        self.pos += size
        return vals

    def read_indices(self, count: int) -> List[int]:
        vals: List[int] = []
        for _ in range(count):
            (code,) = self.read_struct('<H')
            vals.append(code)
        return vals

    def parse_select(self) -> List[Tuple[int, str]]:
        count = self.read_byte()
        choices: List[Tuple[int, str]] = []
        for _ in range(count):
            label = self.read_byte()
            char_len = self.read_byte()
            indices = self.read_indices(char_len)
            text = decode_indices_to_text(indices, self.table)
            choices.append((label, text))
        return choices

    def parse_message(self) -> str:
        char_len = self.read_byte()
        indices = self.read_indices(char_len)
        return decode_indices_to_text(indices, self.table)

    def parse_all(self) -> Optional[List[dict]]:
        cmds: List[dict] = []
        while not self.eof():
            try:
                op = self.read_byte()
                spec = COMMAND_VALUES.get(op)
                if not spec:
                    return None
                name, fmt = spec
                if op in (0x09, 0x0A):
                    text = self.parse_message()
                    cmds.append({'name': name, 'text': text})
                elif op == 0x10:
                    choices = self.parse_select()
                    cmds.append({'name': name, 'choices': choices})
                else:
                    if fmt == '':
                        cmds.append({'name': name, 'params': []})
                    elif fmt is None:
                        cmds.append({'name': name, 'params': []})
                    else:
                        vals = list(self.read_struct(fmt))
                        cmds.append({'name': name, 'params': vals})
            except EOFError as e:
                return None
        return cmds

def format_asm(cmds: List[dict]) -> str:
    lines: List[str] = []
    for c in cmds:
        name = c['name']
        if name in ('MESSAGE', 'MESSAGE_NAME'):
            lines.append(f"{name} {quote_string(c.get('text', ''))}")
        elif name == 'SELECT':
            parts = [str(len(c.get('choices', [])))]
            for (label, text) in c['choices']:
                parts.append(str(label))
                parts.append(quote_string(text))
            lines.append(f"{name} " + ', '.join(parts))
        else:
            params = c.get('params', [])
            if params:
                lines.append(f"{name} " + ', '.join(str(p) for p in params))
            else:
                lines.append(f"{name}")
    return '\n'.join(lines)

# ----------------------------
# 汇编（asm -> bin）
# ----------------------------

def remove_comment(line: str) -> str:
    # 去掉 // 或 # 或 ; 注释（引号内保留）
    out = []
    in_str = False
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == '"':
            in_str = not in_str
            out.append(ch)
            i += 1
            continue
        if not in_str:
            if ch == '/' and i+1 < len(line) and line[i+1] == '/':
                break
            if ch in ('#', ';'):
                break
        out.append(ch)
        i += 1
    return ''.join(out).strip()

def split_params(s: str) -> List[str]:
    # 以逗号分隔，支持引号内逗号
    params = []
    cur = []
    in_str = False
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == '"':
            in_str = not in_str
            cur.append(ch)
        elif ch == ',' and not in_str:
            params.append(''.join(cur).strip())
            cur = []
        else:
            cur.append(ch)
        i += 1
    if cur:
        params.append(''.join(cur).strip())
    return [p for p in params if p != '']

def assemble_commands(lines: List[str],
                      reverse_map: Dict[bytes, int],
                      trie: SjisTrie) -> bytes:
    out = bytearray()
    for lineno, raw in enumerate(lines, 1):
        line = remove_comment(raw)
        if not line:
            continue
        # name + optional params
        sp = line.split(None, 1)
        name = sp[0].strip()
        if name not in NAME_TO_OPCODE:
            raise ValueError(f"第{lineno}行未知指令名: {name}")
        opcode = NAME_TO_OPCODE[name]
        spec = COMMAND_VALUES[opcode]
        fmt = spec[1]
        out.append(opcode)

        if name in ('MESSAGE', 'MESSAGE_NAME'):
            if len(sp) == 1:
                raise ValueError(f"第{lineno}行 {name} 缺少字符串参数")
            token = sp[1].strip()
            text = unquote_string(token)
            indices = encode_text_to_indices(text, reverse_map, trie)
            if len(indices) > 255:
                raise ValueError(f"第{lineno}行 {name} 文本过长(>255字)")
            out.append(len(indices))
            for code in indices:
                out += struct.pack('<H', code)

        elif name == 'SELECT':
            if len(sp) == 1:
                raise ValueError(f"第{lineno}行 SELECT 缺少参数")
            params = split_params(sp[1])
            if not params:
                raise ValueError(f"第{lineno}行 SELECT 参数为空")
            count = parse_int(params[0])
            if count < 0 or count > 255:
                raise ValueError(f"第{lineno}行 SELECT 个数非法: {count}")
            out.append(count)
            # 之后按 (label, "text") 重复
            expect = 1 + count * 2
            if len(params) != expect:
                raise ValueError(f"第{lineno}行 SELECT 参数个数不匹配，应为 {expect}，实际 {len(params)}")
            idx = 1
            for i in range(count):
                label = parse_int(params[idx]); idx += 1
                text = unquote_string(params[idx]); idx += 1
                if label < 0 or label > 255:
                    raise ValueError(f"第{lineno}行 SELECT 第{i+1}项 label 越界: {label}")
                out.append(label)
                indices = encode_text_to_indices(text, reverse_map, trie)
                if len(indices) > 255:
                    raise ValueError(f"第{lineno}行 SELECT 第{i+1}项 文本过长(>255字)")
                out.append(len(indices))
                for code in indices:
                    out += struct.pack('<H', code)

        else:
            # 普通数值参数
            if fmt == '':
                # 无参
                continue
            if len(sp) == 1:
                raise ValueError(f"第{lineno}行 {name} 缺少参数")
            params = split_params(sp[1])
            # 根据fmt参数个数校验
            if fmt == 'B':
                if len(params) != 1:
                    raise ValueError(f"第{lineno}行 {name} 需要1个参数")
                out += struct.pack('B', parse_int(params[0]) & 0xFF)
            elif fmt == '<H':
                if len(params) != 1:
                    raise ValueError(f"第{lineno}行 {name} 需要1个参数")
                out += struct.pack('<H', parse_int(params[0]) & 0xFFFF)
            elif fmt == '<HB':
                if len(params) != 2:
                    raise ValueError(f"第{lineno}行 {name} 需要2个参数")
                out += struct.pack('<H', parse_int(params[0]) & 0xFFFF)
                out += struct.pack('B', parse_int(params[1]) & 0xFF)
            elif fmt == '<BH':
                if len(params) != 2:
                    raise ValueError(f"第{lineno}行 {name} 需要2个参数")
                out += struct.pack('B', parse_int(params[0]) & 0xFF)
                out += struct.pack('<H', parse_int(params[1]) & 0xFFFF)
            else:
                raise NotImplementedError(f"未实现的格式: {fmt} (指令 {name})")
    return bytes(out)

# ----------------------------
# I/O 与主流程
# ----------------------------

def disassemble_file(bin_path: Path, out_path: Path, table: Dict[int, bytes], offset: int):
    data = bin_path.read_bytes()
    reader = ScriptReader(data, offset=offset, table=table)
    cmds = reader.parse_all()
    if cmds:
        asm_text = format_asm(cmds)
        out_path.write_text(asm_text, encoding='utf-8')

def assemble_file(asm_path: Path, out_path: Path, table: Dict[int, bytes]):
    # 构建反向映射与Trie
    reverse_map: Dict[bytes, int] = {}
    for k, v in table.items():
        reverse_map[v] = k
    trie = SjisTrie(reverse_map)

    lines = asm_path.read_text(encoding='utf-8').splitlines()
    body = assemble_commands(lines, reverse_map, trie)
    # 无文件头，直接写脚本体
    out_path.write_bytes(body)

def collect_files(input_path: Path, mode: str) -> List[Path]:
    if input_path.is_file():
        return [input_path]
    if mode == 'disasm':
        return sorted(input_path.glob('*.bin'))
    else:
        return sorted(input_path.glob('*.asm'))

def main():
    ap = argparse.ArgumentParser(description="脚本 反汇编/汇编 工具（无文件头，从offset开始）")
    ap.add_argument('--mode', choices=['disasm', 'asm'], required=True, help='disasm: bin->asm；asm: asm->bin')
    ap.add_argument('table', type=Path, help='码表文件（utf-16）')
    ap.add_argument('input', type=Path, help='输入文件或文件夹（disasm: .bin；asm: .asm）')
    ap.add_argument('output', type=Path, help='输出文件夹')
    ap.add_argument('--offset', type=int, default=0, help='反汇编起始偏移（默认0）')
    args = ap.parse_args()

    if not args.table.exists():
        print(f"错误: 码表文件不存在: {args.table}")
        sys.exit(1)
    table = load_table(args.table)

    args.output.mkdir(parents=True, exist_ok=True)
    files = collect_files(args.input, args.mode)
    if not files:
        print("未找到输入文件")
        sys.exit(1)

    if args.mode == 'disasm':
        for p in files:
            out = args.output / (p.stem + '.asm')
            disassemble_file(p, out, table, args.offset)
    else:
        for p in files:
            out = args.output / (p.stem + '.bin')
            assemble_file(p, out, table)

    print("完成。")

if __name__ == '__main__':
    main()