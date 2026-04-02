from __future__ import annotations

import re
import sys
from pathlib import Path


MAGIC = b"GFRD"
CHUNK_HEADER_SIZE = 16
INDEX_START = 0x1C
FIXED_0C = 0x80000000
FIXED_18 = 0


def u32le(data: bytes, off: int) -> int:
    return int.from_bytes(data[off:off + 4], "little")


def p32(v: int) -> bytes:
    return int(v).to_bytes(4, "little")


def ensure(cond: bool, msg: str) -> None:
    if not cond:
        raise ValueError(msg)


def align_up(v: int, a: int) -> int:
    return (v + (a - 1)) & ~(a - 1)


def parse_chunks(data: bytes, first_chunk_off: int) -> list[dict]:
    chunks: list[dict] = []
    off = first_chunk_off
    idx = 0
    while True:
        ensure(off + CHUNK_HEADER_SIZE <= len(data), f"chunk header out of range @0x{off:X}")
        tag = data[off:off + 4].decode("latin1")
        size = u32le(data, off + 4)
        data_off = u32le(data, off + 8)
        end = off + data_off + size
        ensure(data_off >= CHUNK_HEADER_SIZE, f"bad data_off @0x{off:X}")
        ensure(end <= len(data), f"chunk end out of range @0x{off:X}")
        chunks.append(
            {
                "index": idx,
                "tag": tag,
                "off": off,
                "size": size,
                "data_off": data_off,
                "end": end,
            }
        )
        idx += 1
        off = end
        if tag == "EOFC":
            break
    ensure(off == len(data), f"trailing bytes after EOFC: {len(data) - off}")
    return chunks


def unpack(bin_path: Path, out_dir: Path) -> None:
    data = bin_path.read_bytes()
    ensure(data[:4] == MAGIC, "not GFRD")
    first_chunk_off = u32le(data, 0x08)
    ensure(0x20 <= first_chunk_off <= len(data), "bad first_chunk_off")

    chunks = parse_chunks(data, first_chunk_off)
    out_dir.mkdir(parents=True, exist_ok=True)

    for c in chunks:
        name = f"{c['index'] + 1}.{c['tag']}"
        raw = data[c["off"]:c["end"]]
        (out_dir / name).write_bytes(raw)

    print(f"ok: unpacked {len(chunks)} chunks -> {out_dir}")


def _collect_chunk_files(in_dir: Path) -> list[Path]:
    base = in_dir
    ensure(base.is_dir(), "input dir not found")

    pat = re.compile(r"^(\d+)\.([^.]+)$")
    items: list[tuple[int, Path]] = []
    for p in base.iterdir():
        if not p.is_file():
            continue
        m = pat.match(p.name)
        if not m:
            continue
        items.append((int(m.group(1)), p))
    ensure(items, "no chunk files like 1.SFNT found")
    items.sort(key=lambda x: x[0])
    return [p for _, p in items]


def pack(in_dir: Path, out_bin: Path) -> None:
    files = _collect_chunk_files(in_dir)
    raws: list[tuple[str, bytes]] = []
    for p in files:
        raw = p.read_bytes()
        ensure(len(raw) >= CHUNK_HEADER_SIZE, f"chunk too small: {p.name}")
        tag = raw[:4].decode("latin1")
        size = u32le(raw, 4)
        data_off = u32le(raw, 8)
        ensure(len(raw) == data_off + size, f"chunk size mismatch: {p.name}")
        raws.append((tag, raw))

    ensure(raws[-1][0] == "EOFC", "last chunk must be EOFC")
    offsets_count = sum(1 for tag, _ in raws if tag != "EOFC")

    header_need = INDEX_START + 4 * (offsets_count + 1)
    first_chunk_off = max(0x40, align_up(header_need, 0x10))
    header = bytearray(first_chunk_off)
    header[0x00:0x04] = MAGIC
    header[0x08:0x0C] = p32(first_chunk_off)
    header[0x0C:0x10] = p32(FIXED_0C)
    header[0x10:0x14] = p32(offsets_count)
    header[0x14:0x18] = p32(INDEX_START)
    header[0x18:0x1C] = p32(FIXED_18)

    off = first_chunk_off
    idx = 0
    chunk_span_no_eofc = 0
    for tag, raw in raws:
        if tag != "EOFC":
            header[INDEX_START + idx * 4: INDEX_START + (idx + 1) * 4] = p32(off)
            idx += 1
            chunk_span_no_eofc += len(raw)
        off += len(raw)
    header[INDEX_START + idx * 4: INDEX_START + (idx + 1) * 4] = p32(0)
    header[0x04:0x08] = p32(chunk_span_no_eofc)

    out = bytearray(header)
    for _, raw in raws:
        out += raw
    out_bin.write_bytes(out)
    print(f"ok: packed {len(raws)} chunks -> {out_bin}")


def usage() -> int:
    print("usage:")
    print("  python first.py u input.bin out_dir")
    print("  python first.py p in_dir output.bin")
    return 2


def main() -> int:
    if len(sys.argv) != 4:
        return usage()
    mode = sys.argv[1].lower()
    try:
        if mode == "u":
            unpack(Path(sys.argv[2]), Path(sys.argv[3]))
            return 0
        if mode == "p":
            pack(Path(sys.argv[2]), Path(sys.argv[3]))
            return 0
        return usage()
    except Exception as e:
        print(f"err: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
