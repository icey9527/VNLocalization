# -*- coding: utf-8 -*-
# Weiss Schwarz Portable .BRP 解包/打包
# 用法:
#   python brp.py u backup/__FINAL.BRP FINAL    解包
#   python brp.py p FINAL repack/__FINAL.BRP    打包
# 名字: list.txt 里按名字命中 -> 按真实路径存放; 没命中的 -> $哈希.后缀(后缀按文件头猜)
# 打包: $开头的文件从文件名取哈希, 其余按相对路径算哈希(大小写必须和原名一致)
# 文件夹里的 list.xml 记录每条的压缩状态(z)和索引meta字段(m), 打包时原样还原;
#   没记录的新文件: 内容以1f8b开头则裸存, 否则压缩后更小就存gzip, meta=0
# *.txt 不打包: 反编译出来的明文lua存成 .LUA.txt, 千万别覆盖 .LUA 本身(游戏读的是字节码)

import os
import sys
import zlib
import xml.etree.ElementTree as ET

SECTOR = 2048

_TBL = []
for _x in range(256):
    _c = _x << 24
    for _ in range(8):
        _c = ((_c << 1) ^ 0x04C11DB7) & 0xFFFFFFFF if _c & 0x80000000 else (_c << 1) & 0xFFFFFFFF
    _TBL.append(_c)

def name_crc(s):
    if isinstance(s, str):
        s = s.encode()
    i = 0
    for c in s:
        i = ((i << 8) & 0xFFFFFFFF) ^ _TBL[((i >> 24) & 0xFF) ^ c]
    return (~i) & 0xFFFFFFFF

def gz_store(data):
    co = zlib.compressobj(1, zlib.DEFLATED, -15)
    body = co.compress(data) + co.flush()
    return b'\x1f\x8b\x08\x00\x00\x00\x00\x00\x04\x03' + body + \
           zlib.crc32(data).to_bytes(4, 'little') + (len(data) & 0xFFFFFFFF).to_bytes(4, 'little')

def gz_load(data):
    return zlib.decompress(data, 31)

def guess_ext(d):
    if d[:4] == b'\x1bLua':           return '.lua'
    if d[:4] == b'PSMF':              return '.pmf'
    if d[:4] == b'RIFF':              return '.at3' if b'\xe9\x23\xaa\xbf' in d[:0x50] else '.wav'
    if d[:8] == b'\x89PNG\r\n\x1a\n': return '.png'
    if d[:4] == b'OggS':              return '.ogg'
    if d[:4] == b'GIM\x00':           return '.gim'
    if d[:4] == b'BIN\x00':           return '.bin'
    return ''

def load_names():
    names = {}
    if os.path.isfile('list.txt'):
        for line in open('list.txt', encoding='utf-8'):
            line = line.strip()
            if line:
                names[name_crc(line)] = line
    return names

def brh_of(path):
    d, b = os.path.split(path)
    stem, _ = os.path.splitext(b)
    if stem.startswith('_'):
        stem = stem[1:]
    return os.path.join(d, stem + '.BRH')

def unpack(brp_path, outdir):
    brh_path = brh_of(brp_path)
    if not os.path.isfile(brh_path):
        print('找不到索引:', brh_path)
        return
    d = open(brh_path, 'rb').read()
    n = int.from_bytes(d[0:4], 'little')
    A = d[8:8+4*n]; B = d[8+4*n:8+8*n]; C = d[8+8*n:8+12*n]; D = d[8+12*n:8+16*n]
    brp = open(brp_path, 'rb').read()
    names = load_names()
    os.makedirs(outdir, exist_ok=True)
    xml = open(os.path.join(outdir, 'list.xml'), 'w', encoding='utf-8', newline='\n')
    xml.write('<?xml version="1.0" encoding="utf-8"?>\n<list>\n')
    for i in range(n):
        h   = int.from_bytes(A[4*i:4*i+4], 'little')
        off = int.from_bytes(B[4*i:4*i+4], 'little')
        siz = int.from_bytes(C[4*i:4*i+4], 'little')
        met = int.from_bytes(D[4*i:4*i+4], 'little')
        raw = brp[off:off+siz]
        gz  = raw[:2] == b'\x1f\x8b'
        data = gz_load(raw) if gz else raw
        if h in names:
            fname = names[h].replace('/', os.sep)
        else:
            fname = '$%08X%s' % (h, guess_ext(data))
        fp = os.path.join(outdir, fname)
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        open(fp, 'wb').write(data)
        xml.write('<f h="%08X" z="%d" m="%08X"/>\n' % (h, 1 if gz else 0, met))
        print(fname)
    xml.write('</list>\n')
    xml.close()
    print('解包完成: %d 个文件 -> %s' % (n, outdir))

def pack(indir, brp_path):
    info = {}
    xml_path = os.path.join(indir, 'list.xml')
    if os.path.isfile(xml_path):
        for f in ET.parse(xml_path).getroot().iter('f'):
            info[int(f.get('h'), 16)] = (f.get('z') == '1', int(f.get('m'), 16))
    ent = []
    for root, _dirs, files in os.walk(indir):
        for f in files:
            if f.lower().endswith(('.txt', '.xml')) or f.lower() == 'desktop.ini':
                continue
            fp = os.path.join(root, f)
            rel = os.path.relpath(fp, indir).replace(os.sep, '/')
            base = rel.rsplit('/', 1)[-1]
            h = int(base[1:9], 16) if base.startswith('$') else name_crc(rel)
            data = open(fp, 'rb').read()
            gz, met = info.get(h, (None, 0))
            if gz is None:                       # list.xml 里没有的新文件
                gz = data[:2] != b'\x1f\x8b' and len(gz_store(data)) < len(data)
            if gz and data[:2] != b'\x1f\x8b':
                blob = gz_store(data)            # 内容本身是gzip的只能裸存, 不能套两层
            else:
                blob = data
            ent.append((h, met, blob, rel))
    ent.sort(key=lambda e: e[0])
    uniq = []
    seen = set()
    for e in ent:
        if e[0] in seen:
            print('哈希冲突, 跳过:', e[3])
            continue
        seen.add(e[0])
        uniq.append(e)
    A = b''; B = b''; C = b''; D = b''; out = bytearray(); off = 0
    for h, met, blob, _rel in uniq:
        A += h.to_bytes(4, 'little'); B += off.to_bytes(4, 'little')
        C += len(blob).to_bytes(4, 'little'); D += met.to_bytes(4, 'little')
        out += blob
        pad = -len(blob) % SECTOR
        out += b'\x00' * pad
        off += len(blob) + pad
    n = len(uniq)
    od = os.path.dirname(brp_path)
    if od:
        os.makedirs(od, exist_ok=True)
    open(brp_path, 'wb').write(out)
    open(brh_of(brp_path), 'wb').write(n.to_bytes(4, 'little') * 2 + A + B + C + D)
    print('打包完成: %d 个文件 -> %s / %s' % (n, brp_path, brh_of(brp_path)))

if __name__ == '__main__':
    if len(sys.argv) != 4 or sys.argv[1] not in ('u', 'p'):
        print('用法: python brp.py u xx.BRP 输出文件夹   (解包)')
        print('      python brp.py p 输出文件夹 xx.BRP   (打包)')
    elif sys.argv[1] == 'u':
        unpack(sys.argv[2], sys.argv[3])
    else:
        pack(sys.argv[2], sys.argv[3])
