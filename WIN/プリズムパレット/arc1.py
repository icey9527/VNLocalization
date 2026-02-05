#!/usr/bin/env python3
import argparse
import struct
from dataclasses import dataclass
from pathlib import Path

SIG = b"ARC1"
NAME_LEN = 16
ENT_SIZE = 24


@dataclass(frozen=True)
class Entry:
    name: str
    off: int
    size: int


def is_arc(name: str) -> bool:
    return name.lower().endswith(".arc")


def enc_name(name: str, enc: str) -> bytes:
    b = name.encode(enc)
    return b[:NAME_LEN].ljust(NAME_LEN, b"\0")


def dec_name(raw: bytes, enc: str) -> str:
    return raw.split(b"\0", 1)[0].decode(enc)


def read_entries(buf: bytes, enc: str) -> list[Entry]:
    if buf[:4] != SIG:
        raise ValueError("bad signature")
    count, index_off, data_off, data_size = struct.unpack_from("<IIII", buf, 4)
    p = index_off
    out: list[Entry] = []
    for _ in range(count):
        name = dec_name(buf[p : p + NAME_LEN], enc)
        size, off = struct.unpack_from("<II", buf, p + NAME_LEN)
        out.append(Entry(name, off, size))
        p += ENT_SIZE
    return out


def build_arc(items: list[tuple[str, bytes]], enc: str) -> bytes:
    buf = bytearray()
    buf += SIG
    buf += struct.pack("<I", len(items))
    buf += b"\0" * 12

    data_off = len(buf)
    meta: list[tuple[str, int, int]] = []
    for name, data in items:
        off = len(buf)
        buf += data
        meta.append((name, len(data), off))

    index_off = len(buf)
    for name, size, off in meta:
        buf += enc_name(name, enc)
        buf += struct.pack("<II", size, off)

    struct.pack_into("<III", buf, 8, index_off, data_off, len(buf) - data_off)
    return bytes(buf)


def pack_dir_to_bytes(d: Path, enc: str) -> bytes:
    items: list[tuple[str, bytes]] = []
    for p in sorted(d.iterdir(), key=lambda x: x.name):
        if p.is_file():
            items.append((p.name, p.read_bytes()))
        elif p.is_dir():
            items.append((p.name + ".arc", pack_dir_to_bytes(p, enc)))
    return build_arc(items, enc)


def pack(indir: Path, out_arc: Path, enc: str) -> None:
    out_arc.parent.mkdir(parents=True, exist_ok=True)
    out_arc.write_bytes(pack_dir_to_bytes(indir, enc))


def unpack_bytes(buf: bytes, outdir: Path, enc: str) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    for e in read_entries(buf, enc):
        data = buf[e.off : e.off + e.size]
        if is_arc(e.name):
            unpack_bytes(data, outdir / Path(e.name).with_suffix("").name, enc)
        else:
            dst = outdir / e.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)


def unpack(arc_path: Path, outdir: Path, enc: str) -> None:
    unpack_bytes(arc_path.read_bytes(), outdir, enc)


def main() -> None:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("mode", choices=["p", "u"])
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("-enc", default="cp932")
    a = ap.parse_args()

    if a.mode == "p":
        pack(Path(a.input), Path(a.output), a.enc)
    else:
        unpack(Path(a.input), Path(a.output), a.enc)


if __name__ == "__main__":
    main()