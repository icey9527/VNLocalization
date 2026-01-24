#!/usr/bin/env python3
"""游戏字库工具 - GBK 支持版（修复标点符号渲染）"""

import struct
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import numpy as np

GLYPH_SIZE = 32
GLYPH_PIXELS = GLYPH_SIZE ** 2
PALETTE = np.array([[0, 0, 0], [85, 85, 85], [170, 170, 170], [255, 255, 255]], dtype=np.uint8)
BASE_HI = 0x81


def rle_decode(data: bytes) -> list[int]:
    px = []
    for b in data:
        color = (b >> 6) & 3
        count = b & 0x3F
        if count == 0:
            count = 64
        px.extend([color] * count)
        if len(px) >= GLYPH_PIXELS:
            return px[:GLYPH_PIXELS]
    return px


def rle_encode(px: list[int]) -> bytes:
    out, i, n = bytearray(), 0, len(px)
    while i < n:
        c, run = px[i], 1
        while i + run < n and px[i + run] == c and run < 63:
            run += 1
        out.append((c << 6) | run)
        i += run
    return bytes(out)


def load_table(table_file: str):
    text = Path(table_file).read_text(encoding='utf-16')
    chars = []
    for line in text.splitlines():
        line = line.rstrip('\r\n')
        if '=' not in line:
            continue
        code, ch = line.split('=', 1)
        code = code.strip()
        if not code or not ch:
            continue
        try:
            code_bytes = bytes.fromhex(code)
            if len(code_bytes) == 1:
                hi, lo = 0, code_bytes[0]
            elif len(code_bytes) == 2:
                hi, lo = code_bytes[0], code_bytes[1]
            else:
                continue
            chars.append((hi, lo, ch))
        except ValueError:
            continue
    return chars


