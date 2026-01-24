#!/usr/bin/env python3
"""IPG图像格式转换工具"""

import sys
import struct
from pathlib import Path
from PIL import Image


def decode_ipg(ipg_file, png_file):
    """IPG -> PNG"""
    with open(ipg_file, 'rb') as f:
        assert f.read(4) == b'IPG0', "Invalid IPG file"
        width, height = struct.unpack('<II', f.read(8))
        data = f.read(width * height * 4)
    
    Image.frombytes('RGBA', (width, height), data).save(png_file)
    print(f"✓ {ipg_file.name} -> {png_file.name}")


def encode_ipg(png_file, ipg_file):
    """PNG -> IPG"""
    img = Image.open(png_file).convert('RGBA')
    width, height = img.size
    
    with open(ipg_file, 'wb') as f:
        f.write(b'IPG0')
        f.write(struct.pack('<II', width, height))
        f.write(img.tobytes())
    
    print(f"✓ {png_file.name} -> {ipg_file.name}")


def main():
    if len(sys.argv) != 4:
        print("用法: python 1.py [d|e] <输入文件夹> <输出文件夹>")
        sys.exit(1)
    
    mode, input_dir, output_dir = sys.argv[1:]
    input_path, output_path = Path(input_dir), Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    if mode == 'd':
        for f in input_path.glob('*.ipg'):
            decode_ipg(f, output_path / f"{f.stem}.png")
    elif mode == 'e':
        for f in input_path.glob('*.png'):
            encode_ipg(f, output_path / f"{f.stem}.ipg")
    else:
        print("模式必须是 'd'(解码) 或 'e'(编码)")


if __name__ == '__main__':
    main()