import struct
import csv
import re
from pathlib import Path
from collections import defaultdict
from typing import List, Tuple, Dict

# 中日文检测正则（预编译）
CJK_PATTERN = re.compile(r'[\u4e00-\u9fff\u3040-\u30ff\u31f0-\u31ff]')

# 命令字典
COMMAND_DICT = {
    b'\x01\x06': 6,
    b'\x00\x06': 6,
    b'\x10\x07': 2,
    b'\x00\x02': 8,
    b'\x08\x00': 10,
    b'\x11\x00': 6,
}

def check_has_text(data: bytes) -> Tuple[bool, str]:
    """检查数据中是否包含中日文文本（优化版）"""
    if len(data) < 6:
        return False, ""
    
    try:
        # 直接解码，减少中间步骤
        decoded = data.decode('utf-16-le', errors='ignore')
        
        # 先检查是否有CJK字符（最快的筛选）
        if not CJK_PATTERN.search(decoded):
            return False, ""
        
        # 只在有CJK时才过滤字符
        readable = ''.join(c for c in decoded if c.isprintable() or c in '\n\r\t')
        
        if len(readable.strip()) >= 3:
            # 使用切片避免多次字符串操作
            preview = readable[:60].replace('\n', '\\n').replace('\r', '\\r')
            if len(readable) > 60:
                preview += '...'
            return True, preview
    except:
        pass
    
    return False, ""

def decode_text(data: bytes) -> str:
    """解码UTF-16 LE文本（优化版）"""
    if not data:
        return ""
    
    # 使用列表收集，最后一次性join
    result = []
    i = 0
    data_len = len(data)
    
    while i < data_len - 1:  # 确保至少有2字节
        two_bytes = data[i:i+2]
        
        try:
            char = two_bytes.decode('utf-16-le', errors='strict')
            
            # 使用字典映射替代多个if-elif
            if char == '\x00':
                remaining_data = data[i+2:]
                has_more, preview = check_has_text(remaining_data)
                if has_more:
                    print(f"警告: 在00后发现更多文本: {preview}")
                                
                break
            elif char == '\n':
                result.append('\\n')
            elif char == '\r':
                result.append('\\r')
            elif char == '\t':
                result.append('\\t')
            elif ord(char) < 0x20 or ord(char) == 0x7F:
                result.append(f'<{two_bytes[0]:02X}{two_bytes[1]:02X}>')
            else:
                result.append(char)
        except:
            result.append(f'<{two_bytes[0]:02X}{two_bytes[1]:02X}>')
        
        i += 2
    
    return ''.join(result)

def parse_index_table(data: bytes, index_start: int, count: int, base_address: int) -> List[Tuple[int, int]]:
    """
    预解析索引表，返回排序后的 (section_id, absolute_address) 列表
    优化点：一次性读取所有索引，避免重复计算
    """
    addresses = []
    
    for i in range(count):
        offset = index_start + i * 4
        if offset + 4 > len(data):
            continue
        
        relative_addr = struct.unpack('<I', data[offset:offset+4])[0]
        absolute_addr = base_address + relative_addr
        
        if absolute_addr < len(data):
            addresses.append((i, absolute_addr))
    
    # 按地址排序
    addresses.sort(key=lambda x: x[1])
    return addresses

def analyze_sections(file_path: Path) -> Tuple[List[Tuple[int, str]], List[Dict]]:
    """分析文件中的所有区段（优化版）"""
    texts = []
    unknown_commands = []
    
    with open(file_path, 'rb') as f:
        data = f.read()
    
    data_len = len(data)
    if data_len < 0x18:
        return texts, unknown_commands
    
    # 一次性解析头部
    section_size = struct.unpack('<I', data[0x10:0x14])[0]
    count = struct.unpack('<I', data[0x14:0x18])[0]
    index_start = 0x30 + section_size
    base_address = index_start + (count * 4)
    
    # 预解析并排序索引表
    sorted_addresses = parse_index_table(data, index_start, count, base_address)
    
    # 预计算每个section的结束地址
    section_ranges = []
    for idx, (section_id, start_addr) in enumerate(sorted_addresses):
        # 下一个section的起始地址就是当前section的结束地址
        end_addr = sorted_addresses[idx + 1][1] if idx + 1 < len(sorted_addresses) else data_len
        section_ranges.append((section_id, start_addr, end_addr))
    
    # 处理每个section
    for section_id, start_addr, end_addr in section_ranges:
        if start_addr + 2 > data_len:
            continue
        
        command = data[start_addr:start_addr+2]
        section_data = data[start_addr:end_addr]
        
        if command in COMMAND_DICT:
            header_len = COMMAND_DICT[command]
            
            if len(section_data) > header_len:
                text_data = section_data[header_len:]
                decoded_text = decode_text(text_data)
                
                if decoded_text.strip():
                    texts.append((section_id + 1, decoded_text)) 
        else:
            # 只在启用检查时才检测未知命令
            has_text, preview = check_has_text(section_data)
            
            if has_text:
                # 优化hex转换
                header_bytes = section_data[:min(16, len(section_data))]
                header_preview = ' '.join(f'{b:02X}' for b in header_bytes)
                
                unknown_commands.append({
                    'section_id': section_id + 1,
                    'command': command.hex().upper(),
                    'address': f'0x{start_addr:X}',
                    'size': len(section_data),
                    'header': header_preview,
                    'preview': preview
                })
    
    return texts, unknown_commands

