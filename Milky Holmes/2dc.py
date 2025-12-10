import struct
import tkinter as tk
from tkinter import ttk, filedialog, Menu
from dataclasses import dataclass, field
from typing import List, Optional
from PIL import Image, ImageTk
import tempfile
import subprocess
import os


@dataclass
class TextureInfo:
    x: int
    y: int
    width: int
    height: int
    gim_data: bytes
    image: Optional[Image.Image] = None


@dataclass
class PlanInfo:
    name: str
    x: int
    y: int
    width: int
    height: int
    textures: List[TextureInfo] = field(default_factory=list)


@dataclass
class ExpressionInfo:
    name: str
    frames: List[PlanInfo] = field(default_factory=list)


@dataclass
class Character2D:
    base_plans: List[PlanInfo] = field(default_factory=list)
    expressions: List[ExpressionInfo] = field(default_factory=list)


class GimDecoder:
    @staticmethod
    def _u16(data, off, le):
        if off + 2 > len(data):
            return 0
        return struct.unpack('<H' if le else '>H', data[off:off+2])[0]

    @staticmethod
    def _u32(data, off, le):
        if off + 4 > len(data):
            return 0
        return struct.unpack('<I' if le else '>I', data[off:off+4])[0]

    @staticmethod
    def _unswizzle(src, width, height, bpp):
        if not src:
            return b''
        dst_size = (width * height * bpp + 7) // 8
        block_w, block_h = 16, 8
        rows = (width + block_w - 1) // block_w
        cols = (height + block_h - 1) // block_h

        if bpp >= 8:
            dst = bytearray(dst_size)
            bpp_bytes = bpp // 8
            si = 0
            for by in range(cols):
                for bx in range(rows):
                    for r in range(block_h):
                        for c in range(block_w):
                            x = bx * block_w + c
                            y = by * block_h + r
                            if x < width and y < height:
                                di = (y * width + x) * bpp_bytes
                                if si + bpp_bytes <= len(src) and di + bpp_bytes <= len(dst):
                                    dst[di:di+bpp_bytes] = src[si:si+bpp_bytes]
                            si += bpp_bytes
            return bytes(dst)
        elif bpp == 4:
            byte_w = (width + 1) // 2
            dst = bytearray(byte_w * height)
            byte_rows = (byte_w + 15) // 16
            si = 0
            for by in range(cols):
                for bx in range(byte_rows):
                    for r in range(8):
                        for c in range(16):
                            bx_pos = bx * 16 + c
                            y = by * 8 + r
                            if bx_pos < byte_w and y < height:
                                di = y * byte_w + bx_pos
                                if si < len(src) and di < len(dst):
                                    dst[di] = src[si]
                            si += 1
            return bytes(dst)
        return src

    @staticmethod
    def _build_palette_bgra(pal_rgba, color_count):
        out = bytearray(color_count * 4)
        for i in range(color_count):
            idx = i * 4
            if idx + 4 > len(pal_rgba):
                break
            r, g, b, a = pal_rgba[idx:idx+4]
            if a <= 128:
                a = min(255, a * 2)
            o = i * 4
            out[o] = b
            out[o+1] = g
            out[o+2] = r
            out[o+3] = a
        return bytes(out)

    @staticmethod
    def _row_rgba32(src_row, width):
        out = bytearray(width * 4)
        for x in range(width):
            o = x * 4
            if o + 4 > len(src_row):
                break
            r, g, b, a = src_row[o:o+4]
            if a <= 128:
                a = min(255, a * 2)
            out[o] = b
            out[o+1] = g
            out[o+2] = r
            out[o+3] = a
        return bytes(out)

    @staticmethod
    def _row_rgb565(src_row, width):
        out = bytearray(width * 4)
        for x in range(width):
            o = x * 2
            if o + 2 > len(src_row):
                break
            v = src_row[o] | (src_row[o+1] << 8)
            r = ((v >> 11) & 0x1F) * 255 // 31
            g = ((v >> 5) & 0x3F) * 255 // 63
            b = (v & 0x1F) * 255 // 31
            d = x * 4
            out[d] = b
            out[d+1] = g
            out[d+2] = r
            out[d+3] = 255
        return bytes(out)

    @staticmethod
    def _row_rgba5551(src_row, width):
        out = bytearray(width * 4)
        for x in range(width):
            o = x * 2
            if o + 2 > len(src_row):
                break
            v = src_row[o] | (src_row[o+1] << 8)
            r = ((v >> 11) & 0x1F) * 255 // 31
            g = ((v >> 6) & 0x1F) * 255 // 31
            b = ((v >> 1) & 0x1F) * 255 // 31
            a = 255 if (v & 1) else 0
            d = x * 4
            out[d] = b
            out[d+1] = g
            out[d+2] = r
            out[d+3] = a
        return bytes(out)

    @staticmethod
    def _row_rgba4444(src_row, width):
        out = bytearray(width * 4)
        for x in range(width):
            o = x * 2
            if o + 2 > len(src_row):
                break
            v = src_row[o] | (src_row[o+1] << 8)
            r = ((v >> 12) & 0xF) * 17
            g = ((v >> 8) & 0xF) * 17
            b = ((v >> 4) & 0xF) * 17
            a = (v & 0xF) * 17
            d = x * 4
            out[d] = b
            out[d+1] = g
            out[d+2] = r
            out[d+3] = a
        return bytes(out)

    @staticmethod
    def _row_indexed4(src_row, width, pal):
        out = bytearray(width * 4)
        for x in range(width):
            bi = x // 2
            if bi >= len(src_row):
                break
            b = src_row[bi]
            idx = (b & 0x0F) if (x % 2 == 0) else ((b >> 4) & 0x0F)
            po = idx * 4
            if po + 4 > len(pal):
                continue
            d = x * 4
            out[d:d+4] = pal[po:po+4]
        return bytes(out)

    @staticmethod
    def _row_indexed8(src_row, width, pal):
        out = bytearray(width * 4)
        for x in range(width):
            if x >= len(src_row):
                break
            idx = src_row[x]
            po = idx * 4
            if po + 4 > len(pal):
                continue
            d = x * 4
            out[d:d+4] = pal[po:po+4]
        return bytes(out)

    @classmethod
    def decode(cls, data, *_):
        if not data or len(data) < 0x20:
            return None

        if data[:3] == b'GIM':
            le = False
        elif data[:3] == b'MIG':
            le = True
        else:
            return None

        img_info = -1
        pal_info = -1
        pal_block_end = -1
        off = 0x10
        loops = 0

        while off + 0x10 <= len(data) and loops < 64:
            bid = cls._u16(data, off, le)
            if bid == 0xFF:
                break
            size = cls._u32(data, off + 4, le)
            nxt = cls._u32(data, off + 8, le)
            hdr = cls._u32(data, off + 0xC, le)
            if size < hdr or hdr == 0 or nxt == 0:
                return None
            block_start = off
            block_end = block_start + size
            sub = block_start + hdr
            if block_end > len(data) or sub > block_end:
                return None

            if bid == 4 and img_info < 0:
                img_info = sub
            elif bid == 5 and pal_info < 0:
                pal_info = sub
                pal_block_end = block_end

            off = block_start + nxt
            loops += 1

        if img_info < 0:
            return None

        fmt = cls._u16(data, img_info + 4, le)
        order = cls._u16(data, img_info + 6, le)
        w = cls._u16(data, img_info + 8, le)
        h = cls._u16(data, img_info + 0xA, le)
        bpp = cls._u16(data, img_info + 0xC, le)
        img_rel = cls._u32(data, img_info + 0x1C, le)

        if w <= 0 or h <= 0 or w > 16384 or h > 16384:
            return None
        if bpp not in (4, 8, 16, 32):
            return None

        img_off = img_info + img_rel
        if img_off < 0 or img_off >= len(data):
            return None

        pixel_bytes = (w * h * bpp + 7) // 8
        max_avail = len(data) - img_off
        if max_avail < pixel_bytes:
            return None

        buf_size = max_avail
        if pal_info > 0 and img_off < pal_info:
            buf_size = min(buf_size, pal_info - img_off)

        image_bytes = bytearray(data[img_off:img_off+buf_size])

        if order == 1:
            image_bytes = bytearray(cls._unswizzle(bytes(image_bytes), w, h, bpp))

        palette = None
        if fmt in (0x04, 0x05):
            if pal_info < 0 or pal_block_end <= 0:
                return None
            pal_rel = cls._u32(data, pal_info + 0x1C, le)
            pal_off = pal_info + pal_rel
            if pal_off < 0 or pal_off >= len(data) or pal_off >= pal_block_end:
                return None
            pal_bytes = pal_block_end - pal_off
            if pal_bytes <= 0:
                return None
            colors = pal_bytes // 4
            if fmt == 0x04:
                colors = min(colors, 16)
            else:
                colors = min(colors, 256)
            if colors <= 0:
                return None
            pal_rgba = data[pal_off:pal_off+colors*4]
            palette = cls._build_palette_bgra(pal_rgba, colors)

        row_size = (w * bpp + 7) // 8
        pixels = bytearray(w * h * 4)
        si = 0

        for y in range(h):
            if si + row_size > len(image_bytes):
                break
            row = image_bytes[si:si+row_size]
            si += row_size

            if fmt == 0x00:
                dst = cls._row_rgb565(row, w)
            elif fmt == 0x01:
                dst = cls._row_rgba5551(row, w)
            elif fmt == 0x02:
                dst = cls._row_rgba4444(row, w)
            elif fmt == 0x03:
                dst = cls._row_rgba32(row, w)
            elif fmt == 0x04:
                if not palette:
                    return None
                dst = cls._row_indexed4(row, w, palette)
            elif fmt == 0x05:
                if not palette:
                    return None
                dst = cls._row_indexed8(row, w, palette)
            else:
                return None

            di = y * w * 4
            pixels[di:di+w*4] = dst

        try:
            return Image.frombytes('RGBA', (w, h), bytes(pixels), 'raw', 'BGRA')
        except Exception:
            return None


