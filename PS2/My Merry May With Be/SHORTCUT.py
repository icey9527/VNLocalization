import struct
import os
import argparse

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
        out.append(ch); i += 1
    return "".join(out)

def decode_shortcut(input_file, output_asm, output_txt):
    """解码 SHORTCUT.BIN"""
    with open(input_file, "rb") as f:
        data = f.read()
    
    # 读取指令区地址
    script_start = struct.unpack('<H', data[2:4])[0]
    
    # 解析分块区
    block_data = []
    offset = 4
    while offset + 0x120 <= script_start:
        block_values = []
        for i in range(0, 0x120, 2):
            val = struct.unpack('<H', data[offset+i:offset+i+2])[0]
            block_values.append(val)
        block_data.append(block_values)
        offset += 0x120
    
    # 找指令区结束
    offset = script_start
    inst_end = offset
    while offset < len(data):
        if offset + 2 > len(data):
            break
        inst_type = data[offset]
        inst_len = data[offset + 1]
        if inst_type == 0x0D and inst_len == 2:
            inst_end = offset + inst_len
            break
        if inst_len == 0 or offset + inst_len > len(data):
            break
        offset += inst_len
        inst_end = offset
    
    text_start = inst_end
    
    # 提取文本：从分块区的位置7和8
    text_list = []
    addr_to_id = {}
    
    for block_values in block_data:
        for pos_idx in [7, 8]:
            if pos_idx < len(block_values):
                addr = block_values[pos_idx]
                if text_start <= addr < len(data):
                    raw = read_raw_cstring(data, addr)
                    if raw:
                        text = decode_text_bytes(raw)
                        if addr not in addr_to_id:
                            addr_to_id[addr] = len(text_list) + 1
                            text_list.append(text)
    
    # 构建分块区header（标记@ID）
    block_lines = []
    for block_values in block_data:
        formatted = []
        for val in block_values:
            if val in addr_to_id:
                formatted.append(f"@{addr_to_id[val]}")
            else:
                formatted.append(f"0x{val:04X}")
        block_lines.append(", ".join(formatted))
    
    # 解析指令区
    lines_out = []
    offset = script_start
    count = 0
    while offset < inst_end:
        if offset + 2 > len(data):
            break
        inst_type = data[offset]
        inst_len = data[offset + 1]
        if inst_len == 0 or offset + inst_len > len(data):
            break
        
        params = []
        pos = offset + 2
        while pos + 2 <= offset + inst_len:
            params.append(struct.unpack('<H', data[pos:pos+2])[0])
            pos += 2
        tail = data[pos:offset + inst_len]
        
        output_params = [f"0x{p:04X}" for p in params]
        
        if output_params:
            line = f"0x{inst_type:02X}: " + ", ".join(output_params)
        else:
            line = f"0x{inst_type:02X}"
        if tail:
            line += f" | EXTRA={tail.hex()}"
        lines_out.append(line)
        
        offset += inst_len
        count += 1
    
    # 写ASM
    with open(output_asm, "w", encoding="utf-8") as out:
        out.write(f"# TEXT_COUNT: {len(text_list)}\n")
        out.write("# HEADER\n")
        out.write("SHORTCUT\n")
        for line in block_lines:
            out.write(line + "\n")
        out.write("# SCRIPT\n")
        for line in lines_out:
            out.write(line + "\n")
    
    # 写TXT
    with open(output_txt, "w", encoding="utf-8") as out:
        for text in text_list:
            out.write(escape_for_txt(text) + "\n")
    
    print(f"  完成: {len(text_list)} 个文本, {count} 条指令")

