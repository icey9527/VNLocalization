from __future__ import annotations

import json
import sys
import struct
import hashlib
from pathlib import Path

import char


DEFAULT_ELF_PATH = Path("SLPM_654.04")
EXPORT_DIR = Path("phone_json")
OUT_TXT = Path("phone_texts_dump.txt")

char.MAP_PATH = Path("font/font.tbl")


def load_elf_image(path: Path) -> tuple[bytes, list[dict[str, int]]]:
    data = path.read_bytes()
    if data[:4] != b"\x7fELF":
        raise SystemExit(f"{path} is not an ELF")
    if data[4] != 1:
        raise SystemExit("Only 32-bit ELF is supported")
    if data[5] != 1:
        raise SystemExit("Only little-endian ELF is supported")

    (
        _e_type,
        _e_machine,
        _e_version,
        _e_entry,
        e_phoff,
        _e_shoff,
        _e_flags,
        _e_ehsize,
        e_phentsize,
        e_phnum,
        _e_shentsize,
        _e_shnum,
        _e_shstrndx,
    ) = struct.unpack_from("<HHIIIIIHHHHHH", data, 16)

    segs: list[dict[str, int]] = []
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type, p_offset, p_vaddr, _p_paddr, p_filesz, p_memsz, p_flags, p_align = struct.unpack_from(
            "<IIIIIIII", data, off
        )
        if p_type != 1:
            continue
        segs.append(
            {
                "offset": p_offset,
                "vaddr": p_vaddr,
                "filesz": p_filesz,
                "memsz": p_memsz,
                "flags": p_flags,
                "align": p_align,
            }
        )
    return data, segs


def vaddr_to_offset(vaddr: int, segs: list[dict[str, int]]) -> int:
    for seg in segs:
        start = seg["vaddr"]
        end = start + seg["filesz"]
        if start <= vaddr < end:
            return seg["offset"] + (vaddr - start)
    raise ValueError(f"vaddr {vaddr:#x} is not in a file-backed PT_LOAD segment")


def read_block(image: bytes, segs: list[dict[str, int]], vaddr: int, size: int) -> bytes:
    off = vaddr_to_offset(vaddr, segs)
    return image[off : off + size]


def decode_cp932(blob: bytes) -> str:
    return blob.decode("cp932")


def cp932_char_len(first: int) -> int:
    if (0x81 <= first <= 0x9F) or (0xE0 <= first <= 0xFC):
        return 2
    return 1


def encode_phone_text(text: str) -> bytes:
    text = normalize_phone_text(text)
    out = bytearray()
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "#" and i + 1 < len(text):
            cmd = text[i + 1]
            if cmd in "nwec":
                out.extend(b"#" + cmd.encode("ascii"))
                i += 2
                continue
        out.extend(text[i].encode("cp932"))
        i += 1
    return bytes(out)


def export_phone_text(text: str) -> str:
    return text.replace("#n", "{R;}")


def normalize_phone_text(text: str) -> str:
    return text.replace("{R;}", "#n")


def parse_entry(blob: bytes, start: int = 0, alt_blob: bytes | None = None) -> tuple[str, int, int]:
    parts: list[bytes] = []
    pos = start
    cur = blob
    switched = False

    while pos < len(cur):
        b = cur[pos]
        if b == 0:
            break
        if b == 0x23 and pos + 1 < len(cur):
            cmd = cur[pos + 1]
            if cmd in (ord("n"), ord("w"), ord("e"), ord("c")):
                parts.append(cur[pos : pos + 2])
                pos += 2
                if cmd == ord("c"):
                    if alt_blob is None or switched:
                        break
                    cur = alt_blob
                    pos = 0
                    switched = True
                    continue
                if cmd == ord("e"):
                    break
                continue
        clen = cp932_char_len(b)
        parts.append(cur[pos : pos + clen])
        pos += clen

    return decode_cp932(b"".join(parts)).rstrip("\x00"), pos, 1 if switched else 0


