#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json, struct, sys
from dataclasses import dataclass
from pathlib import Path

SIG, KEYTAB = 0x65525841, 0x400
u8  = lambda x: x & 0xFF
u16 = lambda x: x & 0xFFFF
u32 = lambda x: x & 0xFFFFFFFF

def die(s): raise SystemExit(s)
def dom_from(path: Path):
    n = path.name
    i = n.rfind(".")
    return n[:i] if i > 0 else n

def load_domains(p: Path) -> dict:
    if not p.exists(): return {}
    d = json.loads(p.read_text(encoding="utf-8"))
    return d if isinstance(d, dict) else {}

def save_domains(p: Path, d: dict) -> None:
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# --- engine mutate (this game variant) ---
def mutate(k: int) -> int:
    k = u32(k)
    k ^= u32((k & 0xFFF) << 17)
    return u32(~(k ^ u32((k << 18) | (k >> 15))))

def ddec_inplace(buf: bytearray, key: int, nbytes: int) -> None:
    n, key, off = nbytes // 4, u32(key), 0
    for _ in range(n):
        key = mutate(key)
        c = struct.unpack_from("<I", buf, off)[0]
        p = u32(c ^ key)
        struct.pack_into("<I", buf, off, p)
        key = u32(key + p)
        off += 4

