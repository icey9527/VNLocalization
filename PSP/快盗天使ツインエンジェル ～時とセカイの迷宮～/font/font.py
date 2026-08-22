import argparse
import struct
from pathlib import Path

import freetype
import numpy as np
from PIL import Image


INDEX_SIZE = 10531
TILE_BIAS = 2
TAIL_TILES = 2
PALETTES = (
    (0, 32, 16, 207, 127, 255, 223, 191, 80, 158, 64, 156, 96, 48, 239, 112),
    (0, 16, 48, 158, 79, 255, 64, 127, 206, 199, 191, 143, 32, 96, 111, 239),
    (0, 32, 16, 207, 127, 255, 223, 191, 97, 159, 64, 143, 96, 48, 239, 175),
)


def read_tbl(path):
    raw = path.read_bytes()
    text = raw.decode('utf-16') if raw[:2] in (b'\xff\xfe', b'\xfe\xff') else raw.decode('utf-8-sig')
    rows = []
    codes = set()
    for number, line in enumerate(text.splitlines(), 1):
        if not line or line[0] in '#;':
            continue
        if '=' not in line:
            raise ValueError('line %d: expected CODE=CHAR' % number)
        key, char = line.split('=', 1)
        try:
            code = int(key, 16)
        except ValueError:
            raise ValueError('line %d: invalid code' % number) from None
        if not 0 <= code <= 0xFFFF or len(char) > 1:
            raise ValueError('line %d: invalid character' % number)
        if code in codes:
            raise ValueError('line %d: duplicate code %04X' % (number, code))
        codes.add(code)
        rows.append((code, char))
    if not rows:
        raise ValueError('empty table')
    return rows


def sjis_jis(code):
    if code < 0x100:
        return code
    lead, trail = code >> 8, code & 255
    if not (0x81 <= lead <= 0x9F or 0xE0 <= lead <= 0xFC) or trail == 0x7F or not 0x40 <= trail <= 0xFC:
        return -1
    row = (lead - (0x81 if lead <= 0x9F else 0xC1)) * 2 + 0x21
    return ((row + 1) << 8 | trail - 0x7E) if trail >= 0x9F else (row << 8 | trail - (0x20 if trail > 0x7F else 0x1F))


def font_index(sjis):
    if sjis < 0x100:
        return sjis
    lead = sjis >> 8
    if 0x81 <= lead <= 0x9F:
        return sjis - 0x8140
    if 0xE0 <= lead <= 0xFC:
        return sjis - 0xC182
    return -1


def make_tables(rows):
    cmap = [0] * INDEX_SIZE
    jis2ucs = [0] * 65536
    ucs2jis = [0] * 65536
    used = set()
    for logical, (code, char) in enumerate(rows):
        jis = sjis_jis(code)
        index = font_index(code)
        if jis < 0 or not 0 <= index < INDEX_SIZE:
            raise ValueError('%04X is outside the supported Shift-JIS range' % code)
        if index in used:
            raise ValueError('%04X collides at font index %d' % (code, index))
        if logical > 0xFFFF:
            raise ValueError('too many glyphs')
        used.add(index)
        cmap[index] = logical
        if char and ord(char) < 0x10000:
            cp = ord(char)
            jis2ucs[jis] = cp
            if not ucs2jis[cp]:
                ucs2jis[cp] = jis
    return struct.pack('<%dH' % INDEX_SIZE, *cmap), struct.pack('<65536H', *jis2ucs), struct.pack('<65536H', *ucs2jis)


