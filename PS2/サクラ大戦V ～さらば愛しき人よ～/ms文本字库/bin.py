#!/usr/bin/env python3
import struct
import sys
from pathlib import Path

import char

char.MAP_PATH = Path("font/font.tbl")
TEST = Path("test")

FILE_HEADER_SIZE = 0x10
TABLE1_START = 0x4580
TABLE1_END = 0x4C94
TABLE2_START = 0x4C94
TABLE2_END = 0x52F4
TEXT_START = 0x52F4
TABLE2_TEXT_START = 0x8000
TABLE1_BASE = TEXT_START
TABLE2_BASE = TABLE1_START
FOOTER_SIZE = 0x10
EOFC_MAGIC = b"EOFC"

u32 = lambda b, o: struct.unpack_from("<I", b, o)[0]
p32 = lambda v: struct.pack("<I", v)


def read_c_string(blob: bytes, start: int) -> str:
    end = blob.find(0, start)
    if end < 0:
        raise ValueError(f"Missing NUL at {start:#x}")
    return blob[start:end].decode("cp932")


def encode_text(text: str) -> bytes:
    try:
        return text.encode("cp932")
    except UnicodeEncodeError:
        return conv(text).encode("cp932", "ignore")


def string_start(blob: bytes, hit: int, floor: int) -> int:
    start = hit
    while start > floor and blob[start - 1] != 0:
        start -= 1
    return start


def iter_pool(blob: bytes, start: int, end: int):
    pos = start
    while pos < end:
        nul = blob.find(0, pos)
        if nul < 0 or nul > end:
            break
        if nul > pos:
            yield pos, blob[pos:nul].decode("cp932")
        pos = nul + 1
        while pos < end and blob[pos] == 0:
            pos += 1


def parse(path: Path):
    blob = path.read_bytes()
    if blob[:4] != b"GHSL":
        raise ValueError("Not GHSL")
    if u32(blob, 4) != len(blob) - 0x20:
        raise ValueError("Unexpected data size")

    table_rel = u32(blob, 0x10)
    if table_rel + FILE_HEADER_SIZE != TABLE1_START:
        raise ValueError(f"Unexpected table start: {table_rel + FILE_HEADER_SIZE:#x}")

    footer_off = len(blob) - FOOTER_SIZE
    footer = blob[footer_off:]
    if footer[:4] != EOFC_MAGIC:
        raise ValueError("Missing EOFC footer")

    full_entries = list(iter_pool(blob, TEXT_START, footer_off))
    full_index_by_start = {start: index for index, (start, _) in enumerate(full_entries)}

    table1_refs = []
    for index, pos in enumerate(range(TABLE1_START, TABLE1_END, 4)):
        off = u32(blob, pos)
        hit = TABLE1_BASE + off
        if hit < TEXT_START or hit >= footer_off:
            raise ValueError(f"Table1 entry {index} out of range: {hit:#x}")
        start = string_start(blob, hit, TEXT_START)
        table1_refs.append((full_index_by_start[start], hit - start))

    table2_rows = []
    for index, pos in enumerate(range(TABLE2_START, TABLE2_END, 4)):
        off = u32(blob, pos)
        start = TABLE2_BASE + off
        if start < TABLE2_TEXT_START or start >= footer_off:
            raise ValueError(f"Table2 entry {index} out of range: {start:#x}")
        table2_rows.append((off, start, read_c_string(blob, start)))

    table2_entries = []
    table2_index_by_start = {}
    for _, start, text in table2_rows:
        if start not in table2_index_by_start:
            table2_index_by_start[start] = len(table2_entries)
            table2_entries.append((start, text))

    table2_refs = [table2_index_by_start[start] for _, start, _ in table2_rows]

    return {
        "blob": blob,
        "footer_off": footer_off,
        "footer": footer,
        "full_entries": full_entries,
        "table1_refs": table1_refs,
        "table2_entries": table2_entries,
        "table2_refs": table2_refs,
    }


def extract(src_dir: Path, dst_dir: Path):
    if dst_dir == Path("."):
        dst_dir = TEST
    for src in src_dir.rglob("*"):
        if src.suffix.lower() != ".bin":
            continue
        try:
            info = parse(src)
            base = dst_dir / src.relative_to(src_dir)
            base.parent.mkdir(parents=True, exist_ok=True)
            full_out = base.with_name(src.name + ".name.txt")
            table2_out = base.with_name(src.name + ".txt")
            full_lines = [text.replace("\n", "\\n") for _, text in info["full_entries"]]
            table2_lines = [text.replace("\n", "\\n") for _, text in info["table2_entries"]]
            full_out.write_text("\n".join(full_lines), "utf-8")
            table2_out.write_text("\n".join(table2_lines), "utf-8")
        except Exception as exc:
            print(f"E: {src.name} - {exc}")


