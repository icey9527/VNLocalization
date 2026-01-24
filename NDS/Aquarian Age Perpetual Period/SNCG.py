from PIL import Image
import struct
import sys
import os
import re

class SNGCTool:
    MAGIC_SNCG = b'SNCG'
    MAGIC_SNSC = b'SNSC'
    SNCG_HEADER = 0x10
    SNSC_HEADER = 0x0C
    SNSC_MARK = '$'  # 有SNSC配合的标记
    
    def __init__(self):
        self.success = 0
        self.fail = 0
    
    def strip_number(self, filename):
        return re.sub(r'^\d+\.', '', filename)
    
    def read_sncg_header(self, data):
        colors_per_pal = struct.unpack('<H', data[0x04:0x06])[0]
        num_palettes = struct.unpack('<H', data[0x06:0x08])[0]
        w_tiles = struct.unpack('<H', data[0x08:0x0A])[0]
        h_tiles = struct.unpack('<H', data[0x0A:0x0C])[0]
        px_off = struct.unpack('<H', data[0x0C:0x0E])[0]
        bpp = 4 if colors_per_pal == 0x10 else 8
        return w_tiles, h_tiles, px_off, bpp, colors_per_pal, num_palettes
    
    def read_snsc_header(self, data):
        w_tiles = struct.unpack('<H', data[0x08:0x0A])[0]
        h_tiles = struct.unpack('<H', data[0x0A:0x0C])[0]
        return w_tiles, h_tiles, self.SNSC_HEADER
    
    def parse_palette(self, data, px_offset):
        palette = []
        num_colors = (px_offset - self.SNCG_HEADER) // 2
        for i in range(num_colors):
            c = struct.unpack('<H', data[self.SNCG_HEADER + i*2 : self.SNCG_HEADER + i*2 + 2])[0]
            r = (c & 0x1F) * 255 // 31
            g = ((c >> 5) & 0x1F) * 255 // 31
            b = ((c >> 10) & 0x1F) * 255 // 31
            palette.append((r, g, b))
        while len(palette) < 256:
            palette.append((0, 0, 0))
        return palette
    
    def decode_tiles(self, data, bpp, px_off, palette):
        pixels = data[px_off:]
        tiles = []
        tile_size = 32 if bpp == 4 else 64
        num_tiles = len(pixels) // tile_size
        
        for t in range(num_tiles):
            tile = Image.new('RGB', (8, 8))
            px = tile.load()
            
            if bpp == 8:
                for py in range(8):
                    for ppx in range(8):
                        idx = t * 64 + py * 8 + ppx
                        if idx < len(pixels):
                            px[ppx, py] = palette[pixels[idx]]
            else:
                for py in range(8):
                    for ppx in range(0, 8, 2):
                        idx = t * 32 + py * 4 + ppx // 2
                        if idx < len(pixels):
                            byte = pixels[idx]
                            px[ppx, py] = palette[byte & 0x0F]
                            px[ppx + 1, py] = palette[(byte >> 4) & 0x0F]
            tiles.append(tile)
        return tiles
    
    def decode_with_snsc(self, sncg_data, snsc_data):
        w_tiles_g, h_tiles_g, px_off, bpp, colors_per_pal, num_pals = self.read_sncg_header(sncg_data)
        palette = self.parse_palette(sncg_data, px_off)
        tiles = self.decode_tiles(sncg_data, bpp, px_off, palette)
        
        snsc_w, snsc_h, tilemap_off = self.read_snsc_header(snsc_data)
        w, h = snsc_w * 8, snsc_h * 8
        
        img = Image.new('RGB', (w, h))
        
        for ty in range(snsc_h):
            for tx in range(snsc_w):
                snsc_idx = tilemap_off + (ty * snsc_w + tx) * 2
                if snsc_idx + 2 <= len(snsc_data):
                    entry = struct.unpack('<H', snsc_data[snsc_idx:snsc_idx+2])[0]
                    tile_idx = entry & 0x3FF
                    hflip = (entry >> 10) & 1
                    vflip = (entry >> 11) & 1
                    
                    if tile_idx < len(tiles):
                        tile = tiles[tile_idx].copy()
                        if hflip:
                            tile = tile.transpose(Image.FLIP_LEFT_RIGHT)
                        if vflip:
                            tile = tile.transpose(Image.FLIP_TOP_BOTTOM)
                        img.paste(tile, (tx * 8, ty * 8))
        
        img = img.transpose(Image.ROTATE_90)
        return img
    
    def decode(self, data):
        if data[:4] != self.MAGIC_SNCG:
            raise ValueError('Invalid magic')
        
        w_tiles, h_tiles, px_off, bpp, colors_per_pal, num_pals = self.read_sncg_header(data)
        w, h = w_tiles * 8, h_tiles * 8
        palette = self.parse_palette(data, px_off)
        pixels = data[px_off:]
        
        img = Image.new('RGB', (w, h))
        px = img.load()
        
        tile_idx = 0
        for ty in range(h_tiles):
            for tx in range(w_tiles):
                if bpp == 8:
                    for py in range(8):
                        for ppx in range(8):
                            idx = tile_idx * 64 + py * 8 + ppx
                            if idx < len(pixels):
                                px[tx*8 + ppx, ty*8 + py] = palette[pixels[idx]]
                else:
                    for py in range(8):
                        for ppx in range(0, 8, 2):
                            idx = tile_idx * 32 + py * 4 + ppx // 2
                            if idx < len(pixels):
                                byte = pixels[idx]
                                px[tx*8 + ppx, ty*8 + py] = palette[byte & 0x0F]
                                px[tx*8 + ppx + 1, ty*8 + py] = palette[(byte >> 4) & 0x0F]
                tile_idx += 1
        
        img = img.transpose(Image.ROTATE_90)
        return img
    
    def encode(self, img, orig_data):
        w_tiles, h_tiles, px_off, bpp, colors_per_pal, num_pals = self.read_sncg_header(orig_data)
        w, h = w_tiles * 8, h_tiles * 8
        
        img = img.transpose(Image.ROTATE_270)
        
        if img.size != (w, h):
            raise ValueError(f'Size must be {h}x{w} (rotated), got {img.size}')
        
        num_colors = (px_off - self.SNCG_HEADER) // 2
        if num_colors > 256:
            num_colors = 256
        
        img_p = img.convert('RGB').quantize(colors=num_colors)
        pal = img_p.getpalette()
        
        new_pal = bytearray()
        for i in range(num_colors):
            r, g, b = pal[i*3] >> 3, pal[i*3+1] >> 3, pal[i*3+2] >> 3
            new_pal += struct.pack('<H', r | (g << 5) | (b << 10))
        
        img_data = list(img_p.getdata())
        new_px = bytearray()
        
        for ty in range(h_tiles):
            for tx in range(w_tiles):
                if bpp == 8:
                    for py in range(8):
                        for ppx in range(8):
                            new_px.append(img_data[(ty*8 + py) * w + tx*8 + ppx])
                else:
                    for py in range(8):
                        for ppx in range(0, 8, 2):
                            c1 = img_data[(ty*8 + py) * w + tx*8 + ppx] & 0x0F
                            c2 = img_data[(ty*8 + py) * w + tx*8 + ppx + 1] & 0x0F
                            new_px.append(c1 | (c2 << 4))
        
        return orig_data[:self.SNCG_HEADER] + new_pal + new_px
    
    def is_sncg(self, path):
        try:
            with open(path, 'rb') as f:
                return f.read(4) == self.MAGIC_SNCG
        except:
            return False
    
    def find_snsc_files(self, sncg_name, dir_files):
        sncg_stripped = self.strip_number(sncg_name)
        
        matches = []
        
        if '_ALL_SNCG' in sncg_stripped:
            prefix = sncg_stripped.replace('_ALL_SNCG', '')
            for fname, fpath in dir_files.items():
                f_stripped = self.strip_number(fname)
                if f_stripped.startswith(prefix + '_') and f_stripped.endswith('_SNSC'):
                    middle = f_stripped[len(prefix)+1:-5]
                    if middle.isdigit() or middle == 'ALL':
                        matches.append((fname, fpath))
        else:
            expected_snsc = sncg_stripped.replace('_SNCG', '_SNSC')
            for fname, fpath in dir_files.items():
                f_stripped = self.strip_number(fname)
                if f_stripped == expected_snsc:
                    matches.append((fname, fpath))
        
        return sorted(matches, key=lambda x: self.strip_number(x[0]))
    
    def decode_file(self, src, dst_dir, dir_files, rel_path=''):
        sncg_name = os.path.basename(src)
        
        try:
            with open(src, 'rb') as f:
                sncg_data = f.read()
            
            snsc_files = self.find_snsc_files(sncg_name, dir_files)
            
            if len(snsc_files) > 1:
                # 多表情: 创建文件夹
                folder_name = self.SNSC_MARK + sncg_name
                out_folder = os.path.join(dst_dir, rel_path, folder_name)
                os.makedirs(out_folder, exist_ok=True)
                
                for snsc_name_f, snsc_path in snsc_files:
                    with open(snsc_path, 'rb') as f:
                        snsc_data = f.read()
                    img = self.decode_with_snsc(sncg_data, snsc_data)
                    out_path = os.path.join(out_folder, snsc_name_f + '.png')
                    img.save(out_path)
                    self.success += 1
                
            elif len(snsc_files) == 1:
                # 单个SNSC: 加$标记
                out_dir = os.path.join(dst_dir, rel_path)
                os.makedirs(out_dir, exist_ok=True)
                
                snsc_name_f, snsc_path = snsc_files[0]
                with open(snsc_path, 'rb') as f:
                    snsc_data = f.read()
                img = self.decode_with_snsc(sncg_data, snsc_data)
                out_path = os.path.join(out_dir, self.SNSC_MARK + sncg_name + '.png')
                img.save(out_path)
                self.success += 1
                
            else:
                # 无SNSC: 无标记
                out_dir = os.path.join(dst_dir, rel_path)
                os.makedirs(out_dir, exist_ok=True)
                
                img = self.decode(sncg_data)
                out_path = os.path.join(out_dir, sncg_name + '.png')
                img.save(out_path)
                self.success += 1
                
        except Exception as e:
            print(f'[NG] {src}: {e}')
            self.fail += 1
    
    def encode_file(self, png_path, orig_dir, dst_dir, rel_path=''):
        png_name = os.path.basename(png_path)
        
        # 去掉.png后缀
        if png_name.endswith('.png'):
            name = png_name[:-4]
        else:
            name = png_name
        
        # 检查是否有$标记
        if name.startswith(self.SNSC_MARK):
            # 有SNSC配合的，去掉$标记
            orig_name = name[1:]
        else:
            orig_name = name
        
        orig_path = os.path.join(orig_dir, rel_path, orig_name)
        out_dir = os.path.join(dst_dir, rel_path)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, orig_name)
        
        if not os.path.exists(orig_path):
            print(f'[NG] {png_path}: original not found ({orig_path})')
            self.fail += 1
            return
        
        try:
            with open(orig_path, 'rb') as f:
                orig_data = f.read()
            img = Image.open(png_path)
            data = self.encode(img, orig_data)
            with open(out_path, 'wb') as f:
                f.write(data)
            self.success += 1
        except Exception as e:
            print(f'[NG] {png_path}: {e}')
            self.fail += 1
    
    def encode_folder(self, folder_path, orig_dir, dst_dir, rel_path=''):
        # 处理表情文件夹
        folder_name = os.path.basename(folder_path)
        
        # 去掉$标记获取原始SNCG名
        if folder_name.startswith(self.SNSC_MARK):
            sncg_name = folder_name[1:]
        else:
            sncg_name = folder_name
        
        orig_path = os.path.join(orig_dir, rel_path, sncg_name)
        
        if not os.path.exists(orig_path):
            print(f'[NG] {folder_path}: original not found ({orig_path})')
            self.fail += 1
            return
        
        # 只需要编码SNCG，选取第一张PNG作为来源
        # (因为多表情共享同一套tiles)
        pngs = [f for f in os.listdir(folder_path) if f.endswith('.png')]
        if not pngs:
            print(f'[NG] {folder_path}: no PNG found')
            self.fail += 1
            return
        
        png_path = os.path.join(folder_path, pngs[0])
        out_dir = os.path.join(dst_dir, rel_path)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, sncg_name)
        
        try:
            with open(orig_path, 'rb') as f:
                orig_data = f.read()
            img = Image.open(png_path)
            data = self.encode(img, orig_data)
            with open(out_path, 'wb') as f:
                f.write(data)
            self.success += 1
        except Exception as e:
            print(f'[NG] {folder_path}: {e}')
            self.fail += 1
    
    def walk_decode(self, src_dir, dst_dir):
        for root, dirs, files in os.walk(src_dir):
            rel = os.path.relpath(root, src_dir)
            if rel == '.':
                rel = ''
            
            dir_files = {}
            for f in files:
                dir_files[f] = os.path.join(root, f)
            
            for f in files:
                path = os.path.join(root, f)
                if self.is_sncg(path):
                    self.decode_file(path, dst_dir, dir_files, rel)
        
        print(f'\nDone: {self.success} ok, {self.fail} failed')
    
    def walk_encode(self, png_dir, orig_dir, dst_dir):
        for root, dirs, files in os.walk(png_dir):
            rel = os.path.relpath(root, png_dir)
            if rel == '.':
                rel = ''
            
            # 处理$开头的文件夹（多表情）
            for d in dirs:
                if d.startswith(self.SNSC_MARK):
                    folder_path = os.path.join(root, d)
                    self.encode_folder(folder_path, orig_dir, dst_dir, rel)
            
            # 处理PNG文件
            for f in files:
                if not f.endswith('.png'):
                    continue
                png_path = os.path.join(root, f)
                self.encode_file(png_path, orig_dir, dst_dir, rel)
        
        print(f'\nDone: {self.success} ok, {self.fail} failed')

def main():
    if len(sys.argv) < 2:
        print('SNCG/SNSC Tool')
        print('')
        print('Usage:')
        print('  Decode: python sncg_tool.py d <input_dir> <output_dir>')
        print('  Encode: python sncg_tool.py e <png_dir> <orig_dir> <output_dir>')
        print('')
        print('Output naming:')
        print('  $folder/  - Multiple expressions (with SNSC)')
        print('  $file.png - Single expression (with SNSC)')
        print('  file.png  - No SNSC')
        return
    
    tool = SNGCTool()
    mode = sys.argv[1].lower()
    
    if mode == 'd' and len(sys.argv) >= 4:
        src, dst = sys.argv[2], sys.argv[3]
        if os.path.isfile(src):
            os.makedirs(dst, exist_ok=True)
            directory = os.path.dirname(src) or '.'
            dir_files = {f: os.path.join(directory, f) for f in os.listdir(directory)}
            tool.decode_file(src, dst, dir_files)
        else:
            tool.walk_decode(src, dst)
    
    elif mode == 'e' and len(sys.argv) >= 5:
        tool.walk_encode(sys.argv[2], sys.argv[3], sys.argv[4])
    
    else:
        print('Invalid arguments')

if __name__ == '__main__':
    main()