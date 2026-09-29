"""elf_string.py -- ELF 文本提取 / 写回（通用版）

用法:
    python elf_string.py e <原版ELF> <输出json>
    python elf_string.py w <原版ELF> <json> <输出ELF>

写回只动字符串本身，不碰任何指针 / 表 / 程序头:
    1) 译文字节数 <= 原长度 -> 原位等长替换（尾部补 0x00）
    2) 超长                -> 吃本条串后面的 0x00 填充原位扩容（不越过下一条串）
    3) 还是不够            -> 打印警告并跳过（请缩短译文）

码位映射和 SCR 文本共用 char.py，码表 = font/font.tbl。
"""
import sys
import re
import json
import struct
import unicodedata
import bisect
from pathlib import Path

# 只用 char.py 的函数（不导入模块名，省得跟"一个字符"的临时变量 char 撞名）。
# 码表路径自己拼绝对路径，不依赖 char.MAP_PATH（那是相对当前目录的）。
from char import apply_replace_rules, load_map, map_translation

BASE = Path(__file__).resolve().parent
_RHS = load_map(BASE / 'font' / 'font.tbl')      # 码表只加载一次（单次 ~13ms）


def conv(t):
    """文本 -> proxy 串（等价替换 -> 查码表映射成该码位的日文等值字符）。

    和 char.make_translation_converter 的 conv 是同一套规则：
    char.py 编不出来的字会降级成半角 '?'，并追加进 badchars.txt。
    """
    return map_translation(apply_replace_rules(t), _RHS)


def to_json_text(text):
    return text.replace("\n", "\\n")


def to_game_text(text):
    return text.replace("\\n", "\n")


def is_fw(t):
    return any(unicodedata.east_asian_width(c) in ('W', 'F') for c in t)


def is_text_candidate(raw, text):
    # Executable data often decodes as CP932 while still containing binary control bytes.
    # 只拒收 0x0A/0x0D(换行)以外的控制字节——含换行的调试文本/规则文本
    # 都是真实字符串,必须收录,不能误伤。实测真实文本的控制字节只出现
    # 过这两种,其余 <0x20 的都是二进制数据伪装。
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
    """扫全文件的 0x00 结尾串，cp932 解码 + 过滤，输出 json。

    每条记 key(文件偏移,十六进制) / original / translation / stage / context(原字节长度)。
    """
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
                        "context": str(len(raw))  # 严谨记载字节长度
                    })
            except: continue
    with open(json_p, 'w', encoding='utf-8-sig') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"提取 {len(out)} 条 -> {json_p}")


def patch(bin_p, json_p, new_p):
    """按 json 写回译文（原位替换 / 原位吃 00 扩容），不改任何指针。"""
    with open(bin_p, 'rb') as f:
        data = bytearray(f.read())
    if struct.unpack_from('<H', data, 0x2C)[0] != 3:
        raise ValueError('不是干净原版 ELF(e_phnum!=3)，请用原始 SLPS_252.35')
    with open(json_p, 'r', encoding='utf-8-sig') as f:
        items = json.load(f)

    # 所有条目的偏移，用来判断"本条串后面还有没有别人的填充"（扩容时不能越界）
    all_keys = sorted(int(it['key'], 16) for it in items if it.get('key'))
    n_inplace = n_grow = n_skip = 0

    for item in items:
        # 只看译文：译文为空 = 保留原文，不动
        txt = item.get('translation') or ''
        if not txt:
            continue

        fo = int(item['key'], 16)
        limit = int(item['context'])          # 原字节长度
        enc = conv(to_game_text(txt)).encode('cp932')

        if len(enc) <= limit:
            # 字节层面补 00，等长替换
            data[fo:fo + limit] = enc.ljust(limit, b'\x00')
            n_inplace += 1
            continue

        # 超长：吃原文后面的 00 填充原位扩容
        # （不改任何指针；保留末尾 NUL，不越过下一条字符串）
        p = fo + limit
        idx = bisect.bisect_right(all_keys, fo)
        nxt = all_keys[idx] if idx < len(all_keys) else len(data)
        while p < nxt and data[p] == 0:
            p += 1
        if p - 1 > fo + len(enc):             # 留 1 个 NUL 后仍装得下
            data[fo:fo + len(enc)] = enc
            n_grow += 1
            print(f"扩容 {item['key']}: {limit} -> {len(enc)} 字节(原位吃 00,不改指针)")
            continue

        n_skip += 1
        print(f"警告:{item['key']} 超长({len(enc)} > {limit} 字节)且后面 00 不够,已跳过——请缩短译文")

    with open(new_p, 'wb') as f:
        f.write(data)
    print(f"完成:原位替换 {n_inplace} 条 / 原位扩容 {n_grow} 条 / 跳过 {n_skip} 条 -> {new_p}")


if __name__ == "__main__":
    m, args = sys.argv[1], sys.argv[2:]
    if m == 'e':
        extract(args[0], args[1])
    elif m == 'w':
        patch(args[0], args[1], args[2])
