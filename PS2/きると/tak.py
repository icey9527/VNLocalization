#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
import sys
import json
from pathlib import Path
import char
char.MAP_PATH = Path('font/font.tbl')
from dataclasses import dataclass
from pathlib import Path

g_name_table: list[str] = []

TAG_RE = re.compile(r"<([^<>]+)>")
TRAILING_LABEL_RE = re.compile(r"\([^()]*\)$")

def parse_translation_json(json_path: Path) -> dict[int, str]:
    data = json.loads(json_path.read_text(encoding="utf-8"))

    if not isinstance(data, list):
        raise ValueError(f"JSON格式错误，不是数组: {json_path}")

    translations: dict[int, str] = {}

    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            continue

        key = item.get("key")
        translated = item.get("translation", "")

        if not isinstance(key, str):
            continue
        if not isinstance(translated, str):
            translated = str(translated)

        if not re.fullmatch(r"[0-9A-Fa-f]{8}", key):
            continue

        addr = int(key, 16)
        translations[addr] = translated

    return translations

def parse_translation_any(path: Path) -> dict[int, str]:
    if path.suffix.lower() == ".json":
        return parse_translation_json(path)
    return parse_translation_file(path)
    
        

@dataclass
class ScriptBlock:
    opcode: int
    cmd_addr: int
    start_addr: int
    end_addr: int
    speaker: str
    raw_payload: bytes
    original_text: str


def load_name_table(file_path: Path, table_offset: int) -> None:
    global g_name_table
    g_name_table = []

    data = file_path.read_bytes()
    offset = table_offset

    while offset + 4 <= len(data):
        mem_addr = int.from_bytes(data[offset:offset + 4], "little")
        if mem_addr == 0:
            break

        file_offset = mem_addr - 0xFF000
        if not (0 <= file_offset < len(data)):
            break

        pos = file_offset
        name_bytes = bytearray()
        while pos < len(data) and data[pos] != 0:
            name_bytes.append(data[pos])
            pos += 1

        try:
            name = bytes(name_bytes).decode("cp932")
        except Exception:
            name = f"[Invalid@{file_offset:X}]"

        g_name_table.append(name)
        offset += 4

    print(f"已加载 {len(g_name_table)} 个名字")


def escape_text(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace("\r\n", "\\r\\n")
        .replace("\r", "\\r")
        .replace("\n", "\\n")
    )


def unescape_text(text: str) -> str:
    result = []
    i = 0
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text):
            c = text[i + 1]
            if c == "n":
                result.append("\n")
                i += 2
                continue
            if c == "r":
                result.append("\r")
                i += 2
                continue
            if c == "\\":
                result.append("\\")
                i += 2
                continue
        result.append(text[i])
        i += 1
    return "".join(result)


def extract_tags(text: str) -> list[str]:
    return TAG_RE.findall(text)


def parse_decimal_param(payload: bytes, pos: int) -> tuple[int | None, int]:
    start = pos
    while pos < len(payload) and 0x30 <= payload[pos] <= 0x39:
        pos += 1
    if pos == start:
        return None, start
    try:
        return int(payload[start:pos].decode("ascii")), pos
    except Exception:
        return None, start


def _fmt_num(v: int | None) -> str:
    return "?" if v is None else str(v)


