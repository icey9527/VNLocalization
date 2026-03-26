import os
import sys
import json

def extract_black_diamond_text(input_dir, output_file):
    txt_files = [
        os.path.join(root, name)
        for root, _, files in os.walk(input_dir)
        for name in files
        if name.lower().endswith(".txt")
    ]

    extracted_texts = []

    # 提取 TXT 中以 ◆ 开头的文本
    if not txt_files:
        print(f"警告: 在目录 {input_dir} 及其子目录中未找到TXT文件")
    else:
        for path in txt_files:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.rstrip("\n\r")
                        if line.startswith("◆"):
                            text = line[1:].strip()
                            if text:
                                extracted_texts.append(text)
            except Exception as e:
                print(f"处理文件 {path} 时出错: {e}")

    # 读取输入目录上一级目录中的 chr.json
    chr_json_path = os.path.normpath(os.path.join(input_dir, "..", "chr.json"))

    if not os.path.isfile(chr_json_path):
        print(f"警告: 未找到 chr.json: {chr_json_path}")
    else:
        try:
            with open(chr_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, dict):
                for translated_text in data.values():
                    if isinstance(translated_text, str):
                        translated_text = translated_text.strip()
                        if translated_text:
                            extracted_texts.append(translated_text)
            else:
                print(f"警告: 文件 {chr_json_path} 的内容不是 JSON 对象，已跳过")

        except Exception as e:
            print(f"处理文件 {chr_json_path} 时出错: {e}")

    if not extracted_texts:
        print("未找到任何可提取的文本内容")
        return

    with open(output_file, "w", encoding="utf-8-sig") as f:
        f.write("\n".join(extracted_texts) + "\n")

    print(f"成功提取 {len(extracted_texts)} 条文本到 {output_file}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("用法: python tqjs.py <输入目录> <输出文件>")
        sys.exit(1)

    extract_black_diamond_text(sys.argv[1], sys.argv[2])