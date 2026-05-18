from __future__ import annotations

import math
import struct
import sys
from pathlib import Path

try:
    from PIL import Image
except Exception:
    Image = None

try:
    import freetype
except Exception:
    freetype = None


W = 24
H = 24
GLYPH_COUNT = 8192
PAIR_COUNT = GLYPH_COUNT // 2
PACKED_BLOCK = 0x120
HEADER_SIZE = 0x1E
DESC_OFF = HEADER_SIZE
DESC_SIZE = PAIR_COUNT * 4
TAIL_OFF = 0x401E
BODY_OFF = 0x5000
BODY_SIZE = PAIR_COUNT * PACKED_BLOCK
COLS = 64

SKIP_GLYPH_RANGES: tuple[tuple[int, int], ...] = ((0, 1409),)
BASE_FOP_PATH: Path | None = None
KEEP_BASE_DESC = False

RAW4_LEVELS = (0, 15, 10, 5)
ENCODE_RAMP = (0, 3, 2, 1)
GLYPH_MARGIN = 1
GLYPH_MIN_WIDTH = 12


def in_ranges(index: int, ranges: tuple[tuple[int, int], ...]) -> bool:
    return any(start <= index <= end for start, end in ranges)


def read_tbl_chars(path: Path) -> list[str]:
    chars: list[str] = []
    for raw in path.read_text(encoding="utf-16").splitlines():
        if "=" not in raw:
            continue
        rhs = raw.split("=", 1)[1].split(";", 1)[0]
        if rhs:
            chars.append(rhs[:1])
    return chars


def read_symbol_chars(path: Path) -> list[str]:
    chars: list[str] = []
    for raw in path.read_text(encoding="utf-16").splitlines():
        if raw.endswith("\r"):
            raw = raw[:-1]
        chars.append(raw[:1] if raw else "")
    return chars


def remap_chars_to_glyphs(chars: list[str], *, skip_ranges: tuple[tuple[int, int], ...]) -> list[str]:
    glyph_chars = [""] * GLYPH_COUNT
    source_index = 0
    for glyph_index in range(GLYPH_COUNT):
        if in_ranges(glyph_index, skip_ranges):
            continue
        if source_index >= len(chars):
            break
        glyph_chars[glyph_index] = chars[source_index]
        source_index += 1
    if source_index < len(chars):
        print(f"warning: {len(chars) - source_index} extra chars beyond available glyph slots")
    return glyph_chars


def merge_glyph_chars(symbol_chars: list[str], chars: list[str], *, skip_ranges: tuple[tuple[int, int], ...]) -> tuple[list[str], list[bool]]:
    glyph_chars = [""] * GLYPH_COUNT
    changed = [False] * GLYPH_COUNT

    symbol_start = 1
    for i, ch in enumerate(symbol_chars):
        glyph_index = symbol_start + i
        if glyph_index >= GLYPH_COUNT:
            break
        glyph_chars[glyph_index] = ch
        changed[glyph_index] = True

    source_index = 0
    for glyph_index in range(GLYPH_COUNT):
        if in_ranges(glyph_index, skip_ranges):
            continue
        if source_index >= len(chars):
            break
        glyph_chars[glyph_index] = chars[source_index]
        changed[glyph_index] = True
        source_index += 1

    if len(symbol_chars) > GLYPH_COUNT:
        print(f"warning: {len(symbol_chars) - GLYPH_COUNT} extra symbol chars beyond glyph slots")
    if source_index < len(chars):
        print(f"warning: {len(chars) - source_index} extra chars beyond available glyph slots")
    return glyph_chars, changed


def unpack_block(block: bytes, odd: bool) -> list[int]:
    pixels: list[int] = []
    for b in block:
        lo = b & 0x0F
        hi = (b >> 4) & 0x0F
        pixels.append((lo >> 2) & 0x3 if odd else lo & 0x3)
        pixels.append((hi >> 2) & 0x3 if odd else hi & 0x3)
    return pixels


