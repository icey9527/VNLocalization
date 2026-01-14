from __future__ import annotations

import ctypes
import hashlib
import json
import math
import os
import re
import shutil
import sys
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Literal

import tkinter as tk
from tkinter import filedialog, messagebox


RT_RCDATA = 10


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_at(path: Path, offset: int, size: int) -> bytes:
    with path.open("rb") as f:
        f.seek(offset)
        return f.read(size)


def _copy_range(src: Path, dst_fp, offset: int, size: int, chunk: int = 1024 * 1024) -> None:
    with src.open("rb") as f:
        f.seek(offset)
        remaining = size
        while remaining > 0:
            n = chunk if remaining > chunk else remaining
            b = f.read(n)
            if not b:
                break
            dst_fp.write(b)
            remaining -= len(b)


def _pe_overlay_offset(path: Path) -> int:
    """
    计算 PE overlay 起始偏移（即所有 section 原始数据 + 安全目录之后）。
    overlay 通常是 EXE 末尾额外附加数据（例如 kirikiri 的封包）。
    """
    data = _read_at(path, 0, 4096)
    if len(data) < 64 or data[:2] != b"MZ":
        return path.stat().st_size
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    nt = _read_at(path, e_lfanew, 4 + 20 + 0xF0)
    if len(nt) < 4 + 20 or nt[:4] != b"PE\x00\x00":
        return path.stat().st_size

    file_hdr_off = 4
    num_sections = struct.unpack_from("<H", nt, file_hdr_off + 2)[0]
    opt_size = struct.unpack_from("<H", nt, file_hdr_off + 16)[0]

    opt_off = file_hdr_off + 20
    opt = _read_at(path, e_lfanew + opt_off, opt_size)
    if len(opt) < 2:
        return path.stat().st_size

    magic = struct.unpack_from("<H", opt, 0)[0]
    if magic == 0x10B:
        # PE32: DataDirectory offset = 0x60
        dd_off = 0x60
    elif magic == 0x20B:
        # PE32+: DataDirectory offset = 0x70
        dd_off = 0x70
    else:
        return path.stat().st_size

    sec_dir_end = 0
    # IMAGE_DIRECTORY_ENTRY_SECURITY = 4
    if len(opt) >= dd_off + (5 * 8):
        sec_off, sec_size = struct.unpack_from("<II", opt, dd_off + (4 * 8))
        if sec_off and sec_size:
            sec_dir_end = sec_off + sec_size

    sect_table_off = e_lfanew + opt_off + opt_size
    sect_table = _read_at(path, sect_table_off, num_sections * 40)
    last_end = 0
    for i in range(num_sections):
        ent = sect_table[i * 40 : (i + 1) * 40]
        if len(ent) < 40:
            break
        size_raw = struct.unpack_from("<I", ent, 16)[0]
        ptr_raw = struct.unpack_from("<I", ent, 20)[0]
        last_end = max(last_end, ptr_raw + size_raw)

    return max(last_end, sec_dir_end)


def _overlay_probe(path: Path, overlay_off: int) -> tuple[int, bytes, bytes]:
    """
    返回：(overlay_len, overlay_first, overlay_last)
    用于判断 overlay 是否已经存在于输出文件末尾，而无需读完整 overlay。
    """
    size = path.stat().st_size
    if overlay_off >= size:
        return 0, b"", b""
    overlay_len = size - overlay_off
    head_len = min(64 * 1024, overlay_len)
    tail_len = min(64 * 1024, overlay_len)
    first = _read_at(path, overlay_off, head_len)
    last = _read_at(path, size - tail_len, tail_len)
    return overlay_len, first, last

_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


def safe_filename(name: str, fallback: str = "unnamed") -> str:
    name = name.strip()
    if not name:
        return fallback
    name = _INVALID_FILENAME_CHARS.sub("_", name)
    name = name.strip(" .")
    return name or fallback


def _is_int_resource(v: int) -> bool:
    return 0 <= v <= 0xFFFF


def _ptr_to_name_or_id(ptr: ctypes.c_void_p) -> tuple[Literal["id", "name"], int | str]:
    v = int(ptr.value or 0)
    if _is_int_resource(v):
        return ("id", v)
    return ("name", ctypes.wstring_at(v))


def _name_or_id_to_win_arg(kind: Literal["id", "name"], value: int | str) -> ctypes.c_void_p | ctypes.c_wchar_p:
    if kind == "id":
        if not isinstance(value, int) or not _is_int_resource(value):
            raise ValueError(f"Invalid int resource id: {value!r}")
        return ctypes.c_void_p(value)
    if not isinstance(value, str):
        raise ValueError(f"Invalid resource name: {value!r}")
    # 直接传 c_wchar_p，避免把指针当作整数资源 ID（MAKEINTRESOURCE）导致找不到资源。
    return ctypes.c_wchar_p(value)


class _Win32Error(RuntimeError):
    pass


def _raise_last_error(msg: str) -> None:
    err = ctypes.get_last_error()
    raise _Win32Error(f"{msg} (GetLastError={err})")


