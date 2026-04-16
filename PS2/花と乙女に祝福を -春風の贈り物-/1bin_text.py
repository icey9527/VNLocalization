import json
import shutil
import sys
from pathlib import Path
import char
char.MAP_PATH = Path('font/font.tbl')

def trim(text):
    i = 0
    j = len(text)
    while i < j and text[i] in " \t":
        i += 1
    while j > i and text[j - 1] in " \t":
        j -= 1
    return text[i:j]


def split_args(text):
    out = []
    buf = []
    quoted = False
    esc = False
    for ch in text:
        if quoted:
            buf.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                quoted = False
            continue
        if ch == '"':
            quoted = True
            buf.append(ch)
            continue
        if ch == ",":
            out.append(trim("".join(buf)))
            buf = []
            continue
        buf.append(ch)
    out.append(trim("".join(buf)))
    return out


def parse_line(line):
    line = line.rstrip()
    if not line or "(" not in line or not line.endswith(")"):
        return None, None
    i = line.find("(")
    return line[:i], split_args(line[i + 1:-1])


def unquote(text):
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        text = text[1:-1]
    out = []
    i = 0
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text):
            out.append(text[i + 1])
            i += 2
            continue
        out.append(text[i])
        i += 1
    return "".join(out).replace("<cr>", "\n")


def quote(text):
    return '"' + text.replace("\n", "<cr>").replace("\\", "\\\\").replace('"', '\\"') + '"'


def text_value(item, fallback):
    if not item:
        return fallback
    if item.get("stage", 0):
        return item.get("translation") or fallback
    return item.get("original", fallback)


def mess_key(index):
    return f"ScrMess_{index:04X}"


def select_key(index, sub):
    return f"ScrSelect_{index:04X}_{sub:02X}"


def extract_file(path, out_dir, names):
    rows = []
    mess = 0
    select = 0
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        cmd, args = parse_line(line)
        if cmd == "ScrMess" and len(args) == 4:
            speaker = unquote(args[2])
            rows.append({
                "key": mess_key(mess),
                "original": unquote(args[3]),
                "translation": "",
                "stage": 0,
                "context": speaker,
            })
            if speaker and speaker not in names:
                names[speaker] = {
                    "key": str(len(names)),
                    "original": speaker,
                    "translation": "",
                    "stage": 0,
                    "context": "",
                }
            mess += 1
            continue
        if cmd == "ScrSelect" and len(args) >= 4:
            for i, arg in enumerate(args[3:]):
                rows.append({
                    "key": select_key(select, i),
                    "original": unquote(arg),
                    "translation": "",
                    "stage": 0,
                    "context": "",
                })
            select += 1
    if rows:
        (out_dir / f"{path.stem}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def extract_all(src_dir, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    for path in out_dir.glob("*.json"):
        path.unlink()
    names = {}
    for path in sorted(src_dir.glob("*.asm")):
        extract_file(path, out_dir, names)
    ordered = [item for _, item in sorted(names.items(), key=lambda kv: int(kv[1]["key"]))]
    (out_dir / "name.json").write_text(json.dumps(ordered, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json_dir(json_dir):
    texts = {}
    conv = char.make_translation_converter()
    for path in json_dir.glob("*.json"):
        if path.name == "name.json":
            continue
        items = json.loads(path.read_text(encoding="utf-8"))
        for item in items:
            if item.get("translation"):
                item["translation"] = conv(item["translation"])
        texts[path.stem.upper()] = {item["key"]: item for item in items}
    names = {}
    path = json_dir / "name.json"
    if path.exists():
        for item in json.loads(path.read_text(encoding="utf-8")):
            names[item["original"]] = conv(text_value(item, item["original"]))
    return texts, names


def rewrite_file(src, dst, items, names):
    out = []
    mess = 0
    select = 0
    for line in src.read_text(encoding="utf-8", errors="ignore").splitlines():
        cmd, args = parse_line(line)
        if cmd == "ScrMess" and len(args) == 4:
            speaker = unquote(args[2])
            text = unquote(args[3])
            speaker = names.get(speaker, speaker)
            text = text_value(items.get(mess_key(mess)), text)
            out.append(f'{cmd}({args[0]}, {args[1]}, {quote(speaker)}, {quote(text)})')
            mess += 1
            continue
        if cmd == "ScrSelect" and len(args) >= 4:
            vals = args[:3]
            for i, arg in enumerate(args[3:]):
                vals.append(quote(text_value(items.get(select_key(select, i)), unquote(arg))))
            out.append(f'{cmd}({", ".join(vals)})')
            select += 1
            continue
        out.append(line.rstrip())
    dst.write_text("\n".join(out) + "\n", encoding="utf-8")


def apply_all(src_dir, json_dir, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    texts, names = load_json_dir(json_dir)
    for path in out_dir.iterdir():
        if path.is_file():
            path.unlink()
    for src in sorted(src_dir.iterdir()):
        dst = out_dir / src.name
        if src.suffix.lower() == ".asm":
            rewrite_file(src, dst, texts.get(src.stem.upper(), {}), names)
        else:
            shutil.copy2(src, dst)


def main():
    if len(sys.argv) == 4 and sys.argv[1] == "d":
        extract_all(Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve())
        return
    if len(sys.argv) == 5 and sys.argv[1] == "e":
        apply_all(Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve(), Path(sys.argv[4]).resolve())
        return
    raise SystemExit(
        f"usage: {Path(sys.argv[0]).name} d input_dir output_dir\n"
        f"       {Path(sys.argv[0]).name} e input_dir json_dir output_dir"
    )


if __name__ == "__main__":
    main()
