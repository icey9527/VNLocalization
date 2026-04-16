import json
import os
import sys

def extract_translations(input_dir, output_file):
    json_files = [
        os.path.join(root, name)
        for root, _, files in os.walk(input_dir)
        for name in files
        if name.lower().endswith(".json")
    ]
    if not json_files:
        print(f"警告: 在目录 {input_dir} 及其子目录中未找到JSON文件")
        return

    translations = []
    for path in json_files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                translations += [
                    item["translation"]
                    for item in data
                    if isinstance(item, dict) and item.get("translation")
                ]
        except Exception as e:
            print(f"处理文件 {path} 时出错: {e}")

    if not translations:
        print("未找到任何stage=1的translation内容")
        return

    with open(output_file, "w", encoding="utf-8-sig") as f:
        f.write("\n".join(translations) + "\n")
    print(f"成功从 {len(json_files)} 个文件中提取 {len(translations)} 条翻译到 {output_file}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("用法: python extract_translations.py <输入目录> <输出文件>")
        sys.exit(1)
    extract_translations(sys.argv[1], sys.argv[2])