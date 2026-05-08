import os
import sys

def merge_txts(input_dir, output_file):
    paths = sorted(
        os.path.join(root, name)
        for root, _, files in os.walk(input_dir)
        for name in files
        if name.lower().endswith(".txt")
    )

    if not paths:
        print(f"警告: 在目录 {input_dir} 及其子目录中未找到TXT文件")
        return

    parts = []
    for path in paths:
        try:
            with open(path, "r", encoding="utf-8") as f:
                parts.append(f.read())
        except Exception as e:
            print(f"处理文件 {path} 时出错: {e}")

    content = "\n".join(s.rstrip("\n\r") for s in parts if s is not None).strip()
    if not content:
        print("未找到任何可合并的文本内容")
        return

    with open(output_file, "w", encoding="utf-8-sig") as f:
        f.write(content + "\n")

    print(f"成功合并 {len(paths)} 个TXT到 {output_file}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("用法: python merge.py <输入目录> <输出文件>")
        sys.exit(1)

    merge_txts(sys.argv[1], sys.argv[2])