def parse_payload(payload: bytes) -> str:
    i = 0
    out: list[str] = []

    while i < len(payload):
        b = payload[i]

        if b == 0x00:
            out.append("<00>")
            i += 1
            continue

        if b == 0x21:
            if i + 1 < len(payload):
                val = payload[i + 1]
                i2 = i + 2
            else:
                val = None
                i2 = i + 1
            out.append(f"<!:{_fmt_num(val)}>")
            i = i2
            continue

        if b == 0x23:
            value, i2 = parse_decimal_param(payload, i + 1)
            out.append(f"<#:{_fmt_num(value)}>")
            i = i2
            continue

        if b == 0x25:
            if i + 2 < len(payload):
                fill = payload[i + 1]
                val = payload[i + 2]
                out.append(f"<%:{fill},{val}>")
                i += 3
            elif i + 1 < len(payload):
                fill = payload[i + 1]
                out.append(f"<%:{fill},?>")
                i += 2
            else:
                out.append("<%:?>")
                i += 1
            continue

        if b == 0x2A:
            out.append("<*>")
            i += 1
            continue

        if b == 0x3B:
            out.append("<;>")
            i += 1
            continue

        if b == 0x40:
            out.append("<@>")
            i += 1
            continue

        if b == 0x48:
            if i + 1 < len(payload):
                val = payload[i + 1]
                i2 = i + 2
            else:
                val = None
                i2 = i + 1
            out.append(f"<H:{_fmt_num(val)}>")
            i = i2
            continue

        if b == 0x53:
            out.append("<S>")
            i += 1
            continue

        if b == 0x73:
            out.append("<s>")
            i += 1
            continue

        if b == 0x5E:
            if i + 2 < len(payload):
                val = int.from_bytes(payload[i + 1:i + 3], "little")
                i2 = i + 3
            else:
                val = None
                i2 = i + 1
            out.append(f"<^:{_fmt_num(val)}>")
            i = i2
            continue

        if (0x81 <= b <= 0x9F) or (0xE0 <= b <= 0xEF):
            if i + 1 < len(payload):
                b2 = payload[i + 1]
                if (0x40 <= b2 <= 0x7E) or (0x80 <= b2 <= 0xFC):
                    try:
                        out.append(bytes([b, b2]).decode("cp932"))
                        i += 2
                        continue
                    except UnicodeDecodeError:
                        pass

        out.append(f"<{b:02X}>")
        i += 1

    return "".join(out)


def has_visible_text(parsed: str) -> bool:
    plain = TAG_RE.sub("", parsed)
    return any(ch for ch in plain)


def is_plain_text_payload(parsed: str) -> bool:
    if not parsed:
        return False
    if extract_tags(parsed):
        return False
    return any(not ch.isspace() for ch in parsed)


def is_hex_byte_tag(tag: str) -> bool:
    return re.fullmatch(r"[0-9A-Fa-f]{2}", tag) is not None


def is_control_tag(tag: str) -> bool:
    if tag in {"00", "*", ";", "@", "S", "s"}:
        return True
    return (
        re.fullmatch(r"!:\d+", tag) is not None
        or re.fullmatch(r"#:\d+", tag) is not None
        or re.fullmatch(r"%:\d+,\d+", tag) is not None
        or re.fullmatch(r"H:\d+", tag) is not None
        or re.fullmatch(r"\^:\d+", tag) is not None
    )


def strip_hex_byte_tags(text: str) -> str:
    return re.sub(r"<[0-9A-Fa-f]{2}>", "", text)


def is_known_text_tag(tag: str) -> bool:
    if is_hex_byte_tag(tag):
        return False
    return is_control_tag(tag)


def is_valid_42_payload(parsed: str) -> bool:
    tags = extract_tags(parsed)
    if any(not is_known_text_tag(t) for t in tags):
        return False
    plain = TAG_RE.sub("", parsed)
    return any(not ch.isspace() for ch in plain)


def compile_tag(tag: str) -> bytes:
    if tag == "00":
        return b"\x00"
    if tag == "*":
        return b"\x2A"
    if tag == ";":
        return b"\x3B"
    if tag == "@":
        return b"\x40"
    if tag == "S":
        return b"\x53"
    if tag == "s":
        return b"\x73"

    m = re.fullmatch(r"#:(\d+)", tag)
    if m:
        return b"\x23" + m.group(1).encode("ascii")

    m = re.fullmatch(r"!:(\d+)", tag)
    if m:
        return bytes([0x21, int(m.group(1)) & 0xFF])

    m = re.fullmatch(r"H:(\d+)", tag)
    if m:
        return bytes([0x48, int(m.group(1)) & 0xFF])

    m = re.fullmatch(r"\^:(\d+)", tag)
    if m:
        return b"\x5E" + (int(m.group(1)) & 0xFFFF).to_bytes(2, "little")

    m = re.fullmatch(r"%:(\d+),(\d+)", tag)
    if m:
        fill_b = int(m.group(1)) & 0xFF
        num = int(m.group(2)) & 0xFF
        return bytes([0x25, fill_b, num])

    raise ValueError(f"未知标签: <{tag}>")


