from __future__ import annotations

import ast
import os
import shutil
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


SCRIPT_HEADER_SIZE = 0x40
TEXT_HEADER_SIZE = 0x30
KEY_OFFSET = 0x30
KEY_SIZE = 0x10
SECTOR_SIZE = 0x800


def call(name: str, *args: object) -> str:
    return f"{name}(" + ", ".join(format_arg(x) for x in args) + ")"


def format_arg(value: object) -> str:
    if isinstance(value, str):
        return f'"{value}"'
    return str(value)


def u16(data: bytes, off: int) -> int:
    return data[off] | (data[off + 1] << 8)


def s16(data: bytes, off: int) -> int:
    value = u16(data, off)
    return value - 0x10000 if value & 0x8000 else value


def text(data: bytes, encoding: str) -> str:
    if data.endswith(b"\x00"):
        data = data[:-1]
    return data.decode(encoding, errors="ignore").replace("\r", "\\r").replace("\n", "\\n")


def header_text(chunk: bytes, encoding: str) -> str | None:
    raw = chunk[:TEXT_HEADER_SIZE]
    if not any(raw):
        return None
    head = raw.split(b"\x00", 1)[0]
    if not head:
        return None
    try:
        return head.decode(encoding)
    except Exception:
        return None


def header_raw_needed(chunk: bytes, encoding: str) -> bool:
    raw = chunk[:TEXT_HEADER_SIZE]
    if not any(raw):
        return False
    return header_text(chunk, encoding) is None


def decrypt(chunk: bytes) -> bytes:
    if len(chunk) < SCRIPT_HEADER_SIZE:
        return chunk
    key = chunk[KEY_OFFSET : KEY_OFFSET + KEY_SIZE]
    out = bytearray(chunk)
    for i in range(SCRIPT_HEADER_SIZE, len(out)):
        out[i] = (out[i] - key[(i - SCRIPT_HEADER_SIZE) & 0xF]) & 0xFF
    return bytes(out)


def trim_decrypted_padding(script: bytes, original_chunk: bytes) -> bytes:
    if len(script) < SCRIPT_HEADER_SIZE or len(original_chunk) < SCRIPT_HEADER_SIZE:
        return script
    key = original_chunk[KEY_OFFSET : KEY_OFFSET + KEY_SIZE]
    end = len(script)
    while end > SCRIPT_HEADER_SIZE:
        idx = (end - 1 - SCRIPT_HEADER_SIZE) & 0xF
        if script[end - 1] != ((-key[idx]) & 0xFF):
            break
        end -= 1
    return script[:end]


def skip_debug(script: bytes, start: int = SCRIPT_HEADER_SIZE) -> tuple[int, list[str]]:
    if start >= len(script) or script[start] < 0xE0:
        return start, []
    lines: list[str] = []
    p = start
    step = {0xE0: 3, 0xE1: 3, 0xE2: 2, 0xE3: 3, 0xE4: 2, 0xE5: 3, 0xE6: 0x12, 0xE7: 3}
    while p < len(script):
        op = script[p]
        if op == 0xF2:
            lines.append(call("debug_end"))
            return p + 1, lines
        size = step.get(op)
        if size is None:
            return start, [call("error_debug_unknown_opcode", f"0x{op:02X}", f"0x{p:X}")]
        lines.append(call("debug_op", f"0x{op:02X}", script[p + 1 : p + size].hex()))
        p += size
    return start, lines


@dataclass(frozen=True)
class SetupResult:
    end: int | None
    lines: list[str]
    ok: bool


def parse_setup(script: bytes) -> SetupResult:
    p = SCRIPT_HEADER_SIZE
    limit = min(len(script), SCRIPT_HEADER_SIZE + 0x400)
    lines: list[str] = []
    while p < limit:
        op = script[p]
        if op == 0xF0:
            lines.append(call("setup_end"))
            return SetupResult(p + 1, lines, True)
        if op in (0x01, 0x02) and p + 5 <= len(script):
            slot = script[p + 1]
            no = script[p + 4] + 100 * (script[p + 2] + (script[p + 3] << 8))
            lines.append(call("setup_cbd" if op == 0x01 else "setup_bg", slot, no))
            p += 5
            continue
        if op == 0x03 and p + 2 <= len(script):
            n = script[p + 1]
            if p + 2 + n > len(script):
                break
            lines.append(call("setup_bg_init", script[p + 2 : p + 2 + n].hex()))
            p += 2 + n
            continue
        if op in (0x04, 0x05, 0x06) and p + 3 <= len(script):
            name = {0x04: "voc", 0x05: "mbg", 0x06: "snd"}[op]
            lines.append(call(f"setup_{name}", u16(script, p + 1)))
            p += 3
            continue
        lines.append(call("error_setup_unknown_opcode", f"0x{op:02X}", f"0x{p:X}"))
        return SetupResult(None, lines, False)
    return SetupResult(None, lines, False)


@dataclass(frozen=True)
class Op:
    name: str
    size: int | None
    kind: str = "raw"


@dataclass(frozen=True)
class Cmd:
    offset: int
    size: int
    text: str


@dataclass
class Node:
    name: str
    args: list[object]
    line_index: int = 0


@dataclass
class ChoiceNode:
    name: str
    args: list[object]
    items: list[list[object]]
    line_index: int = 0
    item_line_indices: list[int] | None = None


