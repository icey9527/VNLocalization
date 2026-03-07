from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from . import core


def write_kprl_new(
    path: Path,
    *,
    header: bytes,
    ver: int,
    xlen: int,
    text_encoding: str,
    nodes: list[Any],
    spec: dict,
    hashcall_map: dict[tuple[int, int, int, int], Any],
    opfmt_map: dict[object, list[Optional[str]]],
) -> None:
    core.write_kprl(
        path,
        header=header,
        ver=ver,
        xlen=xlen,
        text_encoding=text_encoding,
        nodes=nodes,
        spec=spec,
        hashcall_map=hashcall_map,
        opfmt_map=opfmt_map,
    )
