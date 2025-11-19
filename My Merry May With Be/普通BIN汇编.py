import struct
import os
import argparse
import re

# 只用你的映射表（指令: 文本参数索引，从0开始；可为列表）
TEXT_PARAM_MAP = {
    0x18: [2],
    0xD8: [0],
    0x24: [0],
    0x1E: [0],
    0x1B: "dynamic_options"
}

TERMINATOR_LEN = 0xA

skip = {
    "INIT.BIN",
    "DBG02.BIN",
    "DBG03.BIN",
    "DMENU.BIN",
    "DMENU2.BIN",
    "DMENU4.BIN",
    "DMENU5.BIN",
    "DMENU6.BIN",
    "SHORTCUT.BIN",
    "DATA.BIN"
}

# ---------- 工具 ----------

def check_terminator(data: bytes, offset: int) -> bool:
    if offset + TERMINATOR_LEN > len(data):
        return False
    return all(b == 0 for b in data[offset:offset + TERMINATOR_LEN])

def read_raw_cstring(data: bytes, offset: int) -> bytes:
    if offset >= len(data):
        return b""
    end = offset
    while end < len(data) and data[end] != 0:
        end += 1
    return data[offset:end]

def decode_text_bytes(raw: bytes) -> str:
    if not raw:
        return ""
    try:
        return raw.decode('cp932')
    except UnicodeDecodeError:
        return "<HEX:" + raw.hex().upper() + ">"

def escape_for_txt(s: str) -> str:
    return s.replace("\\", "\\\\").replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")

def unescape_from_txt(s: str) -> str:
    out = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s):
            n = s[i + 1]
            if n == "n":
                out.append("\n"); i += 2; continue
            elif n == "r":
                out.append("\r"); i += 2; continue
            elif n == "t":
                out.append("\t"); i += 2; continue
            elif n == "\\":
                out.append("\\"); i += 2; continue
        out.append(ch); i += 1
    return "".join(out)

HEX_PLACEHOLDER_RE = re.compile(r"^<HEX:([0-9A-Fa-f]+)>$")

def encode_text_line_to_bytes(line: str) -> bytes:
    s = unescape_from_txt(line)
    m = HEX_PLACEHOLDER_RE.match(s)
    if m:
        hx = m.group(1)
        if len(hx) % 2 != 0:
            raise ValueError(f"HEX 长度不是偶数: {s}")
        return bytes.fromhex(hx)
    try:
        return s.encode('cp932', 'ignore')
    except UnicodeEncodeError:
        print(f"警告: 文本含不可 cp932 编码字符，已以 '?' 代替。原文: {s!r}")
        return s.encode('cp932', 'replace')

# ---------- 解码 ----------

