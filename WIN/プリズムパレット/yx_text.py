#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

SYS_RE = re.compile(r"\bSYS\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)", re.IGNORECASE)
SECTION_RE = re.compile(r"^\s*\[[^\]]+\]\s*$")
TEXT_ARG_RE = re.compile(r"^\s*C1\s*\(\s*0\s*\)\s*A\s*\(\s*[02]\s*,", re.IGNORECASE)
B_STR_RE = re.compile(r'\bB\s*\(\s*(\d+)\s*,\s*"((?:[^"\\]|\\.)*)"\s*\)')

SYS_ALLOWLIST: set[int] = {4, 12, 38, 41, 42, 47, 64, 197, 200, 205, 206, 207, 217, 229, 235}


@dataclass(frozen=True)
class Extracted:
    file: Path
    sys_line_no: int
    arg_line_no: int
    sys_id: int
    arg_index: int
    text: str


def iter_asm_files(path: Path) -> Iterable[Path]:
    if path.is_file():
        raise ValueError(f"input_dir must be a directory, got file: {path}")
    for p in sorted(path.rglob("*.asm")):
        if p.is_file():
            yield p


def parse_sys_call(line: str) -> Optional[tuple[int, int]]:
    m = SYS_RE.search(line)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def extract_b_second_param_as_text(line: str) -> list[str]:
    """
    Extract the B(...) second parameter if it is a quoted string.
    Returns all string literals found in the line (some lines can have multiple B(...) / C(...)).
    """
    out: list[str] = []
    for m in B_STR_RE.finditer(line):
        b_ty = int(m.group(1))
        if b_ty != 6:
            continue
        out.append(m.group(2))
    return out


def _find_closing_brace(s: str, start: int) -> int:
    i = start
    while i < len(s):
        if s[i] == "}":
            return i
        i += 1
    return -1


def split_sys38_text(s: str) -> list[str]:
    cmd = set("@LOPRSWbcdhlmprsw")
    out: list[str] = []
    buf: list[str] = []
    i = 0

    def flush() -> None:
        if buf:
            out.append("".join(buf))
            buf.clear()

    while i < len(s):
        ch = s[i]
        if ch != "\\" or i + 1 >= len(s):
            buf.append(ch)
            i += 1
            continue

        k = s[i + 1]
        if k not in cmd:
            buf.append("\\")
            i += 1
            continue

        if k == "m":
            if i + 2 < len(s) and s[i + 2] in ("f", "l"):
                buf.append(s[i : i + 3])
                i += 3
            else:
                buf.append("\\m")
                i += 2
            continue

        flush()

        if k in ("L", "p", "s", "h", "l"):
            i += 2
            continue

        if k in ("c", "w", "W"):
            j = i + 2
            while j < len(s) and s[j].isdigit():
                j += 1
            if j < len(s) and s[j] == ";":
                j += 1
            i = j
            continue

        if k == "b" and i + 2 < len(s) and s[i + 2] == "{":
            end = _find_closing_brace(s, i + 3)
            if end == -1:
                i += 2
                continue
            inner = s[i + 3 : end]
            for part in split_sys38_text(inner):
                if part:
                    out.append(part)
            i = end + 1
            continue

        i += 2

    flush()
    return [x for x in out if x]


def _trim_edge_newlines(part: str) -> tuple[str, int, int]:
    pre = 0
    suf = 0
    while part.startswith("\\n"):
        pre += 1
        part = part[2:]
    while part.endswith("\\n"):
        suf += 1
        part = part[:-2]
    return part, pre, suf


def _esc_quotes(s: str) -> str:
    return s.replace('"', r"\"")