def encode_shortcut(input_asm, input_txt, output_file):
    """编码 SHORTCUT.BIN"""
    with open(input_asm, "r", encoding="utf-8") as f:
        asm_lines = [line.rstrip("\r\n") for line in f]
    
    text_lines = []
    if os.path.exists(input_txt):
        with open(input_txt, "r", encoding="utf-8") as f:
            text_lines = [line.rstrip("\r\n") for line in f]
    
    # 解析ASM
    header_lines = []
    script_lines = []
    expected_text_count = 0
    section = None
    
    for line in asm_lines:
        s = line.strip()
        if s.startswith("# TEXT_COUNT:"):
            expected_text_count = int(s.split(":", 1)[1].strip())
            continue
        if s == "# HEADER":
            section = "header"; continue
        if s == "# SCRIPT":
            section = "script"; continue
        if s.startswith("#") or not s:
            continue
        
        if section == "header":
            header_lines.append(s)
        elif section == "script":
            script_lines.append(s)
    
    if expected_text_count != len(text_lines):
        print(f"错误: 文本数量不匹配 (声明:{expected_text_count}, 实际:{len(text_lines)})")
        return
    
    # 解析分块数据
    block_data = []
    for line in header_lines:
        if line == "SHORTCUT":
            continue
        parts = [p.strip() for p in line.split(",")]
        block_values = []
        for p in parts:
            if p.startswith("@"):
                block_values.append(p)
            else:
                block_values.append(int(p, 16))
        block_data.append(block_values)
    
    # 解析指令
    temp_inst = []
    total_inst_size = 0
    
    for line in script_lines:
        if "//" in line:
            line = line.split("//", 1)[0].strip()
        if not line:
            continue
        
        if ":" in line:
            inst_part, rest = line.split(":", 1)
        else:
            inst_part = line.strip()
            rest = ""
        
        extra_hex = ""
        params_part = rest.strip()
        if "|" in params_part:
            params_part, meta = params_part.split("|", 1)
            import re
            m = re.search(r"EXTRA=([0-9A-Fa-f]+)", meta.strip())
            if m:
                extra_hex = m.group(1)
        
        params = [p.strip() for p in params_part.split(",") if p.strip()] if params_part else []
        tail_bytes = bytes.fromhex(extra_hex) if extra_hex else b""
        inst_type = int(inst_part.strip(), 16)
        inst_len = 2 + len(params) * 2 + len(tail_bytes)
        
        temp_inst.append((inst_type, params, tail_bytes, inst_len))
        total_inst_size += inst_len
    
    # 计算地址
    block_area_size = len(block_data) * 0x120
    script_start = 4 + block_area_size + 0x7C
    text_start = script_start + total_inst_size
    
    # 编码文本
    text_data = bytearray()
    text_addr = {}
    for i, line in enumerate(text_lines, 1):
        text_addr[f"@{i}"] = text_start + len(text_data)
        raw = unescape_from_txt(line).encode('cp932', 'ignore')
        text_data.extend(raw)
        text_data.append(0)
    
    # 构建输出
    outdata = bytearray()
    outdata.extend(b'\x01\x00')
    outdata.extend(struct.pack('<H', script_start))
    
    # 写分块数据
    for block_values in block_data:
        for val in block_values:
            if isinstance(val, str) and val.startswith("@"):
                addr = text_addr.get(val, 0)
                outdata.extend(struct.pack('<H', addr))
            else:
                outdata.extend(struct.pack('<H', val))
    
    # 填充0x7C
    outdata.extend(b'\x00' * 0x7C)
    
    # 写指令
    for inst_type, params, tail_bytes, inst_len in temp_inst:
        outdata.append(inst_type & 0xFF)
        outdata.append(inst_len & 0xFF)
        for p in params:
            if p.startswith("@"):
                addr = text_addr.get(p, 0)
                outdata.extend(struct.pack('<H', addr))
            else:
                outdata.extend(struct.pack('<H', int(p, 16)))
        if tail_bytes:
            outdata.extend(tail_bytes)
    
    # 写文本
    outdata.extend(text_data)
    
    with open(output_file, "wb") as f:
        f.write(outdata)
    
    print(f"  完成: {len(outdata)} 字节")

def process_folder(input_folder, output_folder, mode):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    for root, dirs, files in os.walk(input_folder):
        rel_path = os.path.relpath(root, input_folder)
        if rel_path == ".":
            rel_path = ""
        
        output_subfolder = os.path.join(output_folder, rel_path)
        if not os.path.exists(output_subfolder):
            os.makedirs(output_subfolder)
        
        for filename in files:
            input_path = os.path.join(root, filename)
            
            if mode == 'd' and filename.upper() == "SHORTCUT.BIN":
                base = filename[:-4]
                out_asm = os.path.join(output_subfolder, base + ".asm")
                out_txt = os.path.join(output_subfolder, base + ".txt")
                print(f"\n解码: {os.path.join(rel_path, filename)}")
                try:
                    decode_shortcut(input_path, out_asm, out_txt)
                except Exception as e:
                    print(f"  错误: {e}")
                    import traceback
                    traceback.print_exc()
            
            elif mode == 'e' and filename.lower().endswith(".asm"):
                base = filename[:-4]
                if base.upper() == "SHORTCUT":
                    in_txt = os.path.join(root, base + ".txt")
                    out_bin = os.path.join(output_subfolder, base + ".BIN")
                    if not os.path.exists(in_txt):
                        print(f"  警告: 未找到 {base}.txt，跳过")
                        continue
                    print(f"\n编码: {os.path.join(rel_path, filename)}")
                    try:
                        encode_shortcut(input_path, in_txt, out_bin)
                    except Exception as e:
                        print(f"  错误: {e}")
                        import traceback
                        traceback.print_exc()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SHORTCUT.BIN 批量处理工具")
    parser.add_argument("mode", choices=["d", "e"], help="d=解码, e=编码")
    parser.add_argument("input", help="输入文件夹")
    parser.add_argument("output", help="输出文件夹")
    args = parser.parse_args()
    
    process_folder(args.input, args.output, args.mode)