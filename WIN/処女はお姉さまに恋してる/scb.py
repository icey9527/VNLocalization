import argparse
import os
import struct
import sys
from pathlib import Path

DEFAULT_ENCODING = 'cp932'


def parse_scb(data, encoding):
    f0 = struct.unpack_from('<I', data, 0)[0]
    f4 = struct.unpack_from('<I', data, 4)[0]
    hdr_extra = (f0 & 0xFFFF) + 18
    text_count = f4 & 0xFFFF
    off_tab = 8 + hdr_extra
    text_start = off_tab + text_count * 4
    offsets = [struct.unpack_from('<I', data, off_tab + i * 4)[0] for i in range(text_count)]
    strings = [
        data[text_start + off:data.index(b'\x00', text_start + off)].decode(encoding, errors='ignore')
        for off in offsets
    ]
    return f0, f4, hdr_extra, text_count, strings


def iter_scb_files(in_dir):
    for fn in sorted(os.listdir(in_dir)):
        if not fn.endswith('.scb'):
            continue
        yield fn


def cmd_extract(in_dir, out_dir, encoding):
    os.makedirs(out_dir, exist_ok=True)
    for fn in iter_scb_files(in_dir):
        scb_path = Path(in_dir) / fn
        data = scb_path.read_bytes()
        _, _, _, text_count, strings = parse_scb(data, encoding)
        (Path(out_dir) / fn).with_suffix('.txt').write_text('\n'.join(strings), encoding='utf-8')
        print(f'{fn}: {text_count} lines')


def cmd_writeback(in_dir, txt_dir, out_dir, encoding):
    os.makedirs(out_dir, exist_ok=True)
    for fn in iter_scb_files(in_dir):
        scb_path = Path(in_dir) / fn
        txt_path = Path(txt_dir) / fn.replace('.scb', '.txt')
        if not txt_path.exists():
            print(f'{txt_path}: not found, skipping')
            continue
        data = scb_path.read_bytes()
        _, f4, hdr_extra, text_count, _ = parse_scb(data, encoding)
        hdr_size = 8 + hdr_extra
        header = data[:hdr_size]
        lines = txt_path.read_text(encoding='utf-8').splitlines()
        if len(lines) != text_count:
            print(f'{fn}: count mismatch ({len(lines)} vs {text_count}), using actual')
            f4 = (f4 & 0xFFFF0000) | (len(lines) & 0xFFFF)
            header = bytearray(header)
            struct.pack_into('<I', header, 4, f4)
        out = bytearray(header)
        out.extend(b'\x00' * (len(lines) * 4))
        offsets = []
        text_data = bytearray()
        for line in lines:
            offsets.append(len(text_data))
            text_data.extend(line.encode(encoding, errors='ignore'))
            text_data.append(0)
        for i, off in enumerate(offsets):
            struct.pack_into('<I', out, hdr_size + i * 4, off)
        out.extend(text_data)
        (Path(out_dir) / fn).write_bytes(out)
        print(f'{fn}: {len(lines)} lines written')


def build_parser():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='mode', required=True)

    pe = sub.add_parser('e')
    pe.add_argument('input_dir')
    pe.add_argument('output_dir')
    pe.add_argument('-e', '--encoding', default=DEFAULT_ENCODING, help=f'write/read encoding (default: {DEFAULT_ENCODING})')

    pw = sub.add_parser('w')
    pw.add_argument('input_dir')
    pw.add_argument('text_dir')
    pw.add_argument('output_dir')
    pw.add_argument('-e', '--encoding', default=DEFAULT_ENCODING, help=f'write/read encoding (default: {DEFAULT_ENCODING})')
    return p

if __name__ == '__main__':
    args = build_parser().parse_args()
    mode = args.mode
    if mode == 'e':
        cmd_extract(args.input_dir, args.output_dir, args.encoding)
    elif mode == 'w':
        cmd_writeback(args.input_dir, args.text_dir, args.output_dir, args.encoding)