def pack_pair(pix0: list[int], pix1: list[int]) -> bytes:
    out = bytearray(PACKED_BLOCK)
    for i in range(PACKED_BLOCK):
        p0a = pix0[i * 2]
        p0b = pix0[i * 2 + 1]
        p1a = pix1[i * 2]
        p1b = pix1[i * 2 + 1]
        out[i] = (p0a & 0x3) | ((p1a & 0x3) << 2) | ((p0b & 0x3) << 4) | ((p1b & 0x3) << 6)
    return bytes(out)


def p2_to_raw4_byte(a: int, b: int) -> int:
    return (RAW4_LEVELS[b] << 4) | RAW4_LEVELS[a]


def glyph_bounds(pixels: list[int]) -> tuple[int, int]:
    left = W
    right = -1
    for y in range(H):
        row = pixels[y * W : (y + 1) * W]
        for x, v in enumerate(row):
            if v:
                left = min(left, x)
                right = max(right, x)
    if right < left:
        return 0, 0
    left = max(0, left - GLYPH_MARGIN)
    right = min(W, right + 1 + GLYPH_MARGIN)
    if right - left < GLYPH_MIN_WIDTH:
        center = (left + right) / 2
        left = int(round(center - GLYPH_MIN_WIDTH / 2))
        right = left + GLYPH_MIN_WIDTH
        if left < 0:
            left = 0
            right = GLYPH_MIN_WIDTH
        if right > W:
            right = W
            left = W - GLYPH_MIN_WIDTH
    return left, right


def load_fop_bytes(data: bytes) -> tuple[bytes, bytes, bytes]:
    if len(data) < BODY_OFF + BODY_SIZE:
        raise ValueError("bad FOP size")
    return (
        data[DESC_OFF : DESC_OFF + DESC_SIZE],
        data[TAIL_OFF:BODY_OFF],
        data[BODY_OFF : BODY_OFF + BODY_SIZE],
    )


def load_fop(path: Path) -> tuple[bytes, bytes, bytes]:
    return load_fop_bytes(path.read_bytes())


def load_fop_glyphs(path: Path) -> list[list[int]]:
    _, _, body = load_fop(path)
    glyphs: list[list[int]] = []
    for i in range(PAIR_COUNT):
        block = body[i * PACKED_BLOCK : (i + 1) * PACKED_BLOCK]
        glyphs.append(unpack_block(block, False))
        glyphs.append(unpack_block(block, True))
    return glyphs


def make_header() -> bytes:
    head = bytearray(HEADER_SIZE)
    struct.pack_into("<I", head, 0x08, DESC_OFF)
    struct.pack_into("<I", head, 0x0C, 0x4000)
    struct.pack_into("<I", head, 0x10, BODY_OFF)
    struct.pack_into("<I", head, 0x14, BODY_SIZE)
    head[0x18:0x1C] = bytes((0x20, 0x01, 0x05, 0x18))
    head[0x1C:0x1E] = bytes((0x18, 0x00))
    return bytes(head)


def save_png(path: Path, width: int, height: int, rgba: bytes) -> None:
    if Image is None:
        raise RuntimeError("missing pillow, install with: pip install pillow")
    img = Image.frombytes("RGBA", (width, height), rgba)
    img.save(path)