OPS: dict[int, Op] = {
    0x11: Op("chr_pose_wait", 3, "u8_u8"),
    0x12: Op("chr_flag", 2, "u8"),
    0x13: Op("bg_scroll", None, "bg_scroll"),
    0x14: Op("screen_reset", 1),
    0x15: Op("bg_set_pos3", 7, "bytes"),
    0x16: Op("fade_type1", 2),
    0x17: Op("fade_type2", 2),
    0x18: Op("screen_fx0", 1),
    0x19: Op("screen_fx1", 1),
    0x1A: Op("set_color1", 2, "u8"),
    0x1B: Op("set_env_color", 4),
    0x1C: Op("bglist_wait", None, "blob_len8"),
    0x1D: Op("bg_move_wait", 3, "u8_u8"),
    0x1E: Op("chr_effect", 2, "u8"),
    0x1F: Op("snow_flag", 2, "u8"),
    0x20: Op("mbg_name", None, "name1"),
    0x21: Op("mbg_clear", 1),
    0x22: Op("chr_ctrl_22", 2, "u8"),
    0x23: Op("fade_type3", 2),
    0x24: Op("fade_type4", 2),
    0x25: Op("screen_fx2", 1),
    0x26: Op("screen_fx3", 1),
    0x27: Op("snow_ctrl", 2, "u8"),
    0x28: Op("bg_name", None, "bg_name"),
    0x29: Op("screen_reset_arg", 2),
    0x41: Op("text", None, "text"),
    0x42: Op("choice", None, "choice42"),
    0x43: Op("choice_simple", None, "choice43"),
    0x44: Op("ctrl_44", 2, "u8"),
    0x45: Op("sys_45", 2, "u8"),
    0x46: Op("sys_46", 2, "u8"),
    0x47: Op("text_wait", None, "text"),
    0x61: Op("jump_rel", 3, "jump"),
    0x62: Op("wait1", 3, "wait"),
    0x63: Op("wait_input", 3, "wait_input"),
    0x64: Op("wait3", 1),
    0x65: Op("wait7", 1),
    0x66: Op("wait8", 1),
    0x67: Op("if_weekday", 6, "bytes"),
    0x68: Op("if_gametime", 5, "if_gametime"),
    0x69: Op("sys_69", 3),
    0x6A: Op("sys_6A", 1),
    0x6B: Op("sys_6B", 1),
    0x6C: Op("sys_6C", 1),
    0x6D: Op("if_chrno", 4, "if_chrno"),
    0x6E: Op("if_weekmask", 4, "if_weekmask"),
    0x6F: Op("if_gamepoint_eq", 5, "if_gamepoint"),
    0x70: Op("onkey_jump", 3, "jump"),
    0x71: Op("wait2", 3, "wait"),
    0x81: Op("flag_set_81", 3, "u8_u8"),
    0x82: Op("flag_jump_82", 5, "bytes"),
    0x83: Op("gamecache_set", 3, "u8_u8"),
    0x84: Op("chr_delta", 2, "u8"),
    0x85: Op("time_add", 2),
    0x86: Op("time_set", 3, "u8_u8"),
    0x87: Op("blob16", 0x12, "bytes"),
    0x88: Op("gamepoint_set", 3, "u8_u8"),
    0x89: Op("time_total_set", 3, "u8_u8"),
    0xA1: Op("voice_set", 2, "u8"),
    0xA2: Op("sys_a2", 2, "u8"),
    0xA3: Op("bgm_stop", 1),
    0xA4: Op("bgm_cmd1", 2, "u8"),
    0xA5: Op("bgm_cmd0", 1),
    0xA6: Op("bgm_play", 2, "u8"),
    0xA7: Op("sys_a7", 1),
    0xA8: Op("sys_a8", 2),
    0xA9: Op("bgm_cmdB", 2, "u8"),
    0xAA: Op("bgm_cmdC", 2, "u8"),
    0xAB: Op("bgm_wait_load", 3, "u8_u8"),
    0xAC: Op("sys_ac", 3),
    0xAD: Op("sys_ad", 3),
    0xC1: Op("day_change", 2, "u8"),
    0xC2: Op("return_wait_neg1", 1),
    0xC3: Op("return_wait_neg2", 1),
    0xC4: Op("sys_c4", 1),
    0xC5: Op("sys_c5", 8, "bytes"),
    0xC6: Op("sys_c6", 2, "u8"),
    0xC7: Op("flag_jump_c7", 5, "bytes"),
}


