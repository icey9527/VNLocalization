#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IPB disassembler/assembler (concise, supports cp932 and custom tables)
Format: b'IPB0' + <u32le data_size> + <data[data_size]>
Usage:
  python 1.py d <input_dir> <output_dir> [--enc cp932] [--table table.txt]
  python 1.py e <input_dir> <output_dir> [--enc cp932] [--table table.txt]
Notes:
- Strings are zero-terminated (C-style).
- Unknown opcodes are preserved as "UNKNOWN 0xNN".
- If --table is provided, it overrides --enc.
- Custom table file format (examples):
    8140=　
    8141=、
    8142=。
  Left side is hex bytes (even length, spaces allowed), right side is the character.
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import argparse, struct, shlex, sys
import unicodedata
import struct

from PIL import ImageFont
# ---------- Opcodes (inferred) ----------
@dataclass(frozen=True)
class OpSpec:
    code: int
    name: str
    args: tuple  # items in {"u8", "strz"}

OPS = [
    OpSpec(0x01, "TEXT", ("strz",)),
    OpSpec(0x02, "PAUSE", ()),
    OpSpec(0x10, "NEWLINE", ()),
    OpSpec(0x11, "CLEAR", ()),
    OpSpec(0x20, "BG", ("u8", "strz")),
    OpSpec(0x21, "NOP", ()),
    OpSpec(0x22, "FREE", ("u8",)),
    OpSpec(0x40, "TOGGLE", ()),
    OpSpec(0x41, "SETSTEP", ("u8",)),
    OpSpec(0x60, "BGM_PLAY", ("strz",)),
    OpSpec(0x61, "BGM_STOP", ()),
    OpSpec(0x62, "SE_PLAY", ("strz",)),
    OpSpec(0x63, "SOUND_STOPALL", ()),      # 99
    OpSpec(0x64, "SOUND_PLAY_TOGGLE", ("strz",)),  # 100
    OpSpec(0x80, "NOP", ()),
]
CODE2SPEC = {s.code: s for s in OPS}
NAME2SPEC = {s.name: s for s in OPS}



# ========== AUTO FONT CONFIG ==========
TTF_PATH = r"font.ttf"  # 改成你的字体路径

def _draw_glyph_16x16(font, char: str) -> bytes:
    from PIL import Image, ImageDraw
    
    # 如果是音乐符号，使用日文字体
    if char == '♪':
        try:
            font = ImageFont.truetype("msgothic.ttc", 16)  # Windows 日文字体
        except:
            pass  # 如果失败就还用原来的字体

    W = H = 16
    img = Image.new("L", (W, H), 0)
    draw = ImageDraw.Draw(img)

    l, t, r, b = font.getbbox(char)
    w, h = r - l, b - t

    # 剩下的代码保持不变...
    # 水平居中
    x = (W - w) // 2 - l
    # 垂直对齐：严格按你给的逻辑
    if char in '，。！？；：""\'\'（）【】《》、.,!?;:\'"()[]<>/「」『』':
        y = H - h - t
    elif char in '一丶乀乁':
        y = (H - h) // 2 - t + 2
    else:
        y = (H - h) // 2 - t

    draw.text((x, y), char, fill=255, font=font)

    # 二值化
    img = img.point(lambda p: 255 if p >= 128 else 0, mode="1")
    px = img.load()

    # 行打包：bit0=最左像素
    rows = bytearray()
    for yy in range(H):
        word = 0
        for xx in range(W):
            if px[xx, yy] != 0:
                word |= (1 << xx)
        rows.extend(struct.pack("<H", word))
    return bytes(rows)

# ---------- String codecs ----------
def _is_hex_byte_pair(s: str) -> bool:
    return len(s) == 2 and all(c in "0123456789abcdefABCDEF" for c in s)

class Codec:
    def decode_bytes(self, b: bytes) -> str: raise NotImplementedError
    def encode_text(self, s: str) -> bytes: raise NotImplementedError