def iter_rcdata_resources(exe_path: Path) -> Iterator[dict[str, Any]]:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.LoadLibraryExW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_uint]
    kernel32.LoadLibraryExW.restype = ctypes.c_void_p
    kernel32.FreeLibrary.argtypes = [ctypes.c_void_p]
    kernel32.FreeLibrary.restype = ctypes.c_bool
    kernel32.EnumResourceNamesW.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    kernel32.EnumResourceNamesW.restype = ctypes.c_bool
    kernel32.EnumResourceLanguagesW.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    kernel32.EnumResourceLanguagesW.restype = ctypes.c_bool
    kernel32.FindResourceExW.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ushort]
    kernel32.FindResourceExW.restype = ctypes.c_void_p
    kernel32.LoadResource.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    kernel32.LoadResource.restype = ctypes.c_void_p
    kernel32.LockResource.argtypes = [ctypes.c_void_p]
    kernel32.LockResource.restype = ctypes.c_void_p
    kernel32.SizeofResource.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    kernel32.SizeofResource.restype = ctypes.c_uint

    LOAD_LIBRARY_AS_DATAFILE = 0x00000002
    LOAD_LIBRARY_AS_IMAGE_RESOURCE = 0x00000020
    # 某些 EXE（例如带壳/非标准 PE）仅用 DATAFILE 会导致 EnumResource* 失败（ERROR_RESOURCE_DATA_NOT_FOUND）。
    h_module = kernel32.LoadLibraryExW(
        str(exe_path),
        None,
        LOAD_LIBRARY_AS_DATAFILE | LOAD_LIBRARY_AS_IMAGE_RESOURCE,
    )
    if not h_module:
        _raise_last_error(f"LoadLibraryExW failed: {exe_path}")

    try:
        EnumResNameProc = ctypes.WINFUNCTYPE(
            ctypes.c_bool,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
        )
        EnumResLangProc = ctypes.WINFUNCTYPE(
            ctypes.c_bool,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_ushort,
            ctypes.c_void_p,
        )

        names: list[tuple[Literal["id", "name"], int | str]] = []
        langs: list[tuple[tuple[Literal["id", "name"], int | str], int]] = []

        def on_name(_h, _type, name, _lparam) -> bool:
            names.append(_ptr_to_name_or_id(ctypes.c_void_p(name)))
            return True

        def on_lang(_h, _type, name, lang, _lparam) -> bool:
            langs.append((_ptr_to_name_or_id(ctypes.c_void_p(name)), int(lang)))
            return True

        cb_name = EnumResNameProc(on_name)
        cb_lang = EnumResLangProc(on_lang)

        if not kernel32.EnumResourceNamesW(h_module, ctypes.c_void_p(RT_RCDATA), cb_name, None):
            err = ctypes.get_last_error()
            # 有些 EXE 根本没有 RT_RCDATA；这不是异常情况。
            if err in (1812, 1813):  # ERROR_RESOURCE_NAME_NOT_FOUND / ERROR_RESOURCE_TYPE_NOT_FOUND
                return
            _raise_last_error("EnumResourceNamesW failed (RT_RCDATA)")

        for kind, value in names:
            name_arg = _name_or_id_to_win_arg(kind, value)
            if not kernel32.EnumResourceLanguagesW(
                h_module,
                ctypes.c_void_p(RT_RCDATA),
                ctypes.cast(name_arg, ctypes.c_void_p),
                cb_lang,
                None,
            ):
                _raise_last_error(f"EnumResourceLanguagesW failed ({kind}={value!r})")

        for (kind, value), lang in langs:
            name_arg = _name_or_id_to_win_arg(kind, value)
            h_res = kernel32.FindResourceExW(
                h_module,
                ctypes.c_void_p(RT_RCDATA),
                ctypes.cast(name_arg, ctypes.c_void_p),
                ctypes.c_ushort(lang),
            )
            if not h_res:
                _raise_last_error(f"FindResourceExW failed ({kind}={value!r}, lang={lang})")

            size = kernel32.SizeofResource(h_module, h_res)
            if size <= 0:
                continue

            h_data = kernel32.LoadResource(h_module, h_res)
            if not h_data:
                _raise_last_error(f"LoadResource failed ({kind}={value!r}, lang={lang})")

            p_data = kernel32.LockResource(h_data)
            if not p_data:
                _raise_last_error(f"LockResource failed ({kind}={value!r}, lang={lang})")

            raw = ctypes.string_at(p_data, size)
            yield {
                "type": "RT_RCDATA",
                "name": {"kind": kind, "value": value},
                "lang": lang,
                "data": raw,
            }
    finally:
        kernel32.FreeLibrary(h_module)


def update_rcdata_resource(
    exe_path: Path,
    *,
    name_kind: Literal["id", "name"],
    name_value: int | str,
    lang: int,
    data: bytes,
) -> None:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.BeginUpdateResourceW.argtypes = [ctypes.c_wchar_p, ctypes.c_bool]
    kernel32.BeginUpdateResourceW.restype = ctypes.c_void_p
    kernel32.UpdateResourceW.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_ushort,
        ctypes.c_void_p,
        ctypes.c_uint,
    ]
    kernel32.UpdateResourceW.restype = ctypes.c_bool
    kernel32.EndUpdateResourceW.argtypes = [ctypes.c_void_p, ctypes.c_bool]
    kernel32.EndUpdateResourceW.restype = ctypes.c_bool

    h_update = kernel32.BeginUpdateResourceW(str(exe_path), False)
    if not h_update:
        _raise_last_error(f"BeginUpdateResourceW failed: {exe_path}")

    try:
        name_arg = _name_or_id_to_win_arg(name_kind, name_value)
        buf = ctypes.create_string_buffer(data)
        ok = kernel32.UpdateResourceW(
            h_update,
            ctypes.c_void_p(RT_RCDATA),
            ctypes.cast(name_arg, ctypes.c_void_p),
            ctypes.c_ushort(lang),
            ctypes.cast(buf, ctypes.c_void_p),
            ctypes.c_uint(len(data)),
        )
        if not ok:
            _raise_last_error(f"UpdateResourceW failed ({name_kind}={name_value!r}, lang={lang})")
    finally:
        if not kernel32.EndUpdateResourceW(h_update, False):
            _raise_last_error("EndUpdateResourceW failed")


class ByteReader:
    def __init__(self, data: bytes, pos: int = 0):
        self.data = data
        self.pos = pos

    def remaining(self) -> int:
        return len(self.data) - self.pos

    def peek_u8(self) -> int:
        if self.pos >= len(self.data):
            raise EOFError("Unexpected EOF")
        return self.data[self.pos]

    def read_u8(self) -> int:
        b = self.peek_u8()
        self.pos += 1
        return b

    def read_i8(self) -> int:
        b = self.read_u8()
        return b - 256 if b >= 128 else b

    def read_u16le(self) -> int:
        if self.remaining() < 2:
            raise EOFError("Unexpected EOF")
        b0 = self.data[self.pos]
        b1 = self.data[self.pos + 1]
        self.pos += 2
        return b0 | (b1 << 8)

    def read_i16le(self) -> int:
        v = self.read_u16le()
        return v - 0x10000 if v >= 0x8000 else v

    def read_u32le(self) -> int:
        if self.remaining() < 4:
            raise EOFError("Unexpected EOF")
        b = self.data[self.pos : self.pos + 4]
        self.pos += 4
        return int.from_bytes(b, "little", signed=False)

    def read_i32le(self) -> int:
        if self.remaining() < 4:
            raise EOFError("Unexpected EOF")
        b = self.data[self.pos : self.pos + 4]
        self.pos += 4
        return int.from_bytes(b, "little", signed=True)

    def read_i64le(self) -> int:
        if self.remaining() < 8:
            raise EOFError("Unexpected EOF")
        b = self.data[self.pos : self.pos + 8]
        self.pos += 8
        return int.from_bytes(b, "little", signed=True)

    def read_bytes(self, n: int) -> bytes:
        if self.remaining() < n:
            raise EOFError("Unexpected EOF")
        b = self.data[self.pos : self.pos + n]
        self.pos += n
        return b

    def read_shortstr_bytes(self) -> bytes:
        n = self.read_u8()
        return self.read_bytes(n)

    def read_shortstr_text(self, encoding: str = "latin1") -> str:
        return self.read_shortstr_bytes().decode(encoding, errors="strict")


