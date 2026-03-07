from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from . import core


_FORBIDDEN_KPRL_TOKENS = (
    "SCRIPT_BLOCK",
    "SCRIPT_BLOB_BLOCK",
    "script_blob_begin",
    "script_blob_end",
    "blob_node ",
)


def _ensure_no_legacy_block_syntax(path: Path) -> None:
    text = path.read_text(encoding="utf-8", errors="strict")
    for tok in _FORBIDDEN_KPRL_TOKENS:
        if tok in text:
            raise ValueError(f"seen2 does not support legacy block syntax: {tok}")


def read_kprl_new(
    path: Path,
    *,
    spec: dict,
    text_encoding: str,
    hashcall_map: dict[tuple[int, int, int, int], Any],
    opfmt_map: dict[object, list[Optional[str]]],
) -> tuple[bytes, int, int, Optional[str], list[Any]]:
    _ensure_no_legacy_block_syntax(path)
    return core.read_kprl(
        path,
        spec=spec,
        text_encoding=text_encoding,
        hashcall_map=hashcall_map,
        opfmt_map=opfmt_map,
    )
