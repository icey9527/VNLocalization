#!/usr/bin/env python3
from __future__ import annotations
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Iterable

sys.dont_write_bytecode = True

def u16le(b: bytes, i: int) -> int: return b[i] | (b[i+1] << 8)
def u24le(b: bytes, i: int) -> int: return b[i] | (b[i+1] << 8) | (b[i+2] << 16)
def u32le(b: bytes, i: int) -> int: return int.from_bytes(b[i:i+4], "little", signed=False)
def p16le(v: int) -> bytes: return int(v & 0xFFFF).to_bytes(2, "little", signed=False)
def p24le(v: int) -> bytes: return int(v & 0xFFFFFF).to_bytes(3, "little", signed=False)
def p32le(v: int) -> bytes: return int(v & 0xFFFFFFFF).to_bytes(4, "little", signed=False)

def parse_seen_hdr(buf: bytes) -> tuple[int,int,int]:
    return (u32le(buf,0x04), u32le(buf,0x20), u32le(buf,0x28))

def _patch_seen_payload_len_in_header(header: bytes, payload_len: int) -> bytes:
    # For this title's SEEN files, header[0x24:0x28] stores the payload length (file_size - header_off).
    # If we edit text, payload size changes, and leaving this field stale can crash the VM loader.
    if len(header) < 0x28:
        raise ValueError(f"SEEN header too small: {len(header)} bytes")
    h = bytearray(header)
    h[0x24:0x28] = p32le(payload_len)
    return bytes(h)

SEEN_XOR_KEY_256 = bytes([
    0x8B,0xE5,0x5D,0xC3,0xA1,0xE0,0x30,0x44,0x00,0x85,0xC0,0x74,0x09,0x5F,0x5E,0x33,
    0xC0,0x5B,0x8B,0xE5,0x5D,0xC3,0x8B,0x45,0x0C,0x85,0xC0,0x75,0x14,0x8B,0x55,0xEC,
    0x83,0xC2,0x20,0x52,0x6A,0x00,0xE8,0xF5,0x28,0x01,0x00,0x83,0xC4,0x08,0x89,0x45,
    0x0C,0x8B,0x45,0xE4,0x6A,0x00,0x6A,0x00,0x50,0x53,0xFF,0x15,0x34,0xB1,0x43,0x00,
    0x8B,0x45,0x10,0x85,0xC0,0x74,0x05,0x8B,0x4D,0xEC,0x89,0x08,0x8A,0x45,0xF0,0x84,
    0xC0,0x75,0x78,0xA1,0xE0,0x30,0x44,0x00,0x8B,0x7D,0xE8,0x8B,0x75,0x0C,0x85,0xC0,
    0x75,0x44,0x8B,0x1D,0xD0,0xB0,0x43,0x00,0x85,0xFF,0x76,0x37,0x81,0xFF,0x00,0x00,
    0x04,0x00,0x6A,0x00,0x76,0x43,0x8B,0x45,0xF8,0x8D,0x55,0xFC,0x52,0x68,0x00,0x00,
    0x04,0x00,0x56,0x50,0xFF,0x15,0x2C,0xB1,0x43,0x00,0x6A,0x05,0xFF,0xD3,0xA1,0xE0,
    0x30,0x44,0x00,0x81,0xEF,0x00,0x00,0x04,0x00,0x81,0xC6,0x00,0x00,0x04,0x00,0x85,
    0xC0,0x74,0xC5,0x8B,0x5D,0xF8,0x53,0xE8,0xF4,0xFB,0xFF,0xFF,0x8B,0x45,0x0C,0x83,
    0xC4,0x04,0x5F,0x5E,0x5B,0x8B,0xE5,0x5D,0xC3,0x8B,0x55,0xF8,0x8D,0x4D,0xFC,0x51,
    0x57,0x56,0x52,0xFF,0x15,0x2C,0xB1,0x43,0x00,0xEB,0xD8,0x8B,0x45,0xE8,0x83,0xC0,
    0x20,0x50,0x6A,0x00,0xE8,0x47,0x28,0x01,0x00,0x8B,0x7D,0xE8,0x89,0x45,0xF4,0x8B,
    0xF0,0xA1,0xE0,0x30,0x44,0x00,0x83,0xC4,0x08,0x85,0xC0,0x75,0x56,0x8B,0x1D,0xD0,
    0xB0,0x43,0x00,0x85,0xFF,0x76,0x49,0x81,0xFF,0x00,0x00,0x04,0x00,0x6A,0x00,0x76,
])

SEEN_XOR_KEY16_V1 = bytes([
    0xB5, 0x1F, 0xD1, 0x5C, 0x85, 0x17, 0x57, 0x37,
    0xA6, 0x3B, 0x8A, 0x42, 0x1A, 0x7C, 0xC1, 0x87,
])

def _is_sjis_lead(c: int) -> bool:
    return (0x81 <= c <= 0x9F) or (0xE0 <= c <= 0xFC)

def _sjis_upper_ascii_inplace(buf: bytearray) -> None:
    i = 0
    while i < len(buf):
        c = buf[i]
        if _is_sjis_lead(c) and i + 1 < len(buf):
            i += 2
            continue
        if 0x61 <= c <= 0x7A:  # a-z
            buf[i] = c - 0x20
        i += 1

_SEEN_XOR_KEY16_V2_CACHE: dict[str, bytes] = {}

def _compute_seen_xor_key16_v2_from_exe(exe_path: Path) -> bytes:
    # From sub_C8A1E0: read the whole module file, XOR it with a key derived from the
    # leaf exe name, then MD5 the result. The digest becomes the 16-byte key stored at
    # dword_28509E8, used to XOR bytes [0x180..0x280] in SEEN payloads when ver/1000000%10 != 0.
    data = bytearray(exe_path.read_bytes())

    # Key string: leaf filename of GetModuleFileNameA (after last '\\'), then ASCII uppercase.
    key = bytearray(exe_path.name.encode("cp932", errors="replace"))
    _sjis_upper_ascii_inplace(key)
    if not key:
        raise ValueError("empty exe filename key")

    for i in range(len(key)):
        key[i] ^= SEEN_XOR_KEY_256[i & 0xFF]

    for i in range(len(data)):
        data[i] ^= key[i % len(key)]

    return hashlib.md5(data).digest()

def _get_seen_xor_key16_v2(exe_path: Optional[Path] = None) -> bytes:
    if exe_path is None:
        candidates = [Path.cwd() / "RealLive.exe", Path(__file__).with_name("RealLive.exe")]
        exe_path = next((p for p in candidates if p.is_file()), None)
    if exe_path is None:
        raise ValueError("need RealLive.exe to derive ver/1000000 XOR key (place next to seen.py or run from its folder)")

    k = str(exe_path.resolve())
    if k in _SEEN_XOR_KEY16_V2_CACHE:
        return _SEEN_XOR_KEY16_V2_CACHE[k]
    v = _compute_seen_xor_key16_v2_from_exe(exe_path)
    _SEEN_XOR_KEY16_V2_CACHE[k] = v
    return v

def apply_seen_xor_layer(payload: bytearray, xlen: int) -> None:
    xlen = min(max(xlen, 0), len(payload))
    for i in range(xlen):
        payload[i] ^= SEEN_XOR_KEY_256[i & 0xFF]

