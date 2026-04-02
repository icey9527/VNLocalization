from __future__ import annotations

import math
import configparser
import os
from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageDraw, ImageTk

try:
    import freetype
except Exception:
    freetype = None

try:
    import winreg
except Exception:
    winreg = None


INI_PATH = Path("sfnt.ini")


def scan_system_fonts() -> tuple[dict[str, str], list[str]]:
    fonts_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    out: dict[str, str] = {}
    if winreg is None:
        return out, []
    reg_paths = [
        r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts",
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Fonts",
    ]
    for reg_path in reg_paths:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path) as k:
                n = winreg.QueryInfoKey(k)[1]
                for i in range(n):
                    name, value, _ = winreg.EnumValue(k, i)
                    v = str(value)
                    p = Path(v)
                    if not p.is_absolute():
                        p = fonts_dir / v
                    if p.suffix.lower() not in (".ttf", ".otf", ".ttc"):
                        continue
                    if not p.exists():
                        continue
                    label = name.replace("(TrueType)", "").strip()
                    if label and label not in out:
                        out[label] = str(p)
        except Exception:
            continue
    names = sorted(out.keys(), key=lambda s: s.lower())
    return out, names


def u16le(b: bytes, o: int) -> int:
    return int.from_bytes(b[o:o + 2], "little")


def u32le(b: bytes, o: int) -> int:
    return int.from_bytes(b[o:o + 4], "little")


@dataclass
class Chunk:
    off: int
    tag: bytes
    size: int
    data_off: int
    unk: int

    @property
    def data_start(self) -> int:
        return self.off + self.data_off

    @property
    def end(self) -> int:
        return self.off + self.data_off + self.size


@dataclass
class Core:
    sfnt: Chunk
    inner: list[Chunk]
    mfnt0: Chunk
    mfnt1: Chunk
    mfnt2: Chunk
    mfgt: Chunk
    hfpr: Chunk | None
    glyph_count: int
    w0: int
    h0: int
    m0: int
    w1: int
    h1: int
    m1: int
    tbl0: int
    tbl1: int
    map_pairs: list[tuple[int, int]]


@dataclass
class GlyphItem:
    code: int
    ptr: int
    size: int
    w: int
    h: int
    mode: int


def read_chunk(b: bytes, off: int) -> Chunk:
    if off < 0 or off + 16 > len(b):
        raise ValueError(f"chunk out of range @0x{off:X}")
    c = Chunk(off, b[off:off + 4], u32le(b, off + 4), u32le(b, off + 8), u32le(b, off + 12))
    if c.data_off < 0x10:
        raise ValueError(f"bad data_off @0x{off:X}")
    if c.end > len(b):
        raise ValueError(f"chunk overflow @0x{off:X}")
    return c