class ByteWriter:
    def __init__(self):
        self.parts: list[bytes] = []

    def write_i8(self, v: int) -> None:
        self.parts.append(int(v).to_bytes(1, "little", signed=True))

    def write_u8(self, v: int) -> None:
        self.parts.append(bytes((v & 0xFF,)))

    def write_i16le(self, v: int) -> None:
        self.parts.append(int(v).to_bytes(2, "little", signed=True))

    def write_u16le(self, v: int) -> None:
        self.parts.append(int(v & 0xFFFF).to_bytes(2, "little", signed=False))

    def write_i32le(self, v: int) -> None:
        self.parts.append(int(v).to_bytes(4, "little", signed=True))

    def write_u32le(self, v: int) -> None:
        self.parts.append(int(v & 0xFFFFFFFF).to_bytes(4, "little", signed=False))

    def write_i64le(self, v: int) -> None:
        self.parts.append(int(v).to_bytes(8, "little", signed=True))

    def write_bytes(self, b: bytes) -> None:
        self.parts.append(b)

    def write_shortstr_bytes(self, b: bytes) -> None:
        if len(b) > 255:
            raise ValueError(f"ShortString too long: {len(b)} bytes")
        self.write_u8(len(b))
        self.write_bytes(b)

    def write_shortstr_text(self, s: str) -> None:
        b = s.encode("latin1", errors="strict")
        self.write_shortstr_bytes(b)

    def to_bytes(self) -> bytes:
        return b"".join(self.parts)


def _ext80_to_float(b10: bytes) -> float:
    if len(b10) != 10:
        raise ValueError("extended80 requires 10 bytes")
    significand = int.from_bytes(b10[:8], "little", signed=False)
    se = int.from_bytes(b10[8:], "little", signed=False)
    sign = (se >> 15) & 1
    exp = se & 0x7FFF
    if exp == 0 and significand == 0:
        return -0.0 if sign else 0.0
    if exp == 0x7FFF:
        return float("-inf") if sign else float("inf")
    mant = significand / (1 << 63)
    try:
        val = math.ldexp(mant, exp - 16383)
    except OverflowError:
        val = float("inf")
    return -val if sign else val


def _float_to_ext80(x: float) -> bytes:
    if x == 0.0:
        return b"\x00" * 10
    if math.isinf(x):
        sign = 1 if x < 0 else 0
        se = (sign << 15) | 0x7FFF
        return (0).to_bytes(8, "little") + se.to_bytes(2, "little")
    if math.isnan(x):
        se = 0x7FFF
        return (1 << 63).to_bytes(8, "little") + se.to_bytes(2, "little")

    sign = 1 if x < 0 else 0
    x = abs(x)
    m, e = math.frexp(x)
    m *= 2.0
    e -= 1
    exp = e + 16383
    if exp <= 0:
        return b"\x00" * 10
    if exp >= 0x7FFF:
        se = (sign << 15) | 0x7FFF
        return (0).to_bytes(8, "little") + se.to_bytes(2, "little")
    significand = int(m * (1 << 63))
    se = (sign << 15) | (exp & 0x7FFF)
    return significand.to_bytes(8, "little", signed=False) + se.to_bytes(2, "little", signed=False)


@dataclass(frozen=True)
class Ident:
    name: str


@dataclass(frozen=True)
class SetValue:
    items: tuple[str, ...]


@dataclass(frozen=True)
class ListValue:
    items: tuple[Any, ...]


@dataclass(frozen=True)
class CollectionValue:
    items: tuple[tuple[tuple[str, Any], ...], ...]


@dataclass
class Component:
    kind: Literal["object", "inherited", "inline"]
    name: str
    class_name: str
    properties: list[tuple[str, Any]]
    children: list["Component"]


def _decode_ansi(b: bytes, encoding_in: str) -> str:
    try:
        return b.decode(encoding_in, errors="strict")
    except UnicodeDecodeError:
        return b.decode("latin1", errors="strict")


def _encode_ansi(s: str, encoding_out: str, *, context: str) -> bytes:
    try:
        return s.encode(encoding_out, errors="ignore")
    except UnicodeEncodeError as e:
        raise UnicodeEncodeError(
            e.encoding,
            e.object,
            e.start,
            e.end,
            f"{e.reason} (context={context})",
        ) from None


