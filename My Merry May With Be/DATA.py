import struct
import os
import argparse
from pathlib import Path

def decode_text_bytes(raw: bytes) -> str:
    if not raw:
        return ""
    try:
        return raw.decode('cp932')
    except UnicodeDecodeError:
        return "<HEX:" + raw.hex().upper() + ">"

def read_raw_cstring(data: bytes, offset: int) -> bytes:
    if offset >= len(data):
        return b""
    end = offset
    while end < len(data) and data[end] != 0:
        end += 1
    return data[offset:end]

def escape_for_txt(s: str) -> str:
    return s.replace("\\", "\\\\").replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")

def unescape_from_txt(s: str) -> str:
    out = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s):
            n = s[i + 1]
            if n == "n": out.append("\n"); i += 2; continue
            elif n == "r": out.append("\r"); i += 2; continue
            elif n == "t": out.append("\t"); i += 2; continue
            elif n == "\\": out.append("\\"); i += 2; continue
        out.append(ch)
        i += 1
    return "".join(out)

def parse_section_0_17(data, start, end, pointers):
    lines = []
    offset = start
    while offset + 16 <= end:
        vals = struct.unpack('<4I', data[offset:offset+16])
        pointers.add(vals[0])
        pointers.add(vals[1])
        lines.append(('type0', vals))
        offset += 16
    return lines

def parse_section_1(data, start, end, pointers):
    lines = []
    offset = start
    while offset + 20 <= end:
        vals = struct.unpack('<5I', data[offset:offset+20])
        pointers.add(vals[0])
        pointers.add(vals[1])
        pointers.add(vals[2])
        lines.append(('type1', vals))
        offset += 20
    return lines

def parse_section_3_8_14_16(data, start, end, pointers):
    lines = []
    offset = start
    while offset + 4 <= end:
        val = struct.unpack('<I', data[offset:offset+4])[0]
        pointers.add(val)
        lines.append(('type3', val))
        offset += 4
    return lines

def parse_section_15(data, start, end, pointers):
    lines = []
    offset = start
    while offset + 8 <= end:
        vals = struct.unpack('<2I', data[offset:offset+8])
        pointers.add(vals[0])
        lines.append(('type15', vals))
        offset += 8
    return lines

def parse_section_hex(data, start, end):
    return [('hex', data[start:end])]

def parse_section_18(data, start):
    """分区18: 4字节一组，找到0x020D(0D 02)作为终止符"""
    lines = []
    offset = start
    
    # 按4字节读取，直到遇到包含 0x020D 的数据
    while offset + 4 <= len(data):
        val = struct.unpack('<I', data[offset:offset+4])[0]
        lines.append(('type18', val))
        offset += 4
        
        # 检查低16位是否是 0x020D (小端 0D 02)
        if (val & 0xFFFF) == 0x020D:
            break
    
    text_start = offset
    return lines, text_start

