import struct
import csv
import re
from pathlib import Path
import shutil

COMMAND_DICT = {
    b'\x01\x06': 6,
    b'\x00\x06': 6,
    b'\x10\x07': 2,
    b'\x00\x02': 8,
    b'\x08\x00': 10,
    b'\x11\x00': 6,
}

def encode_text(text: str) -> bytes:
    """编码文本为UTF-16 LE（含结束符00 00）"""
    # 处理 <XXYY> 格式
    def hex_to_char(m):
        h = m.group(1)
        return bytes([int(h[0:2], 16), int(h[2:4], 16)]).decode('utf-16-le', errors='replace')
    
    text = re.sub(r'<([0-9A-Fa-f]{4})>', hex_to_char, text)
    text = text.replace('\\n', '\n').replace('\\r', '\r').replace('\\t', '\t')
    
    return text.encode('utf-16-le') + b'\x00\x00'

def find_text_end(data: bytes, start: int) -> int:
    """找到00 00的位置（包含00 00）"""
    i = start
    while i < len(data) - 1:
        if data[i:i+2] == b'\x00\x00':
            return i + 2
        i += 2
    return len(data)

def split_section(section: bytes):
    """
    分割section为三部分：
    - header: 命令 + 参数
    - text: 文本数据 + 00 00
    - tail: 00 00 之后的未知数据
    """
    command = section[0:2]
    if command not in COMMAND_DICT:
        return None, None, None
    
    header_len = COMMAND_DICT[command]
    text_end = find_text_end(section, header_len)
    
    return section[0:header_len], section[header_len:text_end], section[text_end:]

def rebuild_adb(adb_path: Path, csv_path: Path, out_path: Path):
    """重建ADB文件"""
    # 读取原始文件
    with open(adb_path, 'rb') as f:
        data = f.read()
    
    # 读取CSV翻译
    translations = {}
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        next(csv.reader(f))  # 跳过标题
        for row in csv.reader(f):
            if len(row) >= 2:
                # 如果有第3项且不为空，使用第3项；否则使用第2项
                if len(row) >= 3 and row[2].strip():
                    translations[int(row[0])] = row[2]
                else:
                    translations[int(row[0])] = row[1]
    
    # 解析文件头
    section_size = struct.unpack('<I', data[0x10:0x14])[0]
    count = struct.unpack('<I', data[0x14:0x18])[0]
    index_start = 0x30 + section_size
    base_addr = index_start + count * 4
    
    # 解析索引表
    sections = []
    for i in range(count):
        addr = struct.unpack('<I', data[index_start + i*4:index_start + i*4 + 4])[0] + base_addr
        sections.append((i, addr))
    
    sections.sort(key=lambda x: x[1])
    
    # 重建sections
    new_sections = []
    for idx, (sec_id, start) in enumerate(sections):
        end = sections[idx + 1][1] if idx + 1 < len(sections) else len(data)
        section = data[start:end]
        
        csv_id = sec_id + 1
        if csv_id in translations:
            header, old_text, tail = split_section(section)
            if header:
                new_text = encode_text(translations[csv_id])
                
                # 更新长度字段
                header = bytearray(header)  # 转成可修改的
                command = bytes(header[0:2])
                
                if command == b'\x01\x06':
                    # 计算：(实际字节 - 2) / 2，不包括00 00
                    text_len = (len(new_text) - 2) // 2
                    struct.pack_into('<H', header, 4, text_len)  # 写到第4-5字节位置
                
                section = bytes(header) + new_text + tail
        
        new_sections.append(section)
    
    # 重建文件
    result = bytearray(data[0:index_start])  # 保留文件头和未知区域
    
    # 重建索引表
    index_table = bytearray(count * 4)
    offset = 0
    for i, sec in enumerate(new_sections):
        struct.pack_into('<I', index_table, i * 4, offset)
        offset += len(sec)
    
    result.extend(index_table)
    
    # 添加section数据
    for sec in new_sections:
        result.extend(sec)
    
    # 更新0x18处的数据区总大小
    struct.pack_into('<I', result, 0x18, offset)
    
    # 写入
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'wb') as f:
        f.write(result)
    
    print(f"✓ {adb_path.name}: {len(translations)}个翻译")

def process_folder(adb_folder: str, csv_folder: str, out_folder: str = None):
    """批量处理"""
    adb_dir = Path(adb_folder)
    csv_dir = Path(csv_folder)
    out_dir = Path(out_folder) if out_folder else adb_dir.parent / "rebuilt"
    out_dir.mkdir(exist_ok=True)
    
    csvs = [f for f in csv_dir.glob("*.csv") if not f.name.startswith('UNKNOWN')]
    print(f"找到 {len(csvs)} 个CSV\n")
    
    # 处理有对应CSV的ADB文件
    for csv_file in csvs:
        adb_file = adb_dir / f"{csv_file.stem}.adb"
        if adb_file.exists():
            try:
                rebuild_adb(adb_file, csv_file, out_dir / adb_file.name)
            except Exception as e:
                print(f"✗ {csv_file.name}: {e}")
        else:
            print(f"{csv_file.name}: 找不到对应adb")
    
    # 新增：复制没有对应CSV的ADB文件
    print("\n处理未翻译文件...")
    for adb_file in adb_dir.glob("*.adb"):
        csv_file = csv_dir / f"{adb_file.stem}.csv"
        out_file = out_dir / adb_file.name
        
        # 如果这个adb文件没有对应的csv，且输出文件还不存在
        if not csv_file.exists() and not out_file.exists():
            shutil.copy2(adb_file, out_file)
            print(f"{adb_file.name}: 复制原文件")
    
    print(f"\n输出: {out_dir}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("用法: python rebuild.py <adb文件夹> <csv文件夹> [输出文件夹]")
        sys.exit(1)
    
    process_folder(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)