def apply_seen_version_layers(payload: bytearray, ver: int, *, exe_path: Optional[Path] = None) -> None:
    # From sub_CD0680:
    # - (ver / 100000 % 10) == 1: XOR bytes [0x100..0x200] with a 16-byte key
    # - (ver / 1000000 % 10) != 0: XOR bytes [0x180..0x280] with another 16-byte key
    # The 2nd key is MD5(CODE_DATA xor f(exe_name)) stored at dword_28509E8.
    v1 = (ver // 100000) % 10
    if v1 == 1:
        start = 0x100
        end = min(0x201, len(payload))
        for i in range(start, end):
            payload[i] ^= SEEN_XOR_KEY16_V1[(i - start) & 0xF]

    v2 = (ver // 1000000) % 10
    if v2:
        key16 = _get_seen_xor_key16_v2(exe_path)
        start = 0x180
        end = min(0x281, len(payload))
        for i in range(start, end):
            payload[i] ^= key16[(i - start) & 0xF]

@dataclass
class Node:
    kind: str
    data: dict[str, Any]

@dataclass
class KfnOpDef:
    name: str
    op_type: int
    op_module: int
    op_function: int
    overload: int
    flags: set[str]
    param_sigs: list[list[str]]

# Expression variable naming (RLdev-style)
IVAR_PREFIX = "%"
SVAR_PREFIX = "$"

_VAR_ID_TO_NAME: dict[int, str] = {
    0x0A: f"{SVAR_PREFIX}K", 0x0B: f"{IVAR_PREFIX}L",
    0x0C: f"{SVAR_PREFIX}M", 0x12: f"{SVAR_PREFIX}S",
    0x00: f"{IVAR_PREFIX}A", 0x01: f"{IVAR_PREFIX}B",
    0x02: f"{IVAR_PREFIX}C", 0x03: f"{IVAR_PREFIX}D",
    0x04: f"{IVAR_PREFIX}E", 0x05: f"{IVAR_PREFIX}F",
    0x06: f"{IVAR_PREFIX}G", 0x19: f"{IVAR_PREFIX}Z",
    0x1A: f"{IVAR_PREFIX}Ab", 0x1B: f"{IVAR_PREFIX}Bb",
    0x1C: f"{IVAR_PREFIX}Cb", 0x1D: f"{IVAR_PREFIX}Db",
    0x1E: f"{IVAR_PREFIX}Eb", 0x1F: f"{IVAR_PREFIX}Fb",
    0x20: f"{IVAR_PREFIX}Gb", 0x33: f"{IVAR_PREFIX}Zb",
    0x34: f"{IVAR_PREFIX}A2b", 0x35: f"{IVAR_PREFIX}B2b",
    0x36: f"{IVAR_PREFIX}C2b", 0x37: f"{IVAR_PREFIX}D2b",
    0x38: f"{IVAR_PREFIX}E2b", 0x39: f"{IVAR_PREFIX}F2b",
    0x3A: f"{IVAR_PREFIX}G2b", 0x4D: f"{IVAR_PREFIX}Z2b",
    0x4E: f"{IVAR_PREFIX}A4b", 0x4F: f"{IVAR_PREFIX}B4b",
    0x50: f"{IVAR_PREFIX}C4b", 0x51: f"{IVAR_PREFIX}D4b",
    0x52: f"{IVAR_PREFIX}E4b", 0x53: f"{IVAR_PREFIX}F4b",
    0x54: f"{IVAR_PREFIX}G4b", 0x67: f"{IVAR_PREFIX}Z4b",
    0x68: f"{IVAR_PREFIX}A8b", 0x69: f"{IVAR_PREFIX}B8b",
    0x6A: f"{IVAR_PREFIX}C8b", 0x6B: f"{IVAR_PREFIX}D8b",
    0x6C: f"{IVAR_PREFIX}E8b", 0x6D: f"{IVAR_PREFIX}F8b",
    0x6E: f"{IVAR_PREFIX}G8b", 0x81: f"{IVAR_PREFIX}Z8b",
}
_VAR_NAME_TO_ID: dict[str, int] = {v: k for k, v in _VAR_ID_TO_NAME.items()}

def _coalesce_u32_from_bytes_and_nuls(nodes: list[Node]) -> list[Node]:
    # Some handlers emit raw little-endian dwords that we don't model yet.
    # They frequently appear as: BYTES <2 bytes> then OP 00 then OP 00.
    # Keep it lossless by turning that exact 4-byte sequence into a dedicated node.

    def _fix_node(n: Node) -> Node:
        if n.kind != "Op":
            return n
        args = n.data.get("args") or {}
        par = args.get("parens")
        if not isinstance(par, dict) or "items" not in par:
            return n

        items: list[Node] = []
        for item in par.get("items", []):
            k = item.get("node_kind")
            d = {kk: vv for kk, vv in item.items() if kk != "node_kind"}
            items.append(Node(str(k), d))
        items = _coalesce_u32_from_bytes_and_nuls(items)

        args2 = dict(args)
        args2["parens"] = {"items": [{"node_kind": x.kind, **x.data} for x in items]}
        return Node("Op", {**n.data, "args": args2})

    nodes = [_fix_node(n) for n in nodes]

    out: list[Node] = []
    i = 0
    while i < len(nodes):
        def _lo2_from_node(n: Node) -> Optional[bytes]:
            if n.kind == "Bytes" and int(n.data.get("len", 0)) == 2:
                lo2 = bytes.fromhex(str(n.data.get("hex", "")))
                return lo2 if len(lo2) == 2 else None
            if n.kind == "Text":
                hx = str(n.data.get("hex", "") or "")
                if len(hx) == 4:
                    lo2 = bytes.fromhex(hx)
                    return lo2 if len(lo2) == 2 else None
            return None

        def _lo3_from_node(n: Node) -> Optional[bytes]:
            if n.kind == "Bytes" and int(n.data.get("len", 0)) == 3:
                lo3 = bytes.fromhex(str(n.data.get("hex", "")))
                return lo3 if len(lo3) == 3 else None
            if n.kind == "Text":
                hx = str(n.data.get("hex", "") or "")
                if len(hx) == 6:
                    lo3 = bytes.fromhex(hx)
                    return lo3 if len(lo3) == 3 else None
            return None

        if (
            i + 2 < len(nodes)
            and nodes[i].kind in ("Bytes", "Text")
            and nodes[i + 1].kind == "Op"
            and str(nodes[i + 1].data.get("op", "")).upper() == "00"
            and nodes[i + 2].kind == "Op"
            and str(nodes[i + 2].data.get("op", "")).upper() == "00"
        ):
            lo2 = _lo2_from_node(nodes[i])
            if lo2:
                val = lo2[0] | (lo2[1] << 8)
                raw = lo2 + b"\x00\x00"
                out.append(Node("U32", {"val": val, "_raw": raw.hex().upper()}))
                i += 3
                continue

        # Another frequent pattern in some SEENs: 24-bit little-endian value + trailing 0x00.
    # It shows up in .asm as: bytes <3 bytes> then opbyte 0x00.
        if (
            i + 1 < len(nodes)
            and nodes[i].kind in ("Bytes", "Text")
            and nodes[i + 1].kind == "Op"
            and str(nodes[i + 1].data.get("op", "")).upper() == "00"
        ):
            lo3 = _lo3_from_node(nodes[i])
            if lo3:
                val = lo3[0] | (lo3[1] << 8) | (lo3[2] << 16)
                raw = lo3 + b"\x00"
                out.append(Node("U32", {"val": val, "_raw": raw.hex().upper()}))
                i += 2
                continue

        out.append(nodes[i])
        i += 1
    return out

def _coalesce_small_bytes(nodes: list[Node]) -> list[Node]:
    def fix_node(n: Node) -> Node:
        if n.kind != "Op":
            return n
        args = n.data.get("args") or {}
        par = args.get("parens")
        if not isinstance(par, dict) or "items" not in par:
            return n
        items: list[Node] = []
        for item in par.get("items", []):
            k = item.get("node_kind")
            d = {kk: vv for kk, vv in item.items() if kk != "node_kind"}
            items.append(Node(str(k), d))
        items = _coalesce_small_bytes(items)
        args2 = dict(args)
        args2["parens"] = {"items": [{"node_kind": x.kind, **x.data} for x in items]}
        return Node("Op", {**n.data, "args": args2})

    nodes = [fix_node(n) for n in nodes]

    out: list[Node] = []
    for n in nodes:
        if n.kind == "Bytes" and int(n.data.get("len", 0)) in (1, 2):
            hx = str(n.data.get("hex", "") or "").upper()
            if len(hx) == int(n.data.get("len", 0)) * 2:
                raw = bytes.fromhex(hx)
                if len(raw) == 1:
                    out.append(Node("U8", {"val": raw[0], "_raw": hx}))
                    continue
                if len(raw) == 2:
                    out.append(Node("U16", {"val": raw[0] | (raw[1] << 8), "_raw": hx}))
                    continue
        out.append(n)
    return out

def _coalesce_qbytes(nodes: list[Node]) -> list[Node]:
    def fix_node(n: Node) -> Node:
        if n.kind != "Op":
            return n
        args = n.data.get("args") or {}
        par = args.get("parens")
        if not isinstance(par, dict) or "items" not in par:
            return n
        items: list[Node] = []
        for item in par.get("items", []):
            k = item.get("node_kind")
            d = {kk: vv for kk, vv in item.items() if kk != "node_kind"}
            items.append(Node(str(k), d))
        items = _coalesce_qbytes(items)
        args2 = dict(args)
        args2["parens"] = {"items": [{"node_kind": x.kind, **x.data} for x in items]}
        return Node("Op", {**n.data, "args": args2})

    nodes = [fix_node(n) for n in nodes]

    out: list[Node] = []
    for n in nodes:
        if n.kind == "Bytes":
            hx = str(n.data.get("hex", "") or "").upper()
            if len(hx) >= 4 and hx.startswith("22") and hx.endswith("22"):
                out.append(Node("QBytes", {"len": len(hx) // 2, "hex": hx}))
                continue
        out.append(n)
    return out

def _coalesce_bytes_02_paren_ascii(nodes: list[Node]) -> list[Node]:
    out: list[Node] = []
    for n in nodes:
        if n.kind == "Bytes":
            hx = str(n.data.get("hex", "") or "").upper()
            raw = bytes.fromhex(hx) if hx else b""
            if len(raw) >= 3 and raw[0] == 0x02 and raw[1] == 0x28 and all(0x20 <= b <= 0x7E for b in raw[2:]):
                out.append(Node("U8", {"val": 0x02, "_raw": "02"}))
                out.append(Node("Sym", {"ch": "("}))
                out.append(Node("Text", {"text": raw[2:].decode("ascii", errors="strict")}))
                continue
        out.append(n)
    return out

def _coalesce_jump_target_u32(nodes: list[Node]) -> list[Node]:
    def fix_node(n: Node) -> Node:
        if n.kind != "Op":
            return n
        args = n.data.get("args") or {}
        par = args.get("parens")
        if not isinstance(par, dict) or "items" not in par:
            return n
        items: list[Node] = []
        for item in par.get("items", []):
            k = item.get("node_kind")
            d = {kk: vv for kk, vv in item.items() if kk != "node_kind"}
            items.append(Node(str(k), d))
        items = _coalesce_jump_target_u32(items)
        args2 = dict(args)
        args2["parens"] = {"items": [{"node_kind": x.kind, **x.data} for x in items]}
        return Node("Op", {**n.data, "args": args2})

    def scalar_bytes(n: Node) -> Optional[bytes]:
        if n.kind == "U32":
            v = int(n.data.get("val", 0)) & 0xFFFFFFFF
            return v.to_bytes(4, "little", signed=False)
        if n.kind == "U16":
            v = int(n.data.get("val", 0)) & 0xFFFF
            return v.to_bytes(2, "little", signed=False)
        if n.kind == "U8":
            v = int(n.data.get("val", 0)) & 0xFF
            return bytes([v])
        if n.kind == "Bytes":
            hx = str(n.data.get("hex", "") or "").upper()
            ln = int(n.data.get("len", 0))
            if ln in (1, 2, 4) and len(hx) >= ln * 2:
                try:
                    return bytes.fromhex(hx[: ln * 2])
                except Exception:
                    return None
            return None
        if n.kind == "Text":
            hx = str(n.data.get("hex", "") or "").upper()
            if not hx:
                return None
            if len(hx) in (2, 4, 8):
                try:
                    return bytes.fromhex(hx)
                except Exception:
                    return None
            return None
        if n.kind == "Sym":
            ch = str(n.data.get("ch", ""))
            if len(ch) == 1:
                v = ord(ch)
                if 0 <= v <= 0xFF:
                    return bytes([v])
            return None
        if n.kind == "OpByte":
            try:
                return bytes([int(str(n.data.get("op", "00")), 16) & 0xFF])
            except Exception:
                return None
        if n.kind == "Op":
            op = str(n.data.get("op", "")).upper()
            if op != "23" and not n.data.get("args"):
                try:
                    return bytes([int(op, 16) & 0xFF])
                except Exception:
                    return None
        return None

    nodes = [fix_node(n) for n in nodes]
    out: list[Node] = []
    i = 0
    while i < len(nodes):
        n = nodes[i]
        if n.kind == "Op" and str(n.data.get("op", "")).upper() == "23":
            a = n.data.get("args", {})
            g = int(a.get("group", 0))
            s = int(a.get("sub", 0))
            f = int(a.get("op16", 0))
            if (g, s, f) in ((0, 1, 0),):
                buf = bytearray()
                j = i + 1
                while j < len(nodes) and len(buf) < 4:
                    b = scalar_bytes(nodes[j])
                    if b is None:
                        break
                    if len(buf) + len(b) > 4:
                        break
                    buf += b
                    j += 1
                if len(buf) == 4:
                    out.append(n)
                    v = int.from_bytes(bytes(buf), "little", signed=False)
                    out.append(Node("U32", {"val": v, "_raw": bytes(buf).hex().upper()}))
                    i = j
                    continue
        out.append(n)
        i += 1
    return out

def _is_jump_hashcall_op(n: Optional[Node]) -> bool:
    if not n or n.kind != "Op":
        return False
    if str(n.data.get("op", "")).upper() != "23":
        return False
    a = n.data.get("args", {})
    g = int(a.get("group", 0))
    s = int(a.get("sub", 0))
    f = int(a.get("op16", 0))
    return (g, s, f) in ((0, 1, 0), (0, 1, 2))

def _is_jump_table_hashcall_op(n: Optional[Node]) -> bool:
    if not n or n.kind != "Op":
        return False
    if str(n.data.get("op", "")).upper() != "23":
        return False
    a = n.data.get("args", {})
    g = int(a.get("group", 0))
    s = int(a.get("sub", 0))
    f = int(a.get("op16", 0))
    return (g, s, f) in ((0, 1, 3), (0, 1, 4), (0, 1, 8), (0, 1, 9))

def _scan_jump_table_block(b: bytes, start: int, n: Node) -> Optional[int]:
    if start >= len(b) or b[start] != 0x7B:  # '{'
        return None
    if n.kind != "Op" or str(n.data.get("op", "")).upper() != "23":
        return None
    a = n.data.get("args", {})
    g = int(a.get("group", 0))
    s = int(a.get("sub", 0))
    f = int(a.get("op16", 0))
    argc = int(a.get("argc", 0))
    i = start + 1
    # goto_case / gosub_case: { (expr) u32 ... }
    if (g, s, f) in ((0, 1, 4), (0, 1, 9)):
        for _ in range(argc):
            if i >= len(b) or b[i] != 0x28:
                return None
            p = _find_matching_paren(b, i)
            if p is None:
                return None
            i = p + 1
            if i + 4 > len(b):
                return None
            i += 4
    # goto_on / gosub_on: { u32 ... }
    elif (g, s, f) in ((0, 1, 3), (0, 1, 8)):
        need = argc * 4
        if i + need > len(b):
            return None
        i += need
    else:
        return None
    if i >= len(b) or b[i] != 0x7D:
        return None
    return i + 1

class Decoder:
    def __init__(self, spec: dict, *, text_encoding: str = "cp932"):
        self.spec = spec
        self.text_encoding = text_encoding
        self._is_sjis = text_encoding.lower() in ("cp932", "shift_jis", "sjis")
        self.sym_map = {int(k,16): v for k,v in spec.get("symbols", {}).items()}
        self.ops = {int(o["op"],16): o for o in spec.get("ops", [])}

        pad = spec.get("padding", {})
        self.ff_min_run = int(pad.get("ff_min_run", 16))
        self.pad_word_min_run = int(pad.get("pad_word_min_run", 4))
        self.pad_words = {int(x,16) for x in pad.get("pad_words", ["FFFF","FFF3"])}

        # boundaries for bytes_until_boundary args
        self.boundary_set: set[int] = set()
        for o in spec.get("ops", []):
            for a in o.get("args", []):
                if a["type"] == "bytes_until_boundary":
                    self.boundary_set |= {int(x,16) for x in a["boundaries"]}

        # unknown handling
        unk = spec.get("unknown", {})
        self.max_blob = int(unk.get("max_blob", 4096))

        # top-level boundaries (from RealLive VM)
        self.top_ctrl = {
            0x00, 0x0A, ord('#'), ord('$'), ord(','), ord('@'), ord('!')
        }

    def is_sjis_1(self, c: int) -> bool:
        if not self._is_sjis:
            return c >= 0x20
        return c < 0x80 or (0xA0 <= c <= 0xDF)

    def is_sjis_lead(self, c: int) -> bool:
        if not self._is_sjis:
            return False
        return (0x81 <= c <= 0x9F) or (0xE0 <= c <= 0xFC)

    def parse_text_run(self, b: bytes, i: int, *, stop: set[int]) -> Optional[tuple[Node, int]]:
        if i >= len(b):
            return None
        if b[i] in stop:
            return None
        j = i
        buf = bytearray()
        while j < len(b):
            c = b[j]
            if c in stop:
                break
            if c == 0x24 and j + 1 < len(b):  # $
                break
            if c == 0x5C and j + 1 < len(b):  # \
                break
            if self.is_sjis_1(c):
                buf.append(c)
                j += 1
                continue
            if self.is_sjis_lead(c) and j + 1 < len(b):
                buf.append(c)
                buf.append(b[j + 1])
                j += 2
                continue
            break
        if not buf:
            return None
        try:
            txt = bytes(buf).decode(self.text_encoding, errors="replace")
        except Exception:
            txt = ""

        if "\ufffd" in txt:
            return Node("Bytes", {"len": len(buf), "hex": bytes(buf).hex().upper()}), j
        if any(ord(ch) < 0x20 and ch not in "\t\r\n" for ch in txt):
            return Node("Bytes", {"len": len(buf), "hex": bytes(buf).hex().upper()}), j

        return Node("Text", {"text": txt, "hex": bytes(buf).hex().upper()}), j

    # ---- padding ----
    def parse_pad(self, b: bytes, i: int) -> Optional[tuple[Node,int]]:
        if b[i] == 0xFF:
            j=i
            while j < len(b) and b[j]==0xFF: j+=1
            if j-i >= self.ff_min_run:
                return Node("PadBytes", {"byte":"FF","count": j-i}), j

        if i+1 < len(b):
            w = u16le(b,i)
            if w in self.pad_words:
                j=i; cnt=0
                while j+1 < len(b) and u16le(b,j)==w:
                    j+=2; cnt+=1
                if cnt >= self.pad_word_min_run:
                    return Node("PadWord", {"word": f"{w:04X}", "count": cnt}), j
        return None

    # ---- ctrl8194 pattern (sub_D2E580) ----
    def parse_ctrl8194(self, b: bytes, i: int) -> Optional[tuple[Node,int]]:
        if i+7 >= len(b): return None
        if u16le(b,i) != 0x8194: return None
        w1=u16le(b,i+2); w2=u16le(b,i+4); w3=u16le(b,i+6)
        if w1 not in (0x8260,0x8261): return None
        if not (0x824F <= w2 <= 0x8258): return None
        if not (0x824F <= w3 <= 0x8258): return None
        idx = (w3 + 10*w2 - 366949)
        typ = 1 if w1==0x8260 else 2
        mode = 0 if w1==0x8260 else 1
        return Node("Ctrl8194", {"type":typ,"mode":mode,"idx":idx}), i+8

    # ---- $ and \ ----
    def parse_dollar(self, b: bytes, i: int, *, stop: Optional[set[int]] = None) -> tuple[Node, int]:
        t = b[i + 1]
        if t == 0xFF:
            val = u32le(b, i + 2)
            return Node("Dollar", {"kind": "FF", "val": val}), i + 6
        j = i + 2
        br = (j < len(b) and b[j] == 0x5B)
        if br:
            j += 1

        expr_start = j
        # In the real VM, '$' payload is context-sensitive.
        # - If bracketed ($X[...]), it is terminated by ']'.
        # - Otherwise, it is usually terminated by higher-level control tokens.
        if br:
            while j < len(b) and b[j] != 0x5D:  # ']'
                j += 1
            expr = b[expr_start:j]
            if j < len(b) and b[j] == 0x5D:
                j += 1
        else:
            stop_set = stop or self.top_ctrl
            while j < len(b) and b[j] not in stop_set:
                j += 1
            expr = b[expr_start:j]
        return Node(
            "Dollar",
            {
                "kind": f"{t:02X}",
                "bracket": br,
                "expr_text": expr.decode(self.text_encoding, errors="replace"),
                "expr_hex": expr.hex().upper(),
            },
        ), j

    def parse_esc(self, b: bytes, i: int) -> tuple[Node,int]:
        return Node("Esc", {"x": f"{b[i+1]:02X}"}), i+2

    # ---- op table ----
    def parse_op(self, b: bytes, i: int) -> Optional[tuple[Node,int]]:
        op = b[i]
        if op not in self.ops:
            return None
        info = self.ops[op]
        j = i+1
        args: dict[str, Any] = {}
        for a in info.get("args", []):
            t=a["type"]; nm=a["name"]
            if t=="u8":
                args[nm]=b[j]; j+=1
            elif t=="u16":
                args[nm]=u16le(b,j); j+=2
            elif t=="u24":
                args[nm]=u24le(b,j); j+=3
            elif t=="bytes_until_boundary":
                maxn=int(a.get("max",0))
                bounds={int(x,16) for x in a["boundaries"]}
                buf=bytearray()
                for _ in range(maxn):
                    if j>=len(b) or b[j] in bounds: break
                    buf.append(b[j]); j+=1
                args[nm]=buf.hex().upper()
            else:
                raise ValueError(f"unknown arg type {t}")

        # HashCall: optional (...) payload right after overload.
        # Jump-family hashcalls (goto/goto_unless/goto_case/goto_on/gosub_*)
        # do NOT use this payload style; they are followed by target/table bytes.
        if info["name"] == "HashCall":
            g = int(args.get("group", 0))
            s = int(args.get("sub", 0))
            f = int(args.get("op16", 0))
            is_jump_family = (g, s, f) in (
                (0, 1, 0), (0, 1, 2), (0, 1, 3), (0, 1, 4), (0, 1, 8), (0, 1, 9)
            )
            if (not is_jump_family) and j < len(b) and b[j] == 0x28:
                block, j = self.parse_parens_block(b, j)
                args["parens"] = block.data

        return Node("Op", {"name": info["name"], "op": f"{op:02X}", "args": args}), j

    def parse_parens_block(self, b: bytes, i: int) -> tuple[Node, int]:
        # i points at '('
        assert b[i] == 0x28
        depth = 0
        j = i
        items: list[Node] = []
        in_quote = False
        quote_buf = bytearray()
        while j < len(b):
            c = b[j]

            if in_quote:
                # Inside quotes, parentheses are literal; consume until closing quote.
                if c == 0x5C and j + 1 < len(b):  # escape
                    quote_buf.append(c)
                    quote_buf.append(b[j + 1])
                    j += 2
                    continue
                if self.is_sjis_lead(c) and j + 1 < len(b):
                    quote_buf.append(c)
                    quote_buf.append(b[j + 1])
                    j += 2
                    continue
                if c == 0x22:  # '"'
                    raw = bytes([0x22]) + bytes(quote_buf) + bytes([0x22])
                    txt = raw.decode(self.text_encoding, errors="replace")
                    if "\ufffd" in txt or any(ord(ch) < 0x20 and ch not in "\t\r\n" for ch in txt):
                        items.append(Node("Bytes", {"len": len(raw), "hex": raw.hex().upper()}))
                    else:
                        items.append(Node("Text", {"text": txt, "hex": raw.hex().upper()}))
                    quote_buf.clear()
                    in_quote = False
                    j += 1
                    continue
                quote_buf.append(c)
                j += 1
                continue

            if c == 0x22:  # '"'
                in_quote = True
                j += 1
                continue

            if c == 0x24 and j + 1 < len(b):
                n, j = self.parse_dollar(b, j, stop={0x28, 0x29, 0x5C, 0x24})
                items.append(n)
                continue
            if c == 0x5C and j + 1 < len(b):
                n, j = self.parse_esc(b, j)
                items.append(n)
                continue
            ctrl = self.parse_ctrl8194(b, j)
            if ctrl:
                n, j = ctrl
                items.append(n)
                continue

            op = self.parse_op(b, j)
            if op:
                n, j = op
                items.append(n)
                continue

            paren_stop = {0x28, 0x29, 0x24, 0x5C} | set(self.ops.keys())

            # SJIS multi-byte must be consumed before interpreting ASCII '(' / ')'.
            if self.is_sjis_lead(c) and j + 1 < len(b):
                t = self.parse_text_run(b, j, stop=paren_stop)
                if t:
                    n, j = t
                    items.append(n)
                    continue

            if c == 0x28:
                depth += 1
                items.append(Node("Sym", {"ch": "("}))
                j += 1
                continue
            if c == 0x29:
                depth -= 1
                items.append(Node("Sym", {"ch": ")"}))
                j += 1
                if depth <= 0:
                    break
                continue

            t = self.parse_text_run(b, j, stop=paren_stop)
            if t:
                n, j = t
                items.append(n)
                continue
            # fallback: keep as 1-byte text
            raw = bytes([b[j]])
            items.append(Node("Text", {"text": raw.decode(self.text_encoding, errors="replace"), "hex": raw.hex().upper()}))
            j += 1
        return Node("Parens", {"items": [{"node_kind": n.kind, **n.data} for n in items]}), j

    def parse_one(self, b: bytes, i: int) -> tuple[Node,int]:
        if i >= len(b): raise EOFError

        pad = self.parse_pad(b,i)
        if pad: return pad

        c = b[i]
        if c in self.sym_map:
            return Node("Sym", {"ch": self.sym_map[c]}), i+1

        ctrl = self.parse_ctrl8194(b,i)
        if ctrl: return ctrl

        if c == 0x24 and i+1 < len(b):
            return self.parse_dollar(b, i)
        if c == 0x5C and i+1 < len(b):
            return self.parse_esc(b,i)
        if c == 0x22:  # quoted string; consume until closing quote, honoring escapes
            j = i + 1
            while j < len(b):
                cb = b[j]
                if cb == 0x5C and j + 1 < len(b):
                    j += 2
                    continue
                if self.is_sjis_lead(cb) and j + 1 < len(b):
                    j += 2
                    continue
                if cb == 0x22:
                    j += 1
                    break
                j += 1
            raw = bytes(b[i:j])
            try:
                txt = raw.decode(self.text_encoding, errors="replace")
            except Exception:
                txt = ""
            if "\ufffd" in txt or any(ord(ch) < 0x20 and ch not in "\t\r\n" for ch in txt):
                return Node("Bytes", {"len": len(raw), "hex": raw.hex().upper()}), j
            return Node("Text", {"text": txt, "hex": raw.hex().upper()}), j

        op = self.parse_op(b,i)
        if op: return op

        # Treat remaining control bytes (<0x20) as raw opbytes to preserve opcode stream.
        if b[i] < 0x20:
            return Node("OpByte", {"op": f"{b[i]:02X}"}), i + 1

        t = self.parse_text_run(b, i, stop=self.top_ctrl | set(self.ops.keys()) | {0x24, 0x5C})
        if t:
            return t

        raw = bytes([b[i]])
        return Node("Text", {"text": raw.decode(self.text_encoding, errors="replace"), "hex": raw.hex().upper()}), i + 1

def dump_node(n: Node) -> str:
    raise RuntimeError("use DumpFormatter")

def _load_spec(spec_path: Path) -> dict:
    return json.loads(spec_path.read_text(encoding="utf-8"))

def _load_opcode_fmt_map(path: Path) -> dict[object, list[Optional[str]]]:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out: dict[object, list[Optional[str]]] = {}
    def _normalize_list(v: Any) -> Optional[list[Optional[str]]]:
        if not isinstance(v, list):
            return None
        return [x if isinstance(x, str) or x is None else None for x in v]
    if isinstance(raw, dict):
        for k, v in raw.items():
            if isinstance(k, str) and ":" in k:
                parts = k.split(":")
                if len(parts) == 3:
                    try:
                        g = int(parts[0])
                        s = int(parts[1])
                        o = int(parts[2]) if parts[2] != "*" else -1
                    except Exception:
                        continue
                    lst = _normalize_list(v)
                    if lst is not None:
                        out[(g, s, o)] = lst
                continue
            try:
                op = int(k)
            except Exception:
                continue
            lst = _normalize_list(v)
            if lst is None:
                continue
            if op in (0, 1, 2):
                # Ignore extracted low opcodes unless they match the known defaults.
                if (op == 0 and lst == ["S"]) or (op == 1 and lst == []) or (op == 2 and lst == ["&"]):
                    out[op] = lst
                continue
            out[op] = lst
    # Known low opcodes (not covered by extracted map)
    out.setdefault(0, ["S"])
    out.setdefault(1, [])
    out.setdefault(2, ["&"])
    return out

def _get_opfmt(opfmt_map: dict[object, list[Optional[str]]], group: int, sub: int, op16: int) -> Optional[list[Optional[str]]]:
    key = (group, sub, op16)
    if key in opfmt_map:
        return opfmt_map[key]
    key = (group, sub, -1)
    if key in opfmt_map:
        return opfmt_map[key]
    return opfmt_map.get(op16)

def _iter_fmt_candidates(fmts: Optional[list[Optional[str]]], argc_hint: int) -> list[str]:
    if not fmts:
        return []
    vals = [f for f in fmts if isinstance(f, str) and f]
    if not vals:
        return []
    same = [f for f in vals if len(f) == argc_hint]
    rest = [f for f in vals if len(f) != argc_hint]
    out: list[str] = []
    seen: set[str] = set()
    for f in same + rest:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out

def _parse_int(s: str) -> int:
    s = s.strip()
    if s.lower().startswith("0x"):
        return int(s, 16)
    return int(s, 10)

def _parse_version_str(s: str) -> tuple[int, int, int, int]:
    parts = [p for p in s.strip().split(".") if p != ""]
    nums = [int(p, 10) for p in parts]
    while len(nums) < 4:
        nums.append(0)
    return tuple(nums[:4])  # type: ignore[return-value]

def _version_cmp(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> int:
    return (a > b) - (a < b)

def _parse_ver_condition(line: str) -> dict[str, Any]:
    # Example: "ver Avg2000, RealLive" or "ver >= 1.3, < 1.6.4.6"
    rest = line.strip()[3:].strip()
    allowed: set[str] = set()
    bounds: list[tuple[str, tuple[int, int, int, int]]] = []
    # collect target tags
    for tok in re.split(r"[,\s]+", rest):
        if not tok:
            continue
        if tok in ("RealLive", "Avg2000", "Kinetic"):
            allowed.add(tok)
    # collect comparisons
    for m in re.finditer(r"(>=|<=|>|<|=)\s*([0-9.]+)", rest):
        op = m.group(1)
        ver = _parse_version_str(m.group(2))
        bounds.append((op, ver))
    # bare version like "ver 1.2.5"
    if not bounds:
        m2 = re.search(r"\b([0-9]+\.[0-9]+(?:\.[0-9]+){0,2})\b", rest)
        if m2:
            bounds.append(("=", _parse_version_str(m2.group(1))))
    return {"allowed": allowed, "bounds": bounds}

def _version_matches(cond: Optional[dict[str, Any]], target: tuple[int, int, int, int], *, target_kind: str = "RealLive") -> bool:
    if cond is None:
        return True
    allowed = cond.get("allowed") or set()
    if allowed and target_kind not in allowed:
        return False
    for op, ver in cond.get("bounds", []):
        c = _version_cmp(target, ver)
        if op == ">=" and not (c >= 0):
            return False
        if op == ">" and not (c > 0):
            return False
        if op == "<=" and not (c <= 0):
            return False
        if op == "<" and not (c < 0):
            return False
        if op == "=" and not (c == 0):
            return False
    return True

def _split_top_level_commas(s: str) -> list[str]:
    out: list[str] = []
    cur: list[str] = []
    depth_paren = 0
    depth_bracket = 0
    depth_brace = 0
    in_quote = False
    esc = False
    for ch in s:
        if in_quote:
            cur.append(ch)
            if esc:
                esc = False
                continue
            if ch == "\\":
                esc = True
                continue
            if ch == "\"":
                in_quote = False
            continue
        if ch == "\"":
            in_quote = True
            cur.append(ch)
            continue
        if ch == "(":
            depth_paren += 1
        elif ch == ")" and depth_paren > 0:
            depth_paren -= 1
        elif ch == "[":
            depth_bracket += 1
        elif ch == "]" and depth_bracket > 0:
            depth_bracket -= 1
        elif ch == "{":
            depth_brace += 1
        elif ch == "}" and depth_brace > 0:
            depth_brace -= 1
        if ch == "," and depth_paren == 0 and depth_bracket == 0 and depth_brace == 0:
            out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if cur:
        out.append("".join(cur).strip())
    return out


def _strip_one_outer_paren_text(s: str) -> str:
    t = s.strip()
    if not (t.startswith("(") and t.endswith(")")):
        return t
    depth = 0
    in_q = False
    esc = False
    for i, ch in enumerate(t):
        if in_q:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == "\"":
                in_q = False
            continue
        if ch == "\"":
            in_q = True
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0 and i != len(t) - 1:
                return t
    return t[1:-1].strip()

def _extract_param_names(sig_text: str) -> list[str]:
    sig_text = sig_text.strip()
    if sig_text.startswith("(") and sig_text.endswith(")"):
        sig_text = sig_text[1:-1].strip()
    parts = _split_top_level_commas(sig_text) if sig_text else []
    names: list[str] = []
    for i, part in enumerate(parts):
        m = re.search(r"'([^']+)'", part)
        if m:
            names.append(m.group(1))
        else:
            # fall back to a generic name
            names.append(f"arg{i+1}")
    return names

def _load_kfn_defs(kfn_path: Path, *, target_version: tuple[int, int, int, int]) -> dict[tuple[int, int, int, int], KfnOpDef]:
    # Map (op_type, op_module, op_function, overload) -> KfnOpDef
    defs: dict[tuple[int, int, int, int], KfnOpDef] = {}
    if not kfn_path.is_file():
        return defs

    current_ver: Optional[dict[str, Any]] = None
    module_map: dict[str, int] = {}

    def add_def(name: str, op_type: int, op_module: int, op_function: int, overload: int, flags: set[str], param_sigs: list[list[str]]) -> None:
        key = (op_type, op_module, op_function, overload)
        defs[key] = KfnOpDef(
            name=name,
            op_type=op_type,
            op_module=op_module,
            op_function=op_function,
            overload=overload,
            flags=flags,
            param_sigs=param_sigs,
        )

    lines = kfn_path.read_text(encoding="utf-8", errors="replace").splitlines()
    last_fun: Optional[tuple[str, int, int, int, int, set[str], list[list[str]]]] = None

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        if line.startswith("module"):
            m = re.search(r"module\s+(\d+)\s*=\s*([A-Za-z0-9_]+)", line)
            if m:
                module_map[m.group(2)] = int(m.group(1))
            continue
        if line.startswith("ver "):
            current_ver = _parse_ver_condition(line)
            continue
        if line == "end":
            current_ver = None
            continue

        if not _version_matches(current_ver, target_version, target_kind="RealLive"):
            continue

        # fun or /// lines
        if line.startswith("fun ") or line.startswith("///"):
            is_special = line.startswith("///")
            body = line[3:].strip() if is_special else line[4:].strip()
            # name
            mname = re.match(r"([A-Za-z0-9_]+)", body)
            if not mname:
                last_fun = None
                continue
            name = mname.group(1)
            # flags in parentheses after name
            flags = set()
            mflags = re.search(r"\(([^\)]*)\)", body)
            if mflags:
                for f in mflags.group(1).replace(",", " ").split():
                    flags.add(f)
            # opcode tuple
            mop = re.search(r"<\s*(\d+)\s*:\s*([A-Za-z0-9_]+)\s*:\s*(\d+)\s*,\s*(\d+)\s*>", body)
            if not mop:
                last_fun = None
                continue
            op_type = int(mop.group(1))
            mod_name = mop.group(2)
            op_module = module_map.get(mod_name, None)
            if op_module is None and mod_name.isdigit():
                op_module = int(mod_name)
            if op_module is None:
                last_fun = None
                continue
            op_function = int(mop.group(3))
            overload = int(mop.group(4))
            # parse parameter signatures after the opcode tuple (before comment)
            param_sigs: list[list[str]] = []
            after = body[mop.end() :].split("//", 1)[0]
            for m in re.finditer(r"\([^\)]*\)", after):
                sig = m.group(0)
                param_sigs.append(_extract_param_names(sig))
            add_def(name, op_type, op_module, op_function, overload, flags, param_sigs)
            last_fun = (name, op_type, op_module, op_function, overload, flags, param_sigs)
            continue

        # continuation overload lines (parameter lists) - we ignore for now but keep name/op mapping
        if last_fun and line.startswith("("):
            # continuation of parameter signatures for the last function
            name, op_type, op_module, op_function, overload, flags, param_sigs = last_fun
            sig = line.split("//", 1)[0].strip()
            if sig.startswith("(") and sig.endswith(")"):
                param_sigs.append(_extract_param_names(sig))
                add_def(name, op_type, op_module, op_function, overload, flags, param_sigs)
                last_fun = (name, op_type, op_module, op_function, overload, flags, param_sigs)
            continue

    return defs

def _build_hashcall_map(defs: dict[tuple[int, int, int, int], KfnOpDef]) -> dict[tuple[int, int, int, int], KfnOpDef]:
    # HashCall keys are (group, sub, op16, overload) which map to (op_type, op_module, op_function, overload)
    out: dict[tuple[int, int, int, int], KfnOpDef] = {}
    for key, d in defs.items():
        out[(d.op_type, d.op_module, d.op_function, d.overload)] = d
    return out

def _sig_of_def(d: KfnOpDef) -> str:
    return f"{d.op_type}:{d.op_module:03d}:{d.op_function:05d}:{d.overload}"

def _sig_of_args(args: dict[str, Any]) -> str:
    return f"{int(args.get('group', 0))}:{int(args.get('sub', 0)):03d}:{int(args.get('op16', 0)):05d}:{int(args.get('overload', 0))}"

def _defs_by_name(hashcall_map: dict[tuple[int, int, int, int], KfnOpDef], name: str) -> list[KfnOpDef]:
    return [d for d in hashcall_map.values() if d.name == name]

def _is_ambiguous_name(hashcall_map: dict[tuple[int, int, int, int], KfnOpDef], name: str) -> bool:
    return len(_defs_by_name(hashcall_map, name)) > 1

def _resolve_fun_def(
    *,
    fname: str,
    sig_token: Optional[str],
    hashcall_map: dict[tuple[int, int, int, int], KfnOpDef],
) -> KfnOpDef:
    by_name = _defs_by_name(hashcall_map, fname)
    if not by_name:
        mm = re.match(r"^op_(\d+)_(\d+)_(\d{5})$", fname)
        if mm:
            g = int(mm.group(1))
            s = int(mm.group(2))
            f = int(mm.group(3))
            if sig_token:
                m = re.match(r"^\s*(\d+)\s*:\s*(\d+)\s*:\s*(\d+)\s*:\s*(\d+)\s*$", sig_token)
                if not m:
                    raise ValueError(f"bad _sig token {sig_token!r} for {fname}")
                ov = int(m.group(4))
                g = int(m.group(1)); s = int(m.group(2)); f = int(m.group(3))
            else:
                ov = 0
            return KfnOpDef(
                name=fname,
                op_type=g,
                op_module=s,
                op_function=f,
                overload=ov,
                flags=set(),
                param_sigs=[],
            )
        raise ValueError(f"unknown fun name {fname!r}")
    if sig_token:
        m = re.match(r"^\s*(\d+)\s*:\s*(\d+)\s*:\s*(\d+)\s*:\s*(\d+)\s*$", sig_token)
        if not m:
            raise ValueError(f"bad _sig token {sig_token!r} for {fname}")
        key = (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))
        d = hashcall_map.get(key)
        if d is None or d.name != fname:
            raise ValueError(f"_sig {sig_token!r} does not match function {fname!r}")
        return d
    if len(by_name) == 1:
        return by_name[0]
    raise ValueError(f"ambiguous function {fname!r}; add _sig=<group:sub:op16:overload>")

def _parse_hex_u32_token(s: str) -> int:
    t = s.strip()
    if not re.fullmatch(r"[0-9A-Fa-f]{1,8}", t):
        raise ValueError(f"bad HEX u32 token: {s!r}")
    return int(t, 16) & 0xFFFFFFFF


def _decode_jump_table_on_to_text(
    raw: bytes,
    *,
    offset_to_op_index: Optional[dict[int, int]] = None,
    base_op_index: Optional[int] = None,
) -> Optional[str]:
    if len(raw) < 2 or raw[0] != 0x7B or raw[-1] != 0x7D:
        return None
    body = raw[1:-1]
    if len(body) % 4 != 0:
        return None
    vals: list[str] = []
    for i in range(0, len(body), 4):
        tgt = int.from_bytes(body[i:i+4], "little") & 0xFFFFFFFF
        vals.append(f"{tgt:X}")
    return "{" + ", ".join(vals) + "}"


def _decode_jump_table_case_to_text(
    raw: bytes,
    *,
    offset_to_op_index: Optional[dict[int, int]] = None,
    base_op_index: Optional[int] = None,
) -> Optional[str]:
    if len(raw) < 2 or raw[0] != 0x7B or raw[-1] != 0x7D:
        return None
    i = 1
    entries: list[str] = []
    while i < len(raw) - 1:
        if raw[i] != 0x28:
            return None
        p = _find_matching_paren(raw, i)
        if p is None:
            return None
        if p == i + 1:
            expr_txt = "_"
        else:
            expr, j = _decode_expr_at(raw, i + 1)
            if j != p:
                return None
            expr_txt = _expr_to_str(expr)
        i = p + 1
        if i + 4 > len(raw):
            return None
        tgt = int.from_bytes(raw[i:i+4], "little") & 0xFFFFFFFF
        i += 4
        entries.append(f"({expr_txt}, {tgt:X})")
    if i != len(raw) - 1:
        return None
    return "{" + ", ".join(entries) + "}"


def _encode_jump_table_on_from_text(s: str) -> Optional[bytes]:
    t = s.strip()
    if not (t.startswith("{") and t.endswith("}")):
        return None
    inner = t[1:-1].strip()
    out = bytearray([0x7B])
    if inner:
        parts = _split_top_level_commas(inner)
        for p in parts:
            out += p32le(_parse_hex_u32_token(p))
    out.append(0x7D)
    return bytes(out)


def _encode_jump_table_case_from_text(s: str, *, text_encoding: str) -> Optional[bytes]:
    t = s.strip()
    if not (t.startswith("{") and t.endswith("}")):
        return None
    inner = t[1:-1].strip()
    out = bytearray([0x7B])
    if inner:
        parts = _split_top_level_commas(inner)
        for ent in parts:
            e = ent.strip()
            if not (e.startswith("(") and e.endswith(")")):
                return None
            inside = e[1:-1].strip()
            two = _split_top_level_commas(inside)
            if len(two) != 2:
                return None
            expr_tok = two[0].strip()
            tgt = _parse_hex_u32_token(two[1].strip())
            out.append(0x28)
            if expr_tok != "_":
                expr = _parse_expr_text_list_single(expr_tok)
                out += _encode_single_expr_to_bytes(expr, text_encoding=text_encoding)
            out.append(0x29)
            out += p32le(tgt)
    out.append(0x7D)
    return bytes(out)


def _parse_jump_table_on_entries(s: str) -> Optional[list[tuple[str, int]]]:
    t = s.strip()
    if not (t.startswith("{") and t.endswith("}")):
        return None
    inner = t[1:-1].strip()
    entries: list[tuple[str, int]] = []
    if inner:
        parts = _split_top_level_commas(inner)
        for p in parts:
            tok = p.strip()
            if re.fullmatch(r"[+-]\d+", tok):
                entries.append(("rel", int(tok, 10)))
            else:
                entries.append(("abs", _parse_hex_u32_token(tok)))
    return entries


def _parse_jump_table_case_entries(s: str) -> Optional[list[tuple[str, str, int]]]:
    t = s.strip()
    if not (t.startswith("{") and t.endswith("}")):
        return None
    inner = t[1:-1].strip()
    entries: list[tuple[str, str, int]] = []
    if inner:
        parts = _split_top_level_commas(inner)
        for ent in parts:
            e = ent.strip()
            if not (e.startswith("(") and e.endswith(")")):
                return None
            inside = e[1:-1].strip()
            two = _split_top_level_commas(inside)
            if len(two) != 2:
                return None
            expr_tok = two[0].strip()
            tgt_tok = two[1].strip()
            if re.fullmatch(r"[+-]\d+", tgt_tok):
                entries.append((expr_tok, "rel", int(tgt_tok, 10)))
            else:
                entries.append((expr_tok, "abs", _parse_hex_u32_token(tgt_tok)))
    return entries


def _build_jump_table_on_bytes(
    entries: list[tuple[str, int]],
    *,
    base_op_index: int,
    op_offsets: list[int],
) -> bytes:
    out = bytearray([0x7B])
    for mode, val in entries:
        if mode == "rel":
            tgt_index = base_op_index + val
            if tgt_index < 0 or tgt_index >= len(op_offsets):
                raise ValueError("jump_table rel target out of range")
            tgt = op_offsets[tgt_index]
        else:
            tgt = val
        out += p32le(int(tgt) & 0xFFFFFFFF)
    out.append(0x7D)
    return bytes(out)


def _build_jump_table_case_bytes(
    entries: list[tuple[str, str, int]],
    *,
    base_op_index: int,
    op_offsets: list[int],
    text_encoding: str,
) -> bytes:
    out = bytearray([0x7B])
    for expr_tok, mode, val in entries:
        out.append(0x28)
        if expr_tok != "_":
            expr = _parse_expr_text_list_single(expr_tok)
            out += _encode_single_expr_to_bytes(expr, text_encoding=text_encoding)
        out.append(0x29)
        if mode == "rel":
            tgt_index = base_op_index + val
            if tgt_index < 0 or tgt_index >= len(op_offsets):
                raise ValueError("jump_table rel target out of range")
            tgt = op_offsets[tgt_index]
        else:
            tgt = val
        out += p32le(int(tgt) & 0xFFFFFFFF)
    out.append(0x7D)
    return bytes(out)


def _estimate_jump_table_len(
    *,
    kind: str,
    entries: Any,
    text_encoding: str,
) -> int:
    if kind == "on":
        # 0x7B + N * u32 + 0x7D
        return 1 + 4 * len(entries or []) + 1
    # case: 0x7B + N * (0x28 + expr + 0x29 + u32) + 0x7D
    total = 1
    for expr_tok, _mode, _val in (entries or []):
        total += 1  # '('
        if expr_tok != "_":
            expr = _parse_expr_text_list_single(expr_tok)
            total += len(_encode_single_expr_to_bytes(expr, text_encoding=text_encoding))
        total += 1  # ')'
        total += 4  # target u32
    total += 1
    return total

# ---------------- Expression bytecode parsing/encoding ----------------

class _ExprReader:
    def __init__(self, data: bytes, i: int = 0):
        self.data = data
        self.i = i

    def eof(self) -> bool:
        return self.i >= len(self.data)

    def peek(self, n: int = 0) -> int:
        j = self.i + n
        if j >= len(self.data):
            return -1
        return self.data[j]

    def get(self) -> int:
        if self.i >= len(self.data):
            raise EOFError
        b = self.data[self.i]
        self.i += 1
        return b

    def match(self, b: int) -> bool:
        if self.peek() == b:
            self.i += 1
            return True
        return False

_OPCODE_TO_SYM = {
    0x00: "+", 0x01: "-",
    0x02: "*", 0x03: "/", 0x04: "%", 0x05: "&", 0x06: "|", 0x07: "^",
    0x08: "<<", 0x09: ">>",
    0x28: "==", 0x29: "!=", 0x2A: "<=", 0x2B: "<", 0x2C: ">=", 0x2D: ">",
    0x3C: "&&", 0x3D: "||",
}
_SYM_TO_OPCODE = {v: k for k, v in _OPCODE_TO_SYM.items()}

def _expr_prec(sym: str) -> int:
    if sym in ("||",):
        return 0
    if sym in ("&&",):
        return 1
    if sym in ("==", "!=", "<=", "<", ">=", ">"):
        return 2 if sym in ("==", "!=") else 3
    if sym in ("+", "-", "&", "|", "^"):
        return 4
    if sym in ("*", "/", "%"):
        return 5
    if sym in ("<<", ">>"):
        return 6
    return 10


def _decode_expr_at(data: bytes, i: int) -> tuple[Any, int]:
    r = _ExprReader(data, i)
    expr = _parse_expr_bool(r)
    return expr, r.i


def _is_sjis_lead_for_enc(c: int, text_encoding: str) -> bool:
    enc = text_encoding.lower()
    if enc in ("cp932", "shift_jis", "sjis"):
        return _is_sjis_lead(c)
    return False


def _parse_dollar_var(data: bytes, i: int, *, text_encoding: str) -> Optional[tuple[str, int]]:
    if i >= len(data) or data[i] != 0x24:
        return None
    if i + 1 >= len(data):
        return None
    b = data[i + 1]
    if b == 0xFF:
        if i + 6 > len(data):
            return None
        v = u32le(data, i + 2)
        name = f"$FF({v})"
        return name, i + 6
    var_id = b
    name = _VAR_ID_TO_NAME.get(var_id, f"VAR{var_id:02X}")
    j = i + 2
    if j < len(data) and data[j] == 0x5B:  # '['
        j += 1
        expr, j2 = _decode_expr_at(data, j)
        if j2 < len(data) and data[j2] == 0x5D:  # ']'
            name = f"{name}[{_expr_to_str(expr)}]"
            j = j2 + 1
        else:
            return None
    return name, j


def _parse_quoted_string(data: bytes, i: int, *, text_encoding: str) -> Optional[tuple[str, int]]:
    if i >= len(data) or data[i] != 0x22:
        return None
    j = i + 1
    buf = bytearray()
    while j < len(data):
        c = data[j]
        if c == 0x5C and j + 1 < len(data):
            buf.append(c)
            buf.append(data[j + 1])
            j += 2
            continue
        if _is_sjis_lead_for_enc(c, text_encoding) and j + 1 < len(data):
            buf.append(c)
            buf.append(data[j + 1])
            j += 2
            continue
        if c == 0x22:
            j += 1
            s = buf.decode(text_encoding, errors="replace")
            return _escape_kprl_text(s), j
        buf.append(c)
        j += 1
    return None


def _parse_ident_token(data: bytes, i: int, *, text_encoding: str) -> Optional[tuple[str, int]]:
    if i >= len(data):
        return None
    j = i
    buf = bytearray()
    while j < len(data):
        c = data[j]
        if c in (0x2C, 0x20, 0x29):  # , space )
            break
        if _is_sjis_lead_for_enc(c, text_encoding) and j + 1 < len(data):
            buf.append(c)
            buf.append(data[j + 1])
            j += 2
            continue
        if (0x41 <= c <= 0x5A) or (0x61 <= c <= 0x7A) or (0x30 <= c <= 0x39) or c in (0x5F, 0x3F):
            buf.append(c)
            j += 1
            continue
        break
    if j == i:
        return None
    s = buf.decode(text_encoding, errors="replace")
    return s, j


def _decode_args_by_format(raw: bytes, fmt: str, *, text_encoding: str) -> Optional[list[str]]:
    i = 0
    out: list[str] = []
    for ch in fmt:
        while i < len(raw) and raw[i] in (0x2C, 0x20):
            i += 1
        if i >= len(raw):
            return None
        if ch == "$":
            try:
                expr, j = _decode_expr_at(raw, i)
            except Exception:
                return None
            out.append(_expr_to_str(expr))
            i = j
            continue
        if ch in ("%","&"):
            pv = _parse_dollar_var(raw, i, text_encoding=text_encoding)
            if not pv:
                return None
            name, i = pv
            out.append(name)
            continue
        if ch == "S":
            if raw[i] == 0x24:
                pv = _parse_dollar_var(raw, i, text_encoding=text_encoding)
                if not pv:
                    return None
                name, i = pv
                out.append(name)
                continue
            qs = _parse_quoted_string(raw, i, text_encoding=text_encoding)
            if qs:
                s, i = qs
                out.append(s)
                continue
            ident = _parse_ident_token(raw, i, text_encoding=text_encoding)
            if not ident:
                return None
            s, i = ident
            out.append(s)
            continue
        return None
    return out


def _decode_expr_list_greedy(raw: bytes) -> Optional[list[Any]]:
    i = 0
    out: list[Any] = []
    while i < len(raw):
        while i < len(raw) and raw[i] in (0x2C, 0x20):
            i += 1
        if i >= len(raw):
            break
        try:
            expr, j = _decode_expr_at(raw, i)
        except Exception:
            return None
        out.append(expr)
        i = j
    return out


def _find_matching_paren(raw: bytes, start: int) -> Optional[int]:
    if start < 0 or start >= len(raw) or raw[start] != 0x28:
        return None
    depth = 0
    i = start
    in_quote = False
    esc = False
    while i < len(raw):
        c = raw[i]
        if in_quote:
            if esc:
                esc = False
            elif c == 0x5C:
                esc = True
            elif c == 0x22:
                in_quote = False
            i += 1
            continue
        if c == 0x22:
            in_quote = True
            i += 1
            continue
        if c == 0x28:
            depth += 1
        elif c == 0x29:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def _format_block_exprs(raw_block: bytes, *, text_encoding: str) -> str:
    exprs = _decode_expr_list_greedy(raw_block)
    if exprs is None:
        return f"RAW[{raw_block.hex().upper()}]"
    return "(" + ", ".join(_expr_to_str(e) for e in exprs) + ")"


def _decode_mixed_parts(raw: bytes, *, text_encoding: str, allow_paren: bool) -> Optional[list[str]]:
    i = 0
    parts: list[str] = []
    while i < len(raw):
        while i < len(raw) and raw[i] in (0x2C, 0x20):
            i += 1
        if i >= len(raw):
            break
        if allow_paren and raw[i] == 0x28:
            end = _find_matching_paren(raw, i)
            if end is None:
                return None
            inner = _decode_mixed_parts(raw[i + 1 : end], text_encoding=text_encoding, allow_paren=False)
            if inner is None:
                parts.append(f"RAW[{raw[i + 1:end].hex().upper()}]")
            else:
                parts.append("(" + ", ".join(inner) + ")")
            i = end + 1
            continue
        try:
            expr, j = _decode_expr_at(raw, i)
            parts.append(_expr_to_str(expr))
            i = j
            continue
        except Exception:
            pass
        ident = _parse_ident_token(raw, i, text_encoding=text_encoding)
        if ident:
            s, j = ident
            parts.append(s)
            i = j
            continue
        parts.append(f"0x{raw[i]:02X}")
        i += 1
    return parts


def _summarize_script_blob(raw: bytes, *, spec: dict, text_encoding: str) -> Optional[str]:
    dec = Decoder(spec, text_encoding=text_encoding)
    i = 0
    total = 0
    op23 = 0
    opbyte = 0
    bytes_max = 0
    goto_n = 0
    goto_unless_n = 0
    targets: list[str] = []
    prev_was_jump = False
    head: list[str] = []
    try:
        while i < len(raw):
            n, j = dec.parse_one(raw, i)
            if j <= i:
                return None
            total += 1
            if n.kind == "Op":
                prev_was_jump = False
                if str(n.data.get("op", "")).upper() == "23":
                    op23 += 1
                    a = n.data.get("args", {})
                    g = int(a.get("group", 0))
                    s = int(a.get("sub", 0))
                    f = int(a.get("op16", 0))
                    if (g, s, f) == (0, 1, 0):
                        goto_n += 1
                        prev_was_jump = True
                    elif (g, s, f) == (0, 1, 2):
                        goto_unless_n += 1
                        prev_was_jump = True
                # Collect only meaningful preview tokens.
                if len(head) < 8:
                    if str(n.data.get("op", "")).upper() == "23":
                        tag = f"{int(a.get('group',0))}:{int(a.get('sub',0)):03d}:{int(a.get('op16',0)):05d}"
                        head.append(tag)
                    else:
                        opv = str(n.data.get("op", "")).upper()
                        if opv not in ("00",):
                            head.append(f"op{opv}")
            elif n.kind == "U32":
                if prev_was_jump and len(targets) < 6:
                    v = int(n.data.get("val", 0)) & 0xFFFFFFFF
                    targets.append(f"0x{v:08X}")
                prev_was_jump = False
            elif n.kind == "OpByte":
                prev_was_jump = False
                opbyte += 1
            elif n.kind == "Bytes":
                if prev_was_jump:
                    try:
                        hx = str(n.data.get("hex", ""))
                        ln = int(n.data.get("len", 0))
                        if ln == 4 and len(hx) >= 8 and len(targets) < 6:
                            b4 = bytes.fromhex(hx[:8])
                            v = int.from_bytes(b4, "little", signed=False)
                            targets.append(f"0x{v:08X}")
                    except Exception:
                        pass
                prev_was_jump = False
                try:
                    bytes_max = max(bytes_max, int(n.data.get("len", 0)))
                except Exception:
                    pass
            else:
                prev_was_jump = False
            i = j
    except Exception:
        return None
    preview = ",".join(head) if head else "-"
    tgt = ",".join(targets) if targets else "-"
    return (
        "SCRIPT_BLOB("
        f"nodes={total}, op23={op23}, opbyte={opbyte}, bytes_max={bytes_max}, "
        f"goto={goto_n}, goto_unless={goto_unless_n}, targets={tgt}, head={preview}"
        ")"
    )


def _decode_special_fun_args(
    *,
    group: int,
    sub: int,
    op16: int,
    raw: bytes,
    spec: dict,
    text_encoding: str,
) -> Optional[str]:
    key = (group, sub, op16)
    if key not in ((1, 33, 75), (1, 34, 2112), (1, 4, 623), (1, 4, 630)):
        return None

    if key == (1, 33, 75):
        parts: list[str] = []
        i = 0
        lead = _parse_ident_token(raw, i, text_encoding=text_encoding)
        if lead:
            s, i = lead
            parts.append(s)
        try:
            expr, j = _decode_expr_at(raw, i)
            parts.append(_expr_to_str(expr))
            i = j
        except Exception:
            return None
        while i < len(raw) and raw[i] not in (0x28,):
            parts.append(f"0x{raw[i]:02X}")
            i += 1
        if i < len(raw) and raw[i] == 0x28:
            end = _find_matching_paren(raw, i)
            if end is None:
                return None
            inner = _decode_mixed_parts(raw[i + 1 : end], text_encoding=text_encoding, allow_paren=False)
            if inner is None:
                parts.append(f"RAW[{raw[i + 1:end].hex().upper()}]")
            else:
                parts.append("(" + ", ".join(inner) + ")")
            i = end + 1
        if i < len(raw):
            parts.append(f"RAW[{raw[i:].hex().upper()}]")
    else:
        parts = _decode_mixed_parts(raw, text_encoding=text_encoding, allow_paren=True) or []

    if not parts:
        return None
    return ", ".join(parts)


def _split_args_for_fmt(s: str) -> list[str]:
    out: list[str] = []
    cur: list[str] = []
    depth = 0
    in_quote = False
    esc = False
    for ch in s:
        if in_quote:
            cur.append(ch)
            if esc:
                esc = False
                continue
            if ch == "\\":
                esc = True
                continue
            if ch == "\"":
                in_quote = False
            continue
        if ch == "\"":
            in_quote = True
            cur.append(ch)
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if cur:
        out.append("".join(cur).strip())
    return out


def _encode_single_expr_to_bytes(expr: Any, *, text_encoding: str) -> bytes:
    out = bytearray()
    _encode_expr(expr, out, text_encoding=text_encoding)
    return bytes(out)


def _encode_dollar_var_token(tok: str, *, text_encoding: str) -> Optional[bytes]:
    t = tok.strip()
    if not t:
        return None
    if t.startswith("$FF(") and t.endswith(")"):
        inner = t[4:-1].strip()
        try:
            v = _parse_int(inner)
        except Exception:
            return None
        return bytes([0x24, 0xFF]) + p32le(v & 0xFFFFFFFF)
    if t[0] in ("$", "%"):
        t = t[1:]
    name = t
    idx_expr = None
    if "[" in t and t.endswith("]"):
        base, rest = t.split("[", 1)
        name = base
        idx_expr = rest[:-1]
    var_id = _VAR_NAME_TO_ID.get(f"${name}") or _VAR_NAME_TO_ID.get(f"%{name}")
    if var_id is None:
        if name.upper().startswith("VAR"):
            try:
                var_id = int(name[3:], 16)
            except Exception:
                return None
        else:
            return None
    buf = bytearray()
    buf.append(0x24)
    buf.append(int(var_id) & 0xFF)
    if idx_expr is not None and idx_expr.strip():
        try:
            expr = _parse_expr_text_list_single(idx_expr.strip())
        except Exception:
            return None
        buf.append(0x5B)
        buf += _encode_single_expr_to_bytes(expr, text_encoding=text_encoding)
        buf.append(0x5D)
    return bytes(buf)


def _encode_quoted_string_token(tok: str, *, text_encoding: str) -> Optional[bytes]:
    t = tok.strip()
    if not (t.startswith("\"") and t.endswith("\"")):
        return None
    try:
        s = json.loads(t)
    except Exception:
        return None
    raw = s.encode(text_encoding, errors="ignore")
    out = bytearray()
    out.append(0x22)
    for b in raw:
        if b in (0x22, 0x5C):
            out.append(0x5C)
        out.append(b)
    out.append(0x22)
    return bytes(out)


def _encode_args_by_format(parts: list[str], fmt: str, *, text_encoding: str, with_commas: bool = False) -> Optional[bytes]:
    if len(parts) < len(fmt):
        return None
    out = bytearray()
    for idx, ch in enumerate(fmt):
        if with_commas and idx > 0:
            out.append(0x2C)
        tok = parts[idx].strip()
        m_named = re.match(r"^[A-Za-z_][A-Za-z0-9_]*\s*=(.*)$", tok)
        if m_named:
            tok = m_named.group(1).strip()
        if ch == "$":
            try:
                expr = _parse_expr_text_list_single(tok)
            except Exception:
                return None
            out += _encode_single_expr_to_bytes(expr, text_encoding=text_encoding)
        elif ch in ("%","&"):
            b = _encode_dollar_var_token(tok, text_encoding=text_encoding)
            if b is None:
                return None
            out += b
        elif ch == "S":
            if tok.startswith("$") or tok.startswith("%"):
                b = _encode_dollar_var_token(tok, text_encoding=text_encoding)
                if b is None:
                    return None
                out += b
            else:
                b = _encode_quoted_string_token(tok, text_encoding=text_encoding)
                if b is not None:
                    out += b
                else:
                    out += tok.encode(text_encoding, errors="ignore")
        else:
            return None
    return bytes(out)

def _encode_mixed_parts(parts: list[str], *, text_encoding: str) -> Optional[bytes]:
    out = bytearray()
    for idx, raw_tok in enumerate(parts):
        tok = raw_tok.strip()
        if not tok:
            continue
        mh = re.fullmatch(r"0x([0-9A-Fa-f]{2})", tok)
        if mh:
            out.append(int(mh.group(1), 16))
            continue
        b = _encode_dollar_var_token(tok, text_encoding=text_encoding)
        if b is not None:
            out += b
            continue
        b = _encode_quoted_string_token(tok, text_encoding=text_encoding)
        if b is not None:
            out += b
            continue
        if tok.startswith("(") and tok.endswith(")"):
            if re.fullmatch(r"\([A-Za-z0-9_?]+\)", tok):
                out += tok.encode(text_encoding, errors="replace")
                continue
            inner = tok[1:-1].strip()
            inner_parts = _split_top_level_commas(inner) if inner else []
            inner_b = _encode_mixed_parts(inner_parts, text_encoding=text_encoding)
            if inner_b is None:
                return None
            out.append(0x28)
            out += inner_b
            out.append(0x29)
            continue
        # Keep plain identifiers/symbol chunks as raw bytes; only parse clear expressions.
        try_expr = False
        if re.fullmatch(r"-?(?:0x[0-9A-Fa-f]+|\d+)", tok):
            try_expr = True
        elif any(ch in tok for ch in ("+", "-", "*", "/", "%", "&", "|", "^", "<", ">", "=", "~", " ")):
            try_expr = True
        if try_expr:
            try:
                expr = _parse_expr_text_list_single(tok)
                out += _encode_single_expr_to_bytes(expr, text_encoding=text_encoding)
                continue
            except Exception:
                pass
        out += tok.encode(text_encoding, errors="replace")
    return bytes(out)

def _parse_expr_token(r: _ExprReader) -> Any:
    b = r.get()
    if b == 0xFF:
        v = u32le(r.data, r.i)
        r.i += 4
        # signed?
        if v & 0x80000000:
            v = v - 0x100000000
        return ("int", v)
    if b == 0xC8:
        return ("store",)
    # variable
    name = _VAR_ID_TO_NAME.get(b, f"VAR{b:02X}")
    if r.match(0x5B):  # '['
        expr = _parse_expr_bool(r)
        if not r.match(0x5D):
            raise ValueError("missing ] in expr")
        return ("var", name, expr)
    return ("var", name, None)

def _parse_expr_term(r: _ExprReader) -> Any:
    if r.match(0x22):  # '"'
        start = r.i
        while r.i < len(r.data) and r.data[r.i] != 0x22:
            r.i += 1
        if r.i >= len(r.data):
            raise ValueError("unterminated string in expr")
        raw = bytes(r.data[start:r.i])
        r.i += 1  # consume closing '"'
        try:
            txt = raw.decode(r.text_encoding, errors="replace")
        except Exception:
            txt = ""
        return ("str", txt)
    if r.match(0x24):  # '$'
        return _parse_expr_token(r)
    if r.peek() == 0x5C:
        # unary + / - / ~
        if r.peek(1) in (0x00, 0x01, 0x0A):
            r.get(); op = r.get()
            expr = _parse_expr_term(r)
            if op == 0x00:
                return ("unary", "+", expr)
            if op == 0x01:
                return ("unary", "-", expr)
            return ("unary", "~", expr)
    if r.match(0x28):  # '('
        expr = _parse_expr_bool(r)
        if not r.match(0x29):
            raise ValueError("missing ) in expr")
        return ("paren", expr)
    raise ValueError("bad expr term")

def _parse_expr_arith(r: _ExprReader) -> Any:
    def parse_hi(tok: Any) -> Any:
        while r.peek() == 0x5C and 0x02 <= r.peek(1) <= 0x09:
            r.get(); op = r.get()
            rhs = _parse_expr_term(r)
            tok = ("bin", _OPCODE_TO_SYM.get(op, f"op{op:02X}"), tok, rhs)
        return tok
    tok = parse_hi(_parse_expr_term(r))
    while r.peek() == 0x5C and r.peek(1) in (0x00, 0x01):
        r.get(); op = r.get()
        rhs = parse_hi(_parse_expr_term(r))
        tok = ("bin", _OPCODE_TO_SYM.get(op, f"op{op:02X}"), tok, rhs)
    return tok

def _parse_expr_cond(r: _ExprReader) -> Any:
    tok = _parse_expr_arith(r)
    while r.peek() == 0x5C and 0x28 <= r.peek(1) <= 0x2D:
        r.get(); op = r.get()
        rhs = _parse_expr_arith(r)
        tok = ("bin", _OPCODE_TO_SYM.get(op, f"op{op:02X}"), tok, rhs)
    return tok

def _parse_expr_bool(r: _ExprReader) -> Any:
    tok = _parse_expr_cond(r)
    while r.peek() == 0x5C and r.peek(1) in (0x3C, 0x3D):
        r.get(); op = r.get()
        rhs = _parse_expr_cond(r)
        tok = ("bin", _OPCODE_TO_SYM.get(op, f"op{op:02X}"), tok, rhs)
    return tok

def _expr_to_str(e: Any) -> str:
    if e[0] == "int":
        return str(e[1])
    if e[0] == "store":
        return "store"
    if e[0] == "str":
        return _escape_kprl_text(e[1])
    if e[0] == "var":
        name = e[1]
        idx = e[2]
        if idx is None:
            return name
        return f"{name}[{_expr_to_str(idx)}]"
    if e[0] == "unary":
        return f"{e[1]}{_expr_to_str(e[2])}"
    if e[0] == "paren":
        return f"({_expr_to_str(e[1])})"
    if e[0] == "bin":
        op = e[1]
        l, r = e[2], e[3]
        ls = _expr_to_str(l)
        rs = _expr_to_str(r)
        return f"{ls} {op} {rs}"
    return "<?>"

def _encode_expr(e: Any, out: bytearray, parent_prec: int = -1, *, text_encoding: str = "cp932") -> None:
    if e[0] == "int":
        out.append(0x24)
        out.append(0xFF)
        out += p32le(int(e[1]) & 0xFFFFFFFF)
        return
    if e[0] == "store":
        out.append(0x24)
        out.append(0xC8)
        return
    if e[0] == "str":
        out.append(0x22)
        out += str(e[1]).encode(text_encoding, errors="replace")
        out.append(0x22)
        return
    if e[0] == "var":
        name = e[1]
        vid = _VAR_NAME_TO_ID.get(name, None)
        if vid is None and name.startswith("VAR"):
            try:
                vid = int(name[3:], 16)
            except Exception:
                vid = 0x00
        if vid is None:
            vid = 0x00
        out.append(0x24)
        out.append(vid & 0xFF)
        if e[2] is not None:
            out.append(0x5B)
            _encode_expr(e[2], out, text_encoding=text_encoding)
            out.append(0x5D)
        return
    if e[0] == "unary":
        op = e[1]
        if op == "+":
            out += b"\x5c\x00"
            _encode_expr(e[2], out, text_encoding=text_encoding)
            return
        if op == "-":
            out += b"\x5c\x01"
            _encode_expr(e[2], out, text_encoding=text_encoding)
            return
        if op == "~":
            out += b"\x5c\x0A"
            _encode_expr(e[2], out, text_encoding=text_encoding)
            return
        if op == "!":
            _encode_expr(e[2], out, text_encoding=text_encoding)
            out += b"\x5c\x28"
            _encode_expr(("int", 0), out, text_encoding=text_encoding)
            return
    if e[0] == "paren":
        out.append(0x28)
        _encode_expr(e[1], out, text_encoding=text_encoding)
        out.append(0x29)
        return
    if e[0] == "bin":
        op = e[1]
        prec = _expr_prec(op)
        need_paren = prec < parent_prec
        if need_paren:
            out.append(0x28)
        _encode_expr(e[2], out, prec, text_encoding=text_encoding)
        opb = _SYM_TO_OPCODE.get(op)
        if opb is None:
            raise ValueError(f"unknown op {op}")
        out.append(0x5C)
        out.append(opb)
        _encode_expr(e[3], out, prec, text_encoding=text_encoding)
        if need_paren:
            out.append(0x29)
        return
    raise ValueError("bad expr")

def _parse_expr_text_list(s: str) -> list[Any]:
    parts: list[str] = []
    depth = 0
    cur: list[str] = []
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append("".join(cur).strip())
    exprs: list[Any] = []
    for part in parts:
        if part:
            exprs.append(_parse_expr_text_list_single(part))
    return exprs

def _parse_expr_text_list_single(s: str) -> Any:
    # helper to parse one expression
    tokens: list[str] = []
    i = 0
    while i < len(s):
        c = s[i]
        if c.isspace():
            i += 1
            continue
        if c == "\"":
            # parse JSON-style quoted string
            try:
                dec = json.JSONDecoder()
                val, end = dec.raw_decode(s[i:])
            except Exception:
                raise ValueError("bad quoted string in expr")
            if not isinstance(val, str):
                raise ValueError("bad quoted string in expr")
            tokens.append(s[i:i+end])
            i += end
            continue
        if c.isdigit():
            j = i + 1
            while j < len(s) and (s[j].isdigit() or s[j] in "xXabcdefABCDEF"):
                j += 1
            tokens.append(s[i:j])
            i = j
            continue
        if c.isalpha() or c in "%$":
            j = i + 1
            while j < len(s) and (s[j].isalnum() or s[j] in "_%$"):
                j += 1
            tokens.append(s[i:j])
            i = j
            continue
        if c in "(),[]":
            tokens.append(c)
            i += 1
            continue
        for op in ("&&", "||", "==", "!=", "<=", ">=", "<<", ">>"):
            if s.startswith(op, i):
                tokens.append(op)
                i += len(op)
                break
        else:
            tokens.append(c)
            i += 1

    pos = 0
    def peek() -> Optional[str]:
        return tokens[pos] if pos < len(tokens) else None
    def get() -> str:
        nonlocal pos
        t = tokens[pos]
        pos += 1
        return t
    def parse_primary() -> Any:
        t = peek()
        if t is None:
            raise ValueError("unexpected end")
        if t.startswith("\"") and t.endswith("\""):
            get()
            try:
                return ("str", json.loads(t))
            except Exception:
                raise ValueError("bad quoted string in expr")
        if t == "(":
            get()
            e = parse_expr(0)
            if get() != ")":
                raise ValueError("missing )")
            return ("paren", e)
        if t in ("+", "-", "!", "~"):
            op = get()
            e = parse_primary()
            return ("unary", op, e)
        if t and (t.startswith("0x") or t.isdigit()):
            get()
            v = int(t, 0)
            return ("int", v)
        if t == "store":
            get()
            return ("store",)
        name = get()
        if peek() == "[":
            get()
            idx = parse_expr(0)
            if get() != "]":
                raise ValueError("missing ]")
            return ("var", name, idx)
        return ("var", name, None)
    def parse_expr(min_prec: int) -> Any:
        lhs = parse_primary()
        while True:
            op = peek()
            if op is None or op not in _SYM_TO_OPCODE:
                break
            prec = _expr_prec(op)
            if prec < min_prec:
                break
            get()
            rhs = parse_expr(prec + 1)
            lhs = ("bin", op, lhs, rhs)
        return lhs
    return parse_expr(0)

def _decode_expr_list_from_bytes(b: bytes, argc: int) -> list[Any]:
    r = _ExprReader(b, 0)
    exprs: list[Any] = []
    if argc > 0:
        for _ in range(argc):
            exprs.append(_parse_expr_bool(r))
            if r.peek() == 0x2C:
                r.get()
    else:
        while not r.eof():
            exprs.append(_parse_expr_bool(r))
            if r.peek() == 0x2C:
                r.get()
            else:
                break
    return exprs

def _encode_expr_list_to_bytes(exprs: list[Any], *, text_encoding: str) -> bytes:
    out = bytearray()
    for i, e in enumerate(exprs):
        if i > 0:
            out.append(0x2C)
        _encode_expr(e, out, text_encoding=text_encoding)
    return bytes(out)

def _encode_expr_list_to_bytes_no_commas(exprs: list[Any], *, text_encoding: str) -> bytes:
    out = bytearray()
    for e in exprs:
        _encode_expr(e, out, text_encoding=text_encoding)
    return bytes(out)

def _expr_begins_unary(e: Any) -> bool:
    if not isinstance(e, tuple) or not e:
        return False
    if e[0] == "int":
        try:
            return int(e[1]) < 0
        except Exception:
            return False
    if e[0] == "unary":
        return True
    if e[0] == "bin":
        return _expr_begins_unary(e[2])
    return False

def _encode_expr_list_with_optional_commas(exprs: list[Any], *, text_encoding: str) -> bytes:
    out = bytearray()
    for i, e in enumerate(exprs):
        if i > 0 and _expr_begins_unary(e):
            out.append(0x2C)
        _encode_expr(e, out, text_encoding=text_encoding)
    return bytes(out)

def _decode_expr_list_with_optional_commas(raw: bytes) -> Optional[list[Any]]:
    out: list[Any] = []
    i = 0
    try:
        while i < len(raw):
            while i < len(raw) and raw[i] in (0x2C, 0x20):
                i += 1
            if i >= len(raw):
                break
            e, j = _decode_expr_at(raw, i)
            out.append(e)
            i = j
    except Exception:
        return None
    return out

def _encode_ctrl8194(data: dict[str, Any]) -> bytes:
    typ = int(data["type"])
    idx = int(data["idx"])
    tens = (idx // 10) % 10
    ones = idx % 10
    w1 = 0x8260 if typ == 1 else 0x8261
    w2 = 0x824F + tens
    w3 = 0x824F + ones
    out = bytearray()
    out += p16le(0x8194)
    out += p16le(w1)
    out += p16le(w2)
    out += p16le(w3)
    return bytes(out)

def encode_node(n: Node, spec_ops: dict[int, dict], *, text_encoding: str = "cp932", prefer_raw: bool = True) -> bytes:
    if prefer_raw and "_raw" in n.data:
        return bytes.fromhex(n.data["_raw"])
    if n.kind == "Sym":
        ch = n.data["ch"]
        inv = {"(": 0x28, ")": 0x29, "[": 0x5B, "]": 0x5D}
        if ch not in inv:
            raise ValueError(f"unknown Sym {ch!r}")
        return bytes([inv[ch]])
    if n.kind == "Esc":
        return bytes([0x5C, int(n.data["x"], 16)])
    if n.kind == "Ctrl8194":
        return _encode_ctrl8194(n.data)
    if n.kind == "Text":
        if prefer_raw and "hex" in n.data:
            return bytes.fromhex(n.data["hex"])
        return str(n.data.get("text", "")).encode(text_encoding, errors="ignore")
    if n.kind == "Bytes":
        return bytes.fromhex(n.data["hex"])
    if n.kind == "QBytes":
        return bytes.fromhex(n.data["hex"])
    if n.kind == "U32":
        return p32le(int(n.data["val"]))
    if n.kind == "U16":
        return p16le(int(n.data["val"]))
    if n.kind == "U8":
        return bytes([int(n.data["val"]) & 0xFF])
    if n.kind == "PadBytes":
        return bytes([0xFF]) * int(n.data["count"])
    if n.kind == "PadWord":
        w = int(n.data["word"], 16)
        return p16le(w) * int(n.data["count"])
    if n.kind == "Dollar":
        kind = n.data["kind"]
        if kind == "FF":
            return bytes([0x24, 0xFF]) + p32le(int(n.data["val"]))
        out = bytearray()
        out.append(0x24)
        out.append(int(kind, 16))
        if n.data.get("bracket"):
            out.append(0x5B)
            out += bytes.fromhex(n.data.get("expr_hex", ""))
            out.append(0x5D)
        else:
            out += bytes.fromhex(n.data.get("expr_hex", ""))
        return bytes(out)
    if n.kind == "Op":
        op = int(n.data["op"], 16)
        info = spec_ops.get(op)
        if not info:
            # Allow raw opbytes with no args
            args = n.data.get("args") or {}
            if not args:
                return bytes([op & 0xFF])
            raise ValueError(f"unknown op {n.data['op']}")
        args = n.data["args"]
        out = bytearray([op])
        for a in info.get("args", []):
            t = a["type"]
            nm = a["name"]
            if t == "u8":
                out.append(int(args[nm]) & 0xFF)
            elif t == "u16":
                out += p16le(int(args[nm]))
            elif t == "u24":
                out += p24le(int(args[nm]))
            else:
                raise ValueError(f"encode unsupported arg type {t}")
        if op == 0x23 and "parens" in args:
            tmp = bytearray()
            for item in args["parens"]["items"]:
                node_kind = item["node_kind"]
                node_data = {k: v for k, v in item.items() if k != "node_kind"}
                tmp += encode_node(Node(node_kind, node_data), spec_ops, text_encoding=text_encoding, prefer_raw=prefer_raw)
            # Jump-family hashcalls (goto/goto_unless/goto_case/goto_on/gosub_*)
            # store a synthetic wrapper in parens-items.
            g = int(args.get("group", 0))
            s = int(args.get("sub", 0))
            f = int(args.get("op16", 0))
            is_jump_family = (g, s, f) in (
                (0, 1, 0), (0, 1, 2), (0, 1, 3), (0, 1, 4), (0, 1, 8), (0, 1, 9)
            )
            if is_jump_family and len(tmp) >= 2 and tmp[0] == 0x28 and tmp[-1] == 0x29:
                # Only goto/goto_unless store condition bytes without outer "()".
                if (g, s, f) in ((0, 1, 0), (0, 1, 2)):
                    tmp = tmp[1:-1]
            out += tmp
        return bytes(out)
    if n.kind == "OpByte":
        op = int(n.data["op"], 16)
        return bytes([op & 0xFF])
    raise ValueError(f"cannot encode node kind={n.kind}")

def encode_nodes(nodes: Iterable[Node], spec: dict, *, text_encoding: str = "cp932", prefer_raw: bool = True) -> bytes:
    node_list = list(nodes)
    spec_ops = {int(o["op"], 16): o for o in spec.get("ops", [])}
    op_offsets, node_to_op_index, _ = _compute_op_offsets_from_nodes(
        node_list, spec=spec, text_encoding=text_encoding
    )
    out = bytearray()
    last_op_index: Optional[int] = None
    for idx, n in enumerate(node_list):
        if n.kind == "Op":
            last_op_index = node_to_op_index.get(idx)
        if n.kind == "U32" and n.data.get("rel") and last_op_index is not None:
            delta = int(n.data.get("val", 0))
            tgt_index = last_op_index + delta
            if tgt_index < 0 or tgt_index >= len(op_offsets):
                raise ValueError("relative jump target out of range")
            out += p32le(op_offsets[tgt_index])
            continue
        if n.kind == "Bytes" and n.data.get("_jump_table") and n.data.get("jump_table_entries") is not None:
            if last_op_index is None:
                raise ValueError("jump table without preceding op")
            kind = str(n.data.get("jump_table_kind", ""))
            entries = n.data.get("jump_table_entries")
            if kind == "case":
                raw_tbl = _build_jump_table_case_bytes(
                    entries,
                    base_op_index=last_op_index,
                    op_offsets=op_offsets,
                    text_encoding=text_encoding,
                )
            else:
                raw_tbl = _build_jump_table_on_bytes(
                    entries,
                    base_op_index=last_op_index,
                    op_offsets=op_offsets,
                )
            out += raw_tbl
            continue
        out += encode_node(n, spec_ops, text_encoding=text_encoding, prefer_raw=prefer_raw)
    return bytes(out)


def _compute_op_offsets_from_nodes(
    nodes: list[Node], *, spec: dict, text_encoding: str
) -> tuple[list[int], dict[int, int], dict[int, int]]:
    spec_ops = {int(o["op"], 16): o for o in spec.get("ops", [])}
    op_offsets: list[int] = []
    node_to_op_index: dict[int, int] = {}
    offset_to_op_index: dict[int, int] = {}
    cur = 0
    for idx, n in enumerate(nodes):
        if n.kind == "Op":
            op_index = len(op_offsets)
            op_offsets.append(cur)
            node_to_op_index[idx] = op_index
            offset_to_op_index[cur] = op_index
        if n.kind == "Bytes" and n.data.get("_jump_table") and n.data.get("jump_table_entries") is not None:
            kind = str(n.data.get("jump_table_kind", "on"))
            entries = n.data.get("jump_table_entries")
            cur += _estimate_jump_table_len(kind=kind, entries=entries, text_encoding=text_encoding)
            continue
        cur += len(encode_node(n, spec_ops, text_encoding=text_encoding, prefer_raw=True))
    return op_offsets, node_to_op_index, offset_to_op_index

def _escape_kprl_text(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)

def _unescape_kprl_text(s: str) -> str:
    t = s.strip()
    if len(t) >= 2 and t[0] == "\"" and t[-1] == "\"":
        return json.loads(t)
    return s

def _unescape_kprl_text_loose(s: str) -> str:
    # For unquoted text lines: honor simple escape sequences.
    return (
        s.replace("\\u3000", chr(0x3000))
         .replace("\\r", "\r")
         .replace("\\n", "\n")
         .replace("\\\\", "\\")
    )

def _bytes_to_kprl_arg(b: bytes) -> str:
    out = []
    for ch in b:
        if 0x20 <= ch <= 0x7E and ch not in (0x5C, 0x28, 0x29):
            out.append(chr(ch))
        else:
            out.append(f"\\x{ch:02X}")
    return "".join(out)

def _kprl_arg_to_bytes(s: str, *, text_encoding: str) -> bytes:
    out = bytearray()
    i = 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            n = s[i + 1]
            if n == "x" and i + 3 < len(s):
                hh = s[i + 2 : i + 4]
                out.append(int(hh, 16))
                i += 4
                continue
            if n == "n":
                out.append(0x0A)
                i += 2
                continue
            if n == "r":
                out.append(0x0D)
                i += 2
                continue
            if n == "t":
                out.append(0x09)
                i += 2
                continue
            out.append(ord(n))
            i += 2
            continue
        out += c.encode(text_encoding, errors="replace")
        i += 1
    return bytes(out)

def _parens_items_to_bytes(items: list[dict[str, Any]], spec: dict, *, text_encoding: str) -> bytes:
    buf = bytearray()
    spec_ops = {int(o["op"], 16): o for o in spec.get("ops", [])}
    for it in items:
        kind = it["node_kind"]
        data = {k: v for k, v in it.items() if k != "node_kind"}
        buf += encode_node(Node(kind, data), spec_ops, text_encoding=text_encoding, prefer_raw=True)
    if len(buf) >= 2 and buf[0] == 0x28 and buf[-1] == 0x29:
        buf = buf[1:-1]
    return bytes(buf)

def _bytes_to_parens_items(b: bytes, spec: dict, *, text_encoding: str) -> list[dict[str, Any]]:
    dec = Decoder(spec, text_encoding=text_encoding)
    wrapped = b"\x28" + b + b"\x29"
    node, _ = dec.parse_parens_block(wrapped, 0)
    return node.data.get("items", [])

def _node_to_kprl_lines(
    n: Node,
    *,
    spec: dict,
    text_encoding: str,
    hashcall_map: dict[tuple[int, int, int, int], KfnOpDef],
    opfmt_map: dict[object, list[Optional[str]]],
    prev_node: Optional[Node] = None,
    next_node: Optional[Node] = None,
    allow_script_block: bool = True,
    node_index: Optional[int] = None,
    node_to_op_index: Optional[dict[int, int]] = None,
    offset_to_op_index: Optional[dict[int, int]] = None,
) -> list[str]:
    def _strip_named_arg_prefix(s: str, name: str) -> str:
        p = f"{name}="
        return s[len(p):].strip() if s.strip().startswith(p) else s

    if n.kind == "Op":
        args = n.data.get("args", {})
        op = n.data["op"].upper()
        if int(op, 16) == 0x23:
            group = int(args.get("group", 0))
            sub = int(args.get("sub", 0))
            op16 = int(args.get("op16", 0))
            argc = int(args.get("argc", 0))
            overload = int(args.get("overload", 0))
            key = (group, sub, op16, overload)
            defn = hashcall_map.get(key)
            name = defn.name if defn else f"op_{group}_{sub}_{op16:05d}"
            par = args.get("parens")
            arg_str = ""
            raw_hex = ""
            fmt_candidates = _iter_fmt_candidates(_get_opfmt(opfmt_map, group, sub, op16), argc)
            had_parens = isinstance(par, dict) and "items" in par
            if isinstance(par, dict) and "items" in par:
                raw = _parens_items_to_bytes(par["items"], spec, text_encoding=text_encoding)
                raw_hex = raw.hex().upper()
                blob_lines: list[str] = []
                if (group, sub, op16) == (1, 33, 73):
                    idp = _parse_ident_token(raw, 0, text_encoding=text_encoding)
                    if idp:
                        s0, p0 = idp
                        try:
                            e1, p1 = _decode_expr_at(raw, p0)
                            if p1 == len(raw):
                                arg_str = f"{s0}, {_expr_to_str(e1)}"
                        except Exception:
                            pass
                if (group, sub, op16) == (1, 10, 0):
                    try:
                        e0, p0 = _decode_expr_at(raw, 0)
                        if p0 < len(raw) and raw[p0] == 0x22:
                            q0 = _parse_quoted_string(raw, p0, text_encoding=text_encoding)
                            if q0:
                                qs, p1 = q0
                                if p1 == len(raw):
                                    arg_str = f"{_expr_to_str(e0)}, {qs}"
                    except Exception:
                        pass
                if (group, sub, op16) == (1, 71, 1200):
                    try:
                        e0, p0 = _decode_expr_at(raw, 0)
                        q0 = _parse_quoted_string(raw, p0, text_encoding=text_encoding)
                        if q0:
                            qs, p1 = q0
                            e1, p2 = _decode_expr_at(raw, p1)
                            e2, p3 = _decode_expr_at(raw, p2)
                            e3, p4 = _decode_expr_at(raw, p3)
                            k = p2
                            # Some streams place an explicit arg-separator escape before a parenthesized arg.
                            if k + 2 < len(raw) and raw[k] == 0x5C and raw[k + 2] == 0x28:
                                k += 2
                            a4 = f"({_expr_to_str(e2)})" if raw[k:k+1] == b"\x28" else _expr_to_str(e2)
                            if p4 == len(raw):
                                arg_str = ", ".join([_expr_to_str(e0), qs, _expr_to_str(e1), a4, _expr_to_str(e3)])
                    except Exception:
                        pass
                if (not arg_str or arg_str.startswith("RAW[")) and (group, sub, op16) == (1, 71, 1200):
                    # Variant with bare (unquoted) text payload after arg0, usually comma-delimited.
                    try:
                        e0, p0 = _decode_expr_at(raw, 0)
                        if not (p0 < len(raw) and raw[p0] == 0x2C):
                            raise ValueError("no comma-delimited text segment")
                        p_txt = p0 + 1
                        for cut in range(p_txt + 1, len(raw)):
                            try:
                                tb = raw[p_txt:cut]
                                if not tb:
                                    continue
                                if any(b < 0x20 for b in tb):
                                    continue
                                txt = tb.decode(text_encoding, errors="replace")
                                i = cut
                                if i < len(raw) and raw[i] == 0x2C:
                                    i += 1
                                e1, i1 = _decode_expr_at(raw, i)
                                i = i1
                                if i < len(raw) and raw[i] == 0x2C:
                                    i += 1
                                paren_mid = False
                                if i < len(raw) and raw[i] == 0x28:
                                    paren_mid = True
                                    e2, j2 = _decode_expr_at(raw, i + 1)
                                    if j2 >= len(raw) or raw[j2] != 0x29:
                                        continue
                                    i = j2 + 1
                                else:
                                    e2, i = _decode_expr_at(raw, i)
                                if i < len(raw) and raw[i] == 0x2C:
                                    i += 1
                                e3, i = _decode_expr_at(raw, i)
                                if i != len(raw):
                                    continue
                                a2 = _expr_to_str(e2)
                                if paren_mid:
                                    a2 = f"({a2})"
                                arg_str = ", ".join([_expr_to_str(e0), txt, _expr_to_str(e1), a2, _expr_to_str(e3)])
                                break
                            except Exception:
                                continue
                    except Exception:
                        pass
                if (group, sub, op16) == (1, 81, 1005):
                    try:
                        exprs = _decode_expr_list_greedy(raw) or []
                        if exprs and _encode_expr_list_to_bytes_no_commas(exprs, text_encoding=text_encoding) == raw:
                            arg_str = ", ".join(_expr_to_str(e) for e in exprs)
                    except Exception:
                        pass
                if (not arg_str or arg_str.startswith("RAW[")) and (group, sub, op16) == (1, 81, 1025):
                    # Pattern with optional comma before last argument.
                    try:
                        vals: list[Any] = []
                        i = 0
                        while i < len(raw):
                            if raw[i] == 0x2C:
                                i += 1
                                continue
                            e, j = _decode_expr_at(raw, i)
                            vals.append(e)
                            i = j
                        if vals:
                            arg_str = ", ".join(_expr_to_str(e) for e in vals)
                    except Exception:
                        pass
                if (not arg_str or arg_str.startswith("RAW[")) and (group, sub, op16) == (1, 81, 1001):
                    try:
                        exprs = _decode_expr_list_greedy(raw) or []
                        if len(exprs) == 2:
                            arg_str = ", ".join(_expr_to_str(e) for e in exprs)
                    except Exception:
                        pass
                if (not arg_str or arg_str.startswith("RAW[")) and (group, sub, op16) == (1, 21, 0) and overload == 2:
                    try:
                        idp = _parse_ident_token(raw, 0, text_encoding=text_encoding)
                        if idp:
                            s0, p0 = idp
                            exprs = _decode_expr_list_greedy(raw[p0:]) or []
                            if _encode_expr_list_to_bytes_no_commas(exprs, text_encoding=text_encoding) == raw[p0:]:
                                arg_str = ", ".join([s0] + [_expr_to_str(e) for e in exprs])
                    except Exception:
                        pass
                if (not arg_str or arg_str.startswith("RAW[")) and (group, sub, op16) == (0, 1, 2):
                    # Keep parenthesized boolean form when encoded that way.
                    try:
                        if len(raw) >= 7 and raw[0] == 0x28:
                            p1 = _find_matching_paren(raw, 0)
                            if p1 is not None and p1 + 2 < len(raw) and raw[p1 + 1] == 0x5C and raw[p1 + 2] in (0x3C, 0x3D):
                                i2 = p1 + 3
                                if i2 < len(raw) and raw[i2] == 0x28:
                                    p2 = _find_matching_paren(raw, i2)
                                    if p2 is not None and p2 == len(raw) - 1:
                                        e1, j1 = _decode_expr_at(raw, 1)
                                        e2, j2 = _decode_expr_at(raw, i2 + 1)
                                        if j1 == p1 and j2 == p2:
                                            op_sym = _OPCODE_TO_SYM.get(raw[p1 + 2], f"op{raw[p1+2]:02X}")
                                            ltxt = _strip_one_outer_paren_text(_expr_to_str(e1))
                                            rtxt = _strip_one_outer_paren_text(_expr_to_str(e2))
                                            arg_str = f"({ltxt}) {op_sym} ({rtxt})"
                        if not arg_str:
                            e0, j0 = _decode_expr_at(raw, 0)
                            if j0 == len(raw):
                                arg_str = _expr_to_str(e0)
                    except Exception:
                        pass
                if (group, sub, op16) == (1, 33, 73) and int(args.get("overload", 0)) in (2, 4):
                    try:
                        idp = _parse_ident_token(raw, 0, text_encoding=text_encoding)
                        if idp:
                            s0, p0 = idp
                            exprs = _decode_expr_list_greedy(raw[p0:]) or []
                            if _encode_expr_list_to_bytes_no_commas(exprs, text_encoding=text_encoding) == raw[p0:]:
                                arg_str = ", ".join([s0] + [_expr_to_str(e) for e in exprs])
                    except Exception:
                        pass
                # Keep arguments encoder-friendly by avoiding non-reversible pretty printers.
                special_args = None
                if special_args:
                    arg_str = special_args
                # For giant goto blobs, emit an editable node-hex block instead of one giant RAW line.
                # Intentionally disabled: large goto script block expansion.
                # Keep raw-aligned output unless explicitly requested again.
                try:
                    if not arg_str:
                        decoded_ok = False
                        for fmt_use in fmt_candidates:
                            if set(fmt_use) <= {"$"}:
                                exprs = _decode_expr_list_from_bytes(raw, len(fmt_use))
                                enc_a = _encode_expr_list_to_bytes(exprs, text_encoding=text_encoding)
                                enc_b = _encode_expr_list_to_bytes_no_commas(exprs, text_encoding=text_encoding)
                                if enc_a != raw and enc_b != raw:
                                    continue
                                if defn and defn.param_sigs:
                                    sig = next((s for s in defn.param_sigs if len(s) == len(exprs)), None)
                                    if sig:
                                        arg_str = ", ".join(_expr_to_str(exprs[i]) for i in range(len(exprs)))
                                    else:
                                        arg_str = ", ".join(_expr_to_str(e) for e in exprs)
                                else:
                                    arg_str = ", ".join(_expr_to_str(e) for e in exprs)
                                decoded_ok = True
                                break
                            if any(c in fmt_use for c in ("%", "&", "S")):
                                decoded = _decode_args_by_format(raw, fmt_use, text_encoding=text_encoding)
                                if not decoded:
                                    continue
                                enc_check = _encode_args_by_format(decoded, fmt_use, text_encoding=text_encoding)
                                enc_check_c = _encode_args_by_format(decoded, fmt_use, text_encoding=text_encoding, with_commas=True)
                                if enc_check != raw and enc_check_c != raw:
                                    continue
                                arg_str = ", ".join(decoded)
                                decoded_ok = True
                                break
                        if not decoded_ok:
                            exprs = _decode_expr_list_from_bytes(raw, argc)
                            enc_a = _encode_expr_list_to_bytes(exprs, text_encoding=text_encoding)
                            enc_b = _encode_expr_list_to_bytes_no_commas(exprs, text_encoding=text_encoding)
                            if enc_a == raw or enc_b == raw:
                                if defn and defn.param_sigs:
                                    sig = next((s for s in defn.param_sigs if len(s) == len(exprs)), None)
                                    if sig:
                                        arg_str = ", ".join(_expr_to_str(exprs[i]) for i in range(len(exprs)))
                                    else:
                                        arg_str = ", ".join(_expr_to_str(e) for e in exprs)
                                else:
                                    arg_str = ", ".join(_expr_to_str(e) for e in exprs)
                            else:
                                arg_str = f"RAW[{raw_hex}]"
                except StopIteration:
                    pass
                except Exception:
                    arg_str = f"RAW[{raw_hex}]"
                if (not arg_str) or arg_str.startswith("RAW["):
                    parts_mixed = _decode_mixed_parts(raw, text_encoding=text_encoding, allow_paren=True)
                    if parts_mixed:
                        enc_mixed = _encode_mixed_parts(parts_mixed, text_encoding=text_encoding)
                        if enc_mixed == raw:
                            arg_str = ", ".join(parts_mixed)
                if (not arg_str or arg_str.startswith("RAW[")) and (group, sub, op16) in ((1, 71, 1000), (1, 71, 1300), (1, 72, 1000)):
                    try:
                        e0, p0 = _decode_expr_at(raw, 0)
                        p1 = p0 + (1 if p0 < len(raw) and raw[p0] == 0x2C else 0)
                        idp = _parse_ident_token(raw, p1, text_encoding=text_encoding)
                        if idp:
                            s1, p2 = idp
                            tail = raw[p2:]
                            expr_tail = _decode_expr_list_greedy(tail) or []
                            bchk = bytearray()
                            bchk += _encode_single_expr_to_bytes(e0, text_encoding=text_encoding)
                            bchk.append(0x2C)
                            bchk += s1.encode(text_encoding, errors="replace")
                            bchk += _encode_expr_list_to_bytes_no_commas(expr_tail, text_encoding=text_encoding)
                            if bytes(bchk) == raw:
                                arg_str = ", ".join([_expr_to_str(e0), s1] + [_expr_to_str(e) for e in expr_tail])
                            else:
                                # Some streams insert optional commas between tail expressions.
                                i = p2
                                got: list[Any] = []
                                while i < len(raw):
                                    if raw[i] == 0x2C:
                                        i += 1
                                        continue
                                    ee, j = _decode_expr_at(raw, i)
                                    got.append(ee)
                                    i = j
                                bb = bytearray()
                                bb += _encode_single_expr_to_bytes(e0, text_encoding=text_encoding)
                                bb.append(0x2C)
                                bb += s1.encode(text_encoding, errors="replace")
                                ti = p2
                                for ee in got:
                                    if ti < len(raw) and raw[ti] == 0x2C:
                                        bb.append(0x2C)
                                        ti += 1
                                    eb = _encode_single_expr_to_bytes(ee, text_encoding=text_encoding)
                                    bb += eb
                                    ti += len(eb)
                                if bytes(bb) == raw:
                                    arg_str = ", ".join([_expr_to_str(e0), s1] + [_expr_to_str(e) for e in got])
                    except Exception:
                        pass
                if (not arg_str or arg_str.startswith("RAW[")) and name in ("objRepOrigin", "objShow", "InitExFrame"):
                    try:
                        exprs_nc = _decode_expr_list_greedy(raw) or []
                        if _encode_expr_list_to_bytes_no_commas(exprs_nc, text_encoding=text_encoding) == raw:
                            arg_str = ", ".join(_expr_to_str(e) for e in exprs_nc)
                    except Exception:
                        pass
                if (not arg_str or arg_str.startswith("RAW[")) and name == "objMove":
                    try:
                        exprs_mv = _decode_expr_list_with_optional_commas(raw) or []
                        if len(exprs_mv) == 3:
                            arg_str = ", ".join(_expr_to_str(e) for e in exprs_mv)
                    except Exception:
                        pass
                if (not arg_str or arg_str.startswith("RAW[")) and name in ("objDriftOpts", "objScale", "objTop", "InitFrame"):
                    try:
                        exprs_mv = _decode_expr_list_with_optional_commas(raw) or []
                        if exprs_mv:
                            arg_str = ", ".join(_expr_to_str(e) for e in exprs_mv)
                    except Exception:
                        pass
                if (not arg_str or arg_str.startswith("RAW[")) and name == "grpOpenBg":
                    try:
                        idp = _parse_ident_token(raw, 0, text_encoding=text_encoding)
                        if idp:
                            s0, p0 = idp
                            exprs_mv = _decode_expr_list_with_optional_commas(raw[p0:]) or []
                            if exprs_mv:
                                arg_str = ", ".join([s0] + [_expr_to_str(e) for e in exprs_mv])
                    except Exception:
                        pass
            args_out = [p.strip() for p in _split_top_level_commas(arg_str)] if arg_str.strip() else []
            rendered_argc = len(args_out)
            if (group, sub, op16) == (0, 1, 2) and args_out:
                args_out[0] = _strip_named_arg_prefix(args_out[0], "condition")
                c0 = args_out[0].strip()
                if c0.startswith("((") and c0.endswith("))") and ("&&" not in c0 and "||" not in c0):
                    args_out[0] = _strip_one_outer_paren_text(c0)
            if (group, sub, op16) in ((0, 1, 4), (0, 1, 9)) and args_out:
                a0 = args_out[0].strip()
                if a0.startswith("(") and a0.endswith(")"):
                    inner = a0[1:-1].strip()
                    if inner:
                        args_out[0] = inner
            if _is_ambiguous_name(hashcall_map, name) or (int(args.get("overload", 0)) != 0):
                args_out.append(f"_sig={_sig_of_args(args)}")
            has_raw_arg = any(x.strip().startswith("RAW[") and x.strip().endswith("]") for x in args_out)
            if (
                (group, sub, op16) not in ((0, 1, 0), (0, 1, 2), (0, 1, 3), (0, 1, 4), (0, 1, 8), (0, 1, 9))
                and (int(args.get("argc", 0)) != rendered_argc or has_raw_arg)
            ):
                args_out.append(f"_argc={int(args.get('argc', 0))}")

            if (group, sub, op16) in ((0, 1, 0), (0, 1, 2)) and next_node and next_node.kind == "U32":
                try:
                    target = int(next_node.data.get("val", 0)) & 0xFFFFFFFF
                    args_out.append(f"{target:X}")
                except Exception:
                    pass
            elif (group, sub, op16) in ((0, 1, 0), (0, 1, 2)) and next_node and next_node.kind == "Bytes":
                try:
                    tail_hex = str(next_node.data.get("hex", "") or "").upper()
                    if tail_hex:
                        args_out.append(f"RAW[{tail_hex}]")
                except Exception:
                    pass
            if _is_jump_table_hashcall_op(n) and next_node and next_node.kind == "Bytes" and next_node.data.get("_jump_table"):
                try:
                    if next_node.data.get("jump_table_entries") is not None:
                        kind = str(next_node.data.get("jump_table_kind", ""))
                        entries = next_node.data.get("jump_table_entries")
                        if kind == "case":
                            parts = []
                            for expr_tok, mode, val in entries:
                                tgt_txt = f"{val:+d}" if mode == "rel" else f"{val:X}"
                                parts.append(f"({expr_tok}, {tgt_txt})")
                            args_out.append("{" + ", ".join(parts) + "}")
                        else:
                            parts = []
                            for mode, val in entries:
                                parts.append(f"{val:+d}" if mode == "rel" else f"{val:X}")
                            args_out.append("{" + ", ".join(parts) + "}")
                    else:
                        tbl_hex = str(next_node.data.get("hex", "") or "").upper()
                        if tbl_hex:
                            raw_tbl = bytes.fromhex(tbl_hex)
                            tbl_text: Optional[str] = None
                            if (group, sub, op16) in ((0, 1, 4), (0, 1, 9)):
                                tbl_text = _decode_jump_table_case_to_text(
                                    raw_tbl,
                                    offset_to_op_index=offset_to_op_index,
                                    base_op_index=(node_to_op_index.get(node_index) if node_to_op_index and node_index is not None else None),
                                )
                            elif (group, sub, op16) in ((0, 1, 3), (0, 1, 8)):
                                tbl_text = _decode_jump_table_on_to_text(
                                    raw_tbl,
                                    offset_to_op_index=offset_to_op_index,
                                    base_op_index=(node_to_op_index.get(node_index) if node_to_op_index and node_index is not None else None),
                                )
                            args_out.append(tbl_text if tbl_text else f"RAW[{tbl_hex}]")
                except Exception:
                    pass

            arg_str = ", ".join([x for x in args_out if x])
            if name == "title":
                title_txt = arg_str.strip()
                title_txt = (
                    title_txt.replace("\\", "\\\\")
                             .replace("\r", "\\r")
                             .replace("\n", "\\n")
                             .replace("\u3000", "\\u3000")
                )
                return ["fun title(", title_txt, ")"]
            # Multiline fun with single text argument (quoted or bare).
            str_indices = [i for i, a in enumerate(args_out) if a.startswith("\"") and a.endswith("\"")]
            bare_indices = [
                i for i, a in enumerate(args_out)
                if a and any(ord(ch) >= 0x80 for ch in a)
                and not a.startswith("$") and not a.startswith("%")
                and not re.fullmatch(r"-?(?:0x[0-9A-Fa-f]+|\d+)", a)
                and "," not in a
            ]
            pick: Optional[int] = None
            if len(str_indices) == 1:
                pick = str_indices[0]
            elif len(str_indices) == 0 and len(bare_indices) == 1:
                pick = bare_indices[0]
            if pick is not None:
                raw_txt = args_out[pick]
                txt_line = (
                    raw_txt.replace("\\", "\\\\")
                           .replace("\r", "\\r")
                           .replace("\n", "\\n")
                           .replace("\u3000", "\\u3000")
                )
                prefix = ", ".join(x for x in args_out[:pick] if x)
                suffix = ", ".join(x for x in args_out[pick + 1:] if x)
                out_lines = [f"fun {name}("]
                if prefix:
                    out_lines.append(prefix + ",")
                out_lines.append(txt_line)
                if suffix:
                    out_lines.append(", " + suffix)
                out_lines.append(")")
                return out_lines
            # Multiline fun with single bare text argument (e.g. kana/kanji identifier).
            if len(args_out) == 1:
                a0 = args_out[0].strip()
                if a0 and (any(ord(ch) >= 0x80 for ch in a0)) and ("," not in a0):
                    txt_line = (
                        a0.replace("\\", "\\\\")
                           .replace("\r", "\\r")
                           .replace("\n", "\\n")
                           .replace("\u3000", "\\u3000")
                    )
                    return [f"fun {name}(", txt_line, ")"]
            out_lines = [f"fun {name}({arg_str})"]
            if isinstance(par, dict) and "items" in par and "blob_lines" in locals() and blob_lines:
                out_lines.extend(blob_lines)
            return out_lines
        opi = int(op, 16)
        info = {int(o["op"], 16): o for o in spec.get("ops", [])}.get(opi) or {}
        ordered_vals: list[str] = []
        for a in info.get("args", []):
            nm = a.get("name")
            if nm == "parens":
                continue
            if nm in args:
                ordered_vals.append(str(int(args.get(nm, 0))))
        if ordered_vals:
            return [f"op {op} " + " ".join(ordered_vals)]
        return [f"op {op}"]
    if n.kind == "OpByte":
        op = n.data.get("op", "")
        return [f"op {op}"]

    if n.kind == "Text":
        txt = str(n.data.get("text", ""))
        # Multiline text output: keep unquoted, escape control sequences.
        txt_arg = (
            txt.replace("\\", "\\\\")
               .replace("\r", "\\r")
               .replace("\n", "\\n")
               .replace("\u3000", "\\u3000")
        )
        if prev_node and prev_node.kind == "Op" and str(prev_node.data.get("op", "")).upper() == "40":
            kidoku = int((prev_node.data.get("args") or {}).get("kidoku", 0))
            line = f"text({txt_arg}, {kidoku})"
        else:
            line = f"string({txt_arg})"
        # Multiline text layout:
        # text(
        # <text>
        # , <kidoku>)  or )
        if line.startswith("text("):
            return ["text(", txt_arg, f", {kidoku})"]
        if line.startswith("string("):
            return ["string(", txt_arg, ")"]
        return [line]
    if n.kind == "Bytes":
        return ["bytes " + (n.data.get("hex", "") or "")]
    if n.kind == "QBytes":
        return ["qbytes " + (n.data.get("hex", "") or "")]
    if n.kind == "U32":
        v = int(n.data.get("val", 0))
        return [f"u32 0x{v:08X}"]
    if n.kind == "U16":
        v = int(n.data.get("val", 0)) & 0xFFFF
        return [f"u16 0x{v:04X}"]
    if n.kind == "U8":
        v = int(n.data.get("val", 0)) & 0xFF
        return [f"u8 0x{v:02X}"]
    if n.kind == "Sym":
        ch = str(n.data["ch"])
        return [f"sym {ch}"]
    if n.kind == "Esc":
        return [f"esc {n.data['x']}"]
    if n.kind == "Dollar":
        if n.data.get("kind") == "FF":
            return [f"dollarff {int(n.data['val'])}"]
        br = 1 if n.data.get("bracket") else 0
        expr = n.data.get("expr_hex", "") or ""
        return [f"dollar {n.data['kind']} {br} {expr}".rstrip()]
    if n.kind == "PadBytes":
        return [f"padbytes {int(n.data['count'])}"]
    if n.kind == "PadWord":
        return [f"padword {n.data['word']} {int(n.data['count'])}"]
    if n.kind == "Ctrl8194":
        return [f"ctrl8194 type={int(n.data['type'])} mode={int(n.data['mode'])} idx={int(n.data['idx'])}"]
    raise ValueError(f"cannot kprl-dump node kind={n.kind}")

def write_kprl(
    path: Path,
    *,
    header: bytes,
    ver: int,
    xlen: int,
    text_encoding: str,
    nodes: list[Node],
    spec: dict,
    hashcall_map: dict[tuple[int, int, int, int], KfnOpDef],
    opfmt_map: dict[object, list[Optional[str]]],
) -> None:
    lines: list[str] = []
    lines.append("#kprl-lite")
    lines.append(f"#text_encoding {text_encoding}")
    lines.append(f"#ver 0x{ver:08X}")
    lines.append(f"#xlen {xlen}")
    lines.append(f"#off {len(header)}")
    lines.append("#header " + header.hex().upper())
    lines.append("")

    op_offsets, node_to_op_index, offset_to_op_index = _compute_op_offsets_from_nodes(
        nodes, spec=spec, text_encoding=text_encoding
    )
    for idx, n in enumerate(nodes):
        prev_node = nodes[idx - 1] if idx > 0 else None
        next_node = nodes[idx + 1] if idx + 1 < len(nodes) else None
        if n.kind == "Op" and str(n.data.get("op", "")).upper() == "40" and next_node and next_node.kind == "Text":
            continue
        if n.kind == "U32" and _is_jump_hashcall_op(prev_node):
            continue
        if n.kind == "Bytes" and n.data.get("_jump_table") and _is_jump_table_hashcall_op(prev_node):
            continue
        lines.extend(
            _node_to_kprl_lines(
                n,
                spec=spec,
                text_encoding=text_encoding,
                hashcall_map=hashcall_map,
                opfmt_map=opfmt_map,
                prev_node=prev_node,
                next_node=next_node,
                node_index=idx,
                node_to_op_index=node_to_op_index,
                offset_to_op_index=offset_to_op_index,
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", errors="strict")

def read_kprl(
    path: Path,
    *,
    spec: dict,
    text_encoding: str,
    hashcall_map: dict[tuple[int, int, int, int], KfnOpDef],
    opfmt_map: dict[object, list[Optional[str]]],
) -> tuple[bytes, int, int, Optional[str], list[Node]]:
    header_hex = None
    ver = None
    xlen = None
    file_text_encoding: Optional[str] = None
    nodes: list[Node] = []

    lines = path.read_text(encoding="utf-8").splitlines()

    def _parse_body_lines(body_lines: list[str], file_enc: Optional[str]) -> list[Node]:
        out_nodes: list[Node] = []
        bi = 0
        while bi < len(body_lines):
            raw_line = body_lines[bi]
            line = raw_line.strip()
            bi += 1
            if not line or line.startswith(";"):
                continue
            if line.startswith("#"):
                continue

            low = line.lower()
            if low == "fun title(":
                if bi + 1 >= len(body_lines):
                    raise ValueError("multiline title missing lines")
                text_line = body_lines[bi]
                tail_line = body_lines[bi + 1].strip()
                bi += 2
                if not tail_line.startswith(")"):
                    raise ValueError("multiline title missing closing )")
                line = f"fun title({text_line})"
            if low in ("text(", "string("):
                if bi + 1 > len(body_lines):
                    raise ValueError("multiline text/string missing lines")
                if bi >= len(body_lines):
                    raise ValueError("multiline text/string missing text line")
                if bi + 1 >= len(body_lines):
                    raise ValueError("multiline text/string missing tail line")
                text_line = body_lines[bi]
                tail_line = body_lines[bi + 1].strip()
                bi += 2
                line = f"{line}{text_line}{tail_line}"

            if line.startswith("fun "):
                name_and_rest = line[4:].strip()
                if name_and_rest.endswith("(") and ")" not in name_and_rest:
                    if bi >= len(body_lines):
                        raise ValueError("multiline fun missing lines")
                    mid_lines: list[str] = []
                    while bi < len(body_lines):
                        t = body_lines[bi].strip()
                        bi += 1
                        if t == ")":
                            break
                        mid_lines.append(t)
                    if not mid_lines:
                        raise ValueError("multiline fun missing args")
                    # Expect at least a text line; optional prefix/suffix lines.
                    prefix = ""
                    text_line = ""
                    suffix = ""
                    if len(mid_lines) == 1:
                        text_line = mid_lines[0]
                    elif len(mid_lines) >= 2:
                        if mid_lines[0].endswith(","):
                            prefix = mid_lines[0][:-1].strip()
                            text_line = mid_lines[1].strip()
                            if len(mid_lines) > 2:
                                suffix = ", ".join(x.strip().lstrip(",") for x in mid_lines[2:] if x.strip())
                        else:
                            text_line = mid_lines[0].strip()
                            suffix = ", ".join(x.strip().lstrip(",") for x in mid_lines[1:] if x.strip())
                    parts: list[str] = []
                    if prefix:
                        parts.append(prefix)
                    if text_line.startswith("\"") and text_line.endswith("\""):
                        try:
                            inner = json.loads(text_line)
                            parts.append(f"\"{inner}\"")
                        except Exception:
                            parts.append(text_line)
                    else:
                        parts.append(_unescape_kprl_text_loose(text_line))
                    if suffix:
                        parts.append(suffix)
                    name_and_rest = name_and_rest[:-1].strip()
                    name_and_rest = f"{name_and_rest}({', '.join(parts)})"
                if ";" in name_and_rest:
                    main, _comment = name_and_rest.split(";", 1)
                else:
                    main = name_and_rest
                m = re.match(r"([A-Za-z0-9_]+)\((.*)\)", main.strip())
                if not m:
                    raise ValueError(f"bad fun line: {line!r}")
                fname = m.group(1)
                arg_str = m.group(2)
                raw_parts = _split_top_level_commas(arg_str) if arg_str.strip() else []
                sig_token: Optional[str] = None
                argc_token: Optional[int] = None
                table_hex: Optional[str] = None
                kept_parts: list[str] = []
                for p in raw_parts:
                    ms = re.match(r"^\s*_sig\s*=\s*([0-9]+:[0-9]+:[0-9]+:[0-9]+)\s*$", p)
                    if ms:
                        sig_token = ms.group(1)
                        continue
                    ma = re.match(r"^\s*_argc\s*=\s*(-?(?:0x[0-9A-Fa-f]+|\d+))\s*$", p)
                    if ma:
                        argc_token = _parse_int(ma.group(1))
                        continue
                    kept_parts.append(p.strip())
                arg_str = ", ".join([p for p in kept_parts if p])
                defn = _resolve_fun_def(fname=fname, sig_token=sig_token, hashcall_map=hashcall_map)
                op_type, op_module, op_func, overload = defn.op_type, defn.op_module, defn.op_function, defn.overload
                target_u32: Optional[int] = None
                target_rel: Optional[int] = None
                jump_tail_hex: Optional[str] = None
                table_entries: Optional[tuple[str, Any]] = None
                parts_for_special = _split_top_level_commas(arg_str) if arg_str.strip() else []
                if fname.lower() == "title" and parts_for_special:
                    p0 = parts_for_special[0].strip()
                    if not (p0.startswith("\"") and p0.endswith("\"")):
                        parts_for_special[0] = _unescape_kprl_text_loose(p0)
                if (op_type, op_module, op_func) == (0, 1, 0) and parts_for_special:
                    last = parts_for_special[-1].strip()
                    if re.fullmatch(r"[+-]\d+", last):
                        target_rel = int(last, 10)
                        parts_for_special = parts_for_special[:-1]
                    elif re.fullmatch(r"[0-9A-Fa-f]{1,8}", last):
                        target_u32 = _parse_hex_u32_token(last)
                        parts_for_special = parts_for_special[:-1]
                    else:
                        mb = re.match(r"^\s*RAW\[([0-9A-Fa-f]*)\]\s*$", last)
                        if mb and len(parts_for_special) == 1:
                            jump_tail_hex = mb.group(1).upper()
                            parts_for_special = parts_for_special[:-1]
                elif (op_type, op_module, op_func) == (0, 1, 2) and len(parts_for_special) >= 2:
                    last = parts_for_special[-1].strip()
                    if re.fullmatch(r"[+-]\d+", last):
                        target_rel = int(last, 10)
                        parts_for_special = parts_for_special[:-1]
                    elif re.fullmatch(r"[0-9A-Fa-f]{1,8}", last):
                        target_u32 = _parse_hex_u32_token(last)
                        parts_for_special = parts_for_special[:-1]
                    else:
                        mb = re.match(r"^\s*RAW\[([0-9A-Fa-f]*)\]\s*$", last)
                        if mb:
                            jump_tail_hex = mb.group(1).upper()
                            parts_for_special = parts_for_special[:-1]
                elif (op_type, op_module, op_func) in ((0, 1, 3), (0, 1, 4), (0, 1, 8), (0, 1, 9)) and parts_for_special:
                    last_tbl = parts_for_special[-1].strip()
                    mb = re.match(r"^\s*RAW\[([0-9A-Fa-f]*)\]\s*$", last_tbl)
                    if mb:
                        table_hex = mb.group(1).upper()
                        parts_for_special = parts_for_special[:-1]
                    else:
                        try:
                            if (op_type, op_module, op_func) in ((0, 1, 4), (0, 1, 9)):
                                ent = _parse_jump_table_case_entries(last_tbl)
                                if ent is not None:
                                    table_entries = ("case", ent)
                                    parts_for_special = parts_for_special[:-1]
                            else:
                                ent = _parse_jump_table_on_entries(last_tbl)
                                if ent is not None:
                                    table_entries = ("on", ent)
                                    parts_for_special = parts_for_special[:-1]
                        except Exception:
                            pass
                argc_input_count = len(parts_for_special)
                arg_str = ", ".join([p.strip() for p in parts_for_special if p.strip()])
                fmt_candidates = _iter_fmt_candidates(
                    _get_opfmt(opfmt_map, int(op_type), int(op_module), int(op_func)),
                    len(parts_for_special),
                )

                args: dict[str, Any] = {
                    "group": int(op_type),
                    "sub": int(op_module),
                    "op16": int(op_func),
                    "argc": 0,
                    "overload": int(overload or 0),
                }
                # CLI -i must override file header encoding.
                use_enc = text_encoding or file_enc or "cp932"
                arg_bytes = b""
                did_special_block = False

                def _parse_args_exprs(s: str) -> list[Any]:
                    if not s.strip():
                        return []
                    parts = _split_top_level_commas(s)
                    exprs_pos: list[Any] = []
                    exprs_named: dict[str, Any] = {}
                    for p in parts:
                        if "=" in p:
                            n, v = p.split("=", 1)
                            exprs_named[n.strip()] = _parse_expr_text_list_single(v.strip())
                        else:
                            exprs_pos.append(_parse_expr_text_list_single(p.strip()))
                    if defn and defn.param_sigs:
                        sig = next((s for s in defn.param_sigs if len(s) >= len(exprs_named) + len(exprs_pos)), None)
                        if sig:
                            out: list[Any] = []
                            pos_i = 0
                            for name in sig:
                                if name in exprs_named:
                                    out.append(exprs_named[name])
                                elif pos_i < len(exprs_pos):
                                    out.append(exprs_pos[pos_i]); pos_i += 1
                                else:
                                    break
                            return out
                    return exprs_pos

                expr_body = arg_str.strip()
                if expr_body.startswith("SCRIPT_BLOCK"):
                    j = bi
                    while j < len(body_lines) and not body_lines[j].strip():
                        j += 1
                    if j < len(body_lines) and body_lines[j].strip().lower() == "script_block {":
                        j += 1
                        depth = 1
                        inner_lines: list[str] = []
                        while j < len(body_lines):
                            s0 = body_lines[j].strip()
                            if s0.lower() == "script_block {":
                                depth += 1
                                if depth > 1:
                                    inner_lines.append(body_lines[j])
                                j += 1
                                continue
                            if s0 == "}":
                                depth -= 1
                                if depth == 0:
                                    break
                                inner_lines.append(body_lines[j])
                                j += 1
                                continue
                            inner_lines.append(body_lines[j])
                            j += 1
                        if depth != 0:
                            raise ValueError("SCRIPT_BLOCK missing closing '}'")
                        inner_nodes = _parse_body_lines(inner_lines, file_enc)
                        arg_bytes = encode_nodes(inner_nodes, spec, text_encoding=use_enc, prefer_raw=True)
                        did_special_block = True
                        bi = j + 1

                if (not did_special_block) and expr_body.startswith("SCRIPT_BLOB_BLOCK"):
                    j = bi
                    while j < len(body_lines) and not body_lines[j].strip():
                        j += 1
                    if j < len(body_lines) and body_lines[j].strip().lower() == "script_blob_begin":
                        j += 1
                        buf = bytearray()
                        while j < len(body_lines):
                            s = body_lines[j].strip()
                            if s.lower() == "script_blob_end":
                                break
                            if s and not s.startswith(";") and s.lower().startswith("blob_node "):
                                body = s[len("blob_node ") :]
                                hx = body.split(";", 1)[0].strip().replace(" ", "")
                                if hx:
                                    buf += bytes.fromhex(hx)
                            j += 1
                        if j >= len(body_lines) or body_lines[j].strip().lower() != "script_blob_end":
                            raise ValueError("SCRIPT_BLOB_BLOCK missing script_blob_end")
                        arg_bytes = bytes(buf)
                        did_special_block = True
                        bi = j + 1

                if (not did_special_block) and expr_body.startswith("RAW[") and expr_body.endswith("]"):
                    hx = arg_str.strip()[4:-1].strip()
                    arg_bytes = bytes.fromhex(hx) if hx else b""
                elif not did_special_block:
                    if expr_body.startswith("EDIT:"):
                        expr_body = expr_body[5:].strip()
                    did_fmt = False
                    if (int(op_type), int(op_module), int(op_func), int(overload or 0)) == (1, 33, 73, 0) and expr_body:
                        p2 = _split_top_level_commas(expr_body)
                        if len(p2) >= 2:
                            left = p2[0].strip()
                            right = ",".join(p2[1:]).strip()
                            try:
                                e2 = _parse_expr_text_list_single(right)
                                arg_bytes = left.encode(use_enc, errors="replace") + _encode_single_expr_to_bytes(e2, text_encoding=use_enc)
                                args["argc"] = 2
                                did_fmt = True
                            except Exception:
                                did_fmt = False
                    if (not did_fmt) and (int(op_type), int(op_module), int(op_func)) == (1, 10, 0) and expr_body:
                        p2 = _split_top_level_commas(expr_body)
                        if len(p2) >= 2:
                            left = p2[0].strip()
                            right = ",".join(p2[1:]).strip()
                            try:
                                e2 = _parse_expr_text_list_single(left)
                                b2 = _encode_quoted_string_token(right, text_encoding=use_enc)
                                if b2 is not None:
                                    arg_bytes = _encode_single_expr_to_bytes(e2, text_encoding=use_enc) + b2
                                    args["argc"] = 2
                                    did_fmt = True
                            except Exception:
                                did_fmt = False
                    if (not did_fmt) and (int(op_type), int(op_module), int(op_func)) == (1, 71, 1200) and expr_body:
                        p2 = _split_top_level_commas(expr_body)
                        if len(p2) >= 5:
                            try:
                                e0 = _parse_expr_text_list_single(p2[0].strip())
                                s1 = p2[1].strip()
                                b1 = _encode_quoted_string_token(s1, text_encoding=use_enc)
                                if b1 is None:
                                    dv1 = _encode_dollar_var_token(s1, text_encoding=use_enc)
                                    b1 = dv1 if dv1 is not None else s1.encode(use_enc, errors="replace")
                                e2 = _parse_expr_text_list_single(p2[2].strip())
                                e3 = _parse_expr_text_list_single(p2[3].strip())
                                e4 = _parse_expr_text_list_single(",".join(p2[4:]).strip())
                                bb = bytearray()
                                bb += _encode_single_expr_to_bytes(e0, text_encoding=use_enc)
                                # Bare text variant uses an explicit comma after arg0.
                                if b1 and b1[:1] not in (b"\x22", b"\x24", b"\x25"):
                                    bb.append(0x2C)
                                bb += b1
                                bb += _encode_single_expr_to_bytes(e2, text_encoding=use_enc)
                                p3tok = p2[3].strip()
                                if p3tok.startswith("(") and p3tok.endswith(")"):
                                    bb.append(0x28)
                                    bb += _encode_single_expr_to_bytes(e3, text_encoding=use_enc)
                                    bb.append(0x29)
                                elif s1.startswith("\"") and s1.endswith("\""):
                                    # Keep literal expression text for quoted variant.
                                    # Do not force-wrap rhs; parser already preserves explicit parentheses.
                                    bb += _encode_single_expr_to_bytes(e3, text_encoding=use_enc)
                                else:
                                    bb += _encode_single_expr_to_bytes(e3, text_encoding=use_enc)
                                bb += _encode_single_expr_to_bytes(e4, text_encoding=use_enc)
                                arg_bytes = bytes(bb)
                                args["argc"] = 5
                                did_fmt = True
                            except Exception:
                                did_fmt = False
                    if (not did_fmt) and (int(op_type), int(op_module), int(op_func)) == (1, 81, 1005) and expr_body:
                        try:
                            exprs_nc = [_parse_expr_text_list_single(x.strip()) for x in _split_top_level_commas(expr_body)]
                            arg_bytes = _encode_expr_list_to_bytes_no_commas(exprs_nc, text_encoding=use_enc)
                            args["argc"] = len(exprs_nc)
                            did_fmt = True
                        except Exception:
                            did_fmt = False
                    if (not did_fmt) and (int(op_type), int(op_module), int(op_func), int(overload or 0)) in ((1, 33, 73, 2), (1, 33, 73, 4)) and expr_body:
                        p2 = _split_top_level_commas(expr_body)
                        if len(p2) >= 2:
                            try:
                                lead = p2[0].strip().encode(use_enc, errors="replace")
                                exprs_nc = [_parse_expr_text_list_single(x.strip()) for x in p2[1:]]
                                bb = bytearray(lead)
                                for ex in exprs_nc:
                                    enc_ex = _encode_single_expr_to_bytes(ex, text_encoding=use_enc)
                                    if _expr_begins_unary(ex):
                                        bb.append(0x2C)
                                    bb += enc_ex
                                arg_bytes = bytes(bb)
                                args["argc"] = len(p2)
                                did_fmt = True
                            except Exception:
                                did_fmt = False
                    if (not did_fmt) and (int(op_type), int(op_module), int(op_func)) == (1, 33, 70) and expr_body:
                        p2 = _split_top_level_commas(expr_body)
                        if len(p2) >= 2:
                            first_tok = p2[0].strip()
                            if re.fullmatch(r"[A-Za-z0-9_?]+", first_tok):
                                try:
                                    lead = first_tok.encode(use_enc, errors="replace")
                                    exprs_nc = [_parse_expr_text_list_single(x.strip()) for x in p2[1:]]
                                    arg_bytes = lead + _encode_expr_list_to_bytes_no_commas(exprs_nc, text_encoding=use_enc)
                                    args["argc"] = len(p2)
                                    did_fmt = True
                                except Exception:
                                    did_fmt = False
                    if (not did_fmt) and (int(op_type), int(op_module), int(op_func)) == (1, 33, 75) and expr_body:
                        p2 = _split_top_level_commas(expr_body)
                        if len(p2) >= 2:
                            try:
                                bb = bytearray()
                                bb += p2[0].strip().encode(use_enc, errors="replace")
                                e1 = _parse_expr_text_list_single(p2[1].strip())
                                bb += _encode_single_expr_to_bytes(e1, text_encoding=use_enc)
                                for t0 in p2[2:]:
                                    t = t0.strip()
                                    if not t:
                                        continue
                                    mh = re.fullmatch(r"0x([0-9A-Fa-f]{1,2})", t)
                                    if mh:
                                        bb.append(int(mh.group(1), 16) & 0xFF)
                                        continue
                                    if t.startswith("(") and t.endswith(")"):
                                        inner_t = t[1:-1].strip()
                                        inner_parts = _split_top_level_commas(inner_t)
                                        if len(inner_parts) >= 2 and re.fullmatch(r"[A-Za-z0-9_?]+", inner_parts[0].strip()):
                                            bb.append(0x28)
                                            bb += inner_parts[0].strip().encode(use_enc, errors="replace")
                                            inner_exprs = [_parse_expr_text_list_single(x.strip()) for x in inner_parts[1:]]
                                            bb += _encode_expr_list_to_bytes_no_commas(inner_exprs, text_encoding=use_enc)
                                            bb.append(0x29)
                                            continue
                                        ib = inner_t.encode(use_enc, errors="replace")
                                        bb.append(0x28)
                                        bb += ib
                                        bb.append(0x29)
                                        continue
                                    bb += t.encode(use_enc, errors="replace")
                                arg_bytes = bytes(bb)
                                args["argc"] = len(p2)
                                did_fmt = True
                            except Exception:
                                did_fmt = False
                    fmt_exact = [f for f in fmt_candidates if len(f) == argc_input_count] if argc_input_count > 0 else list(fmt_candidates)
                    if (not did_fmt) and fmt_exact and expr_body and (int(op_type), int(op_module), int(op_func)) not in ((1, 4, 500), (1, 21, 0), (1, 21, 1), (1, 71, 1000), (1, 71, 1001), (1, 71, 1300), (1, 72, 1000), (1, 72, 1001), (1, 81, 1000), (1, 81, 1001), (1, 81, 1002), (1, 81, 1031), (1, 82, 1002), (1, 87, 1001)):
                        parts = _split_args_for_fmt(expr_body)
                        for fmt_use in fmt_exact:
                            enc = _encode_args_by_format(parts, fmt_use, text_encoding=use_enc)
                            if enc is not None:
                                arg_bytes = enc
                                args["argc"] = len(fmt_use)
                                did_fmt = True
                                break
                            enc_c = _encode_args_by_format(parts, fmt_use, text_encoding=use_enc, with_commas=True)
                            if enc_c is not None:
                                arg_bytes = enc_c
                                args["argc"] = len(fmt_use)
                                did_fmt = True
                                break
                    if (not did_fmt) and (int(op_type), int(op_module), int(op_func)) in ((1, 71, 1000), (1, 71, 1001), (1, 71, 1300), (1, 72, 1000), (1, 72, 1001)) and expr_body:
                        p2 = _split_top_level_commas(expr_body)
                        if len(p2) >= 2:
                            try:
                                e0 = _parse_expr_text_list_single(p2[0].strip())
                                t1 = p2[1].strip()
                                b1 = _encode_quoted_string_token(t1, text_encoding=use_enc)
                                if b1 is None:
                                    dv = _encode_dollar_var_token(t1, text_encoding=use_enc)
                                    b1 = dv if dv is not None else t1.encode(use_enc, errors="replace")
                                tail_exprs = [_parse_expr_text_list_single(x.strip()) for x in p2[2:]]
                                bb = bytearray()
                                bb += _encode_single_expr_to_bytes(e0, text_encoding=use_enc)
                                bb.append(0x2C)
                                bb += b1
                                bb += _encode_expr_list_with_optional_commas(tail_exprs, text_encoding=use_enc)
                                arg_bytes = bytes(bb)
                                args["argc"] = len(p2)
                                did_fmt = True
                            except Exception:
                                did_fmt = False
                    if (not did_fmt) and (int(op_type), int(op_module), int(op_func)) in ((1, 20, 0), (1, 21, 0), (1, 21, 1)) and int(overload or 0) in (0, 1, 2) and expr_body:
                        p2 = _split_top_level_commas(expr_body)
                        if len(p2) >= 1:
                            try:
                                lead = p2[0].strip().encode(use_enc, errors="replace")
                                exprs_nc = [_parse_expr_text_list_single(x.strip()) for x in p2[1:]]
                                arg_bytes = lead + _encode_expr_list_to_bytes_no_commas(exprs_nc, text_encoding=use_enc)
                                args["argc"] = len(p2)
                                did_fmt = True
                            except Exception:
                                did_fmt = False
                    if (not did_fmt) and (int(op_type), int(op_module), int(op_func)) == (1, 81, 1001) and expr_body:
                        try:
                            exprs_nc = [_parse_expr_text_list_single(x.strip()) for x in _split_top_level_commas(expr_body)]
                            bb = bytearray()
                            if exprs_nc:
                                bb += _encode_single_expr_to_bytes(exprs_nc[0], text_encoding=use_enc)
                            for ex in exprs_nc[1:]:
                                enc_ex = _encode_single_expr_to_bytes(ex, text_encoding=use_enc)
                                if _expr_begins_unary(ex):
                                    bb.append(0x2C)
                                bb += enc_ex
                            arg_bytes = bytes(bb)
                            args["argc"] = len(exprs_nc)
                            did_fmt = True
                        except Exception:
                            did_fmt = False
                    if (not did_fmt) and (int(op_type), int(op_module), int(op_func)) in ((1, 81, 1002), (1, 82, 1002)) and expr_body:
                        try:
                            exprs_nc = [_parse_expr_text_list_single(x.strip()) for x in _split_top_level_commas(expr_body)]
                            bb = bytearray()
                            if exprs_nc:
                                bb += _encode_single_expr_to_bytes(exprs_nc[0], text_encoding=use_enc)
                            for ex in exprs_nc[1:]:
                                enc_ex = _encode_single_expr_to_bytes(ex, text_encoding=use_enc)
                                if _expr_begins_unary(ex):
                                    bb.append(0x2C)
                                bb += enc_ex
                            arg_bytes = bytes(bb)
                            args["argc"] = len(exprs_nc)
                            did_fmt = True
                        except Exception:
                            did_fmt = False
                    if (not did_fmt) and (int(op_type), int(op_module), int(op_func)) == (1, 81, 1025) and expr_body:
                        try:
                            exprs_nc = [_parse_expr_text_list_single(x.strip()) for x in _split_top_level_commas(expr_body)]
                            bb = bytearray()
                            for i_ex, ex in enumerate(exprs_nc):
                                enc_ex = _encode_single_expr_to_bytes(ex, text_encoding=use_enc)
                                if i_ex == len(exprs_nc) - 1 and i_ex > 0 and _expr_begins_unary(ex):
                                    bb.append(0x2C)
                                bb += enc_ex
                            arg_bytes = bytes(bb)
                            args["argc"] = len(exprs_nc)
                            did_fmt = True
                        except Exception:
                            did_fmt = False
                    if (not did_fmt) and (int(op_type), int(op_module), int(op_func)) == (1, 81, 1000) and expr_body:
                        try:
                            exprs_mv = [_parse_expr_text_list_single(x.strip()) for x in _split_top_level_commas(expr_body)]
                            if len(exprs_mv) == 3:
                                arg_bytes = _encode_expr_list_with_optional_commas(exprs_mv, text_encoding=use_enc)
                                args["argc"] = 3
                                did_fmt = True
                        except Exception:
                            did_fmt = False
                    if (not did_fmt) and fname in ("objDriftOpts", "objScale", "objTop", "InitFrame") and expr_body:
                        try:
                            exprs_mv = [_parse_expr_text_list_single(x.strip()) for x in _split_top_level_commas(expr_body)]
                            if exprs_mv:
                                arg_bytes = _encode_expr_list_with_optional_commas(exprs_mv, text_encoding=use_enc)
                                args["argc"] = len(exprs_mv)
                                did_fmt = True
                        except Exception:
                            did_fmt = False
                    if (not did_fmt) and (int(op_type), int(op_module), int(op_func)) == (1, 87, 1001) and expr_body:
                        try:
                            # OBJFRONTADD_* family requires explicit comma separators in script bytes.
                            exprs_nc = [_parse_expr_text_list_single(x.strip()) for x in _split_top_level_commas(expr_body)]
                            bb = bytearray()
                            if exprs_nc:
                                bb += _encode_single_expr_to_bytes(exprs_nc[0], text_encoding=use_enc)
                            for ex in exprs_nc[1:]:
                                enc_ex = _encode_single_expr_to_bytes(ex, text_encoding=use_enc)
                                if _expr_begins_unary(ex):
                                    bb.append(0x2C)
                                bb += enc_ex
                            arg_bytes = bytes(bb)
                            args["argc"] = len(exprs_nc)
                            did_fmt = True
                        except Exception:
                            did_fmt = False
                    if (not did_fmt) and fname == "grpOpenBg" and expr_body:
                        p2 = _split_top_level_commas(expr_body)
                        if len(p2) >= 2:
                            try:
                                lead = p2[0].strip().encode(use_enc, errors="replace")
                                exprs_mv = [_parse_expr_text_list_single(x.strip()) for x in p2[1:]]
                                arg_bytes = lead + _encode_expr_list_with_optional_commas(exprs_mv, text_encoding=use_enc)
                                args["argc"] = len(p2)
                                did_fmt = True
                            except Exception:
                                did_fmt = False
                    if (not did_fmt) and (int(op_type), int(op_module), int(op_func)) == (0, 1, 2) and expr_body:
                        try:
                            m_bool = re.match(r"^\s*\((.*)\)\s*(&&|\|\|)\s*\((.*)\)\s*$", expr_body)
                            if m_bool:
                                ltxt, op_sym, rtxt = m_bool.group(1).strip(), m_bool.group(2), m_bool.group(3).strip()
                                le = _parse_expr_text_list_single(ltxt)
                                re_ = _parse_expr_text_list_single(rtxt)
                                ob = _SYM_TO_OPCODE.get(op_sym)
                                if ob is None:
                                    raise ValueError("bad bool op")
                                bb = bytearray()
                                bb.append(0x28)
                                bb += _encode_single_expr_to_bytes(le, text_encoding=use_enc)
                                bb.append(0x29)
                                bb += bytes([0x5C, ob])
                                bb.append(0x28)
                                bb += _encode_single_expr_to_bytes(re_, text_encoding=use_enc)
                                bb.append(0x29)
                                arg_bytes = bytes(bb)
                            else:
                                e0 = _parse_expr_text_list_single(expr_body)
                                arg_bytes = _encode_single_expr_to_bytes(e0, text_encoding=use_enc)
                            args["argc"] = 0
                            did_fmt = True
                        except Exception:
                            did_fmt = False
                    if (not did_fmt) and fname in ("objRepOrigin", "objShow", "InitExFrame") and expr_body:
                        try:
                            exprs_nc = [_parse_expr_text_list_single(x.strip()) for x in _split_top_level_commas(expr_body)]
                            arg_bytes = _encode_expr_list_to_bytes_no_commas(exprs_nc, text_encoding=use_enc)
                            args["argc"] = len(exprs_nc)
                            did_fmt = True
                        except Exception:
                            did_fmt = False
                    if not did_fmt:
                        try:
                            exprs = _parse_args_exprs(expr_body) if expr_body else []
                            arg_bytes = _encode_expr_list_to_bytes_no_commas(exprs, text_encoding=use_enc)
                            if args["argc"] == 0:
                                args["argc"] = len(exprs)
                        except Exception:
                            parts_m = _split_top_level_commas(expr_body) if expr_body else []
                            enc_m = _encode_mixed_parts(parts_m, text_encoding=use_enc)
                            if enc_m is None:
                                raise
                            arg_bytes = enc_m
                            if args["argc"] == 0:
                                args["argc"] = len(parts_m)
                if argc_token is not None:
                    args["argc"] = int(argc_token)
                elif argc_input_count > 0 and int(args.get("argc", 0)) < argc_input_count:
                    args["argc"] = argc_input_count
                if arg_str.strip() or arg_bytes:
                    items = _bytes_to_parens_items(arg_bytes, spec, text_encoding=use_enc)
                    args["parens"] = {"items": items}
                if (op_type, op_module, op_func) in ((0, 1, 0), (0, 1, 2)):
                    args["argc"] = 0
                if table_hex is not None and (op_type, op_module, op_func) in ((0, 1, 3), (0, 1, 8)):
                    raw_tbl = bytes.fromhex(table_hex) if table_hex else b""
                    if len(raw_tbl) >= 2 and raw_tbl[0] == 0x7B and raw_tbl[-1] == 0x7D and (len(raw_tbl) - 2) % 4 == 0:
                        args["argc"] = (len(raw_tbl) - 2) // 4
                if table_hex is not None and (op_type, op_module, op_func) in ((0, 1, 4), (0, 1, 9)):
                    raw_tbl = bytes.fromhex(table_hex) if table_hex else b""
                    if len(raw_tbl) >= 2 and raw_tbl[0] == 0x7B and raw_tbl[-1] == 0x7D:
                        ti = 1
                        cnt = 0
                        ok = True
                        while ti < len(raw_tbl) - 1:
                            if raw_tbl[ti] != 0x28:
                                ok = False
                                break
                            p = _find_matching_paren(raw_tbl, ti)
                            if p is None:
                                ok = False
                                break
                            ti = p + 1
                            if ti + 4 > len(raw_tbl):
                                ok = False
                                break
                            ti += 4
                            cnt += 1
                        if ok and ti == len(raw_tbl) - 1:
                            args["argc"] = cnt
                if table_entries is not None and (op_type, op_module, op_func) in ((0, 1, 3), (0, 1, 4), (0, 1, 8), (0, 1, 9)):
                    _k, _ent = table_entries
                    args["argc"] = len(_ent)
                out_nodes.append(Node("Op", {"op": "23", "name": fname, "args": args}))
                if target_u32 is not None and (int(op_type), int(op_module), int(op_func)) in ((0, 1, 0), (0, 1, 2)):
                    out_nodes.append(Node("U32", {"val": int(target_u32) & 0xFFFFFFFF}))
                if target_rel is not None and (int(op_type), int(op_module), int(op_func)) in ((0, 1, 0), (0, 1, 2)):
                    out_nodes.append(Node("U32", {"val": int(target_rel), "rel": True}))
                if jump_tail_hex is not None and (int(op_type), int(op_module), int(op_func)) in ((0, 1, 0), (0, 1, 2)):
                    out_nodes.append(Node("Bytes", {"len": len(jump_tail_hex) // 2, "hex": jump_tail_hex}))
                if table_entries is not None and (int(op_type), int(op_module), int(op_func)) in ((0, 1, 3), (0, 1, 4), (0, 1, 8), (0, 1, 9)):
                    kind, entries = table_entries
                    out_nodes.append(Node("Bytes", {"_jump_table": 1, "jump_table_kind": kind, "jump_table_entries": entries}))
                if table_hex is not None and (int(op_type), int(op_module), int(op_func)) in ((0, 1, 3), (0, 1, 4), (0, 1, 8), (0, 1, 9)):
                    out_nodes.append(Node("Bytes", {"len": len(table_hex) // 2, "hex": table_hex, "_jump_table": 1}))
                continue

            if (line.lower().startswith("text(") or line.lower().startswith("string(")) and line.endswith(")"):
                is_text = line.lower().startswith("text(")
                inner = line[(5 if is_text else 7):-1]
                kidoku_val: Optional[int] = None
                txt_part = inner
                if is_text:
                    mk = re.search(r",\s*kidoku\s*=\s*(-?(?:0x[0-9A-Fa-f]+|\d+))\s*$", inner)
                    if mk:
                        kidoku_val = _parse_int(mk.group(1))
                        txt_part = inner[:mk.start()]
                    else:
                        mp = re.search(r",\s*(-?(?:0x[0-9A-Fa-f]+|\d+))\s*$", inner)
                        if mp:
                            try:
                                kidoku_val = _parse_int(mp.group(1))
                                txt_part = inner[:mp.start()]
                            except Exception:
                                pass
                if txt_part.strip().startswith("\"") and txt_part.strip().endswith("\""):
                    try:
                        inner = json.loads(txt_part.strip())
                        txt = f"\"{inner}\""
                    except Exception:
                        txt = txt_part
                else:
                    txt = _unescape_kprl_text_loose(txt_part)
                if kidoku_val is not None:
                    out_nodes.append(Node("Op", {"op": "40", "name": "KidokuText", "args": {"kidoku": int(kidoku_val)}}))
                out_nodes.append(Node("Text", {"text": txt}))
                continue

            parts = line.split(maxsplit=1)
            tag = parts[0].lower()
            rest = parts[1] if len(parts) > 1 else ""
            if tag == "text":
                if rest.strip().startswith("\"") and rest.strip().endswith("\""):
                    try:
                        inner = json.loads(rest.strip())
                        txt = f"\"{inner}\""
                    except Exception:
                        txt = rest
                else:
                    txt = _unescape_kprl_text_loose(rest)
                out_nodes.append(Node("Text", {"text": txt}))
            elif tag == "string":
                if rest.strip().startswith("\"") and rest.strip().endswith("\""):
                    try:
                        inner = json.loads(rest.strip())
                        txt = f"\"{inner}\""
                    except Exception:
                        txt = rest
                else:
                    txt = _unescape_kprl_text_loose(rest)
                out_nodes.append(Node("Text", {"text": txt}))
            elif tag == "bytes":
                rr = rest.strip()
                if rr.startswith("SCRIPT_BLOCK"):
                    m_lp = re.search(r"lenprefix\s*=\s*(\d+)", rr)
                    lenprefix = int(m_lp.group(1)) if m_lp else 0
                    m_wrap = re.search(r"wrap\s*=\s*(\d+)", rr)
                    wrap = int(m_wrap.group(1)) if m_wrap else 1
                    j = bi
                    while j < len(body_lines) and not body_lines[j].strip():
                        j += 1
                    if j >= len(body_lines) or body_lines[j].strip().lower() != "bytes_block {":
                        raise ValueError("SCRIPT_BLOCK bytes missing bytes_block {")
                    j += 1
                    depth = 1
                    inner_lines: list[str] = []
                    while j < len(body_lines):
                        s0 = body_lines[j].strip()
                        if s0.lower() == "bytes_block {":
                            depth += 1
                            if depth > 1:
                                inner_lines.append(body_lines[j])
                            j += 1
                            continue
                        if s0 == "}":
                            depth -= 1
                            if depth == 0:
                                break
                            inner_lines.append(body_lines[j])
                            j += 1
                            continue
                        inner_lines.append(body_lines[j])
                        j += 1
                    if depth != 0:
                        raise ValueError("bytes_block missing closing '}'")
                    inner_nodes = _parse_body_lines(inner_lines, file_enc)
                    payload = encode_nodes(inner_nodes, spec, text_encoding=(text_encoding or file_enc or "cp932"), prefer_raw=True)
                    if lenprefix:
                        n3 = len(payload)
                        inner = bytes([(n3) & 0xFF, (n3 >> 8) & 0xFF, (n3 >> 16) & 0xFF]) + payload
                    else:
                        inner = payload
                    braw = (b"\x22" + inner + b"\x22") if wrap else inner
                    hx = braw.hex().upper()
                    out_nodes.append(Node("Bytes", {"len": len(braw), "hex": hx}))
                    bi = j + 1
                else:
                    hx = rr.upper()
                    out_nodes.append(Node("Bytes", {"len": len(hx) // 2, "hex": hx}))
            elif tag == "qbytes":
                rr = rest.strip()
                if rr.startswith("SCRIPT_BLOCK"):
                    m_lp = re.search(r"lenprefix\s*=\s*(\d+)", rr)
                    lenprefix = int(m_lp.group(1)) if m_lp else 0
                    j = bi
                    while j < len(body_lines) and not body_lines[j].strip():
                        j += 1
                    if j >= len(body_lines) or body_lines[j].strip().lower() != "qbytes_block {":
                        raise ValueError("SCRIPT_BLOCK qbytes missing qbytes_block {")
                    j += 1
                    depth = 1
                    inner_lines: list[str] = []
                    while j < len(body_lines):
                        s0 = body_lines[j].strip()
                        if s0.lower() == "qbytes_block {":
                            depth += 1
                            if depth > 1:
                                inner_lines.append(body_lines[j])
                            j += 1
                            continue
                        if s0 == "}":
                            depth -= 1
                            if depth == 0:
                                break
                            inner_lines.append(body_lines[j])
                            j += 1
                            continue
                        inner_lines.append(body_lines[j])
                        j += 1
                    if depth != 0:
                        raise ValueError("qbytes_block missing closing '}'")
                    inner_nodes = _parse_body_lines(inner_lines, file_enc)
                    payload = encode_nodes(inner_nodes, spec, text_encoding=(text_encoding or file_enc or "cp932"), prefer_raw=True)
                    if lenprefix:
                        n3 = len(payload)
                        inner = bytes([(n3) & 0xFF, (n3 >> 8) & 0xFF, (n3 >> 16) & 0xFF]) + payload
                    else:
                        inner = payload
                    qraw = b"\x22" + inner + b"\x22"
                    hx = qraw.hex().upper()
                    out_nodes.append(Node("QBytes", {"len": len(qraw), "hex": hx}))
                    bi = j + 1
                else:
                    hx = rr.upper()
                    out_nodes.append(Node("QBytes", {"len": len(hx) // 2, "hex": hx}))
            elif tag == "u32":
                out_nodes.append(Node("U32", {"val": _parse_int(rest)}))
            elif tag == "u16":
                out_nodes.append(Node("U16", {"val": _parse_int(rest)}))
            elif tag == "u8":
                out_nodes.append(Node("U8", {"val": _parse_int(rest)}))
            elif tag == "sym":
                out_nodes.append(Node("Sym", {"ch": rest.strip()}))
            elif tag == "esc":
                out_nodes.append(Node("Esc", {"x": rest.strip().upper()}))
            elif tag == "dollarff":
                out_nodes.append(Node("Dollar", {"kind": "FF", "val": _parse_int(rest)}))
            elif tag == "dollar":
                r = rest.split()
                kind = r[0].upper()
                br = bool(_parse_int(r[1])) if len(r) > 1 else False
                expr = (r[2].upper() if len(r) > 2 else "")
                out_nodes.append(Node("Dollar", {"kind": kind, "bracket": br, "expr_hex": expr, "expr_text": ""}))
            elif tag == "padbytes":
                out_nodes.append(Node("PadBytes", {"byte": "FF", "count": _parse_int(rest)}))
            elif tag == "padword":
                r = rest.split()
                out_nodes.append(Node("PadWord", {"word": r[0].upper(), "count": _parse_int(r[1])}))
            elif tag == "ctrl8194":
                kvs = dict(x.split("=", 1) for x in rest.split())
                out_nodes.append(Node("Ctrl8194", {"type": _parse_int(kvs["type"]), "mode": _parse_int(kvs.get("mode", "0")), "idx": _parse_int(kvs["idx"])}))
            elif tag in ("opbyte", "op"):
                parts2 = rest.split()
                op = parts2[0].replace("0x", "").upper()
                args2: dict[str, Any] = {}
                spec_ops = {int(o["op"], 16): o for o in spec.get("ops", [])}
                info = spec_ops.get(int(op, 16)) or {}
                arg_defs = [a for a in info.get("args", []) if a.get("name") != "parens"]
                named_mode = any("=" in x for x in parts2[1:])
                if named_mode:
                    for kv in parts2[1:]:
                        if "=" not in kv:
                            continue
                        k, v = kv.split("=", 1)
                        args2[k] = _parse_int(v)
                else:
                    for i2, tok in enumerate(parts2[1:]):
                        if i2 >= len(arg_defs):
                            break
                        nm = str(arg_defs[i2].get("name", ""))
                        if nm:
                            args2[nm] = _parse_int(tok)
                if args2:
                    out_nodes.append(Node("Op", {"op": op, "name": f"Op{op}", "args": args2}))
                else:
                    out_nodes.append(Node("OpByte", {"op": op}))
            else:
                raise ValueError(f"unknown kprl line at bi={bi}: {line!r}")
        return out_nodes
    body_lines: list[str] = []
    for raw_line in lines:
        stripped = raw_line.strip()
        if stripped.startswith(";"):
            continue
        if stripped.startswith("#"):
            parts = stripped[1:].split(maxsplit=1)
            if not parts:
                continue
            key = parts[0].lower()
            val = parts[1].strip() if len(parts) > 1 else ""
            if key == "text_encoding":
                file_text_encoding = val
            elif key == "ver":
                ver = _parse_int(val)
            elif key == "xlen":
                xlen = _parse_int(val)
            elif key == "off":
                pass
            elif key == "header":
                header_hex = val
            continue
        body_lines.append(raw_line)
    nodes = _parse_body_lines(body_lines, file_text_encoding)

    if header_hex is None or ver is None or xlen is None:
        raise ValueError("kprl missing #header/#ver/#xlen")
    return (bytes.fromhex(header_hex), int(ver), int(xlen), file_text_encoding, nodes)

def decode_one(
    in_path: Path,
    out_path: Path,
    *,
    spec: dict,
    text_encoding: str,
    hashcall_map: dict[tuple[int, int, int, int], KfnOpDef],
    opfmt_map: dict[object, list[Optional[str]]],
    asm_strict: bool,
) -> None:
    data = in_path.read_bytes()
    ver, off, xlen = parse_seen_hdr(data)
    header = data[:off]

    payload = bytearray(data[off:])
    if xlen:
        apply_seen_xor_layer(payload, xlen)
    apply_seen_version_layers(payload, ver)

    dec = Decoder(spec, text_encoding=text_encoding)
    i = 0
    nodes: list[Node] = []
    while i < len(payload):
        n, j = dec.parse_one(payload, i)
        nodes.append(n)
        i = j
        # RealLive jump opcodes:
        # - goto: followed by 4-byte target
        # - goto_unless: followed by condition expr bytes + 4-byte target
        if n.kind == "Op" and str(n.data.get("op", "")).upper() == "23":
            a = n.data.get("args", {})
            g = int(a.get("group", 0))
            s = int(a.get("sub", 0))
            f = int(a.get("op16", 0))
            if (g, s, f) == (0, 1, 0) and i + 4 <= len(payload):
                raw4 = bytes(payload[i : i + 4])
                nodes.append(Node("U32", {"val": int.from_bytes(raw4, "little"), "_raw": raw4.hex().upper()}))
                i += 4
            elif (g, s, f) == (0, 1, 2):
                cond_start = i
                cond_end = cond_start
                try:
                    _expr, cond_end = _decode_expr_at(payload, cond_start)
                except Exception:
                    cond_end = cond_start
                if cond_end > cond_start:
                    cond_raw = bytes(payload[cond_start:cond_end])
                    try:
                        items = _bytes_to_parens_items(cond_raw, spec, text_encoding=text_encoding)
                        a2 = dict(a)
                        a2["parens"] = {"items": items}
                        n = Node("Op", {**n.data, "args": a2})
                        nodes[-1] = n
                    except Exception:
                        pass
                    i = cond_end
                if i + 4 <= len(payload):
                    raw4 = bytes(payload[i : i + 4])
                    nodes.append(Node("U32", {"val": int.from_bytes(raw4, "little"), "_raw": raw4.hex().upper()}))
                    i += 4
            elif _is_jump_table_hashcall_op(n):
                # goto_case/gosub_case: value expr before jump-table block.
                if (g, s, f) in ((0, 1, 4), (0, 1, 9)):
                    expr_start = i
                    expr_end = expr_start
                    try:
                        _expr, expr_end = _decode_expr_at(payload, expr_start)
                    except Exception:
                        expr_end = expr_start
                    if expr_end > expr_start:
                        expr_raw = bytes(payload[expr_start:expr_end])
                        try:
                            items = _bytes_to_parens_items(expr_raw, spec, text_encoding=text_encoding)
                            a2 = dict(a)
                            a2["parens"] = {"items": items}
                            n = Node("Op", {**n.data, "args": a2})
                            nodes[-1] = n
                        except Exception:
                            pass
                        i = expr_end
                if i < len(payload) and payload[i] == 0x7B:
                    end = _scan_jump_table_block(payload, i, n)
                    if end is not None and end > i:
                        tbl = bytes(payload[i:end])
                        nodes.append(Node("Bytes", {"len": len(tbl), "hex": tbl.hex().upper(), "_jump_table": 1}))
                        i = end
        elif _is_jump_table_hashcall_op(n) and i < len(payload) and payload[i] == 0x7B:
            end = _scan_jump_table_block(payload, i, n)
            if end is not None and end > i:
                tbl = bytes(payload[i:end])
                nodes.append(Node("Bytes", {"len": len(tbl), "hex": tbl.hex().upper(), "_jump_table": 1}))
                i = end

    nodes = _coalesce_jump_target_u32(nodes)
    if not asm_strict:
        nodes = _coalesce_u32_from_bytes_and_nuls(nodes)
        nodes = _coalesce_small_bytes(nodes)
        nodes = _coalesce_qbytes(nodes)
        nodes = _coalesce_bytes_02_paren_ascii(nodes)
    write_kprl(
        out_path,
        header=header,
        ver=ver,
        xlen=xlen,
        text_encoding=text_encoding,
        nodes=nodes,
        spec=spec,
        hashcall_map=hashcall_map,
        opfmt_map=opfmt_map,
    )

def encode_one(
    in_path: Path,
    out_path: Path,
    *,
    spec: dict,
    text_encoding: str,
    hashcall_map: dict[tuple[int, int, int, int], KfnOpDef],
    opfmt_map: dict[object, list[Optional[str]]],
) -> None:
    header, ver, xlen, enc_in_file, nodes = read_kprl(
        in_path,
        spec=spec,
        text_encoding=text_encoding,
        hashcall_map=hashcall_map,
        opfmt_map=opfmt_map,
    )
    enc = text_encoding or (enc_in_file or "cp932")

    base_payload_plain: Optional[bytes] = None
    base_header_off: Optional[int] = None
    try:
        base_path = _find_base_seen_for_kprl(in_path)
        if base_path is not None and base_path.is_file():
            base_data = base_path.read_bytes()
            _, base_off, _ = parse_seen_hdr(base_data)
            base_header_off = int(base_off)
            base_payload_plain = _decode_seen_plain_payload(base_path)
    except Exception:
        base_payload_plain = None

    enable_relocation = False
    if enable_relocation and base_payload_plain is not None:
        try:
            nodes = _relocate_u32_nodes_using_base(nodes, base_payload_plain, spec=spec, text_encoding=enc)
        except Exception as e:
            # Relocation is best-effort; keep output lossless if we can't prove a safe mapping.
            print(f"[warn] relocation skipped for {in_path.name}: {e}")

    payload = bytearray(encode_nodes(nodes, spec, text_encoding=enc, prefer_raw=True))

    if enable_relocation and base_payload_plain is not None:
        try:
            base_sigs, base_offs = _iter_op_sigs_and_offsets_from_payload(
                base_payload_plain, spec=spec, text_encoding=enc
            )
            new_sigs, new_offs = _iter_op_sigs_and_offsets_from_payload(
                payload, spec=spec, text_encoding=enc
            )
            if base_sigs != new_sigs:
                raise ValueError(f"opcode stream mismatch (base_ops={len(base_sigs)} new_ops={len(new_sigs)})")

            off_map = {base_offs[i]: new_offs[i] for i in range(len(base_offs))}
            sites = _collect_relocation_sites(
                base_payload_plain,
                base_op_offsets=base_offs,
                off_map=off_map,
                spec=spec,
                text_encoding=enc,
            )
            _apply_relocation_sites(
                payload,
                new_op_offsets=new_offs,
                off_map=off_map,
                sites=sites,
            )
            if base_header_off is not None:
                header = _patch_header_offsets(
                    header,
                    off_map=off_map,
                    old_header_off=base_header_off,
                    new_header_off=len(header),
                )
        except Exception as e:
            print(f"[warn] relocation site pass skipped for {in_path.name}: {e}")
    apply_seen_version_layers(payload, ver)
    if xlen:
        apply_seen_xor_layer(payload, xlen)

    header = _patch_seen_payload_len_in_header(header, len(payload))
    out_path.write_bytes(header + payload)

def _find_base_seen_for_kprl(kprl_path: Path) -> Optional[Path]:
    stem = kprl_path.stem
    # Common layouts in this workspace:
    #   kprl/Seen0101.asm  ->  seen/Seen0101.txt
    #   kprl/Seen0101.asm  ->  Seen/Seen0101.txt
    candidates = [
        Path.cwd() / "seen" / f"{stem}.txt",
        Path.cwd() / "Seen" / f"{stem}.txt",
        kprl_path.with_suffix(".txt"),
        kprl_path.parent / "seen" / f"{stem}.txt",
        kprl_path.parent / "Seen" / f"{stem}.txt",
        kprl_path.parent.parent / "seen" / f"{stem}.txt",
        kprl_path.parent.parent / "Seen" / f"{stem}.txt",
    ]
    for p in candidates:
        try:
            if p.is_file():
                return p
        except Exception:
            continue

    # If the kprl file has a suffix (e.g. Seen0101_mod.asm / _Seen0101_test.asm),
    # try to recover the canonical SeenXXXX name.
    m = re.search(r"(Seen\d{4})", stem, flags=re.IGNORECASE)
    if m:
        stem2 = m.group(1)
        candidates2 = [
            Path.cwd() / "seen" / f"{stem2}.txt",
            Path.cwd() / "Seen" / f"{stem2}.txt",
            kprl_path.with_name(stem2).with_suffix(".txt"),
            kprl_path.parent.parent / "seen" / f"{stem2}.txt",
            kprl_path.parent.parent / "Seen" / f"{stem2}.txt",
        ]
        for p in candidates2:
            try:
                if p.is_file():
                    return p
            except Exception:
                continue
    return None

def _decode_seen_plain_payload(path: Path) -> bytes:
    data = path.read_bytes()
    ver, off, xlen = parse_seen_hdr(data)
    payload = bytearray(data[off:])
    if xlen:
        apply_seen_xor_layer(payload, xlen)
    apply_seen_version_layers(payload, ver)
    return bytes(payload)

def _iter_op_sigs_and_offsets_from_payload(payload: bytes, *, spec: dict, text_encoding: str) -> tuple[list[tuple[Any, ...]], list[int]]:
    spec_ops = {int(o["op"], 16): o for o in spec.get("ops", [])}
    sigs: list[tuple[Any, ...]] = []
    offs: list[int] = []

    dec = Decoder(spec, text_encoding=text_encoding)
    i = 0
    while i < len(payload):
        i0 = i
        n, i = dec.parse_one(payload, i)
        if n.kind == "Op":
            op = int(str(n.data.get("op", "0")), 16)
            args = n.data.get("args") or {}
            # Include args in a stable order based on spec so we can safely match base/new.
            info = spec_ops.get(op) or {}
            ordered: list[int] = []
            for a in info.get("args", []):
                nm = a.get("name")
                ordered.append(int(args.get(nm, 0)))
            sigs.append((op, *ordered))
            offs.append(i0)
            # Keep op-stream scan consistent with decode flow for jump-family hashcalls:
            # consume inline tails (condition/targets/tables) so they are not seen as op/opbyte.
            if op == 0x23:
                g = int(args.get("group", 0))
                s = int(args.get("sub", 0))
                f = int(args.get("op16", 0))
                if (g, s, f) == (0, 1, 0):
                    if i + 4 <= len(payload):
                        i += 4
                elif (g, s, f) == (0, 1, 2):
                    try:
                        _expr, j2 = _decode_expr_at(payload, i)
                        if j2 > i:
                            i = j2
                    except Exception:
                        pass
                    if i + 4 <= len(payload):
                        i += 4
                elif (g, s, f) in ((0, 1, 4), (0, 1, 9)):
                    try:
                        _expr, j2 = _decode_expr_at(payload, i)
                        if j2 > i:
                            i = j2
                    except Exception:
                        pass
                    if i < len(payload) and payload[i] == 0x7B:
                        end = _scan_jump_table_block(payload, i, n)
                        if end is not None and end > i:
                            i = end
                elif (g, s, f) in ((0, 1, 3), (0, 1, 8)):
                    if i < len(payload) and payload[i] == 0x7B:
                        end = _scan_jump_table_block(payload, i, n)
                        if end is not None and end > i:
                            i = end
        elif n.kind == "OpByte":
            op = int(str(n.data.get("op", "0")), 16)
            sigs.append((op,))
            offs.append(i0)
    return sigs, offs


def _iter_op_sigs_and_offsets_from_nodes(
    nodes: list[Node], *, spec: dict, text_encoding: str
) -> tuple[list[tuple[Any, ...]], list[int]]:
    spec_ops = {int(o["op"], 16): o for o in spec.get("ops", [])}
    sigs: list[tuple[Any, ...]] = []
    offs: list[int] = []
    cur = 0
    for n in nodes:
        if n.kind == "Op":
            op = int(str(n.data.get("op", "0")), 16)
            args = n.data.get("args") or {}
            info = spec_ops.get(op) or {}
            ordered: list[int] = []
            for a in info.get("args", []):
                nm = a.get("name")
                ordered.append(int(args.get(nm, 0)))
            sigs.append((op, *ordered))
            offs.append(cur)
        elif n.kind == "OpByte":
            op = int(str(n.data.get("op", "0")), 16)
            sigs.append((op,))
            offs.append(cur)
        if n.kind == "Bytes" and n.data.get("_jump_table") and n.data.get("jump_table_entries") is not None:
            kind = str(n.data.get("jump_table_kind", "on"))
            entries = n.data.get("jump_table_entries")
            cur += _estimate_jump_table_len(kind=kind, entries=entries, text_encoding=text_encoding)
        else:
            cur += len(encode_node(n, spec_ops, text_encoding=text_encoding, prefer_raw=True))
    return sigs, offs

def _iter_nodes_with_offsets(payload: bytes, *, spec: dict, text_encoding: str) -> list[tuple[int, int, Node]]:
    dec = Decoder(spec, text_encoding=text_encoding)
    out: list[tuple[int, int, Node]] = []
    i = 0
    while i < len(payload):
        i0 = i
        n, i = dec.parse_one(payload, i)
        out.append((i0, i, n))
    return out


def _fit_text_bytes_len(s: str, *, enc: str, target_len: int) -> bytes:
    if target_len <= 0:
        return b""
    out = bytearray()
    for ch in s:
        b = ch.encode(enc, errors="replace")
        if len(out) + len(b) > target_len:
            break
        out += b
    if len(out) < target_len:
        out += b" " * (target_len - len(out))
    return bytes(out)


def _lock_text_nodes_to_base_lengths(
    nodes: list[Node],
    *,
    base_payload_plain: bytes,
    spec: dict,
    new_text_encoding: str,
    base_text_encoding: str = "cp932",
) -> list[Node]:
    base_nodes = _iter_nodes_with_offsets(base_payload_plain, spec=spec, text_encoding=base_text_encoding)
    base_lens: list[int] = []
    for _s, _e, n in base_nodes:
        if n.kind == "Text":
            hx = str(n.data.get("hex", "") or "")
            if hx:
                base_lens.append(len(hx) // 2)
            else:
                base_lens.append(len(str(n.data.get("text", "")).encode(base_text_encoding, errors="replace")))

    out: list[Node] = []
    ti = 0
    for n in nodes:
        if n.kind == "Text" and ti < len(base_lens):
            tgt = int(base_lens[ti])
            ti += 1
            b = _fit_text_bytes_len(str(n.data.get("text", "")), enc=new_text_encoding, target_len=tgt)
            out.append(Node("Bytes", {"len": len(b), "hex": b.hex().upper(), "_len_lock_text": 1}))
        else:
            if n.kind == "Text":
                ti += 1
            out.append(n)
    return out

def _collect_relocation_sites(
    base_payload: bytes,
    *,
    base_op_offsets: list[int],
    off_map: dict[int, int],
    spec: dict,
    text_encoding: str,
) -> list[tuple[int, int, int, int]]:
    # Return sites as (op_index, delta, width, old_value)
    if not base_op_offsets or not off_map:
        return []

    nodes = _iter_nodes_with_offsets(base_payload, spec=spec, text_encoding=text_encoding)
    non_text_spans: list[tuple[int, int]] = [(s, e) for s, e, n in nodes if n.kind != "Text"]
    non_text_spans.sort()

    def in_non_text(pos: int, width: int, idx_ref: list[int]) -> bool:
        i = idx_ref[0]
        while i < len(non_text_spans) and pos >= non_text_spans[i][1]:
            i += 1
        idx_ref[0] = i
        return i < len(non_text_spans) and non_text_spans[i][0] <= pos and pos + width <= non_text_spans[i][1]

    import bisect

    sites: list[tuple[int, int, int, int]] = []
    seen: set[tuple[int, int, int, int]] = set()

    idx_ref = [0]
    op_starts = set(base_op_offsets)
    n = len(base_payload)
    for pos in range(n):
        if pos in op_starts:
            continue
        # imm32 token: 0xFF + 4 bytes
        if pos + 5 <= n and base_payload[pos] == 0xFF:
            if not in_non_text(pos, 5, idx_ref):
                continue
            v = u32le(base_payload, pos + 1)
            if v in off_map:
                op_i = bisect.bisect_right(base_op_offsets, pos) - 1
                if op_i >= 0:
                    delta = pos - base_op_offsets[op_i]
                    key = (op_i, delta, 5, v)
                    if key not in seen:
                        sites.append(key)
                        seen.add(key)
        # width 4
        if pos + 4 <= n:
            if not in_non_text(pos, 4, idx_ref):
                continue
            v = u32le(base_payload, pos)
            if v in off_map:
                op_i = bisect.bisect_right(base_op_offsets, pos) - 1
                if op_i >= 0:
                    delta = pos - base_op_offsets[op_i]
                    key = (op_i, delta, 4, v)
                    if key not in seen:
                        sites.append(key)
                        seen.add(key)
        # width 3
        if pos + 3 <= n:
            if not in_non_text(pos, 3, idx_ref):
                continue
            v = u24le(base_payload, pos)
            if v in off_map:
                op_i = bisect.bisect_right(base_op_offsets, pos) - 1
                if op_i >= 0:
                    delta = pos - base_op_offsets[op_i]
                    key = (op_i, delta, 3, v)
                    if key not in seen:
                        sites.append(key)
                        seen.add(key)
        # width 2
        if pos + 2 <= n:
            if not in_non_text(pos, 2, idx_ref):
                continue
            v = u16le(base_payload, pos)
            if v in off_map:
                op_i = bisect.bisect_right(base_op_offsets, pos) - 1
                if op_i >= 0:
                    delta = pos - base_op_offsets[op_i]
                    key = (op_i, delta, 2, v)
                    if key not in seen:
                        sites.append(key)
                        seen.add(key)
    return sites


def _collect_relocation_sites_jump_only(
    base_payload: bytes,
    *,
    spec: dict,
    text_encoding: str,
) -> list[tuple[int, int, int, int]]:
    # Precise relocation sites for control-flow only:
    # - goto / goto_unless trailing u32 target
    # - goto_on / gosub_on table u32 entries
    # - goto_case / gosub_case table u32 entries
    dec = Decoder(spec, text_encoding=text_encoding)
    sites: list[tuple[int, int, int, int]] = []
    i = 0
    op_i = -1
    while i < len(base_payload):
        i0 = i
        n, i = dec.parse_one(base_payload, i)
        if n.kind in ("Op", "OpByte"):
            op_i += 1
        if n.kind != "Op" or str(n.data.get("op", "")).upper() != "23":
            continue
        a = n.data.get("args", {})
        g = int(a.get("group", 0))
        s = int(a.get("sub", 0))
        f = int(a.get("op16", 0))
        if (g, s, f) == (0, 1, 0):
            if i + 4 <= len(base_payload):
                v = u32le(base_payload, i)
                sites.append((op_i, i - i0, 4, v))
                i += 4
            continue
        if (g, s, f) == (0, 1, 2):
            try:
                _e, j2 = _decode_expr_at(base_payload, i)
                if j2 > i:
                    i = j2
            except Exception:
                pass
            if i + 4 <= len(base_payload):
                v = u32le(base_payload, i)
                sites.append((op_i, i - i0, 4, v))
                i += 4
            continue
        if (g, s, f) in ((0, 1, 4), (0, 1, 9)):
            try:
                _e, j2 = _decode_expr_at(base_payload, i)
                if j2 > i:
                    i = j2
            except Exception:
                pass
            if i < len(base_payload) and base_payload[i] == 0x7B:
                end = _scan_jump_table_block(base_payload, i, n)
                if end is not None and end > i:
                    j = i + 1
                    while j < end - 1:
                        if base_payload[j] != 0x28:
                            break
                        p = _find_matching_paren(base_payload, j)
                        if p is None or p + 5 > end:
                            break
                        j = p + 1
                        v = u32le(base_payload, j)
                        sites.append((op_i, j - i0, 4, v))
                        j += 4
                    i = end
            continue
        if (g, s, f) in ((0, 1, 3), (0, 1, 8)):
            if i < len(base_payload) and base_payload[i] == 0x7B:
                end = _scan_jump_table_block(base_payload, i, n)
                if end is not None and end > i:
                    j = i + 1
                    while j + 4 <= end - 1:
                        v = u32le(base_payload, j)
                        sites.append((op_i, j - i0, 4, v))
                        j += 4
                    i = end
            continue
    return sites

def _apply_relocation_sites(
    payload: bytearray,
    *,
    new_op_offsets: list[int],
    off_map: dict[int, int],
    sites: list[tuple[int, int, int, int]],
) -> int:
    patched = 0
    for op_i, delta, width, old_val in sites:
        if op_i < 0 or op_i >= len(new_op_offsets):
            continue
        pos = new_op_offsets[op_i] + delta
        if pos < 0 or pos + width > len(payload):
            continue
        if width == 5:
            cur = u32le(payload, pos + 1) if pos + 5 <= len(payload) and payload[pos] == 0xFF else None
            if cur is None:
                continue
        elif width == 4:
            cur = u32le(payload, pos)
        elif width == 3:
            cur = u24le(payload, pos)
        else:
            cur = u16le(payload, pos)
        if cur != old_val:
            continue
        new_val = off_map.get(old_val)
        if new_val is None:
            continue
        if width == 5:
            payload[pos + 1 : pos + 5] = p32le(new_val)
        elif width == 4:
            payload[pos:pos + 4] = p32le(new_val)
        elif width == 3:
            payload[pos:pos + 3] = p24le(new_val)
        else:
            payload[pos:pos + 2] = p16le(new_val)
        patched += 1
    return patched

def _patch_header_offsets(
    header: bytes,
    *,
    off_map: dict[int, int],
    old_header_off: int,
    new_header_off: int,
) -> bytes:
    if not off_map:
        return header
    h = bytearray(header)
    # Skip known header fields that are not offsets.
    skip = {0x04, 0x20, 0x24, 0x28}
    for i in range(0, len(h) - 3, 4):
        if i in skip:
            continue
        v = u32le(h, i)
        if v in off_map:
            h[i:i + 4] = p32le(off_map[v])
            continue
        if v >= old_header_off:
            rel = v - old_header_off
            if rel in off_map:
                h[i:i + 4] = p32le(new_header_off + off_map[rel])
    return bytes(h)

def _relocate_u32_nodes_using_base(nodes: list[Node], base_payload_plain: bytes, *, spec: dict, text_encoding: str) -> list[Node]:
    base_sigs, base_offs = _iter_op_sigs_and_offsets_from_payload(base_payload_plain, spec=spec, text_encoding=text_encoding)

    new_payload_plain = encode_nodes(nodes, spec, text_encoding=text_encoding, prefer_raw=False)
    new_sigs, new_offs = _iter_op_sigs_and_offsets_from_payload(new_payload_plain, spec=spec, text_encoding=text_encoding)
    if base_sigs != new_sigs:
        raise ValueError(f"opcode stream mismatch (base_ops={len(base_sigs)} new_ops={len(new_sigs)})")

    off_map = {base_offs[i]: new_offs[i] for i in range(len(base_offs))}

    def patch_node(n: Node) -> Node:
        if n.kind == "Op":
            args = n.data.get("args") or {}
            par = args.get("parens")
            if isinstance(par, dict) and "items" in par:
                items2: list[dict[str, Any]] = []
                for item in par.get("items", []):
                    k = item.get("node_kind")
                    d = {kk: vv for kk, vv in item.items() if kk != "node_kind"}
                    nn = patch_node(Node(str(k), d))
                    items2.append({"node_kind": nn.kind, **nn.data})
                args2 = dict(args)
                args2["parens"] = {"items": items2}
                return Node("Op", {**n.data, "args": args2})
            return n
        if n.kind == "U32":
            v = int(n.data.get("val", 0))
            if v in off_map:
                return Node("U32", {**n.data, "val": off_map[v]})
        return n

    patched = [patch_node(n) for n in nodes]
    return patched

def _iter_files_for_decode(in_path: Path) -> list[Path]:
    if in_path.is_file():
        return [in_path]
    return sorted([p for p in in_path.rglob("Seen*.txt") if p.is_file()])

def _iter_files_for_encode(in_path: Path) -> list[Path]:
    if in_path.is_file():
        return [in_path]
    return sorted([p for p in in_path.rglob("*.asm") if p.is_file()])

def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(prog="seen.py")
    ap.add_argument("mode", choices=["d", "e"], help="d: decode SEEN to .asm, e: encode .asm to SEEN")
    ap.add_argument("inp", type=Path, help="input file or directory")
    ap.add_argument("out", type=Path, help="output file or directory")
    ap.add_argument("-i", dest="text_encoding", default="cp932", help="text encoding for script bytes (default: cp932)")
    ap.add_argument("--spec", type=Path, default=Path("spec.json"), help="opcode spec path (default: spec.json)")
    ap.add_argument("--kfn", type=Path, default=Path("src/reallive.kfn"), help="RealLive kfn path (default: src/reallive.kfn)")
    ap.add_argument("--target-version", default="1.6.5.9", help="RealLive version for kfn filtering (default: 1.6.5.9)")
    ap.add_argument("--opfmt", type=Path, default=Path("opcode_fmt_map.json"), help="opcode format map path (default: opcode_fmt_map.json)")
    ap.add_argument("--asm-strict", dest="asm_strict", action="store_true", default=True, help="preserve assembler-like node boundaries (default: on)")
    ap.add_argument("--no-asm-strict", dest="asm_strict", action="store_false", help="enable heuristic node coalescing")
    args = ap.parse_args()

    spec = _load_spec(args.spec)
    target_ver = _parse_version_str(args.target_version)
    kfn_defs = _load_kfn_defs(args.kfn, target_version=target_ver)
    hashcall_map = _build_hashcall_map(kfn_defs)
    opfmt_map = _load_opcode_fmt_map(args.opfmt)

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
                decode_one(
                    f,
                    out_file,
                    spec=spec,
                    text_encoding=args.text_encoding,
                    hashcall_map=hashcall_map,
                    opfmt_map=opfmt_map,
                    asm_strict=args.asm_strict,
                )
        else:
            decode_one(
                args.inp,
                args.out,
                spec=spec,
                text_encoding=args.text_encoding,
                hashcall_map=hashcall_map,
                opfmt_map=opfmt_map,
                asm_strict=args.asm_strict,
            )
        return

    files = _iter_files_for_encode(args.inp)
    if not files:
        raise SystemExit("no input files")
    if args.inp.is_dir():
        args.out.mkdir(parents=True, exist_ok=True)
        for f in files:
            rel = f.relative_to(args.inp)
            out_file = (args.out / rel).with_suffix(".txt")
            out_file.parent.mkdir(parents=True, exist_ok=True)
            encode_one(
                f,
                out_file,
                spec=spec,
                text_encoding=args.text_encoding,
                hashcall_map=hashcall_map,
                opfmt_map=opfmt_map,
            )
    else:
        encode_one(
            args.inp,
            args.out,
            spec=spec,
            text_encoding=args.text_encoding,
            hashcall_map=hashcall_map,
            opfmt_map=opfmt_map,
        )

if __name__ == "__main__":
    main()