class FileScanner:
    @staticmethod
    def _be32(data, off):
        if off + 4 > len(data):
            return 0
        return struct.unpack('>I', data[off:off+4])[0]

    @staticmethod
    def _signed(v):
        return v - 0x100000000 if v > 0x7FFFFFFF else v

    @staticmethod
    def _str(data, off, max_len=32):
        end = off
        while end < min(len(data), off + max_len) and data[end]:
            end += 1
        return data[off:end].decode('ascii', errors='ignore')

    @classmethod
    def scan(cls, path):
        try:
            with open(path, 'rb') as f:
                data = f.read()
        except:
            return Character2D()

        result = Character2D()
        expr = None
        plan = None
        in_expr = False
        cur = 0

        while cur < len(data) - 8:
            sig = data[cur:cur+8]

            if sig == b'CH2DEXPR':
                expr = ExpressionInfo(cls._str(data, cur + 0x10))
                result.expressions.append(expr)
                in_expr = True
                plan = None
                cur += 16

            elif sig == b'CH2DPLAN':
                x = cls._signed(cls._be32(data, cur + 0x30))
                y = cls._signed(cls._be32(data, cur + 0x34))
                w = cls._be32(data, cur + 0x38)
                h = cls._be32(data, cur + 0x3C)
                if abs(x) > 4000:
                    x = 0
                if abs(y) > 4000:
                    y = 0
                if w <= 0 or h <= 0 or w > 4000 or h > 4000:
                    w, h = 960, 544
                name = cls._str(data, cur + 0x10)
                plan = PlanInfo(name, x, y, w, h)
                (expr.frames if in_expr and expr else result.base_plans).append(plan)
                cur += 16

            elif sig == b'CH2DTEXI':
                chunk = cls._be32(data, cur + 0x08)
                gim_offset = cls._be32(data, cur + 0x0C)
                gim_sz = cls._be32(data, cur + 0x10)
                tx = cls._signed(cls._be32(data, cur + 0x20))
                ty = cls._signed(cls._be32(data, cur + 0x24))
                tw = cls._be32(data, cur + 0x28)
                th = cls._be32(data, cur + 0x2C)
                gim_start = cur + gim_offset
                gim_end = gim_start + gim_sz
                if plan and gim_end <= len(data):
                    plan.textures.append(TextureInfo(tx, ty, tw, th, data[gim_start:gim_end]))
                cur += max((chunk + 15) & ~15, 16)

            else:
                cur += 4

        return result


