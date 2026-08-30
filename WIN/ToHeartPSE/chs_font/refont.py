"""ToHeartPSE 字库生成: FONTEX24.FD0 / FONTEX08.FD0 + psth.exe 码表

- 全角区 (GBK 8140-FDA0): 思源黑体渲染 + 原版同款阴影 (tile 字节 = 主笔画4bit<<4 | 阴影4bit)
- 半角区 (0x21-7E) / 外字区 (0xF040-47) / PRESERVE_CODES 集合: 字形整块取自原版字库, 不渲染
- 码表已内嵌 (ORIG_TABLE, 逐字节取自 backup/psth.exe VA 0x44D208), 原版 24px/08px 字库同表同索引
- 原版字库文件尾部多 1 个 0x00 字节, 读取时自动裁掉
"""
import os
import struct
import sys
import time

import numpy as np
import freetype

# 路径均相对当前目录; 字体在 Windows 用户字体目录
FONT_PATH = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Windows\Fonts\SOURCEHANSANSCN-MEDIUM.OTF")

# psth.exe 字体映射表: VA 0x44D208 (文件 0x4D208), 56 项 {u32 base; u16 start; u16 end}。
# 第52项 base = 全角字形总数 (引擎算半角区偏移用, dword_44D3A8), start/end = 全角空格拦截;
# 第53项 = 半角 ASCII (0x21-7E, 94 tile); 55 = 半角空格拦截。半角 tile: 宽=(v9-3)/2+3, 高=v9。
EXE_OFF = 0x4D208
ORIG_TABLE = bytes.fromhex(
    "000000004181AC816C000000B881BF8174000000C881CE817B000000DA81FC81"
    "9E0000004F825882A800000060827982C200000081829A82DC0000009F82F182"
    "2F01000040839683860100009F83B6839E010000BF83D683B601000040846084"
    "D701000070849184F90100009F84BE841902000040879987730200009F88FC88"
    "D10200004089FC898E030000408AFC8A4B040000408BFC8B08050000408CFC8C"
    "C5050000408DFC8D82060000408EFC8E3F070000408FFC8FFC0700004090FC90"
    "B90800004091FC91760900004092FC92330A00004093FC93F00A00004094FC94"
    "AD0B00004095FC956A0C00004096FC96270D00004097FC97E40D000040987298"
    "170E00009F98FC98750E00004099FC99320F0000409AFC9AEF0F0000409BFC9B"
    "AC100000409CFC9C69110000409DFC9D26120000409EFC9EE3120000409FFC9F"
    "A013000040E0FCE05D14000040E1FCE11A15000040E2FCE2D715000040E3FCE3"
    "9416000040E4FCE45117000040E5FCE50E18000040E6FCE6CB18000040E7FCE7"
    "8819000040E8FCE8451A000040E9FCE9021B000040EAA4EA671B000040F047F0"
    "6F1B0000408140810000000021007E005E000000A1FFDFFF9D00000020002000")

ORIG_FULL = []                                    # 前 52 项 [(start, end, base)]
for _i in range(56):
    _b, _s, _e = struct.unpack_from("<IHH", ORIG_TABLE, _i * 8)
    if _i < 52:
        ORIG_FULL.append((_s, _e, _b))
ORIG_FULL_COUNT = ORIG_FULL[-1][2] + (ORIG_FULL[-1][1] - ORIG_FULL[-1][0] + 1)   # 7023
ORIG_HALF_COUNT = 0x7E - 0x21 + 1                                                # 94 (半角 ASCII)
ORIG_HALF_TILES = ORIG_HALF_COUNT + (0xFFDF - 0xFFA1 + 1)                        # 157 (94+63 片假名)

# ── 保留集合表: 想保留原版字形的原版码位, 直接往里加一行 ────────────────
# 集合里的码位按原版码表取 tile, 放到新字库同一码位。
# 例: 0x8788=㊧ 0x8789=㊨, 译文里直接用这两个码位即可显示。
PRESERVE_CODES = {
    # 外字区 (游戏特殊图形)
    0xF040, 0xF041, 0xF042, 0xF043,
    0xF044, 0xF045, 0xF046, 0xF047,
    # 自定义保留
    0x8788, 0x8789,
}