class AutoCodecOnTheFly:
    def __init__(self, tbl_path: Path, fontbin_path: Path):
        from PIL import ImageFont
        self.map: dict[str, bytes] = {}
        self.next_code = 0x8100  # 改：从 0x8100 开始
        self.tbl = open(tbl_path, "w", encoding="utf-16")
        self.fontf = open(fontbin_path, "wb")
        self.font = ImageFont.truetype(TTF_PATH, 16)

    def close(self):
        try: self.tbl.close()
        except: pass
        try: self.fontf.close()
        except: pass

    def _assign(self, ch: str):
        # 跳过 cp932 编码范围内的编码
        while True:
            code = self.next_code
            high = (code >> 8) & 0xFF
            low = code & 0xFF
            
            # 检查是否在 cp932 范围内
            # 第一字节：0x81-0x9F 或 0xE0-0xFC
            # 第二字节：0x40-0x7E 或 0x80-0xFC
            is_in_cp932 = False
            if (0x81 <= high <= 0x9F) or (0xE0 <= high <= 0xFC):
                if (0x40 <= low <= 0x7E) or (0x80 <= low <= 0xFC):
                    is_in_cp932 = True
            
            self.next_code += 1
            
            if is_in_cp932:
                break
            else:
                self.fontf.write(b'\x00' * 32)
                continue
        
        # 文本编码用：高字节在前
        code_bytes = bytes([(code >> 8) & 0xFF, code & 0xFF])
        self.map[ch] = code_bytes
        self.tbl.write(f"{code:04X}={ch}\n")
        # 写入字形
        glyph = _draw_glyph_16x16(self.font, ch)
        self.fontf.write(glyph)

    def encode_text(self, s: str) -> bytes:
        out = bytearray()
        for ch in s:
            # 正确的ASCII判断：使用Unicode码点
            o = ord(ch)
            if o < 0x80:  # 真正的ASCII字符 (0x00-0x7F)
                out.append(o)  # 直接写出ASCII字节
                continue
                
            # 非ASCII字符：走映射表逻辑
            if ch not in self.map:
                self._assign(ch)
            out.extend(self.map[ch])
        return bytes(out)

class StdCodec(Codec):
    def __init__(self, encoding: str = "utf-8"):
        self.enc = encoding

    def decode_bytes(self, b: bytes) -> str:
        try:
            return b.decode(self.enc)
        except Exception:
            return "".join(f"\\x{x:02X}" for x in b)

    def encode_text(self, s: str) -> bytes:
        # First materialize \xNN into raw bytes; others re-encoded by target codec
        out = bytearray(); buf = bytearray()
        i = 0; n = len(s)
        def flush_buf():
            nonlocal buf
            if buf:
                try:
                    out.extend(bytes(buf).decode("utf-8").encode(self.enc))
                except Exception as e:
                    raise ValueError(f"Text not encodable by {self.enc}: {bytes(buf).decode('utf-8')} ({e})")
                buf.clear()
        while i < n:
            if s[i] == "\\" and i + 3 < n and s[i+1] == "x" and _is_hex_byte_pair(s[i+2:i+4]):
                flush_buf()
                out.append(int(s[i+2:i+4], 16))
                i += 4
            else:
                buf.extend(s[i].encode("utf-8"))
                i += 1
        flush_buf()
        return bytes(out)

