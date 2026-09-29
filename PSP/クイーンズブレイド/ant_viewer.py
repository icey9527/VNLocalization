# -*- coding: utf-8 -*-
"""Queen's Blade SC — ANT UV 查看器 v6

  python ant_viewer.py            打开界面
  python ant_viewer.py --selftest 无界面自检

工作流: 启动扫描 extracted 下全部 bna(格式解析: bin子节点表→gim索引) →
        左侧 gim 列表直接点选(筛选框即时过滤) → 右上下拉选引用它的 bin →
        拖框/拖角/方向键调整采样范围 → 保存

对应关系(已验证): gim文件号 = 索引 + bin槽位; 记录字段:
  +04u1 +08v1 +0Cu2 +10v2 采样角, +14w +18h 显示宽高(负=镜像),
  +0x24旋转, +28/+2C联动值 (数字条等由代码公式切片, 不在ANT里)
"""
import os
import struct
import sys
import shutil
import zlib

STRIDE = 0x40
ANT_DATA = 0x50

# ---------------- GIM 解码 ----------------

def _r16(d, o): return struct.unpack_from('<H', d, o)[0]
def _r32(d, o): return struct.unpack_from('<I', d, o)[0]

def gim_dims(path):
    """只读头部取尺寸 (w, h)，不做像素解码"""
    try:
        with open(path, 'rb') as f:
            data = f.read(0x100)
    except OSError:
        return None
    if len(data) < 0x40 or not data.startswith(b'MIG'):
        return None
    o = 16
    while o + 16 <= len(data):
        cid = _r16(data, o)
        hs = _r32(data, o + 12)
        if cid == 4:
            io = o + hs
            if io + 14 <= len(data):
                w, h = _r16(data, io + 8), _r16(data, io + 10)
                if 0 < w <= 1024 and 0 < h <= 1024:
                    return (w, h)
            return None
        nx = _r32(data, o + 8)
        if not nx:
            break
        o += nx
    return None

def _unswizzle4(s, w, h):
    rb = (w + 1) // 2
    bw = (rb + 15) // 16
    bh = (h + 7) // 8
    out = bytearray(rb * h)
    q = 0
    for by in range(bh):
        for bx in range(bw):
            for y in range(8):
                for x in range(16):
                    xx, yy = bx * 16 + x, by * 8 + y
                    if xx < rb and yy < h:
                        out[yy * rb + xx] = s[q]
                    q += 1
    return bytes(out)

def _unswizzle(s, w, h, bpp):
    ps = bpp // 8
    bw = (w + 15) // 16
    bh = (h + 7) // 8
    out = bytearray(w * h * ps)
    q = 0
    for by in range(bh):
        for bx in range(bw):
            for y in range(8):
                for x in range(16):
                    xx, yy = bx * 16 + x, by * 8 + y
                    if xx < w and yy < h:
                        out[(yy * w + xx) * ps:(yy * w + xx) * ps + ps] = s[q:q + ps]
                    q += ps
    return bytes(out)