# 渲染参数
FW_W, FW_H = 27, 27      # 24px 全角 tile
HW_W, HW_H = 15, 27      # 24px 半角 tile (整块复制, 不渲染)
SW_W, SW_H = 11, 11      # 08px 全角
TW_W, TW_H = 7, 11       # 08px 半角
GAMMA = 0.8              # 主笔画加粗系数


# ── 原版字库 ─────────────────────────────────────────────────────────
def load_orig(path: str, exact: int) -> bytes:
    data = open(path, "rb").read()
    if len(data) == exact + 1:            # 原版 pak 内多 1 个 0x00 尾字节
        data = data[:-1]
    if len(data) != exact:
        raise ValueError(f"{path}: 大小 {len(data)} != {exact}(±1)")
    return data


def orig_index(sjis: int) -> int:
    for s, e, b in ORIG_FULL:
        if s <= sjis <= e:
            return b + sjis - s
    raise KeyError(f"码位 {sjis:04X} 不在原版码表内")


# ── 渲染 ─────────────────────────────────────────────────────────────
_MAIN_LUT = np.round((np.arange(256) / 255.0) ** GAMMA * 15).astype(np.uint8)
_SHD_LUT = np.minimum(15, np.round(np.arange(256) / 17.0)).astype(np.uint8)


def shadow_layer(cov: np.ndarray) -> np.ndarray:
    """原版阴影配方: 主笔画覆盖度的窗口最大值 (左/上伸 2px, 右/下伸 1px), 可分离实现"""
    h, w = cov.shape
    p = np.zeros((h, w + 3), cov.dtype)          # 水平窗口 [x-2, x+1]
    p[:, 2:w + 2] = cov
    hm = np.maximum(np.maximum(p[:, :w], p[:, 1:w + 1]),
                    np.maximum(p[:, 2:w + 2], p[:, 3:w + 3]))
    p2 = np.zeros((h + 3, w), cov.dtype)         # 垂直窗口 [y-2, y+1]
    p2[2:h + 2, :] = hm
    return np.maximum(np.maximum(p2[:h], p2[1:h + 1]),
                      np.maximum(p2[2:h + 2], p2[3:h + 3]))


def encode_tile(canvas: np.ndarray) -> bytes:
    tile = (_MAIN_LUT[canvas] << 4) | _SHD_LUT[shadow_layer(canvas)]
    return tile.tobytes()


