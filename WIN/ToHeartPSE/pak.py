import os
import struct
import sys
from pathlib import Path


MAGIC = b"LEAFPACK"
ENTRY_SIZE = 0x18


def crypt(data, key, add):
    out = bytearray(data)
    key_len = len(key)
    for i in range(len(out)):
        if add:
            out[i] = (out[i] + key[i % key_len]) & 0xFF
        else:
            out[i] = (out[i] - key[i % key_len]) & 0xFF
    return bytes(out)


def decode_name(raw):
    name = raw[:8].rstrip(b" \x00").decode("cp932", errors="ignore")
    ext = raw[8:11].rstrip(b" \x00").decode("cp932", errors="ignore")
    return f"{name}.{ext}" if ext else name


def encode_name(name):
    base, ext = os.path.splitext(name)
    ext = ext[1:] if ext.startswith(".") else ext
    base_bytes = base.encode("cp932")
    ext_bytes = ext.encode("cp932")
    if len(base_bytes) > 8:
        raise ValueError(f"name too long for 8.3 field: {name}")
    if len(ext_bytes) > 3:
        raise ValueError(f"extension too long for 8.3 field: {name}")
    return base_bytes.ljust(8, b" ") + ext_bytes.ljust(3, b" ") + b"\x00"


def parse_pak(path):
    blob = Path(path).read_bytes()
    if blob[:8] != MAGIC:
        raise ValueError("not a LEAFPACK archive")
    if len(blob) < 11:
        raise ValueError("file too small")

    count = struct.unpack_from("<H", blob, len(blob) - 3)[0]
    key_len = blob[-1]
    if key_len == 0:
        raise ValueError("key length is zero")

    key = blob[8:8 + key_len]
    index_size = count * ENTRY_SIZE
    index_off = len(blob) - 3 - index_size
    if index_off < 8 + key_len:
        raise ValueError("invalid archive layout")

    index = crypt(blob[index_off:index_off + index_size], key, add=False)
    entries = []
    for i in range(count):
        entry = index[i * ENTRY_SIZE:(i + 1) * ENTRY_SIZE]
        name = decode_name(entry[:12])
        offset, size, end_offset = struct.unpack_from("<III", entry, 0x0C)
        if offset + size != end_offset:
            raise ValueError(f"entry {i}: invalid end offset")
        entries.append((name, offset, size))
    return blob, entries


def unpack(src, out_dir):
    blob, entries = parse_pak(src)
    key_len = blob[-1]
    key = blob[8:8 + key_len]
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for i, (name, offset, size) in enumerate(entries):
        if offset + size > len(blob):
            raise ValueError(f"entry {i}: data out of range")
        data = crypt(blob[offset:offset + size], key, add=False)
        (out_dir / name.replace("\\", "_").replace("/", "_")).write_bytes(data)

    print(f"unpacked {len(entries)} files")


def pack(in_dir, out_path):
    in_dir = Path(in_dir)
    out_path = Path(out_path)
    files = sorted(p for p in in_dir.iterdir() if p.is_file())
    if not files:
        raise ValueError("input folder is empty")

    key = os.urandom(16)
    data_parts = []
    index_plain = bytearray()
    offset = 8 + len(key)

    for f in files:
        plain = f.read_bytes()
        data = crypt(plain, key, add=True)
        size = len(data)
        end_offset = offset + size
        index_plain += encode_name(f.name)
        index_plain += struct.pack("<III", offset, size, end_offset)
        data_parts.append(data)
        offset = end_offset

    out = bytearray()
    out += MAGIC
    out += key
    for data in data_parts:
        out += data
    out += crypt(index_plain, key, add=True)
    out += struct.pack("<HB", len(files), len(key))
    out_path.write_bytes(out)
    print(f"packed {len(files)} files")


def main():
    if len(sys.argv) != 4 or sys.argv[1] not in ("u", "p"):
        print("usage:")
        print("  python PSE.py u <input.pak> <output_dir>")
        print("  python PSE.py p <input_dir> <output.pak>")
        return 1

    cmd, src, dst = sys.argv[1], sys.argv[2], sys.argv[3]
    if cmd == "u":
        unpack(src, dst)
    else:
        pack(src, dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
