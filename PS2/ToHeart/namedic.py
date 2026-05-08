from __future__ import annotations

import json
import re
import struct
import sys
from pathlib import Path

import char


TEXT_ENCODING = "cp932"
HEX_RE = re.compile(r"<([0-9A-Fa-f]+)>")
DEFAULT_DAT = Path("namedic.dat")
DEFAULT_TBL = Path("font") / "font.tbl"


def u32(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def p32(value: int) -> bytes:
    return struct.pack("<I", value)


def decode_char(raw: bytes) -> str:
    try:
        return raw.decode(TEXT_ENCODING)
    except UnicodeDecodeError:
        return f"<{raw.hex().upper()}>"


def decode_bytes(raw: bytes) -> str:
    out: list[str] = []
    pos = 0
    while pos < len(raw):
        byte = raw[pos]
        if byte < 0x80 or 0xA1 <= byte <= 0xDF:
            out.append(decode_char(raw[pos : pos + 1]))
            pos += 1
            continue
        if pos + 1 >= len(raw):
            out.append(f"<{byte:02X}>")
            break
        out.append(decode_char(raw[pos : pos + 2]))
        pos += 2
    return "".join(out)


def encode_text(text: str, conv=None) -> bytes:
    if conv is not None:
        text = conv(text)
    out = bytearray()
    pos = 0
    while pos < len(text):
        if text[pos] == "<":
            match = HEX_RE.match(text, pos)
            if match:
                raw = bytes.fromhex(match.group(1))
                out.extend(raw)
                pos = match.end()
                continue
        out.extend(text[pos].encode(TEXT_ENCODING, errors="ignore"))
        pos += 1
    return bytes(out)


def parse_main_block(data: bytes, off: int) -> tuple[list[str], int]:
    rows: list[str] = []
    buf = bytearray()
    pos = off
    while pos < len(data):
        head = data[pos]
        if head == 0:
            pos += 1
            break
        if head == 1:
            rows.append(decode_bytes(bytes(buf)))
            buf.clear()
            pos += 1
            continue
        if pos + 1 >= len(data):
            raise ValueError(f"main block at 0x{off:X} truncated")
        buf.extend(data[pos : pos + 2])
        pos += 2
    if buf or not rows:
        rows.append(decode_bytes(bytes(buf)))
    return rows, pos


def parse_dict_block(data: bytes, off: int, end: int) -> tuple[list[tuple[bytes, str]], int]:
    out: list[tuple[bytes, str]] = []
    pos = off
    while pos < end:
        hdr = data[pos]
        if hdr == 0:
            pos += 1
            break
        pos += 1
        key_len = (hdr >> 4) & 0xF
        val_count = hdr & 0xF
        need = key_len + val_count * 2
        if pos + need > end:
            break
        key = data[pos : pos + key_len]
        pos += key_len
        raw = data[pos : pos + val_count * 2]
        pos += len(raw)
        out.append((key, decode_bytes(raw)))
    return out, pos


def add_item(group: dict[str, str], text: str) -> None:
    key = text
    index = 2
    while key in group:
        key = f"{text} [{index:02d}]"
        index += 1
    group[key] = ""


def split_item(label: str) -> tuple[str, int]:
    match = re.match(r"^(.*) \[(\d{2})\]$", label)
    if not match:
        return label, 1
    return match.group(1), int(match.group(2))


def build_lookup(group: dict[str, str]) -> dict[tuple[str, int], str]:
    out: dict[tuple[str, int], str] = {}
    for key, value in group.items():
        base, index = split_item(key)
        out[(base, index)] = value
    return out


def get_table_info(data: bytes) -> tuple[int, int, int, list[int], list[int], list[int]]:
    if len(data) < 12:
        raise ValueError("file too small")
    main_off = u32(data, 0)
    table_a_off = u32(data, 4)
    table_b_off = u32(data, 8)
    if main_off != 0x0C:
        raise ValueError(f"unexpected main index offset: 0x{main_off:X}")
    first_main = u32(data, main_off)
    main_count = (first_main - main_off) // 4
    table_a_count = (table_b_off - table_a_off) // 4
    table_b_count = (len(data) - table_b_off) // 4
    main_index = [u32(data, main_off + i * 4) for i in range(main_count)]
    table_a = [u32(data, table_a_off + i * 4) for i in range(table_a_count)]
    table_b = [u32(data, table_b_off + i * 4) for i in range(table_b_count)]
    return main_off, table_a_off, table_b_off, main_index, table_a, table_b


def dump_namedic(src: Path, dst: Path) -> None:
    data = src.read_bytes()
    _, table_a_off, _, main_index, table_a, table_b = get_table_info(data)
    out = {"main": {}, "table_a": {}, "table_b": {}}
    for off in main_index:
        rows, _ = parse_main_block(data, off)
        for row in rows:
            add_item(out["main"], row)
    for i, off in enumerate(table_a):
        end = table_a[i + 1] if i + 1 < len(table_a) else table_b[0]
        items, _ = parse_dict_block(data, off, end)
        for _, text in items:
            add_item(out["table_a"], text)
    for i, off in enumerate(table_b):
        end = table_b[i + 1] if i + 1 < len(table_b) else table_a_off
        items, _ = parse_dict_block(data, off, end)
        for _, text in items:
            add_item(out["table_b"], text)
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_main_block(rows: list[str], conv=None) -> bytes:
    out = bytearray()
    for row_index, row in enumerate(rows):
        raw = encode_text(row, conv)
        if len(raw) & 1:
            raise ValueError(f"main row {row_index} has odd byte length")
        out.extend(raw)
        out.append(1)
    if rows:
        out[-1] = 0
    else:
        out.append(0)
    return bytes(out)


def build_dict_block(items: list[tuple[bytes, str]], conv=None) -> bytes:
    out = bytearray()
    for key, text in items:
        raw = encode_text(text, conv)
        if len(raw) & 1:
            raise ValueError(f"dict text has odd byte length: {text!r}")
        count = len(raw) // 2
        if len(key) > 0xF or count > 0xF:
            raise ValueError(f"dict entry too large: key={len(key)} value={count}")
        out.append((len(key) << 4) | count)
        out.extend(key)
        out.extend(raw)
    out.append(0)
    return bytes(out)


def make_converter(tbl_path: Path | None):
    if tbl_path is None:
        return None
    if not tbl_path.exists():
        raise FileNotFoundError(f"table file not found: {tbl_path}")
    rhs_to_proxy = char.load_map(tbl_path)
    return lambda text: char.map_translation(char.apply_replace_rules(text), rhs_to_proxy)


def rebuild_namedic(src_json: Path, src_dat: Path, dst_dat: Path, tbl_path: Path | None = None) -> None:
    text_map = json.loads(src_json.read_text(encoding="utf-8"))
    for name in ("main", "table_a", "table_b"):
        if name not in text_map or not isinstance(text_map[name], dict):
            raise ValueError(f"missing json group: {name}")

    lookups = {name: build_lookup(text_map[name]) for name in ("main", "table_a", "table_b")}
    seen = {name: {} for name in ("main", "table_a", "table_b")}

    data = src_dat.read_bytes()
    main_off, table_a_off, table_b_off, main_index, table_a, table_b = get_table_info(data)
    first_blob = min(main_index)
    prefix = bytearray(data[:first_blob])
    blob = bytearray()
    conv = make_converter(tbl_path)

    def next_text(group: str, original: str) -> str:
        count = seen[group].get(original, 0) + 1
        seen[group][original] = count
        return lookups[group].get((original, count), "")

    new_main: list[int] = []
    for off in main_index:
        rows, _ = parse_main_block(data, off)
        text_rows = [next_text("main", row) or row for row in rows]
        new_main.append(first_blob + len(blob))
        blob.extend(build_main_block(text_rows, conv))

    new_a: list[int] = []
    for i, off in enumerate(table_a):
        end = table_a[i + 1] if i + 1 < len(table_a) else table_b[0]
        items, _ = parse_dict_block(data, off, end)
        text_items = [(key, next_text("table_a", text) or text) for key, text in items]
        new_a.append(len(blob))
        blob.extend(build_dict_block(text_items, conv))

    new_b: list[int] = []
    for i, off in enumerate(table_b):
        end = table_b[i + 1] if i + 1 < len(table_b) else table_a_off
        items, _ = parse_dict_block(data, off, end)
        text_items = [(key, next_text("table_b", text) or text) for key, text in items]
        new_b.append(len(blob))
        blob.extend(build_dict_block(text_items, conv))
    table_a_new_off = first_blob + len(blob)
    table_b_new_off = table_a_new_off + len(new_a) * 4
    struct.pack_into("<I", prefix, 4, table_a_new_off)
    struct.pack_into("<I", prefix, 8, table_b_new_off)
    for i, off in enumerate(new_main):
        struct.pack_into("<I", prefix, main_off + i * 4, off)
    table_a_index = bytearray()
    for rel_off in new_a:
        table_a_index.extend(p32(first_blob + rel_off))
    table_b_index = bytearray()
    for rel_off in new_b:
        table_b_index.extend(p32(first_blob + rel_off))
    dst_dat.write_bytes(bytes(prefix) + bytes(blob) + bytes(table_a_index) + bytes(table_b_index))


def usage() -> int:
    print("usage:")
    print("  python namedic.py namedic.dat out.json")
    print("  python namedic.py namedic.json [namedic.dat] [new.dat] [font.tbl]")
    return 1


def main(argv: list[str]) -> int:
    if len(argv) == 3 and Path(argv[1]).suffix.lower() == ".dat":
        dump_namedic(Path(argv[1]), Path(argv[2]))
        return 0
    if 2 <= len(argv) <= 5 and Path(argv[1]).suffix.lower() == ".json":
        src_json = Path(argv[1])
        src_dat = Path(argv[2]) if len(argv) >= 3 else DEFAULT_DAT
        dst_dat = Path(argv[3]) if len(argv) >= 4 else src_json.with_suffix(".dat")
        tbl_path = Path(argv[4]) if len(argv) >= 5 else DEFAULT_TBL
        rebuild_namedic(src_json, src_dat, dst_dat, tbl_path)
        return 0
    return usage()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