def parse_op(script: bytes, p: int, encoding: str) -> tuple[str, int]:
    op = script[p]
    spec = OPS.get(op)
    if spec is None:
        raise ValueError(f"unknown opcode 0x{op:02X} @0x{p:X}")
    kind = spec.kind
    if spec.name == "fade_type1":
        return call("fade_type1", script[p + 1]), 2
    if spec.name == "fade_type2":
        return call("fade_type2", script[p + 1]), 2
    if spec.name == "fade_type3":
        return call("fade_type3", script[p + 1]), 2
    if spec.name == "fade_type4":
        return call("fade_type4", script[p + 1]), 2
    if spec.name == "set_env_color":
        return call("set_env_color", script[p + 1], script[p + 2], script[p + 3]), 4
    if spec.name == "sys_ad":
        return call("sys_ad", script[p + 1], script[p + 2]), 3
    if spec.name == "sys_ac":
        return call("sys_ac", script[p + 1], script[p + 2]), 3
    if spec.name == "sys_69":
        return call("sys_69", script[p + 1], script[p + 2]), 3
    if kind == "raw":
        return call(spec.name), spec.size or 1
    if kind == "u8":
        return call(spec.name, script[p + 1]), spec.size or 1
    if kind == "u8_u8":
        return call(spec.name, script[p + 1], script[p + 2]), spec.size or 1
    if kind == "bytes":
        return call(spec.name, *script[p + 1 : p + (spec.size or 1)]), spec.size or 1
    if kind == "jump":
        return call(spec.name, s16(script, p + 1)), spec.size or 1
    if kind == "wait":
        return call(spec.name, u16(script, p + 1)), spec.size or 1
    if kind == "wait_input":
        return call("wait_input", u16(script, p + 1)), spec.size or 1
    if kind == "text":
        flags = script[p + 1]
        aux = script[p + 2]
        n = script[p + 3]
        return call(spec.name, (flags >> 6) & 3, aux, text(script[p + 4 : p + 4 + n], encoding)), 4 + n
    if kind == "choice42":
        flags = script[p + 1]
        aux = script[p + 2]
        n = script[p + 3]
        cur = p + 4 + n
        lines = [call("choice", (flags >> 6) & 3, aux, flags & 0x3F, text(script[p + 4 : p + 4 + n], encoding))]
        for i in range(flags & 0x3F):
            if cur >= len(script):
                lines.append(call("error_choice_item_truncated", i))
                return "\n".join(lines), max(cur - p, 1)
            head = script[cur]
            m = ((head >> 6) & 3) + 1
            size = head & 0x3F
            if cur + 1 + size + 2 > len(script):
                lines.append(call("error_choice_item_truncated", i))
                return "\n".join(lines), max(len(script) - p, 1)
            lines.append(call("choice_item", i, m, f"0x{u16(script, cur + 1 + size):04X}", text(script[cur + 1 : cur + 1 + size], encoding)))
            cur += 1 + size + 2
        return "\n".join(lines), cur - p
    if kind == "choice43":
        count = script[p + 1] & 0x7F
        cur = p + 2
        lines = [call("choice_simple", count)]
        for i in range(count):
            if cur >= len(script):
                lines.append(call("error_choice_item_truncated", i))
                return "\n".join(lines), max(cur - p, 1)
            size = script[cur]
            if cur + 1 + size + 2 > len(script):
                lines.append(call("error_choice_item_truncated", i))
                return "\n".join(lines), max(len(script) - p, 1)
            lines.append(call("choice_item", i, f"0x{u16(script, cur + 1 + size):04X}", text(script[cur + 1 : cur + 1 + size], encoding)))
            cur += 1 + size + 2
        return "\n".join(lines), cur - p
    if kind == "bg_scroll":
        n = script[p + 5] & 0x7F
        flag = script[p + 5] >> 7
        return call("bg_scroll", u16(script, p + 1), u16(script, p + 3), flag, text(script[p + 6 : p + 6 + n], encoding) if n else ""), 6 + n
    if kind == "name1":
        n = script[p + 1] & 0x7F
        flag = script[p + 1] >> 7
        return call("mbg_name", flag, text(script[p + 2 : p + 2 + n], encoding) if n else ""), 2 + n
    if kind == "bg_name":
        n = script[p + 6] & 0x7F
        flag = script[p + 6] >> 7
        return call("bg_name", script[p + 5], u16(script, p + 1), u16(script, p + 3), flag, text(script[p + 7 : p + 7 + n], encoding) if n else ""), 7 + n
    if kind == "blob_len8":
        n = script[p + 1]
        return call(spec.name, n, script[p + 2 : p + 2 + n].hex()), 2 + n
    if kind == "if_gametime":
        packed = script[p + 1]
        return call("if_gametime", (packed >> 6) & 3, f"{script[p + 2]:02d}:{packed & 0x3F:02d}", s16(script, p + 3)), spec.size or 1
    if kind == "if_chrno":
        raw = script[p + 1]
        return call("if_chrno", (raw >> 7) & 1, raw & 0x7F, s16(script, p + 2)), spec.size or 1
    if kind == "if_weekmask":
        raw = script[p + 1]
        return call("if_weekmask", (raw >> 7) & 1, raw & 0x7F, s16(script, p + 2)), spec.size or 1
    if kind == "if_gamepoint":
        return call("if_gamepoint_eq", u16(script, p + 1), s16(script, p + 3)), spec.size or 1
    return call(spec.name), spec.size or 1


def signed_cmd_delta(target_index: int, current_index: int) -> str:
    delta = target_index - current_index
    return f"{delta:+d}"


def target_cmd(base: int, rel: int, start_to_index: dict[int, int], current_index: int) -> str:
    target = base + rel
    target_index = start_to_index.get(target)
    if target_index is None:
        return f"byte{rel:+d}"
    return signed_cmd_delta(target_index, current_index)


def render_op(script: bytes, p: int, encoding: str, start_to_index: dict[int, int], current_index: int) -> str:
    op = script[p]
    spec = OPS[op]
    kind = spec.kind
    if kind == "jump":
        base = p + 1
        rel = s16(script, p + 1)
        if op == 0x70 and rel == 0:
            return call("onkey_jump_clear")
        return call(spec.name, target_cmd(base, rel, start_to_index, current_index))
    if kind == "if_gametime":
        packed = script[p + 1]
        return call("if_gametime", (packed >> 6) & 3, f"{script[p + 2]:02d}:{packed & 0x3F:02d}", target_cmd(p + 3, s16(script, p + 3), start_to_index, current_index))
    if kind == "if_chrno":
        raw = script[p + 1]
        return call("if_chrno", (raw >> 7) & 1, raw & 0x7F, target_cmd(p + 2, s16(script, p + 2), start_to_index, current_index))
    if kind == "if_weekmask":
        raw = script[p + 1]
        return call("if_weekmask", (raw >> 7) & 1, raw & 0x7F, target_cmd(p + 2, s16(script, p + 2), start_to_index, current_index))
    if kind == "if_gamepoint":
        return call("if_gamepoint_eq", u16(script, p + 1), target_cmd(p + 3, s16(script, p + 3), start_to_index, current_index))
    if kind == "choice42":
        flags = script[p + 1]
        aux = script[p + 2]
        n = script[p + 3]
        cur = p + 4 + n
        lines = [call("choice", (flags >> 6) & 3, aux, flags & 0x3F, text(script[p + 4 : p + 4 + n], encoding))]
        for i in range(flags & 0x3F):
            if cur >= len(script):
                lines.append(call("error_choice_item_truncated", i))
                return "\n".join(lines)
            head = script[cur]
            mode = ((head >> 6) & 3) + 1
            size = head & 0x3F
            if cur + 1 + size + 2 > len(script):
                lines.append(call("error_choice_item_truncated", i))
                return "\n".join(lines)
            jump_off = cur + 1 + size
            lines.append(call("choice_item", i, mode, target_cmd(jump_off, s16(script, jump_off), start_to_index, current_index), text(script[cur + 1 : cur + 1 + size], encoding)))
            cur += 1 + size + 2
        return "\n".join(lines)
    if kind == "choice43":
        count = script[p + 1] & 0x7F
        cur = p + 2
        lines = [call("choice_simple", count)]
        for i in range(count):
            if cur >= len(script):
                lines.append(call("error_choice_item_truncated", i))
                return "\n".join(lines)
            size = script[cur]
            if cur + 1 + size + 2 > len(script):
                lines.append(call("error_choice_item_truncated", i))
                return "\n".join(lines)
            jump_off = cur + 1 + size
            lines.append(call("choice_item", i, target_cmd(jump_off, s16(script, jump_off), start_to_index, current_index), text(script[cur + 1 : cur + 1 + size], encoding)))
            cur += 1 + size + 2
        return "\n".join(lines)
    text_line, _ = parse_op(script, p, encoding)
    return text_line