class TableCodec(Codec):
    def __init__(self, table_path: Path):
        # Parse "8140=　" etc. Left: hex bytes, right: character(s)
        text = table_path.read_text(encoding="utf-16")
        b2s: dict[bytes, str] = {}
        s2b: dict[str, bytes] = {}
        for ln, raw in enumerate(text.splitlines(), 1):
            line = raw.rstrip('\n\r')
            if not line or line.startswith("#") or line.startswith(";"):
                continue
            if "=" not in line:
                raise ValueError(f"{table_path}:{ln}: missing '='")
            left, right = [x.rstrip('\n\r') for x in line.split("=", 1)]
            left = left.replace(" ", "")
            if len(left) % 2 != 0:
                raise ValueError(f"{table_path}:{ln}: hex length must be even: {left}")
            try:
                bs = bytes(int(left[i:i+2], 16) for i in range(0, len(left), 2))
            except Exception:
                raise ValueError(f"{table_path}:{ln}: bad hex: {left}")
            # keep right verbatim (allow multi-char, but encode only if length==1 or user uses \xNN)
            val = right
            b2s[bs] = val
            if len(val) == 1 and val not in s2b:
                s2b[val] = bs  # first wins if duplicates
        self.b2s = b2s
        self.s2b = s2b
        self.key_lengths = sorted({len(k) for k in b2s.keys()}, reverse=True) or [1]

    def decode_bytes(self, b: bytes) -> str:
        # Greedy longest-match; ASCII passthrough
        out = []
        i = 0; n = len(b)
        while i < n:
            # ASCII straight-through
            if b[i] < 0x80:
                out.append(chr(b[i])); i += 1; continue
            matched = False
            for L in self.key_lengths:
                if i + L <= n:
                    seg = b[i:i+L]
                    if seg in self.b2s:
                        out.append(self.b2s[seg]); i += L; matched = True; break
            if not matched:
                out.append(f"\\x{b[i]:02X}"); i += 1
        return "".join(out)

    def encode_text(self, s: str) -> bytes:
        # honor \xNN, ASCII passthrough, table for others
        out = bytearray()
        i = 0; n = len(s)
        while i < n:
            if s[i] == "\\" and i + 3 < n and s[i+1] == "x" and _is_hex_byte_pair(s[i+2:i+4]):
                out.append(int(s[i+2:i+4], 16)); i += 4; continue
            ch = s[i]
            code = self.s2b.get(ch)
            if code is not None:
                out.extend(code)
            else:
                o = ord(ch)
                if o < 0x80:
                    out.append(o)  # ASCII passthrough
                else:
                    raise ValueError(f"Character not in table: {ch!r} (U+{o:04X})")
            i += 1
        return bytes(out)

# ---------- Binary helpers ----------
class Cur:
    def __init__(self, data: bytes): self.d, self.p, self.n = data, 0, len(data)
    def eof(self) -> bool: return self.p >= self.n
    def tell(self) -> int: return self.p
    def u8(self) -> int:
        if self.p >= self.n: raise EOFError("read past end")
        b = self.d[self.p]; self.p += 1; return b
    def cstr(self) -> bytes:
        if self.p >= self.n: return b""
        end = self.d.find(b"\x00", self.p)
        if end < 0: s = self.d[self.p:]; self.p = self.n; return s
        s = self.d[self.p:end]; self.p = end + 1; return s

# ---------- Disassemble / Assemble ----------
def disasm(data: bytes, codec: Codec) -> list[str]:
    cur = Cur(data)
    out = ["; ipb-disasm"]
    while not cur.eof():
        off = cur.tell()
        op = cur.u8()
        spec = CODE2SPEC.get(op)
        if not spec:
            out.append(f"UNKNOWN 0x{op:02X} ; off=0x{off:04X}")
            continue
        args = []
        for a in spec.args:
            if a == "u8":
                args.append(str(cur.u8()))
            elif a == "strz":
                s = codec.decode_bytes(cur.cstr())
                args.append(f"\"{s.replace('\\', '\\\\').replace('\"', '\\\"').replace('\n', '\\n').replace('\t', '\\t').replace('\r', '\\r')}\"")
        out.append(f"{spec.name}" + ("" if not args else " " + " ".join(args)))
    return out