def compile_payload(tagged_text: str) -> bytes:
    out = bytearray()
    i = 0

    while i < len(tagged_text):
        if tagged_text[i] == "<":
            m = TAG_RE.match(tagged_text, i)
            if not m:
                raise ValueError(f"无效标签位置: {i}")
            out.extend(compile_tag(m.group(1)))
            i = m.end()
            continue

        ch = tagged_text[i]
        try:
            out.extend(ch.encode("cp932"))
        except UnicodeEncodeError as e:
            raise ValueError(f"字符无法用CP932编码: {ch!r}") from e
        i += 1

    return bytes(out)


def apply_conv_preserve_tags(tagged_text: str, conv) -> str:
    if conv is None:
        return tagged_text
    parts = TAG_RE.split(tagged_text)
    for idx in range(0, len(parts), 2):
        if parts[idx]:
            parts[idx] = conv(parts[idx])
    out: list[str] = []
    for idx, part in enumerate(parts):
        if idx % 2 == 1:
            out.append(f"<{part}>")
        else:
            out.append(part)
    return "".join(out)


def scan_script_blocks(data: bytes, filename: str = "") -> list[ScriptBlock]:
    blocks: list[ScriptBlock] = []
    current_name = ""
    i = 0

    while i < len(data) - 2:
        if (
            i + 9 <= len(data)
            and data[i] == 0x22
            and data[i + 1] == 0x36
            and data[i + 2] == 0x01
            and data[i + 3] == 0x01
            and data[i + 4] == 0x00
        ):
            name_id = int.from_bytes(data[i + 5:i + 9], "little", signed=True)

            if name_id == -1:
                current_name = ""
            elif g_name_table:
                if 0 <= name_id < len(g_name_table):
                    current_name = g_name_table[name_id]
                else:
                    raise ValueError(
                        f"名字ID {name_id} 在名字表中找不到！文件: {filename}, 位置: 0x{i:06X}"
                    )
            else:
                current_name = f"[ID:{name_id}]"

            i += 9
            continue

        if data[i] in (0x42, 0x5D) and i + 3 <= len(data):
            opcode = data[i]
            cmd_addr = i
            end_addr = int.from_bytes(data[i + 1:i + 3], "little")
            start_addr = i + 3

            if start_addr < end_addr <= len(data):

                if opcode == 0x5D:
                    payload_len = end_addr - start_addr
                    if payload_len > 41:
                        i += 1
                        continue

                payload = data[start_addr:end_addr]
                parsed = parse_payload(payload)

                if opcode == 0x42 and not is_valid_42_payload(parsed):
                    i += 1
                    continue

                if opcode == 0x5D and not is_plain_text_payload(parsed):
                    i += 1
                    continue

                speaker = current_name if opcode == 0x42 else "SaveLabel"
                blocks.append(
                    ScriptBlock(
                        opcode=opcode,
                        cmd_addr=cmd_addr,
                        start_addr=start_addr,
                        end_addr=end_addr,
                        speaker=speaker,
                        raw_payload=payload,
                        original_text=parsed,
                    )
                )
                i = end_addr
                continue

        i += 1

    return blocks


