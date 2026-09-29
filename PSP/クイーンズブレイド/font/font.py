import argparse
import struct
from pathlib import Path

import freetype


WIDTH_BYTES = 0x80
TILES_PER_ROW = 14
KEEP_FIRST = 0x81A7
KEEP_LAST = 0x879C
AUX_TABLE_SIZE = 0x10


def read_table(path):
    raw = path.read_bytes()
    text = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8-sig")
    rows = []
    seen = set()
    for number, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith(("#", ";", "//")):
            continue
        if "=" not in line:
            raise ValueError(f"line {number}: expected CODE=CHAR")
        key, char = line.split("=", 1)
        char = char.split(";", 1)[0].strip()
        try:
            code = int(key.strip(), 16)
        except ValueError:
            raise ValueError(f"line {number}: invalid code") from None
        if not 0 <= code <= 0xFFFF or len(char) > 1:
            raise ValueError(f"line {number}: invalid entry")
        if code in seen:
            raise ValueError(f"line {number}: duplicate code {code:04X}")
        seen.add(code)
        rows.append((code, char))
    return rows


def font_layout(data):
    count, clut_offset, pixel_offset, base = struct.unpack_from("<4I", data)
    if count != 16 or clut_offset < 0x10 + AUX_TABLE_SIZE or pixel_offset < clut_offset + 0x40:
        raise ValueError("not a supported 4bpp font")
    pixel_size = len(data) - pixel_offset
    if pixel_size <= 0 or pixel_size % WIDTH_BYTES:
        raise ValueError("unexpected font pixel area")
    glyph_count = (pixel_size // WIDTH_BYTES // 16) * TILES_PER_ROW
    extra_count = (clut_offset - 0x10 - AUX_TABLE_SIZE) // 2
    if extra_count < 0:
        raise ValueError("font extension table is outside the header")
    alpha = [data[clut_offset + i * 4 + 3] for i in range(16)]
    lookup = [
        min(
            range(16),
            key=lambda i: abs(alpha[i] - value),
        )
        for value in range(256)
    ]
    return pixel_offset, base, glyph_count, extra_count, lookup


def render_glyph(face, char, offset):
    tile = bytearray(256)
    if not char:
        return tile
    face.load_char(char, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_NORMAL)
    bitmap = face.glyph.bitmap
    width, height, pitch = int(bitmap.width), int(bitmap.rows), int(bitmap.pitch)
    if not width or not height:
        return tile
    baseline = (face.size.ascender >> 6) + offset
    left = int(face.glyph.bitmap_left) if width < 16 else 0
    top = baseline - int(face.glyph.bitmap_top)
    source = bytes(bitmap.buffer)
    stride = abs(pitch)
    for y in range(height):
        dy = top + y
        if not 0 <= dy < 16:
            continue
        sy = y if pitch >= 0 else height - 1 - y
        for x in range(width):
            dx = left + x
            if 0 <= dx < 16:
                tile[dy * 16 + dx] = source[sy * stride + x]
    return tile


def write_glyph(data, index, pixels, lookup, threshold, pixel_offset):
    tile_x, tile_y = index % TILES_PER_ROW, index // TILES_PER_ROW
    for y in range(16):
        dst = pixel_offset + (tile_y * 16 + y) * WIDTH_BYTES + tile_x * 8
        for x in range(0, 16, 2):
            left, right = pixels[y * 16 + x], pixels[y * 16 + x + 1]
            if threshold:
                left = 0 if left < threshold else (left - threshold) * 255 // (255 - threshold)
                right = 0 if right < threshold else (right - threshold) * 255 // (255 - threshold)
            data[dst + x // 2] = lookup[left] | (lookup[right] << 4)


def generate(font_path, table_path, original_path, output_path, size, offset, threshold):
    rows = read_table(table_path)
    data = bytearray(original_path.read_bytes())
    pixel_offset, base_glyphs, glyph_count, extra_glyphs, lookup = font_layout(data)
    if len(rows) > glyph_count:
        raise ValueError(f"table has {len(rows)} entries; the file format supports {glyph_count}")
    face = freetype.Face(str(font_path))
    face.set_pixel_sizes(0, size)
    rendered = kept = 0
    for index, (code, char) in enumerate(rows):
        if KEEP_FIRST <= code <= KEEP_LAST:
            kept += 1
            continue
        write_glyph(data, index, render_glyph(face, char, offset), lookup, threshold, pixel_offset)
        rendered += 1

    # Only slots 3600..3863 are selected by the 264-entry table stored inside
    # the font file. Later physical slots are rendered but have no such table.
    extras = rows[base_glyphs:base_glyphs + extra_glyphs]
    if len(rows) >= base_glyphs and len(extras) != extra_glyphs:
        raise ValueError(f"extended table must contain all {extra_glyphs} entries")
    for i, (code, _) in enumerate(extras):
        struct.pack_into(">H", data, 0x10 + i * 2, code)

    output_path.write_bytes(data)
    print(
        f"{output_path}: {rendered} rendered, {kept} preserved, "
        f"{len(rows)} table entries"
    )


def main():
    parser = argparse.ArgumentParser(
        usage="font.py FONT TABLE ORIGINAL OUTPUT [--size 16] "
              "[--offset 0] [--threshold 0]"
    )
    parser.add_argument("font", type=Path)
    parser.add_argument("table", type=Path)
    parser.add_argument("original", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--size", type=int, default=15)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--threshold", type=int, default=0)
    args = parser.parse_args()
    if (not 1 <= args.size <= 32 or not -16 <= args.offset <= 16
            or not 0 <= args.threshold < 255):
        parser.error("invalid rendering option")
    generate(
        args.font, args.table, args.original, args.output,
        args.size, args.offset, args.threshold,
    )


if __name__ == "__main__":
    main()
