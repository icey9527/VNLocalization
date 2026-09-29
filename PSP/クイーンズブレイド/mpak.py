# -*- coding: utf-8 -*-
"""Queen's Blade SC — MPAK 地形文本提取/写回工具

用法:
  python mpak.py e <map.bin目录> <文本输出目录>
  python mpak.py w <map.bin目录> <翻译目录> <重建输出目录>

格式 (map.bin 容器内的 NNNN.mpak, 数据侧 36 个档案全部验证):
  0x00 "MPAK" | 0x04 版本 0x41 | 0x08 头长 0x20 | 0x0C 五个 u32 区块偏移
  区块按偏移升序紧凑排列, MPTD 固定在 0x20:
  MPTD 地形索引网格: magic + u32 + u32宽 + u32高 + 宽*高*u16
  MPTI 地形表:       magic + u32条数 + 条数*36字节记录
                     记录: 名字(CP932, NUL 结尾, 24字节字段) + 8字节保留
                           + u16参数A + u16参数B
  MAPD/TPAK/BNA./PPAK: 原样保留, 不解析
写回时未翻译的行复用原始字节; 名字超过 24 字节时记录自动扩容,
重算区块偏移表, 文件随之变长 (外层容器由 qbsc 重新打包)。
"""
import argparse
import struct
from pathlib import Path

from char import make_translation_encoder


HEADER_SIZE = 0x20
SLOT_TABLE = 0x0C
SECTION_SLOTS = 5
MPAK_VERSION = 0x41
MPTD_HEADER = 0x10
MPTI_HEADER = 0x08
MPTI_NAME_FIELD = 24
MPTI_TAIL = 12
MPTI_ENTRY = MPTI_NAME_FIELD + MPTI_TAIL
KNOWN_MAGICS = (b"MPTD", b"MPTI", b"MAPD", b"TPAK", b"BNA.", b"PPAK")


class MpakError(ValueError):
    pass


def u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def parse_mpak(data):
    """返回 {区块起始: (magic, bytes)} 与 MPTI 记录列表 [(name, name_raw, tail)]。"""
    if len(data) < HEADER_SIZE:
        raise MpakError("file is too small")
    if data[:4] != b"MPAK":
        raise MpakError("not an MPAK file")
    if data[5] != MPAK_VERSION or data[4:5] != b"\0" or data[6:8] != b"\0" * 2:
        raise MpakError("unsupported MPAK version")
    if u32(data, 8) != HEADER_SIZE:
        raise MpakError("unsupported MPAK header size")
    slots = [u32(data, SLOT_TABLE + 4 * i) for i in range(SECTION_SLOTS)]
    starts = sorted({HEADER_SIZE, *(o for o in slots if o)})
    if slots and [o for o in slots if o] != sorted(o for o in slots if o):
        raise MpakError("MPAK section offsets are not ordered")
    for start in starts:
        if start < HEADER_SIZE or start + 4 > len(data):
            raise MpakError("MPAK section offset is outside the file")
    bounds = list(zip(starts, starts[1:] + [len(data)]))
    sections = {}
    cursor_expected = None
    for start, end in bounds:
        if cursor_expected is not None and start != cursor_expected:
            raise MpakError(f"gap or overlap before section 0x{start:X}")
        cursor_expected = end
        magic = data[start:start + 4]
        if magic not in KNOWN_MAGICS:
            raise MpakError(f"unknown section magic {magic!r} at 0x{start:X}")
        sections[start] = (magic, data[start:end])
    mpti_entries = None
    for start, (magic, blob) in sections.items():
        if magic != b"MPTI":
            continue
        if len(blob) < MPTI_HEADER:
            raise MpakError("MPTI section is too small")
        count = u32(blob, 4)
        if MPTI_HEADER + count * MPTI_ENTRY != len(blob):
            raise MpakError("MPTI entry table size does not match")
        mpti_entries = []
        for index in range(count):
            entry = blob[MPTI_HEADER + index * MPTI_ENTRY:
                         MPTI_HEADER + (index + 1) * MPTI_ENTRY]
            field = entry[:MPTI_NAME_FIELD]
            nul = field.find(b"\0")
            if nul < 0:
                raise MpakError(f"MPTI entry {index} has no string terminator")
            if any(field[nul:]):
                raise MpakError(f"MPTI entry {index} has data after the name")
            try:
                name = field[:nul].decode("cp932")
            except UnicodeDecodeError as error:
                raise MpakError(f"MPTI entry {index} is not valid CP932: {error}") from None
            mpti_entries.append((name, field[:nul], entry[MPTI_NAME_FIELD:]))
        break
    if mpti_entries is None:
        raise MpakError("no MPTI section")
    return slots, sections, mpti_entries


def escape_text(text):
    return text.replace("\\", "\\\\").replace("@", "\\n")


def unescape_text(text, line_number):
    output = []
    index = 0
    while index < len(text):
        char = text[index]
        if char != "\\":
            output.append(char)
            index += 1
            continue
        if index + 1 >= len(text):
            raise ValueError(f"line {line_number}: trailing backslash")
        escaped = text[index + 1]
        if escaped == "n":
            output.append("@")
        elif escaped == "\\":
            output.append("\\")
        else:
            raise ValueError(f"line {line_number}: unknown escape \\{escaped}")
        index += 2
    return "".join(output)


