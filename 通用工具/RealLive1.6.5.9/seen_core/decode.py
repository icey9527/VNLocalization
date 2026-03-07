from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from . import core


def decode_file(
    in_path: Path,
    out_path: Path,
    *,
    spec: dict,
    text_encoding: str,
    hashcall_map: dict[tuple[int, int, int, int], Any],
    opfmt_map: dict[object, list[Optional[str]]],
    asm_strict: bool = True,
) -> None:
    core.decode_one(
        in_path,
        out_path,
        spec=spec,
        text_encoding=text_encoding,
        hashcall_map=hashcall_map,
        opfmt_map=opfmt_map,
        asm_strict=asm_strict,
    )
