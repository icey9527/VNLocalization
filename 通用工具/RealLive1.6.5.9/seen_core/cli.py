from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import core
from .decode import decode_file
from .encode import encode_file


def _iter_files_for_decode(in_path: Path) -> list[Path]:
    if in_path.is_file():
        return [in_path]
    return sorted([p for p in in_path.rglob("Seen*.txt") if p.is_file()])


def _iter_files_for_encode(in_path: Path) -> list[Path]:
    if in_path.is_file():
        return [in_path]
    return sorted([p for p in in_path.rglob("*.asm") if p.is_file()])


def _merge_opfmt_maps(paths: list[Path]) -> dict[object, list[Any]]:
    out: dict[object, list[Any]] = {}
    for p in paths:
        m = core._load_opcode_fmt_map(p)
        for k, v in m.items():
            if k not in out:
                out[k] = list(v)
                continue
            cur = out[k]
            for x in v:
                if x not in cur:
                    cur.append(x)
    return out


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(prog="seen2.py")
    ap.add_argument("mode", choices=["d", "e"], help="d: decode SEEN to .asm, e: encode .asm to SEEN")
    ap.add_argument("inp", type=Path, help="input file or directory")
    ap.add_argument("out", type=Path, help="output file or directory")
    ap.add_argument("-i", dest="text_encoding", default="cp932", help="text encoding for script bytes (default: cp932)")
    ap.add_argument("--reloc-mode", choices=["best-effort", "strict", "off", "len-lock"], default="best-effort", help="relocation mode for encode")
    ap.add_argument("--reloc-report", type=Path, default=None, help="write relocation report json")
    args = ap.parse_args()

    # Fixed project defaults (user-facing CLI kept minimal).
    spec = core._load_spec(Path("spec.json"))
    target_ver = core._parse_version_str("1.6.5.9")
    kfn_defs = core._load_kfn_defs(Path("src/reallive.kfn"), target_version=target_ver)
    hashcall_map = core._build_hashcall_map(kfn_defs)
    opfmt_map = _merge_opfmt_maps(
        [
            Path("opcode_fmt_map.json"),
            Path("opcode_fmt_map_extra.json"),
            Path("opcode_fmt_map_ida.json"),
        ]
    )

    if args.mode == "d":
        files = _iter_files_for_decode(args.inp)
        if not files:
            raise SystemExit("no input files")
        if args.inp.is_dir():
            args.out.mkdir(parents=True, exist_ok=True)
            for f in files:
                rel = f.relative_to(args.inp)
                out_file = (args.out / rel).with_suffix(".asm")
                out_file.parent.mkdir(parents=True, exist_ok=True)
                decode_file(
                    f,
                    out_file,
                    spec=spec,
                    text_encoding=args.text_encoding,
                    hashcall_map=hashcall_map,
                    opfmt_map=opfmt_map,
                    asm_strict=True,
                )
        else:
            decode_file(
                args.inp,
                args.out,
                spec=spec,
                text_encoding=args.text_encoding,
                hashcall_map=hashcall_map,
                opfmt_map=opfmt_map,
                asm_strict=True,
            )
        return

    files = _iter_files_for_encode(args.inp)
    if not files:
        raise SystemExit("no input files")
    reports: list[dict[str, Any]] = []
    if args.inp.is_dir():
        args.out.mkdir(parents=True, exist_ok=True)
        for f in files:
            rel = f.relative_to(args.inp)
            out_file = (args.out / rel).with_suffix(".txt")
            out_file.parent.mkdir(parents=True, exist_ok=True)
            try:
                rep = encode_file(
                    f,
                    out_file,
                    spec=spec,
                    text_encoding=args.text_encoding,
                    hashcall_map=hashcall_map,
                    opfmt_map=opfmt_map,
                    reloc_mode=args.reloc_mode,
                )
            except Exception as e:
                raise RuntimeError(f"encode failed for {f}") from e
            rep["input"] = str(f)
            rep["output"] = str(out_file)
            reports.append(rep)
    else:
        rep = encode_file(
            args.inp,
            args.out,
            spec=spec,
            text_encoding=args.text_encoding,
            hashcall_map=hashcall_map,
            opfmt_map=opfmt_map,
            reloc_mode=args.reloc_mode,
        )
        rep["input"] = str(args.inp)
        rep["output"] = str(args.out)
        reports.append(rep)

    if args.reloc_report is not None:
        args.reloc_report.parent.mkdir(parents=True, exist_ok=True)
        payload: Any = reports[0] if len(reports) == 1 else reports
        args.reloc_report.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
