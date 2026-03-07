from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class FunCall:
    name: str
    args: list[str]
    jump_target_hex: Optional[str] = None
    jump_table_text: Optional[str] = None
    sig: Optional[str] = None


@dataclass
class AstDoc:
    header: bytes
    ver: int
    xlen: int
    text_encoding: str
    nodes: list[Any]