def read_lines(path):
    text = path.read_text(encoding="utf-8-sig")
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()
    for index, line in enumerate(lines):
        if line.endswith("\r"):
            lines[index] = line[:-1]
    return [unescape_text(line, i + 1) for i, line in enumerate(lines)]


def extract(source, output):
    data = source.read_bytes()
    _, _, entries = parse_mpak(data)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(escape_text(name) + "\n" for name, _, _ in entries),
                      encoding="utf-8-sig", newline="")
    return len(entries)


def build_entries(entries, translated, encode):
    """按行重建 MPTI 记录; 返回 (记录字节列表, 是否发生扩容)。"""
    if len(translated) != len(entries):
        raise ValueError(f"expected {len(entries)} lines, got {len(translated)}")
    rebuilt = []
    expanded = False
    for index, (original, name_raw, tail) in enumerate(entries):
        text = translated[index]
        raw = name_raw if text == original else encode(text)
        if b"\0" in raw:
            raise ValueError(f"line {index + 1}: encoded text contains NUL")
        if len(raw) + 1 <= MPTI_NAME_FIELD:
            rebuilt.append(raw.ljust(MPTI_NAME_FIELD, b"\0") + tail)
        else:
            rebuilt.append(raw + b"\0" + tail)
            expanded = True
    return rebuilt, expanded


def patch_in_place(data, entries, translated, encode):
    """全部名字仍在 24 字节字段内时, 除名字字段外逐字节保持原文件。"""
    _, sections, _ = parse_mpak(data)
    rebuilt, _ = build_entries(entries, translated, encode)
    mpti_start = next(s for s, (m, _) in sections.items() if m == b"MPTI")
    result = bytearray(data)
    for index, entry in enumerate(rebuilt):
        offset = mpti_start + MPTI_HEADER + index * MPTI_ENTRY
        result[offset:offset + MPTI_ENTRY] = entry
    return bytes(result)


def rebuild_expanded(data, entries, translated, encode):
    """有名字超过 24 字节时的整档重建: 重排 MPTI 并重算区块偏移表。"""
    slots, sections, _ = parse_mpak(data)
    rebuilt, _ = build_entries(entries, translated, encode)
    mpti_blob = bytearray(b"MPTI" + struct.pack("<I", len(rebuilt)))
    for entry in rebuilt:
        mpti_blob += entry
    starts = sorted(sections)
    mpti_at = next(s for s, (m, _) in sections.items() if m == b"MPTI")
    shift = len(mpti_blob) - len(sections[mpti_at][1])
    head = bytearray(data[:HEADER_SIZE])
    for i, slot in enumerate(slots):
        value = slot if slot <= mpti_at or slot == 0 else slot + shift
        struct.pack_into("<I", head, SLOT_TABLE + 4 * i, value)
    result = bytearray(head)
    for start in starts:
        magic, blob = sections[start]
        result += mpti_blob if start == mpti_at else blob
    return bytes(result)


def rebuild(source, translation, output, encode):
    data = source.read_bytes()
    _, _, entries = parse_mpak(data)
    translated = read_lines(translation)
    _, expanded = build_entries(entries, translated, encode)
    result = (rebuild_expanded if expanded else patch_in_place)(data, entries, translated, encode)
    parse_mpak(result)  # 自检: 重建结果必须仍可完整解析
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(result)
    return len(entries), len(data), len(result), expanded


def extract_directory(source, output):
    if not source.is_dir():
        raise ValueError(f"source is not a directory: {source}")
    files = sorted(path for path in source.rglob("*.mpak") if path.is_file())
    count = 0
    for path in files:
        relative = Path(str(path.relative_to(source)) + ".txt")
        count += extract(path, output / relative)
    print(f"Extracted {len(files)} MPAK files, {count} terrain names")


def rebuild_directory(source, translation, output):
    if not source.is_dir():
        raise ValueError(f"source is not a directory: {source}")
    if not translation.is_dir():
        raise ValueError(f"translation is not a directory: {translation}")
    encode = make_translation_encoder()
    files = sorted(translation.rglob("*.mpak.txt"))
    names = grown = 0
    for text_path in files:
        relative = text_path.relative_to(translation).with_suffix("")
        original = source / relative
        if not original.is_file():
            raise FileNotFoundError(f"missing original MPAK: {original}")
        count, old, new, expanded = rebuild(original, text_path, output / relative, encode)
        names += count
        grown += expanded
        if expanded:
            print(f"{relative}: expanded, {old} -> {new} bytes")
    print(f"Rebuilt {len(files)} MPAK files, {names} terrain names, {grown} expanded")


def main():
    parser = argparse.ArgumentParser(
        usage="mpak.py e SOURCE_DIR TEXT_DIR | "
              "mpak.py w SOURCE_DIR TEXT_DIR OUTPUT_DIR")
    sub = parser.add_subparsers(dest="mode", required=True)
    extract_parser = sub.add_parser("e")
    extract_parser.add_argument("source", type=Path)
    extract_parser.add_argument("output", type=Path)
    write_parser = sub.add_parser("w")
    write_parser.add_argument("source", type=Path)
    write_parser.add_argument("translation", type=Path)
    write_parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.mode == "e":
        extract_directory(args.source, args.output)
    else:
        rebuild_directory(args.source, args.translation, args.output)


if __name__ == "__main__":
    main()