def process_folder(folder_path: str, output_folder: str = None, enable_unknown_check: bool = False):
    """处理文件夹中的所有.adb文件"""
    folder = Path(folder_path)
    
    if not folder.exists():
        print(f"错误: 文件夹不存在 {folder_path}")
        return
    
    out_folder = Path(output_folder) if output_folder else folder / "extracted_texts"
    out_folder.mkdir(exist_ok=True)
    
    adb_files = list(folder.glob("*.adb"))
    
    if not adb_files:
        print(f"未找到.adb文件: {folder_path}")
        return
    
    print(f"找到 {len(adb_files)} 个.adb文件")
    print("=" * 60)
    
    total_texts = 0
    all_unknown_commands = defaultdict(list)
    
    for adb_file in adb_files:
        print(f"\n处理: {adb_file.name}", end=' ')
        
        try:
            texts, unknown_commands = analyze_sections(adb_file)
            
            if texts:
                # 使用缓冲写入CSV
                csv_file = out_folder / f"{adb_file.stem}.csv"
                with open(csv_file, 'w', encoding='utf-8-sig', newline='', buffering=8192) as f:
                    writer = csv.writer(f)
                    writer.writerow(['区段ID', '文本内容'])
                    writer.writerows(texts)
                
                print(f"✓ {len(texts)} 个文本段", end='')
                total_texts += len(texts)
            else:
                print("✓ 无文本", end='')
            
            if enable_unknown_check and unknown_commands:
                print(f" | {len(unknown_commands)} 个未知命令", end='')
                for uc in unknown_commands:
                    all_unknown_commands[uc['command']].append({
                        'file': adb_file.name,
                        **uc
                    })
            
            print()  # 换行
        
        except Exception as e:
            print(f"✗ 失败: {e}")
    
    # 生成未知命令报告
    if enable_unknown_check and all_unknown_commands:
        report_file = out_folder / "UNKNOWN_COMMANDS.txt"
        with open(report_file, 'w', encoding='utf-8', buffering=8192) as f:
            f.write("未知命令报告\n")
            f.write("=" * 60 + "\n\n")
            f.write("这些区段包含中日文文本，但命令不在 COMMAND_DICT 中\n")
            f.write("请分析头部数据，确定参数长度后添加到字典\n\n")
            
            for command, occurrences in sorted(all_unknown_commands.items()):
                f.write(f"\n命令: {command} (出现 {len(occurrences)} 次)\n")
                f.write("-" * 60 + "\n")
                
                # 只显示前3个示例
                for occ in occurrences[:3]:
                    f.write(f"文件: {occ['file']}\n")
                    f.write(f"区段ID: {occ['section_id']} | 地址: {occ['address']} | 大小: {occ['size']} 字节\n")
                    f.write(f"头部: {occ['header']}\n")
                    f.write(f"文本: {occ['preview']}\n\n")
                
                if len(occurrences) > 3:
                    f.write(f"... 还有 {len(occurrences) - 3} 个示例\n")
                
                f.write(f"\n建议添加: b'\\x{command[:2]}\\x{command[2:]}': ?\n")
                f.write("=" * 60 + "\n")
        
        print(f"\n⚠ 发现 {len(all_unknown_commands)} 种未知命令")
        print(f"详细报告: {report_file}")
    
    print("\n" + "=" * 60)
    print(f"✓ 完成: 共提取 {total_texts} 个文本段")
    print(f"输出目录: {out_folder.absolute()}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("使用方法: python extract_texts.py <文件夹路径> [输出文件夹] [--check-unknown]")
        print("\n选项:")
        print("  --check-unknown  检测未知命令（较慢）")
        print("\n命令字典配置 (在代码中修改 COMMAND_DICT):")
        print("  b'\\x01\\x06': 6  # 命令2字节 + 参数4字节 = 6")
        sys.exit(1)
    
    folder_path = sys.argv[1]
    output_folder = None
    enable_check = '--check-unknown' in sys.argv
    
    # 解析参数
    if len(sys.argv) > 2:
        for arg in sys.argv[2:]:
            if arg != '--check-unknown' and not arg.startswith('--'):
                output_folder = arg
    
    process_folder(folder_path, output_folder, enable_check)