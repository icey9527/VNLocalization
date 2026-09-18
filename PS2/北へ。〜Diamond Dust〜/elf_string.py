import sys
import re
import json
import unicodedata
from char import make_translation_encoder


def to_json_text(text):
    return text.replace("#n", "{R;}")


def to_game_text(text):
    return text.replace("{R;}", "#n")


def is_fw(t):
    return any(unicodedata.east_asian_width(c) in ('W', 'F') for c in t)


def is_text_candidate(raw, text):
    # Executable data often decodes as CP932 while still containing binary control bytes.
    if any(byte < 0x20 for byte in raw):
        return False
    if '\ufffd' in text:
        return False
    if any(unicodedata.category(char) == 'Cc' for char in text):
        return False
    if any(not char.isprintable() for char in text):
        return False
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
    conv = make_translation_encoder()
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