def parse_contiguous_entries(blob: bytes) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    pos = 0
    idx = 0
    while pos < len(blob):
        while pos < len(blob) and blob[pos] == 0:
            pos += 1
        if pos >= len(blob):
            break
        text, end_pos, _used_alt = parse_entry(blob, pos)
        if not text:
            break
        out.append({"index": idx, "offset": pos, "text": text})
        idx += 1
        if end_pos <= pos:
            break
        pos = end_pos
    return out


def parse_offset_entries(blob: bytes, offsets: list[int]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for idx, start in enumerate(offsets):
        text, _end_pos, _used_alt = parse_entry(blob, start)
        out.append({"index": idx, "offset": start, "text": text})
    return out


def parse_single_entry(blob: bytes, alt_blob: bytes | None = None) -> list[dict[str, object]]:
    text, _end_pos, used_alt = parse_entry(blob, 0, alt_blob=alt_blob)
    item: dict[str, object] = {"index": 0, "offset": 0, "text": text}
    if used_alt:
        item["used_alt_block"] = True
    return [item]


def build_groups(image: bytes, segs: list[dict[str, int]]) -> list[dict[str, object]]:
    specs = [
        {"name": "display_font_mm", "addr": 0x2C78C0, "size": 0x40, "mode": "single", "context": "携帯メニュー"},
        {"name": "display_font_tyaku", "addr": 0x2C7900, "size": 0x90, "mode": "single", "context": "着信メニュー"},
        {"name": "display_font_oki", "addr": 0x2C7990, "size": 0x210, "mode": "contiguous", "context": "お気に入り"},
        {"name": "display_font_zyusin", "addr": 0x2C7BA0, "size": 0x2E0, "mode": "contiguous", "context": "メール件名"},
        {"name": "display_font_mail", "addr": 0x2C7E80, "size": 0x35A0, "mode": "contiguous", "context": "メール本文"},
        {"name": "display_font_memo", "addr": 0x2CB420, "size": 0xB00, "mode": "contiguous", "context": "取材メモ"},
        {"name": "display_font_mokuzi", "addr": 0x2CBF20, "size": 0xE0, "mode": "contiguous", "context": "アンテナ目次"},
        {"name": "display_font_anmain0", "addr": 0x2CC000, "size": 0x430, "mode": "single_pair", "alt_addr": 0x2CEB40, "alt_size": 0x110, "context": "アンテナ本文0"},
        {"name": "display_font_anmain1", "addr": 0x2CC430, "size": 0x200, "mode": "single_pair", "alt_addr": 0x2CEC50, "alt_size": 0x190, "context": "アンテナ本文1"},
        {"name": "display_font_anmain2", "addr": 0x2CC630, "size": 0x170, "mode": "single_pair", "alt_addr": 0x2CEDE0, "alt_size": 0xA0, "context": "アンテナ本文2"},
        {"name": "display_font_anmain3", "addr": 0x2CC7A0, "size": 0x430, "mode": "single_pair", "alt_addr": 0x2CEE80, "alt_size": 0x240, "context": "アンテナ本文3"},
        {"name": "display_font_anmain4", "addr": 0x2CCBD0, "size": 0x130, "mode": "single_pair", "alt_addr": 0x2CF0C0, "alt_size": 0x1A0, "context": "アンテナ本文4"},
        {"name": "display_font_anmain5", "addr": 0x2CCD00, "size": 0x300, "mode": "single_pair", "alt_addr": 0x2CF260, "alt_size": 0x380, "context": "アンテナ本文5"},
        {"name": "display_font_anmain6", "addr": 0x2CD000, "size": 0x240, "mode": "single_pair", "alt_addr": 0x2CF5E0, "alt_size": 0x210, "context": "アンテナ本文6"},
        {"name": "display_font_anmain7", "addr": 0x2CD240, "size": 0x210, "mode": "single_pair", "alt_addr": 0x2CF7F0, "alt_size": 0x440, "context": "アンテナ本文7"},
        {"name": "display_font_anmain8", "addr": 0x2CD450, "size": 0x3E0, "mode": "single_pair", "alt_addr": 0x2CFC30, "alt_size": 0x1C0, "context": "アンテナ本文8"},
        {"name": "display_font_anmain9", "addr": 0x2CD830, "size": 0x100, "mode": "single_pair", "alt_addr": 0x2F65DC, "alt_size": 0xA4, "context": "アンテナ本文9"},
        {"name": "display_font_anbad0", "addr": 0x2CD930, "size": 0x180, "mode": "single", "context": "アンテナbad0"},
        {"name": "display_font_anbad1", "addr": 0x2CDAB0, "size": 0xC0, "mode": "single", "context": "アンテナbad1"},
        {"name": "display_font_anbad2", "addr": 0x2CDB70, "size": 0xD0, "mode": "single", "context": "アンテナbad2"},
        {"name": "display_font_anbad3", "addr": 0x2CDC40, "size": 0x2A0, "mode": "single", "context": "アンテナbad3"},
        {"name": "display_font_anbad4", "addr": 0x2CDEE0, "size": 0x3B0, "mode": "single", "context": "アンテナbad4"},
        {"name": "display_font_anbad5", "addr": 0x2CE290, "size": 0x160, "mode": "single", "context": "アンテナbad5"},
        {"name": "display_font_anbad6", "addr": 0x2CE3F0, "size": 0x330, "mode": "single", "context": "アンテナbad6"},
        {"name": "display_font_anbad7", "addr": 0x2CE720, "size": 0x1F0, "mode": "single", "context": "アンテナbad7"},
        {"name": "display_font_anbad8", "addr": 0x2CE910, "size": 0x1C0, "mode": "single", "context": "アンテナbad8"},
        {"name": "display_font_anbad9", "addr": 0x2CEAD0, "size": 0x70, "mode": "single", "context": "アンテナbad9"},
        {"name": "display_font_angood0", "addr": 0x2CEB40, "size": 0x110, "mode": "single", "context": "アンテナgood0"},
        {"name": "display_font_angood1", "addr": 0x2CEC50, "size": 0x190, "mode": "single", "context": "アンテナgood1"},
        {"name": "display_font_angood2", "addr": 0x2CEDE0, "size": 0xA0, "mode": "single", "context": "アンテナgood2"},
        {"name": "display_font_angood3", "addr": 0x2CEE80, "size": 0x240, "mode": "single", "context": "アンテナgood3"},
        {"name": "display_font_angood4", "addr": 0x2CF0C0, "size": 0x1A0, "mode": "single", "context": "アンテナgood4"},
        {"name": "display_font_angood5", "addr": 0x2CF260, "size": 0x380, "mode": "single", "context": "アンテナgood5"},
        {"name": "display_font_angood6", "addr": 0x2CF5E0, "size": 0x210, "mode": "single", "context": "アンテナgood6"},
        {"name": "display_font_angood7", "addr": 0x2CF7F0, "size": 0x440, "mode": "single", "context": "アンテナgood7"},
        {"name": "display_font_angood8", "addr": 0x2CFC30, "size": 0x1C0, "mode": "single", "context": "アンテナgood8"},
        {"name": "display_font_angood9", "addr": 0x2F65DC, "size": 0xA4, "mode": "single", "context": "アンテナgood9"},
        {"name": "display_font_uranai1", "addr": 0x2CFDF0, "size": 0x40, "mode": "single", "context": "占い固定1"},
        {"name": "display_font_uranai2", "addr": 0x2CFE30, "size": 0x40, "mode": "single", "context": "占い固定2"},
        {"name": "display_font_u_result_nothing", "addr": 0x2CFE70, "size": 0x7C0, "mode": "offsets", "offsets": [0x000, 0x0DC, 0x1B8, 0x294, 0x370, 0x44C, 0x528, 0x604], "context": "占い結果nothing"},
        {"name": "display_font_u_result_ha", "addr": 0x2D0630, "size": 0x1060, "mode": "contiguous", "context": "占い結果ha"},
        {"name": "display_font_u_result_aa", "addr": 0x2D1690, "size": 0x12F0, "mode": "contiguous", "context": "占い結果aa"},
        {"name": "display_font_u_result_ks", "addr": 0x2D2980, "size": 0x12F0, "mode": "contiguous", "context": "占い結果ks"},
        {"name": "display_font_u_result_ak", "addr": 0x2D3C70, "size": 0xEA0, "mode": "contiguous", "context": "占い結果ak"},
        {"name": "display_font_u_result_sk", "addr": 0x2D4B10, "size": 0x1060, "mode": "contiguous", "context": "占い結果sk"},
        {"name": "display_font_u_result_ss", "addr": 0x2D5B70, "size": 0x1130, "mode": "contiguous", "context": "占い結果ss"},
        {"name": "display_font_u_result_mm", "addr": 0x2D6CA0, "size": 0x1580, "mode": "contiguous", "context": "占い結果mm"},
        {"name": "mail_status_strings", "addr": 0x2F5CD0, "size": 0x60, "mode": "contiguous", "context": "メール状態"},
    ]

    groups: list[dict[str, object]] = []
    for spec in specs:
        blob = read_block(image, segs, spec["addr"], spec["size"])
        mode = spec["mode"]
        if mode == "single":
            entries = parse_single_entry(blob)
        elif mode == "single_pair":
            alt_blob = read_block(image, segs, spec["alt_addr"], spec["alt_size"])
            entries = parse_single_entry(blob, alt_blob=alt_blob)
        elif mode == "contiguous":
            entries = parse_contiguous_entries(blob)
        elif mode == "offsets":
            entries = parse_offset_entries(blob, spec["offsets"])
        else:
            raise ValueError(f"Unknown mode: {mode}")

        for entry in entries:
            entry["abs_addr"] = hex(spec["addr"] + int(entry["offset"]))

        groups.append(
            {
                "name": spec["name"],
                "addr": spec["addr"],
                "size": spec["size"],
                "mode": mode,
                "context": spec["context"],
                "entries": entries,
                "alt_addr": spec.get("alt_addr"),
                "alt_size": spec.get("alt_size"),
            }
        )
    return groups


def group_to_rows(group: dict[str, object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    entries = group["entries"]
    assert isinstance(entries, list)
    for entry in entries:
        assert isinstance(entry, dict)
        idx = int(entry["index"])
        rows.append(
            {
                "key": f"{group['name']}_{idx:03d}",
                "original": export_phone_text(str(entry["text"])),
                "translation": "",
                "stage": 0,
                "context": f"{group['name']}:{idx:03d}",
            }
        )
    return rows


def export_groups(elf_path: Path, export_dir: Path) -> None:
    image, segs = load_elf_image(elf_path)
    groups = build_groups(image, segs)
    export_dir.mkdir(parents=True, exist_ok=True)
    for f in export_dir.glob("*.json"):
        f.unlink()

    dump_lines: list[str] = []
    for group in groups:
        rows = group_to_rows(group)
        (export_dir / f"{group['name']}.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        dump_lines.append(f"[{group['name']}]")
        for row in rows:
            dump_lines.append(f"{row['key']}: {row['original']}")
        dump_lines.append("")

    OUT_TXT.write_text("\n".join(dump_lines), encoding="utf-8")
    print(f"Exported JSON files to {export_dir}")
    print(f"Wrote {OUT_TXT}")


def load_json_dir(json_dir: Path, allowed_groups: set[str] | None = None) -> dict[str, dict[str, object]]:
    items_by_group: dict[str, dict[str, object]] = {}
    conv = char.make_translation_converter()
    for f in sorted(json_dir.glob("*.json")):
        if allowed_groups is not None and f.stem not in allowed_groups:
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        by_key: dict[str, object] = {}
        for item in data:
            tr = item.get("translation") or ""
            if tr:
                item["translation"] = conv(tr)
            by_key[item["key"]] = item
        items_by_group[f.stem] = by_key
    return items_by_group


def choose_text(item: dict[str, object] | None, original: str) -> str:
    if not item:
        return original
    if int(item.get("stage", 0) or 0) == 0:
        return original
    tr = item.get("translation") or ""
    return tr or original


def split_pair_text(text: str) -> tuple[str, str]:
    marker = "#c"
    pos = text.find(marker)
    if pos < 0:
        return text, ""
    return text[: pos + len(marker)], text[pos + len(marker) :]


def group_entry_regions(group: dict[str, object], entry_index: int) -> list[dict[str, int | str]]:
    entries = group["entries"]
    assert isinstance(entries, list)
    mode = str(group["mode"])

    if mode == "single":
        if entry_index != 0:
            raise IndexError(entry_index)
        return [{"part": "main", "start": 0, "size": int(group["size"])}]

    if mode == "single_pair":
        if entry_index != 0:
            raise IndexError(entry_index)
        parts: list[dict[str, int | str]] = [{"part": "main", "start": 0, "size": int(group["size"])}]
        alt_size = int(group.get("alt_size") or 0)
        if alt_size:
            parts.append({"part": "alt", "start": 0, "size": alt_size})
        return parts

    if mode in ("contiguous", "offsets"):
        offsets = [int(x["offset"]) for x in entries]
        offsets.append(int(group["size"]))
        return [{"part": "main", "start": offsets[entry_index], "size": offsets[entry_index + 1] - offsets[entry_index]}]

    raise ValueError(f"Unknown mode for regions: {mode}")


def patch_region(dst: bytearray, start: int, size: int, payload: bytes) -> None:
    if len(payload) > size:
        raise ValueError(f"text too long for region: need {len(payload)} bytes, limit {size}")
    dst[start : start + size] = b"\x00" * size
    dst[start : start + len(payload)] = payload


def build_group_blob(group: dict[str, object], original_blob: bytes, merged_items: dict[str, object]) -> tuple[bytes, bytes | None]:
    rows = group_to_rows(group)
    mode = str(group["mode"])
    entries = group["entries"]
    assert isinstance(entries, list)

    if mode == "single_pair":
        row = rows[0]
        item = merged_items.get(str(row["key"]))
        chosen = choose_text(item if isinstance(item, dict) else None, str(row["original"]))
        main_text, alt_text = split_pair_text(chosen)
        main_bytes = encode_phone_text(main_text)
        alt_bytes = encode_phone_text(alt_text)
        main_blob = bytearray(b"\x00" * int(group["size"]))
        alt_size = int(group["alt_size"]) if group.get("alt_size") is not None else 0
        alt_blob = bytearray(b"\x00" * alt_size)
        patch_region(main_blob, 0, len(main_blob), main_bytes)
        if alt_size:
            patch_region(alt_blob, 0, alt_size, alt_bytes)
        return bytes(main_blob), bytes(alt_blob)

    blob = bytearray(original_blob)
    offsets = [int(entry["offset"]) for entry in entries]
    offsets.append(int(group["size"]))
    for idx, entry in enumerate(entries):
        row = rows[idx]
        item = merged_items.get(str(row["key"]))
        chosen = choose_text(item if isinstance(item, dict) else None, str(row["original"]))
        payload = encode_phone_text(chosen)
        start = int(entry["offset"])
        end = offsets[idx + 1]
        patch_region(blob, start, end - start, payload)
    return bytes(blob), None


def entry_capacity(group: dict[str, object], entry_index: int) -> int:
    return sum(int(part["size"]) for part in group_entry_regions(group, entry_index))


def capacity_report(elf_path: Path, json_dir: Path | None, out_json: Path) -> None:
    image, segs = load_elf_image(elf_path)
    groups = build_groups(image, segs)
    merged_items: dict[str, object] = {}
    if json_dir is not None and json_dir.exists():
        allowed_groups = {str(group["name"]) for group in groups}
        for bucket in load_json_dir(json_dir, allowed_groups).values():
            merged_items.update(bucket)

    report_groups: list[dict[str, object]] = []
    for group in groups:
        rows = group_to_rows(group)
        row_reports: list[dict[str, object]] = []
        for idx, row in enumerate(rows):
            original = str(row["original"])
            original_bytes = encode_phone_text(original)
            item = merged_items.get(str(row["key"]))
            translation = ""
            stage = 0
            if isinstance(item, dict):
                translation = str(item.get("translation") or "")
                stage = int(item.get("stage", 0) or 0)
            final_text = choose_text(item if isinstance(item, dict) else None, original)
            final_bytes = encode_phone_text(final_text)
            region_caps = group_entry_regions(group, idx)
            part_usage: list[dict[str, object]] = []
            if str(group["mode"]) == "single_pair":
                orig_main, orig_alt = split_pair_text(original)
                final_main, final_alt = split_pair_text(final_text)
                encoded_parts = {
                    "main": encode_phone_text(orig_main),
                    "alt": encode_phone_text(orig_alt),
                }
                final_part_bytes = {
                    "main": encode_phone_text(final_main),
                    "alt": encode_phone_text(final_alt),
                }
                for part in region_caps:
                    pname = str(part["part"])
                    pcap = int(part["size"])
                    part_usage.append(
                        {
                            "part": pname,
                            "original_len": len(encoded_parts[pname]),
                            "final_len": len(final_part_bytes[pname]),
                            "capacity": pcap,
                            "headroom": pcap - len(encoded_parts[pname]),
                            "fits": len(final_part_bytes[pname]) <= pcap,
                        }
                    )
            else:
                pcap = int(region_caps[0]["size"])
                part_usage.append(
                    {
                        "part": "main",
                        "original_len": len(original_bytes),
                        "final_len": len(final_bytes),
                        "capacity": pcap,
                        "headroom": pcap - len(original_bytes),
                        "fits": len(final_bytes) <= pcap,
                    }
                )
            capacity = entry_capacity(group, idx)
            row_reports.append(
                {
                    "key": row["key"],
                    "original_len": len(original_bytes),
                    "capacity": capacity,
                    "headroom": capacity - len(original_bytes),
                    "stage": stage,
                    "translation_len": len(encode_phone_text(translation)) if translation else 0,
                    "final_len": len(final_bytes),
                    "fits": all(bool(part["fits"]) for part in part_usage),
                    "parts": part_usage,
                }
            )
        report_groups.append({"name": group["name"], "rows": row_reports})

    payload = {"source_elf": str(elf_path), "json_dir": str(json_dir) if json_dir else None, "groups": report_groups}
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_json}")


def capacity_summary(report_json: Path, out_txt: Path, *, low_threshold: int = 16) -> None:
    data = json.loads(report_json.read_text(encoding="utf-8"))
    zero: list[tuple[str, str, int, int]] = []
    low: list[tuple[str, str, int, int]] = []
    overflow: list[tuple[str, str, int, int]] = []
    for group in data["groups"]:
        gname = group["name"]
        for row in group["rows"]:
            item = (gname, row["key"], row["final_len"], row["capacity"])
            if not row["fits"]:
                overflow.append(item)
            elif row["headroom"] == 0:
                zero.append(item)
            elif row["headroom"] <= low_threshold:
                low.append(item)

    lines: list[str] = []
    lines.append(f"Capacity summary from {report_json.name}")
    lines.append("")
    lines.append("Overflow")
    if overflow:
        for gname, key, final_len, cap in overflow:
            lines.append(f"{gname} {key} final={final_len} cap={cap}")
    else:
        lines.append("(none)")
    lines.append("")
    lines.append("Zero Headroom")
    if zero:
        for gname, key, final_len, cap in zero:
            lines.append(f"{gname} {key} len={final_len} cap={cap}")
    else:
        lines.append("(none)")
    lines.append("")
    lines.append(f"Low Headroom (<= {low_threshold})")
    if low:
        for gname, key, final_len, cap in low:
            lines.append(f"{gname} {key} len={final_len} cap={cap}")
    else:
        lines.append("(none)")
    lines.append("")
    out_txt.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out_txt}")


def apply_translations(elf_path: Path, json_dir: Path, out_elf: Path) -> None:
    image, segs = load_elf_image(elf_path)
    groups = build_groups(image, segs)
    allowed_groups = {str(group["name"]) for group in groups}
    buckets = load_json_dir(json_dir, allowed_groups)
    merged_items: dict[str, object] = {}
    for bucket in buckets.values():
        merged_items.update(bucket)
    out_data = bytearray(image)

    for group in groups:
        main_blob = read_block(image, segs, int(group["addr"]), int(group["size"]))
        patched_main, patched_alt = build_group_blob(group, main_blob, merged_items)
        main_off = vaddr_to_offset(int(group["addr"]), segs)
        out_data[main_off : main_off + len(patched_main)] = patched_main
        alt_addr = group.get("alt_addr")
        alt_size = group.get("alt_size")
        if patched_alt is not None and alt_addr is not None and alt_size is not None:
            alt_off = vaddr_to_offset(int(alt_addr), segs)
            out_data[alt_off : alt_off + len(patched_alt)] = patched_alt

    out_elf.write_bytes(bytes(out_data))
    print(f"Wrote {out_elf}")


def collect_rows_by_key(export_dir: Path, allowed_groups: set[str] | None = None) -> dict[str, str]:
    out: dict[str, str] = {}
    for f in sorted(export_dir.glob("*.json")):
        if allowed_groups is not None and f.stem not in allowed_groups:
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        for item in data:
            out[str(item["key"])] = str(item["original"])
    return out


def verify_roundtrip(src_elf: Path, json_dir: Path, out_elf: Path, verify_dir: Path) -> None:
    image, segs = load_elf_image(src_elf)
    groups = build_groups(image, segs)
    allowed_groups = {str(group["name"]) for group in groups}
    apply_translations(src_elf, json_dir, out_elf)
    export_groups(out_elf, verify_dir)
    src_rows = collect_rows_by_key(json_dir, allowed_groups)
    new_rows = collect_rows_by_key(verify_dir, allowed_groups)

    missing = sorted(set(src_rows) - set(new_rows))
    extra = sorted(set(new_rows) - set(src_rows))
    changed = sorted(k for k in src_rows.keys() & new_rows.keys() if src_rows[k] != new_rows[k])

    report = {
        "source_elf": str(src_elf),
        "output_elf": str(out_elf),
        "json_dir": str(json_dir),
        "verify_dir": str(verify_dir),
        "source_count": len(src_rows),
        "verify_count": len(new_rows),
        "missing_keys": missing,
        "extra_keys": extra,
        "changed_keys": changed,
        "ok": not missing and not extra and not changed,
        "src_sha1": hashlib.sha1(src_elf.read_bytes()).hexdigest(),
        "out_sha1": hashlib.sha1(out_elf.read_bytes()).hexdigest(),
    }
    report_path = Path("phone_verify_report.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {report_path}")
    if not report["ok"]:
        raise SystemExit("roundtrip verification failed")


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: python extract_phone_texts.py e <elf> <out_dir> | w <elf> <json_dir> <out_elf> | t <elf> <json_dir> <out_elf> <verify_dir> | c <elf> [json_dir] <out_json>")

    mode = sys.argv[1]
    if mode == "e":
        if len(sys.argv) < 4:
            raise SystemExit("usage: python extract_phone_texts.py e <elf> <out_dir>")
        export_groups(Path(sys.argv[2]), Path(sys.argv[3]))
        return
    if mode == "w":
        if len(sys.argv) < 5:
            raise SystemExit("usage: python extract_phone_texts.py w <elf> <json_dir> <out_elf>")
        apply_translations(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
        return
    if mode == "t":
        if len(sys.argv) < 6:
            raise SystemExit("usage: python extract_phone_texts.py t <elf> <json_dir> <out_elf> <verify_dir>")
        verify_roundtrip(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]), Path(sys.argv[5]))
        return
    if mode == "c":
        if len(sys.argv) == 4:
            capacity_report(Path(sys.argv[2]), None, Path(sys.argv[3]))
            return
        if len(sys.argv) == 5:
            capacity_report(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
            return
        raise SystemExit("usage: python extract_phone_texts.py c <elf> [json_dir] <out_json>")
    if mode == "cs":
        if len(sys.argv) < 4:
            raise SystemExit("usage: python extract_phone_texts.py cs <capacity_json> <out_txt> [threshold]")
        threshold = int(sys.argv[4]) if len(sys.argv) >= 5 else 16
        capacity_summary(Path(sys.argv[2]), Path(sys.argv[3]), low_threshold=threshold)
        return
    raise SystemExit("unknown mode")


if __name__ == "__main__":
    main()
