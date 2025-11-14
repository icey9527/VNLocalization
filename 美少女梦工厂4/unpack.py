import struct
import os
import csv

# 配置参数
ARM9_FILE = 'arm9.BIN'
DATA_FILE = 'data.bin'
OUTPUT_DIR = 'output'
CSV_FILE = os.path.join(OUTPUT_DIR, 'file_list.csv')  # CSV放到output文件夹
OFFSET_TABLE_START = 0x9143C  # 地址表起始位置
FILE_COUNT = 6105              # 文件数量

# 创建输出目录
os.makedirs(OUTPUT_DIR, exist_ok=True)

print("=" * 50)
print(f"开始提取 {FILE_COUNT} 个文件")
print("=" * 50)

# 步骤1: 读取地址表
print(f"\n[1/4] 正在从 {ARM9_FILE} 读取地址表...")
offsets = []
with open(ARM9_FILE, 'rb') as f:
    f.seek(OFFSET_TABLE_START)
    for i in range(FILE_COUNT):
        data = f.read(4)
        offset = struct.unpack('<I', data)[0]
        offsets.append(offset)

print(f"      成功读取 {len(offsets)} 个地址")

# 步骤2: 读取数据文件
print(f"\n[2/4] 正在读取 {DATA_FILE}...")
with open(DATA_FILE, 'rb') as f:
    data_content = f.read()

data_size = len(data_content)
print(f"      数据文件大小: {data_size:,} 字节")

# 步骤3: 提取文件并检测压缩类型
print(f"\n[3/4] 正在提取文件并分析压缩类型...")
file_info_list = []

for i in range(FILE_COUNT):
    # 数据起始位置（跳过4字节文件头）
    start = offsets[i] + 4
    
    # 确定结束地址
    if i < FILE_COUNT - 1:
        end = offsets[i + 1]
    else:
        end = data_size
    
    # 提取文件数据
    file_data = data_content[start:end]
    
    # 检测压缩类型
    compression = 'NZ'  # 默认不压缩
    if len(file_data) >= 4:
        # 检查字符串标识
        header_str = file_data[:4]
        if header_str == b'LZ08':
            compression = 'LZ08'
        elif header_str == b'LZ12':
            compression = 'LZ12'
        # 检查字节标识
        elif file_data[0] == 0x10:
            compression = 'LZ10'
        elif file_data[0] == 0x11:
            compression = 'LZ11'
    
    # 创建对应压缩类型的文件夹
    compression_dir = os.path.join(OUTPUT_DIR, compression)
    os.makedirs(compression_dir, exist_ok=True)
    
    # 文件名
    filename = f'{i:08X}.bin'
    
    # 保存文件到对应文件夹
    output_path = os.path.join(compression_dir, filename)
    with open(output_path, 'wb') as f:
        f.write(file_data)
    
    # 记录文件信息（使用相对路径）
    relative_path = os.path.join(compression, filename)
    file_info_list.append([relative_path, compression])
    
    # 进度提示
    if (i + 1) % 500 == 0 or i == 0:
        print(f"      进度: {i + 1}/{FILE_COUNT} ({(i + 1) * 100 / FILE_COUNT:.1f}%)")

# 步骤4: 保存CSV文件（不写表头）
print(f"\n[4/4] 正在生成 {CSV_FILE}...")
with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerows(file_info_list)

# 统计压缩类型
compression_stats = {}
for info in file_info_list:
    comp = info[1]
    compression_stats[comp] = compression_stats.get(comp, 0) + 1

print("\n" + "=" * 50)
print(f"✓ 完成！所有 {FILE_COUNT} 个文件已保存到 {OUTPUT_DIR}/ 目录")
print(f"\n压缩类型统计:")
for comp_type, count in sorted(compression_stats.items()):
    print(f"  {comp_type}: {count} 个文件 (保存在 {OUTPUT_DIR}/{comp_type}/)")
print(f"\n文件列表已保存为: {CSV_FILE}")
print("=" * 50)