def render(rows, font_path, size, offset, threshold):
    count = len(rows) + TILE_BIAS + TAIL_TILES
    count += count & 1
    height = count // 2 * 16
    if height > 0xFFFF:
        raise ValueError('font texture is too tall')

    image = Image.new('L', (32, height), 0)
    face = freetype.Face(str(font_path))
    face.set_pixel_sizes(0, size)
    ascender = face.size.ascender >> 6
    descender = face.size.descender >> 6
    baseline = (16 - (ascender - descender)) // 2 + ascender + offset

    for logical, (_, char) in enumerate(rows):
        if not char:
            continue

        face.load_char(char, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_NORMAL)
        bitmap = face.glyph.bitmap
        width = int(bitmap.width)
        rows_count = int(bitmap.rows)
        pitch = int(bitmap.pitch)

        if width == 0 or rows_count == 0:
            continue

        if width >= 16:
            glyph_x = 0
        else:
            glyph_x = int(face.glyph.bitmap_left)
            glyph_x = max(0, min(glyph_x, 16 - width))

        glyph_y = baseline - int(face.glyph.bitmap_top)
        tile = logical + TILE_BIAS
        tile_x = (tile & 1) * 16
        tile_y = (tile >> 1) * 16
        orientation = 1
        if pitch < 0:
            orientation = -1

        glyph = Image.frombytes(
            'L',
            (width, rows_count),
            bytes(bitmap.buffer),
            'raw',
            'L',
            abs(pitch),
            orientation,
        )

        crop_left = max(0, -glyph_x)
        crop_top = max(0, -glyph_y)
        crop_right = min(width, 16 - glyph_x)
        crop_bottom = min(rows_count, 16 - glyph_y)

        if crop_left >= crop_right or crop_top >= crop_bottom:
            continue

        glyph = glyph.crop((crop_left, crop_top, crop_right, crop_bottom))
        paste_x = tile_x + glyph_x + crop_left
        paste_y = tile_y + glyph_y + crop_top
        image.paste(glyph, (paste_x, paste_y))

    if threshold:
        image = image.point(lambda value: 0 if value < threshold else min(255, (value - threshold) * 255 // (255 - threshold)))

    return image, count


def header(height, palette):
    value = bytearray(0x50)
    struct.pack_into('<HBBHHII', value, 0, 1, 2, 3, 32, height, 0x10, 0x50)
    for i, alpha in enumerate(palette):
        value[0x10 + i * 4:0x14 + i * 4] = bytes((255, 255, 255, alpha)) if i else b'\0\0\0\0'
    return value


def write_ext(path, image, count, palette):
    height = image.height
    values = np.arange(256, dtype=np.int16)[:, None]
    alphas = np.asarray(palette, dtype=np.int16)[None, :]
    lookup = np.abs(values - alphas).argmin(axis=1).astype(np.uint8)
    pixels = np.asarray(image, dtype=np.uint8)
    indexed = lookup[pixels]
    pairs = indexed.reshape(count // 2, 16, 16, 2)
    packed = pairs[:, :, :, 1] << 4 | pairs[:, :, :, 0]
    path.write_bytes(header(height, palette) + packed.tobytes())


def generate(table, font_path, output, size, offset, threshold):
    rows = read_tbl(table)
    cmap, jis2ucs, ucs2jis = make_tables(rows)
    image, count = render(rows, font_path, size, offset, threshold)
    ccc, font = output / 'CCC', output / 'font'
    ccc.mkdir(parents=True, exist_ok=True)
    font.mkdir(parents=True, exist_ok=True)
    (ccc / 'jis2ucs.bin').write_bytes(jis2ucs)
    (ccc / 'ucs2jis.bin').write_bytes(ucs2jis)
    (font / 'font_16_a.txt').write_bytes(cmap)
    for n in range(3):
        write_ext(font / ('font_16_a%d.ext' % n), image, count, PALETTES[n])
    print('%s: %d tiles, %d glyphs, %d CCC characters' % (output, count, sum(bool(char) for _, char in rows), sum(bool(char) and ord(char) < 0x10000 for _, char in rows)))


def main():
    p = argparse.ArgumentParser(usage='font.py gasj.tbl font.ttf output [--size 16] [--offset 0] [--threshold 0]')
    p.add_argument('table', type=Path)
    p.add_argument('font', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--size', type=int, default=16)
    p.add_argument('--offset', type=int, default=0)
    p.add_argument('--threshold', type=int, default=0)
    a = p.parse_args()
    generate(a.table, a.font, a.output, a.size, a.offset, a.threshold)


if __name__ == '__main__':
    main()
