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

    # 收集所有 JSON：输入目录及子目录下的 *.json，外加输入目录上一级的 chr.json
    json_files = [
        os.path.join(root, name)
        for root, _, files in os.walk(input_dir)
        for name in files
        if name.lower().endswith(".json")
    ]
    chr_json_path = os.path.normpath(os.path.join(input_dir, "..", "chr.json"))
    if os.path.isfile(chr_json_path) and chr_json_path not in json_files:
        json_files.append(chr_json_path)

    extracted_texts = []
    json_used = False

    # 优先处理 JSON（同时兼容 tak 的数组格式 和 chr.json 的字典格式）
    for path in json_files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"处理文件 {path} 时出错: {e}")
            continue

        if isinstance(data, list):
            # tak 风格: [{"key": "00001234", "translation": "..."}]
            for item in data:
                if not isinstance(item, dict):
                    continue
                translated = item.get("translation", "")
                if isinstance(translated, str):
                    translated = translated.strip()
                    if translated:
                        extracted_texts.append(translated)
            json_used = True
        elif isinstance(data, dict):
            # chr.json 风格: {"...": "..."}
            for value in data.values():
                if isinstance(value, str):
                    value = value.strip()
                    if value:
                        extracted_texts.append(value)
            json_used = True
        else:
            print(f"警告: 文件 {path} 的内容不是 JSON 对象或数组，已跳过")

    # 只有在没有任何 JSON 被成功使用的情况下，才回退到 TXT
    if not json_used:
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