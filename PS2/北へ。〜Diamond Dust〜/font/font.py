# -*- coding: utf-8 -*-
"""字库渲染补丁：把 font.tbl 的字符用 TTF 渲染成 24x24 2bpp 字形，
按墨迹盒（实际字形区域）居中放入单元格——不用 ascender/像素偏移调基线。

用法（font 目录下）：
    python font.py font.tbl 字体.ttf SLPM_654 输出.elf 0xBAA20

规则（校验汇总，结尾一次打印，不逐行刷屏）：
  [大小] 超出 24x24 被裁断的字形数量（只报个数）
  [原版] TTF 缺字、但原槽位字形恰好是同一个字（左编码的 CP932 原生解码
         == 右字符）→ 不修改，保留原版字形；结尾打印这些字的清单
  [错误] 两种情况报错并以退出码 1 结束：
         a) TTF 缺字且原槽位不是这个字（两边字形不一致，回退无意义）
         b) 该字符 CP932 根本不存在（永远无法显示）
"""
import sys
from pathlib import Path

import freetype

FONT_INDEX = 0
FONT_SIZE = 24
CELL_W = 24
CELL_H = 24
ENDIAN_BIG = True
FLIP_X = False
FLIP_Y = False
LOAD_FLAGS = freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_NORMAL

TILE = (CELL_W * CELL_H) // 4


def parse_table(path: Path):
    items = []
    for line in path.read_text(encoding="utf-16").splitlines():
        line = line.rstrip()
        if not line or "=" not in line:
            continue
        code, text = line.split("=", 1)
        items.append((code.strip().upper(), text))
    return items


def flip_tile(gray: bytearray) -> bytearray:
    if not (FLIP_X or FLIP_Y):
        return gray
    out = bytearray(len(gray))
    for y in range(CELL_H):
        sy = CELL_H - 1 - y if FLIP_Y else y
        for x in range(CELL_W):
            sx = CELL_W - 1 - x if FLIP_X else x
            out[y * CELL_W + x] = gray[sy * CELL_W + sx]
    return out


def q(v):
    # 灰度->2bpp 量化曲线：阈值 8/74/198——从原版字库反推学习所得
    #（拿原版 24px 字形与 HKStdW9 渲染逐像素对齐后统计"灰度->级别"主导映射）
    return 0 if v < 8 else (1 if v < 74 else (2 if v < 198 else 3))


def pack_2bpp(gray: bytearray) -> bytes:
    out = bytearray((CELL_W * CELL_H) // 4)
    j = 0
    for i in range(0, len(gray), 4):
        p0 = q(gray[i])
        p1 = q(gray[i + 1])
        p2 = q(gray[i + 2])
        p3 = q(gray[i + 3])
        if ENDIAN_BIG:
            out[j] = (p0 << 6) | (p1 << 4) | (p2 << 2) | p3
        else:
            out[j] = (p3 << 6) | (p2 << 4) | (p1 << 2) | p0
        j += 1
    return bytes(out)


def render(face, glyph_index):
    """渲染字形，墨迹盒（实际点阵 w x h）在 24x24 单元格内居中。
    超限时贴边裁断（越界像素丢弃），由调用方统计。返回 (tile, w, h)。"""
    face.load_glyph(glyph_index, LOAD_FLAGS)
    bmp = face.glyph.bitmap
    w = int(bmp.width)
    h = int(bmp.rows)
    tile = bytearray(CELL_W * CELL_H)
    if w > 0 and h > 0:
        x0 = max(0, (CELL_W - w) // 2)
        y0 = max(0, (CELL_H - h + 1) // 2)   # 垂直向下取整居中（对齐原版基线习惯）
        pitch = int(bmp.pitch)
        buf = bmp.buffer
        for y in range(min(h, CELL_H)):
            row = ((h - 1 - y) * (-pitch)) if pitch < 0 else y * pitch
            ty = y0 + y
            for x in range(min(w, CELL_W)):
                tile[ty * CELL_W + x0 + x] = buf[row + x]
    return pack_2bpp(flip_tile(tile)), w, h


def native_char(code: str):
    """左编码（SJIS 码位）在 CP932 下的原生字符；无效码位返回 None。"""
    try:
        return int(code, 16).to_bytes(2, "big").decode("cp932")
    except (ValueError, UnicodeDecodeError):
        return None


def main():
    if len(sys.argv) < 6:
        raise SystemExit("python font.py font.tbl 字体.ttf 输入.elf 输出.elf 偏移hex")
    tbl, font, inp, outp = (Path(p) for p in sys.argv[1:5])
    offset = int(sys.argv[5], 0)

    items = parse_table(tbl)
    face = freetype.Face(str(font), index=FONT_INDEX)
    face.set_pixel_sizes(0, FONT_SIZE)

    data = bytearray(inp.read_bytes())
    need = offset + len(items) * TILE
    if len(data) < need:
        data += bytes(need - len(data))

    clipped = 0
    used_original = []
    errors = []
    done = 0
    for i, (code, text) in enumerate(items):
        ch = text[:1] if text else " "
        p = offset + i * TILE
        glyph_index = face.get_char_index(ord(ch))

        if glyph_index != 0:
            tile, w, h = render(face, glyph_index)
            if w > CELL_W or h > CELL_H:
                clipped += 1
            data[p:p + TILE] = tile
        elif native_char(code) == ch:
            # TTF 缺字，但原槽位本来就是同一个字 → 保留原版字形不修改
            if not any(data[p:p + TILE]):
                errors.append(f"{code}={ch!r} 原槽位为空，无法回退原版")
            else:
                used_original.append(ch)
        else:
            try:
                ch.encode("cp932")
                why = "TTF 缺字且原槽位不是该字（两边字形不一致）"
            except UnicodeEncodeError:
                why = "CP932 不存在该字符，无法显示"
            errors.append(f"{code}={ch!r} {why}")

        done += 1
        if done % 512 == 0 or done == len(items):
            print(f"\r{done}/{len(items)}", end="", flush=True)
    print()

    # ---- 汇总（一次性打印） ----
    print(f"[大小] {clipped} 个字形超出 {CELL_W}x{CELL_H} 被裁断")
    if used_original:
        chars = "".join(used_original)
        print(f"[原版] {len(used_original)} 个字 TTF 缺字，已保留原版字形：")
        for k in range(0, len(chars), 64):
            print("  " + chars[k:k + 64])
    if errors:
        print(f"[错误] {len(errors)} 个字无法处理：")
        for e in errors[:80]:
            print("  " + e)
        if len(errors) > 80:
            print(f"  …（其余 {len(errors) - 80} 条略）")

    outp.write_bytes(data)
    if errors:
        raise SystemExit(f"输出已写出 {outp}，但存在 {len(errors)} 个错误字（见上），请先处理")
    print(f"完成 -> {outp}")


if __name__ == "__main__":
    main()
