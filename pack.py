import struct
import os
import csv

# 配置参数
ARM9_FILE = 'arm9.BIN'
OUTPUT_ARM9_FILE = 'I:/研究/nds/dump2/pack_data/arm9.BIN'
OUTPUT_DATA_FILE = 'I:/研究/nds/dump2/pack_data/data/data.bin'
OUTPUT_DIR = 'pack'
CSV_FILE = os.path.join(OUTPUT_DIR, 'file_list.csv')
OFFSET_TABLE_START = 0x9143C

print("=" * 50)
print("开始重新打包文件")
print("=" * 50)

# 步骤1: 读取CSV文件（无表头）
print(f"\n[1/4] 正在读取 {CSV_FILE}...")
file_info_list = []
with open(CSV_FILE, 'r', newline='', encoding='utf-8') as f:
    reader = csv.reader(f)
    for row in reader:
        file_info_list.append(row)

file_count = len(file_info_list)
print(f"      读取到 {file_count} 个文件记录")

# 统计压缩类型
compression_stats = {}
for info in file_info_list:
    comp = info[1]
    compression_stats[comp] = compression_stats.get(comp, 0) + 1

print(f"\n压缩类型统计:")
for comp_type, count in sorted(compression_stats.items()):
    print(f"  {comp_type}: {count} 个文件")

# 步骤2: 按CSV顺序拼接数据文件
print(f"\n[2/4] 正在生成 {OUTPUT_DATA_FILE}...")
new_offsets = []
current_offset = 0

with open(OUTPUT_DATA_FILE, 'wb') as out_f:
# 修改这部分代码：
    for i, info in enumerate(file_info_list):
        # 使用CSV中记录的相对路径
        relative_path = info[0]
        filepath = os.path.join(OUTPUT_DIR, relative_path)
        
        # 记录当前偏移
        new_offsets.append(current_offset)
        
        # 读取文件内容并计算大小
        if os.path.exists(filepath):
            with open(filepath, 'rb') as in_f:
                file_data = in_f.read()
            file_size = len(file_data)
        else:
            print(f"      警告: 文件 {filepath} 不存在！")
            file_data = b''
            file_size = 0
        
        # 写入4字节文件大小（小端序）
        out_f.write(struct.pack('<I', file_size))
        current_offset += 4
        
        # 写入文件内容
        out_f.write(file_data)
        current_offset += len(file_data)
        
        # 进度提示
        if (i + 1) % 500 == 0 or i == 0:
            print(f"      进度: {i + 1}/{file_count} ({(i + 1) * 100 / file_count:.1f}%)")

print(f"      生成的数据文件大小: {current_offset:,} 字节")

# 步骤3: 读取原始arm9.bin
print(f"\n[3/4] 正在读取原始 {ARM9_FILE}...")
with open(ARM9_FILE, 'rb') as f:
    arm9_data = bytearray(f.read())

print(f"      原始文件大小: {len(arm9_data):,} 字节")

# 步骤4: 修改地址表并写入新文件
print(f"\n[4/4] 正在生成 {OUTPUT_ARM9_FILE}...")
for i, offset in enumerate(new_offsets):
    # 计算地址表中的位置
    pos = OFFSET_TABLE_START + i * 4
    # 写入新的偏移地址
    arm9_data[pos:pos+4] = struct.pack('<I', offset)
    
    # 进度提示
    if (i + 1) % 500 == 0 or i == 0:
        print(f"      进度: {i + 1}/{file_count} ({(i + 1) * 100 / file_count:.1f}%)")

# 写入新的arm9文件
with open(OUTPUT_ARM9_FILE, 'wb') as f:
    f.write(arm9_data)

print("\n" + "=" * 50)
print(f"✓ 完成！")
print(f"  - 数据文件已保存为: {OUTPUT_DATA_FILE}")
print(f"  - ARM9文件已保存为: {OUTPUT_ARM9_FILE}")
print(f"  - 地址表位置: 0x{OFFSET_TABLE_START:X}")
print("=" * 50)