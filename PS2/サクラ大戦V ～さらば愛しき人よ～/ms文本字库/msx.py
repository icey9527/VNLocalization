#!/usr/bin/env python3
import argparse
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

MAGIC_EOFC = b"EOFC"
FLAG_COMPRESSED = 0x0400


@dataclass
class Chunk:
    cid: bytes
    data_size: int
    hdr_size: int
    flags: int
    extra: bytes
    payload: bytes

    def to_bytes(self) -> bytes:
        head = self.cid + struct.pack("<III", self.data_size, self.hdr_size, self.flags) + self.extra
        return head + self.payload


def u32(buf: bytes, off: int) -> int:
    return struct.unpack_from("<I", buf, off)[0]


def parse_chunks(blob: bytes) -> List[Chunk]:
    out: List[Chunk] = []
    off = 0
    n = len(blob)
    while off + 16 <= n:
        cid = blob[off : off + 4]
        data_size = u32(blob, off + 4)
        hdr_size = u32(blob, off + 8)
        flags = u32(blob, off + 12)
        if hdr_size < 16:
            raise ValueError(f"invalid hdr_size={hdr_size} at 0x{off:X}")
        end = off + hdr_size + data_size
        if end > n:
            raise ValueError(f"chunk out of range at 0x{off:X}")
        out.append(
            Chunk(
                cid=cid,
                data_size=data_size,
                hdr_size=hdr_size,
                flags=flags,
                extra=blob[off + 16 : off + hdr_size],
                payload=blob[off + hdr_size : end],
            )
        )
        off = end
        if cid == MAGIC_EOFC:
            break
    return out


def _read_inv(src: bytes, sp: int) -> Tuple[int, int]:
    if sp >= len(src):
        raise ValueError("compressed stream truncated")
    return ((~src[sp]) & 0xFF), sp + 1


def prs_decompress_inv_strict(src: bytes, expected_len: int) -> Tuple[bytes, int]:
    sp = 0
    out = bytearray()
    win = bytearray(0x2000)
    wp = 0
    bits_left = 1
    cur = 0

    def next_bit() -> int:
        nonlocal sp, bits_left, cur
        bits_left -= 1
        if bits_left == 0:
            cur, sp = _read_inv(src, sp)
            bits_left = 8
        b = cur & 1
        cur >>= 1
        return b

    while True:
        while next_bit() == 1:
            b, sp = _read_inv(src, sp)
            out.append(b)
            win[wp & 0x1FFF] = b
            wp += 1

        if next_bit() == 1:
            b0, sp = _read_inv(src, sp)
            b1, sp = _read_inv(src, sp)
            if b0 == 0 and b1 == 0:
                break
            ln = b0 & 7
            disp = ((b1 << 5) + (b0 >> 3)) - 0x2000
            if ln == 0:
                ext, sp = _read_inv(src, sp)
                ln = ext + 1
            else:
                ln += 2
        else:
            b0 = next_bit()
            b1 = next_bit()
            ln = ((b0 << 1) | b1) + 2
            d8, sp = _read_inv(src, sp)
            disp = d8 - 0x100

        for _ in range(ln):
            c = win[(wp + disp) & 0x1FFF]
            out.append(c)
            win[wp & 0x1FFF] = c
            wp += 1

    dec = bytes(out)
    if len(dec) != expected_len:
        raise ValueError(f"decoded size mismatch: got={len(dec)} expect={expected_len}")
    return dec, sp


def parse_comp_header_16(payload: bytes) -> Tuple[int, int, int, int, int]:
    if len(payload) < 16:
        raise ValueError("compressed payload too short for 16-byte header")
    pos = 0
    bits_left = 0
    cur = 0

    def next_bit() -> int:
        nonlocal pos, bits_left, cur
        if bits_left == 0:
            if pos >= len(payload):
                raise ValueError("header bitstream truncated")
            cur = payload[pos]
            pos += 1
            bits_left = 8
        bits_left -= 1
        return (cur >> bits_left) & 1

    vals = []
    for _ in range(4):
        v = 0
        for i in range(32):
            v |= next_bit() << i
        vals.append(v)
    return vals[0], vals[1], vals[2], vals[3], pos


