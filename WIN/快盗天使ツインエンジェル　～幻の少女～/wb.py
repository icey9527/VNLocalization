import sys
import os
import struct

def extract_text(input_file, output_file):
    with open(input_file, 'rb') as f:
        data = f.read()
    
    # 从0x34读取字符区起始地址（4字节小端序）
    text_start = struct.unpack('<I', data[0x34:0x38])[0]
    
    with open(output_file, 'w', encoding='utf-8') as out:
        pos = text_start
        while pos < len(data):
            # 读取字符串长度（2字节小端序）
            if pos + 2 > len(data):
                break
            str_len = struct.unpack('<H', data[pos:pos+2])[0]
            pos += 2
            
            # 计算实际字符串长度
            actual_len = str_len - 4
            if actual_len <= 0 or pos + actual_len + 2 > len(data):
                break
            
            # 读取字符串（UTF-16 LE编码）
            text_bytes = data[pos:pos+actual_len]
            try:
                text = text_bytes.decode('cp932')
                out.write(text + '\n')
            except:
                pass
            
            # 跳过字符串和分隔符
            pos += actual_len + 2

def main():
    if len(sys.argv) != 3:
        print("用法: python script.py 输入文件夹 输出文件夹")
        return
    
    input_dir = sys.argv[1]
    output_dir = sys.argv[2]
    
    os.makedirs(output_dir, exist_ok=True)
    
    for filename in os.listdir(input_dir):
        if filename.endswith('.kgo'):
            input_path = os.path.join(input_dir, filename)
            output_path = os.path.join(output_dir, filename + '.txt')
            
            print(f"处理: {filename}")
            extract_text(input_path, output_path)

if __name__ == '__main__':
    main()
