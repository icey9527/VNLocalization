#!/usr/bin/env python3
"""
SNCE Sprite Tool - Final Version
NDS uses 1D tile mapping, tiles_per_row is only for PNG export display
"""

import struct
import json
import os
import sys
import argparse
import math
from dataclasses import dataclass, asdict
from typing import List, Tuple, Optional

try:
    from PIL import Image
except ImportError:
    print("Error: pip install Pillow")
    sys.exit(1)


@dataclass
class SpriteFileHeader:
    magic: int
    palette_mode: int
    flags: int
    cell_attr_size: int
    cell_data_size: int
    anim_head_size: int
    anim_frame_size: int
    gfx_size: int
    pal_size: int
    
    FORMAT = '<I HH IIII II'
    SIZE = 0x20
    
    @classmethod
    def unpack(cls, data: bytes):
        return cls(*struct.unpack(cls.FORMAT, data[:cls.SIZE]))
    
    def pack(self) -> bytes:
        return struct.pack(self.FORMAT, self.magic, self.palette_mode, self.flags,
            self.cell_attr_size, self.cell_data_size, self.anim_head_size,
            self.anim_frame_size, self.gfx_size, self.pal_size)


@dataclass
class CellAttr:
    offset_x: int
    offset_y: int
    FORMAT = '<ii'
    SIZE = 8
    
    @classmethod
    def unpack(cls, data: bytes):
        return cls(*struct.unpack(cls.FORMAT, data[:cls.SIZE]))
    
    def pack(self) -> bytes:
        return struct.pack(self.FORMAT, self.offset_x, self.offset_y)


@dataclass
class CellData:
    y_offset: int
    x_offset: int
    attr: int
    param1: int
    param2: int
    tile_index: int
    field_0A: int
    field_0C: int      # 高4位是 shape/size 索引
    
    FORMAT = '<hhH BB HH I'
    SIZE = 16
    
    @classmethod
    def unpack(cls, data: bytes):
        return cls(*struct.unpack(cls.FORMAT, data[:cls.SIZE]))
    
    def pack(self) -> bytes:
        return struct.pack(self.FORMAT, self.y_offset, self.x_offset, self.attr,
            self.param1, self.param2, self.tile_index, self.field_0A, self.field_0C)


@dataclass
class AnimHeader:
    field_00: int
    field_02: int
    field_04: int
    field_08: int
    frame_count: int
    
    FORMAT = '<hh II I'
    SIZE = 16
    
    @classmethod
    def unpack(cls, data: bytes):
        return cls(*struct.unpack(cls.FORMAT, data[:cls.SIZE]))
    
    def pack(self) -> bytes:
        return struct.pack(self.FORMAT, self.field_00, self.field_02,
            self.field_04, self.field_08, self.frame_count)


@dataclass 
class AnimFrame:
    field_00: int
    field_02: int
    field_04: int
    field_08: int
    field_0C: int
    field_10: int
    field_14: int
    
    FORMAT = '<hh IIIII'
    SIZE = 24
    
    @classmethod
    def unpack(cls, data: bytes):
        return cls(*struct.unpack(cls.FORMAT, data[:cls.SIZE]))
    
    def pack(self) -> bytes:
        return struct.pack(self.FORMAT, self.field_00, self.field_02,
            self.field_04, self.field_08, self.field_0C,
            self.field_10, self.field_14)


def rgb555_to_rgb888(color: int) -> Tuple[int, int, int]:
    r = ((color & 0x1F) << 3) | ((color & 0x1F) >> 2)
    g = (((color >> 5) & 0x1F) << 3) | (((color >> 5) & 0x1F) >> 2)
    b = (((color >> 10) & 0x1F) << 3) | (((color >> 10) & 0x1F) >> 2)
    return (r, g, b)


def rgb888_to_rgb555(r: int, g: int, b: int) -> int:
    return (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10)


