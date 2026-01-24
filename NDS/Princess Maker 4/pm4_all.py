#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, json
from pathlib import Path

def usage():
    print("usage:\n  python tr.py e asm_dir\n  python tr.py w asm_dir out_dir", file=sys.stderr)
    sys.exit(1)

def strip_quotes(s: str) -> str:
    s = s.strip()
    return s[1:-1] if len(s) >= 2 and s[0] == '"' and s[-1] == '"' else s

def split_params(s: str):
    res, cur, in_str = [], [], False
    for ch in s:
        if ch == '"':
            in_str = not in_str
            cur.append(ch)
        elif ch == ',' and not in_str:
            t = ''.join(cur).strip()
            if t: res.append(t)
            cur = []
        else:
            cur.append(ch)
    t = ''.join(cur).strip()
    if t: res.append(t)
    return res

def parse_int(x: str) -> int:
    x = x.strip()
    return int(x, 16) if x.lower().startswith('0x') else int(x, 10)

def load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))

def save_json(path: str, obj: dict):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def extract(asm_dir: Path):
    all_txt, line_meta = [], []
    names = {}
    selects = {}

    for p in sorted(asm_dir.glob("*.asm")):
        lines = p.read_text(encoding="utf-8").splitlines()
        for ln, line in enumerate(lines, 1):
            s = line.strip()
            if not s:
                continue
            parts = s.split(None, 1)
            op = parts[0]
            rest = parts[1].strip() if len(parts) > 1 else ""

            if op == "MESSAGE_NAME":
                names.setdefault(strip_quotes(rest), "")

            elif op == "MESSAGE":
                all_txt.append(strip_quotes(rest))
                line_meta.append(f"{p.name} {ln}")

            elif op == "SELECT":
                ps = split_params(rest)
                if not ps:
                    continue
                try:
                    n = parse_int(ps[0])
                except:
                    continue
                if len(ps) != 1 + n * 2:
                    continue
                k = 1
                for _ in range(n):
                    k += 1  # 跳过 label
                    selects.setdefault(strip_quotes(ps[k]), "")
                    k += 1

    Path("all.txt").write_text("\n".join(all_txt), encoding="utf-8")
    Path("lines.txt").write_text("\n".join(line_meta), encoding="utf-8")
    save_json("MESSAGE_NAME.json", names)
    save_json("SELECT.json", selects)

def apply_message_line_edits(file_lines, edits_by_lineno):
    for ln, newtxt in edits_by_lineno.items():
        if 1 <= ln <= len(file_lines):
            s = file_lines[ln - 1].strip()
            if s.startswith("MESSAGE "):
                file_lines[ln - 1] = f'MESSAGE "{newtxt}"'
    return file_lines

def apply_name_dict(file_lines, name_dict):
    for i, line in enumerate(file_lines):
        s = line.strip()
        if not s.startswith("MESSAGE_NAME "):
            continue
        rest = s.split(None, 1)[1].strip() if len(s.split(None, 1)) > 1 else ""
        src = strip_quotes(rest)
        dst = name_dict.get(src, "")
        if dst:
            file_lines[i] = f'MESSAGE_NAME "{dst}"'
    return file_lines

def apply_select_dict(file_lines, sel_dict):
    for i, line in enumerate(file_lines):
        s = line.strip()
        if not s.startswith("SELECT "):
            continue
        rest = s.split(None, 1)[1].strip() if len(s.split(None, 1)) > 1 else ""
        ps = split_params(rest)
        if not ps:
            continue
        try:
            n = parse_int(ps[0])
        except:
            continue
        if len(ps) != 1 + n * 2:
            continue
        k = 1
        changed = False
        for _ in range(n):
            k += 1  # label
            src = strip_quotes(ps[k])
            dst = sel_dict.get(src, "")
            if dst:
                ps[k] = f'"{dst}"'
                changed = True
            k += 1
        if changed:
            file_lines[i] = "SELECT " + ", ".join(ps)
    return file_lines

def writeback(asm_dir: Path, out_dir: Path):
    all_txt = Path("all.txt").read_text(encoding="utf-8").splitlines()
    meta = Path("lines.txt").read_text(encoding="utf-8").splitlines()
    if len(all_txt) != len(meta):
        raise SystemExit("all.txt and lines.txt line count mismatch")

    name_dict = load_json("MESSAGE_NAME.json")
    sel_dict = load_json("SELECT.json")

    per_file_msg_edits = {}
    for i, m in enumerate(meta):
        sp = m.split()
        if len(sp) < 2:
            continue
        fn = sp[0]
        ln = int(sp[1])
        per_file_msg_edits.setdefault(fn, {})[ln] = all_txt[i]

    out_dir.mkdir(parents=True, exist_ok=True)

    for p in sorted(asm_dir.glob("*.asm")):
        lines = p.read_text(encoding="utf-8").splitlines()

        lines = apply_message_line_edits(lines, per_file_msg_edits.get(p.name, {}))
        if name_dict:
            lines = apply_name_dict(lines, name_dict)
        if sel_dict:
            lines = apply_select_dict(lines, sel_dict)

        (out_dir / p.name).write_text("\n".join(lines), encoding="utf-8")

if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        usage()
    mode = sys.argv[1].lower()
    if mode == "e":
        extract(Path(sys.argv[2]))
    elif mode == "w" and len(sys.argv) == 4:
        writeback(Path(sys.argv[2]), Path(sys.argv[3]))
    else:
        usage()