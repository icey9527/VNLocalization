#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从bin文件中提取/写回CP932编码的文本（跳转方案）
用法: 
    提取: python extract_text.py e <输入文件夹> <输出文件夹>
    写回: python extract_text.py w <原始bin文件夹> <csv文件夹> <输出文件夹>
"""

import sys
import csv
from pathlib import Path


def escape_text(text: str) -> str:
    """转义换行符等特殊字符"""
    return text.replace('\\', '\\\\').replace('\r\n', '\\r\\n').replace('\r', '\\r').replace('\n', '\\n')


def unescape_text(text: str) -> str:
    """还原转义字符"""
    result = []
    i = 0
    while i < len(text):
        if text[i] == '\\' and i + 1 < len(text):
            next_char = text[i + 1]
            if next_char == 'n':
                result.append('\n')
                i += 2
                continue
            elif next_char == 'r':
                result.append('\r')
                i += 2
                continue
            elif next_char == '\\':
                result.append('\\')
                i += 2
                continue
        result.append(text[i])
        i += 1
    return ''.join(result)


def extract_texts_from_bin(data: bytes) -> list[tuple[int, int, str]]:
    """
    从bin数据中提取文本
    返回: [(0x42的地址, 文本结束地址, 解码后的文本), ...]
    """
    results = []
    i = 0
    
    while i < len(data) - 2:
        if data[i] == 0x42:
            cmd_addr = i
            end_addr = int.from_bytes(data[i+1:i+3], 'little')
            start_addr = i + 3
            
            if start_addr < end_addr <= len(data):
                text_bytes = data[start_addr:end_addr]
                
                try:
                    decoded_text = text_bytes.decode('cp932')
                    if decoded_text and any(c.isprintable() or c in '\r\n' for c in decoded_text):
                        results.append((cmd_addr, end_addr, decoded_text))
                        i = end_addr
                        continue
                except (UnicodeDecodeError, LookupError):
                    pass
        
        i += 1
    
    return results


def extract_to_csv(input_path: Path, output_path: Path) -> int:
    """提取bin文件到CSV"""
    with open(input_path, 'rb') as f:
        data = f.read()
    
    texts = extract_texts_from_bin(data)
    
    if texts:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['地址', '原文', '译文'])
            for cmd_addr, end_addr, text in texts:
                escaped_text = escape_text(text)
                writer.writerow([f'0x{cmd_addr:06X}', escaped_text, ''])
    
    return len(texts)


def read_csv_translations(csv_path: Path) -> dict[int, tuple[str, str]]:
    """读取CSV翻译文件"""
    translations = {}
    
    with open(csv_path, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f)
        next(reader, None)
        
        for row in reader:
            if len(row) >= 3:
                addr_str, original, translated = row[0], row[1], row[2]
                addr = int(addr_str, 16)
                original = unescape_text(original)
                translated = unescape_text(translated) if translated.strip() else ''
                translations[addr] = (original, translated)
    
    return translations


def write_back_to_bin(original_data: bytes, translations: dict[int, tuple[str, str]]) -> bytes:
    """
    使用跳转方案写回翻译
    
    原始: [42][结束地址][文本]
    修改为: [00][跳转地址] + 填充到原结束地址
    
    文件末尾追加: [42][新结束地址][新文本][00][返回地址]
    """
    result = bytearray(original_data)
    append_data = bytearray()  # 追加到文件末尾的数据
    
    # 收集所有需要修改的指令
    commands = []
    i = 0
    
    while i < len(original_data) - 2:
        if original_data[i] == 0x42:
            cmd_addr = i
            end_addr = int.from_bytes(original_data[i+1:i+3], 'little')
            start_addr = i + 3
            
            if start_addr < end_addr <= len(original_data):
                text_bytes = original_data[start_addr:end_addr]
                
                try:
                    decoded_text = text_bytes.decode('cp932')
                    if decoded_text and any(c.isprintable() or c in '\r\n' for c in decoded_text):
                        commands.append({
                            'cmd_addr': cmd_addr,
                            'start_addr': start_addr,
                            'end_addr': end_addr,
                            'original_text': decoded_text
                        })
                        i = end_addr
                        continue
                except (UnicodeDecodeError, LookupError):
                    pass
        i += 1
    
    # 处理每个需要翻译的指令
    for cmd_info in commands:
        cmd_addr = cmd_info['cmd_addr']
        start_addr = cmd_info['start_addr']
        end_addr = cmd_info['end_addr']
        original_text = cmd_info['original_text']
        
        # 检查是否有翻译
        if cmd_addr not in translations:
            continue
        
        _, translated = translations[cmd_addr]
        
        # 如果译文为空，跳过
        if not translated:
            continue
        
        # 编码新文本
        try:
            new_text_bytes = translated.encode('cp932')
        except UnicodeEncodeError:
            print(f"  警告: 0x{cmd_addr:06X} 的译文无法用CP932编码，跳过")
            continue
        
        # 计算跳转目标地址（当前文件末尾 + 已追加数据长度）
        jump_target = len(original_data) + len(append_data)
        
        # 修改原位置: [00][跳转地址]
        result[cmd_addr] = 0x00
        result[cmd_addr + 1:cmd_addr + 3] = jump_target.to_bytes(2, 'little')
        
        # 原位置剩余空间填充（从cmd_addr+3到end_addr用00填充）
        for j in range(start_addr, end_addr):
            result[j] = 0x00
        
        # 构建追加数据: [42][新结束地址][新文本][00][返回地址]
        # 先计算新文本结束地址
        new_text_start = jump_target + 3  # 42 + 2字节地址
        new_text_end = new_text_start + len(new_text_bytes)
        return_jump_addr = new_text_end + 3  # 返回跳转指令之后的位置（实际不用，返回地址是end_addr）
        
        # [42]
        append_data.append(0x42)
        # [新结束地址] - 小端序
        append_data.extend(new_text_end.to_bytes(2, 'little'))
        # [新文本]
        append_data.extend(new_text_bytes)
        # [00][返回地址] - 返回到原结束地址
        append_data.append(0x00)
        append_data.extend(end_addr.to_bytes(2, 'little'))
    
    # 拼接结果
    result.extend(append_data)
    
    return bytes(result)


def process_extract(input_dir: Path, output_dir: Path):
    """提取模式"""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    total_files = 0
    total_texts = 0
    
    for input_path in input_dir.rglob('*'):
        if input_path.is_file():
            relative_path = input_path.relative_to(input_dir)
            output_path = output_dir / relative_path.with_suffix('.csv')
            
            count = extract_to_csv(input_path, output_path)
            
            if count > 0:
                print(f"[OK] {input_path.name} -> {count} 条文本")
                total_files += 1
                total_texts += count
            else:
                print(f"[--] {input_path.name} -> 无文本")
    
    print(f"\n提取完成! 处理了 {total_files} 个文件，共提取 {total_texts} 条文本")


def process_write_back(bin_dir: Path, csv_dir: Path, output_dir: Path):
    """写回模式"""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    total_files = 0
    total_texts = 0
    
    for csv_path in csv_dir.rglob('*.csv'):
        relative_path = csv_path.relative_to(csv_dir)
        bin_stem = relative_path.with_suffix('')
        bin_path = None
        
        for ext in ['', '.bin', '.dat', '.BIN', '.DAT']:
            test_path = bin_dir / bin_stem.parent / (bin_stem.name + ext)
            if test_path.exists():
                bin_path = test_path
                break
        
        if bin_path is None:
            for bin_file in bin_dir.rglob('*'):
                if bin_file.is_file() and bin_file.stem == bin_stem.name:
                    bin_path = bin_file
                    break
        
        if bin_path is None:
            print(f"[!!] 找不到对应的bin文件: {csv_path.name}")
            continue
        
        with open(bin_path, 'rb') as f:
            original_data = f.read()
        
        translations = read_csv_translations(csv_path)
        
        if not translations:
            print(f"[--] {csv_path.name} -> 无翻译内容")
            continue
        
        # 统计有效翻译数量
        valid_count = sum(1 for _, (_, t) in translations.items() if t.strip())
        
        new_data = write_back_to_bin(original_data, translations)
        
        output_path = output_dir / bin_path.relative_to(bin_dir)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'wb') as f:
            f.write(new_data)
        
        added_bytes = len(new_data) - len(original_data)
        print(f"[OK] {bin_path.name} <- {valid_count} 条翻译 (+{added_bytes} bytes)")
        total_files += 1
        total_texts += valid_count
    
    print(f"\n写回完成! 处理了 {total_files} 个文件，共写回 {total_texts} 条翻译")


def main():
    if len(sys.argv) < 2:
        print("用法:")
        print(f"  提取: python {sys.argv[0]} e <输入文件夹> <输出文件夹>")
        print(f"  写回: python {sys.argv[0]} w <原始bin文件夹> <csv文件夹> <输出文件夹>")
        sys.exit(1)
    
    mode = sys.argv[1].lower()
    
    if mode == 'e':
        if len(sys.argv) != 4:
            print(f"提取用法: python {sys.argv[0]} e <输入文件夹> <输出文件夹>")
            sys.exit(1)
        
        input_dir = Path(sys.argv[2])
        output_dir = Path(sys.argv[3])
        
        if not input_dir.exists():
            print(f"错误: 输入文件夹不存在: {input_dir}")
            sys.exit(1)
        
        process_extract(input_dir, output_dir)
    
    elif mode == 'w':
        if len(sys.argv) != 5:
            print(f"写回用法: python {sys.argv[0]} w <原始bin文件夹> <csv文件夹> <输出文件夹>")
            sys.exit(1)
        
        bin_dir = Path(sys.argv[2])
        csv_dir = Path(sys.argv[3])
        output_dir = Path(sys.argv[4])
        
        if not bin_dir.exists():
            print(f"错误: bin文件夹不存在: {bin_dir}")
            sys.exit(1)
        
        if not csv_dir.exists():
            print(f"错误: csv文件夹不存在: {csv_dir}")
            sys.exit(1)
        
        process_write_back(bin_dir, csv_dir, output_dir)
    
    else:
        print(f"未知模式: {mode}")
        print("使用 'e' 提取，'w' 写回")
        sys.exit(1)


if __name__ == '__main__':
    main()