import sys
import shutil
from pathlib import Path

import char

char.MAP_PATH = Path('font/font.tbl')

def extract(input_dir: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    
    init_src = input_dir / "init.txt"
    if init_src.exists():
        shutil.copy2(init_src, output_dir / "init.txt")
    
    mac_src_dir = input_dir / "mac"
    mac_dst_dir = output_dir / "mac"
    if mac_src_dir.is_dir():
        mac_dst_dir.mkdir(parents=True, exist_ok=True)
        for txt_file in mac_src_dir.glob("*.txt"):
            shutil.copy2(txt_file, mac_dst_dir / txt_file.name)

def write_back(input_dir: Path, output_dir: Path) -> None:
    conv = char.make_translation_converter()
    
    init_src = input_dir / "init.txt"
    if init_src.exists():
        shutil.copy2(init_src, output_dir / "init.txt")
    
    mac_src_dir = input_dir / "mac"
    mac_dst_dir = output_dir / "mac"
    if mac_src_dir.is_dir():
        mac_dst_dir.mkdir(parents=True, exist_ok=True)
        for txt_file in mac_src_dir.glob("*.txt"):
            content = txt_file.read_text(encoding="utf-8")
            conved = conv(content)
            dst = mac_dst_dir / txt_file.name
            dst.write_text(conved, encoding="utf-8")

def main() -> None:
    if len(sys.argv) != 4:
        print("用法: python copy.py e 输入目录 输出目录")
        print("      python copy.py w 输入目录 输出目录")
        sys.exit(1)
    
    mode = sys.argv[1]
    input_dir = Path(sys.argv[2])
    output_dir = Path(sys.argv[3])
    
    if mode == "e":
        extract(input_dir, output_dir)
    elif mode == "w":
        write_back(input_dir, output_dir)
    else:
        print(f"未知模式: {mode}")
        sys.exit(1)

if __name__ == "__main__":
    main()