def render_canvas(face, char: str, w: int, h: int, cur: int) -> tuple[np.ndarray, int]:
    """cur = 当前字号; 返回 (画布, 新字号)。位图超宽时逐级缩号 (如"丂")"""
    canvas = np.zeros((h, w), np.uint8)
    if not char:
        return canvas, cur
    size = cur
    while True:
        face.load_char(char, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_NORMAL)
        bmp = face.glyph.bitmap
        if not bmp.width or not bmp.rows or size <= 8 or bmp.width <= w:
            break
        size -= 1
        face.set_pixel_sizes(0, size)
    buf = np.frombuffer(bytes(bmp.buffer), np.uint8, bmp.pitch * bmp.rows).reshape(bmp.rows, bmp.pitch)[:, :w]
    asc = face.size.ascender >> 6
    desc = face.size.descender >> 6
    dy = (h - (asc - desc)) // 2 + asc - int(face.glyph.bitmap_top)
    dx = max(0, (w - bmp.width) // 2)
    y0, y1 = max(0, dy), min(h, dy + bmp.rows)
    x0, x1 = max(0, dx), min(w, dx + bmp.width)
    if y1 > y0 and x1 > x0:
        canvas[y0:y1, x0:x1] = buf[y0 - dy:y1 - dy, x0 - dx:x1 - dx]
    return canvas, size


def build_full(face, fw_s: int, fw_e: int, cmap: dict, keep: dict, w: int, h: int, size: int) -> bytearray:
    fd0 = bytearray()
    face.set_pixel_sizes(0, size)
    cur = size
    for c in range(fw_s, fw_e + 1):
        tile = keep.get(c)
        if tile is not None:
            fd0 += tile
            continue
        canvas, cur = render_canvas(face, cmap.get(c, ""), w, h, cur)
        fd0 += encode_tile(canvas)
    return fd0


# ── 码表/装配 ────────────────────────────────────────────────────────
def build_table(fw_s: int, fw_e: int) -> tuple[bytearray, int]:
    fw_cnt = fw_e - fw_s + 1
    table = bytearray(448)

    def set_entry(i, base, s, e):
        struct.pack_into("<IHH", table, i * 8, base, s, e)

    for i in range(56):
        set_entry(i, 0, 0xFFFF, 0)
    set_entry(0, 0, fw_s, fw_e)              # GBK 全角整段 (含 0xF040-47 外字)
    set_entry(52, fw_cnt, 0xA1A1, 0xA1A1)    # base=全角总数 (引擎半角偏移 aO)
    set_entry(53, 0, 0x0021, 0x007E)         # 半角 ASCII
    set_entry(55, 0, 0x0020, 0x0020)         # 半角空格拦截
    return table, fw_cnt


def main(input_dir: str, output_dir: str):
    """输入目录放旧字库 (FONTEX24/08.FD0), 生成的写进输出目录"""
    t0 = time.time()
    if not os.path.exists(FONT_PATH):
        raise FileNotFoundError(f"找不到字体: {FONT_PATH}")
    os.makedirs(output_dir, exist_ok=True)
    cmap = {}
    for line in open("gbk.tbl", encoding="utf-16", errors="ignore"):
        line = line.rstrip("\r\n")
        if "=" in line:
            k, _, v = line.partition("=")
            cmap[int(k, 16)] = v
    codes = [c for c in cmap if c >= 0x80] + sorted(PRESERVE_CODES)
    fw_s, fw_e = min(codes), max(codes)

    orig24 = load_orig(os.path.join(input_dir, "FONTEX24.FD0"), ORIG_FULL_COUNT * 729 + ORIG_HALF_TILES * HW_W * HW_H)
    orig08 = load_orig(os.path.join(input_dir, "FONTEX08.FD0"), ORIG_FULL_COUNT * 121 + ORIG_HALF_TILES * TW_W * TW_H)
    half24 = orig24[ORIG_FULL_COUNT * 729: ORIG_FULL_COUNT * 729 + ORIG_HALF_COUNT * HW_W * HW_H]
    half08 = orig08[ORIG_FULL_COUNT * 121: ORIG_FULL_COUNT * 121 + ORIG_HALF_COUNT * TW_W * TW_H]

    # 保留集合 → 原版 tile 同码直取
    keep24, keep08, miss = {}, {}, []
    for code in sorted(PRESERVE_CODES):
        try:
            i = orig_index(code)
        except KeyError:
            miss.append(code)
            continue
        keep24[code] = orig24[i * 729:i * 729 + 729]
        keep08[code] = orig08[i * 121:i * 121 + 121]
    for code in miss:
        print(f"警告: 保留码位 {code:04X} 不在原版码表内, 用 TTF 渲染")

    face = freetype.Face(str(FONT_PATH))
    fd0 = build_full(face, fw_s, fw_e, cmap, keep24, FW_W, FW_H, 24) + half24
    fd0s = build_full(face, fw_s, fw_e, cmap, keep08, SW_W, SW_H, 8) + half08
    open(os.path.join(output_dir, "FONTEX24.FD0"), "wb").write(fd0)
    open(os.path.join(output_dir, "FONTEX08.FD0"), "wb").write(fd0s)

    table, fw_cnt = build_table(fw_s, fw_e)
    if os.path.exists("psth.exe"):
        try:
            with open("psth.exe", "r+b") as f:
                f.seek(EXE_OFF)
                f.write(table)
            print(f"EXE 表已注入 @{EXE_OFF:#x}")
        except PermissionError:
            print("警告: psth.exe 被占用 (游戏开着?), 本次未注入码表; 关闭游戏后重跑本脚本即可")
    else:
        print("未找到 psth.exe, 跳过表注入")
    print(f"全角 {fw_cnt} (保留原版 {len(keep24)}) + 半角 {ORIG_HALF_COUNT} (原版复制) | "
          f"FONTEX24 {len(fd0)}B / FONTEX08 {len(fd0s)}B | {time.time() - t0:.1f}s")
    print(f"输出: {output_dir}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: python refont.py 旧字库目录 输出目录")
        print("example: python refont.py backup .")
        raise SystemExit(1)
    main(sys.argv[1], sys.argv[2])