def decode_data_bin(input_file, output_asm, output_txt):
    """解码 DATA.BIN"""
    with open(input_file, "rb") as f:
        data = f.read()
    
    if len(data) < 76:
        print(f"  ⚠️  文件太小，跳过")
        return False
    
    # 读取19个偏移量
    offsets = list(struct.unpack('<19I', data[0:76]))
    
    # 构建分区列表
    sections = []
    sorted_offsets = [(i, offsets[i]) for i in range(19) if 76 <= offsets[i] < len(data)]
    sorted_offsets.sort(key=lambda x: x[1])
    
    if not sorted_offsets:
        print(f"  ⚠️  无有效分区，跳过")
        return False
    
    for idx, (section_id, offset) in enumerate(sorted_offsets):
        next_offset = sorted_offsets[idx + 1][1] if idx + 1 < len(sorted_offsets) else len(data)
        sections.append((section_id, offset, next_offset))
    
    # 解析分区，收集文本指针
    pointers = set()
    section_data = {}
    text_start = len(data)
    
    for section_id, start, end in sections:
        if section_id in [0, 17]:
            section_data[section_id] = parse_section_0_17(data, start, end, pointers)
        elif section_id == 1:
            section_data[section_id] = parse_section_1(data, start, end, pointers)
        elif section_id in [2, 4, 5, 6, 7, 9, 10, 11, 12, 13]:
            section_data[section_id] = parse_section_hex(data, start, end)
        elif section_id in [3, 8, 14, 16]:
            section_data[section_id] = parse_section_3_8_14_16(data, start, end, pointers)
        elif section_id == 15:
            section_data[section_id] = parse_section_15(data, start, end, pointers)
        elif section_id == 18:
            lines, text_start = parse_section_18(data, start)
            section_data[section_id] = lines
    
    # 只保留文本区指针
    valid_pointers = {addr for addr in pointers if text_start <= addr < len(data)}
    
    # 提取文本（包含空串：指针有效但内容可能是 b''）
    text_list = []
    addr_to_line = {}

    for addr in sorted(valid_pointers):
        raw = read_raw_cstring(data, addr)
        # 不再跳过空串；空串也要登记为一条文本
        text = decode_text_bytes(raw)  # b'' 会返回 ""
        line_num = len(text_list) + 1
        addr_to_line[addr] = line_num
        text_list.append(text)
    
    if not text_list:
        print(f"  ℹ️  无文本")
        return False
    
    # 写ASM
    with open(output_asm, "w", encoding="utf-8") as f:
        f.write(f"# TEXT_COUNT: {len(text_list)}\n")
        f.write(f"# OFFSETS: {', '.join(map(str, offsets))}\n\n")
        
        for section_id, start, end in sections:
            f.write(f"# SECTION_{section_id:02d}\n")
            
            if section_id not in section_data:
                continue
            
            for item in section_data[section_id]:
                item_type = item[0]
                
                if item_type == 'type0':
                    vals = item[1]
                    parts = []
                    for i, v in enumerate(vals):
                        parts.append(f"@{addr_to_line[v]}" if i < 2 and v in addr_to_line else hex(v))
                    f.write(", ".join(parts) + "\n")
                
                elif item_type == 'type1':
                    vals = item[1]
                    parts = []
                    for i, v in enumerate(vals):
                        parts.append(f"@{addr_to_line[v]}" if i < 3 and v in addr_to_line else hex(v))
                    f.write(", ".join(parts) + "\n")
                
                elif item_type == 'type3':
                    v = item[1]
                    f.write(f"@{addr_to_line[v]}\n" if v in addr_to_line else f"{hex(v)}\n")
                
                elif item_type == 'type15':
                    vals = item[1]
                    p0 = f"@{addr_to_line[vals[0]]}" if vals[0] in addr_to_line else hex(vals[0])
                    f.write(f"{p0}, {hex(vals[1])}\n")
                
                elif item_type == 'type18':
                    v = item[1]
                    f.write(f"{hex(v)}\n")
                
                elif item_type == 'hex':
                    f.write(item[1].hex().upper() + "\n")
            
            f.write("\n")
    
    # 写TXT
    with open(output_txt, "w", encoding="utf-8") as f:
        for text in text_list:
            f.write(escape_for_txt(text) + "\n")
    
    print(f"  ✅ {len(text_list)} 个文本")
    return True