def parse_sfnt(b: bytes) -> Core:
    sfnt = read_chunk(b, 0)
    if sfnt.tag != b"SFNT":
        raise ValueError("not SFNT")
    p = sfnt.data_start
    inner: list[Chunk] = []
    while p < sfnt.end:
        c = read_chunk(b, p)
        inner.append(c)
        p = c.end
        if c.tag == b"EOFC":
            break
    if not inner or inner[-1].tag != b"EOFC":
        raise ValueError("EOFC not found")
    if inner[-1].end != sfnt.end:
        raise ValueError("SFNT tail mismatch")
    if len(inner) < 5:
        raise ValueError("inner chunk count too small")
    mfnt0, mfnt1, mfnt2, mfgt = inner[0], inner[1], inner[2], inner[3]
    if (mfnt0.tag, mfnt1.tag, mfnt2.tag, mfgt.tag) != (b"MFNT", b"MFNT", b"MFNT", b"MFGT"):
        raise ValueError("inner tags mismatch")
    hfpr = None
    for c in inner[4:]:
        if c.tag == b"HFPR":
            hfpr = c
            break
    flags = u16le(b, mfnt0.off + 0x0E)
    glyph_count = 224 if (flags & 2) else 96
    w0 = u16le(b, mfnt0.off + 0x12)
    h0 = u16le(b, mfnt0.off + 0x10)
    m0 = u32le(b, mfnt0.off + 0x1C)
    w1 = u16le(b, mfnt1.off + 0x12)
    h1 = u16le(b, mfnt1.off + 0x10)
    m1 = u32le(b, mfnt1.off + 0x1C)
    if m0 not in (2, 4, 8, 16) or m1 not in (2, 4, 8, 16):
        raise ValueError("unsupported mode")
    tbl0 = u32le(b, mfnt1.off + 0x14)
    tbl1 = u32le(b, mfnt1.off + 0x18)
    pairs: list[tuple[int, int]] = []
    for i in range(mfgt.size // 8):
        cp = u32le(b, mfgt.data_start + i * 8)
        of = u32le(b, mfgt.data_start + i * 8 + 4)
        if cp == 0 and of == 0:
            break
        pairs.append((cp, of))
    return Core(sfnt, inner, mfnt0, mfnt1, mfnt2, mfgt, hfpr, glyph_count, w0, h0, m0, w1, h1, m1, tbl0, tbl1, pairs)


def step(w: int, h: int, mode: int) -> int:
    return (w * h * mode) >> 4


def mfnt1_ptr(c: Core, code: int, s1: int) -> int | None:
    if 0x8140 <= code < 0x83A0:
        rel = 0x20 + (code - 0x8140) * s1 - (((code - 0x8140) >> 8) << 6) * s1
        return c.mfnt1.off + rel
    if 0x8890 <= code < 0x9000:
        rel = c.tbl0 + (code & 0xFF) * s1 + 192 * (((code - 0x8800) >> 8)) * s1 - 144 * s1
        return c.mfnt1.off + rel
    if 0x9040 <= code < 0x9880:
        rel = c.tbl1 + (code & 0xFF) * s1 + 192 * (((code - 0x9000) >> 8)) * s1 - 64 * s1
        return c.mfnt1.off + rel
    return None


def decode_tile(src: bytes, w: int, h: int, mode: int) -> list[int]:
    out = [0] * (w * h)
    if mode == 16:
        i = 0
        for y in range(h):
            for x in range(w):
                if x % 2 == 0:
                    bb = src[i]
                    i += 1
                    q = (bb >> 4) & 0xF
                else:
                    q = bb & 0xF
                out[y * w + x] = q
        return out
    if mode == 8:
        lut = [0, 2, 4, 6, 9, 11, 13, 15]
        i = 0
        for y in range(h):
            for x in range(w):
                if x % 2 == 0:
                    bb = src[i]
                    i += 1
                    q = (bb >> 4) & 7
                else:
                    q = bb & 7
                out[y * w + x] = lut[q]
        return out
    if mode == 4:
        lut = [0, 5, 10, 15]
        i = 0
        for y in range(h):
            for x in range(w):
                if x % 4 == 0:
                    bb = src[i]
                    i += 1
                out[y * w + x] = lut[(bb >> (6 - 2 * (x % 4))) & 3]
        return out
    if mode == 2:
        lut = [0, 15]
        i = 0
        for y in range(h):
            for x in range(w):
                if x % 8 == 0:
                    bb = src[i]
                    i += 1
                out[y * w + x] = lut[(bb >> (7 - (x % 8))) & 1]
        return out
    raise ValueError(mode)


def encode_tile(px: list[int], w: int, h: int, mode: int) -> bytes:
    if mode == 16:
        out = bytearray((w * h + 1) // 2)
        j = 0
        for i in range(0, w * h, 2):
            out[j] = ((max(0, min(15, px[i])) & 0xF) << 4) | (max(0, min(15, px[i + 1])) & 0xF)
            j += 1
        return bytes(out)
    if mode == 8:
        out = bytearray((w * h + 1) // 2)
        j = 0
        for i in range(0, w * h, 2):
            p0 = max(0, min(7, round(px[i] * 7 / 15)))
            p1 = max(0, min(7, round(px[i + 1] * 7 / 15)))
            out[j] = (p0 << 4) | p1
            j += 1
        return bytes(out)
    if mode == 4:
        out = bytearray((w * h + 3) // 4)
        j = 0
        for y in range(h):
            for x0 in range(0, w, 4):
                bb = 0
                for k in range(4):
                    q = max(0, min(3, round(px[y * w + x0 + k] * 3 / 15)))
                    bb |= (q & 3) << (6 - 2 * k)
                out[j] = bb
                j += 1
        return bytes(out)
    if mode == 2:
        out = bytearray((w * h + 7) // 8)
        j = 0
        for y in range(h):
            for x0 in range(0, w, 8):
                bb = 0
                for k in range(8):
                    bb |= (1 if px[y * w + x0 + k] >= 8 else 0) << (7 - k)
                out[j] = bb
                j += 1
        return bytes(out)
    raise ValueError(mode)


def parse_tbl(path: Path) -> list[tuple[int, str]]:
    txt = path.read_text(encoding="utf-16", errors="ignore")
    out: list[tuple[int, str]] = []
    for line in txt.splitlines():
        s = line.strip()
        if not s or "=" not in s:
            continue
        l, r = s.split("=", 1)
        l = l.strip()
        r = r.strip()
        if not l or not r:
            continue
        try:
            out.append((int(l, 16), r[0]))
        except Exception:
            pass
    return out


def write_tbl(path: Path, pairs: list[tuple[int, str]]) -> None:
    path.write_text("\n".join(f"{c:04X}={ch}" for c, ch in pairs), encoding="utf-16")


def sjis_char(code: int) -> str:
    if code <= 0xFF:
        return bytes([code]).decode("cp932")
    return bytes([(code >> 8) & 0xFF, code & 0xFF]).decode("cp932")


def render_encoded(face: "freetype.Face", ch: str, w: int, h: int, mode: int) -> bytes:
    face.load_char(ch, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_NORMAL)
    slot = face.glyph
    bmp = slot.bitmap
    tile = [0] * (w * h)
    asc = face.size.ascender >> 6
    desc = face.size.descender >> 6
    fh = asc - desc
    base = (h - fh) // 2 + asc
    x0 = int(slot.bitmap_left)
    if bmp.width >= w:
        x0 = 0
    else:
        x0 = max(0, min(x0, w - int(bmp.width)))
    y0 = base - int(slot.bitmap_top)
    bw = int(bmp.width)
    bh = int(bmp.rows)
    pitch = int(bmp.pitch)
    buf = bmp.buffer
    for y in range(bh):
        ty = y0 + y
        if ty < 0 or ty >= h:
            continue
        ro = ((bh - 1 - y) * (-pitch)) if pitch < 0 else y * pitch
        for x in range(bw):
            tx = x0 + x
            if tx < 0 or tx >= w:
                continue
            tile[ty * w + tx] = max(0, min(15, round((buf[ro + x] / 255) * 15)))
    return encode_tile(tile, w, h, mode)


def build_chunk_payload(raw_chunk: bytes, payload: bytes) -> bytes:
    data_off = u32le(raw_chunk, 8)
    if data_off < 0x10 or data_off > len(raw_chunk):
        raise ValueError("bad data_off")
    out = bytearray(raw_chunk[:data_off])
    out[4:8] = len(payload).to_bytes(4, "little")
    out += payload
    return bytes(out)


class BuildDialog:
    def __init__(self, app: "SfntEditorApp"):
        self.app = app
        self.win = tk.Toplevel(app.root)
        self.win.title("修改字库")
        self.win.resizable(False, False)
        self.win.transient(app.root)
        self.win.grab_set()
        frm = ttk.Frame(self.win, padding=10)
        frm.grid(sticky="nsew")

        ttk.Label(frm, text="码表").grid(row=0, column=0, sticky="w")
        self.tbl_var = tk.StringVar(value=self.app.cfg_get("build", "tbl", ""))
        ttk.Entry(frm, textvariable=self.tbl_var, width=46).grid(row=1, column=0, sticky="ew")
        ttk.Button(frm, text="选择", command=self.pick_tbl).grid(row=1, column=1, padx=(8, 0))

        ttk.Label(frm, text="系统字体").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.font_name_var = tk.StringVar(value=self.app.cfg_get("build", "font_name", ""))
        self.font_box = ttk.Combobox(frm, textvariable=self.font_name_var, state="readonly", width=46)
        self.font_box["values"] = self.app.font_names
        self.font_box.grid(row=3, column=0, sticky="ew")
        self.font_box.bind("<<ComboboxSelected>>", self.on_font_selected)
        self.font_var = tk.StringVar(value=self.app.cfg_get("build", "font", ""))
        ent_font = ttk.Entry(frm, textvariable=self.font_var, width=46, state="readonly")
        ent_font.grid(row=4, column=0, sticky="ew")

        row4 = ttk.Frame(frm)
        row4.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Label(row4, text="字号").pack(side="left")
        self.size_var = tk.StringVar(value=self.app.cfg_get("build", "size_px", "24"))
        ttk.Entry(row4, textvariable=self.size_var, width=6).pack(side="left", padx=(6, 12))
        ttk.Label(row4, text="字体索引").pack(side="left")
        self.idx_var = tk.StringVar(value=self.app.cfg_get("build", "font_index", "0"))
        ttk.Entry(row4, textvariable=self.idx_var, width=6).pack(side="left", padx=(6, 0))

        ttk.Label(frm, text="输出SFNT").grid(row=6, column=0, sticky="w", pady=(8, 0))
        self.out_var = tk.StringVar(value=self.app.cfg_get("build", "out", "new_font.SFNT"))
        ttk.Entry(frm, textvariable=self.out_var, width=46).grid(row=7, column=0, sticky="ew")
        ttk.Button(frm, text="选择", command=self.pick_out).grid(row=7, column=1, padx=(8, 0))

        btns = ttk.Frame(frm)
        btns.grid(row=8, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="生成", command=self.build).pack(side="left")
        ttk.Button(btns, text="关闭", command=self.win.destroy).pack(side="left", padx=(8, 0))

        frm.columnconfigure(0, weight=1)
        if self.font_name_var.get() in self.app.font_map:
            self.font_var.set(self.app.font_map[self.font_name_var.get()])
        else:
            self.font_var.set("")
        self.center()

    def center(self) -> None:
        self.win.update_idletasks()
        px = self.app.root.winfo_rootx()
        py = self.app.root.winfo_rooty()
        pw = self.app.root.winfo_width()
        ph = self.app.root.winfo_height()
        ww = self.win.winfo_width()
        wh = self.win.winfo_height()
        x = px + (pw - ww) // 2
        y = py + (ph - wh) // 2
        self.win.geometry(f"+{max(0,x)}+{max(0,y)}")

    def pick_tbl(self) -> None:
        p = filedialog.askopenfilename(title="选择码表", filetypes=[("Table", "*.tbl"), ("All Files", "*.*")], parent=self.win)
        if p:
            self.tbl_var.set(p)

    def on_font_selected(self, _=None) -> None:
        name = self.font_name_var.get().strip()
        p = self.app.font_map.get(name)
        if p:
            self.font_var.set(p)

    def pick_out(self) -> None:
        p = filedialog.asksaveasfilename(
            title="保存为",
            defaultextension=".SFNT",
            initialfile=self.out_var.get() or "new_font.SFNT",
            filetypes=[("SFNT", "*.SFNT;*.sfnt"), ("All Files", "*.*")],
            parent=self.win,
        )
        if p:
            self.out_var.set(p)

    def build(self) -> None:
        try:
            tbl = Path(self.tbl_var.get().strip())
            font_name = self.font_name_var.get().strip()
            font_path = self.app.font_map.get(font_name, "")
            if not font_path:
                raise ValueError("请先从下拉框选择系统字体")
            font = Path(font_path)
            out = Path(self.out_var.get().strip())
            px = int(self.size_var.get().strip() or "24")
            idx = int(self.idx_var.get().strip() or "0")
            self.app.cfg_set("build", "tbl", str(tbl))
            self.app.cfg_set("build", "font", str(font))
            self.app.cfg_set("build", "font_name", self.font_name_var.get().strip())
            self.app.cfg_set("build", "out", str(out))
            self.app.cfg_set("build", "size_px", str(px))
            self.app.cfg_set("build", "font_index", str(idx))
            self.app.cfg_save()
            self.app.build_from_tbl(tbl, font, out, px, idx)
            messagebox.showinfo("完成", f"生成成功:\n{out}", parent=self.win)
            self.win.destroy()
        except Exception as e:
            messagebox.showerror("错误", f"生成失败:\n{e}", parent=self.win)


class SfntEditorApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("SFNT 字库工具")
        self.root.geometry("1200x800")
        self.sfnt_path: Path | None = None
        self.data: bytearray | None = None
        self.core: Core | None = None
        self.partitions: dict[str, list[GlyphItem]] = {}
        self.sheet_photo = None
        self.font_map, self.font_names = scan_system_fonts()
        self.cfg = configparser.ConfigParser(interpolation=None)
        self.cfg_read()
        self.build_menu()
        self.build_ui()

    def cfg_read(self) -> None:
        if INI_PATH.exists():
            self.cfg.read(INI_PATH, encoding="utf-8")
        if not self.cfg.has_section("build"):
            self.cfg.add_section("build")
        defaults = {
            "tbl": "",
            "font": "",
            "font_name": "",
            "out": "new_font.SFNT",
            "size_px": "24",
            "font_index": "0",
        }
        changed = False
        for k, v in defaults.items():
            if not self.cfg.has_option("build", k):
                self.cfg.set("build", k, v)
                changed = True
        if changed or not INI_PATH.exists():
            self.cfg_save()

    def cfg_save(self) -> None:
        with INI_PATH.open("w", encoding="utf-8") as f:
            self.cfg.write(f)

    def cfg_get(self, section: str, key: str, default: str = "") -> str:
        if self.cfg.has_option(section, key):
            return self.cfg.get(section, key)
        return default

    def cfg_set(self, section: str, key: str, value: str) -> None:
        if not self.cfg.has_section(section):
            self.cfg.add_section(section)
        self.cfg.set(section, key, value)

    def build_menu(self) -> None:
        m = tk.Menu(self.root)
        f = tk.Menu(m, tearoff=0)
        f.add_command(label="打开SFNT", command=self.open_sfnt)
        f.add_command(label="导出码表", command=self.export_tbl)
        f.add_separator()
        f.add_command(label="退出", command=self.root.destroy)
        m.add_cascade(label="文件", menu=f)
        t = tk.Menu(m, tearoff=0)
        t.add_command(label="修改字库", command=self.open_build_dialog)
        m.add_cascade(label="工具", menu=t)
        self.root.config(menu=m)

    def build_ui(self) -> None:
        top = ttk.Frame(self.root, padding=8)
        top.pack(side="top", fill="x")
        ttk.Label(top, text="分区").pack(side="left")
        self.part_var = tk.StringVar()
        self.part_box = ttk.Combobox(top, textvariable=self.part_var, state="readonly", width=42)
        self.part_box.pack(side="left", padx=(8, 0))
        self.part_box.bind("<<ComboboxSelected>>", self.on_part_changed)
        main = ttk.Frame(self.root, padding=(8, 0, 8, 8))
        main.pack(side="top", fill="both", expand=True)
        self.canvas = tk.Canvas(main, bg="#10141c", highlightthickness=0)
        vs = ttk.Scrollbar(main, orient="vertical", command=self.canvas.yview)
        hs = ttk.Scrollbar(main, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(0, weight=1)
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)
        self.canvas.bind("<Shift-MouseWheel>", self.on_shift_wheel)
        self.status = ttk.Label(self.root, text="就绪", anchor="w")
        self.status.pack(side="bottom", fill="x")

    def set_status(self, s: str) -> None:
        self.status.config(text=s)
        self.root.update_idletasks()

    def on_mousewheel(self, event) -> None:
        stepv = int(-event.delta / 120)
        if stepv == 0:
            stepv = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(stepv, "units")

    def on_shift_wheel(self, event) -> None:
        steph = int(-event.delta / 120)
        if steph == 0:
            steph = -1 if event.delta > 0 else 1
        self.canvas.xview_scroll(steph, "units")

    def build_partitions(self) -> None:
        assert self.core is not None
        c = self.core
        s0 = step(c.w0, c.h0, c.m0)
        s1 = step(c.w1, c.h1, c.m1)
        p: dict[str, list[GlyphItem]] = {}
        p[f"半角 MFNT0 ({c.glyph_count})"] = [
            GlyphItem(0x20 + i, c.mfnt0.data_start + i * s0, s0, c.w0, c.h0, c.m0) for i in range(c.glyph_count)
        ]
        p["全角 8140-839F"] = [
            GlyphItem(code, ptr, s1, c.w1, c.h1, c.m1)
            for code in range(0x8140, 0x83A0)
            for ptr in [mfnt1_ptr(c, code, s1)]
            if ptr is not None
        ]
        p["全角 8890-8FFF"] = [
            GlyphItem(code, ptr, s1, c.w1, c.h1, c.m1)
            for code in range(0x8890, 0x9000)
            for ptr in [mfnt1_ptr(c, code, s1)]
            if ptr is not None
        ]
        p["全角 9040-987F"] = [
            GlyphItem(code, ptr, s1, c.w1, c.h1, c.m1)
            for code in range(0x9040, 0x9880)
            for ptr in [mfnt1_ptr(c, code, s1)]
            if ptr is not None
        ]
        p[f"MFGT 映射 ({len(c.map_pairs)})"] = [
            GlyphItem(code, c.mfnt2.off + 0x10 + off, s1, c.w1, c.h1, c.m1) for code, off in c.map_pairs
        ]
        self.partitions = p

    def open_sfnt(self) -> None:
        p = filedialog.askopenfilename(
            title="选择SFNT",
            filetypes=[("SFNT", "*.SFNT;*.sfnt"), ("All Files", "*.*")],
        )
        if not p:
            return
        try:
            b = Path(p).read_bytes()
            core = parse_sfnt(b)
            self.data = bytearray(b)
            self.core = core
            self.sfnt_path = Path(p)
            self.build_partitions()
            names = list(self.partitions.keys())
            self.part_box["values"] = names
            if names:
                self.part_var.set(names[0])
                self.draw_partition(names[0])
            self.set_status(
                f"已打开: {p} | MFNT0={core.glyph_count} | MFGT={len(core.map_pairs)} | "
                f"头: size=0x{core.sfnt.size:X}, data_off=0x{core.sfnt.data_off:X}, unk=0x{core.sfnt.unk:X}"
            )
        except Exception as e:
            messagebox.showerror("错误", f"解析失败:\n{e}")

    def draw_partition(self, name: str) -> None:
        if self.data is None:
            return
        items = self.partitions.get(name, [])
        if not items:
            return
        w = items[0].w
        h = items[0].h
        cols = 40
        cellw = w + 1
        cellh = h + 11
        rows = max(1, math.ceil(len(items) / cols))
        img = Image.new("RGB", (cols * cellw, rows * cellh), (16, 20, 28))
        dr = ImageDraw.Draw(img)
        for i, it in enumerate(items):
            if it.ptr < 0 or it.ptr + it.size > len(self.data):
                continue
            px = decode_tile(bytes(self.data[it.ptr:it.ptr + it.size]), it.w, it.h, it.mode)
            tile = Image.new("L", (it.w, it.h))
            tile.putdata([v * 17 for v in px])
            x = (i % cols) * cellw
            y = (i // cols) * cellh
            img.paste(Image.merge("RGB", (tile, tile, tile)), (x, y))
            dr.text((x + 1, y + h), f"{it.code:04X}", fill=(146, 177, 247))
        self.sheet_photo = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.sheet_photo)
        self.canvas.configure(scrollregion=(0, 0, img.width, img.height))
        self.set_status(f"{name} | {len(items)} 字")

    def on_part_changed(self, _=None) -> None:
        n = self.part_var.get()
        if n:
            self.draw_partition(n)

    def collect_codes(self) -> list[int]:
        s = set()
        for items in self.partitions.values():
            for it in items:
                s.add(it.code)
        return sorted(s)

    def export_tbl(self) -> None:
        if self.data is None:
            messagebox.showwarning("提示", "请先打开SFNT")
            return
        out = filedialog.asksaveasfilename(
            title="导出码表",
            defaultextension=".tbl",
            initialfile="Out.tbl",
            filetypes=[("Table", "*.tbl"), ("All Files", "*.*")],
        )
        if not out:
            return
        rows: list[tuple[int, str]] = []
        for code in self.collect_codes():
            try:
                rows.append((code, sjis_char(code)))
            except Exception:
                pass
        write_tbl(Path(out), rows)
        messagebox.showinfo("完成", f"导出成功: {out}\n共 {len(rows)} 条")

    def open_build_dialog(self) -> None:
        if self.data is None or self.core is None:
            messagebox.showwarning("提示", "请先打开SFNT")
            return
        if freetype is None:
            messagebox.showerror("错误", "未找到 freetype-py，请先安装: pip install freetype-py")
            return
        BuildDialog(self)

    def build_from_tbl(self, tbl_path: Path, font_path: Path, out_sfnt: Path, size_px: int, font_index: int) -> None:
        if self.data is None or self.core is None:
            raise ValueError("no sfnt opened")
        if not tbl_path.exists():
            raise FileNotFoundError(tbl_path)
        if not font_path.exists():
            raise FileNotFoundError(font_path)
        try:
            face = freetype.Face(str(font_path), index=font_index)
        except Exception as e:
            raise ValueError(f"字体打开失败: {font_path}\n{e}")
        face.set_pixel_sizes(0, size_px)
        code_to_char = {code: ch for code, ch in parse_tbl(tbl_path)}
        c = self.core
        d = bytearray(self.data)
        s1 = step(c.w1, c.h1, c.m1)

        fixed = 0
        ignored_half = 0
        mapped_codes: list[int] = []
        for code, ch in code_to_char.items():
            if 0x20 <= code < 0x20 + c.glyph_count:
                ignored_half += 1
                continue
            ptr = mfnt1_ptr(c, code, s1)
            if ptr is not None and ptr + s1 <= len(d):
                d[ptr:ptr + s1] = render_encoded(face, ch, c.w1, c.h1, c.m1)
                fixed += 1
            else:
                mapped_codes.append(code)
        mapped_codes = sorted(set(mapped_codes))

        mfnt2_payload = bytearray(len(mapped_codes) * s1)
        mfgt_payload = bytearray((len(mapped_codes) + 1) * 8)
        for i, code in enumerate(mapped_codes):
            glyph_off = i * s1
            mfnt2_payload[glyph_off:glyph_off + s1] = render_encoded(face, code_to_char[code], c.w1, c.h1, c.m1)
            off = 0x10 + glyph_off
            e = i * 8
            mfgt_payload[e:e + 4] = int(code).to_bytes(4, "little")
            mfgt_payload[e + 4:e + 8] = int(off).to_bytes(4, "little")

        inner_raw = [bytes(d[ch.off:ch.end]) for ch in c.inner]
        inner_raw[2] = build_chunk_payload(inner_raw[2], bytes(mfnt2_payload))
        inner_raw[3] = build_chunk_payload(inner_raw[3], bytes(mfgt_payload))

        out = bytearray(d[:c.sfnt.data_off])
        for r in inner_raw:
            out += r
        out[4:8] = (len(out) - c.sfnt.data_off).to_bytes(4, "little")
        out_sfnt.write_bytes(out)
        self.set_status(f"完成: fixed={fixed} mapped={len(mapped_codes)} ignored_half={ignored_half}")


def main() -> int:
    root = tk.Tk()
    SfntEditorApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
