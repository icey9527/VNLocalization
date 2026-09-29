import argparse
import struct
from pathlib import Path

from char import make_translation_encoder
from logo import escape_text, read_lines


TEXT_SECTIONS = (b"Strg", b"Sent")

FIXH_LAYOUTS = {
    (0x7C, 4): (0x10, 26, 0x10),
    (0x5C, 0x00010003): (0x0C, 20, 0x0C),
}


def parse_fixh(data, decode_text=True):
    if len(data) < 0x0C or data[:4] != b"Fixh":
        raise ValueError("not a Fixh file")
    header_size, version = struct.unpack_from("<II", data, 4)
    layout = FIXH_LAYOUTS.get((header_size, version))
    if layout is None:
        raise ValueError("unsupported Fixh header")
    offset_table, section_count, string_header_size = layout
    if len(data) < header_size:
        raise ValueError("truncated Fixh header")
    offsets = list(struct.unpack_from(
        f"<{section_count}I", data, offset_table
    ))
    if offsets[0] != header_size or any(a >= b for a, b in zip(offsets, offsets[1:])):
        raise ValueError("invalid Fixh section table")
    if offsets[-1] >= len(data):
        raise ValueError("Fixh section is outside the file")

    sections = []
    text_sections = []
    for index, start in enumerate(offsets):
        end = offsets[index + 1] if index + 1 < len(offsets) else len(data)
        section = data[start:end]
        if len(section) < 8:
            raise ValueError(f"Fixh section {index} is too small")
        logical_size = struct.unpack_from("<I", section, 4)[0]
        if logical_size > len(section) or len(section) - logical_size > 3:
            raise ValueError(f"Fixh section {index} has invalid size")
        sections.append(section)
        if section[:4] in TEXT_SECTIONS:
            text_sections.append((
                index,
                parse_string_section(section, string_header_size, decode_text),
            ))
    if [sections[i][:4] for i, _ in text_sections] != list(TEXT_SECTIONS):
        raise ValueError("Fixh Strg/Sent sections are missing or reordered")
    return sections, text_sections, layout


def parse_string_section(section, header_size, decode_text=True):
    magic = section[:4]
    logical_size, count = struct.unpack_from("<II", section, 4)
    table_end = header_size + count * 4
    if (header_size == 0x10 and struct.unpack_from("<I", section, 0x0C)[0] != 0) or \
            table_end > logical_size:
        raise ValueError(f"invalid {magic.decode()} header")
    pointers = list(struct.unpack_from(
        f"<{count}I", section, header_size
    ))
    strings = []
    for index, offset in enumerate(pointers):
        if offset < table_end or offset >= logical_size:
            raise ValueError(f"{magic.decode()} pointer {index} is invalid")
        end = section.find(b"\0", offset, logical_size)
        if end < 0:
            raise ValueError(f"{magic.decode()} string {index} is unterminated")
        raw = section[offset:end]
        if decode_text:
            try:
                strings.append(raw.decode("cp932"))
            except UnicodeDecodeError as error:
                raise ValueError(f"{magic.decode()} string {index}: {error}") from None
        else:
            strings.append(raw)
    return strings


def build_string_section(magic, encoded, header_size):
    encoded = [raw + b"\0" for raw in encoded]
    table_end = header_size + len(encoded) * 4
    pointers = []
    cursor = table_end
    for raw in encoded:
        pointers.append(cursor)
        cursor += len(raw)
    section = bytearray(struct.pack("<4sII", magic, cursor, len(encoded)))
    if header_size == 0x10:
        section += struct.pack("<I", 0)
    section += struct.pack(f"<{len(pointers)}I", *pointers)
    section += b"".join(encoded)
    section += b"\0" * ((-len(section)) & 3)
    return section


def extract_file(source, output):
    _, text_sections, _ = parse_fixh(source.read_bytes())
    strings = [text for _, group in text_sections for text in group]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "".join(escape_text(text) + "\n" for text in strings),
        encoding="utf-8-sig",
        newline="",
    )
    counts = "+".join(str(len(group)) for _, group in text_sections)
    print(f"{output}: {counts} lines")


def rebuild_file(source, translation, output, encode):
    original = source.read_bytes()
    sections, text_sections, layout = parse_fixh(original, decode_text=False)
    offset_table, section_count, string_header_size = layout
    lines = read_lines(translation)
    expected = sum(len(group) for _, group in text_sections)
    if len(lines) != expected:
        raise ValueError(f"{translation}: expected {expected} lines, got {len(lines)}")

    cursor = 0
    for section_index, source_strings in text_sections:
        count = len(source_strings)
        new_strings = lines[cursor:cursor + count]
        encoded = [encode(text) for text in new_strings]
        sections[section_index] = build_string_section(
            sections[section_index][:4], encoded, string_header_size
        )
        cursor += count

    header_size = struct.unpack_from("<I", original, 4)[0]
    result = bytearray(original[:header_size])
    offsets = []
    for section in sections:
        offsets.append(len(result))
        result += section
    struct.pack_into(
        f"<{section_count}I", result, offset_table, *offsets
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(result)
    print(f"{output}: {expected} lines, {len(original)} -> {len(result)} bytes")


def extract_directory(source, output):
    if not source.is_dir():
        raise ValueError(f"source is not a directory: {source}")
    files = sorted(path for path in source.rglob("*.fixh") if path.is_file())
    for path in files:
        relative = Path(str(path.relative_to(source)) + ".txt")
        extract_file(path, output / relative)
    print(f"Extracted {len(files)} Fixh files")


def rebuild_directory(source, translation, output):
    if not source.is_dir() or not translation.is_dir():
        raise ValueError("source and translation must be directories")
    files = sorted(translation.rglob("*.fixh.txt"))
    encode = make_translation_encoder()
    for text_path in files:
        relative = text_path.relative_to(translation).with_suffix("")
        original = source / relative
        if not original.is_file():
            raise FileNotFoundError(f"missing original Fixh: {original}")
        rebuild_file(original, text_path, output / relative, encode)
    print(f"Rebuilt {len(files)} translated Fixh files")


def main():
    parser = argparse.ArgumentParser(
        usage="fixh.py e SOURCE_DIR TEXT_DIR | "
              "fixh.py w SOURCE_DIR TEXT_DIR OUTPUT_DIR"
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
