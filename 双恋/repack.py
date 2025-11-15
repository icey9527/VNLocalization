import struct

# ========== 配置区 ==========
FILE1 = '头文件.bin'
FILE2 = 'new/输出文件.bin'
OUTPUT = 'new/sc.bin'
TARGET_SIZE = 0x1efff0  # 填充到这个大小
# ============================

# 读取文件
data = open(FILE1, 'rb').read() + open(FILE2, 'rb').read()

# 填充到目标大小
data = data.ljust(TARGET_SIZE, b'\x00')

# 计算校验和
sum_even = sum_odd = 0x1111111111111111
for i in range(0, len(data), 8):
    val = int.from_bytes(data[i:i+8], 'little')
    if (i // 8) % 2 == 0:
        sum_even = (sum_even + val) & 0xFFFFFFFFFFFFFFFF
    else:
        sum_odd = (sum_odd + val) & 0xFFFFFFFFFFFFFFFF

# 追加校验码
checksum = sum_even.to_bytes(8, 'little') + sum_odd.to_bytes(8, 'little')
final = data + checksum

# 保存
open(OUTPUT, 'wb').write(final)

print(f"✅ 完成! {len(final)} 字节 -> {OUTPUT}")
print(f"   偶数和: 0x{sum_even:016X}")
print(f"   奇数和: 0x{sum_odd:016X}")