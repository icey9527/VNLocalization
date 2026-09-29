"""Convert battle.bin raw texture resources using the verified linear layouts.

battle.bin 内的 .bin 子文件分两类：
- 裸资源：1024 字节 CLUT 调色板 + 8bpp 裸像素，与 graphic.bin 同格式；
- 容器：头部第一个 u32 等于文件大小，内容为精灵/动画指令流，不是图片，跳过。
"""
from pathlib import Path
import argparse
import struct
from PIL import Image

PALETTE = 256 * 4
LAYOUTS = {
    # size: (width, height)
    66560: (256, 256),   # 1024 + 256*256
    33792: (128, 256),   # 1024 + 128*256（与 convert_graphic.py 中 33792 一致）
}

def fix_alpha(a: int) -> int:
    return max(0, min(255, a * 2 - 1))

def is_container(data: bytes) -> bool:
    return len(data) >= 4 and struct.unpack_from('<I', data)[0] == len(data)

def decode(path: Path, output: Path):
    data = path.read_bytes()
    size = len(data)
    if size not in LAYOUTS:
        raise ValueError(f'未知文件大小: {size}' + ('（容器/动画数据，非图片）' if is_container(data) else ''))
    width, height = LAYOUTS[size]
    if len(data) < PALETTE:
        raise ValueError('缺少完整 1024 字节调色板')
    palette = data[:PALETTE]
    pixels = data[PALETTE:]
    if len(pixels) != width * height:
        raise ValueError(f'像素长度 {len(pixels)} 与 {width}×{height} 不符')
    rgba = bytearray()
    for index in pixels:
        r, g, b, a = palette[index * 4:index * 4 + 4]
        rgba.extend((r, g, b, fix_alpha(a)))
    image = Image.frombytes('RGBA', (width, height), bytes(rgba))
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    return width, height

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('input', nargs='?', type=Path, default=Path('extracted/battle.bin'))
    ap.add_argument('--out', type=Path, default=Path('battle.bin'))
    args = ap.parse_args()
    errors = 0
    converted = 0
    skipped = 0
    for path in sorted(args.input.rglob('*.bin')):
        relative = path.relative_to(args.input)
        # 镜像相对路径，避免不同 .lice 目录下同名文件互相覆盖
        target = args.out / relative.with_suffix('.png')
        try:
            w, h = decode(path, target)
            converted += 1
            print(f'{relative}: RGBA+CLUT {w}x{h}')
        except ValueError as exc:
            message = str(exc)
            if '容器' in message:
                skipped += 1
                continue
            errors += 1
            print(f'ERROR {relative}: {exc}')
    print(f'转换 {converted} 张图片，跳过 {skipped} 个动画/容器文件，{errors} 个错误')
    if errors:
        raise SystemExit(f'{errors} 个文件转换失败')

if __name__ == '__main__':
    main()
