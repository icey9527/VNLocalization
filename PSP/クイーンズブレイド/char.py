import re
import sys
from pathlib import Path

BADCHARS_PATH = Path("badchars.txt")

def log_bad_chars(chars, path: Path = BADCHARS_PATH) -> None:
    """
    chars: 可迭代的字符（例如 bad.keys()）
    追加写入 path；一行一个；自动去重；只写字符本身。
    """
    # 读已有，做去重
    existing: set[str] = set()
    if path.exists():
        existing = set(path.read_text(encoding="utf-8", errors="ignore").splitlines())

    # 过滤空行，保持单字符
    new_items = []
    for ch in chars:
        if not ch:
            continue
        # 你这里基本都是单字符；保险起见只取原样
        if ch not in existing:
            new_items.append(ch)
            existing.add(ch)

    if not new_items:
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        for ch in new_items:
            f.write(ch + "\n")


MAP_LINE_RE = re.compile(r"^\s*([0-9A-Fa-f]{2,4})\s*=\s*(.+?)\s*$")
MAP_START = 0x889F
MAP_PATH = Path(__file__).with_name('font') / 'font.tbl'
DEFAULT_REPLACE_RULES: dict[str, str] = {
    "·": "・",
    "—": "─",

    "“": "「",
    "”": "」"
}

def encode_cp932_or_die(s: str) -> bytes:
    try:
        return s.encode("cp932")
    except UnicodeEncodeError:
        bad: dict[str, int] = {}
        for ch in s:
            try:
                ch.encode("cp932")
            except UnicodeEncodeError:
                bad[ch] = ord(ch)
        if bad:
            #items = ", ".join(f"{c}(U+{u:04X})" for c, u in sorted(bad.items(), key=lambda x: x[1]))
            #print(items, file=sys.stderr)
            log_bad_chars(sorted(bad.keys(), key=ord))
        return s.encode("cp932", errors="ignore")

def cp932_code(ch: str) -> int | None:
    if len(ch) != 1:
        return None
    try:
        b = ch.encode("cp932")
    except UnicodeEncodeError:
        return None
    return b[0] if len(b) == 1 else (b[0] << 8) | b[1]

def is_valid_cp932_code(code: int) -> bool:
    if not 0 <= code <= 0xFFFF:
        return False
    raw = bytes((code,)) if code <= 0xFF else bytes((code >> 8, code & 0xFF))
    try:
        raw.decode("cp932")
    except UnicodeDecodeError:
        return False
    return True

def is_cp932_proxy_char(ch: str, *, start: int = MAP_START) -> bool:
    code = cp932_code(ch)
    return code is not None and code >= start

def apply_replace_rules(t: str, rules: dict[str, str] | None = None) -> str:
    r = DEFAULT_REPLACE_RULES if rules is None else rules
    if not r:
        return t
    return "".join(r.get(ch, ch) for ch in t)

def make_translation_converter(rules: dict[str, str] | None = None):
    rhs_to_proxy = load_map(MAP_PATH)
    def conv(t: str) -> str:
        return map_translation(apply_replace_rules(t, rules), rhs_to_proxy)
    return conv

def make_translation_encoder(rules: dict[str, str] | None = None):
    char_to_code = load_code_map(MAP_PATH)
    def encode(t: str) -> bytes:
        t = apply_replace_rules(t, rules)
        output = bytearray()
        bad: dict[str, int] = {}
        for ch in t:
            standard = cp932_code(ch)
            if standard is not None and standard < MAP_START:
                code = standard
            else:
                code = char_to_code.get(ch, standard)
            if code is None:
                bad[ch] = ord(ch)
                output += "？".encode("cp932")
            elif code <= 0xFF:
                output.append(code)
            else:
                output += bytes((code >> 8, code & 0xFF))
        if bad:
            log_bad_chars(sorted(bad.keys(), key=ord))
        return bytes(output)
    return encode

def load_code_map(p: Path) -> dict[str, int]:
    raw = p.read_bytes()
    txt = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8-sig")
    result: dict[str, int] = {}
    for raw_line in txt.splitlines():
        line = raw_line
        if not line or line.startswith(";") or line.startswith("//"):
            continue
        match = MAP_LINE_RE.match(line)
        if not match:
            continue
        code = int(match.group(1), 16)
        char = match.group(2).split(";", 1)[0].split("//", 1)[0]
        if len(char) == 1 and is_valid_cp932_code(code):
            result[char] = code
    return result

def load_map(p: Path) -> dict[str, str]:
    raw = p.read_bytes()
    txt = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8-sig")
    rhs_to_proxy: dict[str, str] = {}
    for raw in txt.splitlines():
        line = raw
        if not line or line.startswith(";") or line.startswith("//"):
            continue
        m = MAP_LINE_RE.match(line)
        if not m:
            continue
        code = int(m.group(1), 16)
        rhs = m.group(2).split(";", 1)[0].split("//", 1)[0]
        if len(rhs) != 1:
            raise SystemExit(line)
        b = bytes([(code >> 8) & 0xFF, code & 0xFF])
        try:
            proxy = b.decode("cp932")
        except UnicodeDecodeError:
            # font.tbl also describes physical font slots. Invalid Shift-JIS
            # holes such as 0x817F can be rendered but can never occur in text.
            continue
        rhs_to_proxy[rhs] = proxy
    return rhs_to_proxy

def map_translation(t: str, rhs_to_proxy: dict[str, str]) -> str:
    if not rhs_to_proxy:
        bad: dict[str, int] = {}
        out: list[str] = []
        for ch in t:
            if cp932_code(ch) is None:
                bad[ch] = ord(ch)
                out.append("？")
            else:
                out.append(ch)
        if bad:
            #items = ", ".join(f"{c}(U+{u:04X})" for c, u in sorted(bad.items(), key=lambda x: x[1]))
            #print(items, file=sys.stderr)
            log_bad_chars(sorted(bad.keys(), key=ord))
        return "".join(out)
    out: list[str] = []
    bad: dict[str, int] = {}
    for ch in t:
        if not is_cp932_proxy_char(ch):
            if cp932_code(ch) is not None:
                out.append(ch)
                continue
        proxy = rhs_to_proxy.get(ch)
        if proxy is None:
            bad[ch] = ord(ch)
            out.append("？")
        else:
            out.append(proxy)
    if bad:
        #items = ", ".join(f"{c}(U+{u:04X})" for c, u in sorted(bad.items(), key=lambda x: x[1]))
        #print(items, file=sys.stderr)
        log_bad_chars(sorted(bad.keys(), key=ord))
    return "".join(out)