def assemble(lines: list[str], codec: Codec) -> bytes:
    out = bytearray()
    for idx, line in enumerate(lines, 1):
        raw = line.rstrip('\n\r')
        if not raw or raw.startswith(("#", ";")): continue
        try:
            toks = shlex.split(raw, posix=True)
        except Exception as e:
            raise ValueError(f"Line {idx}: {e}\n> {raw}")
        name = toks[0].upper()
        if name == "DB":
            for t in toks[1:]:
                if t.startswith(("0x", "0X")): out.append(int(t, 16) & 0xFF)
                elif t.startswith("\"") and t.endswith("\""):
                    out.extend(codec.encode_text(t[1:-1]))
                else: out.append(int(t) & 0xFF)
            continue
        if name == "OP":
            if len(toks) != 2: raise ValueError(f"Line {idx}: OP needs 1 arg")
            out.append(int(toks[1], 0) & 0xFF); continue
        spec = NAME2SPEC.get(name)
        if not spec: raise ValueError(f"Line {idx}: unknown mnemonic {name}\n> {raw}")
        out.append(spec.code)
        need = list(spec.args); got = toks[1:]
        if len(got) != len(need): raise ValueError(f"Line {idx}: {name} expects {len(need)} args, got {len(got)}")
        for a, v in zip(need, got):
            if a == "u8": 
                out.append(int(v, 0) & 0xFF)
            elif a == "strz":
                if v.startswith("\"") and v.endswith("\""): 
                    v = v[1:-1]
                
                # 只有 TEXT 指令使用自定义编码，其他指令直接编码
                encoded = codec.encode_text(v.replace('\\n', '\n')) if name == "TEXT" else v.encode('cp932')
                out.extend(encoded)
                out.append(0)
    return bytes(out)

# ---------- File I/O ----------
def read_ipb(p: Path) -> bytes:
    b = p.read_bytes()
    if len(b) < 8 or b[:4] != b"IPB0": raise ValueError(f"Bad IPB header: {p}")
    size = struct.unpack("<I", b[4:8])[0]
    if 8 + size > len(b): raise ValueError(f"Data size exceeds file length: {p}")
    return b[8:8+size]

def write_ipb(p: Path, data: bytes):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"IPB0" + struct.pack("<I", len(data)) + data)

def run_d(in_dir: Path, out_dir: Path, codec: Codec):
    files = sorted(in_dir.rglob("*.ipb"))
    if not files: print(f"No .ipb under {in_dir}"); return
    for f in files:
        rel = f.relative_to(in_dir)
        try:
            lines = disasm(read_ipb(f), codec)
            (out_dir / rel.with_suffix(".txt")).parent.mkdir(parents=True, exist_ok=True)
            (out_dir / rel.with_suffix(".txt")).write_text("\n".join(lines), encoding="utf-8")
            print(f"[D] {f} -> {out_dir/rel.with_suffix('.txt')}")
        except Exception as e:
            print(f"[!] {f}: {e}")

def run_e(in_dir: Path, out_dir: Path, _codec_unused):
    files = sorted(in_dir.rglob("*.txt"))
    if not files:
        print(f"No .txt under {in_dir}")
        return

    eden = "EDEN.tbl"
    fontbin = out_dir / "font_z_16.bin"
    codec = AutoCodecOnTheFly(eden, fontbin)

    try:
        for f in files:
            rel = f.relative_to(in_dir)
            try:
                lines = f.read_text(encoding="utf-8").splitlines()
                data = assemble(lines, codec)      # assemble 内部：写 strz 后 append(0)
                write_ipb(out_dir / rel.with_suffix(".ipb"), data)
                print(f"[E] {f} -> {out_dir/rel.with_suffix('.ipb')} ({len(data)} bytes)")
            except Exception as e:
                print(f"[!] {f}: {e}")
    finally:
        codec.close()

    print(f"[AUTO] table written: {eden}")
    print(f"[AUTO] font written:  {fontbin}")

# ---------- CLI ----------
def build_codec(enc: str | None, table: str | None) -> Codec:
    if table: return TableCodec(Path(table))
    return StdCodec(enc or "cp932")

def main(argv=None):
    ap = argparse.ArgumentParser(description="IPB disassembler/assembler")
    ap.add_argument("mode", choices=["d", "e"], help="d=disassemble, e=assemble")
    ap.add_argument("input_dir")
    ap.add_argument("output_dir")
    ap.add_argument("--enc", default=None, help="text encoding, e.g. cp932/utf-8 (ignored if --table given)")
    ap.add_argument("--table", default=None, help="custom table path (overrides --enc)")
    args = ap.parse_args(argv)

    codec = build_codec(args.enc, args.table)
    in_dir, out_dir = Path(args.input_dir), Path(args.output_dir)
    if args.mode == "d": run_d(in_dir, out_dir, codec)
    else: run_e(in_dir, out_dir, codec)

if __name__ == "__main__":
    sys.exit(main())