def decode_gim(data):
    if len(data) < 32 or not data.startswith(b'MIG'):
        return None
    io = po = ie = pe = 0
    o = 16
    while o + 16 <= len(data):
        cid = _r16(data, o)
        sz = _r32(data, o + 4)
        nx = _r32(data, o + 8)
        hs = _r32(data, o + 12)
        if cid == 255 or nx == 0 or o + sz > len(data):
            break
        if cid == 4 and not io:
            io, ie = o + hs, o + sz
        if cid == 5 and not po:
            po, pe = o + hs, o + sz
        o += nx
    if not io:
        return None
    try:
        fmt = _r16(data, io + 4)
        swz = _r16(data, io + 6)
        w = _r16(data, io + 8)
        h = _r16(data, io + 10)
        bp = _r16(data, io + 12)
        off = io + _r32(data, io + 28)
    except struct.error:
        return None
    if w <= 0 or h <= 0 or off >= len(data):
        return None
    pal = b''
    pc = 0
    if bp in (4, 8) and po:
        try:
            q = po + _r32(data, po + 28)
            pc = (pe - q) // 4
            pc = min(pc, 16 if (bp == 4) else 256)
            pal = data[q:q + pc * 4]
        except struct.error:
            pal = b''
    nbytes = (w * h * bp + 7) // 8
    rend = min(len(data), max(off + nbytes, ie if ie else off))
    raw = bytearray(data[off:rend])
    if swz:
        if bp == 4:
            rb = (w + 1) // 2
            need = ((rb + 15) // 16) * 128 * ((h + 7) // 8)
            raw.extend(b'\0' * max(0, need - len(raw)))
            raw = bytearray(_unswizzle4(bytes(raw), w, h))
        else:
            need = ((w + 15) // 16) * ((h + 7) // 8) * 128 * (bp // 8)
            raw.extend(b'\0' * max(0, need - len(raw)))
            raw = bytearray(_unswizzle(bytes(raw), w, h, bp))
    out = bytearray(w * h * 4)
    for i in range(w * h):
        if bp == 32:
            out[i*4] = raw[i*4]; out[i*4+1] = raw[i*4+1]
            out[i*4+2] = raw[i*4+2]; out[i*4+3] = raw[i*4+3]
        elif bp == 16:
            v = raw[i*2] | (raw[i*2+1] << 8)
            if fmt == 0:
                out[i*4] = (v & 31) * 255 // 31
                out[i*4+1] = ((v >> 5) & 63) * 255 // 63
                out[i*4+2] = (v >> 11 & 31) * 255 // 31
                out[i*4+3] = 255
            elif fmt == 2:
                out[i*4] = (v & 15) * 17
                out[i*4+1] = ((v >> 4) & 15) * 17
                out[i*4+2] = ((v >> 8) & 15) * 17
                out[i*4+3] = ((v >> 12) & 15) * 17
            else:
                out[i*4] = (v & 31) * 255 // 31
                out[i*4+1] = ((v >> 5) & 31) * 255 // 31
                out[i*4+2] = ((v >> 10) & 31) * 255 // 31
                out[i*4+3] = 255 if (v >> 15) else 0
        else:
            ix = -1
            if bp == 8:
                if i < len(raw):
                    ix = raw[i]
            elif bp == 4:
                if i // 2 < len(raw):
                    z = raw[i // 2]
                    ix = (z >> 4) if (i & 1) else (z & 15)
            if 0 <= ix < pc:
                out[i*4] = pal[ix*4]; out[i*4+1] = pal[ix*4+1]
                out[i*4+2] = pal[ix*4+2]; out[i*4+3] = pal[ix*4+3]
    return w, h, bytes(out)


# ---------------- 原版资源 ----------------

_STREAM_CACHE = {}   # 按文件路径缓存解压流, 避免重复解压大档案

class OriginalSource:
    def __init__(self, usrdir_bin):
        self.path = usrdir_bin
        self._bnas = None

    def _scan(self):
        if self._bnas is not None:
            return self._bnas
        if self.path in _STREAM_CACHE:
            self._bnas = _STREAM_CACHE[self.path]
            return self._bnas
        self._bnas = []
        if not os.path.exists(self.path):
            return self._bnas
        raw = open(self.path, 'rb').read()
        pos = 0
        while pos < len(raw) - 2:
            if raw[pos] == 0x78 and raw[pos+1] in (0x01, 0x9c, 0xda, 0x5e):
                d = zlib.decompressobj()
                try:
                    out = d.decompress(raw[pos:])
                except zlib.error:
                    pos += 1
                    continue
                if out[:4] == b'BNA.':
                    used = len(raw) - pos - len(d.unused_data)
                    self._bnas.append(out)
                    pos += used
                    continue
            pos += 1
        _STREAM_CACHE[self.path] = self._bnas
        return self._bnas

    def gim(self, bna_index, gim_index):
        bnas = self._scan()
        if bna_index >= len(bnas):
            return None
        bna = bnas[bna_index]
        n_gim, = struct.unpack_from('<H', bna, 6)
        if gim_index >= n_gim:
            return None
        tbl, = struct.unpack_from('<I', bna, 0x0C)
        off, = struct.unpack_from('<I', bna, tbl + gim_index * 4)
        if off == 0xFFFFFFFF:
            return None
        nxt = len(bna)
        for j in range(gim_index + 1, n_gim):
            o2, = struct.unpack_from('<I', bna, tbl + j * 4)
            if o2 != 0xFFFFFFFF:
                nxt = o2
                break
        return bna[off:nxt]


# ---------------- ANT / BNA ----------------

FIELD_OFF = {'u1': 4, 'v1': 8, 'u2': 12, 'v2': 16, 'w': 20, 'h': 24}

class AntFile:
    def __init__(self, path):
        self.path = path
        self.data = bytearray(open(path, 'rb').read())
        self.children = [c for c in self.data[:16] if c != 0xFF]
        self.dirty = False
        self.records = []
        n = max(0, (len(self.data) - ANT_DATA) // STRIDE)
        for i in range(n):
            base = ANT_DATA + i * STRIDE
            w0, = struct.unpack_from('<I', self.data, base)
            f = struct.unpack_from('<13f', self.data, base + 4)
            self.records.append({
                'idx': i, 'off': base,
                'type': w0 >> 16, 'child': w0 & 0xFFFF,
                'u1': f[0], 'v1': f[1], 'u2': f[2], 'v2': f[3],
                'w': f[4], 'h': f[5], 'rot': f[8],
                '_ow': f[4], '_oh': f[5], '_o28': f[9], '_o2c': f[10],
            })

    def fset(self, rec, key, value):
        struct.pack_into('<f', self.data, rec['off'] + FIELD_OFF[key], float(value))
        rec[key] = float(value)
        self.dirty = True

    def sync_tail(self, rec):
        n28 = rec['_o28'] + (rec['w'] - rec['_ow'])
        struct.pack_into('<f', self.data, rec['off'] + 0x28, n28)
        if abs(rec['_o2c'] - rec['_ow']) <= abs(rec['_o2c'] - rec['_oh']):
            n2c = rec['_o2c'] + (rec['w'] - rec['_ow'])
        else:
            n2c = rec['_o2c'] + (rec['h'] - rec['_oh'])
        struct.pack_into('<f', self.data, rec['off'] + 0x2C, n2c)
        self.dirty = True

    def save(self):
        open(self.path, 'wb').write(self.data)
        self.dirty = False


def uv_rect(r):
    x1, x2 = sorted((r['u1'], r['u2']))
    y1, y2 = sorted((r['v1'], r['v2']))
    return x1, y1, x2 - x1, y2 - y1


class Bna:
    def __init__(self, d, here):
        self.dir = d
        self.here = here
        self.name = os.path.basename(d)
        self.top = os.path.basename(os.path.dirname(d))
        self.ants = {}
        self.gims = {}
        for name in os.listdir(d):
            p = os.path.join(d, name)
            if not os.path.isfile(p):
                continue
            stem, ext = os.path.splitext(name)
            if not stem.isdigit():
                continue
            if ext == '.bin':
                self.ants[int(stem)] = AntFile(p)
            elif ext == '.gim':
                self.gims[int(stem)] = p
        self.n_bins = (max(self.ants) + 1) if self.ants else 0
        self.origsrc = None
        self.origidx = -1
        for cand in (os.path.join(here, 'USRDIR', self.top), os.path.join(here, self.top)):
            if os.path.exists(cand):
                sibs = sorted(f for f in os.listdir(os.path.dirname(d)) if f.endswith('.bna'))
                if self.name in sibs:
                    self.origsrc = OriginalSource(cand)
                    self.origidx = sibs.index(self.name)
                break

    def gim_no(self, gim_index):
        return gim_index + self.n_bins

    def records_for_gim(self, gim_index):
        out = []
        for num in sorted(self.ants):
            ant = self.ants[num]
            for r in ant.records:
                if (r['type'] in SPRITE_TYPES
                        and r['child'] < len(ant.children)
                        and ant.children[r['child']] == gim_index):
                    out.append((num, r))
        return out

    def _png_path(self, gim_index):
        """定位 png: png/<top>/<name>/NNNN.png (不依赖 self.dir 的格式)"""
        fno = self.gim_no(gim_index)
        fname = '%04d.png' % fno
        cands = [
            os.path.join(self.here, 'png', self.top, self.name, fname),
            os.path.join('png', self.top, self.name, fname),      # 从项目根启动
        ]
        # 兼容旧逻辑: 剥掉 extracted 段的路径
        rel = self.dir.replace('/', os.sep)
        marker = os.sep + 'extracted' + os.sep
        i = rel.find(marker)
        if i >= 0:
            cands.append(os.path.join(self.here, 'png', rel[i + len(marker):], fname))
        elif rel.startswith('extracted' + os.sep):
            cands.append(os.path.join(self.here, 'png',
                                      rel[len('extracted') + 1:], fname))
        for p in cands:
            if os.path.exists(p):
                return p
        return None

    def image_cur(self, gim_index):
        from PIL import Image
        fno = self.gim_no(gim_index)
        p = self.gims.get(fno)
        if p and os.path.exists(p):
            try:
                dec = decode_gim(open(p, 'rb').read())
                if dec:
                    return Image.frombytes('RGBA', (dec[0], dec[1]), dec[2])
            except OSError:
                pass
        png = self._png_path(gim_index)
        if png:
            return Image.open(png).convert('RGBA')
        return None

    def image_png(self, gim_index):
        from PIL import Image
        png = self._png_path(gim_index)
        if png:
            return Image.open(png).convert('RGBA')
        return None

    def image_orig(self, gim_index):
        if not self.origsrc:
            return None
        og = self.origsrc.gim(self.origidx, gim_index)
        if not og:
            return None
        dec = decode_gim(og)
        if not dec:
            return None
        from PIL import Image
        return Image.frombytes('RGBA', (dec[0], dec[1]), dec[2])


def scan_archives(root):
    here = os.path.dirname(os.path.abspath(__file__))
    bnas = []
    for top in sorted(os.listdir(root)):
        tdir = os.path.join(root, top)
        if not os.path.isdir(tdir):
            continue
        for name in sorted(os.listdir(tdir)):
            if name.endswith('.bna'):
                d = os.path.join(tdir, name)
                if os.path.isdir(d):
                    bnas.append(Bna(d, here))
    return bnas




# ---------------- 原版边缘轮廓 (对位检查) ----------------

def orig_edge_image(orig_img):
    """原版图集内容的边缘描边(红色), 叠在修改图上用于对位检查"""
    aw, ah = orig_img.size
    px = orig_img.tobytes()
    def ink(x, y):
        return 0 <= x < aw and 0 <= y < ah and px[(y*aw+x)*4+3] > 16
    ov = bytearray(aw * ah * 4)
    for y in range(ah):
        for x in range(aw):
            if ink(x, y) and not (ink(x-1, y) and ink(x+1, y)
                                  and ink(x, y-1) and ink(x, y+1)):
                i = (y*aw+x)*4
                ov[i] = 255; ov[i+1] = 40; ov[i+2] = 40; ov[i+3] = 220
    from PIL import Image
    return Image.frombytes('RGBA', (aw, ah), bytes(ov))

# ---------------- 推测框 (无引用内容的范围) ----------------

def infer_uncovered_boxes(im, rec_list):
    """图集里未被任何采样框覆盖的内容块 bbox 列表 [x0,y0,x1,y1] (已合并邻近块)"""
    from collections import deque
    aw, ah = im.size
    px = im.tobytes()
    covered = bytearray(aw * ah)
    for r in rec_list:
        x, y, w, h = uv_rect(r)
        for yy in range(max(0, int(y)), min(ah, int(y + h))):
            base = yy * aw
            for xx in range(max(0, int(x)), min(aw, int(x + w))):
                covered[base + xx] = 1
    visited = bytearray(aw * ah)
    boxes = []
    for y0 in range(ah):
        for x0 in range(aw):
            i0 = y0 * aw + x0
            if visited[i0] or covered[i0] or px[i0*4+3] <= 8:
                continue
            q = deque([(x0, y0)])
            visited[i0] = 1
            minx = maxx = x0
            miny = maxy = y0
            while q:
                x, y = q.popleft()
                if x < minx: minx = x
                if x > maxx: maxx = x
                if y < miny: miny = y
                if y > maxy: maxy = y
                for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
                    nx, ny = x+dx, y+dy
                    if 0 <= nx < aw and 0 <= ny < ah:
                        j = ny*aw+nx
                        if not visited[j] and not covered[j] and px[j*4+3] > 8:
                            visited[j] = 1
                            q.append((nx, ny))
            if maxx-minx >= 1 and maxy-miny >= 1:
                boxes.append([minx, miny, maxx, maxy])
    # 合并水平相近、垂直重叠的块(把单个字符拼成文字条)
    changed = True
    while changed:
        changed = False
        out = []
        used = [False]*len(boxes)
        for i in range(len(boxes)):
            if used[i]:
                continue
            a = boxes[i][:]
            for j in range(i+1, len(boxes)):
                if used[j]:
                    continue
                b2 = boxes[j]
                gapx = max(a[0], b2[0]) - min(a[2], b2[2])
                ovy = min(a[3], b2[3]) - max(a[1], b2[1])
                if gapx < 8 and ovy > 0:
                    a[0] = min(a[0], b2[0]); a[1] = min(a[1], b2[1])
                    a[2] = max(a[2], b2[2]); a[3] = max(a[3], b2[3])
                    used[j] = True
                    changed = True
            used[i] = True
            out.append(a)
        boxes = out
    return boxes

# ---------------- XML 默认值 (出厂坐标备份/恢复) ----------------
import xml.etree.ElementTree as ET

DEFAULTS_XML = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ant_defaults.xml')

def _orig_stream(b):
    """取该 bna 的原版解压流(无则None)"""
    if not b.origsrc:
        return None
    try:
        streams = b.origsrc._scan()
        return streams[b.origidx] if 0 <= b.origidx < len(streams) else None
    except Exception:
        return None

def _match_offsets(orig, ants):
    """在原版流里按头部0x50字节定位每个提取bin, 返回 {bin号: 偏移}"""
    out = {}
    for num, ant in ants.items():
        head = bytes(ant.data[:0x50])
        pos = orig.find(head)
        if pos != -1:
            out[num] = pos
    return out

def _min_gim_off(orig):
    tbl, = struct.unpack_from('<I', orig, 0x0C)
    n, = struct.unpack_from('<H', orig, 6)
    best = len(orig)
    for j in range(n):
        o, = struct.unpack_from('<I', orig, tbl + j * 4)
        if o != 0xFFFFFFFF:
            best = min(best, o)
    return best

def build_defaults(bnas):
    """{(top,name,bin号): {recIdx: [13个float]}}  优先取原版流, 匹配不到用当前文件"""
    data = {}
    for b in bnas:
        orig = _orig_stream(b)
        matches = _match_offsets(orig, b.ants) if orig else {}
        bounds = {}
        if matches:
            offs = sorted(set(matches.values()))
            endall = _min_gim_off(orig) if orig else len(orig)
            for i, o in enumerate(offs):
                bounds[o] = offs[i + 1] if i + 1 < len(offs) else endall
        for num, ant in b.ants.items():
            key = (b.top, b.name, num)
            recs = {}
            ob = None
            if num in matches and orig:
                o = matches[num]
                ob = orig[o:bounds[o]]
            for r in ant.records:
                if ob and len(ob) >= r['off'] + 4 + 52:
                    fl = list(struct.unpack_from('<13f', ob, r['off'] + 4))
                else:
                    fl = list(struct.unpack_from('<13f', ant.data, r['off'] + 4))
                recs[r['idx']] = fl
            data[key] = {'source': 'original' if ob else 'current', 'recs': recs}
    return data

def _bits(v):
    """float -> 32位十六进制(位精确, NaN/非规格数不丢失)"""
    return '%08x' % struct.unpack('<I', struct.pack('<f', v))[0]

def _fl_attrs(fl):
    return {('f%02x' % (4 + k * 4)): _bits(v) for k, v in enumerate(fl)}

def _parse_val(s):
    """hex位模式 或 旧版repr浮点 -> 位精确float"""
    try:
        return struct.unpack('<f', struct.pack('<I', int(s, 16)))[0]
    except ValueError:
        return float(s)

def _bits_equal(a, b):
    return struct.pack('<13f', *a) == struct.pack('<13f', *b)

def save_defaults_xml(path, defaults, mods=None):
    """defaults: {key: {'source','recs'}};  mods: {key: {idx: [13f]}} 修改值"""
    mods = mods or {}
    root = ET.Element('ant_defaults')
    for key, ent in sorted(defaults.items()):
        top, name, num = key
        bel = ET.SubElement(root, 'bin', {'top': top, 'name': name, 'id': str(num),
                                          'source': ent['source']})
        for idx, fl in sorted(ent['recs'].items()):
            rel = ET.SubElement(bel, 'r', {'i': str(idx), **_fl_attrs(fl)})
            mfl = mods.get(key, {}).get(idx)
            if mfl is not None and not _bits_equal(mfl, fl):
                ET.SubElement(rel, 'm', _fl_attrs(mfl))
    if hasattr(ET, 'indent'):
        ET.indent(root)
    ET.ElementTree(root).write(path, encoding='utf-8', xml_declaration=True)

def load_defaults_xml(path):
    """-> {key: {'orig': {idx: fl}, 'mod': {idx: fl}}}"""
    tree = ET.parse(path)
    data = {}
    for bel in tree.getroot().findall('bin'):
        key = (bel.get('top'), bel.get('name'), int(bel.get('id')))
        orig, mod = {}, {}
        for rel in bel.findall('r'):
            idx = int(rel.get('i'))
            orig[idx] = [_parse_val(rel.get('f%02x' % (4 + k * 4))) for k in range(13)]
            mel = rel.find('m')
            if mel is not None:
                mod[idx] = [_parse_val(mel.get('f%02x' % (4 + k * 4))) for k in range(13)]
        data[key] = {'orig': orig, 'mod': mod}
    return data

def xml_all_mods(path):
    """-> {key: {idx: fl}} 仅含有修改值的记录"""
    out = {}
    for key, ent in load_defaults_xml(path).items():
        if ent['mod']:
            out[key] = ent['mod']
    return out

def update_xml_mods(ant, bna_top, bna_name, bin_num):
    """把该 bin 当前全部记录值作为修改值写入 XML"""
    try:
        data = load_defaults_xml(DEFAULTS_XML)
    except Exception:
        return False
    key = (bna_top, bna_name, bin_num)
    if key not in data:
        return False
    cur = {}
    for r in ant.records:
        # 只记录精灵类型的修改; 动画曲线/终止符的原始数据是整数, 永不写XML
        if r['type'] not in SPRITE_TYPES:
            continue
        cur[r['idx']] = list(struct.unpack_from('<13f', ant.data, r['off'] + 4))
    # 位级比较(NaN 不再误判为已修改)
    mod = {i: fl for i, fl in cur.items()
           if i not in data[key]['orig'] or not _bits_equal(fl, data[key]['orig'][i])}
    data[key]['mod'] = mod
    mods = {k: v['mod'] for k, v in data.items() if v.get('mod')}
    # 重建 defaults 原始结构用于写出
    defaults = {k: {'source': 'xml', 'recs': v['orig']} for k, v in data.items()}
    save_defaults_xml(DEFAULTS_XML, defaults, mods)
    return True

def apply_all_edits(here):
    """把 XML 里记录的全部修改值批量写回对应 bin 文件(磁盘直写),
    返回 (bin数, 记录数, 失败列表)"""
    mods = xml_all_mods(DEFAULTS_XML)
    nb = nr = 0
    fails = []
    for (top, name, num), recs in sorted(mods.items()):
        p = os.path.join(here, 'extracted', top, name, '%04d.bin' % num)
        if not os.path.exists(p):
            fails.append(p)
            continue
        data = bytearray(open(p, 'rb').read())
        ok = 0
        for idx, fl in sorted(recs.items()):
            off = ANT_DATA + idx * STRIDE + 4
            if off + 52 <= len(data):
                struct.pack_into('<13f', data, off, *fl)
                ok += 1
        open(p, 'wb').write(data)
        nb += 1
        nr += ok
    return nb, nr, fails

def apply_defaults(ant, bna_top, bna_name, bin_num, defaults, use_mod=False):
    """把XML里的13个float写回记录(内存), 返回恢复条数
    use_mod=False 用出厂值, True 用修改值"""
    ent = defaults.get((bna_top, bna_name, bin_num))
    if not ent:
        return 0
    recs = ent['mod'] if use_mod else ent['orig']
    n = 0
    for r in ant.records:
        if r['type'] not in SPRITE_TYPES:
            continue   # 动画曲线/终止符永不通过XML写回(防NaN位模式破坏)
        fl = recs.get(r['idx'])
        if fl is None:
            continue
        struct.pack_into('<13f', ant.data, r['off'] + 4, *fl)
        for k, key in enumerate(('u1', 'v1', 'u2', 'v2', 'w', 'h', 'x6', 'x7', 'rot',
                                 'f28', 'f2c', 'x12', 'x13')):
            if key in r:
                r[key] = fl[k]
        r['_ow'], r['_oh'], r['_o28'], r['_o2c'] = fl[4], fl[5], fl[9], fl[10]
        n += 1
    ant.dirty = True
    return n

# ---------------- GUI ----------------

BIN_COLORS = ['#38D8F8', '#7CFC00', '#FFA0FF', '#FFD070', '#B0B0FF', '#60FFB0']
# 精灵记录类型(有UV坐标); 0x0000=动画曲线, 0xFFFF=终止符, 不画框
SPRITE_TYPES = {0x0001, 0x0002, 0x0101, 0x0102}

def run_gui():
    import tkinter as tk
    from tkinter import ttk, messagebox
    from PIL import Image, ImageTk

    root = tk.Tk()
    root.title('ANT UV 查看器 v6')

    HERE = os.path.dirname(os.path.abspath(__file__))
    state = {
        'bnas': [], 'gimkey': None,
        'curedit': None, 'sel': None,
        'img_cur': None, 'img_orig': None, 'img_png': None,
        'view': tk.StringVar(value='原版'),
        'show_all': tk.BooleanVar(value=True),
        'show_cov': tk.BooleanVar(value=False),
        'zoom': 2.0, 'panx': 8.0, 'pany': 8.0,
        'photo': None, 'cov_photo': None, 'crop_photo': None,
        'inf_boxes': [],
        'edge_ov': None, 'edge_key': None,
        'preview': None,   # {u1..h} 输入框实时预览值(未写入)
        'all_gims': [],          # [(显示项, (bna, gi))]
        'sort': ['gim', False],  # [列, 降序?]
        'bin_entries': [],
    }

    # ---- 顶栏 ----
    bar = ttk.Frame(root); bar.pack(fill='x', padx=6, pady=3)
    ttk.Label(bar, text='底图:').pack(side='left')
    for mode, txt in (('原版', '游戏原版'), ('当前', '当前gim'), ('PNG', 'PNG目录'),
                      ('对位', '对位(红边=原版)'), ('叠加', '叠加对比')):
        ttk.Radiobutton(bar, text=txt, value=mode, variable=state['view'],
                        command=lambda: view_changed()).pack(side='left', padx=4)
    ttk.Checkbutton(bar, text='显示全部bin的框', variable=state['show_all'],
                    command=lambda: refresh_overlay(rebuild_tree=True)).pack(side='left', padx=(24, 4))
    ttk.Checkbutton(bar, text='覆盖检查(红=无框内容)', variable=state['show_cov'],
                    command=lambda: cov_toggled()).pack(side='left')
    ttk.Button(bar, text='重载图片', command=lambda: reload_images()).pack(side='left', padx=(12, 4))
    ttk.Label(bar, text='  引用bin:').pack(side='left', padx=(12, 0))
    c_bin = ttk.Combobox(bar, width=26, state='readonly'); c_bin.pack(side='left', padx=4)

    bar2 = ttk.Frame(root); bar2.pack(fill='x', padx=6, pady=2)
    ttk.Button(bar2, text='保存当前bin', command=lambda: save_cur()).pack(side='left')
    ttk.Button(bar2, text='保存全部改动', command=lambda: save_all()).pack(side='left', padx=4)
    ttk.Button(bar2, text='恢复默认(XML出厂值)', command=lambda: restore_defaults()).pack(side='left')
    ttk.Button(bar2, text='应用XML全部修改', command=lambda: apply_all_btn()).pack(side='left', padx=4)
    ttk.Button(bar2, text='导出框图PNG', command=lambda: export_boxes_png()).pack(side='left')

    # ---- 主体三栏 ----
    body = ttk.Frame(root); body.pack(fill='both', expand=True)

    left = ttk.Frame(body, width=300); left.pack(side='left', fill='y')
    left.pack_propagate(False)
    ttk.Label(left, text='筛选 (编号/归档名):').pack(anchor='w', padx=4)
    e_filter = ttk.Entry(left); e_filter.pack(fill='x', padx=4)
    gl_frame = ttk.Frame(left); gl_frame.pack(fill='both', expand=True, padx=4, pady=2)
    gl_tree = ttk.Treeview(gl_frame, columns=('gim', 'dims', 'refs'), show='headings')
    gl_scroll = ttk.Scrollbar(gl_frame, orient='vertical', command=gl_tree.yview)
    gl_tree.config(yscrollcommand=gl_scroll.set)
    gl_scroll.pack(side='right', fill='y')
    gl_tree.pack(side='left', fill='both', expand=True)
    GL_TITLES = {'gim': 'gim', 'dims': '尺寸', 'refs': '引用它的bin'}
    for col in ('gim', 'dims', 'refs'):
        gl_tree.heading(col, text=GL_TITLES[col],
                        command=lambda c=col: sort_by(c))
    gl_tree.column('gim', width=128)
    gl_tree.column('dims', width=56)
    gl_tree.column('refs', width=104)

    cv = tk.Canvas(body, bg='#3a3a3a', highlightthickness=0)
    cv.pack(side='left', fill='both', expand=True)

    right = ttk.Frame(body, width=390)
    right.pack(side='left', fill='y')
    right.pack_propagate(False)
    right.pack_propagate(False)

    crop_cv = tk.Canvas(right, bg='#202020', width=365, height=150)
    crop_cv.pack(padx=6, pady=3)

    # 表单先 pack —— 保证任何窗口高度下输入框和按钮都可见
    form = ttk.Frame(right); form.pack(fill='x', padx=6, pady=2)
    entries = {}
    labels = [('sx', '取样X'), ('sy', '取样Y'), ('sw', '取样宽'), ('sh', '取样高'),
              ('w', '显示宽(负=镜像)'), ('h', '显示高(负=镜像)')]
    for i, (k, t) in enumerate(labels):
        ttk.Label(form, text=t, width=14).grid(
            row=i, column=0, sticky='w', padx=(0, 6), pady=2
        )

        e = ttk.Entry(form, width=12)
        e.grid(
            row=i, column=1, sticky='ew', padx=(0, 4), pady=2
        )
        entries[k] = e

    form.columnconfigure(1, weight=1)

    def disp_vals(r):
        x1, x2 = sorted((r['u1'], r['u2']))
        y1, y2 = sorted((r['v1'], r['v2']))
        return {'sx': x1, 'sy': y1, 'sw': x2 - x1, 'sh': y2 - y1,
                'w': r['w'], 'h': r['h']}

    def to_corners(r, dv):
        """位置+宽高 -> 四角, 保持原记录的方向/镜像"""
        if r['u1'] <= r['u2']:
            u1, u2 = dv['sx'], dv['sx'] + dv['sw']
        else:
            u2, u1 = dv['sx'], dv['sx'] + dv['sw']
        if r['v1'] <= r['v2']:
            v1, v2 = dv['sy'], dv['sy'] + dv['sh']
        else:
            v2, v1 = dv['sy'], dv['sy'] + dv['sh']
        return u1, v1, u2, v2

    def fill_entries(r):
        state['preview'] = None
        dv = disp_vals(r)
        for k in ('sx', 'sy', 'sw', 'sh', 'w', 'h'):
            entries[k].delete(0, tk.END)
            entries[k].insert(0, '%g' % dv[k])

    def rec_vals(r):
        """记录值 + 输入框实时预览(转回四角), 不写数据"""
        dv = disp_vals(r)
        if state['preview']:
            dv.update(state['preview'])
        u1, v1, u2, v2 = to_corners(r, dv)
        v = dict(r)
        v['u1'], v['v1'], v['u2'], v['v2'] = u1, v1, u2, v2
        v['w'], v['h'] = dv['w'], dv['h']
        return v

    def on_entry_input(_=None):
        r = self_rec()
        if r is None:
            return

        pv = {}
        invalid = []

        for k in ('sx', 'sy', 'sw', 'sh', 'w', 'h'):
            t = entries[k].get().strip()

            if t == '':
                continue

            try:
                pv[k] = float(t)
            except ValueError:
                invalid.append(k)

        if invalid:
            state['preview'] = pv or None
            say('预览输入无效: ' + ', '.join(invalid))
        else:
            state['preview'] = pv or None
            say('输入预览中，尚未写入 bin')

        refresh_overlay()

    def revert_input():
        r = self_rec()
        if r is None:
            return
        fill_entries(r)
        refresh_overlay()
        say('输入已还原为记录当前值')

    def sync_group(quiet=False):
        """把选中记录的采样区, 应用到同组(出厂采样区+child相同)的其他记录"""
        r = self_rec()
        ant = state['curedit']
        if r is None or ant is None or not state['gimkey']:
            if not quiet:
                say('先选中一条记录')
            return 0
        b, _gi = state['gimkey']
        num = next((n for n, a in b.ants.items() if a is ant), -1)
        try:
            ent = load_defaults_xml(DEFAULTS_XML).get((b.top, b.name, num))
        except Exception:
            ent = None
        if not ent or r['idx'] not in ent['orig']:
            if not quiet:
                say('XML里没有该bin的出厂值, 无法判定同组')
            return 0
        my_orig = ent['orig'][r['idx']]
        dv = {'sx': min(r['u1'], r['u2']), 'sw': abs(r['u2'] - r['u1']),
              'sy': min(r['v1'], r['v2']), 'sh': abs(r['v2'] - r['v1'])}
        n = 0
        for r2 in ant.records:
            if r2 is r or r2['type'] not in SPRITE_TYPES or r2['child'] != r['child']:
                continue
            o2 = ent['orig'].get(r2['idx'])
            if not o2:
                continue
            if (o2[0], o2[1], o2[2], o2[3]) != (my_orig[0], my_orig[1], my_orig[2], my_orig[3]):
                continue
            u1, v1, u2, v2 = to_corners(r2, dv)
            ant.fset(r2, 'u1', u1)
            ant.fset(r2, 'v1', v1)
            ant.fset(r2, 'u2', u2)
            ant.fset(r2, 'v2', v2)
            ant.sync_tail(r2)
            n += 1
        refresh_overlay(rebuild_tree=True)
        if not quiet:
            say('已把采样区同步到同组 %d 条记录 (记得保存)' % n)
        return n

    def apply_entries():
        r = self_rec()
        if r is None:
            return
        ant = state['curedit']
        dv = disp_vals(r)
        for k in ('sx', 'sy', 'sw', 'sh', 'w', 'h'):
            t = entries[k].get().strip()
            if t == '':
                continue
            try:
                dv[k] = float(t)
            except ValueError:
                say('字段 %s 不是数字' % k)
                return
        u1, v1, u2, v2 = to_corners(r, dv)
        for k, val in (('u1', u1), ('v1', v1), ('u2', u2), ('v2', v2),
                       ('w', dv['w']), ('h', dv['h'])):
            ant.fset(r, k, val)
        ant.sync_tail(r)
        # 自动把采样区同步到同组全部记录(出厂采样区+child相同)
        n = sync_group(quiet=True)
        if state['show_cov'].get():
            rebuild_coverage()
        refresh_overlay(rebuild_tree=True)
        say('已应用 #%d, 并自动同步同组 %d 条 (未写入, 记得保存)' % (r['idx'], n))


    # 用独立的 Frame 放两个按钮，确保它们不会因为 grid 挤压而位置异常
    btn_row = ttk.Frame(form)
    btn_row.grid(row=6, column=0, columnspan=2, sticky='ew', pady=(5, 3))

    ttk.Button(
        btn_row,
        text='应用数值',
        command=apply_entries
    ).pack(side='left', padx=(0, 6))

    ttk.Button(
        btn_row,
        text='撤销预览',
        command=revert_input
    ).pack(side='left')


    ttk.Label(
        form,
        foreground='#777',
        justify='left',
        wraplength=350,
        text=(
            '取样X/Y/宽/高 = 红框在图集上的位置和大小\n'
            '显示宽/高 = 游戏里画多大（负数=镜像）'
        )
    ).grid(
        row=7,
        column=0,
        columnspan=2,
        sticky='w',
        pady=(3, 0)
    )

    # 记录列表最后 pack —— 空间不够时它自己内部滚动, 不挤掉表单
    rec_frame = ttk.Frame(right); rec_frame.pack(fill='both', expand=True, padx=6, pady=4)
    tree = ttk.Treeview(rec_frame, columns=('rec',), show='headings', height=7)
    tree.heading('rec', text='记录列表 (点选后拖框/改数值; @=其他bin的框)')
    tree.column('rec', width=316)
    rec_scroll = ttk.Scrollbar(rec_frame, orient='vertical', command=tree.yview)
    tree.config(yscrollcommand=rec_scroll.set)
    rec_scroll.pack(side='right', fill='y')
    tree.pack(side='left', fill='both', expand=True)

    status = ttk.Label(root, anchor='w', text='就绪')
    status.pack(fill='x')

    def say(msg):
        status.config(text=msg)

    def dirty_list():
        return [a for b in state['bnas'] for a in b.ants.values() if a.dirty]

    # ---- gim 列表 ----
    def build_gim_index():
        items = []
        for b in state['bnas']:
            if not b.gims:
                continue
            maxchild = max((len(a.children) for a in b.ants.values()), default=0)
            for gi in range(max(len(b.gims) and max(b.gims) - b.n_bins + 1, maxchild)):
                fno = gi + b.n_bins
                recs = b.records_for_gim(gi)
                if fno not in b.gims and not recs:
                    continue
                dims = gim_dims(b.gims[fno]) if fno in b.gims else None
                if recs:
                    bins_ = sorted(set(n for n, _ in recs))
                    refs = ','.join('%04d' % n for n in bins_)
                else:
                    refs = '(无引用)'
                items.append(('%s/%s %04d' % (b.top.split('.')[0], b.name[:4], fno),
                              '%dx%d' % dims if dims else '?',
                              refs, (b, gi)))
        state['all_gims'] = items

    def sort_by(col):
        s = state['sort']
        s[1] = (not s[1]) if s[0] == col else False
        s[0] = col
        fill_gim_list(e_filter.get())

    def _sort_key(it):
        label, dims, refs, (b, gi) = it
        col = state['sort'][0]
        if col == 'gim':
            return (b.top, b.name, gi + b.n_bins)
        if col == 'dims':
            if dims == '?':
                return (0, 0, 0, '')
            w, h = (int(v) for v in dims.split('x'))
            return (w * h, w, h, '')
        n = 0 if refs.startswith('(') else len(refs.split(','))
        return (n, 0, 0, refs)

    def fill_gim_list(flt=''):
        gl_tree.delete(*gl_tree.get_children())
        flt = flt.strip().lower()
        items = []
        for label, dims, refs, key in state['all_gims']:
            if flt and flt not in label.lower() and flt not in refs.lower():
                continue
            items.append((label, dims, refs, key))
        items.sort(key=_sort_key, reverse=state['sort'][1])
        arrow = '↓' if state['sort'][1] else '↑'
        for col, t in (('gim', 'gim'), ('dims', '尺寸'), ('refs', '引用它的bin')):
            gl_tree.heading(col, text=(t + arrow) if col == state['sort'][0] else t)
        n = 0
        for label, dims, refs, key in items:
            gl_tree.insert('', 'end', values=(label, dims, refs))
            n += 1
            if n >= 1500:
                break
        say('gim列表: %d 项 (按%s%s)' % (n, state['sort'][0], arrow))

    def on_gim_list(_=None):
        sel = gl_tree.selection()
        if not sel:
            return
        vals = gl_tree.item(sel[0], 'values')
        # 从 label 反查
        for label, dims, refs, key in state['all_gims']:
            if label == vals[0]:
                select_gim(key)
                return

    def select_gim(key):
        b, gi = key
        state['gimkey'] = key
        state['sel'] = None
        state['img_cur'] = b.image_cur(gi)
        state['img_orig'] = b.image_orig(gi)
        state['img_png'] = b.image_png(gi)
        state['cov_photo'] = None
        recs = b.records_for_gim(gi)
        bins_ = sorted(set(n for n, _ in recs))
        state['bin_entries'] = [
            ('%s/%s  %04d.bin (%d条)' % (b.top.split('.')[0], b.name[:4], n,
                                         sum(1 for m, _ in recs if m == n)), (b, n))
            for n in bins_]
        c_bin.config(values=[e[0] for e in state['bin_entries']])
        state['curedit'] = None
        if state['bin_entries']:
            c_bin.current(0)
            on_bin_sel()
        else:
            refresh_bg(); refresh_overlay(rebuild_tree=True)
            say('%04d.gim 无 bin 引用 (代码直用/未用)' % (gi + b.n_bins))
        report_sources()

    def reload_images():
        """强制从磁盘重新载入当前 gim 的三张图(清掉内存缓存)"""
        if not state['gimkey']:
            return
        select_gim(state['gimkey'])
        report_sources()

    def report_sources():
        b, gi = state['gimkey'] or (None, None)
        if b is None:
            return
        fno = gi + b.n_bins
        png = b._png_path(gi)
        gimp = b.gims.get(fno)
        mtime = ''
        if gimp and os.path.exists(gimp):
            import time as _t
            mtime = _t.strftime('%m-%d %H:%M', _t.localtime(os.path.getmtime(gimp)))
        say('图源: PNG=%s | gim=%s%s | 原版=%s' % (
            (png or '无(回退gim)'), (gimp or '无'), ('(改于' + mtime + ')') if mtime else '',
            '有' if state['img_orig'] is not None else '无'))

    def on_bin_sel(*_):
        if not c_bin.get() or not state['bin_entries']:
            return
        _, (b, n) = state['bin_entries'][c_bin.current()]
        state['curedit'] = b.ants[n]
        refresh_bg()
        refresh_overlay(rebuild_tree=True)
        say('编辑 %s/%s 的 %04d.bin' % (b.top, b.name, n))

    def cov_toggled():
        if state['show_cov'].get():
            say('覆盖检查: 红色=图集里没有任何采样框引用的内容(数字条等, 代码按公式切片) '
                '→ 汉化时在原位重画即可, 无需也无处调框; 有框的部分才用记录调')
        else:
            say('覆盖检查关闭')
        rebuild_coverage()

    def view_changed():
        state['cov_photo'] = None
        refresh_bg()
        rebuild_coverage()
        refresh_overlay()

    def display_image():
        mode = state['view'].get()
        if mode == '原版':
            return state['img_orig'] or state['img_cur']
        if mode == '当前':
            return state['img_cur'] or state['img_orig']
        if mode == 'PNG':
            return state['img_png'] or state['img_cur'] or state['img_orig']
        if mode == '对位':
            base = state['img_png'] or state['img_cur']
            if base is None or state['img_orig'] is None:
                return state['img_orig'] or base
            key = id(state['img_orig'])
            if state.get('edge_key') != key:
                state['edge_ov'] = orig_edge_image(state['img_orig'])
                state['edge_key'] = key
            return Image.alpha_composite(base, state['edge_ov'])
        cur = state['img_png'] or state['img_cur']
        if cur is not None and state['img_orig'] is not None:
            return Image.alpha_composite(cur, state['img_orig'])
        return cur or state['img_orig']

    def cur_records():
        if not state['gimkey']:
            return []
        b, gi = state['gimkey']
        out = []
        for num in sorted(b.ants):
            ant = b.ants[num]
            for r in ant.records:
                if (r['type'] in SPRITE_TYPES
                        and r['child'] < len(ant.children)
                        and ant.children[r['child']] == gi):
                    out.append((num, r, ant))
        return out

    def self_rec():
        if state['curedit'] is None or state['sel'] is None:
            return None
        return next((r for r in state['curedit'].records if r['idx'] == state['sel']), None)

    def cur_bin_no():
        if not c_bin.get() or not state['bin_entries']:
            return -1
        return state['bin_entries'][c_bin.current()][1][1]

    # ---- 渲染 ----
    def refresh_bg():
        im = display_image()
        aw = im.size[0] if im else 256
        ah = im.size[1] if im else 256
        z = state['zoom']
        ox, oy = state['panx'], state['pany']
        cv.delete('all')
        if im:
            disp = im.resize((max(1, int(aw * z)), max(1, int(ah * z))), Image.NEAREST)
            state['photo'] = ImageTk.PhotoImage(disp)
            cv.create_image(ox, oy, image=state['photo'], anchor='nw')
        for gx in range(0, aw + 1, 32):
            cv.create_line(ox + gx * z, oy, ox + gx * z, oy + ah * z, fill='#333')
        for gy in range(0, ah + 1, 32):
            cv.create_line(ox, oy + gy * z, ox + aw * z, oy + gy * z, fill='#333')
        if state['cov_photo']:
            cv.create_image(ox, oy, image=state['cov_photo'], anchor='nw')
        draw_source_tag()

    def draw_source_tag():
        mode = state['view'].get()
        has_png = state.get('img_png') is not None
        has_cur = state.get('img_cur') is not None
        has_orig = state.get('img_orig') is not None
        if mode == '原版':
            txt = '底图: 游戏原版' + ('' if has_orig else '(缺失!)')
            col = '#7CFC00'
        elif mode == '当前':
            txt = '底图: ' + ('gim' if has_cur else 'png') if (has_cur or has_png) else '底图: 全缺失->原版'
            col = '#38D8F8'
        elif mode == 'PNG':
            if has_png:
                txt = '底图: PNG(你的图)'
                col = '#38D8F8'
            else:
                back = 'gim(旧版!)' if has_cur else ('原版' if has_orig else '无')
                txt = '⚠ PNG未找到 -> 正在显示回退: %s' % back
                col = '#FF5050'
        else:
            txt = '底图: 叠加对比(PNG/gim + 原版)'
            col = '#FFD070'
        cv.delete('srctag')
        cv.create_text(10, 6, text=txt, fill=col, anchor='nw', tags='srctag',
                       font=('msyh', 10, 'bold'))

    def rebuild_coverage():
        if not state['show_cov'].get():
            state['cov_photo'] = None
            state['inf_boxes'] = []
            refresh_bg(); refresh_overlay()
            return
        im = display_image()
        if im is None:
            return
        aw, ah = im.size
        px = im.tobytes()
        covered = bytearray(aw * ah)
        for _, r, _a in cur_records():
            x, y, w, h = uv_rect(r)
            for yy in range(max(0, int(y)), min(ah, int(y + h))):
                base = yy * aw
                for xx in range(max(0, int(x)), min(aw, int(x + w))):
                    covered[base + xx] = 1
        ov = bytearray(aw * ah * 4)
        for i in range(aw * ah):
            if not covered[i] and px[i*4+3] > 8:
                ov[i*4] = 255; ov[i*4+1] = 40; ov[i*4+2] = 40; ov[i*4+3] = 110
        z = state['zoom']
        cim = Image.frombytes('RGBA', (aw, ah), bytes(ov))
        state['cov_photo'] = ImageTk.PhotoImage(
            cim.resize((max(1, int(aw * z)), max(1, int(ah * z))), Image.NEAREST))
        state['inf_boxes'] = infer_uncovered_boxes(im, [r for _, r, _a in cur_records()])
        refresh_bg(); refresh_overlay()

    def refresh_overlay(rebuild_tree=False):
        cv.delete('ov')
        z, ox, oy = state['zoom'], state['panx'], state['pany']
        recs = cur_records()
        cbn = cur_bin_no()
        show_all = state['show_all'].get()
        shown = [(n, r) for n, r, _a in recs if (show_all or n == cbn)]
        if state['show_cov'].get() and state.get('inf_boxes'):
            for bx in state['inf_boxes']:
                cv.create_rectangle(ox + bx[0]*z, oy + bx[1]*z,
                                    ox + bx[2]*z + z, oy + bx[3]*z + z,
                                    outline='#E8E8E8', dash=(4, 3), tags='ov')
        for n, r in shown:
            use = rec_vals(r) if (state['sel'] == r['idx'] and n == cbn
                                  and state['preview']) else r
            x, y, w, h = uv_rect(use)
            sel = (state['sel'] == r['idx'] and n == cbn)
            if n == cbn:
                col = '#FF5050' if sel else '#38D8F8'
                label = '#%d' % r['idx']
            else:
                col = BIN_COLORS[n % len(BIN_COLORS)]
                label = '#%d@%04d' % (r['idx'], n)
            x1, y1 = ox + x * z, oy + y * z
            x2, y2 = x1 + w * z, y1 + h * z
            cv.create_rectangle(x1, y1, x2, y2, outline=col,
                                width=2 if sel else 1, tags='ov')
            cv.create_text(x1, y1 - 6, text=label, fill=col, anchor='sw', tags='ov')
        r = self_rec()
        if r:
            x, y, w, h = uv_rect(rec_vals(r))
            x1, y1 = ox + x * z, oy + y * z
            x2, y2 = x1 + w * z, y1 + h * z
            for hx, hy in ((x1, y1), (x2, y1), (x1, y2), (x2, y2)):
                cv.create_rectangle(hx-5, hy-5, hx+5, hy+5,
                                    fill='#FFD070', outline='#803000', tags='ov')
        if rebuild_tree:
            tree.delete(*tree.get_children())
            for n, r in shown:
                tag = '' if n == cbn else ' @%04d' % n
                tree.insert('', 'end', iid='%d|%d' % (r['idx'], n), values=(
                    '#%-3d%s 采样(%g,%g)-(%g,%g) 显示%gx%g%s%s' % (
                        r['idx'], tag, r['u1'], r['v1'], r['u2'], r['v2'],
                        abs(r['w']), abs(r['h']),
                        ' 镜X' if r['w'] < 0 else '', ' 镜Y' if r['h'] < 0 else ''),))
        draw_crop()

    def draw_crop():
        crop_cv.delete('all')
        im = display_image()
        r = self_rec()
        if not (im and r):
            return
        rv = rec_vals(r)
        x, y, w, h = [int(v) for v in uv_rect(rv)]
        x, y = max(0, x), max(0, y)
        w = max(1, min(w, im.size[0] - x))
        h = max(1, min(h, im.size[1] - y))
        crop = im.crop((x, y, x + w, y + h))
        k = min(335 / w, 140 / h, 4.0)
        crop = crop.resize((max(1, int(w * k)), max(1, int(h * k))), Image.NEAREST)
        state['crop_photo'] = ImageTk.PhotoImage(crop)
        crop_cv.create_image(167, 84, image=state['crop_photo'], anchor='center')
        crop_cv.create_text(167, 10, fill='#FFD070', text=(
            '#%d 采样%dx%d (原比例) | 游戏显示 %dx%d%s%s' % (
                r['idx'], w, h, abs(int(rv['w'])), abs(int(rv['h'])),
                ' 会拉伸' if (w and h and abs(abs(rv['w'])/max(1,abs(rv['h'])) - w/max(1,h)) > 0.05) else '',
                ' [预览]' if state['preview'] else '')))

    # ---- 交互 ----
    def cvxy(ev):
        return (ev.x - state['panx']) / state['zoom'], (ev.y - state['pany']) / state['zoom']

    def hit(ev):
        x, y = cvxy(ev)
        best = None
        for n, r, _a in cur_records():
            if not state['show_all'].get() and n != cur_bin_no():
                continue
            rx, ry, rw, rh = uv_rect(r)
            if rx - 3 <= x <= rx + rw + 3 and ry - 3 <= y <= ry + rh + 3:
                best = (n, r)
        return best

    def corner_at(ev, r):
        rx, ry, rw, rh = uv_rect(r)
        x1, y1 = state['panx'] + rx * state['zoom'], state['pany'] + ry * state['zoom']
        x2, y2 = x1 + rw * state['zoom'], y1 + rh * state['zoom']
        for cx, cy, kind in ((x1, y1, 'lt'), (x2, y2, 'rb'), (x1, y2, 'lb'), (x2, y1, 'rt')):
            if abs(ev.x - cx) <= 8 and abs(ev.y - cy) <= 8:
                return kind
        return None

    drag = {}

    def on_press(ev):
        r = self_rec()
        if r:
            k = corner_at(ev, r)
            if k:
                drag.clear()
                drag.update(mode='corner', which=k, r=r, sx=ev.x, sy=ev.y,
                            u1=r['u1'], v1=r['v1'], u2=r['u2'], v2=r['v2'])
                return
        h = hit(ev)
        if h:
            n, r = h
            if n != cur_bin_no():
                for i, (_label, (_bb, nn)) in enumerate(state['bin_entries']):
                    if nn == n:
                        c_bin.current(i); on_bin_sel(); break
            state['sel'] = r['idx']
            fill_entries(r)
            refresh_overlay(rebuild_tree=True)
            drag.clear()
            drag.update(mode='move', r=r, sx=ev.x, sy=ev.y,
                        u1=r['u1'], v1=r['v1'], u2=r['u2'], v2=r['v2'])

    def on_drag(ev):
        if 'pan' in drag:
            dx, dy = ev.x - drag['sx'], ev.y - drag['sy']
            state['panx'] = drag['panx'] + dx
            state['pany'] = drag['pany'] + dy
            cv.move('all', dx - drag.get('ldx', 0), dy - drag.get('ldy', 0))
            drag['ldx'], drag['ldy'] = dx, dy
            return
        if not drag:
            return
        r = drag['r']
        ant = state['curedit']
        dx = (ev.x - drag['sx']) / state['zoom']
        dy = (ev.y - drag['sy']) / state['zoom']
        if drag['mode'] == 'move':
            ant.fset(r, 'u1', round(drag['u1'] + dx))
            ant.fset(r, 'u2', round(drag['u2'] + dx))
            ant.fset(r, 'v1', round(drag['v1'] + dy))
            ant.fset(r, 'v2', round(drag['v2'] + dy))
        else:
            which = drag['which']
            if which in ('rb', 'rt'):
                ant.fset(r, 'u2', round(drag['u2'] + dx))
            if which in ('lb', 'lt'):
                ant.fset(r, 'u1', round(drag['u1'] + dx))
            if which in ('lb', 'rb'):
                ant.fset(r, 'v2', round(drag['v2'] + dy))
            if which in ('lt', 'rt'):
                ant.fset(r, 'v1', round(drag['v1'] + dy))
        fill_entries(r)
        refresh_overlay()

    def on_release(_):
        if drag and 'r' in drag:
            state['curedit'].sync_tail(drag['r'])
            if state['show_cov'].get():
                rebuild_coverage()
        drag.clear()
        refresh_overlay(rebuild_tree=True)
        d = dirty_list()
        if d:
            say('未保存改动: %d 个bin' % len(d))

    def on_wheel(ev):
        old = state['zoom']
        state['zoom'] = min(12.0, max(0.25, old * (1.25 if ev.delta > 0 else 0.8)))
        k = state['zoom'] / old
        state['panx'] = ev.x - (ev.x - state['panx']) * k
        state['pany'] = ev.y - (ev.y - state['pany']) * k
        refresh_bg()
        if state['show_cov'].get():
            rebuild_coverage()
        refresh_overlay()

    def on_press2(ev):
        drag.clear()
        drag.update(pan=True, sx=ev.x, sy=ev.y,
                    panx=state['panx'], pany=state['pany'], ldx=0, ldy=0)

    def on_key(ev):
        w = root.focus_get()

        if w is not None:
            cls = w.winfo_class()
            if cls in ('Entry', 'TEntry', 'Combobox', 'TCombobox'):
                return

        r = self_rec()
        if r is None:
            return

        step = 8 if (ev.state & 0x4) else 1
        d = {
            'Left': (-step, 0),
            'Right': (step, 0),
            'Up': (0, -step),
            'Down': (0, step)
        }.get(ev.keysym)

        if not d:
            return

        ant = state['curedit']
        ant.fset(r, 'u1', r['u1'] + d[0])
        ant.fset(r, 'u2', r['u2'] + d[0])
        ant.fset(r, 'v1', r['v1'] + d[1])
        ant.fset(r, 'v2', r['v2'] + d[1])
        ant.sync_tail(r)

        fill_entries(r)
        refresh_overlay()



    def _sync_xml(ant):
        if not state['gimkey']:
            return False
        b, _gi = state['gimkey']
        num = next((n for n, a in b.ants.items() if a is ant), -1)
        if num < 0:
            return False
        return update_xml_mods(ant, b.top, b.name, num)

    def save_cur():
        ant = state['curedit']
        if not ant:
            say('没有选中的 bin')
            return
        if not ant.dirty:
            say('当前 bin 没有未保存改动')
            return
        ant.save()
        if _sync_xml(ant):
            say('已写入 %s，并同步 XML 修改值' % ant.path)
        else:
            say('已写入 %s，但 XML 同步失败' % ant.path)
            
    def save_all():
        d = dirty_list()
        ok = []
        fail = []
        for ant in d:
            ant.save()
            if _sync_xml(ant):
                ok.append(ant.path)
            else:
                fail.append(ant.path)
        if not d:
            say('没有未保存的改动')
        else:
            msg = '已写入 %d 个bin' % len(d)
            if fail:
                msg += '，其中 XML 同步失败: %s' % ', '.join(fail)
            say(msg)

    def apply_all_btn():
        from tkinter import messagebox
        if not messagebox.askyesno(
            '确认应用 XML 修改',
            '这会把 XML 中记录的全部修改直接写回 bin 文件。\n\n'
            '操作后请自行备份原文件。\n\n'
            '确定继续吗？'
        ):
            return

        here = HERE
        nb, nr, fails = apply_all_edits(here)
        msg = '已把XML修改值写回 %d 个bin (%d条记录)' % (nb, nr)
        if fails:
            msg += '; 缺失文件 %d 个' % len(fails)
        # 重新加载当前bin显示
        if state['gimkey']:
            b, _gi = state['gimkey']
            for num, ant in b.ants.items():
                ant.__init__(ant.path)
            on_bin_sel()
        say(msg)
        if fails:
            messagebox.showwarning('应用XML修改', '缺失:\n' + '\n'.join(fails[:10]))

    def export_boxes_png():
        from PIL import ImageDraw
        im = display_image()
        if im is None or not state['gimkey']:
            say('没有可导出的图')
            return
        b, gi = state['gimkey']
        k = 3
        big = im.resize((im.size[0]*k, im.size[1]*k), Image.NEAREST).convert('RGB')
        dr = ImageDraw.Draw(big)
        cbn = cur_bin_no()
        for n, r, _a in cur_records():
            x, y, w, h = uv_rect(r)
            col = (255, 80, 80) if n == cbn else (56, 216, 248)
            dr.rectangle([x*k, y*k, (x+w)*k, (y+h)*k], outline=col, width=2)
            dr.text((x*k + 2, y*k + 2),
                    '#%d%s' % (r['idx'], '' if n == cbn else '@%04d' % n),
                    fill=(255, 255, 0))
        if state['show_cov'].get() and state.get('inf_boxes'):
            for bx in state['inf_boxes']:
                dr.rectangle([bx[0]*k, bx[1]*k, bx[2]*k, bx[3]*k],
                             outline=(220, 220, 220), width=1)
        fn = '框图_%s_%s_%04d.png' % (b.top.split('.')[0], b.name[:4], gi + b.n_bins)
        big.save(fn)
        say('已导出 %s (红=当前bin 青=其他bin 白=无框内容)' % fn)

    def restore_defaults():
        # 1. 获取当前选中的记录（单选）
        r = self_rec()
        if r is None:
            say('请先在记录列表中选择一条记录')
            return

        ant = state['curedit']
        if ant is None:
            say('没有选中的 bin')
            return

        if not state['gimkey']:
            say('没有选中的 gim')
            return

        b, _gi = state['gimkey']

        # 2. 加载 XML 默认值
        try:
            defaults = load_defaults_xml(DEFAULTS_XML)
        except Exception as e:
            say('读取 %s 失败: %s' % (DEFAULTS_XML, e))
            return

        # 3. 找到当前 bin 的编号
        num = next((n for n, a in b.ants.items() if a is ant), -1)
        if num < 0:
            say('找不到当前 bin 编号')
            return

        key = (b.top, b.name, num)
        ent = defaults.get(key)
        if not ent:
            say('XML 中找不到该 bin 的默认值')
            return

        # 4. 只取当前这一条记录的出厂值 (orig)
        fl = ent['orig'].get(r['idx'])
        if fl is None:
            say('XML 中找不到记录 #%d 的默认值' % r['idx'])
            return

        # 5. 把出厂值写回内存（只改这一条）
        struct.pack_into('<13f', ant.data, r['off'] + 4, *fl)

        # 6. 更新当前记录对象的所有字段
        for k, key2 in enumerate(('u1', 'v1', 'u2', 'v2', 'w', 'h', 'x6', 'x7', 'rot',
                                  'f28', 'f2c', 'x12', 'x13')):
            if key2 in r:
                r[key2] = fl[k]
        r['_ow'], r['_oh'], r['_o28'], r['_o2c'] = fl[4], fl[5], fl[9], fl[10]

        # 7. 标记 bin 为已修改（未保存）
        ant.dirty = True

        # 8. 刷新输入框和画布
        fill_entries(r)
        refresh_overlay(rebuild_tree=True)

        say('已恢复当前记录 #%d 为 XML 出厂值（未写入，需点保存）' % r['idx'])

    def on_tree(_=None):
        sel = tree.selection()
        if sel:
            n, idx = sel[0].split('|')
            if int(n) == cur_bin_no():
                state['sel'] = int(idx)
                r = self_rec()
                if r:
                    fill_entries(r)
                    refresh_overlay()

    def on_filter(_=None):
        fill_gim_list(e_filter.get())

    for k in ('sx', 'sy', 'sw', 'sh', 'w', 'h'):
        entries[k].bind('<KeyRelease>', on_entry_input)
    e_filter.bind('<KeyRelease>', on_filter)
    gl_tree.bind('<<TreeviewSelect>>', on_gim_list)
    cv.bind('<Button-1>', on_press)
    cv.bind('<B1-Motion>', on_drag)
    cv.bind('<ButtonRelease-1>', on_release)
    cv.bind('<Button-2>', on_press2)
    cv.bind('<Button-3>', on_press2)
    cv.bind('<B2-Motion>', on_drag)
    cv.bind('<B3-Motion>', on_drag)
    cv.bind('<MouseWheel>', on_wheel)
    tree.bind('<<TreeviewSelect>>', on_tree)
    c_bin.bind('<<ComboboxSelected>>', on_bin_sel)
    root.bind('<KeyPress>', on_key)

    root.geometry('1420x860')
    say('扫描 extracted ...')
    root.update()
    state['bnas'] = scan_archives(os.path.join(HERE, 'extracted'))
    if not state['bnas']:
        state['bnas'] = scan_archives(HERE)
    build_gim_index()
    if not os.path.exists(DEFAULTS_XML):
        try:
            save_defaults_xml(DEFAULTS_XML, build_defaults(state['bnas']))
            say('%d个bna/%d个gim; 已生成默认值 %s' % (
                len(state['bnas']), len(state['all_gims']), os.path.basename(DEFAULTS_XML)))
        except Exception as e:
            say('默认值XML生成失败: %s' % e)
    else:
        say('%d个bna / %d个gim, 默认值XML已存在' % (len(state['bnas']), len(state['all_gims'])))
    fill_gim_list()
    # 默认选中 0170
    for i, (label, dims, refs, key) in enumerate(state['all_gims']):
        if label.endswith('0170'):
            children = gl_tree.get_children()
            if i < len(children):
                gl_tree.selection_set(children[i])
                gl_tree.see(children[i])
            break
    if os.environ.get('ANT_LAYOUT_CHECK'):
        def _dump():
            order = [w.winfo_name() for w in right.winfo_children()]
            print('RIGHT_PANEL_ORDER:', order)
            print('FORM_CHILDREN:', len(form.winfo_children()),
                  'ENTRIES:', len(entries))
            print('FORM_VISIBLE_HEIGHT:', form.winfo_height())
            bar_btns = [w.cget('text') for w in bar.winfo_children()
                        if isinstance(w, ttk.Button)]
            print('TOPBAR_BUTTONS:', bar_btns)
            if state['gimkey']:
                b, gi = state['gimkey']
                print('GIMKEY: %s/%s 索引%d 文件%04d' % (
                    b.top, b.name, gi, gi + b.n_bins))
                print('IMG_STATE: png=%s cur=%s orig=%s view=%s' % (
                    '有' if state['img_png'] else 'None',
                    '有' if state['img_cur'] else 'None',
                    '有' if state['img_orig'] else 'None',
                    state['view'].get()))
                print('PNG_PATH:', b._png_path(gi))
            root.destroy()
        root.after(2500, _dump)
    root.mainloop()


def selftest():
    here = os.path.dirname(os.path.abspath(__file__))
    bnas = scan_archives(os.path.join(here, 'extracted'))
    if not bnas:
        bnas = scan_archives(here)
    assert len(bnas) >= 1
    b4 = next(b for b in bnas if b.name == '0004.bna' and b.top == 'shared.bin')
    assert b4.n_bins == 165
    recs = b4.records_for_gim(5)
    assert sorted(set(n for n, _ in recs)) == [1] and len(recs) == 20  # 曲线记录已过滤
    # 坐标断言用出厽数据(提取目录里的文件可能正被用户编辑)
    orig = _orig_stream(b4)
    o_off = orig.find(bytes(b4.ants[1].data[:0x50]))
    f04, f08, f0c, f10 = struct.unpack_from('<4f', orig,
                                            o_off + 0x50 + 3 * 0x40 + 4)
    assert (f04, f08, f0c, f10) == (96.0, 56.0, 160.0, 88.0)
    im = b4.image_orig(5)
    assert im is not None and im.size == (256, 256)
    d = gim_dims(b4.gims[165])
    assert d == (128, 24), d
    print('selftest OK (v6)')


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        selftest()
    else:
        run_gui()