def export_font(src: str, dst: str):
    data = Path(src).read_bytes()
    dlen = len(data)
    
    offsets = []
    for i in range(256):
        if i * 4 + 4 > dlen:
            break
        off = struct.unpack_from('<I', data, i * 4)[0]
        offsets.append(off)
        if off == 0 and len(offsets) > 1:
            break
    
    print(f"索引表: {len(offsets)} 项")
    
    glyphs = []
    glyph_codes = []
    
    for slot_idx, off in enumerate(offsets[:-1]):
        if off == 0 or (len(offsets) > 1 and off == offsets[-1]):
            continue
        
        hi = 0 if slot_idx == 0 else BASE_HI + slot_idx - 1
        
        next_off = dlen
        for j in range(slot_idx + 1, len(offsets)):
            if offsets[j] != 0 and offsets[j] != offsets[-1] and offsets[j] > off:
                next_off = offsets[j]
                break
        
        pos = off
        while pos + 4 <= dlen and pos < next_off:
            lo = data[pos]
            nxt = struct.unpack_from('<H', data, pos + 2)[0]
            
            if lo == 0 and nxt == 0:
                break
            
            rle_data = data[pos + 4:min(pos + nxt, next_off)] if nxt > 0 else data[pos + 4:next_off]
            px = rle_decode(rle_data)
            if len(px) >= GLYPH_PIXELS:
                glyphs.append(px)
                glyph_codes.append((hi, lo))
            
            if nxt == 0:
                break
            pos += nxt
    
    cols = 64
    rows = (len(glyphs) + cols - 1) // cols
    img = np.zeros((rows * GLYPH_SIZE, cols * GLYPH_SIZE, 3), dtype=np.uint8)
    
    for i, px in enumerate(glyphs):
        x, y = (i % cols) * GLYPH_SIZE, (i // cols) * GLYPH_SIZE
        glyph = np.array(px, dtype=np.uint8).reshape(GLYPH_SIZE, GLYPH_SIZE)
        img[y:y + GLYPH_SIZE, x:x + GLYPH_SIZE] = PALETTE[glyph]
    
    Image.fromarray(img).save(dst)
    print(f"导出 {len(glyphs)} 字形 -> {dst}")
    
    print("\n前 20 个字形:")
    for i, (hi, lo) in enumerate(glyph_codes[:20]):
        code_str = f"0x{hi:02X}{lo:02X}" if hi else f"0x{lo:02X}"
        print(f"  {i:3d}: {code_str}")


class GlyphRenderer:
    """字形渲染器 - 正确处理标点符号位置"""
    
    def __init__(self, ttf_path: str, base_size: int = 32):
        self.ttf_path = ttf_path
        self.base_size = base_size
        
        # 主字体（稍小以留边距）
        self.font_size = int(base_size * 0.85)
        self.font = ImageFont.truetype(ttf_path, self.font_size)
        
        # 获取字体度量信息
        self.ascent, self.descent = self.font.getmetrics()
        
        # 半角字体（可能需要更小）
        self.half_font_size = int(base_size * 0.75)
        self.half_font = ImageFont.truetype(ttf_path, self.half_font_size)
    
    def render(self, ch: str, is_halfwidth: bool = False) -> bytes:
        """渲染单个字形"""
        img = Image.new('L', (GLYPH_SIZE, GLYPH_SIZE), 0)
        draw = ImageDraw.Draw(img)
        
        if is_halfwidth:
            # 半角字符：在左半边(16px)居中
            self._draw_halfwidth(draw, ch)
        else:
            # 全角字符：整体居中
            self._draw_fullwidth(draw, ch)
        
        # 量化为 4 级灰度
        arr = np.array(img)
        px = np.digitize(arr.ravel(), [43, 128, 213]).tolist()
        return rle_encode(px)
    
    def _draw_fullwidth(self, draw: ImageDraw.Draw, ch: str):
        """绘制全角字符 - 使用基线对齐"""
        center_x = GLYPH_SIZE // 2
        
        # ★ 关键修复：使用 anchor 参数
        # 'mm' = middle-middle，基于字体metrics居中，而不是bbox
        # 这样标点符号会保持在正确的相对位置
        
        # 方法1：完全居中��推荐用于游戏字体）
        center_y = GLYPH_SIZE // 2
        draw.text((center_x, center_y), ch, font=self.font, fill=255, anchor='mm')
    
    def _draw_fullwidth_baseline(self, draw: ImageDraw.Draw, ch: str):
        """备选方案：基线对齐（更符合排版规范）"""
        # 计算基线位置，使 em-box 垂直居中
        baseline_y = (GLYPH_SIZE + self.ascent - self.descent) // 2
        
        # 水平居中
        bbox = self.font.getbbox(ch)
        char_width = bbox[2] - bbox[0]
        x = (GLYPH_SIZE - char_width) // 2 - bbox[0]
        
        # 使用 'ls' = left-baseline
        draw.text((x, baseline_y), ch, font=self.font, fill=255, anchor='ls')
    
    def _draw_halfwidth(self, draw: ImageDraw.Draw, ch: str):
        """绘制半角字符"""
        target_width = 16
        center_x = target_width // 2
        center_y = GLYPH_SIZE // 2
        
        # 检查字符是否太宽
        bbox = self.half_font.getbbox(ch)
        char_width = bbox[2] - bbox[0]
        
        if char_width > target_width - 2:
            # 太宽了，用更小的字体
            scale = (target_width - 2) / char_width
            small_size = max(8, int(self.half_font_size * scale))
            small_font = ImageFont.truetype(self.ttf_path, small_size)
            draw.text((center_x, center_y), ch, font=small_font, fill=255, anchor='mm')
        else:
            draw.text((center_x, center_y), ch, font=self.half_font, fill=255, anchor='mm')


def generate_font(dst: str, ttf: str, table: str, support_halfwidth: bool = True):
    """生成字库"""
    chars = load_table(table)
    print(f"码表: {table} ({len(chars)} 字符)")
    print(f"字体: {ttf}")
    
    # 创建渲染器
    renderer = GlyphRenderer(ttf, GLYPH_SIZE)
    print(f"字号: {renderer.font_size}, ascent={renderer.ascent}, descent={renderer.descent}")
    
    # 分类字符
    single_byte = [(hi, lo, ch) for hi, lo, ch in chars if hi == 0]
    double_byte = [(hi, lo, ch) for hi, lo, ch in chars if hi >= BASE_HI]
    invalid = [(hi, lo, ch) for hi, lo, ch in chars if 0 < hi < BASE_HI]
    
    if invalid:
        print(f"警告: 忽略 {len(invalid)} 个无效编码")
    
    if single_byte:
        if support_halfwidth:
            print(f"半角字符: {len(single_byte)} 个")
        else:
            print(f"警告: 忽略 {len(single_byte)} 个半角字符")
            single_byte = []
    
    print(f"全角字符: {len(double_byte)} 个")
    
    if not double_byte and not single_byte:
        print("错误: 没有有效字符!")
        return
    
    # 生成字形
    groups = {}
    count = 0
    
    # 半角
    for hi, lo, ch in single_byte:
        rle = renderer.render(ch, is_halfwidth=True)
        groups.setdefault(0, []).append((lo, rle))
        count += 1
        if count % 100 == 0:
            print(f"\r生成: {count} ({ch})", end='', flush=True)
    
    # 全角
    for hi, lo, ch in double_byte:
        rle = renderer.render(ch, is_halfwidth=False)
        groups.setdefault(hi, []).append((lo, rle))
        count += 1
        if count % 500 == 0:
            print(f"\r生成: {count} ({ch})", end='', flush=True)
    
    print(f"\r生成完成: {count} 字形")
    
    # 构建文件
    max_hi = max((h for h in groups.keys() if h >= BASE_HI), default=BASE_HI)
    n_slots = max_hi - BASE_HI + 2
    
    print(f"槽位: 0 (半角) + 1-{n_slots-1} (全角 0x{BASE_HI:02X}-0x{max_hi:02X})")
    
    index_size = (n_slots + 1) * 4
    
    offsets = []
    pos = index_size
    
    for slot in range(n_slots):
        hi = 0 if slot == 0 else BASE_HI + slot - 1
        
        if hi in groups:
            offsets.append(pos)
            for lo, rle in groups[hi]:
                pos += 4 + len(rle)
            pos += 4
        else:
            offsets.append(index_size - 4)
    
    out = bytearray()
    
    for off in offsets:
        out.extend(struct.pack('<I', off))
    out.extend(struct.pack('<I', 0))
    
    for slot in range(n_slots):
        hi = 0 if slot == 0 else BASE_HI + slot - 1
        
        if hi not in groups:
            continue
        
        gs = sorted(groups[hi], key=lambda x: x[0])
        
        for j, (lo, rle) in enumerate(gs):
            record_len = 4 + len(rle)
            nxt = record_len if j < len(gs) - 1 else 0
            
            out.append(lo)
            out.append(0xCD)
            out.extend(struct.pack('<H', nxt))
            out.extend(rle)
        
        out.extend(struct.pack('<I', 0))
    
    Path(dst).write_bytes(out)
    print(f"保存: {dst} ({len(out)} 字节)")


def preview_chars(ttf: str, chars: str = "你好，世界！「测试」（OK）"):
    """预览字符渲染效果"""
    renderer = GlyphRenderer(ttf, GLYPH_SIZE)
    
    n = len(chars)
    cols = min(n, 16)
    rows = (n + cols - 1) // cols
    
    img = Image.new('RGB', (cols * GLYPH_SIZE, rows * GLYPH_SIZE), (40, 40, 40))
    
    for i, ch in enumerate(chars):
        x = (i % cols) * GLYPH_SIZE
        y = (i // cols) * GLYPH_SIZE
        
        # 渲染字形
        rle = renderer.render(ch, is_halfwidth=False)
        px = rle_decode(rle)
        glyph = np.array(px, dtype=np.uint8).reshape(GLYPH_SIZE, GLYPH_SIZE)
        glyph_img = Image.fromarray(PALETTE[glyph])
        
        img.paste(glyph_img, (x, y))
        
        # 画格子边框
        draw = ImageDraw.Draw(img)
        draw.rectangle([x, y, x + GLYPH_SIZE - 1, y + GLYPH_SIZE - 1], outline=(80, 80, 80))
    
    img.save('preview.png')
    print(f"预览已保存: preview.png ({chars})")
    img.show()


def analyze_font(src: str):
    data = Path(src).read_bytes()
    dlen = len(data)
    
    print(f"文件: {src}")
    print(f"大小: {dlen} 字节\n")
    
    offsets = []
    for i in range(256):
        if i * 4 + 4 > dlen:
            break
        off = struct.unpack_from('<I', data, i * 4)[0]
        offsets.append(off)
        if off == 0 and len(offsets) > 1:
            break
    
    print(f"索引表: {len(offsets)} 项\n")
    print("槽位分配:")
    print("-" * 60)
    
    for slot in range(min(20, len(offsets) - 1)):
        off = offsets[slot]
        hi_str = "0x00 (半角)" if slot == 0 else f"0x{BASE_HI + slot - 1:02X}"
        
        if off == 0 or off == offsets[-1]:
            print(f"  槽 {slot:3d} ({hi_str}): (空)")
        elif off + 4 <= dlen:
            lo = data[off]
            nxt = struct.unpack_from('<H', data, off + 2)[0]
            print(f"  槽 {slot:3d} ({hi_str}): off=0x{off:06X}, lo=0x{lo:02X}")
    
    if len(offsets) > 21:
        print(f"  ... 共 {len(offsets) - 1} 个槽")


def main():
    import sys
    args = sys.argv[1:]
    
    if not args or args[0] in ('-h', '--help'):
        print("""用法:
  导出: python font.py e <字库> <图片>
  生成: python font.py g <输出> <TTF> <码表> [--no-halfwidth]
  分析: python font.py a <字库>
  预览: python font.py p <TTF> [文字]

示例:
  python font.py g font.bin simsun.ttc table.txt
  python font.py p simsun.ttc "你好，世界！"
""")
        return
    
    cmd = args[0]
    
    if cmd == 'e' and len(args) >= 3:
        export_font(args[1], args[2])
    elif cmd == 'g' and len(args) >= 4:
        support_hw = '--no-halfwidth' not in args
        generate_font(args[1], args[2], args[3], support_hw)
    elif cmd == 'a' and len(args) >= 2:
        analyze_font(args[1])
    elif cmd == 'p' and len(args) >= 2:
        chars = args[2] if len(args) >= 3 else "你好，世界！「测试」（OK）"
        preview_chars(args[1], chars)
    else:
        print("参数错误，用 -h 查看帮助")


if __name__ == '__main__':
    main()