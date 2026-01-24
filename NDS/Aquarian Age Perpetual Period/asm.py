import os
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

CHUNK_SIZE = 0x180
TEXT_OFFSET = 0x18
TEXT_SIZE = CHUNK_SIZE - TEXT_OFFSET

OPCODES: dict[int, tuple[str, int, list[bool]]] = {
    0x00: ("NOP", 0, [False, False, False]),
    0x01: ("TEXT", 1, [False, False, False]),
    0x02: ("NEXT", 0, [False, False, False]),
    0x03: ("NEXT", 0, [False, False, False]),
    0x04: ("SET_VAL", 0, [True, False, False]),
    0x05: ("UNK_05", 0, [False, False, False]),
    0x06: ("WIN_OP", 0, [True, True, True]),
    0x07: ("WIN_CLOSE", 0, [True, False, False]),
    0x08: ("WIN_WAIT", 0, [True, True, False]),
    0x09: ("WIN_SETPARAM", 0, [True, True, True]),
    0x0A: ("UNK_0A", 0, [False, False, False]),
    0x0B: ("UNK_0B", 0, [False, False, False]),
    0x0C: ("WIN_DESTROY", 0, [True, False, False]),
    0x0D: ("WIN_CREATE", 0, [True, True, True]),
    0x0E: ("WIN_SHOW", 0, [True, False, False]),
    0x0F: ("CLEAR_SELECT", 0, [True, False, False]),
    0x10: ("FADE_IN", 0, [True, False, False]),
    0x11: ("FADE_OUT", 0, [True, False, False]),
    0x12: ("FADE_FULL", 0, [True, False, False]),
    0x13: ("FADE_WAIT", 0, [False, False, False]),
    0x14: ("WAIT_COND", 0, [False, False, False]),
    0x15: ("UI_SELECT", 0, [True, False, False]),
    0x16: ("UI_SETMODE", 0, [True, True, False]),
    0x17: ("UI_CLEAR", 0, [True, False, False]),
    0x18: ("UI_SETVAL", 0, [True, False, False]),
    0x19: ("SHOW_ELEM", 0, [True, True, False]),
    0x1A: ("SHOW_ELEM_FAST", 0, [True, True, False]),
    0x1B: ("UNK_1B", 0, [False, False, False]),
    0x1C: ("DEF_CHOICE", 1, [True, False, False]),
    0x1D: ("UNK_1D", 0, [False, False, False]),
    0x1E: ("EXEC_CHOICE", 0, [False, False, False]),
    0x1F: ("END_CHOICE", 0, [False, False, False]),
    0x20: ("MSG_SHOW", 5, [True, True, False]),
    0x21: ("MSG_SHOW_EX", 5, [True, True, False]),
    0x22: ("UNK_22", 0, [False, False, False]),
    0x23: ("CASE_0", 0, [False, False, False]),
    0x24: ("CASE_1", 0, [False, False, False]),
    0x25: ("CASE_2", 0, [False, False, False]),
    0x26: ("CASE_3", 0, [False, False, False]),
    0x27: ("CASE_4", 0, [False, False, False]),
    0x28: ("END_SWITCH", 0, [False, False, False]),
    0x29: ("JUMP", 0, [True, False, False]),
    0x2A: ("LABEL", 0, [True, False, False]),
    0x2B: ("CALL_FUNC", 0, [True, False, False]),
    0x2C: ("WAIT_KEY", 0, [False, False, False]),
    0x2D: ("WAIT_KEY_EX", 0, [False, False, False]),
    0x2E: ("CHECK_INPUT", 0, [False, False, False]),
    0x2F: ("UNK_2F", 0, [False, False, False]),
    0x30: ("UNK_30", 0, [False, False, False]),
    0x31: ("UNK_31", 0, [False, False, False]),
    0x32: ("UNK_32", 0, [False, False, False]),
    0x33: ("UNK_33", 0, [False, False, False]),
    0x34: ("UNK_34", 0, [False, False, False]),
    0x35: ("OBJ_CREATE", 0, [True, True, True]),
    0x36: ("OBJ_SETPARAM", 0, [True, True, False]),
    0x37: ("OBJ_DESTROY", 0, [True, False, False]),
    0x38: ("OBJ_SETPOS", 0, [True, True, False]),
    0x39: ("OBJ_SETSTATE", 0, [True, True, False]),
    0x3A: ("OBJ_CLEAR", 0, [True, False, False]),
    0x3B: ("UNK_3B", 0, [False, False, False]),
    0x3C: ("UNK_3C", 0, [False, False, False]),
    0x3D: ("VAR_INC", 0, [True, False, False]),
    0x3E: ("VAR_DEC", 0, [True, False, False]),
    0x3F: ("IF_EQ", 0, [True, True, False]),
    0x40: ("IF_FLAG", 0, [True, True, False]),
    0x41: ("SET_FLAG", 0, [True, True, False]),
    0x42: ("CLEAR_FLAG", 0, [True, True, False]),
    0x43: ("IF_CHECK", 0, [True, True, False]),
    0x44: ("END_SCRIPT", 0, [True, False, False]),
}


