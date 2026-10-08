from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import configparser

try:
    import freetype  # freetype-py
except Exception:  # pragma: no cover
    freetype = None


@dataclass(frozen=True)
class FontJobConfig:
    mode: str  # "patch" | "tiles"
    input_path: Path
    output_path: Path
    codetable_path: Path
    font_path: Path

    font_index: int
    font_size_px: int

    tile_w: int
    tile_h: int

    offset: int | None
    max_tiles: int | None

    endian_big: bool
    flipx: bool
    flipy: bool


def _parse_int(s: str) -> int:
    s = s.strip()
    return int(s, 0)


def _read_ini_config(ini_path: Path) -> FontJobConfig:
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(ini_path, encoding="utf-8")

    def must_get(section: str, key: str) -> str:
        if not cfg.has_option(section, key):
            raise KeyError(f"font.ini 缺少 [{section}] {key}")
        return cfg.get(section, key)

    base_dir = ini_path.parent

    mode_raw = cfg.get("mode", "kind", fallback="patch").strip().lower()
    mode_map = {
        "patch": "patch",
        "file": "patch",
        "write": "patch",
        "inplace": "patch",
        "tiles": "tiles",
        "tile": "tiles",
        "dump": "tiles",
        "single": "tiles",
    }
    mode = mode_map.get(mode_raw)
    if mode is None:
        raise ValueError("mode.kind 只支持 patch / tiles")

    input_s = cfg.get("paths", "input", fallback="").strip()
    if mode == "patch":
        if not input_s:
            raise KeyError("font.ini 缺少 [paths] input（mode.kind=patch 需要）")
        input_path = base_dir / input_s
    else:
        input_path = base_dir / input_s if input_s else base_dir / "input.bin"

    output_path = base_dir / must_get("paths", "output")
    codetable_path = base_dir / must_get("paths", "codetable")
    font_path = base_dir / must_get("paths", "font")

    font_index = _parse_int(cfg.get("font", "index", fallback="0"))
    font_size_px = _parse_int(must_get("font", "size_px"))

    tile_w = _parse_int(cfg.get("tile", "width", fallback="24"))
    tile_h = _parse_int(cfg.get("tile", "height", fallback="24"))

    offset = None
    if mode == "patch":
        offset = _parse_int(must_get("write", "offset"))
    max_tiles_s = cfg.get("charset", "max_tiles", fallback=cfg.get("write", "max_tiles", fallback=""))
    max_tiles = _parse_int(max_tiles_s) if max_tiles_s.strip() else None

    endian_big = cfg.getboolean("options", "endian_big", fallback=False)
    flipx = cfg.getboolean("options", "flipx", fallback=False)
    flipy = cfg.getboolean("options", "flipy", fallback=False)

    if tile_w <= 0 or tile_h <= 0:
        raise ValueError("tile 尺寸必须为正数")
    if (tile_w * tile_h) % 2 != 0:
        raise ValueError("tile_w * tile_h 必须为偶数（4bpp 每字节 2 像素）")
    if font_size_px <= 0:
        raise ValueError("font.size_px 必须为正数")
    if offset is not None and offset < 0:
        raise ValueError("write.offset 不能为负数")

    return FontJobConfig(
        mode=mode,
        input_path=input_path,
        output_path=output_path,
        codetable_path=codetable_path,
        font_path=font_path,
        font_index=font_index,
        font_size_px=font_size_px,
        tile_w=tile_w,
        tile_h=tile_h,
        offset=offset,
        max_tiles=max_tiles,
        endian_big=endian_big,
        flipx=flipx,
        flipy=flipy,
    )