def format_block(block: ScriptBlock) -> str:
    lines = [f"#{block.cmd_addr:08X}"]
    if block.speaker:
        lines.append(f"#{escape_text(block.speaker)}")
    lines.append(f"◇{escape_text(block.original_text)}")
    lines.append(f"◆{escape_text(block.original_text)}")
    return "\n".join(lines)


def get_file_label(blocks: list[ScriptBlock]) -> str:
    for block in blocks:
        if block.opcode == 0x5D:
            tags = extract_tags(block.original_text)
            has_ctrl = any(is_control_tag(t) for t in tags if not is_hex_byte_tag(t))
            if has_ctrl:
                continue

            plain = strip_hex_byte_tags(block.original_text)
            plain = TAG_RE.sub("", plain).replace("\r", "").replace("\n", "")
            if plain:
                plain = re.sub(r'[\\/:*?"<>|]', "_", plain)
                return plain
    return ""


def build_output_txt_path(input_path: Path, input_dir: Path, output_dir: Path, blocks: list[ScriptBlock]) -> Path:
    relative = input_path.relative_to(input_dir)
    label = get_file_label(blocks)
    stem = relative.stem
    if label:
        stem = f"{stem}({label})"
    return output_dir / relative.with_name(stem + ".txt")


def extract_to_txt(input_path: Path, output_path: Path, keep_control_only: bool = False) -> int:
    data = input_path.read_bytes()
    blocks = scan_script_blocks(data, input_path.name)

    if not keep_control_only:
        blocks = [b for b in blocks if has_visible_text(b.original_text)]

    if blocks:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            "\n\n".join(format_block(b) for b in blocks) + "\n",
            encoding="utf-8-sig",
        )

    return len(blocks)


def normalize_txt_stem(stem: str) -> str:
    return TRAILING_LABEL_RE.sub("", stem)


def parse_translation_file(txt_path: Path) -> dict[int, str]:
    content = txt_path.read_text(encoding="utf-8-sig")
    lines = content.splitlines()
    translations: dict[int, str] = {}
    i = 0
    n = len(lines)

    def parse_hash_addr(line: str) -> int | None:
        m = re.fullmatch(r"#([0-9A-Fa-f]{8})", line)
        return int(m.group(1), 16) if m else None

    while i < n:
        while i < n and (lines[i] == "" or (lines[i].startswith("#") and parse_hash_addr(lines[i]) is None)):
            i += 1
        if i >= n:
            break

        addr = parse_hash_addr(lines[i])
        if addr is None:
            i += 1
            continue
        i += 1

        while i < n and lines[i].startswith("#"):
            i += 1
        while i < n and lines[i] == "":
            i += 1
        if i < n and lines[i].startswith("◇"):
            i += 1
        while i < n and lines[i] == "":
            i += 1

        translated = ""
        if i < n and lines[i].startswith("◆"):
            translated = unescape_text(lines[i][1:])
            i += 1

        translations[addr] = translated

    return translations


def write_back_to_bin(original_data: bytes, translations: dict[int, str], filename: str = "") -> bytes:
    result = bytearray(original_data)
    append_data = bytearray()
    conv = char.make_translation_converter()

    blocks = scan_script_blocks(original_data, filename)
    block_map = {b.cmd_addr: b for b in blocks}

    for addr, translated in translations.items():
        if not translated.strip():
            continue
        if addr not in block_map:
            print(f"  警告: 0x{addr:06X} 找不到原块，跳过")
            continue

        block = block_map[addr]

        orig_tags = extract_tags(block.original_text)
        new_tags = extract_tags(translated)
        if orig_tags != new_tags:
            print(f"  警告: 0x{addr:06X} 标签序列不一致，跳过")
            print(f"    原: {orig_tags}")
            print(f"    新: {new_tags}")
            continue

        translated = apply_conv_preserve_tags(translated, conv)

        try:
            new_payload = compile_payload(translated)
        except ValueError as e:
            print(f"  警告: 0x{addr:06X} 编译失败: {e}")
            continue

        old_len = block.end_addr - block.start_addr
        new_len = len(new_payload)

        if new_len <= old_len:
            result[block.start_addr:block.end_addr] = b"\x04" * old_len
            result[block.start_addr:block.start_addr + new_len] = new_payload
            
            new_end_addr = block.start_addr + new_len
            result[block.cmd_addr + 1:block.cmd_addr + 3] = new_end_addr.to_bytes(2, "little")
            continue

        text_block_addr = len(original_data) + len(append_data)
        return_jump_addr = text_block_addr + 3 + len(new_payload)

        result[block.cmd_addr] = 0x00
        result[block.cmd_addr + 1:block.cmd_addr + 3] = text_block_addr.to_bytes(2, "little")
        result[block.start_addr:block.end_addr] = b"\x04" * old_len

        append_data.append(block.opcode)
        append_data.extend(return_jump_addr.to_bytes(2, "little"))
        append_data.extend(new_payload)

        append_data.append(0x00)
        append_data.extend(block.end_addr.to_bytes(2, "little"))

    result.extend(append_data)
    return bytes(result)


