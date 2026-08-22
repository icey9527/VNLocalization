import argparse
import struct
from pathlib import Path

from PIL import Image


def dump(source, target, columns, scale, high):
    data = source.read_bytes()
    width, height, pixels = struct.unpack_from('<HH', data, 4)[0], struct.unpack_from('<HH', data, 6)[0], data[0x50:]
    count = len(pixels) // 128
    alpha = [data[0x13 + i * 4] for i in range(16)]
    output = Image.new('RGB', (columns * 16, ((count + columns - 1) // columns) * 16), (0, 0, 0))
    dst = output.load()
    for glyph in range(count):
        off = (glyph >> 1) * 256 + (glyph & 1) * 8
        ox, oy = (glyph % columns) * 16, (glyph // columns) * 16
        for y in range(16):
            for x in range(16):
                b = pixels[off + y * 16 + (x >> 1)]
                n = b >> 4 if high ^ bool(x & 1) else b & 15
                dst[ox + x, oy + y] = (alpha[n],) * 3
    if scale != 1:
        output = output.resize((output.width * scale, output.height * scale), Image.Resampling.NEAREST)
    target.parent.mkdir(parents=True, exist_ok=True)
    output.save(target)
    print('%s: %d tiles, %dx%d' % (target, count, output.width, output.height))


def main():
    p = argparse.ArgumentParser(usage='font_dump.py input.ext output.png [--columns 16] [--scale 4] [--high-nibble]')
    p.add_argument('input', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--columns', type=int, default=16)
    p.add_argument('--scale', type=int, default=4)
    p.add_argument('--high-nibble', action='store_true')
    a = p.parse_args()
    dump(a.input, a.output, a.columns, a.scale, a.high_nibble)


if __name__ == '__main__':
    main()