def scan_main(script: bytes, start: int, encoding: str) -> list[tuple[int, int]]:
    items: list[tuple[int, int]] = []
    p = start
    while p < len(script):
        if not any(script[p:]):
            break
        if script[p] == 0xF1:
            items.append((p, 1))
            p += 1
            continue
        try:
            _, size = parse_op(script, p, encoding)
        except Exception:
            break
        size = max(size, 1)
        items.append((p, size))
        p += size
    return items


def cmd_successors(script: bytes, p: int, size: int, next_start: int | None) -> list[int]:
    op = script[p]
    if op == 0xF1:
        return []
    spec = OPS.get(op)
    if spec is None:
        return []
    kind = spec.kind
    if spec.name in {"return_wait_neg1", "return_wait_neg2", "sys_c4", "sys_c5"}:
        return []
    if kind == "jump":
        if op == 0x70:
            out: list[int] = [next_start] if next_start is not None else []
            rel = s16(script, p + 1)
            if rel:
                out.append(p + 1 + rel)
            return out
        return [p + 1 + s16(script, p + 1)]
    if kind == "if_gametime":
        out = [p + 3 + s16(script, p + 3)]
        if next_start is not None:
            out.append(next_start)
        return out
    if kind == "if_chrno":
        out = [p + 2 + s16(script, p + 2)]
        if next_start is not None:
            out.append(next_start)
        return out
    if kind == "if_weekmask":
        out = [p + 2 + s16(script, p + 2)]
        if next_start is not None:
            out.append(next_start)
        return out
    if kind == "if_gamepoint":
        out = [p + 3 + s16(script, p + 3)]
        if next_start is not None:
            out.append(next_start)
        return out
    if kind == "choice42":
        flags = script[p + 1] & 0x3F
        n = script[p + 3]
        cur = p + 4 + n
        out: list[int] = []
        for _ in range(flags):
            head = script[cur]
            item_size = head & 0x3F
            jump_off = cur + 1 + item_size
            out.append(jump_off + s16(script, jump_off))
            cur += 1 + item_size + 2
        return out
    if kind == "choice43":
        count = script[p + 1] & 0x7F
        cur = p + 2
        out: list[int] = []
        for _ in range(count):
            item_size = script[cur]
            jump_off = cur + 1 + item_size
            out.append(jump_off + s16(script, jump_off))
            cur += 1 + item_size + 2
        return out
    return [next_start] if next_start is not None else []


def parse_main(script: bytes, start: int, encoding: str) -> list[str]:
    scanned = scan_main(script, start, encoding)
    if not scanned:
        return []
    starts = [off for off, _size in scanned]
    start_to_index = {off: idx for idx, off in enumerate(starts)}
    lines: list[str] = []
    for current_index, p in enumerate(starts):
        if script[p] == 0xF1:
            lines.append(call("end"))
            continue
        try:
            line = render_op(script, p, encoding, start_to_index, current_index)
        except Exception as exc:
            lines.append(call("error_parse", f"0x{script[p]:02X}", f"0x{p:X}", str(exc)))
            break
        lines.extend(line.splitlines())
    end = max(off + size for off, size in scanned)
    tail = script[end:].rstrip(b"\x00")
    if tail:
        lines.append(call("raw_tail", tail.hex()))
    return lines


@dataclass(frozen=True)
class Fdb:
    data: bytes

    @property
    def dir_offsets(self) -> list[int]:
        return [int.from_bytes(self.data[i : i + 4], "little") for i in range(0, 60 * 4, 4)]

    def section_end(self, off: int) -> int:
        tail = [x for x in self.dir_offsets if x > off]
        return min(tail) if tail else len(self.data)

    def scr_entries(self, group: int) -> list[tuple[int, int]]:
        off = self.dir_offsets[25 + group]
        raw = self.data[off : self.section_end(off)]
        return [(int.from_bytes(raw[i : i + 4], "little"), int.from_bytes(raw[i + 4 : i + 8], "little")) for i in range(0, len(raw) // 8 * 8, 8)]

    def eve_map(self, group: int) -> list[int]:
        off = self.dir_offsets[51 + group]
        raw = self.data[off : self.section_end(off)]
        return [int.from_bytes(raw[i : i + 2], "little") for i in range(0, len(raw), 2)]


def decompile_chunk(chunk: bytes, encoding: str) -> str:
    if not chunk:
        return "\n".join([
            "[header]",
            "[setup]",
            call("none"),
            "",
            "[main]",
            call("empty_chunk"),
        ])
    script = trim_decrypted_padding(decrypt(chunk), chunk)
    debug_start, debug_lines = skip_debug(script)
    synth = b"\x00" * SCRIPT_HEADER_SIZE + script[debug_start:]
    setup = parse_setup(synth)
    out = ["[header]"]
    title = header_text(chunk, encoding)
    if title is not None:
        out.append(call("title", title))
    elif header_raw_needed(chunk, encoding):
        out.append(call("raw_header", chunk[:TEXT_HEADER_SIZE].hex()))
    key_hex = chunk[KEY_OFFSET:KEY_OFFSET + KEY_SIZE].hex()
    if any(chunk[KEY_OFFSET:KEY_OFFSET + KEY_SIZE]):
        out.append(call("key", key_hex))
    if debug_lines:
        out += ["", "[debug]", *debug_lines]
    out += ["", "[setup]", *setup.lines, "", "[main]"]
    if setup.end is None:
        out.append(call("error_setup_parse_failed"))
    else:
        out.extend(parse_main(synth, setup.end, encoding))
    return "\n".join(out)


def write_text(path: Path, data: str) -> None:
    path.write_text(data, encoding="utf-8-sig")


def write_list_xml(path: Path, rows: list[dict[str, str]]) -> None:
    root = ET.Element("scn")
    for row in rows:
        ET.SubElement(root, "item", row)
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def read_list_xml(path: Path) -> dict[tuple[int, int], Path]:
    if not path.exists():
        return {}
    root = ET.parse(path).getroot()
    out: dict[tuple[int, int], Path] = {}
    for item in root.findall("item"):
        group_s = item.get("g")
        real_s = item.get("r")
        file_s = item.get("f")
        if group_s is None or real_s is None or not file_s:
            continue
        out[(int(group_s), int(real_s))] = Path(file_s)
    return out


def encrypt(chunk: bytes) -> bytes:
    if len(chunk) < SCRIPT_HEADER_SIZE:
        return chunk
    key = chunk[KEY_OFFSET : KEY_OFFSET + KEY_SIZE]
    out = bytearray(chunk)
    for i in range(SCRIPT_HEADER_SIZE, len(out)):
        out[i] = (out[i] + key[(i - SCRIPT_HEADER_SIZE) & 0xF]) & 0xFF
    return bytes(out)


def parse_value(node: ast.AST) -> object:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub) and isinstance(node.operand, ast.Constant):
        return -node.operand.value
    raise ValueError("unsupported value")


def parse_call_line(line: str) -> Node:
    expr = ast.parse(line.strip(), mode="eval").body
    if not isinstance(expr, ast.Call) or not isinstance(expr.func, ast.Name):
        raise ValueError(f"bad line: {line}")
    return Node(expr.func.id, [parse_value(x) for x in expr.args], 0)


def load_sections(path: Path) -> dict[str, list[str]]:
    current = ""
    out: dict[str, list[str]] = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].lower()
            out.setdefault(current, [])
            continue
        out.setdefault(current, []).append(line)
    return out