class ViewerApp:
    CANVAS_DEFAULT_W = 960
    CANVAS_DEFAULT_H = 544
    FRAME_MS = 150
    CROP_MARGIN = 6

    def __init__(self, root):
        self.root = root
        self.root.title("2DC Viewer")
        self.root.geometry("1200x680")
        self.root.configure(bg='#1e1e2e')

        self.char: Optional[Character2D] = None
        self.base_image: Optional[Image.Image] = None
        self.current_image: Optional[Image.Image] = None
        self.filename = ""
        self.selected_expr = -1
        self.selected_frame = -1
        self.playing = False
        self.play_idx = 0
        self.anim_job = None
        self._tk_images: List[ImageTk.PhotoImage] = []
        self.base_w = self.CANVAS_DEFAULT_W
        self.base_h = self.CANVAS_DEFAULT_H

        self._build_ui()

    def _build_ui(self):
        left = tk.Frame(self.root, bg='#181825', width=230)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=8, pady=8)
        left.pack_propagate(False)

        tk.Label(left, text="2DC Viewer", font=('Consolas', 13, 'bold'),
                 bg='#181825', fg='#f38ba8').pack(pady=(12, 15))

        tk.Button(left, text="打开文件", font=('Consolas', 10), bg='#f38ba8',
                  fg='#1e1e2e', relief='flat', command=self._open).pack(fill=tk.X, padx=12, pady=(0, 12))

        tk.Label(left, text="结构", font=('Consolas', 10, 'bold'),
                 bg='#181825', fg='#cdd6f4').pack(anchor='w', padx=12)

        tree_f = tk.Frame(left, bg='#313244')
        tree_f.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Treeview', background='#313244', foreground='#cdd6f4',
                       fieldbackground='#313244', font=('Consolas', 10), rowheight=20)
        style.map('Treeview', background=[('selected', '#f38ba8')])

        self.tree = ttk.Treeview(tree_f, show='tree')
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind('<<TreeviewSelect>>', self._on_select)

        self.info = tk.Label(left, text="就绪", font=('Consolas', 9),
                             bg='#181825', fg='#6c7086', wraplength=210, justify='left')
        self.info.pack(fill=tk.X, padx=12, pady=8)

        right = tk.Frame(self.root, bg='#1e1e2e')
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=8, pady=8)

        cf = tk.Frame(right, bg='#313244')
        cf.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(cf, bg='#11111b', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        self.canvas.bind('<Button-3>', self._show_menu)
        self.canvas.bind('<Configure>', lambda e: self._render())

        self.menu = Menu(self.root, tearoff=0)
        self.menu.add_command(label="复制图片到剪贴板", command=self._copy_to_clipboard)
        self.menu.add_command(label="复制 GIF 到剪贴板", command=self._copy_gif_to_clipboard)

        btns = tk.Frame(right, bg='#1e1e2e')
        btns.pack(fill=tk.X, pady=(8, 0))

        self.btn_play = tk.Button(btns, text="▶ 播放", font=('Consolas', 10),
                                  bg='#45475a', fg='#cdd6f4', relief='flat', width=8,
                                  command=self._toggle_play)
        self.btn_play.pack(side=tk.LEFT, padx=(0, 6))

        tk.Button(btns, text="💾 保存", font=('Consolas', 10), bg='#45475a',
                  fg='#cdd6f4', relief='flat', width=8,
                  command=self._save).pack(side=tk.LEFT, padx=(0, 6))

        tk.Button(btns, text="🎬 GIF", font=('Consolas', 10), bg='#45475a',
                  fg='#cdd6f4', relief='flat', width=8,
                  command=self._save_gif).pack(side=tk.LEFT)

        self.frame_label = tk.Label(btns, text="", font=('Consolas', 10),
                                    bg='#1e1e2e', fg='#6c7086')
        self.frame_label.pack(side=tk.RIGHT)

    def _open(self):
        path = filedialog.askopenfilename(filetypes=[("2DC", "*.2dc"), ("All", "*.*")])
        if not path:
            return

        self._stop()
        self.char = FileScanner.scan(path)

        all_plans: List[PlanInfo] = []
        all_plans.extend(self.char.base_plans)
        for e in self.char.expressions:
            all_plans.extend(e.frames)
        if all_plans:
            max_w = max(p.x + p.width for p in all_plans)
            max_h = max(p.y + p.height for p in all_plans)
            self.base_w = max(1, max_w)
            self.base_h = max(1, max_h)
        else:
            self.base_w, self.base_h = self.CANVAS_DEFAULT_W, self.CANVAS_DEFAULT_H

        for p in self.char.base_plans:
            for t in p.textures:
                t.image = GimDecoder.decode(t.gim_data)
        for e in self.char.expressions:
            for f in e.frames:
                for t in f.textures:
                    t.image = GimDecoder.decode(t.gim_data)

        self.base_image = self._compose_plans(self.char.base_plans)
        self.filename = os.path.splitext(os.path.basename(path))[0]
        self.selected_expr = -1
        self.selected_frame = -1

        self._build_tree()
        self._render()
        self.info.config(text=f"{self.filename}\n基础层: {len(self.char.base_plans)}\n动作: {len(self.char.expressions)}")

    def _build_tree(self):
        self.tree.delete(*self.tree.get_children())
        if not self.char:
            return

        base = self.tree.insert('', 'end', text='[基础图]', values=('base',))
        for i, p in enumerate(self.char.base_plans):
            self.tree.insert(base, 'end', text=p.name or f'Base {i}', values=('bp', i))

        for i, e in enumerate(self.char.expressions):
            eid = self.tree.insert('', 'end', text=f'{e.name} ({len(e.frames)}帧)', values=('expr', i))
            for j, f in enumerate(e.frames):
                self.tree.insert(eid, 'end', text=f'[{f.name}]', values=('frm', i, j))

        self.tree.item(base, open=True)

    def _on_select(self, _):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0])['values']
        if not vals:
            return

        self._stop()
        tag = vals[0]

        if tag in ('base', 'bp'):
            self.selected_expr = -1
            self.selected_frame = -1
        elif tag == 'expr':
            idx = int(vals[1])
            self.selected_expr = idx
            self.selected_frame = 0 if self.char.expressions[idx].frames else -1
        elif tag == 'frm':
            self.selected_expr = int(vals[1])
            self.selected_frame = int(vals[2])

        self._render()

    def _toggle_play(self):
        if self.playing:
            self._stop()
        else:
            self._play()

    def _play(self):
        if not self.char or self.selected_expr < 0:
            return
        expr = self.char.expressions[self.selected_expr]
        if not expr.frames:
            return
        self.playing = True
        self.play_idx = 0
        self.btn_play.config(text="⏹ 停止", bg='#a6e3a1')
        self._tick()

    def _stop(self):
        self.playing = False
        self.btn_play.config(text="▶ 播放", bg='#45475a')
        if self.anim_job:
            self.root.after_cancel(self.anim_job)
            self.anim_job = None

    def _tick(self):
        if not self.playing or not self.char or self.selected_expr < 0:
            return
        expr = self.char.expressions[self.selected_expr]
        if not expr.frames:
            return

        self.selected_frame = self.play_idx
        self._render()
        self.play_idx = (self.play_idx + 1) % len(expr.frames)
        self.anim_job = self.root.after(self.FRAME_MS, self._tick)

    def _compose_plans(self, plans: List[PlanInfo]) -> Image.Image:
        img = Image.new("RGBA", (self.base_w, self.base_h), (0, 0, 0, 0))
        for p in plans:
            layer = Image.new("RGBA", (p.width, p.height), (0, 0, 0, 0))
            for t in p.textures:
                if t.image:
                    layer.paste(t.image, (t.x, t.y), t.image)
            img.paste(layer, (p.x, p.y), layer)
        return img

    def _crop_to_content(self, img: Image.Image) -> Image.Image:
        if img is None:
            return img
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        alpha = img.split()[3]
        bbox = alpha.getbbox()
        if not bbox:
            return img
        x0, y0, x1, y1 = bbox
        x0 = max(0, x0 - self.CROP_MARGIN)
        y0 = max(0, y0 - self.CROP_MARGIN)
        x1 = min(img.width, x1 + self.CROP_MARGIN)
        y1 = min(img.height, y1 + self.CROP_MARGIN)
        return img.crop((x0, y0, x1, y1))

    def _compose_frame(self, expr_idx: Optional[int], frame_idx: Optional[int]) -> Optional[Image.Image]:
        if not self.base_image:
            return None
        img = self.base_image.copy()
        if expr_idx is not None and frame_idx is not None and expr_idx >= 0:
            expr = self.char.expressions[expr_idx]
            if 0 <= frame_idx < len(expr.frames):
                overlay = self._compose_plans([expr.frames[frame_idx]])
                img.paste(overlay, (0, 0), overlay)
        return self._crop_to_content(img)

    def _compose_current(self) -> Optional[Image.Image]:
        if not self.base_image:
            return None
        expr_idx = self.selected_expr if self.selected_expr >= 0 else None
        frame_idx = self.selected_frame if self.selected_frame >= 0 else None
        return self._compose_frame(expr_idx, frame_idx)

    def _render(self):
        self.canvas.delete("all")
        self._tk_images.clear()

        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 10 or ch < 10:
            return

        if not self.base_image:
            self.canvas.create_text(cw//2, ch//2, text="请加载文件",
                                    fill='#666', font=('Consolas', 12))
            self.frame_label.config(text="")
            return

        self.current_image = self._compose_current()
        if not self.current_image:
            return

        w, h = self.current_image.size
        px = (cw - w) // 2
        py = (ch - h) // 2

        self.canvas.create_rectangle(px-1, py-1, px+w+1, py+h+1,
                                     outline='#585b70', width=2)

        tk_img = ImageTk.PhotoImage(self.current_image)
        self._tk_images.append(tk_img)
        self.canvas.create_image(px, py, anchor='nw', image=tk_img)

        if self.selected_expr >= 0:
            expr = self.char.expressions[self.selected_expr]
            f = self.selected_frame + 1 if self.selected_frame >= 0 else 0
            self.frame_label.config(text=f"{expr.name} [{f}/{len(expr.frames)}]")
        else:
            self.frame_label.config(text="")

    def _show_menu(self, e):
        if self.current_image:
            self.menu.post(e.x_root, e.y_root)

    def _copy_to_clipboard(self):
        if not self.current_image:
            return
        try:
            tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            tmp_path = tmp.name
            tmp.close()
            self.current_image.save(tmp_path, 'PNG')
            if os.name == 'nt':
                ps_path = tmp_path.replace("'", "''")
                cmd = (
                    "Add-Type -AssemblyName System.Windows.Forms,System.Drawing; "
                    f"[System.Windows.Forms.Clipboard]::SetImage([System.Drawing.Image]::FromFile('{ps_path}'))"
                )
                subprocess.run(['powershell', '-NoProfile', '-Command', cmd], check=True)
            os.unlink(tmp_path)
            self.info.config(text="已复制图片到剪贴板")
        except Exception as e:
            self.info.config(text=f"复制失败: {e}")

    def _make_gif_frame(self, im: Image.Image) -> Image.Image:
        im = im.convert('RGBA')
        alpha = im.split()[3]
        mask = alpha.point(lambda a: 255 if a == 0 else 0, 'L')
        p = im.convert('P', palette=Image.ADAPTIVE, colors=255)
        p.paste(255, mask)
        p.info['transparency'] = 255
        return p

    def _generate_gif_frames(self):
        if not self.char or self.selected_expr < 0:
            return []
        expr = self.char.expressions[self.selected_expr]
        frames = []
        for i in range(len(expr.frames)):
            frame_img = self._compose_frame(self.selected_expr, i)
            if not frame_img:
                continue
            frames.append(self._make_gif_frame(frame_img))
        return frames

    def _copy_gif_to_clipboard(self):
        if not self.char or self.selected_expr < 0:
            self.info.config(text="请先选择一个动作")
            return
        expr = self.char.expressions[self.selected_expr]
        if not expr.frames:
            self.info.config(text="该动作没有帧")
            return
        try:
            frames = self._generate_gif_frames()
            if not frames:
                self.info.config(text="生成GIF失败")
                return
            tmp = tempfile.NamedTemporaryFile(suffix='.gif', delete=False)
            tmp_path = tmp.name
            tmp.close()
            frames[0].save(
                tmp_path,
                save_all=True,
                append_images=frames[1:],
                duration=self.FRAME_MS,
                loop=0,
                disposal=2,
                transparency=255
            )
            if os.name == 'nt':
                ps_path = tmp_path.replace("'", "''")
                ps = (
                    "Add-Type -AssemblyName System.Windows.Forms;"
                    "$files = New-Object System.Collections.Specialized.StringCollection;"
                    f"$files.Add('{ps_path}');"
                    "$data = New-Object System.Windows.Forms.DataObject;"
                    "$data.SetFileDropList($files);"
                    "[System.Windows.Forms.Clipboard]::SetDataObject($data, $true)"
                )
                subprocess.run(['powershell', '-NoProfile', '-Command', ps], check=True)
            self.info.config(text="已复制GIF到剪贴板")
        except Exception as e:
            self.info.config(text=f"复制GIF失败: {e}")

    def _save(self):
        if not self.current_image:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            initialfile=f"{self.filename}.png",
            filetypes=[("PNG", "*.png")])
        if path:
            self.current_image.save(path)
            self.info.config(text="已保存PNG")

    def _save_gif(self):
        if not self.char or self.selected_expr < 0:
            self.info.config(text="请先选择一个动作")
            return
        expr = self.char.expressions[self.selected_expr]
        if not expr.frames:
            self.info.config(text="该动作没有帧")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".gif",
            initialfile=f"{self.filename}_{expr.name}.gif",
            filetypes=[("GIF", "*.gif")])
        if not path:
            return

        self.info.config(text="正在生成GIF...")
        self.root.update()

        try:
            frames = self._generate_gif_frames()
            if not frames:
                self.info.config(text="生成GIF失败")
                return
            frames[0].save(
                path,
                save_all=True,
                append_images=frames[1:],
                duration=self.FRAME_MS,
                loop=0,
                disposal=2,
                transparency=255
            )
            self.info.config(text=f"已保存GIF ({len(frames)}帧)")
        except Exception as e:
            self.info.config(text=f"保存失败: {e}")


if __name__ == "__main__":
    root = tk.Tk()
    ViewerApp(root)
    root.mainloop()