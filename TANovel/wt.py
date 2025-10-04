import sys
import os
import struct
import zenhan

def repack_text(original_file, text_file, output_file):
    # 读取原文件
    with open(original_file, 'rb') as f:
        original_data = f.read()
    
    # 从0x34读取字符区起始地址
    text_start = struct.unpack('<I', original_data[0x34:0x38])[0]
    
    # 提取指令区域（0x00到text_start-1）
    header_data = bytearray(original_data[:text_start])
    
    # 读取翻译后的文本
    with open(text_file, 'r', encoding='utf-8') as f:
        lines = [line.rstrip('\n') for line in f.readlines()]
    
    # 构建新的字符区域
    new_text_data = bytearray()
    
    for text in lines:
        if not text:  # 跳过空行
            continue
            
        encoded_text = zenhan.h2z(text).encode('gbk', errors='ignore')
        text_length = len(encoded_text)
        
        # 计算总长度（文本长度 + 4）
        total_length = text_length + 4
        
        # 写入长度（2字节小端序）
        new_text_data.extend(struct.pack('<H', total_length))
        
        # 写入文本
        new_text_data.extend(encoded_text)
        
        # 写入分隔符（2个00）
        new_text_data.extend(b'\x00\x00')

    header_data[0x38:0x3C] = struct.pack('<I', len(new_text_data))
    
    # 组合新文件：指令区域 + 新的字符区域
    new_file_data = header_data + new_text_data
    
    # 写入输出文件
    with open(output_file, 'wb') as f:
        f.write(new_file_data)

def main():
    if len(sys.argv) != 4:
        print("用法: python repack_script.py 原kgo文件夹 翻译文本文件夹 输出文件夹")
        return
    
    original_dir = sys.argv[1]
    text_dir = sys.argv[2]
    output_dir = sys.argv[3]
    
    os.makedirs(output_dir, exist_ok=True)
    
    for filename in os.listdir(original_dir):
        if filename.endswith('.kgo'):
            # 对应的文本文件名（去掉.kgo）
            base_name = filename[:-4]
            text_filename = base_name + '.kgo.txt'
            
            original_path = os.path.join(original_dir, filename)
            text_path = os.path.join(text_dir, text_filename)
            output_path = os.path.join(output_dir, filename)
            
            if os.path.exists(text_path):
                print(f"重新打包: {filename}")
                repack_text(original_path, text_path, output_path)
            else:
                print(f"警告: 找不到对应的翻译文件 {text_filename}")

if __name__ == '__main__':
    main()
