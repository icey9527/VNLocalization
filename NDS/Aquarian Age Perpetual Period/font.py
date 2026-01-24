#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import math
from PIL import Image, ImageDraw, ImageFont
import xml.etree.ElementTree as ET

# ================= 核心配置 =================
l_size = 12
CONFIG = {
    'input_file':  "font.txt",
    'output_xml':  "new_font.xml",
    'output_png':  "new_font.png",
    'font_path':   "simsun.ttc",

    # --- 样式 ---
    'font_size':   l_size,
    'text_color':  0,
    'rotate':      -90,
    'upscale':     8,       # 4倍画质
    'bold_width':  0.5,       # 1px 微量加粗

    # --- 对齐 ---
    'offset_y':    3.0,
    'offset_x':    0.0,

    # --- 2bpp 量化 ---
    'threshold_black': 110,
    'threshold_dark':  185,
    'threshold_light': 210,

    # --- 结构 ---
    'box_w':       l_size,
    'box_h':       l_size,
    'cols':        16,
    'border':      2,
}

# 竖排标点映射
VERT_MAP = {
    '(': '︵', ')': '︶', '（': '︵', '）': '︶',
    '[': '︹', ']': '︺', '〔': '︹', '〕': '︺',
    '{': '︷', '}': '︸',
    '<': '︿', '>': '﹀', '〈': '︿', '〉': '﹀',
    '《': '︽', '》': '︾', '「': '﹁', '」': '﹂',
    '『': '﹃', '』': '︄', '【': '︻', '】': '︼',
    '—': '︱', '-': '︱', '|': '︱',
    '…': '︙', '～': '︴', '~': '︴'
}

# ================= 工具函数 =================

def add_xml(parent, tag, text=None, **attrs):
    elem = ET.SubElement(parent, tag, attrs)
    if text is not None: elem.text = str(text)
    return elem

def determine_map_id(char_code):
    """复刻原版 Map 分区逻辑"""
    if 0x3000 <= char_code <= 0x30FC: return 0 
    if 0xFF01 <= char_code <= 0xFF5E: return 1 
    return 2 

