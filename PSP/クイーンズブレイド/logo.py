import argparse
import struct
from pathlib import Path

from char import make_translation_encoder


MAGIC = b"LOGO"
def parse_logo(data, allow_custom_text=False):
    if len(data) < 0x60 or data[:4] != MAGIC:
        raise ValueError("not a LOGO file")
    if struct.unpack_from("<I", data, 4)[0] != len(data):
        raise ValueError("LOGO size field does not match the file")

    pairs = [struct.unpack_from("<II", data, 0x10 + i * 8) for i in range(10)]
    first_count, first_table = pairs[6]
    first_text_count, text_pool = pairs[7]
    boundary_count, boundary_table = pairs[8]
    second_count, second_pool = pairs[9]
    if first_count != first_text_count or boundary_count != second_count + 1:
        raise ValueError("unsupported LOGO text table counts")

    def read_offsets(offset, count):
        if offset > len(data) or count > (len(data) - offset) // 4:
            raise ValueError("LOGO offset table is outside the file")
        return list(struct.unpack_from(f"<{count}I", data, offset))

    offsets = read_offsets(first_table, first_count)
    offsets += read_offsets(boundary_table, boundary_count)
    if len(offsets) != first_count + second_count + 1:
        raise ValueError("invalid LOGO text boundary count")
    if any(a > b for a, b in zip(offsets, offsets[1:])):
        raise ValueError("LOGO text offsets are not ordered")
    if text_pool + offsets[first_count] != second_pool:
        raise ValueError("LOGO second text pool offset is inconsistent")
    if text_pool + offsets[-1] > len(data):
        raise ValueError("LOGO text pool is outside the file")

    strings = []
    for index, (start, end) in enumerate(zip(offsets, offsets[1:])):
        raw = data[text_pool + start:text_pool + end]
        if not raw.endswith(b"\0") or b"\0" in raw[:-1]:
            raise ValueError(f"text {index} is not a single terminated string")
        try:
            strings.append(raw[:-1].decode("cp932"))
        except UnicodeDecodeError as error:
            if allow_custom_text:
                strings.append(None)
                continue
            raise ValueError(f"text {index} is not valid CP932: {error}") from None
    return pairs, offsets, strings


def escape_text(text):
    return text.replace("\\", "\\\\").replace("@", "\\n")


def unescape_text(text, line_number):
    output = []
    index = 0
    while index < len(text):
        char = text[index]
        if char != "\\":
            output.append(char)
            index += 1
            continue
        if index + 1 >= len(text):
            raise ValueError(f"line {line_number}: trailing backslash")
        escaped = text[index + 1]
        if escaped == "n":
            output.append("@")
        elif escaped == "\\":
            output.append("\\")
        else:
            raise ValueError(f"line {line_number}: unknown escape \\{escaped}")
        index += 2
    return "".join(output)


def read_lines(path):
    text = path.read_text(encoding="utf-8-sig")
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()
    for index, line in enumerate(lines):
        if line.endswith("\r"):
            lines[index] = line[:-1]
    return [unescape_text(line, i + 1) for i, line in enumerate(lines)]


def extract(source, output):
    _, _, strings = parse_logo(source.read_bytes())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(escape_text(s) + "\n" for s in strings), encoding="utf-8-sig", newline="")
    print(f"{output}: {len(strings)} lines")


def rebuild(source, translation, output, encode):
    data = bytearray(source.read_bytes())
    pairs, old_offsets, original = parse_logo(data, allow_custom_text=True)
    translated = read_lines(translation)
    if len(translated) != len(original):
        raise ValueError(f"{translation}: expected {len(original)} lines, got {len(translated)}")

    first_count, first_table = pairs[6]
    _, text_pool = pairs[7]
    boundary_count, boundary_table = pairs[8]
    encoded = []
    for index, text in enumerate(translated):
        try:
            raw = text.encode("cp932") if text == original[index] else encode(text)
            encoded.append(raw + b"\0")
        except UnicodeEncodeError as error:
            raise ValueError(f"{translation}, line {index + 1}: {error}") from None

    offsets = [0]
    for raw in encoded:
        offsets.append(offsets[-1] + len(raw))
    first_offsets = offsets[:first_count]
    second_offsets = offsets[first_count:]
    if len(second_offsets) != boundary_count:
        raise ValueError("rebuilt LOGO boundary count changed")

    struct.pack_into(f"<{first_count}I", data, first_table, *first_offsets)
    struct.pack_into(f"<{boundary_count}I", data, boundary_table, *second_offsets)
    struct.pack_into("<I", data, 0x5C, text_pool + offsets[first_count])

    old_tail = data[text_pool + old_offsets[-1]:]
    result = data[:text_pool] + b"".join(encoded) + old_tail
    struct.pack_into("<I", result, 4, len(result))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(result)
    print(f"{output}: {len(translated)} lines, {len(data)} -> {len(result)} bytes")


def extract_directory(source, output):
    if not source.is_dir():
        raise ValueError(f"source is not a directory: {source}")
    files = sorted(path for path in source.rglob("*.logo") if path.is_file())
    for path in files:
        relative = Path(str(path.relative_to(source)) + ".txt")
        extract(path, output / relative)
    print(f"Extracted {len(files)} LOGO files")


def rebuild_directory(source, translation, output):
    if not source.is_dir():
        raise ValueError(f"source is not a directory: {source}")
    if not translation.is_dir():
        raise ValueError(f"translation is not a directory: {translation}")
    encode = make_translation_encoder()
    files = sorted(translation.rglob("*.logo.txt"))
    for text_path in files:
        relative = text_path.relative_to(translation).with_suffix("")
        original = source / relative
        if not original.is_file():
            raise FileNotFoundError(f"missing original LOGO: {original}")
        rebuild(original, text_path, output / relative, encode)
    print(f"Rebuilt {len(files)} translated LOGO files")


def main():
    parser = argparse.ArgumentParser(
        usage="logo.py e SOURCE_DIR TEXT_DIR | "
              "logo.py w SOURCE_DIR TEXT_DIR OUTPUT_DIR"
    )
    sub = parser.add_subparsers(dest="mode", required=True)
    extract_parser = sub.add_parser("e")
    extract_parser.add_argument("source", type=Path)
    extract_parser.add_argument("output", type=Path)
    write_parser = sub.add_parser("w")
    write_parser.add_argument("source", type=Path)
    write_parser.add_argument("translation", type=Path)
    write_parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.mode == "e":
        extract_directory(args.source, args.output)
    else:
        rebuild_directory(args.source, args.translation, args.output)


if __name__ == "__main__":
    main()