def _read_value(r: ByteReader, encoding_in: str) -> Any:
    tag = r.read_u8()

    if tag == 0:  # vaNull (also list end)
        return None
    if tag == 1:  # vaList
        items: list[Any] = []
        while True:
            if r.peek_u8() == 0:
                r.read_u8()
                break
            items.append(_read_value(r, encoding_in))
        return ListValue(tuple(items))
    if tag == 2:  # vaInt8
        return r.read_i8()
    if tag == 3:  # vaInt16
        return r.read_i16le()
    if tag == 4:  # vaInt32
        return r.read_i32le()
    if tag == 5:  # vaExtended (80-bit)
        return _ext80_to_float(r.read_bytes(10))
    if tag == 6:  # vaString (ShortString)
        return _decode_ansi(r.read_shortstr_bytes(), encoding_in)
    if tag == 7:  # vaIdent
        return Ident(r.read_shortstr_text("latin1"))
    if tag == 8:  # vaFalse
        return False
    if tag == 9:  # vaTrue
        return True
    if tag == 10:  # vaBinary
        # Delphi/FPC 的二进制块：Word 块长度 + 数据，直到长度=0
        out = bytearray()
        while True:
            if r.remaining() < 2:
                raise EOFError("Unexpected EOF in vaBinary")
            chunk = r.read_u16le()
            if chunk == 0:
                break
            out.extend(r.read_bytes(chunk))
        return bytes(out)
    if tag == 11:  # vaSet
        # Delphi/FPC：一组 ShortString 标识符，直到空字符串结束
        items: list[str] = []
        while True:
            s = r.read_shortstr_text("latin1")
            if s == "":
                break
            items.append(s)
        return SetValue(tuple(items))
    if tag == 12:  # vaLString (AnsiString)
        n = r.read_u32le()
        if n > r.remaining() and r.remaining() >= 2:
            # 兼容 16-bit 长度
            r.pos -= 4
            n2 = r.read_u16le()
            n = n2
        return _decode_ansi(r.read_bytes(n), encoding_in)
    if tag == 13:  # vaNil
        return None
    if tag == 14:  # vaCollection
        b = r.read_u8()
        if b == 0:
            return CollectionValue(tuple())
        if b != 1:
            raise ValueError("Invalid vaCollection: missing list-begin")
        items: list[tuple[tuple[str, Any], ...]] = []
        while True:
            # 0 表示 collection 列表结束
            if r.peek_u8() == 0:
                r.read_u8()
                break
            # 有些流会在每个 item 前写入 1（item-begin）
            if r.peek_u8() == 1:
                r.read_u8()
            props: list[tuple[str, Any]] = []
            while True:
                prop = r.read_shortstr_text("latin1")
                if prop == "":
                    break
                props.append((prop, _read_value(r, encoding_in)))
            items.append(tuple(props))
        return CollectionValue(tuple(items))
    if tag == 15:  # vaSingle
        b = r.read_bytes(4)
        return ctypes.c_float.from_buffer_copy(b).value
    if tag == 16:  # vaCurrency (int64 scaled by 10000)
        return r.read_i64le() / 10000.0
    if tag == 17:  # vaDate (double)
        b = r.read_bytes(8)
        return ctypes.c_double.from_buffer_copy(b).value
    if tag == 18:  # vaWString (WideString)
        n = r.read_u32le()
        need = n * 2
        if need > r.remaining() and n <= r.remaining():
            # 某些流里长度按“字节数”写入
            need = n
        return r.read_bytes(need).decode("utf-16le", errors="strict")
    if tag == 19:  # vaInt64
        return r.read_i64le()
    if tag == 20:  # vaUTF8String
        n = r.read_u32le()
        if n > r.remaining() and r.remaining() >= 2:
            r.pos -= 4
            n = r.read_u16le()
        return r.read_bytes(n).decode("utf-8", errors="strict")
    if tag == 21:  # vaUString (UnicodeString)
        n = r.read_u32le()
        need = n * 2
        if need > r.remaining() and n <= r.remaining():
            need = n
        return r.read_bytes(need).decode("utf-16le", errors="strict")

    raise ValueError(f"Unsupported value tag: {tag}")


def _read_component_body(r: ByteReader, encoding_in: str) -> Component | None:
    kind: Literal["object", "inherited", "inline"] = "object"
    # Delphi/FPC 在二进制流里会用前缀字节标记 inherited/inline
    # 常见：$F1=inherited, $F4=inline
    if r.remaining() > 0:
        b = r.peek_u8()
        if b == 0xF1:
            kind = "inherited"
            r.read_u8()
        elif b == 0xF4:
            kind = "inline"
            r.read_u8()

    class_name = r.read_shortstr_text("latin1")
    if class_name == "":
        return None
    name = r.read_shortstr_text("latin1")

    props: list[tuple[str, Any]] = []
    while True:
        prop = r.read_shortstr_text("latin1")
        if prop == "":
            break
        props.append((prop, _read_value(r, encoding_in)))

    children: list[Component] = []
    while True:
        if r.peek_u8() == 0:
            r.read_u8()
            break
        child = _read_component_body(r, encoding_in)
        if child is None:
            break
        children.append(child)

    return Component(kind=kind, name=name, class_name=class_name, properties=props, children=children)


def dfm_binary_to_component(data: bytes, *, encoding_in: str) -> Component:
    start = 0
    if not data.startswith(b"TPF0"):
        i = data.find(b"TPF0")
        if i < 0:
            raise ValueError("Not a binary DFM stream: missing TPF0 signature")
        start = i
    r = ByteReader(data, start + 4)
    root = _read_component_body(r, encoding_in)
    if root is None:
        raise ValueError("Invalid DFM: empty root")
    return root