def _split_sys38_skeleton(s: str) -> tuple[list[object], list[str]]:
    cmd = set("@LOPRSWbcdhlmprsw")
    skel: list[object] = []
    segs: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        if buf:
            segs.append("".join(buf))
            skel.append(len(segs) - 1)
            buf.clear()

    i = 0
    while i < len(s):
        ch = s[i]
        if ch != "\\" or i + 1 >= len(s):
            buf.append(ch)
            i += 1
            continue

        k = s[i + 1]
        if k not in cmd:
            buf.append("\\")
            i += 1
            continue

        if k == "m":
            if i + 2 < len(s) and s[i + 2] in ("f", "l"):
                buf.append(s[i : i + 3])
                i += 3
            else:
                buf.append("\\m")
                i += 2
            continue

        flush()

        if k in ("L", "p", "s", "h", "l"):
            skel.append(s[i : i + 2])
            i += 2
            continue

        if k in ("c", "w", "W"):
            j = i + 2
            while j < len(s) and s[j].isdigit():
                j += 1
            if j < len(s) and s[j] == ";":
                j += 1
            skel.append(s[i:j])
            i = j
            continue

        if k == "b" and i + 2 < len(s) and s[i + 2] == "{":
            end = _find_closing_brace(s, i + 3)
            if end == -1:
                skel.append("\\b")
                i += 2
                continue
            skel.append("\\b{")
            inner_skel, inner_segs = _split_sys38_skeleton(s[i + 3 : end])
            off = len(segs)
            segs.extend(inner_segs)
            for x in inner_skel:
                skel.append(x + off if isinstance(x, int) else x)
            skel.append("}")
            i = end + 1
            continue

        skel.append(s[i : i + 2])
        i += 2

    flush()
    return skel, segs


def _rebuild_sys38(original: str, repl: dict[int, str]) -> str:
    skel, segs = _split_sys38_skeleton(original)
    out: list[str] = []
    for x in skel:
        if isinstance(x, int):
            seg = segs[x]
            core, pre, suf = _trim_edge_newlines(seg)
            new_core = repl.get(x + 1, core)
            out.append("\\n" * pre + new_core + "\\n" * suf)
        else:
            out.append(x)
    return "".join(out)