def process_extract(input_dir: Path, output_dir: Path, keep_control_only: bool = False) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    total_files = 0
    total_blocks = 0

    for input_path in input_dir.rglob("*"):
        if not input_path.is_file():
            continue

        try:
            data = input_path.read_bytes()
            blocks = scan_script_blocks(data, input_path.name)
            output_path = build_output_txt_path(input_path, input_dir, output_dir, blocks)

            export_blocks = blocks if keep_control_only else [b for b in blocks if has_visible_text(b.original_text)]

            if export_blocks:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(
                    "\n\n".join(format_block(b) for b in export_blocks) + "\n",
                    encoding="utf-8-sig",
                )
                print(f"[OK] {input_path.name} -> {len(export_blocks)} 块")
                total_files += 1
                total_blocks += len(export_blocks)
            else:
                print(f"[--] {input_path.name} -> 无可翻译文本")
        except ValueError as e:
            print(f"[!!] {e}")
            sys.exit(1)

    print(f"\n提取完成! 处理了 {total_files} 个文件，共提取 {total_blocks} 个块")


def find_translation_and_bin(bin_dir: Path, trans_dir: Path) -> list[tuple[Path, Path]]:
    pairs: list[tuple[Path, Path]] = []

    trans_files = sorted(
        [p for p in trans_dir.rglob("*") if p.is_file() and p.suffix.lower() in {".json", ".txt"}]
    )

    if not trans_files:
        return pairs

    # 按“标准化文件名”全局分组，不区分子目录
    grouped: dict[str, dict[str, list[Path]]] = {}
    for p in trans_files:
        key = normalize_txt_stem(p.stem)
        grouped.setdefault(key, {}).setdefault(p.suffix.lower(), []).append(p)

    # 建立 bin 索引：优先用 stem 匹配
    bin_map: dict[str, list[Path]] = {}
    for bin_file in bin_dir.rglob("*"):
        if not bin_file.is_file():
            continue
        bin_map.setdefault(bin_file.stem, []).append(bin_file)

    used_bin_paths: set[Path] = set()

    for key in sorted(grouped.keys()):
        files = grouped[key]

        # json 优先，txt 次之
        trans_path = None
        if files.get(".json"):
            trans_path = sorted(files[".json"])[0]
        elif files.get(".txt"):
            trans_path = sorted(files[".txt"])[0]

        if trans_path is None:
            continue

        candidates = bin_map.get(key, [])
        if not candidates:
            print(f"[!!] 找不到对应的bin文件: {trans_path}")
            continue

        # 如果有多个同名bin，优先选还没被占用的
        bin_path = None
        for c in sorted(candidates):
            if c not in used_bin_paths:
                bin_path = c
                break

        if bin_path is None:
            # 都被占用了，就取第一个
            bin_path = sorted(candidates)[0]

        used_bin_paths.add(bin_path)
        pairs.append((trans_path, bin_path))

    return pairs


