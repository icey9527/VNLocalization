import struct
import sys
import tkinter as tk
from tkinter import filedialog
from pathlib import Path

from PIL import Image, ImageTk


def font_index(sjis):
    if sjis < 0x100:
        return sjis
    lead = sjis >> 8
    if 0x81 <= lead <= 0x9F:
        return sjis - 0x8140
    if 0xE0 <= lead <= 0xFC:
        return sjis - 0xC182
    return -1


def jis_sjis(jis):
    if jis < 0x100:
        return jis
    row, col = (jis >> 8) - 0x21, (jis & 255) - 0x21
    lead = row // 2 + 0x81
    if lead > 0x9F:
        lead += 0x40
    if row & 1:
        trail = col + 0x9F
    else:
        trail = col + (0x40 if col < 0x3F else 0x41)
    return lead << 8 | trail


class Viewer:
    def __init__(self, root, data):
        self.root = root
        self.data = data
        self.variant = tk.IntVar(value=0)
        self.high_left = tk.BooleanVar(value=False)
        cmap_data = (data / 'font/font_16_a.txt').read_bytes()
        self.cmap = struct.unpack('<%dH' % (len(cmap_data) // 2), cmap_data)
        self.load_ext()
        ucs = struct.unpack('<65536H', (data / 'CCC/ucs2jis.bin').read_bytes())
        self.build_maps(ucs)
        self.glyphs = [self.decode(i) for i in range(self.count)]
        self.selected = 0
        self.build()
        self.select(0)

    def load_ext(self):
        self.ext = (self.data / ('font/font_16_a%d.ext' % self.variant.get())).read_bytes()
        self.pixel_offset = struct.unpack_from('<I', self.ext, 0x0C)[0]
        self.count = (len(self.ext) - self.pixel_offset) // 128
        self.alpha = [self.ext[0x13 + i * 4] for i in range(16)]

    def build_maps(self, ucs):
        self.maps = [[] for _ in range(self.count)]
        for cp, jis in enumerate(ucs):
            sjis = jis_sjis(jis)
            index = font_index(sjis)
            if jis and 0 <= index < len(self.cmap):
                glyph = self.cmap[index]
                if glyph == 0 and sjis != 0x8356:
                    continue
                physical = glyph + 2
                if physical < self.count:
                    self.maps[physical].append((cp, jis, sjis, index))

    def decode(self, glyph):
        image = Image.new('RGB', (16, 16), '#202020')
        pixels = image.load()
        base = self.pixel_offset + (glyph >> 1) * 256 + (glyph & 1) * 8
        for y in range(16):
            for x in range(16):
                value = self.ext[base + y * 16 + (x >> 1)]
                if self.high_left.get():
                    index = value >> 4 if not (x & 1) else value & 15
                else:
                    index = value & 15 if not (x & 1) else value >> 4
                level = self.alpha[index]
                pixels[x, y] = (level, level, level)
        return image

    def build(self):
        self.root.title('Font Map Viewer')
        self.root.geometry('1050x720')
        top = tk.Frame(self.root)
        top.pack(fill='x')
        self.query = tk.Entry(top)
        self.query.pack(side='left', fill='x', expand=True, padx=4, pady=4)
        self.query.bind('<Return>', lambda _: self.search())
        tk.Button(top, text='Search', command=self.search).pack(side='left', padx=4)
        for n in range(3):
            tk.Radiobutton(top, text='A%d' % n, variable=self.variant, value=n, command=self.refresh).pack(side='left')
        tk.Radiobutton(top, text='Low left', variable=self.high_left, value=False, command=self.refresh).pack(side='left', padx=(8, 0))
        tk.Radiobutton(top, text='High left', variable=self.high_left, value=True, command=self.refresh).pack(side='left')
        tk.Button(top, text='Export PNG', command=self.export).pack(side='left', padx=4)
        body = tk.Frame(self.root)
        body.pack(fill='both', expand=True)
        self.canvas = tk.Canvas(body, bg='#202020', highlightthickness=0)
        scroll = tk.Scrollbar(body, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)
        self.canvas.pack(side='left', fill='both', expand=True)
        scroll.pack(side='left', fill='y')
        side = tk.Frame(body, width=330)
        side.pack(side='right', fill='y', padx=8)
        side.pack_propagate(False)
        self.preview = tk.Label(side, bg='#202020', width=256, height=256)
        self.preview.pack(pady=8)
        self.info = tk.Text(side, width=42, height=22, font=('Consolas', 11))
        self.info.pack(fill='both', expand=True)
        self.render_sheet()
        self.canvas.bind('<Button-1>', self.click)
        self.root.bind('<Left>', lambda _: self.select(self.selected - 1))
        self.root.bind('<Right>', lambda _: self.select(self.selected + 1))
        self.root.bind('<Up>', lambda _: self.select(self.selected - 16))
        self.root.bind('<Down>', lambda _: self.select(self.selected + 16))

    def render_sheet(self):
        columns, scale = 16, 2
        rows = (self.count + columns - 1) // columns
        sheet = Image.new('RGB', (columns * 16, rows * 16), '#202020')
        for glyph, image in enumerate(self.glyphs):
            sheet.paste(image, ((glyph % columns) * 16, (glyph // columns) * 16))
        self.sheet = sheet.resize((sheet.width * scale, sheet.height * scale), Image.Resampling.NEAREST)
        self.sheet_photo = ImageTk.PhotoImage(self.sheet)
        self.canvas.delete('all')
        self.canvas.create_image(0, 0, image=self.sheet_photo, anchor='nw')
        self.canvas.configure(scrollregion=(0, 0, self.sheet.width, self.sheet.height))

    def refresh(self):
        self.load_ext()
        self.glyphs = [self.decode(i) for i in range(self.count)]
        self.render_sheet()
        self.select(min(self.selected, self.count - 1))

    def export(self):
        path = filedialog.asksaveasfilename(defaultextension='.png', filetypes=[('PNG', '*.png')])
        if path:
            self.sheet.save(path)

    def click(self, event):
        x = int(self.canvas.canvasx(event.x)) // 32
        y = int(self.canvas.canvasy(event.y)) // 32
        self.select(y * 16 + x)

    def select(self, glyph):
        if not 0 <= glyph < self.count:
            return
        self.selected = glyph
        x, y = glyph % 16 * 32, glyph // 16 * 32
        if hasattr(self, 'box'):
            self.canvas.delete(self.box)
        self.box = self.canvas.create_rectangle(x, y, x + 31, y + 31, outline='#00E5FF', width=2)
        self.canvas.yview_moveto(max(0, (y - 180) / max(1, int(self.canvas.cget('scrollregion').split()[3]))))
        image = self.glyphs[glyph].resize((256, 256), Image.Resampling.NEAREST)
        self.preview_photo = ImageTk.PhotoImage(image)
        self.preview.configure(image=self.preview_photo)
        order = 'high nibble left' if self.high_left.get() else 'low nibble left'
        logical = glyph - 2 if glyph >= 2 else None
        lines = ['physical tile: %d (0x%04X)' % (glyph, glyph), 'font value: %s' % (logical if logical is not None else 'padding'), 'variant: A%d' % self.variant.get(), 'pixels: %s' % order, 'offset: 0x%X' % (self.pixel_offset + (glyph >> 1) * 256 + (glyph & 1) * 8), '']
        if self.maps[glyph]:
            shown = self.maps[glyph][:64]
            for cp, jis, sjis, index in shown:
                char = chr(cp) if cp >= 0x20 and not 0x7F <= cp < 0xA0 else ''
                lines.append('%s  U+%04X' % (char, cp))
                lines.append('JIS %04X  SJIS %04X' % (jis, sjis))
                lines.append('font index %d (0x%04X)' % (index, index))
                lines.append('')
            if len(self.maps[glyph]) > len(shown):
                lines.append('%d more aliases' % (len(self.maps[glyph]) - len(shown)))
        else:
            lines.append('No Unicode mapping')
        self.info.delete('1.0', 'end')
        self.info.insert('1.0', '\n'.join(lines))

    def search(self):
        value = self.query.get()
        if not value:
            return
        if len(value) == 1 and not value.isdigit():
            cp = ord(value)
            hit = next((g for g, rows in enumerate(self.maps) if any(row[0] == cp for row in rows)), None)
        else:
            try:
                number = int(value.removeprefix('0x'), 16)
            except ValueError:
                return
            hit = number if number < self.count else None
            if hit is None:
                hit = next((g for g, rows in enumerate(self.maps) if any(number in row[1:4] for row in rows)), None)
        if hit is not None:
            self.select(hit)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('python font_viewer.py DATA1')
    app = tk.Tk()
    Viewer(app, Path(sys.argv[1]))
    app.mainloop()