def find_opcode(name: str) -> Optional[int]:
    for op, (mn, _, _) in OPCODES.items():
        if mn == name:
            return op
    return None


def _is_printable(ch: str) -> bool:
    code = ord(ch)
    return (0x20 <= code <= 0x7E) or (code >= 0x100) or (ch in ("\n", "\t", "\r"))


def escape_text(text: str) -> str:
    out: list[str] = []
    for ch in text:
        if ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        elif ch == "\r":
            out.append("\\r")
        elif _is_printable(ch):
            out.append(ch)
        else:
            code = ord(ch)
            out.append(f"<{(code & 0xFF):02X}{((code >> 8) & 0xFF):02X}>")
    return "".join(out)


def unescape_text(text: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(text):
        if text[i] == "<":
            end = text.find(">", i)
            if end != -1:
                hex_str = text[i + 1 : end]
                try:
                    if len(hex_str) % 2 == 0:
                        out.append(bytes.fromhex(hex_str).decode("utf-16-le", errors="ignore"))
                        i = end + 1
                        continue
                except Exception:
                    pass
            out.append(text[i])
            i += 1
            continue

        if text[i] == "\\" and i + 1 < len(text):
            nxt = text[i + 1]
            if nxt == "n":
                out.append("\n")
                i += 2
                continue
            if nxt == "t":
                out.append("\t")
                i += 2
                continue
            if nxt == "r":
                out.append("\r")
                i += 2
                continue

        out.append(text[i])
        i += 1
    return "".join(out)


def _split_text_segments(raw: str) -> list[str]:
    return raw.split("＠")


def _clean_for_asm(seg: str) -> str:
    return seg.replace("＆", "").replace("Ш", "?!")


def _prepare_for_bin(seg: str) -> str:
    s = s.replace("「", "＆「")
    return s


def _join_segments_for_bin(segs: list[str]) -> str:
    return "＠＆".join(segs)


def _encode_utf16le_fit(text: str, max_bytes: int) -> bytes:
    encoded = text.encode("utf-16-le")
    if len(encoded) <= max_bytes:
        return encoded.ljust(max_bytes, b"\x00")

    lo, hi = 0, len(text)
    best = b""
    while lo <= hi:
        mid = (lo + hi) // 2
        test = text[:mid].encode("utf-16-le")
        if len(test) <= max_bytes:
            best = test
            lo = mid + 1
        else:
            hi = mid - 1
    return best.ljust(max_bytes, b"\x00")


def _extract_text_by_chars(text_data: bytes, char_len: int) -> str:
    byte_len = max(0, min(len(text_data), char_len * 2))
    return text_data[:byte_len].decode("utf-16-le", errors="ignore")


def _extract_texts(opcode: int, header: bytes, text_data: bytes, text_char_len: int) -> list[str]:
    _, text_count, _ = OPCODES.get(opcode, ("UNK", 0, [False, False, False]))
    if text_count == 0:
        return []
    if text_count == 1:
        if opcode == find_opcode("TEXT"):
            return [_extract_text_by_chars(text_data, text_char_len)]
        return [text_data.decode("utf-16-le", errors="ignore").rstrip("\x00")]
    if text_count == 5:
        offsets = [0x00, 0x48, 0x90, 0xD8, 0x120]
        size = 0x48
        out: list[str] = []
        for i, off in enumerate(offsets):
            seg = text_data[off:] if i == 4 else text_data[off : off + size]
            out.append(seg.decode("utf-16-le", errors="ignore").rstrip("\x00"))
        return out
    return []


def _format_args(opcode: int, args: tuple[int, int, int]) -> str:
    _, _, enabled = OPCODES.get(opcode, ("UNK", 0, [False, False, False]))
    parts: list[str] = []
    for i, on in enumerate(enabled):
        if on:
            parts.append(str(args[i]))
    return (" " + " ".join(parts)) if parts else ""


@dataclass
class Chunk:
    opcode: int
    args: list[int]
    texts: list[str]
    text_lines: Optional[int] = None


class Disassembler:
    def __init__(self, data: bytes):
        if len(data) == 0 or len(data) % CHUNK_SIZE != 0:
            raise ValueError("Invalid data size")
        self.data = data
        self.count = len(data) // CHUNK_SIZE
        self.op_label = find_opcode("LABEL")
        self.op_text = find_opcode("TEXT")
        self.op_msg = find_opcode("MSG_SHOW")
        self.op_msg_ex = find_opcode("MSG_SHOW_EX")

    def _read_chunk(self, index: int) -> tuple[int, tuple[int, int, int], bytes, bytes]:
        off = index * CHUNK_SIZE
        chunk = self.data[off : off + CHUNK_SIZE]
        op = struct.unpack_from("<I", chunk, 0)[0]
        a1, a2, a3 = struct.unpack_from("<iii", chunk, 4)
        header = chunk[:TEXT_OFFSET]
        text_data = chunk[TEXT_OFFSET:]
        return op, (a1, a2, a3), header, text_data

    def disasm_lines(self, index: int) -> list[str]:
        op, args, header, text_data = self._read_chunk(index)
        mnemonic, _, _ = OPCODES.get(op, (f"UNK_{op:02X}", 0, [False, False, False]))
        a1, a2, a3 = args

        if self.op_label is not None and op == self.op_label:
            return [f"LABEL_{a1:03d}:"]

        if self.op_text is not None and op == self.op_text:
            raw = _extract_text_by_chars(text_data, a1)
            segs = [_clean_for_asm(s) for s in _split_text_segments(raw)]
            out = [f"TEXT {len(segs)}"]
            out.extend(escape_text(s) for s in segs)
            return out

        if self.op_msg is not None and op == self.op_msg:
            texts = _extract_texts(op, header, text_data, a1)
            out = [f"{mnemonic}{_format_args(op, (a1, a2, a3))}"]
            out.extend(escape_text(t) for t in texts[: max(0, a1)])
            return out

        if self.op_msg_ex is not None and op == self.op_msg_ex:
            texts = _extract_texts(op, header, text_data, a1)
            icon_ids = [struct.unpack_from("<i", header, 8 + i * 4)[0] for i in range(4)]
            out = [f"{mnemonic}{_format_args(op, (a1, a2, a3))}"]
            for i, t in enumerate(texts[: max(0, a1)]):
                icon = icon_ids[i] if i < 4 else -1
                out.append(f"{icon} {escape_text(t)}")
            return out

        return [f"{mnemonic}{_format_args(op, (a1, a2, a3))}"]

    def export(self, path: str) -> None:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            for i in range(self.count):
                for line in self.disasm_lines(i):
                    f.write(line + "\n")


class Assembler:
    def __init__(self):
        self.mnemonic_to_opcode = {mn: op for op, (mn, _, _) in OPCODES.items()}
        self.op_label = find_opcode("LABEL")
        self.op_text = find_opcode("TEXT")
        self.op_msg_ex = find_opcode("MSG_SHOW_EX")
        self.chunks: list[Chunk] = []

    def _parse_instruction(self, line: str) -> Optional[Chunk]:
        if not line or line.startswith(";"):
            return None

        if line.startswith("LABEL_") and line.endswith(":"):
            if self.op_label is None:
                return None
            label_id = int(line[6:-1])
            return Chunk(self.op_label, [label_id, 0, 0], [])

        parts = line.split(None, 1)
        if not parts:
            return None

        mnemonic = parts[0]
        if mnemonic not in self.mnemonic_to_opcode:
            return None

        opcode = self.mnemonic_to_opcode[mnemonic]
        rest = parts[1] if len(parts) > 1 else ""

        if self.op_text is not None and opcode == self.op_text:
            n = 1
            if rest:
                try:
                    n = int(rest.split()[0])
                except Exception:
                    n = 1
            return Chunk(opcode, [0, 0, 0], [], text_lines=max(1, n))

        args = [0, 0, 0]
        if rest:
            for i, tok in enumerate(rest.split()[:3]):
                try:
                    args[i] = int(tok)
                except Exception:
                    break
        return Chunk(opcode, args, [])

    def assemble(self, asm_path: str) -> bytes:
        with open(asm_path, "r", encoding="utf-8") as f:
            lines = [ln.rstrip("\n\r") for ln in f]

        current: Optional[Chunk] = None
        for line in lines:
            inst = self._parse_instruction(line)
            if inst is not None:
                if current is not None:
                    self.chunks.append(current)
                current = inst
                continue

            if current is None:
                continue

            if self.op_msg_ex is not None and current.opcode == self.op_msg_ex:
                tokens = line.split(None, 1)
                if (
                    tokens
                    and len(tokens[0]) <= 4
                    and tokens[0].lstrip("-").isdigit()
                    and all(ord(c) < 128 for c in tokens[0])
                ):
                    text_part = tokens[1] if len(tokens) > 1 else ""
                    current.texts.append(unescape_text(text_part))
                else:
                    current.texts.append(unescape_text(line))
            else:
                current.texts.append(unescape_text(line))

        if current is not None:
            self.chunks.append(current)

        return self._build()

    def _build(self) -> bytes:
        out = bytearray()

        for ch in self.chunks:
            buf = bytearray(CHUNK_SIZE)
            op = ch.opcode
            args = ch.args[:]
            texts = ch.texts
            _, text_count, _ = OPCODES.get(op, ("UNK", 0, [False, False, False]))

            if self.op_text is not None and op == self.op_text:
                n = ch.text_lines or 1
                segs = [(_prepare_for_bin(s) if s is not None else "") for s in texts[:n]]
                if len(segs) < n:
                    segs.extend([""] * (n - len(segs)))
                combined = _join_segments_for_bin(segs)
                args[0] = len(combined)
                texts = [combined]
                text_count = 1

            struct.pack_into("<I", buf, 0, op)
            struct.pack_into("<iii", buf, 4, args[0], args[1], args[2])

            if text_count == 1 and texts:
                buf[TEXT_OFFSET:] = _encode_utf16le_fit(texts[0], TEXT_SIZE)

            elif text_count == 5:
                offsets = [TEXT_OFFSET + 0x00, TEXT_OFFSET + 0x48, TEXT_OFFSET + 0x90, TEXT_OFFSET + 0xD8, TEXT_OFFSET + 0x120]
                sizes = [0x48, 0x48, 0x48, 0x48, 0x48]
                for i, (off, size) in enumerate(zip(offsets, sizes)):
                    if i < len(texts):
                        buf[off : off + size] = _encode_utf16le_fit(texts[i], size)
                if self.op_msg_ex is not None and op == self.op_msg_ex:
                    for i in range(4):
                        struct.pack_into("<i", buf, 8 + i * 4, -1)

            out.extend(buf)

        return bytes(out)


def _dat_to_asm_name(name: str) -> str:
    return (name[:-4] + ".asm") if name.endswith("_DAT") else (name + ".asm")


def _asm_to_dat_name(name: str) -> str:
    return (name[:-4] + "_DAT") if name.endswith(".asm") else (name + "_DAT")


def extract_folder(input_folder: str, output_folder: str) -> None:
    src = Path(input_folder)
    dst = Path(output_folder)
    dst.mkdir(parents=True, exist_ok=True)

    for root, _, files in os.walk(src):
        for fn in files:
            if not fn.endswith("_DAT"):
                continue
            dat_path = Path(root) / fn
            rel = dat_path.relative_to(src)
            asm_path = dst / rel.parent / _dat_to_asm_name(dat_path.name)
            asm_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                data = dat_path.read_bytes()
                if len(data) == 0 or len(data) % CHUNK_SIZE != 0:
                    print(str(rel))
                    continue
                Disassembler(data).export(str(asm_path))
            except Exception:
                print(str(rel))


def write_folder(input_folder: str, output_folder: str) -> None:
    src = Path(input_folder)
    dst = Path(output_folder)
    dst.mkdir(parents=True, exist_ok=True)

    for asm_path in src.rglob("*.asm"):
        rel = asm_path.relative_to(src)
        dat_path = dst / rel.parent / _asm_to_dat_name(asm_path.name)
        dat_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = Assembler().assemble(str(asm_path))
            dat_path.write_bytes(data)
        except Exception:
            print(str(rel))


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print("Usage:")
        print("  python asm.py e <input_folder> <output_folder>")
        print("  python asm.py w <input_folder> <output_folder>")
        return 1

    mode = argv[1].lower()
    inp = argv[2]
    outp = argv[3]

    if mode == "e":
        extract_folder(inp, outp)
        return 0
    if mode == "w":
        write_folder(inp, outp)
        return 0

    print(f"Invalid mode: {argv[1]}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
