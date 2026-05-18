from __future__ import annotations

import math
import struct
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


W = 24
H = 24
GLYPH_COUNT = 8192
PAIR_COUNT = GLYPH_COUNT // 2
PACKED_BLOCK = 0x120
HEADER_SIZE = 0x1E
DESC_OFF = HEADER_SIZE
DESC_SIZE = PAIR_COUNT * 4
BODY_OFF = 0x5000
BODY_SIZE = PAIR_COUNT * PACKED_BLOCK
GRID_COLS = 16
GRID_ROWS = 16
GRID_CELL = 30
ZOOM = 12

PREVIEW_FILL = ("#ffffff", "#000000", "#606060", "#b0b0b0")
PIXEL_FILL = ("#ffffff", "#111111", "#666666", "#bbbbbb")


def read_tbl_chars(path: Path) -> list[str]:
    data = path.read_bytes()
    for enc in ("utf-16", "utf-16-le", "utf-8-sig", "utf-8", "cp932", "gbk"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = data.decode("latin-1")

    chars: list[str] = []
    for line in text.splitlines():
        if "=" not in line:
            continue
        rhs = line.split("=", 1)[1].split(";", 1)[0]
        chars.append(rhs[:1] if rhs else "")
    return chars


def unpack_block(block: bytes, odd: bool) -> list[int]:
    pixels: list[int] = []
    for b in block:
        lo = b & 0x0F
        hi = (b >> 4) & 0x0F
        pixels.append((lo >> 2) & 0x3 if odd else lo & 0x3)
        pixels.append((hi >> 2) & 0x3 if odd else hi & 0x3)
    return pixels


class FontData:
    def __init__(self, path: Path):
        self.path = path
        self.data = bytearray(path.read_bytes())
        if len(self.data) < BODY_OFF + BODY_SIZE:
            raise ValueError("不是有效的 FNT2626.FOP 文件")
        self.desc = self.data[DESC_OFF : DESC_OFF + DESC_SIZE]
        self.body = self.data[BODY_OFF : BODY_OFF + BODY_SIZE]

    def glyph_pixels(self, glyph_index: int) -> list[int]:
        pair_index = glyph_index // 2
        odd = bool(glyph_index & 1)
        block = self.body[pair_index * PACKED_BLOCK : (pair_index + 1) * PACKED_BLOCK]
        return unpack_block(block, odd)

    def glyph_desc(self, glyph_index: int) -> tuple[int, int]:
        pair_index = glyph_index // 2
        off = pair_index * 4 + (2 if glyph_index & 1 else 0)
        return self.desc[off], self.desc[off + 1]

    def set_glyph_desc(self, glyph_index: int, left: int, right: int) -> None:
        pair_index = glyph_index // 2
        off = pair_index * 4 + (2 if glyph_index & 1 else 0)
        self.desc[off] = max(0, min(W, left))
        self.desc[off + 1] = max(0, min(W, right))
        self.data[DESC_OFF + off] = self.desc[off]
        self.data[DESC_OFF + off + 1] = self.desc[off + 1]

    def save(self, path: Path) -> None:
        path.write_bytes(self.data)


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("FNT2626 描述表编辑器")
        self.root.geometry("1380x940")

        self.font_data: FontData | None = None
        self.tbl_chars: list[str] = []
        self.current_index = 0
        self.page_start = 0

        self.path_var = tk.StringVar()
        self.tbl_var = tk.StringVar()
        self.index_var = tk.StringVar(value="0")
        self.char_var = tk.StringVar(value="字符: ")
        self.desc_var = tk.StringVar(value="范围: left=0 right=0 width=0")
        self.page_var = tk.StringVar(value="页: 0 / 0")
        self.status_var = tk.StringVar(value="先打开 FOP 文件")
        self.left_var = tk.IntVar(value=0)
        self.right_var = tk.IntVar(value=0)

        self._building = False
        self._build_ui()

    def _build_ui(self) -> None:
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill="x")

        ttk.Button(top, text="打开 FOP", command=self.open_fop).pack(side="left")
        ttk.Entry(top, textvariable=self.path_var, width=54).pack(side="left", padx=6)
        ttk.Button(top, text="载入码表", command=self.open_tbl).pack(side="left")
        ttk.Entry(top, textvariable=self.tbl_var, width=34).pack(side="left", padx=6)
        ttk.Button(top, text="保存", command=self.save_fop).pack(side="left")
        ttk.Button(top, text="另存为", command=self.save_as_fop).pack(side="left", padx=(6, 0))

        nav = ttk.Frame(self.root, padding=(8, 0, 8, 8))
        nav.pack(fill="x")
        ttk.Button(nav, text="上一页", command=lambda: self.change_page(-1)).pack(side="left")
        ttk.Button(nav, text="下一页", command=lambda: self.change_page(1)).pack(side="left", padx=(6, 12))
        ttk.Label(nav, textvariable=self.page_var, width=18).pack(side="left")
        ttk.Button(nav, text="上一个字", command=lambda: self.change_index(-1)).pack(side="left", padx=(12, 0))
        ttk.Button(nav, text="下一个字", command=lambda: self.change_index(1)).pack(side="left", padx=6)
        ttk.Label(nav, text="索引").pack(side="left", padx=(12, 4))
        idx_entry = ttk.Entry(nav, textvariable=self.index_var, width=8)
        idx_entry.pack(side="left")
        idx_entry.bind("<Return>", self.jump_index)
        ttk.Label(nav, textvariable=self.char_var, width=24).pack(side="left", padx=12)
        ttk.Label(nav, textvariable=self.desc_var, width=34).pack(side="left")

        body = ttk.Frame(self.root, padding=8)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=0)
        body.rowconfigure(0, weight=1)

        left = ttk.Frame(body)
        left.grid(row=0, column=0, sticky="nsew")
        right = ttk.Frame(body)
        right.grid(row=0, column=1, sticky="ns", padx=(10, 0))

        self.grid_canvas = tk.Canvas(
            left,
            width=GRID_COLS * GRID_CELL,
            height=GRID_ROWS * GRID_CELL,
            bg="#f4f1e8",
            highlightthickness=1,
            highlightbackground="#b8b1a3",
        )
        self.grid_canvas.pack(anchor="nw")
        self.grid_canvas.bind("<Button-1>", self.on_grid_click)

        self.zoom_canvas = tk.Canvas(
            right,
            width=W * ZOOM + 1,
            height=H * ZOOM + 1,
            bg="#f7f4ea",
            highlightthickness=1,
            highlightbackground="#b8b1a3",
        )
        self.zoom_canvas.pack()

        ttk.Label(right, text="左右范围", font=("", 11, "bold")).pack(anchor="w", pady=(10, 2))
        self.left_scale = ttk.Scale(right, from_=0, to=W, orient="horizontal", command=self.on_left_scale)
        self.left_scale.pack(fill="x")
        self.right_scale = ttk.Scale(right, from_=0, to=W, orient="horizontal", command=self.on_right_scale)
        self.right_scale.pack(fill="x", pady=(6, 0))

        form = ttk.Frame(right)
        form.pack(fill="x", pady=8)
        ttk.Label(form, text="Left").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(form, from_=0, to=W, textvariable=self.left_var, width=6, command=self.apply_spin).grid(row=0, column=1, padx=6)
        ttk.Label(form, text="Right").grid(row=1, column=0, sticky="w")
        ttk.Spinbox(form, from_=0, to=W, textvariable=self.right_var, width=6, command=self.apply_spin).grid(row=1, column=1, padx=6, pady=(6, 0))
        ttk.Button(form, text="应用", command=self.apply_spin).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        tip = (
            "说明：\n"
            "1. 蓝线是 left，红线是 right。\n"
            "2. 阴影框表示实际排版宽度范围。\n"
            "3. 圆点是可视化手柄，只用于帮助观察。\n"
            "4. 逗号、句号太挤时，通常把 right 往右调，\n"
            "   或者把 left 往左调一点。"
        )
        ttk.Label(right, text=tip, justify="left").pack(anchor="w", pady=(12, 0))

        status = ttk.Label(self.root, textvariable=self.status_var, anchor="w", padding=(8, 4))
        status.pack(fill="x")

    def open_fop(self) -> None:
        filename = filedialog.askopenfilename(
            title="打开 FNT2626.FOP",
            filetypes=[("FOP 字库", "*.FOP"), ("所有文件", "*.*")],
        )
        if not filename:
            return
        try:
            self.font_data = FontData(Path(filename))
        except Exception as exc:
            messagebox.showerror("打开失败", str(exc))
            return
        self.path_var.set(filename)
        self.current_index = 0
        self.page_start = 0
        self.status_var.set("已载入 FOP，可以开始修改描述表")
        self.refresh_all()

    def open_tbl(self) -> None:
        filename = filedialog.askopenfilename(
            title="打开码表",
            filetypes=[("码表", "*.tbl"), ("文本", "*.txt"), ("所有文件", "*.*")],
        )
        if not filename:
            return
        try:
            self.tbl_chars = read_tbl_chars(Path(filename))
        except Exception as exc:
            messagebox.showerror("载入失败", str(exc))
            return
        self.tbl_var.set(filename)
        self.status_var.set(f"已载入码表，共 {len(self.tbl_chars)} 个字符")
        self.refresh_all()

    def save_fop(self) -> None:
        if self.font_data is None:
            return
        self.font_data.save(self.font_data.path)
        self.status_var.set("已保存到原文件")

    def save_as_fop(self) -> None:
        if self.font_data is None:
            return
        filename = filedialog.asksaveasfilename(
            title="另存为",
            defaultextension=".FOP",
            filetypes=[("FOP 字库", "*.FOP"), ("所有文件", "*.*")],
        )
        if not filename:
            return
        self.font_data.save(Path(filename))
        self.status_var.set(f"已另存为 {filename}")

    def change_page(self, delta: int) -> None:
        max_page = (GLYPH_COUNT - 1) // (GRID_COLS * GRID_ROWS)
        current_page = self.page_start // (GRID_COLS * GRID_ROWS)
        new_page = max(0, min(max_page, current_page + delta))
        self.page_start = new_page * GRID_COLS * GRID_ROWS
        if not (self.page_start <= self.current_index < self.page_start + GRID_COLS * GRID_ROWS):
            self.current_index = self.page_start
        self.refresh_all()

    def change_index(self, delta: int) -> None:
        self.current_index = max(0, min(GLYPH_COUNT - 1, self.current_index + delta))
        self.ensure_visible()
        self.refresh_all()

    def jump_index(self, _event: tk.Event | None = None) -> None:
        try:
            index = int(self.index_var.get().strip())
        except ValueError:
            return
        self.current_index = max(0, min(GLYPH_COUNT - 1, index))
        self.ensure_visible()
        self.refresh_all()

    def ensure_visible(self) -> None:
        page_size = GRID_COLS * GRID_ROWS
        self.page_start = (self.current_index // page_size) * page_size

    def on_grid_click(self, event: tk.Event) -> None:
        col = event.x // GRID_CELL
        row = event.y // GRID_CELL
        if not (0 <= col < GRID_COLS and 0 <= row < GRID_ROWS):
            return
        index = self.page_start + row * GRID_COLS + col
        if index >= GLYPH_COUNT:
            return
        self.current_index = index
        self.refresh_all()

    def on_left_scale(self, value: str) -> None:
        if self._building:
            return
        left = int(round(float(value)))
        right = self.right_var.get()
        if left > right:
            right = left
            self.right_var.set(right)
            self.right_scale.set(right)
        self.left_var.set(left)
        self.apply_desc(left, right)

    def on_right_scale(self, value: str) -> None:
        if self._building:
            return
        right = int(round(float(value)))
        left = self.left_var.get()
        if right < left:
            left = right
            self.left_var.set(left)
            self.left_scale.set(left)
        self.right_var.set(right)
        self.apply_desc(left, right)

    def apply_spin(self) -> None:
        left = max(0, min(W, self.left_var.get()))
        right = max(left, min(W, self.right_var.get()))
        self.left_var.set(left)
        self.right_var.set(right)
        self.left_scale.set(left)
        self.right_scale.set(right)
        self.apply_desc(left, right)

    def apply_desc(self, left: int, right: int) -> None:
        if self.font_data is None:
            return
        self.font_data.set_glyph_desc(self.current_index, left, right)
        self.refresh_info()
        self.draw_grid()
        self.draw_zoom()

    def glyph_char(self, index: int) -> str:
        if index < len(self.tbl_chars):
            return self.tbl_chars[index]
        return ""

    def refresh_info(self) -> None:
        if self.font_data is None:
            self.char_var.set("字符: ")
            self.desc_var.set("范围: left=0 right=0 width=0")
            return
        left, right = self.font_data.glyph_desc(self.current_index)
        ch = self.glyph_char(self.current_index)
        shown = ch if ch else " "
        self.char_var.set(f"字符: [{self.current_index}] {shown!r}")
        self.desc_var.set(f"范围: left={left} right={right} width={max(0, right - left)}")
        self.index_var.set(str(self.current_index))
        self.page_var.set(
            f"页: {self.page_start // (GRID_COLS * GRID_ROWS) + 1} / "
            f"{math.ceil(GLYPH_COUNT / (GRID_COLS * GRID_ROWS))}"
        )
        self._building = True
        self.left_var.set(left)
        self.right_var.set(right)
        self.left_scale.set(left)
        self.right_scale.set(right)
        self._building = False

    def refresh_all(self) -> None:
        self.refresh_info()
        self.draw_grid()
        self.draw_zoom()

    def draw_grid(self) -> None:
        self.grid_canvas.delete("all")
        if self.font_data is None:
            return
        for slot in range(GRID_COLS * GRID_ROWS):
            index = self.page_start + slot
            if index >= GLYPH_COUNT:
                break
            x0 = (slot % GRID_COLS) * GRID_CELL
            y0 = (slot // GRID_COLS) * GRID_CELL
            x1 = x0 + GRID_CELL
            y1 = y0 + GRID_CELL
            selected = index == self.current_index
            self.grid_canvas.create_rectangle(
                x0,
                y0,
                x1,
                y1,
                fill="#fffdfa" if not selected else "#dbeeff",
                outline="#b9b1a2" if not selected else "#2478cc",
                width=1 if not selected else 2,
            )

            pixels = self.font_data.glyph_pixels(index)
            left, right = self.font_data.glyph_desc(index)
            scale = GRID_CELL / W
            if right > left:
                self.grid_canvas.create_rectangle(
                    x0 + left * scale,
                    y0,
                    x0 + right * scale,
                    y1,
                    fill="#f3e4a7",
                    outline="",
                )
            for py in range(H):
                for px in range(W):
                    level = pixels[py * W + px]
                    if level == 0:
                        continue
                    gx = x0 + px * scale
                    gy = y0 + py * scale
                    self.grid_canvas.create_rectangle(
                        gx,
                        gy,
                        gx + scale + 0.4,
                        gy + scale + 0.4,
                        fill=PREVIEW_FILL[level],
                        outline="",
                    )
            self.grid_canvas.create_line(x0 + left * scale, y0, x0 + left * scale, y1, fill="#2478cc", width=1)
            self.grid_canvas.create_line(x0 + right * scale, y0, x0 + right * scale, y1, fill="#d14a3b", width=1)

    def draw_zoom(self) -> None:
        self.zoom_canvas.delete("all")
        if self.font_data is None:
            return
        pixels = self.font_data.glyph_pixels(self.current_index)
        left, right = self.font_data.glyph_desc(self.current_index)
        if right > left:
            self.zoom_canvas.create_rectangle(
                left * ZOOM,
                0,
                right * ZOOM,
                H * ZOOM,
                fill="#f5e7ac",
                outline="",
            )
        for y in range(H):
            for x in range(W):
                level = pixels[y * W + x]
                self.zoom_canvas.create_rectangle(
                    x * ZOOM,
                    y * ZOOM,
                    (x + 1) * ZOOM,
                    (y + 1) * ZOOM,
                    fill=PIXEL_FILL[level],
                    outline="#ddd6c8",
                    width=1,
                )
        self.zoom_canvas.create_line(left * ZOOM, 0, left * ZOOM, H * ZOOM, fill="#2478cc", width=3)
        self.zoom_canvas.create_line(right * ZOOM, 0, right * ZOOM, H * ZOOM, fill="#d14a3b", width=3)
        self.zoom_canvas.create_oval(left * ZOOM - 6, H * ZOOM - 14, left * ZOOM + 6, H * ZOOM - 2, fill="#2478cc", outline="")
        self.zoom_canvas.create_oval(right * ZOOM - 6, H * ZOOM - 14, right * ZOOM + 6, H * ZOOM - 2, fill="#d14a3b", outline="")


def main() -> int:
    root = tk.Tk()
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
