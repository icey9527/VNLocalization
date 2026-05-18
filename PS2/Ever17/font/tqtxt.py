#!/usr/bin/env python3
import sys
from pathlib import Path


def collect_text(text_dir):
    parts = []
    for path in sorted(Path(text_dir).rglob("*.txt")):
        if path.name in ("lines.txt", "漏提取.txt", "码表缺少.txt"):
            continue
        parts.append(path.read_text(encoding="utf-8"))
    return "".join(parts)


def build_text_file(text_dir, out_path):
    text = collect_text(text_dir)
    Path(out_path).write_text(text, encoding="utf-8-sig", newline="\n")
    print(f"chars in text: {len(text)}")


def usage():
    print("usage: python build_tbl.py <text_dir> <out_txt>")
    sys.exit(1)


def main(argv):
    if len(argv) != 3:
        usage()
    build_text_file(argv[1], argv[2])


if __name__ == "__main__":
    main(sys.argv)