def parse_palette(pal_data: bytes, is_8bpp: bool = False) -> List[List[Tuple[int, int, int]]]:
    colors_per_pal = 256 if is_8bpp else 16
    bytes_per_pal = colors_per_pal * 2
    num_palettes = max(1, len(pal_data) // bytes_per_pal)
    
    palettes = []
    for p in range(num_palettes):
        palette = []
        for i in range(colors_per_pal):
            offset = p * bytes_per_pal + i * 2
            if offset + 2 <= len(pal_data):
                color = struct.unpack('<H', pal_data[offset:offset+2])[0]
                palette.append(rgb555_to_rgb888(color))
            else:
                palette.append((0, 0, 0))
        palettes.append(palette)
    return palettes


def build_palette(palettes: List[List[Tuple[int, int, int]]]) -> bytes:
    result = bytearray()
    for palette in palettes:
        for r, g, b in palette:
            result.extend(struct.pack('<H', rgb888_to_rgb555(r, g, b)))
    return bytes(result)


def calculate_tiles_per_row(num_tiles: int) -> int:
    """计算合适的每行 tile 数，让图像接近正方形"""
    if num_tiles <= 0:
        return 1
    
    sqrt_tiles = int(math.sqrt(num_tiles))
    
    # 优先使用 2 的幂
    for width in [4, 8, 16, 32, 64, 128]:
        if width >= sqrt_tiles:
            return width
    
    return 128


def render_tilesheet(gfx_data: bytes, palette: List[Tuple[int, int, int]], 
                     tiles_per_row: int, is_8bpp: bool = False) -> Image.Image:
    """渲染 tile sheet"""
    bytes_per_tile = 64 if is_8bpp else 32
    num_tiles = len(gfx_data) // bytes_per_tile
    
    if num_tiles == 0:
        return Image.new('RGBA', (8, 8), (255, 0, 255, 255))
    
    num_rows = (num_tiles + tiles_per_row - 1) // tiles_per_row
    img_width = tiles_per_row * 8
    img_height = num_rows * 8
    
    img = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
    
    for tile_idx in range(num_tiles):
        col = tile_idx % tiles_per_row
        row = tile_idx // tiles_per_row
        
        tile_x = col * 8
        tile_y = row * 8
        
        tile_offset = tile_idx * bytes_per_tile
        tile_data = gfx_data[tile_offset:tile_offset + bytes_per_tile]
        
        if is_8bpp:
            for py in range(8):
                for px in range(8):
                    byte_idx = py * 8 + px
                    if byte_idx < len(tile_data):
                        color_idx = tile_data[byte_idx]
                        if color_idx == 0:
                            img.putpixel((tile_x + px, tile_y + py), (0, 0, 0, 0))
                        elif color_idx < len(palette):
                            img.putpixel((tile_x + px, tile_y + py), palette[color_idx] + (255,))
        else:
            for py in range(8):
                for px in range(0, 8, 2):
                    byte_idx = py * 4 + px // 2
                    if byte_idx < len(tile_data):
                        byte = tile_data[byte_idx]
                        idx_left = byte & 0x0F
                        idx_right = (byte >> 4) & 0x0F
                        
                        if idx_left == 0:
                            img.putpixel((tile_x + px, tile_y + py), (0, 0, 0, 0))
                        elif idx_left < len(palette):
                            img.putpixel((tile_x + px, tile_y + py), palette[idx_left] + (255,))
                        
                        if idx_right == 0:
                            img.putpixel((tile_x + px + 1, tile_y + py), (0, 0, 0, 0))
                        elif idx_right < len(palette):
                            img.putpixel((tile_x + px + 1, tile_y + py), palette[idx_right] + (255,))
    
    return img


def encode_tilesheet(img: Image.Image, palette: List[Tuple[int, int, int]], 
                     is_8bpp: bool = False) -> bytes:
    """编码图像为 tile 数据（行优先）"""
    img = img.convert('RGBA')
    width, height = img.size
    
    tiles_x = (width + 7) // 8
    tiles_y = (height + 7) // 8
    
    color_map = {(0, 0, 0, 0): 0}
    for idx, color in enumerate(palette):
        color_map[color + (255,)] = idx
    
    def find_closest(pixel):
        if len(pixel) == 4 and pixel[3] < 128:
            return 0
        rgb = pixel[:3]
        min_dist = float('inf')
        best = 0
        for idx, pal_color in enumerate(palette):
            if idx == 0:
                continue
            dist = sum((a-b)**2 for a, b in zip(rgb, pal_color))
            if dist < min_dist:
                min_dist = dist
                best = idx
        return best
    
    result = bytearray()
    
    for row in range(tiles_y):
        for col in range(tiles_x):
            tile_x = col * 8
            tile_y = row * 8
            
            if is_8bpp:
                for py in range(8):
                    for px in range(8):
                        abs_x = tile_x + px
                        abs_y = tile_y + py
                        if abs_x < width and abs_y < height:
                            pixel = img.getpixel((abs_x, abs_y))
                            idx = color_map.get(pixel, find_closest(pixel))
                        else:
                            idx = 0
                        result.append(idx)
            else:
                for py in range(8):
                    for px in range(0, 8, 2):
                        abs_x_left = tile_x + px
                        abs_x_right = tile_x + px + 1
                        abs_y = tile_y + py
                        
                        if abs_x_left < width and abs_y < height:
                            pixel = img.getpixel((abs_x_left, abs_y))
                            idx_left = color_map.get(pixel, find_closest(pixel))
                        else:
                            idx_left = 0
                        
                        if abs_x_right < width and abs_y < height:
                            pixel = img.getpixel((abs_x_right, abs_y))
                            idx_right = color_map.get(pixel, find_closest(pixel))
                        else:
                            idx_right = 0
                        
                        result.append((idx_left & 0x0F) | ((idx_right & 0x0F) << 4))
    
    return bytes(result)


class SpriteFile:
    def __init__(self):
        self.header: Optional[SpriteFileHeader] = None
        self.cell_attrs: List[CellAttr] = []
        self.cell_data: List[CellData] = []
        self.anim_headers: List[AnimHeader] = []
        self.anim_frames: List[AnimFrame] = []
        self.gfx_data: bytes = b''
        self.pal_data: bytes = b''
    
    @classmethod
    def load(cls, filepath: str):
        with open(filepath, 'rb') as f:
            data = f.read()
        return cls.parse(data)
    
    @classmethod
    def parse(cls, data: bytes):
        sprite = cls()
        sprite.header = SpriteFileHeader.unpack(data)
        offset = SpriteFileHeader.SIZE
        
        num_cell_attrs = sprite.header.cell_attr_size // CellAttr.SIZE
        for _ in range(num_cell_attrs):
            sprite.cell_attrs.append(CellAttr.unpack(data[offset:]))
            offset += CellAttr.SIZE
        
        num_cells = sprite.header.cell_data_size // CellData.SIZE
        for _ in range(num_cells):
            sprite.cell_data.append(CellData.unpack(data[offset:]))
            offset += CellData.SIZE
        
        num_anims = sprite.header.anim_head_size // AnimHeader.SIZE
        for _ in range(num_anims):
            sprite.anim_headers.append(AnimHeader.unpack(data[offset:]))
            offset += AnimHeader.SIZE
        
        total_frames = sum(ah.frame_count for ah in sprite.anim_headers)
        for _ in range(total_frames):
            sprite.anim_frames.append(AnimFrame.unpack(data[offset:]))
            offset += AnimFrame.SIZE
        
        sprite.gfx_data = data[offset:offset + sprite.header.gfx_size]
        offset += sprite.header.gfx_size
        sprite.pal_data = data[offset:offset + sprite.header.pal_size]
        
        return sprite
    
    def build(self) -> bytes:
        self.header.cell_attr_size = len(self.cell_attrs) * CellAttr.SIZE
        self.header.cell_data_size = len(self.cell_data) * CellData.SIZE
        self.header.anim_head_size = len(self.anim_headers) * AnimHeader.SIZE
        self.header.anim_frame_size = len(self.anim_frames) * AnimFrame.SIZE
        self.header.gfx_size = len(self.gfx_data)
        self.header.pal_size = len(self.pal_data)
        
        result = bytearray()
        result.extend(self.header.pack())
        for ca in self.cell_attrs:
            result.extend(ca.pack())
        for cd in self.cell_data:
            result.extend(cd.pack())
        for ah in self.anim_headers:
            result.extend(ah.pack())
        for af in self.anim_frames:
            result.extend(af.pack())
        result.extend(self.gfx_data)
        result.extend(self.pal_data)
        return bytes(result)
    
    def save(self, filepath: str):
        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)
        with open(filepath, 'wb') as f:
            f.write(self.build())
    
    def is_8bpp(self) -> bool:
        return self.header.palette_mode != 0
    
    def to_dict(self) -> dict:
        return {
            'header': asdict(self.header),
            'cell_attrs': [asdict(ca) for ca in self.cell_attrs],
            'cell_data': [asdict(cd) for cd in self.cell_data],
            'anim_headers': [asdict(ah) for ah in self.anim_headers],
            'anim_frames': [asdict(af) for af in self.anim_frames],
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        sprite = cls()
        sprite.header = SpriteFileHeader(**data['header'])
        sprite.cell_attrs = [CellAttr(**ca) for ca in data['cell_attrs']]
        sprite.cell_data = [CellData(**cd) for cd in data['cell_data']]
        sprite.anim_headers = [AnimHeader(**ah) for ah in data['anim_headers']]
        sprite.anim_frames = [AnimFrame(**af) for af in data['anim_frames']]
        return sprite
    
    def export(self, output_dir: str):
        os.makedirs(output_dir, exist_ok=True)
        
        with open(os.path.join(output_dir, 'data.json'), 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        
        is_8bpp = self.is_8bpp()
        bytes_per_tile = 64 if is_8bpp else 32
        num_tiles = len(self.gfx_data) // bytes_per_tile
        tiles_per_row = calculate_tiles_per_row(num_tiles)
        
        palettes = parse_palette(self.pal_data, is_8bpp)
        
        # 保存调色板和布局信息
        pal_info = {
            'is_8bpp': is_8bpp,
            'num_tiles': num_tiles,
            'tiles_per_row': tiles_per_row,  # 可手动修改
            'palettes': [[list(c) for c in pal] for pal in palettes]
        }
        with open(os.path.join(output_dir, 'palette.json'), 'w') as f:
            json.dump(pal_info, f, indent=2)
        
        print(f"  {num_tiles} tiles -> {tiles_per_row} tiles/row (可在 palette.json 中修改)")
        
        if palettes:
            for pal_idx, palette in enumerate(palettes):
                img = render_tilesheet(self.gfx_data, palette, tiles_per_row, is_8bpp)
                if pal_idx == 0:
                    img.save(os.path.join(output_dir, 'tileset.png'))
                else:
                    img.save(os.path.join(output_dir, f'tileset_pal{pal_idx}.png'))
        
        with open(os.path.join(output_dir, 'graphics.bin'), 'wb') as f:
            f.write(self.gfx_data)
        with open(os.path.join(output_dir, 'palette.bin'), 'wb') as f:
            f.write(self.pal_data)
    
    @classmethod
    def import_from(cls, input_dir: str):
        with open(os.path.join(input_dir, 'data.json'), 'r', encoding='utf-8') as f:
            data = json.load(f)
        sprite = cls.from_dict(data)
        
        with open(os.path.join(input_dir, 'palette.json'), 'r') as f:
            pal_info = json.load(f)
        
        palettes = [[tuple(c) for c in pal] for pal in pal_info['palettes']]
        sprite.pal_data = build_palette(palettes)
        is_8bpp = pal_info.get('is_8bpp', False)
        
        tileset_path = os.path.join(input_dir, 'tileset.png')
        if os.path.exists(tileset_path):
            img = Image.open(tileset_path)
            sprite.gfx_data = encode_tilesheet(img, palettes[0], is_8bpp)
        else:
            with open(os.path.join(input_dir, 'graphics.bin'), 'rb') as f:
                sprite.gfx_data = f.read()
        
        return sprite


def find_snce_files(root: str) -> List[str]:
    files = []
    for dirpath, _, filenames in os.walk(root):
        for fname in filenames:
            if '_SNCE' in fname:
                files.append(os.path.join(dirpath, fname))
    return files


def find_exported_dirs(root: str) -> List[str]:
    dirs = []
    for dirpath, _, filenames in os.walk(root):
        if 'data.json' in filenames:
            dirs.append(dirpath)
    return dirs


def batch_decode(input_dir: str, output_dir: str):
    print(f"=== SNCE Decoder ===\n")
    files = find_snce_files(input_dir)
    print(f"Found {len(files)} file(s)\n")
    
    success = failed = 0
    for filepath in files:
        rel_path = os.path.relpath(filepath, input_dir)
        base_name = rel_path.replace('.bin', '').replace('_SNCE', '')
        out_path = os.path.join(output_dir, base_name)
        
        print(f"[D] {rel_path}")
        try:
            sprite = SpriteFile.load(filepath)
            sprite.export(out_path)
            success += 1
        except Exception as e:
            print(f"    ERROR: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print(f"\n=== Complete: {success} OK, {failed} failed ===")


def batch_encode(input_dir: str, output_dir: str):
    print(f"=== SNCE Encoder ===\n")
    dirs = find_exported_dirs(input_dir)
    print(f"Found {len(dirs)} sprite(s)\n")
    
    success = failed = 0
    for dir_path in dirs:
        rel_path = os.path.relpath(dir_path, input_dir)
        out_file = os.path.join(output_dir, rel_path + '_SNCE')
        
        print(f"[E] {rel_path}")
        try:
            sprite = SpriteFile.import_from(dir_path)
            sprite.save(out_file)
            print(f"    -> {out_file}")
            success += 1
        except Exception as e:
            print(f"    ERROR: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print(f"\n=== Complete: {success} OK, {failed} failed ===")


def main():
    parser = argparse.ArgumentParser(description='SNCE Sprite Tool')
    parser.add_argument('-d', '--decode', nargs=2, metavar=('IN', 'OUT'))
    parser.add_argument('-e', '--encode', nargs=2, metavar=('IN', 'OUT'))
    args = parser.parse_args()
    
    if args.decode:
        batch_decode(*args.decode)
    elif args.encode:
        batch_encode(*args.encode)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()