def denc(plain4: bytes, seed: int) -> bytes:
    if len(plain4) % 4: die("internal: index not aligned")
    out, key, off = bytearray(plain4), u32(seed), 0
    for _ in range(len(out)//4):
        key = mutate(key)
        p = struct.unpack_from("<I", out, off)[0]
        c = u32(p ^ key)
        struct.pack_into("<I", out, off, c)
        key = u32(key + p)
        off += 4
    return bytes(out)

def keytable(K: int) -> bytes:
    t = bytearray(KEYTAB)
    ddec_inplace(t, K, KEYTAB)
    return bytes(t)

def xcrypt(data: bytes, tab: bytes) -> bytes:
    out = bytearray(data)
    for i in range(len(out)):
        out[i] ^= tab[i & (KEYTAB-1)]
    return bytes(out)

# --- header math (sub_473A50 verified) ---
def mix18_15(x): return u32((u32(x) << 18) | (u32(x) >> 15))
def step_s(x):   return u32(u32(x) ^ u32((u32(x) & 0xFFF) << 17))
def g(x):        return u32(~(u32(x) ^ mix18_15(x)))

def v22(h16: bytes) -> int:
    v = h16[4]
    for j in range(1, 8):
        b = h16[4+j]
        v = u8(((u8(b) << (8-j)) | (u8(b) >> j)) ^ v)
    return v

def idxsize_ok(M: int, K: int, B: int, C: int):
    v8 = u32(B ^ M)
    s8 = step_s(v8)
    pl = u16(v8) ^ u16(s8 >> 15)
    v9 = u32(((u32(~pl) & 0xFFF) << 17) ^ g(s8))
    v10 = g(v9)
    v11 = u32(v10 ^ K)
    p2 = u16(v9) ^ u16(v9 >> 15)
    v12 = u32(((u32(~p2) & 0xFFF) << 17) ^ v10)
    v13 = u32(C ^ g(v12))
    ok = (v11 >= 8) and ((v13 & 0xFFFFFF00) == 0) and (u8(v13) == u8(v22(struct.pack("<IIII", M, K, B, C))))
    return v11, ok

def constB(M: int, B: int) -> int:
    v8 = u32(B ^ M)
    s8 = step_s(v8)
    pl = u16(v8) ^ u16(s8 >> 15)
    v9 = u32(((u32(~pl) & 0xFFF) << 17) ^ g(s8))
    return g(v9)

def findC(M: int, K: int, B: int, tag24: int) -> int:
    v8 = u32(B ^ M); s8 = step_s(v8)
    pl = u16(v8) ^ u16(s8 >> 15)
    v9 = u32(((u32(~pl) & 0xFFF) << 17) ^ g(s8))
    v10 = g(v9)
    p2 = u16(v9) ^ u16(v9 >> 15)
    v12 = u32(((u32(~p2) & 0xFFF) << 17) ^ v10)
    tweak = g(v12)
    need = v22(struct.pack("<III", M, K, B) + b"\0\0\0\0")
    hi = u32((tag24 & 0xFFFFFF) << 8)
    for low in range(256):
        C = u32(hi | low)
        v13 = u32(C ^ tweak)
        if (v13 & 0xFFFFFF00) == 0 and u8(v13) == u8(need):
            return C
    die("internal: cannot find C")

@dataclass
class Entry:
    name: str
    off: int
    size: int

def parse_index(idx: bytes, isz: int, fsz: int):
    out, cur, lim = [], 0, int(isz)
    while cur + 8 < lim:
        off, size = struct.unpack_from("<II", idx, cur); cur += 8
        try:
            end = idx.index(0, cur, lim)
        except ValueError:
            break
        if end == cur: break
        name = idx[cur:end].decode("cp932", errors="strict")
        if off + size > fsz: die(f"bad entry: {name}")
        out.append(Entry(name, off, size))
        cur = (end + 1 + 3) & ~3
    if not out: die("no entries")
    return out

def build_index(entries):
    b = bytearray()
    for e in entries:
        e.name.encode("cp932", errors="strict")
        b += struct.pack("<II", u32(e.off), u32(e.size))
        b += e.name.encode("cp932", errors="strict") + b"\0"
        while len(b) % 4: b += b"\0"
    b += struct.pack("<II", 0, 0) + b"\0"
    while len(b) % 4: b += b"\0"
    return bytes(b)

def read_ax(p: Path):
    raw = p.read_bytes()
    if len(raw) < 16: die("file too small")
    M, K, B, C = struct.unpack_from("<IIII", raw, 0)
    if M != SIG: die("bad signature")
    isz, ok = idxsize_ok(M, K, B, C)
    if not ok: die("header check failed")
    if 0x10 + isz > len(raw): die("index out of file")
    aligned = (isz + 4) & ~3
    buf = bytearray(aligned)
    buf[:isz] = raw[0x10:0x10+isz]
    ddec_inplace(buf, isz, aligned)
    ents = parse_index(bytes(buf[:isz]), isz, len(raw))
    return raw, K, B, C, isz, ents

def collect(indir: Path):
    files = []
    for p in sorted(indir.rglob("*")):
        if p.is_file() and p.name.lower() != "domains.json":
            files.append((p.relative_to(indir).as_posix(), p.read_bytes()))
    if not files: die("input dir empty")
    return files

def do_u(infile: Path, outdir: Path, domfile: Path):
    raw, K, B, C, _, ents = read_ax(infile)
    tab = keytable(K)
    outdir.mkdir(parents=True, exist_ok=True)
    for e in ents:
        data = xcrypt(raw[e.off:e.off+e.size], tab)
        op = outdir / e.name
        op.parent.mkdir(parents=True, exist_ok=True)
        op.write_bytes(data)
    d = load_domains(domfile)
    domain = dom_from(infile)
    tag24 = (C >> 8) & 0xFFFFFF
    val = [u32(B), int(tag24)]
    old = d.get(domain)
    if old and (int(old[0]) != val[0] or int(old[1]) != val[1]):
        die(f"domain conflict {domain}: old={old} new={val}")
    d[domain] = val
    save_domains(domfile, d)

def do_p(indir: Path, outfile: Path, domfile: Path):
    d = load_domains(domfile)
    domain = dom_from(outfile)
    if domain not in d or not isinstance(d[domain], list) or len(d[domain]) != 2:
        die(f"domains.json missing domain '{domain}'")
    B = int(d[domain][0]) & 0xFFFFFFFF
    tag24 = int(d[domain][1]) & 0xFFFFFF

    files = collect(indir)
    tmp = [Entry(n, 0, len(b)) for (n, b) in files]
    idx_plain = build_index(tmp)
    isz = len(idx_plain)

    K = u32(isz ^ constB(SIG, B))
    C = findC(SIG, K, B, tag24)

    cur = 0x10 + isz
    tab = keytable(K)
    ents, chunks = [], []
    for name, plain in files:
        enc = xcrypt(plain, tab)
        ents.append(Entry(name, cur, len(plain)))
        chunks.append(enc)
        cur += len(enc)
        if cur > 0xFFFFFFFF: die("archive too large")

    idx_plain = build_index(ents)
    if len(idx_plain) != isz:
        isz = len(idx_plain)
        K = u32(isz ^ constB(SIG, B))
        C = findC(SIG, K, B, tag24)
        tab = keytable(K)
        cur = 0x10 + isz
        ents, chunks = [], []
        for name, plain in files:
            enc = xcrypt(plain, tab)
            ents.append(Entry(name, cur, len(plain)))
            chunks.append(enc)
            cur += len(enc)
        idx_plain = build_index(ents)

    idx_cipher = denc(idx_plain, isz)[:isz]
    v11, ok = idxsize_ok(SIG, K, B, C)
    if not ok or v11 != isz: die("internal mismatch")

    header = struct.pack("<IIII", SIG, K, B, C)
    outfile.parent.mkdir(parents=True, exist_ok=True)
    with outfile.open("wb") as f:
        f.write(header); f.write(idx_cipher)
        for ch in chunks: f.write(ch)

    # quick self-check
    _raw, _K, _B, _C, _isz, _ents = read_ax(outfile)
    if _isz != isz or len(_ents) != len(ents): die("self-check failed")

def main():
    if len(sys.argv) != 4:
        print("usage:\n  python axr.py u <in.ax?> <outdir>\n  python axr.py p <indir> <out.ax?>")
        raise SystemExit(2)
    mode = sys.argv[1]
    inp = Path(sys.argv[2])
    out = Path(sys.argv[3])
    domfile = Path("domains.json")  # current directory

    if mode == "u":
        do_u(inp, out, domfile)
    elif mode == "p":
        do_p(inp, out, domfile)
    else:
        die("mode must be u or p")

if __name__ == "__main__":
    main()