def compile_setup(lines: list[str]) -> bytes:
    out = bytearray()
    for line in lines:
        node = parse_call_line(line)
        if node.name == "none":
            continue
        if node.name == "setup_end":
            out.append(0xF0)
            continue
        if node.name == "setup_cbd":
            slot, no = int(node.args[0]), int(node.args[1])
            base = no // 100
            out += bytes((0x01, slot, base & 0xFF, (base >> 8) & 0xFF, no % 100))
            continue
        if node.name == "setup_bg":
            slot, no = int(node.args[0]), int(node.args[1])
            base = no // 100
            out += bytes((0x02, slot, base & 0xFF, (base >> 8) & 0xFF, no % 100))
            continue
        if node.name == "setup_bg_init":
            blob = bytes.fromhex(str(node.args[0]))
            out += bytes((0x03, len(blob))) + blob
            continue
        if node.name in ("setup_voc", "setup_mbg", "setup_snd"):
            op = {"setup_voc": 0x04, "setup_mbg": 0x05, "setup_snd": 0x06}[node.name]
            no = int(node.args[0])
            out += bytes((op, no & 0xFF, (no >> 8) & 0xFF))
            continue
        raise ValueError(f"unsupported setup op: {node.name}")
    if not out or out[-1] != 0xF0:
        out.append(0xF0)
    return bytes(out)


def enc_rel(delta: str | int, current: int, offsets: list[int], base_shift: int) -> bytes:
    if isinstance(delta, str):
        n = int(delta)
    else:
        n = int(delta)
    target = current + n
    rel = offsets[target] - (offsets[current] + base_shift)
    return int(rel).to_bytes(2, "little", signed=True)


def main_nodes(lines: list[str]) -> list[Node | ChoiceNode]:
    out: list[Node | ChoiceNode] = []
    i = 0
    while i < len(lines):
        node = parse_call_line(lines[i])
        node.line_index = i
        if node.name in ("choice", "choice_simple"):
            items: list[list[object]] = []
            item_line_indices: list[int] = []
            i += 1
            while i < len(lines):
                peek = parse_call_line(lines[i])
                if peek.name != "choice_item":
                    break
                items.append(peek.args)
                item_line_indices.append(i)
                i += 1
            out.append(ChoiceNode(node.name, node.args, items, node.line_index, item_line_indices))
            continue
        out.append(node)
        i += 1
    return out


def cmd_size(node: Node | ChoiceNode, encoding: str) -> int:
    if isinstance(node, ChoiceNode):
        if node.name == "choice":
            text_len = len(str(node.args[3]).encode(encoding)) + 1
            size = 4 + text_len
            for item in node.items:
                item_len = len(str(item[3]).encode(encoding)) + 1
                size += 1 + item_len + 2
            return size
        size = 2
        for item in node.items:
            item_len = len(str(item[2]).encode(encoding)) + 1
            size += 1 + item_len + 2
        return size
    fixed = {
        "chr_pose_wait": 3, "chr_flag": 2, "screen_reset": 1, "bg_set_pos3": 7,
        "screen_fx0": 1, "screen_fx1": 1, "set_color1": 2,
        "bg_move_wait": 3, "chr_effect": 2, "snow_flag": 2, "mbg_clear": 1, "chr_ctrl_22": 2,
        "fade_type3": 2, "fade_type4": 2, "screen_fx2": 1, "screen_fx3": 1, "snow_ctrl": 2,
        "screen_reset_arg": 2, "ctrl_44": 2, "sys_45": 2, "sys_46": 2, "wait3": 1, "wait7": 1,
        "wait8": 1, "if_weekday": 6, "sys_6A": 1, "sys_6B": 1, "sys_6C": 1,
        "wait2": 3, "flag_set_81": 3, "flag_jump_82": 5, "gamecache_set": 3, "chr_delta": 2,
        "time_add": 2, "time_set": 3, "blob16": 0x12, "gamepoint_set": 3, "time_total_set": 3,
        "voice_set": 2, "sys_a2": 2, "bgm_stop": 1, "bgm_cmd1": 2, "bgm_cmd0": 1, "bgm_play": 2,
        "sys_a7": 1, "sys_a8": 2, "bgm_cmdB": 2, "bgm_cmdC": 2, "bgm_wait_load": 3,
        "day_change": 2, "return_wait_neg1": 1, "return_wait_neg2": 1, "onkey_jump_clear": 3, "sys_c4": 1,
        "sys_c5": 8, "sys_c6": 2, "flag_jump_c7": 5, "end": 1,
    }
    if node.name in fixed:
        return fixed[node.name]
    if node.name in ("fade_type1", "fade_type2", "fade_type3", "fade_type4", "set_env_color", "sys_69", "sys_ac", "sys_ad"):
        return {"fade_type1": 2, "fade_type2": 2, "fade_type3": 2, "fade_type4": 2, "set_env_color": 4, "sys_69": 3, "sys_ac": 3, "sys_ad": 3}[node.name]
    if node.name in ("jump_rel", "onkey_jump", "if_gametime", "if_chrno", "if_weekmask", "if_gamepoint_eq", "wait1", "wait_input"):
        return {"jump_rel": 3, "onkey_jump": 3, "if_gametime": 5, "if_chrno": 4, "if_weekmask": 4, "if_gamepoint_eq": 5, "wait1": 3, "wait_input": 3}[node.name]
    if node.name in ("bglist_wait",):
        return 2 + int(node.args[0])
    if node.name in ("bg_scroll",):
        return 6 + len(str(node.args[3]).encode(encoding)) + 1
    if node.name in ("mbg_name",):
        return 2 + len(str(node.args[1]).encode(encoding)) + 1
    if node.name in ("bg_name",):
        return 7 + len(str(node.args[4]).encode(encoding)) + 1
    if node.name in ("text", "text_wait"):
        return 4 + len(str(node.args[2]).encode(encoding)) + 1
    raise ValueError(f"unsupported op size: {node.name}")


