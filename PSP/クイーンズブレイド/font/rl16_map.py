import argparse
import struct
from pathlib import Path


def decode(data):
    if len(data) < 8 or data[:4] != b"RL16":
        raise ValueError("not an RL16 file")
    units = struct.unpack_from("<I", data, 4)[0]
    pos = 8
    values = []
    consumed = 0
    while consumed < units:
        if pos + 2 > len(data):
            raise ValueError("truncated RL16 stream")
        control = struct.unpack_from("<H", data, pos)[0]
        pos += 2
        if control & 0x8000:
            count = (control & 0x7FFF) + 1
            if pos + 2 > len(data):
                raise ValueError("truncated RL16 run")
            value = struct.unpack_from("<H", data, pos)[0]
            pos += 2
            consumed += 2
            values.extend([value] * count)
        else:
            count = control + 1
            end = pos + count * 2
            if end > len(data):
                raise ValueError("truncated RL16 literal")
            values.extend(struct.unpack_from(f"<{count}H", data, pos))
            pos = end
            consumed += count + 1
    if consumed != units:
        raise ValueError("invalid RL16 unit count")
    return values


def encode(values):
    out = bytearray(b"RL16\0\0\0\0")
    i = 0
    while i < len(values):
        run = 1
        while i + run < len(values) and values[i + run] == values[i] and run < 0x8000:
            run += 1
        if run >= 2:
            out += struct.pack("<HH", 0x8000 | (run - 1), values[i])
            i += run
            continue
        start = i
        i += 1
        while i < len(values) and i - start < 0x8000:
            run = 1
            while i + run < len(values) and values[i + run] == values[i] and run < 2:
                run += 1
            if run >= 2:
                break
            i += 1
        count = i - start
        out += struct.pack("<H", count - 1)
        out += struct.pack(f"<{count}H", *values[start:i])
    struct.pack_into("<I", out, 4, len(out[8:]) // 2)
    return bytes(out)


def read_table(path):
    raw = path.read_bytes()
    encoding = "utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig"
    text = raw.decode(encoding)
    result = {}
    for line_no, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.split(";", 1)[0]
        if not line.strip() or line.lstrip().startswith(("#", "//")):
            continue
        if "=" not in line:
            raise ValueError(f"{path}:{line_no}: expected CODE=CHAR")
        code_text, char = line.split("=", 1)
        code = int(code_text.strip(), 16)
        if not 0 <= code <= 0xFFFF or len(char) > 1:
            raise ValueError(f"{path}:{line_no}: invalid mapping")
        if char:
            result[code] = ord(char)
    return result


def shift_jis_to_rl16_index(code):
    if code <= 0xFF:
        return code
    lead, trail = code >> 8, code & 0xFF
    raw = bytes((lead, trail))
    try:
        raw.decode("cp932")
    except UnicodeDecodeError:
        return None
    row = (lead - (0x81 if lead <= 0x9F else 0xC1)) * 2 + 0x21
    if trail >= 0x9F:
        row += 1
        cell = trail - 0x7E
    else:
        cell = trail - (0x1F if trail < 0x7F else 0x20)
    return row << 8 | cell


def main():
    parser = argparse.ArgumentParser(description="Update UTF-16 mapping entries in an RL16 table")
    parser.add_argument("table", type=Path, help="CODE=CHAR mapping table")
    parser.add_argument("input", type=Path, help="original RL16 source")
    parser.add_argument("output", type=Path)
    parser.add_argument("--dump", type=Path, help="write decoded CODE=U+XXXX=character table")
    args = parser.parse_args()
    values = decode(args.input.read_bytes())
    if len(values) != 0x10000:
        raise ValueError(f"expected 65536 mappings, got {len(values)}")
    mappings = read_table(args.table)
    indices = {}
    skipped = 0
    for code, value in mappings.items():
        index = shift_jis_to_rl16_index(code)
        if index is None:
            skipped += 1
            continue
        previous = indices.get(index)
        if previous is not None and previous != code:
            raise ValueError(
                f"codes {previous:04X} and {code:04X} map to RL16 index {index:04X}"
            )
        indices[index] = code
        values[index] = value
    encoded = encode(values)
    args.output.write_bytes(encoded)
    print(
        f"{args.output}: updated {len(indices)} mappings, "
        f"skipped {skipped} invalid slots, {len(encoded)} bytes"
    )
    if args.dump:
        with args.dump.open("w", encoding="utf-8", newline="\n") as out:
            for code, value in enumerate(values):
                if value:
                    char = chr(value) if 0x20 <= value <= 0xFFFF else ""
                    out.write(f"{code:04X}=U+{value:04X}={char}\n")


if __name__ == "__main__":
    main()
