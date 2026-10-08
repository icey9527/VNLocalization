import sys
import re
import json
import unicodedata
from pathlib import Path

import char

char.MAP_PATH = Path('font/font.tbl')

def to_json_text(text):
    return text.replace("\n", "\\n")


def to_game_text(text):
    return text.replace("\\n", "\n")


def is_fw(t):
    return any(unicodedata.east_asian_width(c) in ('W', 'F') for c in t)


def is_text_candidate(raw, text):
    # Executable data often decodes as CP932 while still containing binary control bytes.
    # 0x0A/0x0D 是调试文本的行尾 CRLF，放行——曾因此整批误杀 656 条调试日志
    # （如 23B290 的 "GA005必殺音指定無し\r\n"）。实测全文件被杀串只出现过
    # 这两种控制字节，白名单不需要再放宽。
    if any(byte < 0x20 and byte not in (0x0A, 0x0D) for byte in raw):
        return False
    if '\ufffd' in text:
        return False
    if any(unicodedata.category(char) == 'Cc' and char not in '\r\n' for char in text):
        return False
    # U+3000（全角空格，类别 Zs）被 isprintable() 判为不可打印，但它是
    # 游戏文本的合法字符（UI 居中/间隔填充，0x8140），须放行——曾因此
    # 误杀 329 条（存档界面标签、取材メモ等整批）。\r\n 同理，见上。
    if any(not char.isprintable() and char != '\u3000' and char not in '\r\n' for char in text):
        return False
    if not text.strip('\u3000 '):
        return False  # 纯空格填充串（如 1F1170 的 "　　"）不算文本
    return is_fw(text)


def extract(bin_p, json_p):
    pat = re.compile(rb'[^\x00]{1,}\x00')
    out = []
    with open(bin_p, 'rb') as f:
        data = f.read()
        for m in pat.finditer(data):
            try:
                raw = m.group().rstrip(b'\x00')
                s = raw.decode('cp932')
                if is_text_candidate(raw, s):
                    out.append({
                        "key": f"{m.start():X}",
                        "original": to_json_text(s),
                        "translation": "",
                        "stage": 0,
                        "context": str(len(raw)) # 严谨记载字节长度
                    })
            except: continue
    with open(json_p, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

def patch(bin_p, json_p, new_p):
    with open(bin_p, 'rb') as f:
        data = bytearray(f.read())
    with open(json_p, 'r', encoding='utf-8') as f:
        items = json.load(f)
    conv = char.make_translation_converter()
    for item in items:
        # stage 为 0 使用原文，否则使用译文
        txt = item['original'] if item.get('stage') == 0 else item['translation']
        if txt is None: continue
        
        addr = int(item['key'], 16)
        limit = int(item['context']) # 从 context 读取字节长度限制
        new_bytes = conv(to_game_text(txt))
        
        if len(new_bytes) > limit:
            print(f"Warning: {item['key']} too long ({len(new_bytes)} > {limit} bytes), skipping")
            continue  # 跳过这个条目
            
        # 填充 00 并替换
        data[addr:addr + limit] = new_bytes.ljust(limit, b'\x00')
        
    with open(new_p, 'wb') as f:
        f.write(data)

if __name__ == "__main__":
    m, args = sys.argv[1], sys.argv[2:]
    if m == 'e': extract(args[0], args[1])
    elif m == 'w': patch(args[0], args[1], args[2])