def rebuild_pool(lines: list[str], start: int) -> tuple[bytes, list[int]]:
    pool = bytearray()
    starts = []
    for line in lines:
        starts.append(start + len(pool))
        pool += encode_text(line) + b"\0"
    return bytes(pool), starts


def write(txt_dir: Path, base_dir: Path, out_dir: Path):
    if out_dir == Path("."):
        out_dir = TEST / "new"
    seen = set()
    for txt in txt_dir.rglob("*.txt"):
        name = txt.name
        if name.endswith(".name.txt"):
            stem = name[:-9]
        else:
            stem = name[:-4]
        rel = txt.relative_to(txt_dir)
        base_rel = rel.with_name(stem)
        if base_rel in seen:
            continue
        seen.add(base_rel)

        base = base_dir / base_rel
        if not base.exists():
            continue
        try:
            info = parse(base)
            full_txt = txt_dir / base_rel.with_name(base_rel.name + ".name.txt")
            table2_txt = txt_dir / base_rel.with_suffix(base_rel.suffix + ".txt")

            if full_txt.exists():
                full_lines = [line.replace("\\n", "\n") for line in full_txt.read_text("utf-8").splitlines()]
            else:
                full_lines = [text for _, text in info["full_entries"]]
            if table2_txt.exists():
                table2_lines = [line.replace("\\n", "\n") for line in table2_txt.read_text("utf-8").splitlines()]
            else:
                table2_lines = [text for _, text in info["table2_entries"]]

            if len(full_lines) != len(info["full_entries"]):
                raise ValueError("Name count mismatch")
            if len(table2_lines) != len(info["table2_entries"]):
                raise ValueError("Text count mismatch")

            full_bytes, full_starts = rebuild_pool(full_lines, TEXT_START)
            out = bytearray(info["blob"][:TEXT_START])
            out += full_bytes
            if len(out) > info["footer_off"]:
                raise ValueError("Text pool overflowed into footer")
            while len(out) < info["footer_off"]:
                out += b"\0"
            out += info["footer"]
            out[4:8] = p32(len(out) - 0x20)

            for index, (entry_index, delta) in enumerate(info["table1_refs"]):
                enc_len = len(encode_text(full_lines[entry_index]))
                if delta > enc_len:
                    # 翻译后字符串比原锚点偏移短：锚点改为指向该字符串开头。
                    # table1 是内部索引（大量锚点原本就切在双字节字符中间，并非显示指针），
                    # 钳到起点只影响该索引项，不影响 table2 的显示文本。
                    print(f"W: {base.name} - table1[{index}] anchor delta {delta} > new length {enc_len} of entry {entry_index}, clamped to string start")
                    delta = 0
                new_start = full_starts[entry_index]
                new_off = (new_start + delta) - TABLE1_BASE
                pos = TABLE1_START + index * 4
                out[pos:pos + 4] = p32(new_off)

            table2_entry_to_full = {}
            full_lookup = {text: i for i, (_, text) in enumerate(info["full_entries"])}
            for entry_index, (_, text) in enumerate(info["table2_entries"]):
                if text not in full_lookup:
                    raise ValueError(f"Missing table2 text in full pool: {text}")
                table2_entry_to_full[entry_index] = full_lookup[text]

            for index, entry_index in enumerate(info["table2_refs"]):
                full_index = table2_entry_to_full[entry_index]
                new_start = full_starts[full_index]
                new_off = new_start - TABLE2_BASE
                pos = TABLE2_START + index * 4
                out[pos:pos + 4] = p32(new_off)

            dst = out_dir / base_rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(out)
        except Exception as exc:
            print(f"E: {base.name} - {exc}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        sys.exit(0)
    if args[0] == "e":
        extract(Path(args[1]), Path(args[2]) if len(args) > 2 else Path("."))
    elif args[0] == "w":
        conv = char.make_translation_converter()
        write(Path(args[1]), Path(args[2]), Path(args[3]) if len(args) > 3 else Path("."))
