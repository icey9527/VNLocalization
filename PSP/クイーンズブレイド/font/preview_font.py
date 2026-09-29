import argparse
from pathlib import Path

from PIL import Image


PIXEL_OFFSET = 0x260
WIDTH_BYTES = 0x80
TILE_SIZE = 16


def palette_ranks(data):
    _, clut_offset, _, _ = __import__("struct").unpack_from("<4I", data)
    alpha = [data[clut_offset + index * 4 + 3] for index in range(16)]
    ranks = [0] * 16
    for rank, index in enumerate(sorted(range(16), key=alpha.__getitem__)):
        ranks[index] = rank * 17
    return ranks


def glyph_pixels(data, index, columns, ranks):
    tile_x, tile_y = index % columns, index // columns
    pixels = []
    for y in range(TILE_SIZE):
        row_y = tile_y * TILE_SIZE + y
        for x in range(TILE_SIZE):
            row_x = tile_x * 8 + x // 2
            value = data[PIXEL_OFFSET + row_y * WIDTH_BYTES + row_x]
            pixels.append(ranks[(value >> (4 * (x & 1))) & 0xF])
    return pixels


def render(data, columns, start, count, scale, output):
    rows = (count + columns - 1) // columns
    image = Image.new("L", (columns * TILE_SIZE, rows * TILE_SIZE))
    ranks = palette_ranks(data)
    for position in range(count):
        index = start + position
        x = (position % columns) * TILE_SIZE
        y = (position // columns) * TILE_SIZE
        glyph = Image.frombytes("L", (TILE_SIZE, TILE_SIZE),
                                bytes(glyph_pixels(data, index, columns, ranks)))
        image.paste(glyph, (x, y))
    image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST).save(output)


def main():
    parser = argparse.ArgumentParser(description="Render Queen's Blade 0002.bin glyphs.")
    parser.add_argument("font", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--columns", type=int, choices=(14, 16), default=16)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--count", type=int, default=448)
    parser.add_argument("--scale", type=int, default=2)
    args = parser.parse_args()
    data = args.font.read_bytes()
    if len(data) < PIXEL_OFFSET + WIDTH_BYTES * TILE_SIZE:
        parser.error("font file is too short")
    render(data, args.columns, args.start, args.count, args.scale, args.output)
    print(args.output)


if __name__ == "__main__":
    main()
