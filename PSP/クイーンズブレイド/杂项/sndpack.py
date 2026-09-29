# -*- coding: utf-8 -*-
"""Queen's Blade SC — USRDIR/sound 专用解包/回写工具 (sndsq.bin / sndstrm.bin)

这两个档不是 qbsc 那种「ELF FAT + LBA」格式, ELF 里没有逐文件表,
游戏引导时自行扫描扇区结构 (BOOT.BIN sub_892FE9C 只把 MPAK 记录换算成
LBA 键), 所以 qbsc.exe 对它们只能解出一堆 padding。本工具按磁盘上的
自描述结构直接切分:

sndsq.bin  (0x8DD000 字节, ISO LBA 基址 0x5D230):
  77 个扇区对齐的 pack, 每个 pack:
    偏移 0x00 "MPAK" + u32版本(=1) + u32文件数 + u32头长
    偏移 0x10 起文件数个 {u32偏移, u32长度} 条目 (MIDI 全部 0x40 字节)
    头长 = align64(16 + 8*文件数), 条目偏移相对头末尾
    MIDI 区之后到 pack 末尾是 PPHD/PPPG/PPTN/PPVA 音色库 + ADPCM 数据
  合计 1062 个 MThd (格式 0, 单 MTrk 的短 BGM/效果音序列)。

sndstrm.bin (0x2A65800 字节, ISO LBA 基址 0x5E3F0):
  1799 个扇区对齐的 RIFF/WAVE (AT3+) 顺序拼接, 长度由 RIFF 头自述,
  文件间全零补齐到 0x800, 无空隙。

用法:
  python sndpack.py e <sndsq.bin|sndstrm.bin|含两者的目录> <输出目录>
  python sndpack.py p <输出目录> <目标 .bin 或目录(按 manifest 重建)>

回写约束 (保证与原档字节布局一致, 不破坏游戏的主索引):
  - MIDI 必须仍是 0x40 字节 (MThd 格式 0 短序列, 没有加长余地);
  - 音色库 / AT3 新数据不得大于原槽位, 不足部分自动补零;
  - 不得增删文件。替换音频请先压到不大于原始大小。
未改动时 p 重建结果与原始档逐字节一致 (manifest 记录原始槽位)。
"""
import argparse
import json
import struct
import sys
from pathlib import Path

SECTOR = 0x800
BASE_LBA = {"sndsq.bin": 0x5D230, "sndstrm.bin": 0x5E3F0}


class SndError(ValueError):
    pass


def u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def align(value, unit):
    return (value + unit - 1) & ~(unit - 1)


# ---------------------------------------------------------------- 解包

def extract_sndsq(data, out_dir):
    packs = [o for o in range(0, len(data) - 0x40, SECTOR)
             if data[o:o + 4] == b"MPAK"]
    if not packs:
        raise SndError("sndsq.bin: 找不到任何 MPAK pack")
    manifest = {"archive": "sndsq.bin", "packs": []}
    for index, start in enumerate(packs):
        count = u32(data, start + 8)
        header_size = u32(data, start + 12)
        if (data[start + 4:start + 8] != b"\x01\0\0\0" or
                header_size < 16 + 8 * count or
                header_size % 0x40 or start + header_size > len(data)):
            raise SndError(f"pack {index}: 异常 MPAK 头 (count={count}, "
                           f"头长={header_size:#x})")
        pack_dir = out_dir / f"p{index:02d}"
        pack_dir.mkdir(parents=True, exist_ok=True)
        data_start = start + header_size
        bank_end = packs[index + 1] if index + 1 < len(packs) else len(data)
        bank_start = data_start
        for j in range(count):
            entry_off, entry_size = struct.unpack_from(
                "<II", data, start + 16 + 8 * j)
            blob = data[data_start + entry_off:
                        data_start + entry_off + entry_size]
            if blob[:4] != b"MThd":
                raise SndError(f"pack {index} 条目 {j}: 不是 MThd")
            (pack_dir / f"m{j:02d}.mid").write_bytes(blob)
            bank_start = max(bank_start, data_start + entry_off + entry_size)
        bank = data[bank_start:bank_end]
        if bank[:4] != b"PPHD":
            raise SndError(f"pack {index}: MIDI 区后不是 PPHD "
                           f"(实际 {bank[:4]!r})")
        (pack_dir / "bank.bin").write_bytes(bank)
        manifest["packs"].append({
            "dir": f"p{index:02d}",
            "offset": start,
            "lba": BASE_LBA["sndsq.bin"] + start // SECTOR,
            "midi": count,
            "header_size": header_size,
            "bank_span": bank_end - bank_start,
        })
    return manifest


def extract_sndstrm(data, out_dir):
    manifest = {"archive": "sndstrm.bin", "files": []}
    offset = 0
    index = 0
    while offset < len(data):
        if data[offset:offset + 4] == b"RIFF":
            if data[offset + 8:offset + 12] != b"WAVE":
                raise SndError(f"{offset:#x}: RIFF 但非 WAVE")
            size = 8 + u32(data, offset + 4)
            span = align(size, SECTOR)
            if offset + size > len(data):
                raise SndError(f"{offset:#x}: RIFF 长度越界")
            pad = data[offset + size:offset + span]
            if pad.strip(b"\0"):
                raise SndError(f"{offset:#x}: 文件尾部补齐区非零, 布局假设不成立")
            (out_dir / f"{index:04d}.at3").write_bytes(
                data[offset:offset + size])
            manifest["files"].append({
                "name": f"{index:04d}.at3",
                "offset": offset,
                "lba": BASE_LBA["sndstrm.bin"] + offset // SECTOR,
                "size": size,
                "span": span,
            })
            offset += span
            index += 1
        else:
            raise SndError(f"{offset:#x}: 期望 RIFF 头 (档可能损坏)")
    return manifest