def encode_data_bin(input_asm, input_txt, output_file):
    """编码 DATA.BIN（严格使用 ASM 头部 # OFFSETS 中记录的原始分区偏移）"""
    import struct
    import os

    def pack_ptr_or_hex(token: str, text_addr: dict) -> bytes:
        if token.startswith("@"):
            if token in text_addr:
                return struct.pack('<I', text_addr[token])
            raise ValueError(f"未知文本引用: {token}")
        return struct.pack('<I', int(token, 16))

    # 读取 ASM
    with open(input_asm, "r", encoding="utf-8") as f:
        asm_lines = [line.rstrip("\r\n") for line in f]

    # 读取 TXT
    text_lines = []
    if os.path.exists(input_txt):
        with open(input_txt, "r", encoding="utf-8") as f:
            text_lines = [line.rstrip("\r\n") for line in f]

    # 解析 ASM 头部
    expected_text_count = 0
    original_offsets = []

    for line in asm_lines:
        s = line.strip()
        if s.startswith("# TEXT_COUNT:"):
            expected_text_count = int(s.split(":", 1)[1].strip())
        elif s.startswith("# OFFSETS:"):
            offset_str = s.split(":", 1)[1].strip()
            original_offsets = [int(x.strip()) for x in offset_str.split(",")]
            break

    if len(original_offsets) != 19:
        raise ValueError("ASM 头部缺少或未完整记录 19 个 OFFSETS")

    if expected_text_count != len(text_lines):
        print(f"  ❌ 文本数量不匹配 (声明:{expected_text_count}, 实际:{len(text_lines)})")
        return

    # 收集分区行
    section_data = {}
    current_section = None
    for line in asm_lines:
        s = line.strip()
        if s.startswith("# SECTION_"):
            section_id = int(s[10:12])
            current_section = section_id
            section_data[section_id] = []
            continue
        if s.startswith("#") or not s:
            continue
        if current_section is not None:
            section_data[current_section].append(s)

    # 计算各分区编码后大小（按分区定义）
    section_sizes = {}
    for section_id in range(19):
        if section_id not in section_data:
            continue
        lines = section_data[section_id]
        if section_id in [0, 17]:
            section_sizes[section_id] = len(lines) * 16      # 4*4B
        elif section_id == 1:
            section_sizes[section_id] = len(lines) * 20      # 5*4B
        elif section_id in [3, 8, 14, 16]:
            section_sizes[section_id] = len(lines) * 4       # 1*4B
        elif section_id == 15:
            section_sizes[section_id] = len(lines) * 8       # 2*4B
        elif section_id == 18:
            section_sizes[section_id] = len(lines) * 4       # 1*4B
        elif section_id in [2, 4, 5, 6, 7, 9, 10, 11, 12, 13]:
            hex_str = lines[0] if lines else ""
            section_sizes[section_id] = len(bytes.fromhex(hex_str))
        else:
            # 默认按 4 字节对齐的未识别类型（通常不会走到）
            section_sizes[section_id] = sum(len(x) for x in lines)

    # 用原 OFFSETS 计算每个分区的容量（capacity = next_offset - this_offset）
    active_offsets = [(sid, original_offsets[sid]) for sid in range(19) if original_offsets[sid] >= 76]
    active_offsets.sort(key=lambda x: x[1])

    next_ofs_by_sid = {}
    for i, (sid, ofs) in enumerate(active_offsets):
        nxt = active_offsets[i + 1][1] if i + 1 < len(active_offsets) else None
        next_ofs_by_sid[sid] = nxt

    # text_start = 所有“会写出的分区”的 (offset + 新大小) 的最大值
    text_start = 76
    for sid, ofs in active_offsets:
        if sid in section_sizes:
            text_start = max(text_start, ofs + section_sizes[sid])

    # 建立文本地址映射（从 text_start 开始依次放置）
    def unescape_from_txt(s: str) -> str:
        out = []
        i = 0
        while i < len(s):
            ch = s[i]
            if ch == "\\" and i + 1 < len(s):
                n = s[i + 1]
                if n == "n": out.append("\n"); i += 2; continue
                elif n == "r": out.append("\r"); i += 2; continue
                elif n == "t": out.append("\t"); i += 2; continue
                elif n == "\\": out.append("\\"); i += 2; continue
            out.append(ch); i += 1
        return "".join(out)

    text_data = bytearray()
    text_addr = {}
    for i, line in enumerate(text_lines, 1):
        text_addr[f"@{i}"] = text_start + len(text_data)
        raw = unescape_from_txt(line).encode('cp932', 'ignore')
        text_data.extend(raw)
        text_data.append(0)
    # 可选：仍然支持 @0 代表空指针（不常用）
    text_addr["@0"] = 0

    # 先编码各分区为 bytes，方便做容量检查
    def build_section_bytes(section_id, lines, text_addr):
        import struct
        out = bytearray()
        if section_id in [0, 17]:
            # 4*4 字节，前2个是指针
            for line in lines:
                parts = [p.strip() for p in line.split(",")]
                for i, p in enumerate(parts):
                    if i < 2:
                        out += pack_ptr_or_hex(p, text_addr)
                    else:
                        out += struct.pack('<I', int(p, 16))
        elif section_id == 1:
            # 5*4 字节，前3个是指针
            for line in lines:
                parts = [p.strip() for p in line.split(",")]
                for i, p in enumerate(parts):
                    if i < 3:
                        out += pack_ptr_or_hex(p, text_addr)
                    else:
                        out += struct.pack('<I', int(p, 16))
        elif section_id in [3, 8, 14, 16]:
            # 1*4 字节，可能是指针
            for line in lines:
                p = line.strip()
                out += pack_ptr_or_hex(p, text_addr)
        elif section_id == 15:
            # 2*4 字节，第1个是指针
            for line in lines:
                parts = [p.strip() for p in line.split(",")]
                out += pack_ptr_or_hex(parts[0], text_addr)
                out += struct.pack('<I', int(parts[1], 16))
        elif section_id == 18:
            # 1*4 字节（原样数值）
            for line in lines:
                out += struct.pack('<I', int(line.strip(), 16))
        elif section_id in [2, 4, 5, 6, 7, 9, 10, 11, 12, 13]:
            # hex 数据
            hex_str = lines[0] if lines else ""
            out += bytes.fromhex(hex_str)
        else:
            # 未覆盖类型：逐行按 32 位数值
            for line in lines:
                out += struct.pack('<I', int(line.strip(), 16))
        return bytes(out)

    section_bytes = {}
    for sid in section_data.keys():
        section_bytes[sid] = build_section_bytes(sid, section_data[sid], text_addr)
        # 安全：长度应与预估一致
        if len(section_bytes[sid]) != section_sizes[sid]:
            raise ValueError(f"分区 {sid} 大小不一致：预估 {section_sizes[sid]} 实际 {len(section_bytes[sid])}")

    # 容量检查（固定布局）
    for sid, ofs in active_offsets:
        if sid in section_bytes:
            nxt = next_ofs_by_sid.get(sid)
            cap = (nxt - ofs) if nxt is not None else None
            need = len(section_bytes[sid])
            if cap is not None and need > cap:
                raise ValueError(
                    f"分区 {sid} 超出原容量: 需要 {need} 字节, 容量 {cap} 字节 "
                    f"(offset=0x{ofs:X}, next=0x{nxt:X})。请缩短内容或改用“重打包模式”。"
                )

    # 构建输出：按原 OFFSETS 写入
    final_size = text_start + len(text_data)
    outdata = bytearray(final_size)  # 默认零填充

    # 写入 19 个偏移量（使用原值）
    import struct
    for ofs in original_offsets:
        outdata.extend(b"")  # 无操作，只是占位提示
    outdata[:76] = b"".join(struct.pack("<I", x) for x in original_offsets)

    # 写入每个分区到固定 offset
    for sid, ofs in active_offsets:
        if sid in section_bytes:
            blob = section_bytes[sid]
            end = ofs + len(blob)
            if end > len(outdata):
                outdata.extend(b"\x00" * (end - len(outdata)))
            outdata[ofs:end] = blob

    # 写入文本区
    if text_start > len(outdata):
        outdata.extend(b"\x00" * (text_start - len(outdata)))
    outdata[text_start:text_start + len(text_data)] = text_data

    # 写文件
    with open(output_file, "wb") as f:
        f.write(outdata)

    print(f"  ✅ 输出 {len(outdata)} 字节（使用原 OFFSETS 固定布局，text_start=0x{text_start:X}）")