def extract_from_file(path: Path, sys_allow: set[int]) -> tuple[list[Extracted], set[int], dict[int, tuple[int, int]]]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    lines = raw.splitlines(keepends=True)

    extracted: list[Extracted] = []
    extracted_line_nos: set[int] = set()
    sys_meta: dict[int, tuple[int, int]] = {}

    block: list[tuple[int, str]] = []

    for idx, line in enumerate(lines):
        line_no = idx + 1

        if SECTION_RE.match(line):
            block.clear()
            continue

        parsed = parse_sys_call(line)
        if parsed:
            sys_id, argc = parsed
            sys_meta[line_no] = (sys_id, argc)

            if sys_id in sys_allow:
                candidates: list[tuple[int, str]] = []
                for b_line_no, b_line in block:
                    if not TEXT_ARG_RE.match(b_line):
                        continue
                    for text in extract_b_second_param_as_text(b_line):
                        candidates.append((b_line_no, text))

                if sys_id == 41:
                    candidates = candidates[1:] if len(candidates) >= 2 else []

                for arg_pos, (b_line_no, text) in enumerate(candidates, start=1):
                    extracted.append(
                        Extracted(
                            file=path,
                            sys_line_no=line_no,
                            arg_line_no=b_line_no,
                            sys_id=sys_id,
                            arg_index=arg_pos,
                            text=text,
                        )
                    )
                    extracted_line_nos.add(b_line_no)

            block.clear()
            continue

        block.append((line_no, line))

    return extracted, extracted_line_nos, sys_meta


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="ASM text extractor (SYS-block based, section-safe).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ap_e = sub.add_parser("e", help="Extract: asm folder -> txt folder (+ lines.txt index)")
    ap_e.add_argument("asm_dir", help="Input folder containing .asm files")
    ap_e.add_argument("txt_dir", help="Output folder for .txt and lines.txt")

    ap_w = sub.add_parser("w", help="Write-back (reserved, not implemented yet)")
    ap_w.add_argument("asm_dir", help="Input asm folder")
    ap_w.add_argument("txt_dir", help="Input txt folder")
    ap_w.add_argument("new_asm_dir", help="Output new asm folder")

    args = ap.parse_args(argv)

    if args.cmd == "w":
        asm_dir = Path(args.asm_dir)
        txt_dir = Path(args.txt_dir)
        new_asm_dir = Path(args.new_asm_dir)
        new_asm_dir.mkdir(parents=True, exist_ok=True)

        by_file: dict[str, dict[int, dict[int, str] | str]] = {}
        for line in (txt_dir / "lines.txt").read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            parts = line.split()
            if len(parts) not in (3, 4):
                continue
            fn = parts[0]
            asm_ln = int(parts[1])
            txt_ln = int(parts[2])
            seg = int(parts[3]) if len(parts) == 4 else None

            txt_path = txt_dir / f"{Path(fn).stem}.txt"
            txt_lines = txt_path.read_text(encoding="utf-8", errors="replace").splitlines()
            if not (1 <= txt_ln <= len(txt_lines)):
                continue
            val = txt_lines[txt_ln - 1]

            f = by_file.setdefault(fn, {})
            if seg is None:
                f[asm_ln] = val
            else:
                d = f.get(asm_ln)
                if not isinstance(d, dict):
                    d = {}
                    f[asm_ln] = d
                d[seg] = val

        for asm_path in iter_asm_files(asm_dir):
            rel = asm_path.relative_to(asm_dir)
            out_path = new_asm_dir / rel
            out_path.parent.mkdir(parents=True, exist_ok=True)

            edits = by_file.get(asm_path.name)
            if not edits:
                out_path.write_text(asm_path.read_text(encoding="utf-8", errors="replace"), encoding="utf-8", newline="")
                continue

            raw = asm_path.read_text(encoding="utf-8", errors="replace")
            lines = raw.splitlines(keepends=True)
            for ln, spec in edits.items():
                if not (1 <= ln <= len(lines)):
                    continue
                line = lines[ln - 1]
                m = B_STR_RE.search(line)
                if not m or int(m.group(1)) != 6:
                    continue
                orig = m.group(2)
                if isinstance(spec, dict):
                    rebuilt = _rebuild_sys38(orig, spec)
                    new_txt = rebuilt
                else:
                    core_new, _, _ = _trim_edge_newlines(spec)
                    core_old, pre, suf = _trim_edge_newlines(orig)
                    new_txt = "\\n" * pre + core_new + "\\n" * suf
                rep = f'B(6,"{_esc_quotes(new_txt)}")'
                lines[ln - 1] = line[: m.start()] + rep + line[m.end() :]
            out_path.write_text("".join(lines), encoding="utf-8", newline="")

        return 0

    in_path = Path(args.asm_dir)
    out_dir = Path(args.txt_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not SYS_ALLOWLIST:
        raise SystemExit("ERROR: SYS_ALLOWLIST is empty; fill it in extract_asm_text.py")

    lines_index = out_dir / "lines.txt"
    with lines_index.open("w", encoding="utf-8", newline="") as idxf:
        for asm_path in iter_asm_files(in_path):
            extracted, _extracted_line_nos, _sys_meta = extract_from_file(asm_path, SYS_ALLOWLIST)

            out_txt = out_dir / f"{asm_path.stem}.txt"
            txt_line_no = 0

            with out_txt.open("w", encoding="utf-8", newline="") as outf:
                for item in extracted:
                    parts = split_sys38_text(item.text) if item.sys_id == 38 else [item.text]
                    write_seg = item.sys_id == 38
                    for seg_no, part in enumerate(parts, start=1):
                        core, pre_nl, suf_nl = _trim_edge_newlines(part)
                        if core.replace("\\n", "").strip(" \t\r") == "":
                            continue
                        txt_line_no += 1
                        outf.write(core + "\n")
                        if write_seg:
                            idxf.write(f"{asm_path.name} {item.arg_line_no} {txt_line_no} {seg_no}\n")
                        else:
                            idxf.write(f"{asm_path.name} {item.arg_line_no} {txt_line_no}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
