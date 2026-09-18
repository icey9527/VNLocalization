#!/usr/bin/env python3
"""提取/回写 asm 脚本里遗留的函数字符串（bg_name / mbg_name / bg_scroll 等）。

用法：
    py bg_name.py e <目录> <输出.json> [函数名 ...]   # 提取（按原文去重）
    py bg_name.py w <目录> <json> [函数名 ...]        # 原目录就地回写

函数名缺省为 bg_name mbg_name bg_scroll，也可以自行指定，例如：
    py bg_name.py e raw/asm_cn choice.json choice choice_item
    py bg_name.py w raw/asm_cn choice.json choice choice_item

json 为 [{key, original, translation, stage}] 列表（同 elf_string.py 格式）：
    stage 为 0 使用原文，否则使用译文；译文留空也回退原文。
回写时译文先经过 to_fullwidth(char.convert_translation(译文)) 映射
（·->・、-->─、引号转「」、半角转全角），与 scn_txt 的回写规则一致。
字符串内容原样提取（不做 strip），文件 BOM / CRLF 原样保留。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import char
from scn_txt import to_fullwidth

char.MAP_PATH = Path("font/font.tbl")

DEFAULT_FUNCS = ("bg_name", "mbg_name", "bg_scroll")

BOM = b"\xef\xbb\xbf"
# 整行调用：缩进 + 函数名 + ( 参数 ) + 行尾符。贪婪匹配使 ")" 对准行内最后一个右括号
CALL_RE = re.compile(r"^([ \t]*)([A-Za-z_][A-Za-z0-9_]*)\(([^\n]*)\)(\r?\n?)$")
STR_RE = re.compile(r'"([^"\n]*)"')


def iter_txt_files(root: Path) -> list[Path]:
    return sorted(p for p in root.glob("*.txt") if p.is_file())


def read_text(path: Path) -> tuple[str, bool]:
    data = path.read_bytes()
    bom = data.startswith(BOM)
    if bom:
        data = data[len(BOM):]
    return data.decode("utf-8"), bom


def write_text(path: Path, text: str, bom: bool) -> None:
    data = text.encode("utf-8")
    if bom:
        data = BOM + data
    path.write_bytes(data)


def split_funcs(argv_funcs: list[str]) -> set[str]:
    return {f for f in argv_funcs if f} or set(DEFAULT_FUNCS)


def do_extract(root: Path, out_json: Path, funcs: set[str]) -> None:
    seen: dict[str, dict] = {}
    for path in iter_txt_files(root):
        text, _ = read_text(path)
        for line in text.splitlines(keepends=True):
            m = CALL_RE.match(line)
            if not m or m.group(2) not in funcs:
                continue
            for s in STR_RE.findall(m.group(3)):
                if s == "" or s in seen:
                    continue
                seen[s] = {
                    "key": f"name_{len(seen):04d}",
                    "original": s,
                    "translation": "",
                    "stage": 0,
                }
    out_json.write_text(
        json.dumps(list(seen.values()), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"提取 {len(seen)} 条唯一字符串 -> {out_json}")


def load_table(in_json: Path) -> dict[str, tuple[bool, str]]:
    """译文先走映射，返回 {原文: (是否启用译文, 映射后的译文)}"""
    with open(in_json, encoding="utf-8") as f:
        items = json.load(f)
    table: dict[str, tuple[bool, str]] = {}
    for item in items:
        tr = item.get("translation") or ""
        if tr:
            tr = to_fullwidth(char.convert_translation(tr))
        use_tr = int(item.get("stage", 0) or 0) != 0 and tr != ""
        table[item["original"]] = (use_tr, tr)
    return table


def do_write(root: Path, in_json: Path, funcs: set[str]) -> None:
    table = load_table(in_json)

    replaced = 0
    files_changed = 0
    untranslated = 0
    unknown: set[str] = set()
    for path in iter_txt_files(root):
        text, bom = read_text(path)
        out_lines: list[str] = []
        changed = False
        for line in text.splitlines(keepends=True):
            m = CALL_RE.match(line)
            if not m or m.group(2) not in funcs:
                out_lines.append(line)
                continue
            indent, func, args, term = m.groups()
            stats = [0]  # 本行替换数

            def repl(mm: re.Match) -> str:
                nonlocal untranslated
                s = mm.group(1)
                if s == "":
                    return mm.group(0)
                entry = table.get(s)
                if entry is None:
                    unknown.add(s)
                    return mm.group(0)
                use_tr, tr = entry
                if not use_tr:
                    untranslated += 1
                    return mm.group(0)
                if '"' in tr:  # 译文含双引号会破坏语法，跳过并保持原文
                    return mm.group(0)
                stats[0] += 1
                return f'"{tr}"'

            new_args = STR_RE.sub(repl, args)
            if stats[0]:
                replaced += stats[0]
                changed = True
            out_lines.append(f"{indent}{func}({new_args}){term}")
        if changed:
            files_changed += 1
            write_text(path, "".join(out_lines), bom)
    print(f"回写 {replaced} 处，修改 {files_changed} 个文件")
    if untranslated:
        print(f"跳过未启用译文 {untranslated} 处（stage 为 0 或译文留空）")
    if unknown:
        print(f"警告：{len(unknown)} 个字符串不在 json 中（文件可能已变动），可重新提取确认")


def main() -> None:
    argv = sys.argv[1:]
    if len(argv) >= 3 and argv[0] == "e":
        do_extract(Path(argv[1]), Path(argv[2]), split_funcs(argv[3:]))
    elif len(argv) >= 3 and argv[0] == "w":
        do_write(Path(argv[1]), Path(argv[2]), split_funcs(argv[3:]))
    else:
        sys.exit(__doc__.strip())


if __name__ == "__main__":
    main()
