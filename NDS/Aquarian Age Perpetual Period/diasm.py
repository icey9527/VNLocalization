#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script Assembler/Disassembler for _DAT files
Usage:
    python script_tool.py e <input_folder> <output_folder>
    python script_tool.py w <input_folder> <output_folder>
"""

import os
import sys
import struct
from pathlib import Path
from typing import List, Tuple, Optional

CHUNK_SIZE = 0x180
TEXT_OFFSET = 0x18
TEXT_SIZE = CHUNK_SIZE - TEXT_OFFSET

# 唯一的指令定义表: opcode -> (助记符, 文本段数, [arg1启用, arg2启用, arg3启用])
OPCODES = {
    0x00: ("NOP", 0, [False, False, False]),
    0x01: ("TEXT", 1, [False, False, False]),
    0x02: ("NEXT", 0, [False, False, False]),          # 可能是换行/翻页
    0x03: ("NEXT", 0, [False, False, False]),          # 功能同上
    0x04: ("SET_VAL", 0, [True, False, False]),
    0x05: ("UNK_05", 0, [False, False, False]),
    0x06: ("WIN_OP", 0, [True, True, True]),
    0x07: ("WIN_CLOSE", 0, [True, False, False]),
    0x08: ("WIN_WAIT", 0, [True, True, False]),        # ← 改这里！等待窗口
    0x09: ("WIN_SETPARAM", 0, [True, True, True]),
    0x0A: ("UNK_0A", 0, [False, False, False]),
    0x0B: ("UNK_0B", 0, [False, False, False]),
    0x0C: ("WIN_DESTROY", 0, [True, False, False]),
    0x0D: ("WIN_CREATE", 0, [True, True, True]),
    0x0E: ("WIN_SHOW", 0, [True, False, False]),
    0x0F: ("CLEAR_SELECT", 0, [True, False, False]),  # ← 改这里！清除选择状态
    0x10: ("FADE_IN", 0, [True, False, False]),
    0x11: ("FADE_OUT", 0, [True, False, False]),
    0x12: ("FADE_FULL", 0, [True, False, False]),
    0x13: ("FADE_WAIT", 0, [False, False, False]),
    0x14: ("WAIT_COND", 0, [False, False, False]),
    0x15: ("UI_SELECT", 0, [True, False, False]),
    0x16: ("UI_SETMODE", 0, [True, True, False]),
    0x17: ("UI_CLEAR", 0, [True, False, False]),
    0x18: ("UI_SETVAL", 0, [True, False, False]),
    0x19: ("SHOW_ELEM", 0, [True, True, False]),
    0x1A: ("SHOW_ELEM_FAST", 0, [True, True, False]),
    0x1B: ("UNK_1B", 0, [False, False, False]),        # 只是PC+1
    0x1C: ("DEF_CHOICE", 1, [True, False, False]),
    0x1D: ("UNK_1D", 0, [False, False, False]),        # 只是PC+1
    0x1E: ("EXEC_CHOICE", 0, [False, False, False]),
    0x1F: ("END_CHOICE", 0, [False, False, False]),
    0x20: ("MSG_SHOW", 5, [True, True, False]),
    0x21: ("MSG_SHOW_EX", 5, [True, True, False]),
    0x22: ("UNK_22", 0, [False, False, False]),        # 只是PC+1
    0x23: ("CASE_0", 0, [False, False, False]),
    0x24: ("CASE_1", 0, [False, False, False]),
    0x25: ("CASE_2", 0, [False, False, False]),
    0x26: ("CASE_3", 0, [False, False, False]),
    0x27: ("CASE_4", 0, [False, False, False]),
    0x28: ("END_SWITCH", 0, [False, False, False]),
    0x29: ("JUMP", 0, [True, False, False]),
    0x2A: ("LABEL", 0, [True, False, False]),
    0x2B: ("CALL_FUNC", 0, [True, False, False]),
    0x2C: ("WAIT_KEY", 0, [False, False, False]),
    0x2D: ("WAIT_KEY_EX", 0, [False, False, False]),   # 等待特定键(0x20或0x10位)
    0x2E: ("CHECK_INPUT", 0, [False, False, False]),
    0x2F: ("UNK_2F", 0, [False, False, False]),        # 只是PC+1
    0x30: ("UNK_30", 0, [False, False, False]),        # 只是PC+1
    0x31: ("UNK_31", 0, [False, False, False]),        # 只是PC+1
    0x32: ("UNK_32", 0, [False, False, False]),        # 只是PC+1
    0x33: ("UNK_33", 0, [False, False, False]),        # 只是PC+1
    0x34: ("UNK_34", 0, [False, False, False]),        # 只是PC+1
    0x35: ("OBJ_CREATE", 0, [True, True, True]),
    0x36: ("OBJ_SETPARAM", 0, [True, True, False]),
    0x37: ("OBJ_DESTROY", 0, [True, False, False]),
    0x38: ("OBJ_SETPOS", 0, [True, True, False]),
    0x39: ("OBJ_SETSTATE", 0, [True, True, False]),
    0x3A: ("OBJ_CLEAR", 0, [True, False, False]),
    0x3B: ("UNK_3B", 0, [False, False, False]),        # 只是PC+1
    0x3C: ("UNK_3C", 0, [False, False, False]),        # 只是PC+1
    0x3D: ("VAR_INC", 0, [True, False, False]),        # 变量+1，最大99
    0x3E: ("VAR_DEC", 0, [True, False, False]),        # 变量-1，最小0
    0x3F: ("IF_EQ", 0, [True, True, False]),
    0x40: ("IF_FLAG", 0, [True, True, False]),
    0x41: ("SET_FLAG", 0, [True, True, False]),
    0x42: ("CLEAR_FLAG", 0, [True, True, False]),
    0x43: ("IF_CHECK", 0, [True, True, False]),
    0x44: ("END_SCRIPT", 0, [True, False, False]),     # 没有PC+1，脚本停止
}

def find_opcode_by_mnemonic(mnemonic: str) -> Optional[int]:
    """通过助记符查找opcode数字"""
    for opcode, (name, _, _) in OPCODES.items():
        if name == mnemonic:
            return opcode
    return None

def is_printable(char: str) -> bool:
    """判断字符是否可打印（不需要转义）"""
    code = ord(char)
    if 0x20 <= code <= 0x7E:
        return True
    if code >= 0x100:
        return True
    if char in ('\n', '\t', '\r'):
        return True
    return False

def escape_text(text: str) -> str:
    """文本转义：换行用\\n，其他非可见字符用<hex>"""
    result = []
    for char in text:
        if char == '\n':
            result.append('\\n')
        elif char == '\t':
            result.append('\\t')
        elif char == '\r':
            result.append('\\r')
        elif is_printable(char):
            result.append(char)
        else:
            code = ord(char)
            byte1 = code & 0xFF
            byte2 = (code >> 8) & 0xFF
            result.append(f'<{byte1:02X}{byte2:02X}>')
    
    return ''.join(result)

def unescape_text(text: str) -> str:
    """文本反转义"""
    result = []
    i = 0
    while i < len(text):
        if text[i] == '<':
            end = text.find('>', i)
            if end != -1:
                hex_str = text[i+1:end]
                try:
                    if len(hex_str) % 2 == 0:
                        bytes_data = bytes.fromhex(hex_str)
                        decoded = bytes_data.decode('utf-16-le', errors='ignore')
                        result.append(decoded)
                        i = end + 1
                        continue
                except:
                    pass
            result.append(text[i])
            i += 1
        elif text[i] == '\\' and i + 1 < len(text):
            next_char = text[i + 1]
            if next_char == 'n':
                result.append('\n')
                i += 2
            elif next_char == 't':
                result.append('\t')
                i += 2
            elif next_char == 'r':
                result.append('\r')
                i += 2
            else:
                result.append(text[i])
                i += 1
        else:
            result.append(text[i])
            i += 1
    
    return ''.join(result)

class ScriptDisassembler:
    def __init__(self, data: bytes):
        self.data = data
        self.chunks = len(data) // CHUNK_SIZE
        self.labels = {}
        # 查表获取opcode数字
        self.opcode_label = find_opcode_by_mnemonic("LABEL")
        self.opcode_text = find_opcode_by_mnemonic("TEXT")
        self.opcode_choice = find_opcode_by_mnemonic("CHOICE")
        self.opcode_msg_show = find_opcode_by_mnemonic("MSG_SHOW")
        self.opcode_msg_show_ex = find_opcode_by_mnemonic("MSG_SHOW_EX")
        self._find_labels()
        
    def _find_labels(self):
        """查找所有LABEL指令"""
        if self.opcode_label is None:
            return
        
        for i in range(self.chunks):
            op, args, _, _ = self._parse_chunk_basic(i)
            if op == self.opcode_label:
                self.labels[args[0]] = i
    
    def _parse_chunk_basic(self, index: int) -> Tuple[int, Tuple[int, int, int], bytes, bytes]:
        off = index * CHUNK_SIZE
        if off + CHUNK_SIZE > len(self.data):
            raise ValueError(f"Chunk {index} exceeds data size")
        
        chunk = self.data[off:off + CHUNK_SIZE]
        
        op = struct.unpack('<I', chunk[0:4])[0]
        arg1 = struct.unpack('<i', chunk[4:8])[0]
        arg2 = struct.unpack('<i', chunk[8:12])[0]
        arg3 = struct.unpack('<i', chunk[12:16])[0]
        
        header = chunk[0:TEXT_OFFSET]
        text_data = chunk[TEXT_OFFSET:CHUNK_SIZE]
        
        return op, (arg1, arg2, arg3), header, text_data
    
    def _extract_text_by_length(self, text_data: bytes, char_length: int) -> str:
        """根据字符长度精确提取文本"""
        byte_length = char_length * 2
        if byte_length > len(text_data):
            byte_length = len(text_data)
        
        extracted = text_data[:byte_length]
        return extracted.decode('utf-16-le', errors='ignore')
    
    def _extract_texts(self, opcode: int, text_data: bytes, char_length: int = 0) -> List[str]:
        opcode_info = OPCODES.get(opcode, ("UNK", 0, [False, False, False]))
        text_count = opcode_info[1]
        texts = []
        
        if text_count == 0:
            return []
        elif text_count == 1:
            if char_length > 0:
                text = self._extract_text_by_length(text_data, char_length)
            else:
                text = text_data.decode('utf-16-le', errors='ignore').rstrip('\x00')
            texts.append(text)
        elif text_count == 5:
            offsets = [0x00, 0x48, 0x90, 0xD8, 0x120]
            sizes = [0x48, 0x48, 0x48, 0x48, 0x48]
            
            for i, (off, size) in enumerate(zip(offsets, sizes)):
                if i == 4:
                    segment = text_data[off:]
                else:
                    segment = text_data[off:off + size]
                text = segment.decode('utf-16-le', errors='ignore').rstrip('\x00')
                texts.append(text)
        
        return texts
    
    def _format_args(self, opcode: int, a1: int, a2: int, a3: int) -> str:
        """根据参数启用表格式化参数"""
        opcode_info = OPCODES.get(opcode, ("UNK", 0, [False, False, False]))
        arg_enabled = opcode_info[2]
        
        args = []
        if arg_enabled[0]:
            args.append(str(a1))
        if arg_enabled[1]:
            args.append(str(a2))
        if arg_enabled[2]:
            args.append(str(a3))
        
        return ' ' + ' '.join(args) if args else ''
    
    def disasm_instruction(self, index: int) -> List[str]:
        op, args, header, text_data = self._parse_chunk_basic(index)
        opcode_info = OPCODES.get(op, (f"UNK_{op:02X}", 0, [False, False, False]))
        mnemonic = opcode_info[0]
        a1, a2, a3 = args
        
        lines = []
        
        # 用数字判断（数字是通过查表获得的）
        if op == self.opcode_label:
            # LABEL格式
            lines.append(f"LABEL_{a1:03d}:")
            return lines
        
        if op == self.opcode_text:
            # TEXT指令（arg1是文本长度）
            texts = self._extract_texts(op, text_data, a1)
            lines.append(mnemonic)
            if texts:
                escaped = escape_text(texts[0])
                lines.append(escaped)
            return lines
        
        if op == self.opcode_choice:
            # CHOICE
            texts = self._extract_texts(op, text_data)
            arg_str = self._format_args(op, a1, a2, a3)
            lines.append(f'{mnemonic}{arg_str}')
            if texts:
                escaped = escape_text(texts[0])
                lines.append(escaped)
            return lines
        
        if op == self.opcode_msg_show:
            # MSG_SHOW
            texts = self._extract_texts(op, text_data)
            arg_str = self._format_args(op, a1, a2, a3)
            lines.append(f'{mnemonic}{arg_str}')
            for text in texts[:a1]:
                escaped = escape_text(text)
                lines.append(escaped)
            return lines
        
        if op == self.opcode_msg_show_ex:
            # MSG_SHOW_EX（带图标ID）
            texts = self._extract_texts(op, text_data)
            icon_ids = []
            for i in range(4):
                icon_id = struct.unpack('<i', header[8+i*4:12+i*4])[0]
                icon_ids.append(icon_id)
            
            arg_str = self._format_args(op, a1, a2, a3)
            lines.append(f'{mnemonic}{arg_str}')
            for i, text in enumerate(texts[:a1], 1):
                icon_id = icon_ids[i-1] if i <= 4 else -1
                escaped = escape_text(text)
                lines.append(f'{icon_id} {escaped}')
            return lines
        
        # 普通指令
        arg_str = self._format_args(op, a1, a2, a3)
        lines.append(f'{mnemonic}{arg_str}')
        
        return lines
    
    def export(self, filepath: str):
        with open(filepath, 'w', encoding='utf-8') as f:
            for i in range(self.chunks):
                lines = self.disasm_instruction(i)
                for line in lines:
                    f.write(line + '\n')

class ScriptAssembler:
    def __init__(self):
        self.chunks = []
        # 构建助记符->opcode映射表
        self.mnemonic_to_opcode = {v[0]: k for k, v in OPCODES.items()}
        # 查表获取特殊opcode数字
        self.opcode_label = find_opcode_by_mnemonic("LABEL")
        self.opcode_text = find_opcode_by_mnemonic("TEXT")
        self.opcode_msg_show_ex = find_opcode_by_mnemonic("MSG_SHOW_EX")
    
    def _encode_text_utf16le(self, text: str, max_bytes: int) -> bytes:
        """编码文本为UTF-16LE，自动截断"""
        encoded = text.encode('utf-16-le')
        if len(encoded) > max_bytes:
            lo, hi = 0, len(text)
            best = b''
            while lo <= hi:
                mid = (lo + hi) // 2
                test = text[:mid].encode('utf-16-le')
                if len(test) <= max_bytes:
                    best = test
                    lo = mid + 1
                else:
                    hi = mid - 1
            encoded = best
        
        return encoded.ljust(max_bytes, b'\x00')
    
    def _parse_line(self, line: str) -> Optional[dict]:
        line = line.rstrip('\n\r')
        
        if not line or line.startswith(';'):
            return None
        
        # LABEL - 用查表获得的opcode数字
        if line.startswith('LABEL_') and line.endswith(':'):
            label_id = int(line[6:-1])
            if self.opcode_label is None:
                return None
            return {
                'type': 'instruction',
                'opcode': self.opcode_label,
                'args': [label_id, 0, 0],
                'texts': []
            }
        
        # 检查是否是指令行
        parts = line.split(None, 1)
        if not parts:
            return {'type': 'text', 'content': line}
        
        first_word = parts[0]
        
        # 检查是否是已知指令（通过遍历表查找）
        if first_word in self.mnemonic_to_opcode:
            opcode = self.mnemonic_to_opcode[first_word]
            rest = parts[1] if len(parts) > 1 else ""
            
            args = [0, 0, 0]
            
            # 解析参数
            if rest:
                tokens = rest.split()
                for i in range(min(3, len(tokens))):
                    try:
                        args[i] = int(tokens[i])
                    except ValueError:
                        break
            
            return {
                'type': 'instruction',
                'opcode': opcode,
                'args': args,
                'texts': []
            }
        
        # 纯文本行
        return {'type': 'text', 'content': line}
    
    def assemble(self, asm_path: str) -> bytes:
        with open(asm_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        current_chunk = None
        
        for line in lines:
            parsed = self._parse_line(line)
            
            if parsed is None:
                continue
            
            if parsed['type'] == 'instruction':
                if current_chunk:
                    self.chunks.append(current_chunk)
                current_chunk = parsed
            
            elif parsed['type'] == 'text':
                if current_chunk is None:
                    continue
                
                content = parsed['content']
                
                # 用数字判断（查表获得的opcode）
                if self.opcode_msg_show_ex and current_chunk['opcode'] == self.opcode_msg_show_ex:
                    tokens = content.split(None, 1)
                    if (tokens and 
                        len(tokens[0]) <= 4 and 
                        tokens[0].lstrip('-').isdigit() and
                        all(ord(c) < 128 for c in tokens[0])):
                        # 图标行
                        if len(tokens) >= 2:
                            text = unescape_text(tokens[1])
                        else:
                            text = ''
                        current_chunk['texts'].append(text)
                    else:
                        # 普通文本
                        text = unescape_text(content)
                        current_chunk['texts'].append(text)
                else:
                    # 其他指令的文本
                    text = unescape_text(content)
                    current_chunk['texts'].append(text)
        
        if current_chunk:
            self.chunks.append(current_chunk)
        
        return self._build_binary()
    
    def _build_binary(self) -> bytes:
        result = bytearray()
        
        for chunk_info in self.chunks:
            chunk_data = bytearray(CHUNK_SIZE)
            
            opcode = chunk_info['opcode']
            args = chunk_info['args']
            texts = chunk_info['texts']
            
            # TEXT指令 - 用数字判断
            if self.opcode_text and opcode == self.opcode_text and texts:
                args[0] = len(texts[0])
            
            struct.pack_into('<I', chunk_data, 0, opcode)
            struct.pack_into('<i', chunk_data, 4, args[0])
            struct.pack_into('<i', chunk_data, 8, args[1])
            struct.pack_into('<i', chunk_data, 12, args[2])
            
            opcode_info = OPCODES.get(opcode, ("UNK", 0, [False, False, False]))
            text_count = opcode_info[1]
            
            if text_count == 1:
                if texts:
                    encoded = self._encode_text_utf16le(texts[0], TEXT_SIZE)
                    chunk_data[TEXT_OFFSET:TEXT_OFFSET + len(encoded)] = encoded
            
            elif text_count == 5:
                offsets = [TEXT_OFFSET + 0x00, TEXT_OFFSET + 0x48, 
                          TEXT_OFFSET + 0x90, TEXT_OFFSET + 0xD8, 
                          TEXT_OFFSET + 0x120]
                sizes = [0x48, 0x48, 0x48, 0x48, 0x48]
                
                for i, (off, size) in enumerate(zip(offsets, sizes)):
                    if i < len(texts):
                        encoded = self._encode_text_utf16le(texts[i], size)
                        chunk_data[off:off + len(encoded)] = encoded
                
                # MSG_SHOW_EX - 用数字判断
                if self.opcode_msg_show_ex and opcode == self.opcode_msg_show_ex:
                    for i in range(4):
                        struct.pack_into('<i', chunk_data, 8 + i*4, -1)
            
            result.extend(chunk_data)
        
        return bytes(result)

def convert_dat_to_asm_name(dat_name: str) -> str:
    if dat_name.endswith('_DAT'):
        return dat_name[:-4] + '.asm'
    return dat_name + '.asm'

def convert_asm_to_dat_name(asm_name: str) -> str:
    if asm_name.endswith('.asm'):
        return asm_name[:-4] + '_DAT'
    return asm_name + '_DAT'

def process_extract(input_folder: str, output_folder: str):
    input_path = Path(input_folder)
    output_path = Path(output_folder)
    output_path.mkdir(parents=True, exist_ok=True)
    
    all_files = []
    for root, dirs, files in os.walk(input_path):
        for file in files:
            if file.endswith('_DAT'):
                all_files.append(Path(root) / file)
    
    for dat_file in all_files:
        try:
            rel_path = dat_file.relative_to(input_path)
            asm_filename = convert_dat_to_asm_name(dat_file.name)
            asm_file = output_path / rel_path.parent / asm_filename
            asm_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(dat_file, 'rb') as f:
                data = f.read()
            
            if len(data) == 0 or len(data) % CHUNK_SIZE != 0:
                print(f"{rel_path}")
                continue
            
            disasm = ScriptDisassembler(data)
            disasm.export(str(asm_file))
        
        except Exception as e:
            print(f"{dat_file.relative_to(input_path)}")

def process_write(input_folder: str, output_folder: str):
    input_path = Path(input_folder)
    output_path = Path(output_folder)
    output_path.mkdir(parents=True, exist_ok=True)
    
    asm_files = list(input_path.rglob('*.asm'))
    
    for asm_file in asm_files:
        try:
            rel_path = asm_file.relative_to(input_path)
            dat_filename = convert_asm_to_dat_name(asm_file.name)
            dat_file = output_path / rel_path.parent / dat_filename
            dat_file.parent.mkdir(parents=True, exist_ok=True)
            
            assembler = ScriptAssembler()
            data = assembler.assemble(str(asm_file))
            
            with open(dat_file, 'wb') as f:
                f.write(data)
        
        except Exception as e:
            print(f"{asm_file.relative_to(input_path)}")

def main():
    if len(sys.argv) != 4:
        print("Usage:")
        print("  python script_tool.py e <input_folder> <output_folder>")
        print("  python script_tool.py w <input_folder> <output_folder>")
        sys.exit(1)
    
    mode = sys.argv[1].lower()
    input_folder = sys.argv[2]
    output_folder = sys.argv[3]
    
    if mode == 'e':
        process_extract(input_folder, output_folder)
    elif mode == 'w':
        process_write(input_folder, output_folder)
    else:
        print(f"Invalid mode: {mode}")
        sys.exit(1)

if __name__ == '__main__':
    main()