def process_write_back(bin_dir: Path, txt_dir: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    total_files = 0
    total_blocks = 0

    pairs = find_translation_and_bin(bin_dir, txt_dir)

    if not pairs:
        print("[--] 文本文件夹中没有可用的 txt/json 翻译文件")
        print("\n写回完成! 处理了 0 个文件，共写回 0 条")
        return

    for trans_path, bin_path in pairs:
        original_data = bin_path.read_bytes()

        try:
            translations = parse_translation_any(trans_path)
        except ValueError as e:
            print(f"[!!] 解析失败: {trans_path.name}: {e}")
            continue
        except json.JSONDecodeError as e:
            print(f"[!!] JSON解析失败: {trans_path.name}: {e}")
            continue

        if not translations:
            print(f"[--] {trans_path.name} -> 无翻译内容")
            continue

        valid_count = sum(1 for t in translations.values() if t)
        new_data = write_back_to_bin(original_data, translations, bin_path.name)

        output_path = output_dir / bin_path.relative_to(bin_dir)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(new_data)

        added_bytes = len(new_data) - len(original_data)
        print(f"[OK] {bin_path.name} <- {valid_count} 条 ({trans_path.suffix.lower()}，+{added_bytes} bytes)")
        total_files += 1
        total_blocks += valid_count

    print(f"\n写回完成! 处理了 {total_files} 个文件，共写回 {total_blocks} 条")


def main() -> None:
    if len(sys.argv) < 2:
        print("用法:")
        print(f"  提取: python {sys.argv[0]} e <输入文件夹> <输出文件夹> [-t <名字表文件> <表偏移>] [--all]")
        print(f"  写回: python {sys.argv[0]} w <原始bin文件夹> <文本文件夹> <输出文件夹>")
        sys.exit(1)

    mode = sys.argv[1].lower()

    if mode == "e":
        args = sys.argv[2:]
        positional = []
        keep_control_only = False
        i = 0

        while i < len(args):
            if args[i] == "-t" and i + 2 < len(args):
                table_file = Path(args[i + 1])
                table_offset_arg = args[i + 2]
                table_offset = int(table_offset_arg, 16) if table_offset_arg.lower().startswith("0x") else int(table_offset_arg)

                if not table_file.exists():
                    print(f"错误: 名字表文件不存在: {table_file}")
                    sys.exit(1)

                load_name_table(table_file, table_offset)
                i += 3
            elif args[i] == "--all":
                keep_control_only = True
                i += 1
            else:
                positional.append(args[i])
                i += 1

        if len(positional) != 2:
            print(f"提取用法: python {sys.argv[0]} e <输入文件夹> <输出文件夹> [-t <名字表文件> <表偏移>] [--all]")
            sys.exit(1)

        input_dir = Path(positional[0])
        output_dir = Path(positional[1])

        if not input_dir.exists():
            print(f"错误: 输入文件夹不存在: {input_dir}")
            sys.exit(1)

        process_extract(input_dir, output_dir, keep_control_only=keep_control_only)

    elif mode == "w":
        if len(sys.argv) != 5:
            print(f"写回用法: python {sys.argv[0]} w <原始bin文件夹> <文本文件夹> <输出文件夹>")
            sys.exit(1)

        bin_dir = Path(sys.argv[2])
        txt_dir = Path(sys.argv[3])
        output_dir = Path(sys.argv[4])

        if not bin_dir.exists():
            print(f"错误: bin文件夹不存在: {bin_dir}")
            sys.exit(1)

        if not txt_dir.exists():
            print(f"错误: 文本文件夹不存在: {txt_dir}")
            sys.exit(1)

        process_write_back(bin_dir, txt_dir, output_dir)

    else:
        print(f"未知模式: {mode}")
        print("使用 'e' 提取，'w' 写回")
        sys.exit(1)


if __name__ == "__main__":
    main()