def extract_sheet_from_body(body: bytes, out_png: Path) -> None:
    count = (len(body) // PACKED_BLOCK) * 2
    rows = math.ceil(count / COLS)
    width = COLS * W
    height = rows * H
    rgba = bytearray(b"\xFF" * (width * height * 4))

    for i in range(count):
        block = body[(i >> 1) * PACKED_BLOCK : ((i >> 1) + 1) * PACKED_BLOCK]
        pixels = unpack_block(block, bool(i & 1))
        gx = (i % COLS) * W
        gy = (i // COLS) * H
        for y in range(H):
            dst = ((gy + y) * width + gx) * 4
            row = bytearray()
            for x in range(W):
                v = (255, 0, 96, 176)[pixels[y * W + x]]
                row.extend((v, v, v, 255))
            rgba[dst : dst + W * 4] = row

    save_png(out_png, width, height, bytes(rgba))


def fop_to_raw4(data: bytes) -> bytes:
    desc, _, body = load_fop_bytes(data)
    raw = bytearray()
    for i in range(PAIR_COUNT):
        block = body[i * PACKED_BLOCK : (i + 1) * PACKED_BLOCK]
        for odd in (False, True):
            pixels = unpack_block(block, odd)
            for j in range(0, len(pixels), 2):
                raw.append(p2_to_raw4_byte(pixels[j], pixels[j + 1]))
    if len(desc) != DESC_SIZE:
        raise ValueError("bad descriptor size")
    return bytes(raw)


class TileEncoder:
    def __init__(self, font_path: Path, size_px: int = 22, face_index: int = 0):
        if freetype is None:
            raise RuntimeError("missing freetype-py, install with: pip install freetype-py")
        self.face = freetype.Face(str(font_path), index=face_index)
        self.face.set_pixel_sizes(0, size_px)
        asc = self.face.size.ascender >> 6
        desc = self.face.size.descender >> 6
        self.baseline = (H - (asc - desc)) // 2 + asc

    def render(self, ch: str) -> list[int]:
        tile = [0] * (W * H)
        if not ch:
            return tile
        self.face.load_char(ch[:1], freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_NORMAL)
        bmp = self.face.glyph.bitmap
        bw = int(bmp.width)
        bh = int(bmp.rows)
        if bw <= 0 or bh <= 0:
            return tile
        x0 = int(self.face.glyph.bitmap_left)
        if bw >= W:
            x0 = 0
        else:
            x0 = min(max(0, x0), W - bw)
        y0 = self.baseline - int(self.face.glyph.bitmap_top)
        pitch = int(bmp.pitch)
        buf = bytes(bmp.buffer)
        row_stride = abs(pitch)
        for y in range(bh):
            ty = y0 + y
            if not (0 <= ty < H):
                continue
            row_off = ((bh - 1 - y) * row_stride) if pitch < 0 else (y * row_stride)
            for x in range(bw):
                tx = x0 + x
                if 0 <= tx < W:
                    src_index = row_off + x
                    if 0 <= src_index < len(buf):
                        gray = buf[src_index]
                        level = min(3, (gray * 3 + 127) // 255)
                        tile[ty * W + tx] = ENCODE_RAMP[level]
        return tile


def build_desc_and_body(
    glyphs: list[list[int]],
    *,
    base_desc: bytes | None = None,
    changed: list[bool] | None = None,
) -> tuple[bytes, bytes]:
    desc = bytearray(base_desc if base_desc is not None else (b"\x00" * DESC_SIZE))
    body = bytearray(BODY_SIZE)
    for i in range(PAIR_COUNT):
        pix0 = glyphs[i * 2]
        pix1 = glyphs[i * 2 + 1]
        idx0 = i * 2
        idx1 = idx0 + 1
        if base_desc is None or changed is not None:
            if base_desc is None or (changed is not None and changed[idx0]):
                left0, right0 = glyph_bounds(pix0)
            else:
                left0, right0 = desc[i * 4], desc[i * 4 + 1]

            if base_desc is None or (changed is not None and changed[idx1]):
                left1, right1 = glyph_bounds(pix1)
            else:
                left1, right1 = desc[i * 4 + 2], desc[i * 4 + 3]

            if base_desc is None or (changed is not None and (changed[idx0] or changed[idx1])):
                desc[i * 4 : i * 4 + 4] = bytes((left0, right0, left1, right1))
        body[i * PACKED_BLOCK : (i + 1) * PACKED_BLOCK] = pack_pair(pix0, pix1)
    return bytes(desc), bytes(body)


def build_fop(
    glyphs: list[list[int]],
    out_path: Path,
    *,
    base_desc: bytes | None = None,
    changed: list[bool] | None = None,
) -> None:
    desc, body = build_desc_and_body(
        glyphs,
        base_desc=base_desc,
        changed=changed,
    )
    out = bytearray()
    out.extend(make_header())
    out.extend(desc)
    out.extend(b"\x00" * (BODY_OFF - TAIL_OFF))
    out.extend(body)
    if len(out) != BODY_OFF + BODY_SIZE:
        raise ValueError(f"bad generated size: 0x{len(out):X}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(bytes(out))


def cmd_extract(fop_path: Path, out_png: Path) -> int:
    _, _, body = load_fop(fop_path)
    extract_sheet_from_body(body, out_png)
    print(out_png)
    return 0


def cmd_transform(fop_path: Path, out_raw: Path) -> int:
    data = fop_path.read_bytes()
    desc, _, _ = load_fop_bytes(data)
    out_raw.write_bytes(fop_to_raw4(data))
    metrics_path = out_raw.with_suffix(out_raw.suffix + ".metrics.bin")
    metrics = bytearray(GLYPH_COUNT * 2)
    for i in range(PAIR_COUNT):
        a, b, c, d = desc[i * 4 : i * 4 + 4]
        metrics[i * 4 : i * 4 + 4] = bytes((a, b, c, d))
    metrics_path.write_bytes(metrics)
    print(out_raw)
    print(metrics_path)
    return 0


def cmd_create(
    font_path: Path,
    symbol_tbl_path: Path,
    tbl_path: Path,
    out_fop: Path,
    *,
    base_fop: Path | None,
    keep_desc: bool,
) -> int:
    symbol_chars = read_symbol_chars(symbol_tbl_path)
    chars = read_tbl_chars(tbl_path)
    glyph_chars, changed = merge_glyph_chars(symbol_chars, chars, skip_ranges=SKIP_GLYPH_RANGES)
    base_glyphs = load_fop_glyphs(base_fop) if base_fop is not None else None
    base_desc = load_fop(base_fop)[0] if base_fop is not None else None
    changed[0] = False

    enc = TileEncoder(font_path)
    glyphs: list[list[int]] = []
    for i in range(GLYPH_COUNT):
        if base_glyphs is not None and in_ranges(i, SKIP_GLYPH_RANGES):
            glyphs.append(base_glyphs[i])
        else:
            glyphs.append(enc.render(glyph_chars[i]))
        if (i + 1) % 256 == 0 or i + 1 == GLYPH_COUNT:
            print(f"\r{i + 1}/{GLYPH_COUNT}", end="")
    print()

    build_fop(
        glyphs,
        out_fop,
        base_desc=base_desc,
        changed=changed,
    )
    verify_png = Path.cwd() / (out_fop.stem + ".png")
    _, _, body = load_fop(out_fop)
    extract_sheet_from_body(body, verify_png)
    print(out_fop)
    print(verify_png)
    return 0


def usage() -> None:
    print("usage:")
    print("  font.py e <font.fop> <sheet.png>")
    print("  font.py c <font.ttf> <symbol.tbl> <code.tbl> <out.fop> [-b base.fop] [-n]")
    print("  font.py t <font.fop> <out.raw4>")
    sys.exit(1)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        usage()

    mode = argv[1]
    args = argv[2:]
    base_fop: Path | None = None
    keep_desc = False

    if mode == "c":
        cleaned: list[str] = []
        i = 0
        while i < len(args):
            arg = args[i]
            if arg == "-b":
                if i + 1 >= len(args):
                    usage()
                base_fop = Path(args[i + 1])
                i += 2
                continue
            if arg == "-n":
                keep_desc = True
                i += 1
                continue
            cleaned.append(arg)
            i += 1
        args = cleaned

    if mode == "e" and len(args) == 2:
        return cmd_extract(Path(args[0]), Path(args[1]))
    if mode == "c" and len(args) == 4:
        return cmd_create(
            Path(args[0]),
            Path(args[1]),
            Path(args[2]),
            Path(args[3]),
            base_fop=base_fop,
            keep_desc=keep_desc,
        )
    if mode == "t" and len(args) == 2:
        return cmd_transform(Path(args[0]), Path(args[1]))

    usage()
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
