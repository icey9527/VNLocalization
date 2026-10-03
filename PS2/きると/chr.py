#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import sys
from pathlib import Path
import char
char.MAP_PATH = Path('font/font.tbl')
BASE_ADDR = 0xFF000


def read_c_string(data: bytes, offset: int) -> bytes:
    end = offset
    while end < len(data) and data[end] != 0:
        end += 1
    return data[offset:end]


def load_name_table(data: bytes, table_offset: int):
    entries = []
    ptr_off = table_offset

    while ptr_off + 4 <= len(data):
        mem_addr = int.from_bytes(data[ptr_off:ptr_off + 4], "little")

        if mem_addr == 0:
            break

        file_off = mem_addr - BASE_ADDR
        if not (0 <= file_off < len(data)):
            break

        raw = read_c_string(data, file_off)
        try:
            text = raw.decode("cp932")
        except Exception:
            break

        entries.append((ptr_off, file_off, text))
        ptr_off += 4

    if not entries:
        return [], ptr_off, ptr_off

    string_area_start = min(x[1] for x in entries)
    string_area_end = max(x[1] + len(read_c_string(data, x[1])) + 1 for x in entries)

    return entries, string_area_start, string_area_end


def extract_mode(exe_path: Path, table_offset: int):
    data = exe_path.read_bytes()
    entries, _, _ = load_name_table(data, table_offset)

    result = {}
    for _, _, text in entries:
        if text not in result:
            result[text] = ""

    Path("chr.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"[OK] 提取完成，共 {len(entries)} 项，输出 chr.json")


def write_mode(exe_path: Path, table_offset: int, json_path: Path, out_path: Path):
    data = bytearray(exe_path.read_bytes())
    trans = json.loads(json_path.read_text(encoding="utf-8"))
    conv = char.make_translation_converter()

    entries, string_area_start, string_area_end = load_name_table(bytes(data), table_offset)
    if not entries:
        raise ValueError("没有读取到名字表")

    new_strings = []
    for _, _, original in entries:
        text = trans.get(original, "")
        if not text:
            text = original
        text = conv(text)
        bs = text.encode("cp932") + b"\x00"
        new_strings.append(bs)

    total_size = sum(len(x) for x in new_strings)
    capacity = string_area_end - string_area_start
    if total_size > capacity:
        raise ValueError(f"字符串区超出: 需要 {total_size} 字节, 可用 {capacity} 字节")

    # 清空原字符串区
    for i in range(string_area_start, string_area_end):
        data[i] = 0

    # 重新写字符串并修指针
    cur = string_area_start
    for ptr_off, _, _original in entries:
        mem_addr = BASE_ADDR + cur
        data[ptr_off:ptr_off + 4] = mem_addr.to_bytes(4, "little")

        bs = new_strings.pop(0)
        data[cur:cur + len(bs)] = bs
        cur += len(bs)

    out_path.write_bytes(bytes(data))
    print(f"[OK] 写回完成 -> {out_path}")


def main():
    if len(sys.argv) < 2:
        print("用法:")
        print(f"  提取: python {sys.argv[0]} e <主程序文件> <地址>")
        print(f"  写回: python {sys.argv[0]} w <原主程序文件> <地址> <chr.json> <输出主程序文件>")
        sys.exit(1)

    mode = sys.argv[1].lower()

    if mode == "e":
        if len(sys.argv) != 4:
            print(f"提取: python {sys.argv[0]} e <主程序文件> <地址>")
            sys.exit(1)

        exe_path = Path(sys.argv[2])
        table_offset = int(sys.argv[3], 16) if sys.argv[3].lower().startswith("0x") else int(sys.argv[3])
        extract_mode(exe_path, table_offset)

    elif mode == "w":
        if len(sys.argv) != 6:
            print(f"写回: python {sys.argv[0]} w <原主程序文件> <地址> <chr.json> <输出主程序文件>")
            sys.exit(1)

        exe_path = Path(sys.argv[2])
        table_offset = int(sys.argv[3], 16) if sys.argv[3].lower().startswith("0x") else int(sys.argv[3])
        json_path = Path(sys.argv[4])
        out_path = Path(sys.argv[5])

        write_mode(exe_path, table_offset, json_path, out_path)

    else:
        print("模式只能是 e 或 w")
        sys.exit(1)


if __name__ == "__main__":
    main()