def _escape_dfm_string(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def _format_bytes_blob(b: bytes, indent: str) -> str:
    if not b:
        return "{}"
    hex_str = b.hex().upper()
    pairs = [hex_str[i : i + 2] for i in range(0, len(hex_str), 2)]
    lines: list[str] = []
    chunk = 32
    for i in range(0, len(pairs), chunk):
        lines.append(indent + "  " + "".join(pairs[i : i + chunk]))
    return "{\n" + "\n".join(lines) + "\n" + indent + "}"


def _value_to_text(v: Any, indent: str) -> str:
    if v is None:
        return "nil"
    if isinstance(v, bool):
        return "True" if v else "False"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if math.isfinite(v):
            return repr(v)
        return "0"
    if isinstance(v, Ident):
        return v.name
    if isinstance(v, str):
        return _escape_dfm_string(v)
    if isinstance(v, SetValue):
        return "[" + ", ".join(v.items) + "]"
    if isinstance(v, ListValue):
        if not v.items:
            return "()"
        lines = ["("]
        for item in v.items:
            lines.append(indent + "  " + _value_to_text(item, indent + "  "))
        lines.append(indent + ")")
        return "\n".join(lines)
    if isinstance(v, CollectionValue):
        lines = ["<"]
        for item in v.items:
            lines.append(indent + "  item")
            for k, vv in item:
                lines.append(indent + "    " + k + " = " + _value_to_text(vv, indent + "    "))
            lines.append(indent + "  end")
        lines.append(indent + ">")
        return "\n".join(lines)
    if isinstance(v, (bytes, bytearray)):
        return _format_bytes_blob(bytes(v), indent)
    raise TypeError(f"Unsupported value type: {type(v)}")


def component_to_dfm_text(root: Component) -> str:
    lines: list[str] = []

    def walk(c: Component, indent: str) -> None:
        lines.append(f"{indent}{c.kind} {c.name}: {c.class_name}")
        for k, v in c.properties:
            rendered = _value_to_text(v, indent + "  ")
            if "\n" in rendered:
                first, *rest = rendered.splitlines()
                lines.append(f"{indent}  {k} = {first}")
                for ln in rest:
                    lines.append(f"{indent}  {ln}")
            else:
                lines.append(f"{indent}  {k} = {rendered}")
        for child in c.children:
            walk(child, indent + "  ")
        lines.append(f"{indent}end")

    walk(root, "")
    return "\n".join(lines) + "\n"


class _Tok:
    __slots__ = ("kind", "value", "pos")

    def __init__(self, kind: str, value: str, pos: int):
        self.kind = kind
        self.value = value
        self.pos = pos


class DfmTextTokenizer:
    def __init__(self, text: str):
        self.text = text
        self.i = 0
        self.n = len(text)

    def _peek(self) -> str:
        return self.text[self.i] if self.i < self.n else ""

    def _get(self) -> str:
        ch = self._peek()
        self.i += 1
        return ch

    def tokens(self) -> Iterator[_Tok]:
        while self.i < self.n:
            ch = self._peek()
            if ch.isspace():
                self.i += 1
                continue
            pos = self.i

            if ch in "=:[].(),<>{}":
                self.i += 1
                yield _Tok(ch, ch, pos)
                continue

            if ch == "'":
                self.i += 1
                out: list[str] = []
                while True:
                    if self.i >= self.n:
                        raise ValueError("Unterminated string literal")
                    c = self._get()
                    if c == "'":
                        if self._peek() == "'":
                            self.i += 1
                            out.append("'")
                            continue
                        break
                    out.append(c)
                yield _Tok("STRING", "".join(out), pos)
                continue

            if ch == "#":
                self.i += 1
                j = self.i
                while self.i < self.n and self.text[self.i].isdigit():
                    self.i += 1
                if j == self.i:
                    raise ValueError(f"Invalid # token at {pos}")
                yield _Tok("HASHNUM", self.text[j : self.i], pos)
                continue

            if ch in "+-" or ch.isdigit():
                j = self.i
                if ch in "+-":
                    self.i += 1
                while self.i < self.n and self.text[self.i].isdigit():
                    self.i += 1
                if self.i < self.n and self.text[self.i] == ".":
                    self.i += 1
                    while self.i < self.n and self.text[self.i].isdigit():
                        self.i += 1
                if self.i < self.n and self.text[self.i] in "eE":
                    self.i += 1
                    if self.i < self.n and self.text[self.i] in "+-":
                        self.i += 1
                    while self.i < self.n and self.text[self.i].isdigit():
                        self.i += 1
                yield _Tok("NUMBER", self.text[j : self.i], pos)
                continue

            if ch.isalpha() or ch in "_":
                j = self.i
                self.i += 1
                while self.i < self.n:
                    c = self.text[self.i]
                    if c.isalnum() or c in "._":
                        self.i += 1
                    else:
                        break
                yield _Tok("IDENT", self.text[j : self.i], pos)
                continue

            raise ValueError(f"Unexpected character {ch!r} at {pos}")

        yield _Tok("EOF", "", self.n)


class DfmTextParser:
    def __init__(self, text: str, *, encoding_in_for_hash: str):
        self.tokens = list(DfmTextTokenizer(text).tokens())
        self.k = 0
        self.encoding_in_for_hash = encoding_in_for_hash

    def _cur(self) -> _Tok:
        return self.tokens[self.k]

    def _eat(self, kind: str | None = None, value_ci: str | None = None) -> _Tok:
        tok = self._cur()
        if kind is not None and tok.kind != kind:
            raise ValueError(f"Expected {kind}, got {tok.kind} at {tok.pos}")
        if value_ci is not None:
            if tok.value.lower() != value_ci.lower():
                raise ValueError(f"Expected {value_ci}, got {tok.value} at {tok.pos}")
        self.k += 1
        return tok

    def parse(self) -> Component:
        tok = self._eat("IDENT")
        if tok.value.lower() not in ("object", "inherited", "inline"):
            raise ValueError(f"Expected object/inherited/inline at {tok.pos}")
        kind: Literal["object", "inherited", "inline"] = tok.value.lower()  # type: ignore[assignment]
        name = self._eat("IDENT").value
        self._eat(":")
        class_name = self._eat("IDENT").value
        props: list[tuple[str, Any]] = []
        children: list[Component] = []
        while True:
            tok = self._cur()
            if tok.kind == "IDENT" and tok.value.lower() in ("object", "inherited", "inline"):
                children.append(self.parse())
                continue
            if tok.kind == "IDENT" and tok.value.lower() == "end":
                self._eat("IDENT")
                break
            if tok.kind == "EOF":
                raise ValueError("Unexpected EOF (missing end)")
            key = self._eat("IDENT").value
            self._eat("=")
            val = self._parse_value()
            props.append((key, val))
        return Component(kind=kind, name=name, class_name=class_name, properties=props, children=children)

    def _parse_value(self) -> Any:
        tok = self._cur()
        if tok.kind in ("STRING", "HASHNUM"):
            return self._parse_delphi_string_expr()
        if tok.kind == "NUMBER":
            s = self._eat("NUMBER").value
            if "." in s or "e" in s.lower():
                return float(s)
            return int(s, 10)
        if tok.kind == "IDENT":
            v = self._eat("IDENT").value
            if v.lower() == "true":
                return True
            if v.lower() == "false":
                return False
            if v.lower() == "nil":
                return None
            return Ident(v)
        if tok.kind == "[":
            self._eat("[")
            items: list[str] = []
            while self._cur().kind != "]":
                if self._cur().kind == ",":
                    self._eat(",")
                    continue
                items.append(self._eat("IDENT").value)
            self._eat("]")
            return SetValue(tuple(items))
        if tok.kind == "(":
            self._eat("(")
            items: list[Any] = []
            while self._cur().kind != ")":
                if self._cur().kind == ",":
                    self._eat(",")
                    continue
                items.append(self._parse_value())
            self._eat(")")
            return ListValue(tuple(items))
        if tok.kind == "{":
            return self._parse_hex_blob()
        if tok.kind == "<":
            return self._parse_collection()
        raise ValueError(f"Unexpected token {tok.kind}/{tok.value} at {tok.pos}")

    def _parse_delphi_string_expr(self) -> str:
        parts_str: list[str] = []
        parts_bytes: bytearray | None = None

        while True:
            tok = self._cur()
            if tok.kind == "STRING":
                s = self._eat("STRING").value
                if parts_bytes is not None:
                    parts_bytes.extend(s.encode("latin1", errors="replace"))
                else:
                    parts_str.append(s)
                continue
            if tok.kind == "HASHNUM":
                n = int(self._eat("HASHNUM").value, 10)
                if not (0 <= n <= 255):
                    parts_str.append(chr(n))
                    continue
                if parts_bytes is None:
                    parts_bytes = bytearray()
                    for s in parts_str:
                        parts_bytes.extend(s.encode("latin1", errors="replace"))
                    parts_str.clear()
                parts_bytes.append(n)
                continue
            break

        if parts_bytes is not None:
            return _decode_ansi(bytes(parts_bytes), self.encoding_in_for_hash)
        return "".join(parts_str)

    def _parse_hex_blob(self) -> bytes:
        self._eat("{")
        hex_chars: list[str] = []
        while self._cur().kind != "}":
            tok = self._cur()
            if tok.kind == "EOF":
                raise ValueError("Unterminated hex blob")
            if tok.kind in ("IDENT", "NUMBER"):
                hex_chars.append(self._eat(tok.kind).value)
            else:
                self._eat(tok.kind)
        self._eat("}")
        s = "".join(hex_chars)
        s = re.sub(r"[^0-9a-fA-F]", "", s)
        if len(s) % 2 != 0:
            raise ValueError("Hex blob length must be even")
        return bytes.fromhex(s)

    def _parse_collection(self) -> CollectionValue:
        self._eat("<")
        items: list[tuple[tuple[str, Any], ...]] = []
        while True:
            tok = self._cur()
            if tok.kind == ">":
                self._eat(">")
                break
            self._eat("IDENT", "item")
            props: list[tuple[str, Any]] = []
            while True:
                tok = self._cur()
                if tok.kind == "IDENT" and tok.value.lower() == "end":
                    self._eat("IDENT")
                    break
                key = self._eat("IDENT").value
                self._eat("=")
                props.append((key, self._parse_value()))
            items.append(tuple(props))
        return CollectionValue(tuple(items))


def dfm_text_to_component(text: str, *, encoding_in_for_hash: str) -> Component:
    return DfmTextParser(text, encoding_in_for_hash=encoding_in_for_hash).parse()


def _write_value(w: ByteWriter, v: Any, *, encoding_out: str, context: str) -> None:
    if v is None:
        w.write_u8(13)  # vaNil
        return
    if isinstance(v, bool):
        w.write_u8(9 if v else 8)
        return
    if isinstance(v, int):
        # 尽量匹配 Delphi 生成的最小整数类型（很多属性用 Int8/Int16）
        if -128 <= v <= 127:
            w.write_u8(2)  # vaInt8
            w.write_i8(v)
        elif -32768 <= v <= 32767:
            w.write_u8(3)  # vaInt16
            w.write_i16le(v)
        else:
            w.write_u8(4)  # vaInt32
            w.write_i32le(v)
        return
    if isinstance(v, float):
        w.write_u8(5)  # vaExtended
        w.write_bytes(_float_to_ext80(v))
        return
    if isinstance(v, Ident):
        w.write_u8(7)  # vaIdent
        w.write_shortstr_text(v.name)
        return
    if isinstance(v, str):
        b = _encode_ansi(v, encoding_out, context=context)
        # <=255 字节用 vaString(ShortString) 更贴近原版 DFM
        if len(b) <= 255:
            w.write_u8(6)  # vaString
            w.write_shortstr_bytes(b)
        else:
            w.write_u8(12)  # vaLString
            w.write_u32le(len(b))
            w.write_bytes(b)
        return
    if isinstance(v, SetValue):
        w.write_u8(11)
        for item in v.items:
            w.write_shortstr_text(item)
        w.write_u8(0)
        return
    if isinstance(v, ListValue):
        w.write_u8(1)
        for idx, item in enumerate(v.items):
            _write_value(w, item, encoding_out=encoding_out, context=f"{context}[{idx}]")
        w.write_u8(0)
        return
    if isinstance(v, CollectionValue):
        # Delphi/FPC 的 vaCollection：
        # - 空集合：tag(14) + 0
        # - 非空：tag(14) + 1(list-begin) + [1(item-begin) + itemProps...] + 0(list-end)
        # itemProps: propName/value... + ""(0长度) 结束
        w.write_u8(14)
        if not v.items:
            w.write_u8(0)
            return
        w.write_u8(1)  # list-begin
        for item_idx, item in enumerate(v.items):
            # 原版 DFM：第一个 item 前通常没有 1；后续 item 前有 1
            if item_idx != 0:
                w.write_u8(1)
            for k, vv in item:
                w.write_shortstr_text(k)
                _write_value(w, vv, encoding_out=encoding_out, context=f"{context}<{item_idx}>.{k}")
            w.write_u8(0)  # end-of-item properties (empty shortstring)
        w.write_u8(0)  # list-end
        return
    if isinstance(v, (bytes, bytearray)):
        b = bytes(v)
        # Delphi/FPC 写法：vaBinary + (word chunkLen + chunkBytes)* + word(0)
        w.write_u8(10)
        pos = 0
        while pos < len(b):
            n = min(0xFFFE, len(b) - pos)
            w.write_u16le(n)
            w.write_bytes(b[pos : pos + n])
            pos += n
        w.write_u16le(0)
        return
    raise TypeError(f"Unsupported value type for writing: {type(v)}")


def _write_component_body(w: ByteWriter, c: Component, *, encoding_out: str, context: str) -> None:
    if c.kind == "inherited":
        w.write_u8(0xF1)
    elif c.kind == "inline":
        w.write_u8(0xF4)
    w.write_shortstr_text(c.class_name)
    w.write_shortstr_text(c.name)
    for k, v in c.properties:
        w.write_shortstr_text(k)
        _write_value(w, v, encoding_out=encoding_out, context=f"{context}.{k}")
    w.write_u8(0)  # end properties
    for idx, child in enumerate(c.children):
        _write_component_body(w, child, encoding_out=encoding_out, context=f"{context}.children[{idx}]")
    w.write_u8(0)  # end children


def component_to_dfm_binary(root: Component, *, encoding_out: str) -> bytes:
    w = ByteWriter()
    w.write_bytes(b"TPF0")
    _write_component_body(w, root, encoding_out=encoding_out, context=f"{root.name}:{root.class_name}")
    return w.to_bytes()


def _read_text_guess(path: Path, *, fallback_encoding: str) -> str:
    b = path.read_bytes()
    for enc in ("utf-8", "utf-8-sig", fallback_encoding):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("latin1")


def _load_preextracted_dfm_texts(dfm_n_dir: Path, *, fallback_encoding: str) -> dict[str, tuple[Path, str]]:
    """
    读取已有的文本 DFM（例如 konohana/dfm_n/*.dfm），用于在纯 Python 解析失败时兜底。
    返回：UPPER(类名) -> (path, text)
    """
    out: dict[str, tuple[Path, str]] = {}
    if not dfm_n_dir.exists():
        return out
    for p in dfm_n_dir.glob("*.dfm"):
        try:
            txt = _read_text_guess(p, fallback_encoding=fallback_encoding)
        except OSError:
            continue
        first = txt.splitlines()[0].strip() if txt else ""
        # object Name: TClass
        m = re.match(r"^(object|inherited|inline)\s+[^:]+:\s*([A-Za-z0-9_]+)\s*$", first, re.IGNORECASE)
        if not m:
            continue
        cls = m.group(2).upper()
        out[cls] = (p, txt)
    return out


def extract_dfm_from_exe(
    exe_path: Path,
    *,
    out_root: Path,
    encoding_in: str,
) -> Path:
    out_root.mkdir(parents=True, exist_ok=True)
    dfm_dir = out_root / "dfm"
    dfm_dir.mkdir(parents=True, exist_ok=True)

    exe_hash = sha256_file(exe_path)
    resources: list[dict[str, Any]] = []
    # 兜底：如果有历史提取的文本 DFM，就用它来生成可编辑文本
    pre_dfm_map = _load_preextracted_dfm_texts(
        Path(__file__).resolve().parent / "konohana" / "dfm_n",
        fallback_encoding=encoding_in,
    )

    for res in iter_rcdata_resources(exe_path):
        data: bytes = res["data"]
        if not data.startswith(b"TPF0"):
            continue
        name = res["name"]
        lang = int(res["lang"])

        parse_ok = False
        root_name = ""
        root_class = name["value"] if name["kind"] == "name" else f"#{name['value']}"
        dfm_text: str | None = None

        try:
            root = dfm_binary_to_component(data, encoding_in=encoding_in)
            dfm_text = component_to_dfm_text(root)
            parse_ok = True
            root_name = root.name
            root_class = root.class_name
        except Exception:
            # 纯 Python 解析失败时，尝试使用已有的 dfm_n 兜底
            if isinstance(root_class, str):
                hit = pre_dfm_map.get(str(root_class).upper())
                if hit:
                    root_name = ""
                    root_class = str(root_class)
                    dfm_text = hit[1]

        # 文件名：优先用 DFM 第一行里的 object 名（通常是更友好的混合大小写），否则回退资源名。
        file_stem_base = ""
        if dfm_text:
            first = dfm_text.splitlines()[0].strip() if dfm_text else ""
            m = re.match(r"^(object|inherited|inline)\s+([^:]+):\s*([A-Za-z0-9_]+)\s*$", first, re.IGNORECASE)
            if m:
                file_stem_base = m.group(2).strip()
        if not file_stem_base:
            file_stem_base = f"{name['value']}" if name["kind"] == "name" else f"#{name['value']}"
        file_stem_base = safe_filename(file_stem_base)
        file_stem = file_stem_base
        # 一般 lang=0 没必要写进文件名；若存在重复再追加。
        if lang != 0:
            file_stem = safe_filename(f"{file_stem_base}_lang{lang}")
        # 避免重名覆盖
        n = 2
        while (dfm_dir / f"{file_stem}.dfm").exists():
            suffix = f"_lang{lang}" if lang != 0 else str(n)
            file_stem = safe_filename(f"{file_stem_base}_{suffix}")
            n += 1
        dfm_text_path = dfm_dir / f"{file_stem}.dfm"

        if dfm_text is not None:
            dfm_text_path.write_text(dfm_text, encoding="utf-8", newline="\n")

        resources.append(
            {
                "type": "RT_RCDATA",
                "name": name,
                "lang": lang,
                "dfm_text": str(dfm_text_path.relative_to(out_root)).replace("\\", "/"),
                "root": {"name": root_name, "class": root_class},
                "parse_ok": parse_ok,
            }
        )

    if not resources:
        raise RuntimeError("未找到任何以 RT_RCDATA 存储、且以 TPF0 开头的 DFM 资源。")

    manifest = {
        "tool": "konohana_dfm_tool",
        "version": 1,
        "input_exe": str(exe_path),
        "input_exe_sha256": exe_hash,
        "encoding_in": encoding_in,
        "resources": resources,
    }
    (out_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return out_root


def write_dfm_back_to_exe(
    exe_path: Path,
    *,
    work_dir: Path,
    output_exe: Path,
    encoding_in_for_hash: str,
    encoding_out: str,
) -> None:
    manifest_path = work_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"找不到 manifest.json：{manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = manifest.get("input_exe_sha256")
    if expected:
        actual = sha256_file(exe_path)
        if actual.lower() != str(expected).lower():
            raise RuntimeError("输入 EXE 与 manifest.json 不匹配（sha256 不一致）。")

    if output_exe.resolve() == exe_path.resolve():
        raise RuntimeError("输出 EXE 不能与输入 EXE 同名同路径。")
    output_exe.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(exe_path, output_exe)

    # 关键：保留 EXE 末尾 overlay（比如 kirikiri 封包），否则写回后文件会被截断变小。
    overlay_off = _pe_overlay_offset(exe_path)
    overlay_len, overlay_first, overlay_last = _overlay_probe(exe_path, overlay_off)

    updated = 0
    for res in manifest.get("resources", []):
        dfm_text_rel = res["dfm_text"]
        dfm_text_path = (work_dir / dfm_text_rel).resolve()
        if not dfm_text_path.exists():
            raise FileNotFoundError(f"缺少 DFM 文本：{dfm_text_path}")

        text = dfm_text_path.read_text(encoding="utf-8")
        root = dfm_text_to_component(text, encoding_in_for_hash=encoding_in_for_hash)
        new_bin = component_to_dfm_binary(root, encoding_out=encoding_out)

        name = res["name"]
        update_rcdata_resource(
            output_exe,
            name_kind=name["kind"],
            name_value=name["value"],
            lang=int(res["lang"]),
            data=new_bin,
        )
        updated += 1

    if updated == 0:
        raise RuntimeError("manifest.json 中没有 resources，无法写入。")

    if overlay_len > 0:
        out_size = output_exe.stat().st_size
        has_overlay = False
        if out_size >= overlay_len:
            # 检测 output 末尾是否已经包含 overlay（避免重复追加）
            out_first = _read_at(output_exe, out_size - overlay_len, len(overlay_first))
            out_last = _read_at(output_exe, out_size - len(overlay_last), len(overlay_last))
            has_overlay = (out_first == overlay_first) and (out_last == overlay_last)

        if not has_overlay:
            with output_exe.open("ab") as out_fp:
                _copy_range(exe_path, out_fp, overlay_off, overlay_len)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Konohana DFM 一体工具 (提取 / 写入)")
        self.geometry("720x220")

        self.var_enc_in = tk.StringVar(value="cp932")
        self.var_enc_out = tk.StringVar(value="cp936")

        frm = tk.Frame(self)
        frm.pack(fill="both", expand=True, padx=12, pady=12)

        row0 = tk.Frame(frm)
        row0.pack(fill="x")
        tk.Label(row0, text="提取解码(输入编码)：").pack(side="left")
        tk.Entry(row0, textvariable=self.var_enc_in, width=12).pack(side="left", padx=(6, 18))
        tk.Label(row0, text="写回编码(输出编码)：").pack(side="left")
        tk.Entry(row0, textvariable=self.var_enc_out, width=12).pack(side="left", padx=(6, 0))

        row1 = tk.Frame(frm)
        row1.pack(fill="x", pady=(14, 0))
        tk.Button(row1, text="提取", width=18, command=self.on_extract).pack(side="left")
        tk.Button(row1, text="写入", width=18, command=self.on_write).pack(side="left", padx=(12, 0))
        tk.Button(row1, text="导出BIN", width=18, command=self.on_export_bin).pack(side="left", padx=(12, 0))

        self.txt = tk.Text(frm, height=6, wrap="word")
        self.txt.pack(fill="both", expand=True, pady=(14, 0))
        self._log(
            "说明：\n- 提取：选择原始 EXE，会在脚本同目录生成 <exe名>_work\\manifest.json 与 dfm/。\n- 写入：选择工作目录(含 manifest.json) + 选择输出 EXE 文件名。"
        )

    def _log(self, s: str) -> None:
        self.txt.insert("end", s + "\n")
        self.txt.see("end")

    def on_extract(self) -> None:
        exe = filedialog.askopenfilename(
            title="选择要提取的游戏 EXE",
            filetypes=[("Executable", "*.exe"), ("All files", "*.*")],
        )
        if not exe:
            return
        exe_path = Path(exe)
        base_dir = Path(__file__).resolve().parent
        out_root = base_dir / f"{exe_path.stem}_work"
        enc_in = self.var_enc_in.get().strip() or "cp932"
        try:
            work_dir = extract_dfm_from_exe(exe_path, out_root=out_root, encoding_in=enc_in)
        except Exception as e:
            messagebox.showerror("提取失败", str(e))
            return
        self._log(f"[提取完成] 工作目录：{work_dir}")
        messagebox.showinfo("完成", f"提取完成：\n{work_dir}")

    def on_write(self) -> None:
        work_dir = filedialog.askdirectory(title="选择工作目录（包含 manifest.json）")
        if not work_dir:
            return
        work_dir_path = Path(work_dir)

        manifest_path = work_dir_path / "manifest.json"
        if not manifest_path.exists():
            messagebox.showerror("写入失败", f"找不到 manifest.json：{manifest_path}")
            return
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as e:
            messagebox.showerror("写入失败", f"manifest.json 解析失败：{e}")
            return

        exe_path = Path(manifest.get("input_exe", ""))
        if not exe_path.exists():
            exe = filedialog.askopenfilename(
                title="找不到 manifest 记录的原始 EXE，请手动选择原始 EXE",
                filetypes=[("Executable", "*.exe"), ("All files", "*.*")],
            )
            if not exe:
                return
            exe_path = Path(exe)

        out_exe = filedialog.asksaveasfilename(
            title="选择输出 EXE（必须与原始 EXE 不同名）",
            defaultextension=".exe",
            filetypes=[("Executable", "*.exe"), ("All files", "*.*")],
            initialfile=f"{exe_path.stem}_patched.exe",
        )
        if not out_exe:
            return

        enc_in = self.var_enc_in.get().strip() or "cp932"
        enc_out = self.var_enc_out.get().strip() or "cp936"
        try:
            write_dfm_back_to_exe(
                exe_path,
                work_dir=work_dir_path,
                output_exe=Path(out_exe),
                encoding_in_for_hash=enc_in,
                encoding_out=enc_out,
            )
        except Exception as e:
            messagebox.showerror("写入失败", str(e))
            return
        self._log(f"[写入完成] 输出 EXE：{out_exe}")
        messagebox.showinfo("完成", f"写入完成：\n{out_exe}")

    def on_export_bin(self) -> None:
        work_dir = filedialog.askdirectory(title="选择工作目录（包含 manifest.json）")
        if not work_dir:
            return
        work_dir_path = Path(work_dir)
        manifest_path = work_dir_path / "manifest.json"
        if not manifest_path.exists():
            messagebox.showerror("导出BIN失败", f"找不到 manifest.json：{manifest_path}")
            return
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as e:
            messagebox.showerror("导出BIN失败", f"manifest.json 解析失败：{e}")
            return

        out_dir = filedialog.askdirectory(title="选择 BIN 输出目录")
        if not out_dir:
            return
        out_dir_path = Path(out_dir)
        out_dir_path.mkdir(parents=True, exist_ok=True)

        enc_in = self.var_enc_in.get().strip() or "cp932"
        enc_out = self.var_enc_out.get().strip() or "cp936"

        bin_manifest: list[dict[str, Any]] = []
        ok = 0
        for res in manifest.get("resources", []):
            dfm_text_rel = res["dfm_text"]
            dfm_text_path = (work_dir_path / dfm_text_rel).resolve()
            if not dfm_text_path.exists():
                continue
            text = dfm_text_path.read_text(encoding="utf-8")
            root = dfm_text_to_component(text, encoding_in_for_hash=enc_in)
            b = component_to_dfm_binary(root, encoding_out=enc_out)

            stem = safe_filename(Path(dfm_text_rel).stem)
            out_bin = out_dir_path / f"{stem}.bin"
            out_bin.write_bytes(b)
            ok += 1
            bin_manifest.append(
                {
                    "bin": str(out_bin.name),
                    "name": res["name"],
                    "lang": res["lang"],
                    "root": res.get("root", {}),
                }
            )

        (out_dir_path / "bin_manifest.json").write_text(
            json.dumps(
                {
                    "tool": "konohana_dfm_tool",
                    "version": 1,
                    "encoding_in_for_hash": enc_in,
                    "encoding_out": enc_out,
                    "items": bin_manifest,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )

        self._log(f"[导出BIN完成] 数量：{ok} 目录：{out_dir_path}")
        messagebox.showinfo("完成", f"导出BIN完成：\n{out_dir_path}\n数量：{ok}")


def main() -> int:
    if os.name != "nt":
        print("此脚本只支持 Windows（需要 Win32 资源 API）。", file=sys.stderr)
        return 2
    app = App()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