def indent_xml(elem, level=0):
    """
    手动 XML 缩进函数
    替代 minidom，确保汉字不被转义成 &#xxxxx;
    """
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent_xml(elem, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

def quantize_to_2bpp(img_gray, cfg):
    lut = []
    for i in range(256):
        if i < cfg['threshold_black']: lut.append(3)
        elif i < cfg['threshold_dark']: lut.append(2)
        elif i < cfg['threshold_light']: lut.append(1)
        else: lut.append(0)

    img_indexed = img_gray.point(lut, mode='P')
    palette = [
        255, 255, 255,  # 0: White
        170, 170, 170,  # 1: Light Gray
         85,  85,  85,  # 2: Dark Gray
          0,   0,   0,  # 3: Black
    ]
    palette = palette + [0] * (768 - len(palette))
    img_indexed.putpalette(palette)
    return img_indexed

def process_glyph(char, font, cfg):
    upscale = cfg['upscale']
    box_w, box_h = cfg['box_w'], cfg['box_h']
    safe_w, safe_h = box_w * upscale, box_h * upscale

    display_char = VERT_MAP.get(char, char)
    bbox = font.getbbox(display_char)
    if not bbox: return None, 5, 0, 8

    ink_w = bbox[2] - bbox[0]
    ink_h = bbox[3] - bbox[1]
    
    center_y = (safe_h - ink_h) / 2
    target_y = center_y + (cfg['offset_y'] * upscale)
    if (target_y + ink_h) > safe_h: target_y = safe_h - ink_h
    if target_y < 0: target_y = 0
        
    target_x = (safe_w - ink_w) / 2 + (cfg['offset_x'] * upscale)

    pivot_size = int(max(safe_w, safe_h) * 2.0)
    img_pivot = Image.new("L", (pivot_size, pivot_size), 255)
    draw = ImageDraw.Draw(img_pivot)
    
    off_sx = (pivot_size - safe_w) // 2
    off_sy = (pivot_size - safe_h) // 2
    draw_x = off_sx + target_x - bbox[0]
    draw_y = off_sy + target_y - bbox[1]

    draw.text((draw_x, draw_y), display_char, font=font, fill=0, 
              stroke_width=cfg['bold_width'], stroke_fill=0)

    if cfg['rotate'] != 0:
        img_pivot = img_pivot.rotate(cfg['rotate'], resample=Image.BICUBIC, fillcolor=255)

    center = pivot_size // 2
    left = center - safe_w // 2
    top  = center - safe_h // 2
    img_crop = img_pivot.crop((left, top, left + safe_w, top + safe_h))
    img_final = img_crop.resize((box_w, box_h), resample=Image.LANCZOS)

    final_ink_w = ink_w + (cfg['bold_width'] * 2)
    xml_width = int(final_ink_w / upscale)
    xml_bearing = int((box_w - xml_width) / 2)
    if xml_bearing < 0: xml_bearing = 0
    
    return img_final, xml_width, xml_bearing, box_w

# ================= 主程序 =================

def main():
    c = CONFIG
    if not os.path.exists(c['input_file']):
        print(f"错误: 未找到 {c['input_file']}")
        return

    with open(c['input_file'], 'r', encoding='utf-16') as f:
        content = f.read()
    chars = sorted(list(set(ch for ch in content if ord(ch) != 0xFEFF)), key=ord)
    total = len(chars)
    
    print(f"处理字符: {total} | 修复XML注释乱码")

    rows = math.ceil(total / c['cols'])
    img_w = (c['cols'] * c['box_w']) + ((c['cols'] + 1) * c['border'])
    img_h = (rows * c['box_h']) + ((rows + 1) * c['border'])

    full_img = Image.new("L", (img_w, img_h), 255)
    try:
        font = ImageFont.truetype(c['font_path'], int(c['font_size'] * c['upscale']))
    except:
        font = ImageFont.load_default()

    # XML 构建
    root = ET.Element("NFTR")
    add_xml(root, "Version", "1.1")
    add_xml(root, "LineGap", "15")
    add_xml(root, "BoxWidth", c['box_w'])
    add_xml(root, "BoxHeight", c['box_h'])
    add_xml(root, "GlyphWidth", "15")
    add_xml(root, "GlyphHeight", "13")
    dw = add_xml(root, "DefaultWidth")
    add_xml(dw, "IdRegion", "-1")
    add_xml(dw, "BearingX", "0")
    add_xml(dw, "Width", "15")
    add_xml(dw, "Advance", "15")
    add_xml(root, "ErrorChar", "0")
    add_xml(root, "Depth", "2")
    add_xml(root, "Rotation", "Rot270")
    add_xml(root, "Encoding", "UTF8")
    
    # Maps & Widths
    maps = add_xml(root, "Maps")
    m0 = add_xml(maps, "Map")
    add_xml(m0, "Id", "0"), add_xml(m0, "FirstChar", "3000"), add_xml(m0, "LastChar", "30FC"), add_xml(m0, "Type", "1")
    m1 = add_xml(maps, "Map")
    add_xml(m1, "Id", "1"), add_xml(m1, "FirstChar", "FF01"), add_xml(m1, "LastChar", "FF5E"), add_xml(m1, "Type", "1")
    m2 = add_xml(maps, "Map")
    add_xml(m2, "Id", "2"), add_xml(m2, "FirstChar", "0"), add_xml(m2, "LastChar", "FFFF"), add_xml(m2, "Type", "2")

    widths = add_xml(root, "Widths")
    r = add_xml(widths, "Region")
    add_xml(r, "Id", "0"), add_xml(r, "FirstChar", "0"), add_xml(r, "LastChar", str(total - 1))
    
    glyphs_node = add_xml(root, "Glyphs")

    for idx, char in enumerate(chars):
        col = idx % c['cols']
        row = idx // c['cols']
        cx = (col * c['box_w']) + ((col + 1) * c['border'])
        cy = (row * c['box_h']) + ((row + 1) * c['border'])

        if char not in ['\n', '\r', '\t']:
            g_img, xml_w, xml_bx, xml_ad = process_glyph(char, font, c)
            if g_img:
                full_img.paste(g_img, (cx, cy))
        else:
            xml_w, xml_bx, xml_ad = 5, 0, 8

        char_code = ord(char)
        id_map = determine_map_id(char_code)

        g = add_xml(glyphs_node, "Glyph")
        
        # 注释处理
        comment_txt = char
        if char == '\n': comment_txt = "\\n"
        elif char == '\r': comment_txt = "\\r"
        elif char == '\t': comment_txt = "\\t"
        
        g.append(ET.Comment(f" ({comment_txt}) "))

        add_xml(g, "Id", idx)
        w = add_xml(g, "Width")
        add_xml(w, "IdRegion", "0")
        add_xml(w, "BearingX", xml_bx)
        add_xml(w, "Width", xml_w)
        add_xml(w, "Advance", xml_ad)
        add_xml(g, "Code", format(char_code, 'X'))
        add_xml(g, "IdMap", id_map)

    # 【关键修改】使用自定义缩进函数，不再用 minidom
    indent_xml(root)
    tree = ET.ElementTree(root)

    # xml_declaration=True 会自动加上 <?xml...?> 头
    tree.write(c['output_xml'], encoding="utf-8", xml_declaration=True, short_empty_elements=False)

    print("正在量化颜色...")
    final_img = quantize_to_2bpp(full_img, c)
    final_img.save(c['output_png'])
    print(f"完成! XML中文注释已修复。")

if __name__ == "__main__":
    main()