def decode_script(input_file, output_asm, output_txt):
    with open(input_file, "rb") as f:
        data = f.read()

    filename = os.path.basename(input_file)

    if filename in skip:
        return    
    
    # 读取脚本起始位置（跳过文件头）
    script_start = struct.unpack('<H', data[0:2])[0]

    header = data[0:script_start]

    # 找指令区结束
    offset = script_start
    inst_end = offset
    while offset < len(data):
        if offset + 2 > len(data):
            break
        
        inst_type = data[offset]
        inst_len = data[offset + 1]
        
        # 只判断当前指令是否为 0x0D（结束命令）
        if inst_type == 0x0D and inst_len == 2:
            inst_end = offset + inst_len  # 包含 0x0D 指令本身
            break
        
        if inst_len == 0 or offset + inst_len > len(data):
            break
            
        offset += inst_len
        inst_end = offset

    text_start = inst_end

    # 解析指令 + 抽取文本
    text_list = []
    addr_to_id = {}
    extracted_addrs = set()  # 记录被提取的文本地址
    lines_out = []

    offset = script_start
    count = 0
    while offset < inst_end:
        if check_terminator(data, offset) or offset + 2 > len(data):
            break

        inst_type = data[offset]
        inst_len = data[offset + 1]
        if inst_len == 0 or offset + inst_len > len(data):
            break

        # 解析参数（2字节对齐），剩余为 EXTRA
        params = []
        pos = offset + 2
        while pos + 2 <= offset + inst_len:
            params.append(struct.unpack('<H', data[pos:pos+2])[0])
            pos += 2
        tail = data[pos:offset + inst_len]

        output_params = [None] * len(params)

        # 仅按表替换为 @ID
        if inst_type in TEXT_PARAM_MAP and params:
            idxs = TEXT_PARAM_MAP[inst_type]
            if isinstance(idxs, int):
                idxs = [idxs]
            
            # 在这里添加对 0x1B 的特殊处理
            if inst_type == 0x1B and len(params) > 0:
                # 0x1B 指令的特殊处理：参数0是选项数量
                option_count = params[0]
                # 使用公式 4*选项索引-1 计算文本参数位置
                for option_index in range(option_count):
                    param_position = 4 * option_index + 3
                    if 0 <= param_position < len(params):
                        addr = params[param_position]
                        if text_start <= addr < len(data):
                            raw = read_raw_cstring(data, addr)
                            text = decode_text_bytes(raw)
                            if addr not in addr_to_id:
                                addr_to_id[addr] = len(text_list) + 1
                                text_list.append(text)
                                extracted_addrs.add(addr)
                            output_params[param_position] = f"@{addr_to_id[addr]}"
            else:
                # 原来的处理逻辑（其他指令）
                for i in idxs:
                    if 0 <= i < len(params):
                        addr = params[i]
                        if text_start <= addr < len(data):
                            raw = read_raw_cstring(data, addr)
                            text = decode_text_bytes(raw)
                            if addr not in addr_to_id:
                                addr_to_id[addr] = len(text_list) + 1
                                text_list.append(text)
                                extracted_addrs.add(addr)
                            output_params[i] = f"@{addr_to_id[addr]}"

        # 其他参数原样
        for i, p in enumerate(params):
            if output_params[i] is None:
                output_params[i] = f"0x{p:04X}"

        # 输出行
        if output_params:
            line = f"0x{inst_type:02X}: " + ", ".join(output_params)
        else:
            line = f"0x{inst_type:02X}"
        if tail:
            line += f" | EXTRA={tail.hex()}"
        lines_out.append(line)

        offset += inst_len
        count += 1

    # 扫描文本区所有文本（用00分割）
    all_text_addrs = []
    current_addr = text_start
    while current_addr < len(data):
        if data[current_addr] == 0:
            current_addr += 1
            continue
            
        # 找到字符串起始位置
        start_addr = current_addr
        raw = read_raw_cstring(data, start_addr)
        if raw:  # 非空字符串
            text = decode_text_bytes(raw)
            all_text_addrs.append((start_addr, text, raw))
            current_addr = start_addr + len(raw) + 1  # 跳过字符串和终止符
        else:
            current_addr += 1

    # 找出未提取的文本
    unextracted_texts = []
    for addr, text, raw in all_text_addrs:
        if addr not in extracted_addrs:
            unextracted_texts.append((addr, text, raw))

    if len(unextracted_texts) > 0 and len(text_list) < 0:
        # 写日志文件（记录未提取的文本）
        log_file = output_txt.replace('.txt', '_unextracted.log')
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(hex(current_addr) + "\n\n")
            f.write(f"未提取的文本列表 (共 {len(unextracted_texts)} 个)\n")
            f.write("=" * 60 + "\n")
            for addr, text, raw in unextracted_texts:
                escaped_text = escape_for_txt(text)
                hex_representation = raw.hex().upper()
                f.write(f"地址: 0x{addr:04X}\n")
                f.write(f"文本: {escaped_text}\n")
                f.write(f"HEX : {hex_representation}\n")
                f.write("-" * 40 + "\n")
        print(f"未提取文本: {len(unextracted_texts)} 个，已保存到 {log_file}")        

    if len(text_list) > 0:
        print(f"\n解码: {filename}")
        # 写 ASM
        with open(output_asm, "w", encoding="utf-8") as out:
            out.write(f"# TEXT_COUNT: {len(text_list)}\n")
            out.write("# HEADER\n")
            out.write(header.hex() + "\n")
            out.write("# SCRIPT\n")
            for line in lines_out:
                out.write(line + "\n")
        print(f"输出: {output_asm}, {output_txt}")        

    # 写 TXT

        with open(output_txt, "w", encoding="utf-8") as out:
            for t in text_list:
                out.write(escape_for_txt(t) + "\n")

        print(f"完成！共 {count} 条指令，{len(text_list)} 个文本")
    
    

# ---------- 编码 ----------