def decode_chunk_strict(c: Chunk, allow_zero_pad: bool = True) -> Tuple[Chunk, str]:
    if (c.flags & FLAG_COMPRESSED) == 0:
        return c, "plain"
    w0, w1, w2, w3, hsz = parse_comp_header_16(c.payload)
    dec, consumed = prs_decompress_inv_strict(c.payload[hsz:], w0)
    total_src = len(c.payload) - hsz
    tail = c.payload[hsz + consumed :]
    if tail:
        if any(b != 0 for b in tail):
            raise ValueError(f"non-zero trailing compressed bytes: used={consumed} total={total_src} tail={tail.hex()}")
        if not allow_zero_pad:
            raise ValueError(f"zero padding exists but disallowed: pad={len(tail)}")

    out = Chunk(c.cid, len(dec), c.hdr_size, c.flags & ~FLAG_COMPRESSED, c.extra, dec)
    return out, f"cmp ok hdr=[0x{w0:X},0x{w1:X},0x{w2:X},0x{w3:X}] src={total_src} used={consumed} pad={len(tail)} dec={len(dec)}"


def decode_msx_strict(blob: bytes, allow_zero_pad: bool = True) -> Tuple[bytes, List[str]]:
    chunks = parse_chunks(blob)
    logs: List[str] = []
    out_chunks: List[Chunk] = []
    for i, c in enumerate(chunks):
        dc, msg = decode_chunk_strict(c, allow_zero_pad=allow_zero_pad)
        logs.append(f"chunk[{i}] {c.cid.decode('ascii', 'replace')}: {msg}")
        out_chunks.append(dc)
    return b"".join(c.to_bytes() for c in out_chunks), logs


def iter_msx(root: Path, exclude: Path | None = None) -> List[Path]:
    ex = exclude.resolve() if exclude else None
    files = []
    seen = set()
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix.lower() != ".msx":
            continue
        rp = p.resolve()
        if rp in seen:
            continue
        seen.add(rp)
        if ex:
            try:
                rp.relative_to(ex)
                continue
            except ValueError:
                pass
        files.append(p)
    return sorted(files)


def run_d(input_dir: Path, output_dir: Path, allow_zero_pad: bool = True) -> None:
    files = iter_msx(input_dir, output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    ok = 0
    for src in files:
        rel = src.relative_to(input_dir)
        dst = output_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            dec, _ = decode_msx_strict(src.read_bytes(), allow_zero_pad=allow_zero_pad)
            dst.write_bytes(dec)
            ok += 1
        except Exception as e:
            print(f"[WARN] {rel.as_posix()}: {e}")
    print(f"[OK] strict-decompressed {ok}/{len(files)} files -> {output_dir}")


def run_v(input_dir: Path, output_dir: Path, allow_zero_pad: bool = True) -> None:
    files = iter_msx(input_dir, output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report = output_dir / "verify.txt"
    lines: List[str] = []
    ok = 0
    for src in files:
        rel = src.relative_to(input_dir).as_posix()
        try:
            dec, logs = decode_msx_strict(src.read_bytes(), allow_zero_pad=allow_zero_pad)
            _ = parse_chunks(dec)
            lines.append(f"[OK] {rel}")
            lines.extend(f"  {x}" for x in logs)
            ok += 1
        except Exception as e:
            lines.append(f"[NG] {rel} :: {e}")
    report.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    print(f"[OK] strict-verified {ok}/{len(files)} files -> {report}")


def main() -> None:
    ap = argparse.ArgumentParser(description="MSXN2 strict MSX decompressor")
    ap.add_argument("mode", choices=["d", "v"], help="d=decompress, v=verify")
    ap.add_argument("input", help="input folder")
    ap.add_argument("output", help="output folder")
    ap.add_argument("--no-zero-pad", action="store_true", help="fail if compressed stream has any trailing zero padding bytes")
    args = ap.parse_args()

    in_dir = Path(args.input)
    out_dir = Path(args.output)
    if not in_dir.is_dir():
        raise SystemExit(f"input is not a folder: {in_dir}")

    allow_zero_pad = not args.no_zero_pad
    if args.mode == "d":
        run_d(in_dir, out_dir, allow_zero_pad=allow_zero_pad)
    else:
        run_v(in_dir, out_dir, allow_zero_pad=allow_zero_pad)


if __name__ == "__main__":
    main()
