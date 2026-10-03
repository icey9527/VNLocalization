from __future__ import annotations

import configparser
from dataclasses import dataclass
from pathlib import Path

import numpy as np

try:
    import freetype
except Exception:
    freetype = None


@dataclass(frozen=True)
class FontJobConfig:
    mode: str
    input_path: Path
    output_path: Path
    codetable_path: Path
    font_path: Path
    font_index: int
    font_size_px: float
    tile_w: int
    tile_h: int
    offset: int | None
    max_tiles: int | None
    endian_big: bool
    flipx: bool
    flipy: bool


def _parse_int(value: str) -> int:
    return int(value.strip(), 0)


def _parse_float(value: str) -> float:
    return float(value.strip())


def _read_ini_config(path: Path) -> FontJobConfig:
    cfg = configparser.ConfigParser(interpolation=None)
    if not cfg.read(path, encoding="utf-8"):
        raise FileNotFoundError(path)

    def required(section: str, key: str) -> str:
        if not cfg.has_option(section, key):
            raise KeyError(f"font.ini 缺少 [{section}] {key}")
        return cfg.get(section, key)

    base = path.parent
    mode = cfg.get("mode", "kind", fallback="patch").strip().lower()
    mode = {
        "patch": "patch",
        "file": "patch",
        "write": "patch",
        "inplace": "patch",
        "tiles": "tiles",
        "tile": "tiles",
        "dump": "tiles",
        "single": "tiles",
    }.get(mode)
    if mode is None:
        raise ValueError("mode.kind 只支持 patch / tiles")

    input_name = cfg.get("paths", "input", fallback="").strip()
    input_path = base / input_name if input_name or mode != "patch" else base / "input.bin"

    max_tiles_raw = cfg.get(
        "charset",
        "max_tiles",
        fallback=cfg.get("write", "max_tiles", fallback=""),
    ).strip()

    return FontJobConfig(
        mode=mode,
        input_path=input_path,
        output_path=base / required("paths", "output"),
        codetable_path=base / required("paths", "codetable"),
        font_path=base / required("paths", "font"),
        font_index=_parse_int(cfg.get("font", "index", fallback="0")),
        font_size_px=_parse_float(required("font", "size_px")),
        tile_w=_parse_int(cfg.get("tile", "width", fallback="24")),
        tile_h=_parse_int(cfg.get("tile", "height", fallback="24")),
        offset=_parse_int(required("write", "offset")) if mode == "patch" else None,
        max_tiles=_parse_int(max_tiles_raw) if max_tiles_raw else None,
        endian_big=cfg.getboolean("options", "endian_big", fallback=False),
        flipx=cfg.getboolean("options", "flipx", fallback=False),
        flipy=cfg.getboolean("options", "flipy", fallback=False),
    )


def _read_bitmap(face: "freetype.Face", char: str) -> np.ndarray:
    face.load_char(char, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_NORMAL)
    bitmap = face.glyph.bitmap
    width, rows, pitch = bitmap.width, bitmap.rows, bitmap.pitch
    if not width or not rows:
        return np.zeros((0, 0), dtype=np.uint8)

    raw = np.frombuffer(bytes(bitmap.buffer), dtype=np.uint8)
    stride = abs(pitch)
    raw = raw[: rows * stride].reshape(rows, stride)

    if pitch < 0:
        raw = raw[::-1]

    return raw[:, :width].copy()

def _fill_holes(mask: np.ndarray) -> np.ndarray:
    h, w = mask.shape
    bg = ~mask
    reached = np.zeros_like(bg)
    reached[0, :] = bg[0, :]
    reached[-1, :] = bg[-1, :]
    reached[:, 0] = bg[:, 0]
    reached[:, -1] = bg[:, -1]
    while True:
        nxt = reached.copy()
        nxt[1:, :] |= reached[:-1, :]
        nxt[:-1, :] |= reached[1:, :]
        nxt[:, 1:] |= reached[:, :-1]
        nxt[:, :-1] |= reached[:, 1:]
        nxt &= bg
        if np.array_equal(nxt, reached):
            break
        reached = nxt
    return mask | (bg & ~reached)

