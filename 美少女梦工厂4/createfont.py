# -*- coding: utf-8 -*-
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

def load_codemap(path):
    """读取码表文件（UTF-16）"""
    code_map = {}
    with open(path, 'r', encoding='utf-16') as f:
        for line in f:
            if '=' in line:
                try:
                    idx, code = line.split('=', 1)
                    code_map[int(idx.strip())] = code.strip()
                except:
                    continue
    return code_map

def render_char(char, font, size=(16, 16), shadow_dx=1, shadow_dy=0, shadow_thickness=1):
    """渲染字符，返回256长度列表：0背景/1阴影/2主体"""
    # 渲染主体
    img = Image.new('L', size, color=0)
    draw = ImageDraw.Draw(img)
    
    # 居中定位
    try:
        bbox = draw.textbbox((0, 0), char, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (size[0] - w) // 2 - bbox[0]
        y = (size[1] - h) // 2 - bbox[1]
    except AttributeError:
        w, h = font.getsize(char)
        x, y = (size[0] - w) // 2, (size[1] - h) // 2
    
    draw.text((x, y), char, font=font, fill=255)
    
    # 主体掩膜
    main_mask = np.array(img) > 127
    
    # 阴影掩膜（向右/下偏移，支持多层厚度）
    shadow_mask = np.zeros_like(main_mask)
    h, w = main_mask.shape
    for k in range(shadow_thickness):
        dx, dy = shadow_dx + k, shadow_dy
        if 0 < dx < w and 0 <= dy < h:
            shifted = np.zeros_like(main_mask)
            shifted[dy:, dx:] = main_mask[:h-dy, :w-dx]
            shadow_mask |= shifted
    
    # 合成：2主体/1阴影/0背景
    result = np.zeros((h, w), dtype=np.uint8)
    result[shadow_mask] = 1
    result[main_mask] = 2
    return result.flatten().tolist()

def encode_tile(pixels):
    """编码256像素为64字节tile格式"""
    output = bytearray(64)
    for tile_idx in range(4):
        tx, ty = (tile_idx % 2) * 8, (tile_idx // 2) * 8
        for i in range(16):
            y, x_offset = i // 2, (i % 2) * 4
            byte = 0
            for j in range(4):
                byte |= (pixels[(ty + y) * 16 + tx + x_offset + j] << (j * 2))
            output[tile_idx * 16 + i] = byte
    return bytes(output)

def generate_font(codemap_path, font_path, output_dir, font_size=12, shadow_dx=1, shadow_dy=0, shadow_thickness=1):
    """生成字库"""
    os.makedirs(output_dir, exist_ok=True)
    
    code_map = load_codemap(codemap_path)
    font = ImageFont.truetype(font_path, font_size)
    
    # 颜色映射 (0->0, 1->2, 2->1, 3->3)
    reverse_map = [0, 2, 1, 3]
    
    print(f"✅ 共 {len(code_map)} 个字符，开始生成...\n")
    
    font_data = bytearray()
    for i in range(len(code_map)):
        # 解码字符
        try:
            char = bytes.fromhex(code_map.get(i, '20')).decode('cp936')
        except:
            char = ' '
        
        # 渲染 -> 映射 -> 编码
        pixels = render_char(char, font, shadow_dx=shadow_dx, shadow_dy=shadow_dy, shadow_thickness=shadow_thickness)
        mapped = [reverse_map[p] for p in pixels]
        font_data.extend(encode_tile(mapped))
        
        if (i + 1) % 1000 == 0:
            print(f"  {i + 1}/{len(code_map)}")
    
    # 保存
    bin_path = os.path.join(output_dir, '00000255.bin')
    with open(bin_path, 'wb') as f:
        f.write(bytes.fromhex('464E5404') + font_data)
    
    print(f"\n✅ 完成！📄 {bin_path}")

if __name__ == '__main__':
    generate_font(
        codemap_path='pm4_gbk.tbl',
        font_path='font.ttf',
        output_dir='I:\\研究\\nds\\pack\\pack\\NZ',
        font_size=14,           # 字号
        shadow_dx=1,            # 阴影右移
        shadow_dy=0,            # 阴影下移
        shadow_thickness=1      # 阴影厚度
    )