def _write_ini_template(ini_path: Path) -> None:
    ini_path.write_text(
        "\n".join(
            [
                "[mode]",
                "; patch: 把字形写进现有文件（按 offset 顺序覆盖/扩容）",
                "; tiles: 只输出连续 tile 数据（单文件，不读 input，不用 offset）",
                "kind = patch",
                "",
                "[paths]",
                "; patch 模式才会读取 input；tiles 模式可留空",
                "input = input.bin",
                "output = output.bin",
                "codetable = code.tbl",
                "font = font.ttf",
                "",
                "[font]",
                "; freetype 像素字号（不做下采样）",
                "size_px = 24",
                "; 字体集合（TTC/OTC）时可切换 index",
                "index = 0",
                "",
                "[tile]",
                "; 输出 tile 的像素尺寸",
                "width = 24",
                "height = 24",
                "",
                "[charset]",
                "; 最大写入/输出多少个字符；留空表示用完整码表长度",
                "max_tiles =",
                "",
                "[write]",
                "; 仅 patch 模式使用：从文件的哪个偏移开始写入（支持 0x 十六进制）",
                "offset = 0x0",
                "",
                "[options]",
                "; endian_big=false 时每字节为 (右像素<<4)|左像素；true 时为 (左<<4)|右",
                "endian_big = false",
                "flipx = false",
                "flipy = false",
                "",
            ]
        ),
        encoding="utf-8",
    )

def _mono_pixel(buf: bytes, row_off: int, x: int) -> int:
    byte = buf[row_off + (x >> 3)]
    bit = 7 - (x & 7)
    return 255 if (byte >> bit) & 1 else 0