class TileEncoder:
    stroke_radius = 1.35
    stroke_feather = 0.8

    def __init__(
        self,
        face: "freetype.Face",
        tile_w: int,
        tile_h: int,
        *,
        endian_big: bool,
        flipx: bool,
        flipy: bool,
    ):
        self.face = face
        self.tile_w = tile_w
        self.tile_h = tile_h
        self.endian_big = endian_big
        self.flipx = flipx
        self.flipy = flipy
        self.tile_size = tile_w * tile_h // 2
        self._cache: dict[str, bytes] = {}

        limit = int(np.ceil(self.stroke_radius + self.stroke_feather))
        offsets = []
        for dy in range(-limit, limit + 1):
            for dx in range(-limit, limit + 1):
                distance = float(np.hypot(dx, dy))
                if distance <= self.stroke_radius + self.stroke_feather:
                    offsets.append((dx, dy, distance))
        self._stroke_offsets = tuple(
            sorted(offsets, key=lambda item: item[2])
        )

    def _place_body(self, bitmap: np.ndarray) -> np.ndarray:
        tile = np.zeros((self.tile_h, self.tile_w), dtype=np.float32)
        rows, cols = bitmap.shape
        if not rows or not cols:
            return tile

        face = self.face
        glyph = face.glyph
        asc = face.size.ascender >> 6
        desc = face.size.descender >> 6
        dy = (self.tile_h - (asc - desc)) // 2 + asc - int(glyph.bitmap_top)
        dx = max(0, (self.tile_w - cols) // 2)

        y0 = max(0, dy)
        y1 = min(self.tile_h, dy + rows)
        x0 = max(0, dx)
        x1 = min(self.tile_w, dx + cols)

        if y1 > y0 and x1 > x0:
            tile[y0:y1, x0:x1] = bitmap[y0 - dy:y1 - dy, x0 - dx:x1 - dx]

        return tile

    def _stroke(self, body: np.ndarray) -> np.ndarray:
        binary = body > 15
        if not binary.any():
            return np.zeros_like(body)

        h, w = body.shape
        feather = self.stroke_feather
        radius = self.stroke_radius
        alpha = np.zeros((h, w), dtype=np.float32)

        for dx, dy, distance in self._stroke_offsets:
            if distance > radius + feather:
                continue

            value = (radius + feather - distance) / feather * 255.0
            sx0 = max(0, -dx)
            sx1 = min(w, w - dx)
            sy0 = max(0, -dy)
            sy1 = min(h, h - dy)
            dx0 = max(0, dx)
            dy0 = max(0, dy)

            if sx1 <= sx0 or sy1 <= sy0:
                continue

            source = binary[sy0:sy1, sx0:sx1]
            target = alpha[dy0:dy0 + sy1 - sy0, dx0:dx0 + sx1 - sx0]
            np.maximum(target, source * value, out=target)

        interior = binary
        padded = np.pad(interior, 1)
        cardinal = (
            padded[:-2, 1:-1]
            + padded[2:, 1:-1]
            + padded[1:-1, :-2]
            + padded[1:-1, 2:]
        )
        diagonal = (
            padded[:-2, :-2]
            + padded[:-2, 2:]
            + padded[2:, :-2]
            + padded[2:, 2:]
        )
        dense = (~interior) & (cardinal + diagonal >= 5)
        alpha[dense] *= 0.25

        edge = (~interior) & (cardinal >= 2)
        alpha[edge] *= 0.65

        return alpha

    def render(self, char: str) -> bytes:
        cached = self._cache.get(char)
        if cached is not None:
            return cached

        body = self._place_body(_read_bitmap(self.face, char))
        stroke = self._stroke(body)

        tile = np.zeros((self.tile_h, self.tile_w), dtype=np.uint8)

        stroke_mask = (stroke > 1.0) & (body <= 15)
        if stroke_mask.any():
            tile[stroke_mask] = np.clip(
                1 + np.rint(stroke[stroke_mask] * 3.0 / 255.0),
                1,
                4,
            ).astype(np.uint8)

        body_mask = body > 15
        if body_mask.any():
            tile[body_mask] = np.clip(
                8 + np.rint(body[body_mask] * 7.0 / 255.0),
                8,
                15,
            ).astype(np.uint8)

        if self.flipx:
            tile = tile[:, ::-1]
        if self.flipy:
            tile = tile[::-1, :]

        pairs = tile.reshape(-1, 2)
        if self.endian_big:
            packed = (pairs[:, 0] << 4) | pairs[:, 1]
        else:
            packed = (pairs[:, 1] << 4) | pairs[:, 0]

        result = packed.tobytes()
        self._cache[char] = result
        return result


def parse_codetable(path: Path) -> list[str]:
    chars: list[str] = []
    with path.open("r", encoding="utf-16-le", errors="ignore") as file:
        for line in file:
            if "=" not in line:
                continue
            char = line.split("=", 1)[1]
            chars.append(char[0])
    return chars


def main() -> int:
    if freetype is None:
        return 2

    ini_path = Path.cwd() / "font.ini"
    if not ini_path.exists():
        return 2

    try:
        job = _read_ini_config(ini_path)
    except Exception as exc:
        print(f"配置错误: {exc}")
        return 2

    if not job.codetable_path.exists() or not job.font_path.exists():
        print("缺少码表文件或字体文件")
        return 2

    face = freetype.Face(str(job.font_path), index=job.font_index)
    face.set_char_size(0, round(job.font_size_px * 64), 72, 72)

    encoder = TileEncoder(
        face,
        job.tile_w,
        job.tile_h,
        endian_big=job.endian_big,
        flipx=job.flipx,
        flipy=job.flipy,
    )

    chars = parse_codetable(job.codetable_path)
    if job.max_tiles is not None:
        chars = chars[:job.max_tiles]

    tile_size = encoder.tile_size

    if job.mode == "patch":
        if job.offset is None:
            raise ValueError("patch 模式缺少 offset")
        with job.input_path.open("rb") as file:
            data = bytearray(file.read())
        base_offset = job.offset
        required_size = base_offset + len(chars) * tile_size
        if len(data) < required_size:
            data.extend(b"\x00" * (required_size - len(data)))
    else:
        data = bytearray(len(chars) * tile_size)
        base_offset = 0

    for index, char in enumerate(chars):
        offset = base_offset + index * tile_size
        data[offset:offset + tile_size] = encoder.render(char)

    with job.output_path.open("wb") as file:
        file.write(data)

    print(f"写入成功: {job.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