def compile_main(lines: list[str], encoding: str) -> bytes:
    nodes = main_nodes(lines)
    raw_tail = b""
    filtered: list[Node | ChoiceNode] = []
    for node in nodes:
        if not isinstance(node, ChoiceNode) and node.name == "raw_tail":
            raw_tail += bytes.fromhex(str(node.args[0]))
            continue
        filtered.append(node)
    nodes = filtered
    offsets: list[int] = []
    line_cmd_offsets: dict[int, int] = {}
    item_base_offsets: dict[int, int] = {}
    pos = 0
    for node in nodes:
        offsets.append(pos)
        line_cmd_offsets[node.line_index] = pos
        if isinstance(node, ChoiceNode):
            if node.name == "choice":
                prompt = str(node.args[3])
                cur = pos + 4 + len(prompt.encode(encoding)) + 1
                for item, line_index in zip(node.items, node.item_line_indices or []):
                    line_cmd_offsets[line_index] = pos
                    item_text = str(item[3])
                    tb = item_text.encode(encoding) + b"\x00"
                    item_base_offsets[line_index] = cur + 1 + len(tb)
                    cur += 1 + len(tb) + 2
            else:
                cur = pos + 2
                for item, line_index in zip(node.items, node.item_line_indices or []):
                    line_cmd_offsets[line_index] = pos
                    item_text = str(item[2])
                    tb = item_text.encode(encoding) + b"\x00"
                    item_base_offsets[line_index] = cur + 1 + len(tb)
                    cur += 1 + len(tb) + 2
        pos += cmd_size(node, encoding)
    out = bytearray()
    for i, node in enumerate(nodes):
        if isinstance(node, ChoiceNode):
            if node.name == "choice":
                mode, aux, count, prompt = int(node.args[0]), int(node.args[1]), int(node.args[2]), str(node.args[3])
                blob = prompt.encode(encoding) + b"\x00"
                out += bytes((0x42, ((mode & 3) << 6) | (count & 0x3F), aux, len(blob)))
                out += blob
                for item, item_line_index in zip(node.items, node.item_line_indices or []):
                    idx, item_mode, delta, text_s = int(item[0]), int(item[1]), item[2], str(item[3])
                    _ = idx
                    tb = text_s.encode(encoding) + b"\x00"
                    out.append(((item_mode - 1) & 3) << 6 | len(tb))
                    out += tb
                    rel = offsets[i + int(delta)] - item_base_offsets[item_line_index]
                    out += int(rel).to_bytes(2, "little", signed=True)
                continue
            out += bytes((0x43, int(node.args[0]) & 0x7F))
            for item, item_line_index in zip(node.items, node.item_line_indices or []):
                idx, delta, text_s = int(item[0]), item[1], str(item[2])
                _ = idx
                tb = text_s.encode(encoding) + b"\x00"
                out.append(len(tb))
                out += tb
                rel = offsets[i + int(delta)] - item_base_offsets[item_line_index]
                out += int(rel).to_bytes(2, "little", signed=True)
            continue
        n = node.name
        a = node.args
        if n == "end":
            out.append(0xF1)
        elif n == "jump_rel":
            out.append(0x61); out += enc_rel(a[0], i, offsets, 1)
        elif n == "onkey_jump":
            out.append(0x70); out += enc_rel(a[0], i, offsets, 1)
        elif n == "onkey_jump_clear":
            out += b"\x70\x00\x00"
        elif n == "wait1":
            c = int(a[0]); out += bytes((0x62, c & 0xFF, (c >> 8) & 0xFF))
        elif n == "wait2":
            c = int(a[0]); out += bytes((0x71, c & 0xFF, (c >> 8) & 0xFF))
        elif n == "wait_input":
            c = int(a[0]); out += bytes((0x63, c & 0xFF, (c >> 8) & 0xFF))
        elif n in ("wait3", "wait7", "wait8"):
            out.append({"wait3": 0x64, "wait7": 0x65, "wait8": 0x66}[n])
        elif n == "ctrl_44":
            out += bytes((0x44, int(a[0])))
        elif n in ("text", "text_wait"):
            op = 0x41 if n == "text" else 0x47
            mode, aux, s = int(a[0]), int(a[1]), str(a[2])
            tb = s.encode(encoding) + b"\x00"
            out += bytes((op, (mode & 3) << 6, aux, len(tb))) + tb
        elif n == "bg_scroll":
            x, y, flag, s = int(a[0]), int(a[1]), int(a[2]), str(a[3])
            tb = s.encode(encoding) + b"\x00"
            out += bytes((0x13, x & 0xFF, (x >> 8) & 0xFF, y & 0xFF, (y >> 8) & 0xFF, ((flag & 1) << 7) | len(tb))) + tb
        elif n == "bg_set_pos3":
            vals = [int(x) for x in a[:6]]
            out += bytes((0x15, *vals))
        elif n == "fade_type1":
            out += bytes((0x16, int(a[0])))
        elif n == "fade_type2":
            out += bytes((0x17, int(a[0])))
        elif n == "fade_type3":
            out += bytes((0x23, int(a[0])))
        elif n == "fade_type4":
            out += bytes((0x24, int(a[0])))
        elif n == "set_env_color":
            out += bytes((0x1B, int(a[0]), int(a[1]), int(a[2])))
        elif n == "bglist_wait":
            blob = bytes.fromhex(str(a[1]))
            out += bytes((0x1C, int(a[0]))) + blob
        elif n == "bg_name":
            layer, x, y, flag, s = int(a[0]), int(a[1]), int(a[2]), int(a[3]), str(a[4])
            tb = s.encode(encoding) + b"\x00"
            out += bytes((0x28, x & 0xFF, (x >> 8) & 0xFF, y & 0xFF, (y >> 8) & 0xFF, layer, ((flag & 1) << 7) | len(tb))) + tb
        elif n == "mbg_name":
            flag, s = int(a[0]), str(a[1]); tb = s.encode(encoding) + b"\x00"
            out += bytes((0x20, ((flag & 1) << 7) | len(tb))) + tb
        elif n == "if_gametime":
            mode = int(a[0]); hh, mm = map(int, str(a[1]).split(":"))
            out += bytes((0x68, ((mode & 3) << 6) | (mm & 0x3F), hh)) + enc_rel(a[2], i, offsets, 3)
        elif n == "if_chrno":
            out += bytes((0x6D, ((int(a[0]) & 1) << 7) | (int(a[1]) & 0x7F))) + enc_rel(a[2], i, offsets, 2)
        elif n == "if_weekmask":
            out += bytes((0x6E, ((int(a[0]) & 1) << 7) | (int(a[1]) & 0x7F))) + enc_rel(a[2], i, offsets, 2)
        elif n == "if_gamepoint_eq":
            v = int(a[0]); out += bytes((0x6F, v & 0xFF, (v >> 8) & 0xFF)) + enc_rel(a[1], i, offsets, 3)
        elif n == "sys_ad":
            out += bytes((0xAD, int(a[0]), int(a[1])))
        elif n == "sys_ac":
            out += bytes((0xAC, int(a[0]), int(a[1])))
        elif n == "sys_69":
            out += bytes((0x69, int(a[0]), int(a[1])))
        elif n == "sys_a2":
            out += bytes((0xA2, int(a[0])))
        elif n == "bgm_cmd1":
            out += bytes((0xA4, int(a[0])))
        elif n == "bgm_cmdB":
            out += bytes((0xA9, int(a[0])))
        elif n == "bgm_cmdC":
            out += bytes((0xAA, int(a[0])))
        else:
            raw_map = {
                "chr_pose_wait": (0x11, 2), "chr_flag": (0x12, 1), "screen_reset": (0x14, 0),
                "screen_fx0": (0x18, 0),
                "screen_fx1": (0x19, 0), "set_color1": (0x1A, 1),
                "bg_move_wait": (0x1D, 2), "chr_effect": (0x1E, 1), "snow_flag": (0x1F, 1),
                "mbg_clear": (0x21, 0), "chr_ctrl_22": (0x22, 1), "screen_fx2": (0x25, 0), "screen_fx3": (0x26, 0),
                "snow_ctrl": (0x27, 1), "screen_reset_arg": (0x29, 1), "sys_45": (0x45, 1),
                "sys_46": (0x46, 1), "sys_6A": (0x6A, 0),
                "sys_6B": (0x6B, 0), "sys_6C": (0x6C, 0), "flag_set_81": (0x81, 2),
                "gamecache_set": (0x83, 2), "chr_delta": (0x84, 1),
                "time_add": (0x85, 1), "time_set": (0x86, 2), "blob16": (0x87, 17), "gamepoint_set": (0x88, 2),
                "time_total_set": (0x89, 2), "voice_set": (0xA1, 1), "bgm_stop": (0xA3, 0),
                "bgm_cmd0": (0xA5, 0), "bgm_play": (0xA6, 1), "sys_a7": (0xA7, 0),
                "sys_a8": (0xA8, 1), "bgm_wait_load": (0xAB, 2),
                "return_wait_neg1": (0xC2, 0),
                "return_wait_neg2": (0xC3, 0), "sys_c4": (0xC4, 0), "sys_c5": (0xC5, 7), "sys_c6": (0xC6, 1),
                "flag_jump_c7": (0xC7, 4),
            }
            if n not in raw_map:
                byte_ops = {"if_weekday": 0x67, "flag_jump_82": 0x82}
                if n in byte_ops:
                    out.append(byte_ops[n])
                    out += bytes(int(x) & 0xFF for x in a)
                    continue
                if n == "day_change":
                    out += bytes((0xC1, int(a[0])))
                    continue
                raise ValueError(f"unsupported encode op: {n}")
            op, argn = raw_map[n]
            out.append(op)
            for j in range(argn):
                out.append(int(a[j]) if j < len(a) else 0)
    return bytes(out) + raw_tail


