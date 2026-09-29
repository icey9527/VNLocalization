import argparse
import struct
from pathlib import Path

from char import make_translation_encoder


HEADER_SIZE = 0x14
MISSING = 0xFFFF


def parse_bin(data, decode_text=True):
    if len(data) < HEADER_SIZE:
        raise ValueError("file is too small")
    header = list(struct.unpack_from("<10H", data))
    boundaries = [value for value in header[3:] if value != MISSING]
    old_layout = bool(boundaries) and not any(
        a >= b for a, b in zip(boundaries, boundaries[1:])
    )
    new_layout = False
    if old_layout:
        reference_start, reference_end, pool = header[7:10]
    elif (header[6] < header[7] <= header[8] < len(data) and
          (header[7] - header[6]) % 2 == 0):
        # Queen's Blade battle BINs keep the text references in fields 6/7;
        # field 8 is the CP932 pool.
        reference_start, reference_end, pool = header[6:8] + [header[8]]
        new_layout = True
    else:
        raise ValueError("invalid section boundaries")
    if MISSING in (reference_start, reference_end, pool):
        raise ValueError("text sections are missing")
    if not (HEADER_SIZE <= reference_start <= reference_end <= pool < len(data)):
        raise ValueError("invalid text section boundaries")
    if (reference_end - reference_start) & 1:
        raise ValueError("text reference table has an odd size")
    if not new_layout and data[pool] != 0:
        raise ValueError("text pool has no empty-string sentinel")

    references = list(struct.unpack_from(
        f"<{(reference_end - reference_start) // 2}H", data, reference_start
    ))
    offsets = sorted(set(references) - ({0} if old_layout else set()))
    strings = []
    for index, offset in enumerate(offsets):
        start = pool + offset
        if start < pool or start >= len(data):
            raise ValueError(f"text offset {index} is outside the file")
        if start > pool and data[start - 1] != 0:
            raise ValueError(f"text offset {index} is not at a string boundary")
        end = data.find(b"\0", start)
        if end < 0:
            raise ValueError(f"text {index} is unterminated")
        raw = data[start:end]
        if decode_text:
            try:
                strings.append(raw.decode("cp932"))
            except UnicodeDecodeError as error:
                raise ValueError(f"text {index} is not valid CP932: {error}") from None
        else:
            strings.append(raw)

    return header, references, offsets, strings


def escape_text(text):
    return text.replace("\\", "\\\\").replace("/", "\\n")


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
            output.append("/")
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
    return [unescape_text(line, index + 1) for index, line in enumerate(lines)]


def extract_file(source, output):
    _, _, _, strings = parse_bin(source.read_bytes())
    if not strings or not any(strings):
        return False
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "".join(escape_text(text) + "\n" for text in strings),
        encoding="utf-8-sig",
        newline="",
    )
    print(f"{output}: {len(strings)} lines")
    return True


def rebuild_file(source, translation, output, encode):
    original_data = source.read_bytes()
    header, references, old_offsets, source_strings = parse_bin(
        original_data, decode_text=False
    )
    translated = read_lines(translation)
    if len(translated) != len(source_strings):
        raise ValueError(
            f"{translation}: expected {len(source_strings)} lines, got {len(translated)}"
        )
    encoded = [encode(text) + b"\0" for text in translated]

    new_layout = (header[6] < header[7] <= header[8] < len(original_data)
                  and (header[7] - header[6]) % 2 == 0
                  and header[5] < header[6])
    new_offsets = []
    cursor = 0 if new_layout else 1
    for raw in encoded:
        if cursor > 0xFFFF:
            raise ValueError(f"{translation}: text pool exceeds 16-bit offsets")
        new_offsets.append(cursor)
        cursor += len(raw)
    mapping = dict(zip(old_offsets, new_offsets))
    new_references = [mapping.get(value, 0) for value in references]

    if new_layout:
        reference_start, reference_end, pool = header[6:8] + [header[8]]
    else:
        reference_start, reference_end, pool = header[7:10]
    result = bytearray(original_data[:pool + (0 if new_layout else 1)])
    struct.pack_into(
        f"<{len(new_references)}H", result, reference_start, *new_references
    )
    result += b"".join(encoded)
    result += b"\0" * ((-len(result)) & 3)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(result)
    print(f"{output}: {len(translated)} lines, {len(original_data)} -> {len(result)} bytes")


def extract_directory(source, output):
    if not source.is_dir():
        raise ValueError(f"source is not a directory: {source}")
    found = 0
    for path in sorted(path for path in source.rglob("*.bin") if path.is_file()):
        try:
            relative = Path(str(path.relative_to(source)) + ".txt")
            found += extract_file(path, output / relative)
        except ValueError:
            continue
    print(f"Extracted {found} text BIN files")


def rebuild_directory(source, translation, output):
    if not source.is_dir() or not translation.is_dir():
        raise ValueError("source and translation must be directories")
    encode = make_translation_encoder()
    files = sorted(translation.rglob("*.bin.txt"))
    for text_path in files:
        relative = text_path.relative_to(translation).with_suffix("")
        original = source / relative
        if not original.is_file():
            raise FileNotFoundError(f"missing original BIN: {original}")
        rebuild_file(original, text_path, output / relative, encode)
    print(f"Rebuilt {len(files)} translated BIN files")


def main():
    parser = argparse.ArgumentParser(
        usage="bin.py e SOURCE_DIR TEXT_DIR | bin.py w SOURCE_DIR TEXT_DIR OUTPUT_DIR"
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
