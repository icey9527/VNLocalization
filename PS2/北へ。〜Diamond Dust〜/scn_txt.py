#!/usr/bin/env python3
import json
import sys
from pathlib import Path
import char

char.MAP_PATH = Path("font/font.tbl")


def unquote(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        s = s[1:-1]
    return s.replace("￥", "")


def quote(s: str) -> str:
    return f'"{s}"'


def parse_line(line: str):
    line = line.rstrip("\n")
    if not line:
        return None, None
    lpar = line.find("(")
    if lpar < 0 or not line.endswith(")"):
        return None, None
    cmd = line[:lpar].strip()
    rest = line[lpar + 1 : -1]
    args, buf, in_quote = [], [], False
    for ch in rest:
        if ch == '"':
            in_quote = not in_quote
            buf.append(ch)
        elif ch == "," and not in_quote:
            args.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if buf or rest.endswith(","):
        args.append("".join(buf).strip())
    return cmd, args


def extract_file(txt_path: Path, json_dir: Path):
    rows = []
    text_cnt = 0
    choice_cnt = 0
    lines = txt_path.read_text(encoding="utf-8").splitlines()
    i = 0
    while i < len(lines):
        cmd, args = parse_line(lines[i])
        if cmd in ("text", "text_wait") and args and len(args) >= 3:
            text_cnt += 1
            speaker = args[0]
            text = unquote(args[2])
            rows.append(
                {
                    "key": f"text_{text_cnt}",
                    "original": text,
                    "translation": "",
                    "stage": 0,
                    "context": speaker,
                }
            )
            i += 1
            continue
        if cmd == "choice" and args and len(args) >= 4:
            choice_cnt += 1
            prompt = unquote(args[3])
            rows.append(
                {
                    "key": f"choice_{choice_cnt}_0",
                    "original": prompt,
                    "translation": "",
                    "stage": 0,
                    "context": "【0】选项提示",
                }
            )
            i += 1
            opt_idx = 1
            while i < len(lines):
                sub_cmd, sub_args = parse_line(lines[i])
                if sub_cmd != "choice_item":
                    break
                if sub_args and len(sub_args) >= 4:
                    opt_text = unquote(sub_args[3])
                    rows.append(
                        {
                            "key": f"choice_{choice_cnt}_{opt_idx}",
                            "original": opt_text,
                            "translation": "",
                            "stage": 0,
                            "context": f"选项{opt_idx}",
                        }
                    )
                    opt_idx += 1
                i += 1
            continue
        if cmd == "choice_simple" and args and len(args) >= 1:
            choice_cnt += 1
            i += 1
            opt_idx = 1
            while i < len(lines):
                sub_cmd, sub_args = parse_line(lines[i])
                if sub_cmd != "choice_item":
                    break
                if sub_args and len(sub_args) >= 3:
                    opt_text = unquote(sub_args[2])
                    rows.append(
                        {
                            "key": f"choice_{choice_cnt}_{opt_idx}",
                            "original": opt_text,
                            "translation": "",
                            "stage": 0,
                            "context": f"选项{opt_idx}",
                        }
                    )
                    opt_idx += 1
                i += 1
            continue
        i += 1
    if rows:
        (json_dir / f"{txt_path.stem}.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def extract_all(input_dir: Path, json_dir: Path):
    json_dir.mkdir(parents=True, exist_ok=True)
    for f in json_dir.glob("*.json"):
        f.unlink()
    for txt in sorted(input_dir.glob("*.txt")):
        extract_file(txt, json_dir)
    print(f"提取完成 → {json_dir}")


def load_json_dir(json_dir: Path):
    conv = char.make_translation_converter()
    texts = {}
    for f in json_dir.glob("*.json"):
        data = json.loads(f.read_text(encoding="utf-8"))
        by_key = {}
        for item in data:
            tr = item.get("translation") or ""
            if tr:
                item["translation"] = conv(tr)
            by_key[item["key"]] = item
        texts[f.stem.upper()] = by_key
    return texts


def choose_text(item: dict, original: str) -> str:
    if not item:
        return original
    if int(item.get("stage", 0) or 0) == 0:
        return original
    return item.get("translation") or original


def rewrite_file(src: Path, dst: Path, items: dict):
    out = []
    text_cnt = 0
    choice_cnt = 0
    lines = src.read_text(encoding="utf-8").splitlines()
    i = 0
    while i < len(lines):
        cmd, args = parse_line(lines[i])
        if cmd in ("text", "text_wait") and args and len(args) >= 3:
            text_cnt += 1
            key = f"text_{text_cnt}"
            speaker = args[0]
            old_text = unquote(args[2])
            new_text = choose_text(items.get(key), old_text)
            out.append(f'{cmd}({speaker}, {args[1]}, {quote(new_text)})')
            i += 1
            continue
        if cmd == "choice" and args and len(args) >= 4:
            choice_cnt += 1
            old_prompt = unquote(args[3])
            new_prompt = choose_text(items.get(f"choice_{choice_cnt}_0"), old_prompt)
            out.append(f'{cmd}({args[0]}, {args[1]}, {args[2]}, {quote(new_prompt)})')
            i += 1
            opt_idx = 1
            while i < len(lines):
                sub_cmd, sub_args = parse_line(lines[i])
                if sub_cmd != "choice_item":
                    break
                if sub_args and len(sub_args) >= 4:
                    old_opt = unquote(sub_args[3])
                    key = f"choice_{choice_cnt}_{opt_idx}"
                    new_opt = choose_text(items.get(key), old_opt)
                    out.append(
                        f'choice_item({sub_args[0]}, {sub_args[1]}, {sub_args[2]}, {quote(new_opt)})'
                    )
                    opt_idx += 1
                i += 1
            continue
        if cmd == "choice_simple" and args and len(args) >= 1:
            choice_cnt += 1
            out.append(f"{cmd}({args[0]})")
            i += 1
            opt_idx = 1
            while i < len(lines):
                sub_cmd, sub_args = parse_line(lines[i])
                if sub_cmd != "choice_item":
                    break
                if sub_args and len(sub_args) >= 3:
                    old_opt = unquote(sub_args[2])
                    key = f"choice_{choice_cnt}_{opt_idx}"
                    new_opt = choose_text(items.get(key), old_opt)
                    out.append(f'choice_item({sub_args[0]}, {sub_args[1]}, {quote(new_opt)})')
                    opt_idx += 1
                i += 1
            continue
        out.append(lines[i])
        i += 1
    dst.write_text("\n".join(out) + "\n", encoding="utf-8")


def apply_all(input_dir: Path, json_dir: Path, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    texts = load_json_dir(json_dir)
    for src in input_dir.glob("*.txt"):
        rewrite_file(src, output_dir / src.name, texts.get(src.stem.upper(), {}))
    print(f"回写完成 → {output_dir}")


def main():
    if len(sys.argv) < 4:
        print("用法:")
        print("  提取: python script.py e 输入文件夹 输出json文件夹")
        print("  回写: python script.py w 输入txt文件夹 json文件夹 输出文件夹")
        sys.exit(2)
    mode = sys.argv[1]
    if mode == "e" and len(sys.argv) == 4:
        extract_all(Path(sys.argv[2]), Path(sys.argv[3]))
    elif mode == "w" and len(sys.argv) == 5:
        apply_all(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
    else:
        print("参数错误")
        sys.exit(2)


if __name__ == "__main__":
    main()