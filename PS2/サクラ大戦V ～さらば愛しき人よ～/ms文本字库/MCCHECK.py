#!/usr/bin/env python3
import struct
import sys
from pathlib import Path

import char

char.MAP_PATH = Path('font/font.tbl')
TEST = Path("test")

FILE_HEADER_SIZE = 0x10
ENTRY_HEADER_SIZE = 0x60
FOOTER_SIZE = 0x10
EOFC_MAGIC = b"EOFC"

u32 = lambda b, o: struct.unpack_from("<I", b, o)[0]
p32 = lambda v: struct.pack("<I", v)


def align4(n: int) -> int:
    return (n + 3) & ~3


def parse(p: Path):
    b = p.read_bytes()
    if b[:4] != b"GTPA":
        raise ValueError("Not GTPA")

    count = u32(b, 0x10)
    raw_offs = [u32(b, 0x14 + i * 4) for i in range(count)]
    offs = [off + FILE_HEADER_SIZE for off in raw_offs]

    if offs != sorted(offs):
        raise ValueError("Offsets are not sorted")

    first_off = offs[0]
    table_end = 0x14 + count * 4
    if first_off != table_end:
        raise ValueError(f"Unexpected first entry start: {first_off:#x} != {table_end:#x}")

    footer_off = len(b) - FOOTER_SIZE
    footer = b[footer_off:]
    if footer[:4] != EOFC_MAGIC:
        raise ValueError("Missing EOFC footer")

    entries = []
    for i, off in enumerate(offs):
        end = offs[i + 1] if i + 1 < count else footer_off
        blob = b[off:end]
        if len(blob) < ENTRY_HEADER_SIZE + 1:
            raise ValueError(f"Entry {i} too short")
        nul = blob.find(0, ENTRY_HEADER_SIZE)
        if nul < 0:
            raise ValueError(f"Entry {i} missing NUL terminator")
        entries.append((blob[:ENTRY_HEADER_SIZE], blob[ENTRY_HEADER_SIZE:nul].decode("cp932")))

    return {
        "count": count,
        "entries": entries,
        "prefix": bytearray(b[:first_off]),
        "footer": footer,
    }


def extract(src_d: Path, dst_d: Path):
    if dst_d == Path("."):
        dst_d = TEST
    for f in src_d.rglob("*"):
        if f.suffix.lower() != ".gtp":
            continue
        try:
            info = parse(f)
            txts = [text.replace("\n", "\\n") for _, text in info["entries"]]
            out = dst_d / f.relative_to(src_d).with_name(f.name + ".txt")
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text("\n".join(txts), "utf-8")
        except Exception as e:
            print(f"E: {f.name} - {e}")


def rebuild_entry(head: bytes, text: str) -> bytes:
    enc = text.encode("cp932", "ignore")
    body = head + enc + b"\0"
    return body + (b"\0" * (align4(len(body)) - len(body)))


def write(txt_d: Path, base_d: Path, out_d: Path):
    if out_d == Path("."):
        out_d = TEST / "new"
    for f in txt_d.rglob("*.txt"):
        rel = f.relative_to(txt_d)
        base = base_d / rel.with_suffix("")
        if not base.exists():
            continue
        try:
            lines = [conv(x.replace("\\n", "\n")) for x in f.read_text("utf-8").splitlines()]
            info = parse(base)
            if len(lines) != info["count"]:
                raise ValueError("Count mismatch")

            out = bytearray(info["prefix"])
            new_offs = []
            for (head, _), line in zip(info["entries"], lines):
                new_offs.append(len(out) - FILE_HEADER_SIZE)
                out += rebuild_entry(head, line)

            out += info["footer"]
            out[4:8] = p32(len(out) - 0x20)
            for i, off in enumerate(new_offs):
                out[0x14 + i * 4:0x18 + i * 4] = p32(off)

            dst = out_d / rel.with_suffix("")
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(out)
        except Exception as e:
            print(f"E: {f.name} - {e}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(0)
    if a[0] == "e":
        extract(Path(a[1]), Path(a[2]) if len(a) > 2 else Path("."))
    elif a[0] == "w":
        conv = char.make_translation_converter()
        write(Path(a[1]), Path(a[2]), Path(a[3]) if len(a) > 3 else Path("."))
