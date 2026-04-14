import json
import struct
import sys


REC = struct.Struct("<IIII")
PAIR = struct.Struct("<II")
HEADER = 0xB0
BUCKETS = 418
GROUPS = 3075


def u32(buf, off):
    return struct.unpack_from("<I", buf, off)[0]


def cstr(buf, off):
    end = buf.find(b"\0", off)
    if end < 0:
        end = len(buf)
    return buf[off:end].decode("utf-8", "replace")


def load_json(path):
    return json.loads(open(path, "r", encoding="utf-8").read())


def save_json(path, rows):
    text = json.dumps(rows, ensure_ascii=False, indent=2) + "\n"
    open(path, "w", encoding="utf-8", newline="\n").write(text)


def tags_from_rows(rows):
    if not rows:
        return []
    out = [k for k in rows[0] if k != "hash"]
    for tag in out:
        raw = tag.encode("ascii", "strict")
        if len(raw) != 4:
            raise SystemExit(f"fresh mode requires 4-char language tags: {tag}")
    return out


def meta(buf):
    return {
        "langs": u32(buf, 0x0C),
        "count": u32(buf, 0x10),
        "hash_off": u32(buf, 0x1C),
        "block_off": u32(buf, 0x20),
        "pool_off": u32(buf, 0x24),
        "block_span": u32(buf, 0x34),
    }


def blocks(buf, m):
    out = []
    for i in range(m["langs"]):
        base = m["block_off"] + i * m["block_span"]
        tag = bytes(buf[base:base + 4]).decode("ascii", "replace")
        out.append((tag, base))
    return out


def decode(src, dst):
    buf = open(src, "rb").read()
    if buf[:4] != b"TTB0":
        raise SystemExit("not a TTB0 file")
    m = meta(buf)
    blk = blocks(buf, m)
    rows = []
    for i in range(m["count"]):
        h, idx = PAIR.unpack_from(buf, m["hash_off"] + i * 8)
        row = {"hash": h}
        key = 1 << 31
        for tag, base in blk:
            a, off, size, d = REC.unpack_from(buf, base + idx * 16)
            row[tag] = None if size == 0 else cstr(buf, m["pool_off"] + off)
            if tag == blk[0][0] and size:
                key = off
        rows.append((key, i, row))
    rows.sort(key=lambda x: (x[0], x[1]))
    save_json(dst, [row for _, _, row in rows])


def build_pool(rows, tags):
    pool = bytearray()
    refs = []
    for row in rows:
        item = {}
        for tag in tags:
            text = row.get(tag)
            if text is None:
                item[tag] = (0, 0)
                continue
            raw = text.encode("utf-8") + b"\0"
            hit = (len(pool), len(raw))
            pool += raw
            item[tag] = hit
        refs.append(item)
    return refs, pool


def encode_fresh(src, dst):
    rows = load_json(src)
    tags = tags_from_rows(rows)
    count = len(rows)
    span = count * 16 + 4
    hash_off = HEADER + BUCKETS * 16
    pair_off = hash_off
    pair_size = count * 8
    block_off = pair_off + pair_size
    pool_off = block_off + len(tags) * span

    pairs = sorted((row["hash"], i) for i, row in enumerate(rows))
    base = len(pairs) // BUCKETS
    extra = len(pairs) % BUCKETS
    buckets = []
    pos = 0
    for i in range(BUCKETS):
        size = base + (1 if i < extra else 0)
        first = pairs[pos][0] if size else 0
        buckets.append((first, GROUPS, size, pos * 8))
        pos += size

    refs, pool = build_pool(rows, tags)
    out = bytearray(pool_off)
    out[:4] = b"TTB0"
    struct.pack_into("<I", out, 0x04, HEADER)
    struct.pack_into("<I", out, 0x08, BUCKETS)
    struct.pack_into("<I", out, 0x0C, len(tags))
    struct.pack_into("<I", out, 0x10, count)
    struct.pack_into("<I", out, 0x14, GROUPS)
    struct.pack_into("<I", out, 0x18, HEADER)
    struct.pack_into("<I", out, 0x1C, pair_off)
    struct.pack_into("<I", out, 0x20, block_off)
    struct.pack_into("<I", out, 0x24, pool_off)
    struct.pack_into("<I", out, 0x34, span)
    if len(tags) > 2:
        struct.pack_into("<I", out, 0x58, span * 2)
    if len(tags) > 3:
        struct.pack_into("<I", out, 0x5C, span * 3)

    for i, item in enumerate(buckets):
        REC.pack_into(out, HEADER + i * 16, *item)
    for i, item in enumerate(pairs):
        PAIR.pack_into(out, pair_off + i * 8, *item)

    for n, tag in enumerate(tags):
        base_off = block_off + n * span
        tag4 = tag.encode("ascii", "replace")[:4].ljust(4, b"\0")
        out[base_off:base_off + 4] = tag4
        for idx in range(count):
            off = base_off + idx * 16
            text_off, text_size = refs[idx][tag]
            a = struct.unpack("<I", tag4)[0] if idx == 0 else 338
            REC.pack_into(out, off, a, text_off, text_size, 0)

    out += pool
    open(dst, "wb").write(out)


def main():
    if len(sys.argv) != 4:
        raise SystemExit("decode: python ttb.py d text.ttb text.json\nencode: python ttb.py e text.json text.ttb")
    mode, src, dst = sys.argv[1:4]
    if mode == "d":
        decode(src, dst)
        return
    if mode == "e":
        encode_fresh(src, dst)
        return
    raise SystemExit("mode must be d or e")


if __name__ == "__main__":
    main()
