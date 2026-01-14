#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def load_table(path: Path) -> dict[int, str]:
    m = {}
    for line in path.read_text(encoding='utf-16').splitlines():
        if '=' not in line:
            continue
        k, v = line.split('=', 1)
        k = k.strip()
        if not k:
            continue
        try:
            m[int(k)] = v.rstrip('\r\n')
        except:
            pass
    return m


def render_mask(char: str, font: ImageFont.FreeTypeFont, size=(16, 16)) -> list[int]:
    img = Image.new('L', size, 0)
    draw = ImageDraw.Draw(img)
    draw.text((0, 0), char, font=font, fill=255)  # 默认位置：左上角(0,0)
    px = img.load()
    return [1 if px[i % 16, i // 16] > 127 else 0 for i in range(256)]


def shift_mask(mask: list[int], dx: int, dy: int) -> list[int]:
    out = [0] * 256
    for y in range(16):
        ny = y + dy
        if ny < 0 or ny >= 16:
            continue
        for x in range(16):
            nx = x + dx
            if nx < 0 or nx >= 16:
                continue
            if mask[y * 16 + x]:
                out[ny * 16 + nx] = 1
    return out


def compose_pixels(char: str, font: ImageFont.FreeTypeFont, shadow_dx=1, shadow_dy=0, shadow_thickness=1) -> list[int]:
    main = render_mask(char, font)
    shadow = [0] * 256
    for k in range(shadow_thickness):
        s = shift_mask(main, shadow_dx + k, shadow_dy)
        shadow = [1 if (shadow[i] or s[i]) else 0 for i in range(256)]
    return [2 if main[i] else (1 if shadow[i] else 0) for i in range(256)]  # 0背景 1阴影 2主体


def encode_tile_2bpp(pixels: list[int]) -> bytes:
    out = bytearray(64)
    for tile in range(4):
        tx = (tile & 1) * 8
        ty = (tile >> 1) * 8
        for row in range(8):
            base = (ty + row) * 16 + tx
            for half in range(2):
                x0 = base + half * 4
                b = 0
                b |= (pixels[x0 + 0] & 3) << 0
                b |= (pixels[x0 + 1] & 3) << 2
                b |= (pixels[x0 + 2] & 3) << 4
                b |= (pixels[x0 + 3] & 3) << 6
                out[tile * 16 + row * 2 + half] = b
    return bytes(out)


def generate_font(tbl: Path, ttf: Path, out_dir: Path, font_size=13, shadow_dx=1, shadow_dy=0, shadow_thickness=1):
    table = load_table(tbl)
    if not table:
        raise SystemExit("empty table")

    font = ImageFont.truetype(str(ttf), font_size)
    out_dir.mkdir(parents=True, exist_ok=True)

    max_idx = max(table.keys())
    fallback = '　'  # 全角空格
    remap = [0, 2, 1]  # 0背景->0, 1阴影->2, 2主体->1

    data = bytearray()
    for i in range(max_idx + 1):
        ch = table.get(i, fallback)
        px = compose_pixels(ch, font, shadow_dx, shadow_dy, shadow_thickness)
        px = [remap[p] for p in px]
        data.extend(encode_tile_2bpp(px))

        if (i + 1) % 1000 == 0:
            print(f"{i + 1}/{max_idx + 1}")

    out_path = out_dir / "00000255.bin"
    out_path.write_bytes(bytes.fromhex("464E5404") + data)
    print(out_path)


if __name__ == '__main__':
    # 用法也可以自己改成 sys.argv 版；你现在习惯写死参数我就保持最短
    generate_font(
        tbl=Path('pm4_gbk.tbl'),
        ttf=Path('font.ttf'),
        out_dir=Path(r'I:/研究/nds/pack/output/NZ'),
        font_size=13,
        shadow_dx=1,
        shadow_dy=0,
        shadow_thickness=1
    )