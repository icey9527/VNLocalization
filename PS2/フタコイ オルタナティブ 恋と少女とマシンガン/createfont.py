# -*- coding: utf-8 -*-
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import math

def load_codemap(path):
    """读取码表文件（UTF-16），保留空格"""
    chars = []
    with open(path, 'r', encoding='utf-16') as f:
        for line in f:
            line = line.rstrip('\n\r')
            if '=' in line:
                try:
                    idx, char = line.split('=', 1)
                    chars.append(char)
                except:
                    chars.append(' ')
    return chars

def render_char(char, font, size=(24, 24), scale=4, shadow_dx=1, shadow_dy=1):
    """高分辨率渲染字符，返回0-3的2bpp数据"""
    hr_size = (size[0] * scale, size[1] * scale)
    img = Image.new('L', hr_size, color=0)
    draw = ImageDraw.Draw(img)
    
    hr_font = ImageFont.truetype(font.path, font.size * scale)
    
    # 获取字符边界框
    bbox = draw.textbbox((0, 0), char, font=hr_font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    
    # 水平居中
    x = (hr_size[0] - w) // 2 - bbox[0]
    
    # 垂直对齐：区分标点符号和普通字符
    if char in '，。！？；：""''（）【】《》、.,!?;:\'"()[]<>/':
        # 标点符号：底部对齐，留出下方空间
        y = hr_size[1] - h - bbox[1] - 2 * scale
    elif char in '一丶乀乁':
        # 横线类字符：稍微下移，避免太高
        y = (hr_size[1] - h) // 2 - bbox[1] + 2 * scale        
    else:
        # 普通字符：垂直居中
        y = (hr_size[1] - h) // 2 - bbox[1]
    
    if shadow_dx or shadow_dy:
        draw.text((x + shadow_dx, y + shadow_dy), char, font=hr_font, fill=128)
    
    draw.text((x, y), char, font=hr_font, fill=255)
    
    if scale > 1:
        img = img.resize(size, Image.Resampling.NEAREST)
    
    data = np.array(img, dtype=np.uint8)
    data_2bpp = (data >> 6).clip(0, 3)
    
    return data_2bpp

def encode_tile_2bpp(pixels):
    """24×24像素数组 -> 2bpp tile数据 (144字节)"""
    flat = pixels.flatten()
    packed = bytearray()
    
    for i in range(0, len(flat), 4):
        byte = (flat[i+3] << 6) | (flat[i+2] << 4) | (flat[i+1] << 2) | flat[i]
        packed.append(byte)
    
    return bytes(packed)

def calculate_checksum(data):
    """计算校验和"""
    sum_even = sum_odd = 0x1111111111111111
    for i in range(0, len(data), 8):
        val = int.from_bytes(data[i:i+8], 'little')
        if (i // 8) % 2 == 0:
            sum_even = (sum_even + val) & 0xFFFFFFFFFFFFFFFF
        else:
            sum_odd = (sum_odd + val) & 0xFFFFFFFFFFFFFFFF
    return sum_even, sum_odd

def generate_font(codemap_path, font_path, output_path, font_size=18, block_size=48):
    """
    生成2bpp字库，自动补齐到block_size的整数倍
    校验和始终在最末尾16字节
    """
    # 加载配置
    chars = load_codemap(codemap_path)
    font = ImageFont.truetype(font_path, font_size)
    
    print(f"📖 加载 {len(chars)} 个字符")
    print(f"🖋️  字体: {font_path} (大小: {font_size})")
    print(f"📐 Tile: 24×24 2bpp = 144字节/字符")
    print(f"📦 区块大小: {block_size} 字节\n")
    
    font_data = bytearray()
    
    # ========== 渲染所有字符 ==========
    for idx, char in enumerate(chars):
        try:
            pixels = render_char(
                char, 
                font, 
                size=(24, 24), 
                scale=1,
                shadow_dx=0,
                shadow_dy=0
            )
            
            tile_data = encode_tile_2bpp(pixels)
            font_data.extend(tile_data)
            
            if (idx + 1) % 100 == 0 or idx < 30:
                display = repr(char) if char.strip() else '(空格)'
                print(f"\r处理: {idx+1}/{len(chars)} - {display}    ", end='')
        
        except Exception as e:
            print(f"\n⚠️  错误 [{idx}] '{char}': {e}")
            font_data.extend(bytes(144))
    
    print(f"\n\n✅ 字库渲染完成!")
    print(f"📊 当前字库: {len(font_data)} 字节 ({len(chars)} 字符)")
    
    # ========== 自动补齐到block_size倍数 ==========
    CHECKSUM_SIZE = 16
    current_size = len(font_data)
    
    # 计算总大小（包含校验）需要占用多少区块
    total_with_checksum = current_size + CHECKSUM_SIZE
    target_blocks = math.ceil(total_with_checksum / block_size)
    target_size = target_blocks * block_size
    
    # 需要填充的数据（在校验和之前）
    padding_size = target_size - total_with_checksum
    
    if padding_size > 0:
        print(f"\n📐 自动对齐:")
        print(f"   字库数据: {current_size} 字节")
        print(f"   + 校验和: {CHECKSUM_SIZE} 字节")
        print(f"   = 小计: {total_with_checksum} 字节")
        print(f"   目标区块: {target_blocks} 个 × {block_size} = {target_size} 字节")
        print(f"   需填充: {padding_size} 字节 (≈{padding_size/144:.1f}个空白字符)")
        
        font_data.extend(bytes(padding_size))  # 填充0x00
        print(f"   ✅ 已填充")
    
    # ========== 计算并追加校验和 ==========
    print(f"\n🔍 计算校验和...")
    sum_even, sum_odd = calculate_checksum(font_data)
    
    checksum = sum_even.to_bytes(8, 'little') + sum_odd.to_bytes(8, 'little')
    font_data.extend(checksum)
    
    # 验证
    assert len(font_data) == target_size, f"❌ 大小错误: {len(font_data)} ≠ {target_size}"
    assert len(font_data) % block_size == 0, f"❌ 未对齐"
    
    # 保存
    with open(output_path, 'wb') as f:
        f.write(font_data)
    
    # ========== 输出报告 ==========
    print(f"\n🎉 生成完成!")
    print(f"📄 文件: {output_path}")
    print(f"📊 最终大小: {len(font_data)} 字节 (0x{len(font_data):X})")
    print(f"📊 结构:")
    print(f"   ├─ 字库数据: {current_size} 字节")
    print(f"   ├─ 填充数据: {padding_size} 字节")
    print(f"   └─ 校验和: {CHECKSUM_SIZE} 字节")
    print(f"🔢 偶数和: 0x{sum_even:016X}")
    print(f"🔢 奇数和: 0x{sum_odd:016X}")
    
    # ========== 修改ELF文件 ==========
    print(f"\n🔧 修改ELF文件...")
    
    # 读取ELF文件
    elf_path = 'SLPS_255.16'
    try:
        with open(elf_path, 'r+b') as f:
            # 0xF5874: 字库文件大小
            f.seek(0xF5874)
            f.write(len(font_data).to_bytes(4, 'little'))
            print(f"   ✅ 0xF5874: 字库大小 = 0x{len(font_data):08X}")
            
            # 0xF5878: 字库文件分区数
            block_count = target_blocks
            f.seek(0xF5878)
            f.write(block_count.to_bytes(4, 'little'))
            print(f"   ✅ 0xF5878: 区块数 = 0x{block_count:08X}")
            
            # 0x90378: 字库内字符数量
            char_count = len(chars)
            f.seek(0x90378)
            f.write(char_count.to_bytes(4, 'little'))
            print(f"   ✅ 0x90378: 字符数 = 0x{char_count:08X}")
            
    except Exception as e:
        print(f"   ❌ 修改ELF失败: {e}")

if __name__ == '__main__':
    generate_font(
        codemap_path='FA_gbk.tbl',
        font_path='SourceHanSansCN-Medium.otf',
        output_path='new/lt.bin',
        font_size=24,
        block_size=2048  # 👈 关键参数！必须与原ROM一致
    )