def extract_archive(bin_path, out_root):
    data = Path(bin_path).read_bytes()
    if data[:4] == b"MPAK":
        kind = "sndsq.bin"
        manifest = extract_sndsq(data, out_root)
    elif data[:4] == b"RIFF":
        kind = "sndstrm.bin"
        manifest = extract_sndstrm(data, out_root)
    else:
        raise SndError(f"{bin_path}: 既不是 MPAK 也不是 RIFF 开头")
    (out_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return kind, manifest


# ---------------------------------------------------------------- 回写

def build_sndsq(src_dir, manifest, out_path):
    total = 0
    with open(out_path, "wb") as out:
        for pack in manifest["packs"]:
            pack_dir = src_dir / pack["dir"]
            count = pack["midi"]
            header_size = pack["header_size"]
            midis = sorted(pack_dir.glob("m??.mid"))
            if len(midis) != count:
                raise SndError(f"{pack['dir']}: MIDI 数量不符 "
                               f"({len(midis)} != {count}), 不允许增删文件")
            header = bytearray(header_size)
            struct.pack_into("<4sIII", header, 0, b"MPAK", 1, count,
                             header_size)
            blob = bytearray()
            for j, path in enumerate(midis):
                midi = path.read_bytes()
                if len(midi) != 0x40 or midi[:4] != b"MThd":
                    raise SndError(f"{pack['dir']}/m{j:02d}.mid: "
                                   f"必须保持 0x40 字节的 MThd")
                struct.pack_into("<II", header, 16 + 8 * j, j * 0x40, 0x40)
                blob += midi
            bank_path = pack_dir / "bank.bin"
            bank = bank_path.read_bytes() if bank_path.exists() else b""
            span = pack["bank_span"]
            if len(bank) > span:
                raise SndError(f"{pack['dir']}/bank.bin: {len(bank)} 字节 "
                               f"超过原槽位 {span}, 请压缩到不大于原始大小")
            blob += bank + b"\0" * (span - len(bank))
            out.write(header)
            out.write(blob)
            total += len(header) + len(blob)
    return total


def build_sndstrm(src_dir, manifest, out_path):
    total = 0
    with open(out_path, "wb") as out:
        for entry in manifest["files"]:
            blob = (src_dir / entry["name"]).read_bytes()
            if len(blob) > entry["span"]:
                raise SndError(f"{entry['name']}: {len(blob)} 字节超过原槽位 "
                               f"{entry['span']}, 请压缩到不大于原始大小")
            out.write(blob)
            out.write(b"\0" * (entry["span"] - len(blob)))
            total += entry["span"]
    return total


def build_archive(src_dir, out_target):
    manifest = json.loads((src_dir / "manifest.json").read_text("utf-8"))
    if manifest["archive"] == "sndsq.bin":
        build = build_sndsq
    else:
        build = build_sndstrm
    out_target = Path(out_target)
    if out_target.is_dir() or not out_target.suffix:
        out_target.mkdir(parents=True, exist_ok=True)
        out_path = out_target / manifest["archive"]
        build(src_dir, manifest, out_path)
        return out_path
    build(src_dir, manifest, out_target)
    return out_target


# ---------------------------------------------------------------- 入口

def cmd_extract(inputs, out_root):
    out_root = Path(out_root)
    targets = []
    for item in inputs:
        item = Path(item)
        if item.is_dir():
            targets += [p for name in BASE_LBA for p in item.glob(name)]
        else:
            targets.append(item)
    if not targets:
        raise SndError("没有找到 sndsq.bin / sndstrm.bin")
    for bin_path in targets:
        sub = out_root / bin_path.name
        sub.mkdir(parents=True, exist_ok=True)
        kind, manifest = extract_archive(bin_path, sub)
        if kind == "sndsq.bin":
            detail = (f"{len(manifest['packs'])} packs, "
                      f"{sum(p['midi'] for p in manifest['packs'])} MIDI")
        else:
            detail = f"{len(manifest['files'])} AT3"
        print(f"{bin_path.name}: {detail} -> {sub}")


def cmd_pack(src_dir, out_target):
    src_dir = Path(src_dir)
    out_path = build_archive(src_dir, out_target)
    print(f"重建完成 -> {out_path} ({out_path.stat().st_size} 字节)")


def main():
    parser = argparse.ArgumentParser(
        description="sndsq.bin / sndstrm.bin 解包与回写")
    parser.add_argument("cmd", choices=("e", "p"), help="e=解包 p=回写")
    parser.add_argument("input", help="e: bin或目录(可多个) / p: 解包输出目录")
    parser.add_argument("output", nargs="+",
                        help="e: 输出目录 / p: 目标 bin 或目录")
    args = parser.parse_args()
    try:
        if args.cmd == "e":
            cmd_extract([args.input] + args.output[:-1], args.output[-1])
        else:
            cmd_pack(args.input, args.output[0])
    except (SndError, OSError) as error:
        print(f"错误: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