def encode_script(input_asm, input_txt, output_file):
    with open(input_asm, "r", encoding="utf-8") as f:
        asm_lines = [line.rstrip("\r\n") for line in f]

    txt_lines = []
    if os.path.exists(input_txt):
        with open(input_txt, "r", encoding="utf-8") as f:
            txt_lines = [line.rstrip("\r\n") for line in f]

    header_bytes = None
    script_lines = []
    expected_text_count = 0
    section = None

    for line in asm_lines:
        s = line.strip()
        if s.startswith("# TEXT_COUNT:"):
            try:
                expected_text_count = int(s.split(":", 1)[1].strip())
            except Exception:
                expected_text_count = 0
            continue
        if s == "# HEADER":
            section = "header"; continue
        if s == "# SCRIPT":
            section = "script"; continue
        if s.startswith("#") or not s:
            continue

        if section == "header":
            header_bytes = bytes.fromhex(s)
        elif section == "script":
            script_lines.append(s)

    if header_bytes is None:
        print("错误: 未找到文件头 (# HEADER 段)")
        return

    if expected_text_count != len(txt_lines):
        print("错误: 文本数量不匹配！")
        print(f"  ASM声明: {expected_text_count}")
        print(f"  TXT实际: {len(txt_lines)}")
        return

    # 第一遍：解析指令、提取 EXTRA、统计长度
    temp = []
    total_inst_size = 0

    for line in script_lines:
        # 去掉 // 注释
        if "//" in line:
            line = line.split("//", 1)[0].strip()
        if not line:
            continue

        if ":" in line:
            inst_part, rest = line.split(":", 1)
            inst_part = inst_part.strip()
            rest = rest.strip()
        else:
            inst_part = line.strip()
            rest = ""

        # EXTRA
        extra_hex = ""
        params_part = rest
        if "|" in rest:
            params_part, meta = rest.split("|", 1)
            m = re.search(r"EXTRA=([0-9A-Fa-f]+)", meta.strip())
            if m:
                extra_hex = m.group(1)

        params = []
        if params_part:
            params = [p.strip() for p in params_part.split(",") if p.strip()]

        tail_bytes = bytes.fromhex(extra_hex) if extra_hex else b""

        # 指令码
        if inst_part.lower().startswith("0x"):
            try:
                inst_type = int(inst_part, 16)
            except Exception:
                inst_type = 0
        else:
            inst_type = 0

        inst_len = 2 + len(params) * 2 + len(tail_bytes)
        temp.append((inst_type, params, tail_bytes, inst_len))
        total_inst_size += inst_len

    # 文本区与地址表
    header_len = len(header_bytes)
    text_start = header_len + total_inst_size + TERMINATOR_LEN

    text_data = bytearray()
    text_addr = {}
    for i, line in enumerate(txt_lines, 1):
        text_addr[f"@{i}"] = text_start + len(text_data)
        raw = encode_text_line_to_bytes(line)
        text_data.extend(raw)
        text_data.append(0)

    # 写回
    outdata = bytearray(header_bytes)

    for inst_type, params, tail_bytes, inst_len in temp:
        outdata.append(inst_type & 0xFF)
        outdata.append(inst_len & 0xFF)

        for p in params:
            if p.startswith("@") and p[1:].isdigit():
                addr = text_addr.get(p, 0)
                outdata.extend(struct.pack('<H', addr & 0xFFFF))
            elif p.lower().startswith("0x"):
                try:
                    val = int(p, 16)
                except Exception:
                    val = 0
                outdata.extend(struct.pack('<H', val & 0xFFFF))
            else:
                outdata.extend(struct.pack('<H', 0))

        if tail_bytes:
            outdata.extend(tail_bytes)

    outdata.extend(b"\x00" * TERMINATOR_LEN)
    outdata.extend(text_data)

    with open(output_file, "wb") as f:
        f.write(outdata)

    #print(f"编码完成: {output_file}, 大小: {len(outdata)} 字节")
    #print(f"  指令区: 0x{header_len:X}-0x{header_len + total_inst_size:X}")
    #print(f"  文本区: 0x{text_start:X}-0x{len(outdata):X}")

# ---------- 批处理 ----------

def process_folder(input_folder, output_folder, mode):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # 使用 os.walk 递归遍历所有子文件夹
    for root, dirs, files in os.walk(input_folder):
        # 计算相对于输入文件夹的相对路径
        rel_path = os.path.relpath(root, input_folder)
        if rel_path == ".":
            rel_path = ""
        
        # 创建对应的输出子文件夹
        output_subfolder = os.path.join(output_folder, rel_path)
        if not os.path.exists(output_subfolder):
            os.makedirs(output_subfolder)

        for filename in files:
            input_path = os.path.join(root, filename)
            
            if mode == 'd' and filename.upper().endswith(".BIN"):
                base = filename[:-4]
                out_asm = os.path.join(output_subfolder, base + ".asm")
                out_txt = os.path.join(output_subfolder, base + ".txt")
                print(f"\n解码: {os.path.join(rel_path, filename)}")
                try:
                    decode_script(input_path, out_asm, out_txt)
                except Exception as e:
                    print(f"错误: 处理文件 {filename} 时发生异常: {e}")
                    
            elif mode == 'e' and filename.lower().endswith(".asm"):
                base = filename[:-4]
                in_txt = os.path.join(root, base + ".txt")
                out_bin = os.path.join(output_subfolder, base + ".BIN")
                if not os.path.exists(in_txt):
                    print(f"警告: 未找到对应的 {os.path.join(rel_path, base + '.txt')}，跳过")
                    continue
                print(f"\n编码: {os.path.join(rel_path, filename)}")
                try:
                    encode_script(input_path, in_txt, out_bin)
                except Exception as e:
                    print(f"错误: 处理文件 {filename} 时发生异常: {e}")

# ---------- CLI ----------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="脚本编解码工具（极简：仅按映射表抓文本，保留EXTRA，可逆TXT）")
    parser.add_argument("mode", choices=["d", "e"], help="d=解码, e=编码")
    parser.add_argument("input", help="输入文件夹")
    parser.add_argument("output", help="输出文件夹")
    args = parser.parse_args()
    process_folder(args.input, args.output, args.mode)