def process_folder(input_folder, output_folder, mode):
    """批量处理"""
    Path(output_folder).mkdir(parents=True, exist_ok=True)
    
    processed = []
    skipped = []
    errors = []
    
    for root, dirs, files in os.walk(input_folder):
        rel_path = os.path.relpath(root, input_folder)
        if rel_path == ".":
            rel_path = ""
        
        out_dir = Path(output_folder) / rel_path
        out_dir.mkdir(parents=True, exist_ok=True)
        
        for filename in files:
            input_path = Path(root) / filename
            
            if mode == 'd' and filename.upper() == "DATA.BIN":
                base = filename[:-4]
                out_asm = out_dir / f"{base}.asm"
                out_txt = out_dir / f"{base}.txt"
                
                display = str(Path(rel_path) / filename) if rel_path else filename
                print(f"\n解码: {display}")
                
                try:
                    if decode_data_bin(str(input_path), str(out_asm), str(out_txt)):
                        processed.append(display)
                    else:
                        skipped.append(display)
                except Exception as e:
                    print(f"  ❌ 错误: {e}")
                    errors.append((display, str(e)))
            
            elif mode == 'e' and filename.lower().endswith(".asm"):
                base = filename[:-4]
                in_txt = Path(root) / f"{base}.txt"
                out_bin = out_dir / "DATA.BIN"
                
                if not in_txt.exists():
                    continue
                
                display = str(Path(rel_path) / filename) if rel_path else filename
                print(f"\n编码: {display}")
                
                try:
                    encode_data_bin(str(input_path), str(in_txt), str(out_bin))
                    processed.append(display)
                except Exception as e:
                    print(f"  ❌ 错误: {e}")
                    errors.append((display, str(e)))
    
    # 统计
    print(f"\n{'='*60}")
    print(f"📊 统计: ✅ {len(processed)} | ⊘ {len(skipped)} | ❌ {len(errors)}")
    print(f"{'='*60}")
    
    if processed:
        print(f"\n✅ 成功:")
        for f in processed:
            print(f"  • {f}")
    
    if skipped:
        print(f"\n⊘ 跳过:")
        for f in skipped:
            print(f"  • {f}")
    
    if errors:
        print(f"\n❌ 错误:")
        for f, err in errors:
            print(f"  • {f}: {err}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DATA.BIN 处理工具")
    parser.add_argument("mode", choices=["d", "e"], help="d=解码, e=编码")
    parser.add_argument("input", help="输入文件夹")
    parser.add_argument("output", help="输出文件夹")
    args = parser.parse_args()
    
    print(f"\nDATA.BIN 工具 - {'解码' if args.mode == 'd' else '编码'} 模式\n")
    process_folder(args.input, args.output, args.mode)
    print(f"\n{'='*60}")
    print("✅ 完成\n")