class TileEncoder:
    def __init__(self, face: "freetype.Face", tile_w: int, tile_h: int, *, endian_big: bool, flipx: bool, flipy: bool):
        self.face = face
        self.tile_w = tile_w
        self.tile_h = tile_h
        self.endian_big = endian_big
        self.flipx = flipx
        self.flipy = flipy

        ascender = self.face.size.ascender >> 6
        descender = self.face.size.descender >> 6
        font_height = ascender - descender
        self._baseline_y = (self.tile_h - font_height) // 2 + ascender

    def _render_glyph_to_gray_tile(self, ch: str) -> bytearray:
        tile = bytearray(self.tile_w * self.tile_h)

        self.face.load_char(
            ch,
            freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_NORMAL
        )
        slot = self.face.glyph
        bmp = slot.bitmap

        width = int(bmp.width)
        rows = int(bmp.rows)
        if width <= 0 or rows <= 0:
            return tile

        dst_x0 = int(slot.bitmap_left)
        if width >= self.tile_w:
            dst_x0 = 0
        else:
            if dst_x0 < 0:
                dst_x0 = 0
            elif dst_x0 + width > self.tile_w:
                dst_x0 = self.tile_w - width
        dst_y0 = self._baseline_y - int(slot.bitmap_top)    

        pitch = int(bmp.pitch)
        buf = bmp.buffer

        for y in range(rows):
            ty = dst_y0 + y
            if ty < 0 or ty >= self.tile_h:
                continue
            row_off = ((rows - 1 - y) * (-pitch)) if pitch < 0 else (y * pitch)
            for x in range(width):
                tx = dst_x0 + x
                if tx < 0 or tx >= self.tile_w:
                    continue
                tile[ty * self.tile_w + tx] = buf[row_off + x]
        return tile

    def render_text(self, text: str) -> bytes:
        if not text:
            return bytes((self.tile_w * self.tile_h) // 2)

        # 0..255 灰度 tile
        tile_gray = self._render_glyph_to_gray_tile(text[0])

        # flip（可选）
        if self.flipx or self.flipy:
            flipped = bytearray(len(tile_gray))
            for y in range(self.tile_h):
                sy = self.tile_h - 1 - y if self.flipy else y
                for x in range(self.tile_w):
                    sx = self.tile_w - 1 - x if self.flipx else x
                    flipped[y * self.tile_w + x] = tile_gray[sy * self.tile_w + sx]
            tile_gray = flipped

        # gamma + 量化到 4bpp (0..15)
        gamma = 1  # 0.7~0.9 自己试
        tile_4bpp = bytearray(
            min(15, max(0, int((((v / 255.0) ** gamma) * 15) + 0.5)))
            for v in tile_gray
        )

        # 打包 2 像素 / 字节
        out = bytearray((self.tile_w * self.tile_h) // 2)
        j = 0
        for i in range(0, len(tile_4bpp), 2):
            p0 = tile_4bpp[i]
            p1 = tile_4bpp[i + 1]
            if self.endian_big:
                out[j] = ((p0 & 0xF) << 4) | (p1 & 0xF)
            else:
                out[j] = ((p1 & 0xF) << 4) | (p0 & 0xF)
            j += 1

        return bytes(out)

def parse_codetable(filename):
    """更健壮的码表解析"""
    chars = []
    with open(filename, 'r', encoding='utf-16-le',errors='ignore') as f:
        for line in f:
            line = line.strip()
            if '=' in line:
                parts = line.split('=', 1)
                if len(parts) == 2:
                    chars.append(parts[1].strip())
    return chars

def main():
    ini_path = Path.cwd() / "font.ini"
    if not ini_path.exists():
        _write_ini_template(ini_path)
        print(f"已生成模板配置：{ini_path}")
        print("请填写路径/参数后再次运行。")
        return 2

    if freetype is None:
        print("未找到 freetype-py（import freetype 失败）。")
        print("请先安装：pip install freetype-py")
        return 2

    try:
        job = _read_ini_config(ini_path)
    except Exception as e:
        print(f"读取配置失败：{e}")
        return 2

    if not job.codetable_path.exists():
        print(f"找不到码表：{job.codetable_path}")
        return 2
    if not job.font_path.exists():
        print(f"找不到字体：{job.font_path}")
        return 2
    if job.mode == "patch" and not job.input_path.exists():
        print(f"找不到输入文件：{job.input_path}")
        return 2

    # 初始化编码器
    face = freetype.Face(str(job.font_path), index=job.font_index)
    face.set_pixel_sizes(0, job.font_size_px)

    encoder = TileEncoder(
        face,
        job.tile_w,
        job.tile_h,
        endian_big=job.endian_big,
        flipx=job.flipx,
        flipy=job.flipy,
    )
    tile_size = (job.tile_w * job.tile_h) // 2  # 4bpp计算
    print(f"Tile尺寸: {job.tile_w}x{job.tile_h} 4bpp = {tile_size}字节")
    print(f"模式: {job.mode}")

    # 加载字符
    chars = parse_codetable(str(job.codetable_path))
    if job.max_tiles is not None:
        chars = chars[: job.max_tiles]
    print(f"准备写入 {len(chars)} 个字符")

    if job.mode == "patch":
        assert job.offset is not None
        with open(job.input_path, "rb") as f:
            data = bytearray(f.read())
        required_size = job.offset + len(chars) * tile_size
        if len(data) < required_size:
            data += bytes(required_size - len(data))
            print(f"文件已扩展至 {len(data)//1024}KB")
        base_offset = job.offset
    else:
        data = bytearray(len(chars) * tile_size)
        base_offset = 0

    # 批量写入
    success_count = 0
    for idx, char in enumerate(chars):
        try:
            offset = base_offset + idx * tile_size
            if offset + tile_size > len(data):
                print(f"偏移越界: 0x{offset:X}")
                break

            # 使用TileEncoder直接生成tile数据
            tile_data = encoder.render_text(
                char, 
            )
            
            # 写入数据
            data[offset:offset+tile_size] = tile_data
            success_count += 1
        except Exception as e:
            print(f"失败字符 {idx} '{char}': {str(e)}")
        if idx % 32 == 0 or idx + 1 == len(chars):
            print(f"\r{idx+1}/{len(chars)}", end="")

    print()

    # 保存文件
    with open(job.output_path, "wb") as f:
        f.write(data)
    print(f"写入完成，成功率 {success_count}/{len(chars)}")

if __name__ == "__main__":
    raise SystemExit(main())