def find_accessdb(root: Path) -> Path:
    path = root / "ACCESSDB.BIN"
    if not path.exists():
        raise FileNotFoundError(f"missing {path}")
    return path


def find_scr_dir(root: Path) -> Path:
    scr = root / "SCR"
    return scr if scr.exists() else root


def cmd_decompile(src_dir: Path, out_dir: Path, encoding: str = "cp932") -> int:
    accessdb = find_accessdb(src_dir)
    fdb = Fdb(accessdb.read_bytes())
    scr_dir = find_scr_dir(src_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(accessdb, out_dir / "ACCESSDB.BIN")
    list_rows: list[dict[str, str]] = []
    for group in range(9):
        src = scr_dir / f"scr{group}00.bin"
        if not src.exists():
            continue
        data = src.read_bytes()
        reverse: dict[int, list[int]] = {}
        for event_id, real_id in enumerate(fdb.eve_map(group)):
            reverse.setdefault(real_id, []).append(event_id)
        for real_id, (sector, size) in enumerate(fdb.scr_entries(group)):
            events = reverse.get(real_id)
            if not events:
                continue
            chunk = data[sector * SECTOR_SIZE : (sector + size) * SECTOR_SIZE]
            result = decompile_chunk(chunk, encoding)
            event_id = events[0]
            name = f"ev{group * 1000 + event_id:04d}.txt"
            write_text(out_dir / name, result)
            row = {
                "g": str(group),
                "e": str(group * 1000 + event_id),
                "r": str(real_id),
                "s": str(sector),
                "n": str(size),
                "f": name,
            }
            if len(events) > 1:
                row["alias"] = ",".join(str(group * 1000 + x) for x in events[1:])
            list_rows.append(row)
    write_list_xml(out_dir / "list.xml", list_rows)
    print(f"output={out_dir}")
    return 0


def cmd_encode(src_dir: Path, out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    accessdb = find_accessdb(src_dir)
    accessdb_out = out_dir / "ACCESSDB.BIN"
    shutil.copy2(accessdb, accessdb_out)
    scr_src = find_scr_dir(src_dir)
    scr_out = out_dir / "SCR"
    scr_out.mkdir(exist_ok=True)
    fdb = Fdb(accessdb.read_bytes())
    fdb_bytes = bytearray(accessdb.read_bytes())
    list_map = read_list_xml(src_dir / "list.xml")
    for group in range(9):
        src = scr_src / f"scr{group}00.bin"
        if src.exists():
            shutil.copy2(src, scr_out / src.name)
    for group in range(9):
        bin_path = scr_out / f"scr{group}00.bin"
        entries = fdb.scr_entries(group)
        data = bytearray()
        new_entries: list[tuple[int, int]] = []
        reverse: dict[int, int] = {}
        for event_id, real_id in enumerate(fdb.eve_map(group)):
            reverse.setdefault(real_id, event_id)
        if list_map:
            has_group_text = any((src_dir / rel).exists() for (g, _real_id), rel in list_map.items() if g == group)
        else:
            has_group_text = any((src_dir / f"ev{group * 1000 + event_id:04d}.txt").exists() for event_id in reverse.values())
        if not has_group_text:
            continue
        for real_id, old_entry in enumerate(entries):
            rel_txt = list_map.get((group, real_id))
            if rel_txt is not None:
                txt = src_dir / rel_txt
            else:
                event_id = reverse.get(real_id)
                txt = src_dir / f"ev{group * 1000 + event_id:04d}.txt" if event_id is not None else None
            if txt is None or not txt.exists():
                new_entries.append(old_entry)
                continue
            sections = load_sections(txt)
            main_lines = sections.get("main", [])
            if main_lines == [call("empty_chunk")]:
                new_entries.append(old_entry)
                continue
            header_lines = sections.get("header", [])
            header_text_value: str | None = None
            raw_header = b"\x00" * TEXT_HEADER_SIZE
            key = os.urandom(KEY_SIZE)
            for line in header_lines:
                node = parse_call_line(line)
                if node.name == "title":
                    header_text_value = str(node.args[0])
                elif node.name == "raw_header":
                    raw_header = bytes.fromhex(str(node.args[0]))[:TEXT_HEADER_SIZE].ljust(TEXT_HEADER_SIZE, b"\x00")
                if node.name == "key":
                    key = bytes.fromhex(str(node.args[0]))
            debug_lines = sections.get("debug", [])
            if not debug_lines or debug_lines == [call("none")]:
                debug = b""
            else:
                debug_buf = bytearray()
                for line in debug_lines:
                    node = parse_call_line(line)
                    if node.name == "debug_end":
                        debug_buf.append(0xF2)
                    elif node.name == "debug_op":
                        op = int(str(node.args[0]), 16)
                        payload = bytes.fromhex(str(node.args[1])) if len(node.args) > 1 else b""
                        if op in (0xE0, 0xE1, 0xE3, 0xE5, 0xE7):
                            debug_buf += bytes([op]) + payload.ljust(2, b"\x00")[:2]
                        elif op in (0xE2, 0xE4):
                            debug_buf += bytes([op]) + payload.ljust(1, b"\x00")[:1]
                        elif op == 0xE6:
                            debug_buf += bytes([op]) + payload.ljust(0x11, b"\x00")[:0x11]
                        else:
                            raise ValueError(f"unsupported debug op: 0x{op:02X}")
                    else:
                        raise ValueError(f"unsupported debug line: {node.name}")
                debug = bytes(debug_buf)
            setup = compile_setup(sections.get("setup", []))
            main = compile_main(main_lines, "cp932")
            plain = bytearray(b"\x00" * SCRIPT_HEADER_SIZE)
            if header_text_value is not None:
                raw_header = header_text_value.encode("cp932")[:TEXT_HEADER_SIZE]
                raw_header = raw_header.ljust(TEXT_HEADER_SIZE, b"\x00")
            plain[:TEXT_HEADER_SIZE] = raw_header
            plain[KEY_OFFSET:KEY_OFFSET + KEY_SIZE] = key[:KEY_SIZE].ljust(KEY_SIZE, b"\x00")
            plain += debug + setup + main
            chunk = bytearray(encrypt(bytes(plain)))
            while len(chunk) % SECTOR_SIZE:
                chunk.append(0)
            chunk = bytes(chunk)
            sector = len(data) // SECTOR_SIZE
            size = len(chunk) // SECTOR_SIZE
            new_entries.append((sector, size))
            data += chunk
        bin_path.write_bytes(bytes(data))
        off = fdb.dir_offsets[25 + group]
        for i, (sector, size) in enumerate(new_entries):
            base = off + i * 8
            fdb_bytes[base:base + 4] = int(sector).to_bytes(4, "little")
            fdb_bytes[base + 4:base + 8] = int(size).to_bytes(4, "little")
    accessdb_out.write_bytes(bytes(fdb_bytes))
    print(f"output={out_dir}")
    return 0


def main() -> int:
    argv = sys.argv[1:]
    if len(argv) != 3 or argv[0] not in {"d", "e"}:
        print("usage: scn.py d <input_dir> <output_dir>")
        print("   or: scn.py e <input_dir> <output_dir>")
        return 2
    cmd, input_dir, output_dir = argv
    if cmd == "d":
        return cmd_decompile(Path(input_dir), Path(output_dir))
    return cmd_encode(Path(input_dir), Path(output_dir))


if __name__ == "__main__":
    raise SystemExit(main())
