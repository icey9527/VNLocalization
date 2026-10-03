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
MAP_PATH = Path('font.tbl')
DEFAULT_REPLACE_RULES: dict[str, str] = {
    "·": "・",
    "—": "─",
    "～": "〜",
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

def load_map(p: Path) -> dict[str, str]:
    txt = p.read_text(encoding="utf-16")
    rhs_to_proxy: dict[str, str] = {}
    for raw in txt.splitlines():
        line = raw.strip()
        if not line or line.startswith(";") or line.startswith("//"):
            continue
        m = MAP_LINE_RE.match(line)
        if not m:
            continue
        code = int(m.group(1), 16)
        rhs = m.group(2).split(";", 1)[0].split("//", 1)[0].strip()
        if len(rhs) != 1:
            raise SystemExit(line)
        b = bytes([(code >> 8) & 0xFF, code & 0xFF])
        try:
            proxy = b.decode("cp932")
        except UnicodeDecodeError:
            raise SystemExit(f"{code:04X}={rhs}")
        if proxy.encode("cp932") != b:
            raise SystemExit(f"{code:04X}={rhs}")
        rhs_to_proxy[rhs] = proxy
    return rhs_to_proxy

def map_translation(t: str, rhs_to_proxy: dict[str, str]) -> str:
    if not rhs_to_proxy:
        bad: dict[str, int] = {}
        out: list[str] = []
        for ch in t:
            if cp932_code(ch) is None:
                bad[ch] = ord(ch)
                out.append("?")
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
            out.append("?")
        else:
            out.append(proxy)
    if bad:
        #items = ", ".join(f"{c}(U+{u:04X})" for c, u in sorted(bad.items(), key=lambda x: x[1]))
        #print(items, file=sys.stderr)
        log_bad_chars(sorted(bad.keys(), key=ord))
    return "".join(out)
