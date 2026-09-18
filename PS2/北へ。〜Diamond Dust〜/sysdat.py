from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

import char

char.MAP_PATH = Path("font/font.tbl")


SECTOR_SIZE = 0x800
BLOCK_RECORD_SIZE = 116

MODE_SPECS = {
    0: {"sector_off": 1193, "sector_count": 1093},
    1: {"sector_off": 2286, "sector_count": 1140},
    2: {"sector_off": 3426, "sector_count": 1054},
}


def read_block(data: bytes, mode: int) -> bytes:
    spec = MODE_SPECS[mode]
    start = spec["sector_off"] * SECTOR_SIZE
    end = start + spec["sector_count"] * SECTOR_SIZE
    return data[start:end]


def parse_block(blob: bytes) -> dict[str, object]:
    text_pool_size = struct.unpack_from("<H", blob, 0)[0]
    point_count = struct.unpack_from("<H", blob, 2)[0]
    pool_start = 4
    pool_end = pool_start + text_pool_size
    table_end = pool_end + point_count * BLOCK_RECORD_SIZE
    string_pool = blob[pool_start:pool_end]
    point_table = blob[pool_end:table_end]
    tail = blob[table_end:]
    names_raw = [part for part in string_pool.split(b"\x00") if part]
    names = [part.decode("cp932") for part in names_raw]
    records: list[dict[str, object]] = []
    for i in range(point_count):
        rec = bytearray(point_table[i * BLOCK_RECORD_SIZE : (i + 1) * BLOCK_RECORD_SIZE])
        fields = [struct.unpack_from("<H", rec, j)[0] for j in range(0, BLOCK_RECORD_SIZE, 2)]
        records.append(
            {
                "index": i,
                "name": names[i] if i < len(names) else "",
                "name_offset": fields[0],
                "route_index": fields[4],
                "route_count": fields[5],
                "record_hex": bytes(rec).hex(),
            }
        )
    return {
        "text_pool_size": text_pool_size,
        "point_count": point_count,
        "records": records,
        "tail": tail.hex(),
        "block_size": len(blob),
    }


def choose_text(item: dict[str, object]) -> str:
    if int(item.get("stage", 0) or 0) == 0:
        return str(item["original"])
    text = str(item.get("translation") or "")
    return text if text else str(item["original"])


def build_map_rows(parsed: dict[str, object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for rec in parsed["records"]:
        rows.append(
            {
                "key": f"place_{rec['index']:03d}",
                "original": rec["name"],
                "translation": "",
                "stage": 0,
                "context": "",
            }
        )
    return rows


def rebuild_block(parsed: dict[str, object], rows: list[dict[str, object]]) -> bytes:
    if len(rows) != int(parsed["point_count"]):
        raise SystemExit("map.json row count does not match point_count")
    pool = bytearray()
    table = bytearray()
    for rec, row in zip(parsed["records"], rows):
        expected_key = f"place_{rec['index']:03d}"
        if str(row.get("key")) != expected_key:
            raise SystemExit(f"map.json key order mismatch: expected {expected_key}")
        name = choose_text(row)
        encoded = name.encode("kitatbl") + b"\x00"
        if len(encoded) > 40:
            raise SystemExit(f"place name exceeds the game's 40-byte limit: {expected_key}")
        if len(pool) > 0xFFFF:
            raise SystemExit("string pool offset overflow")
        record = bytearray.fromhex(str(rec["record_hex"]))
        struct.pack_into("<H", record, 0, len(pool))
        pool += encoded
        table += record
    pool_capacity = int(parsed["text_pool_size"])
    if len(pool) > pool_capacity:
        raise SystemExit(
            f"translated string pool too large: {len(pool)} > {pool_capacity}; "
            "the map record table must remain at its original offset"
        )

    # Keep the record table and all following route data at their original offsets.
    tail = bytes.fromhex(str(parsed["tail"]))
    block = bytearray()
    block += struct.pack("<H", pool_capacity)
    block += struct.pack("<H", int(parsed["point_count"]))
    block += pool
    block += b"\x00" * (pool_capacity - len(pool))
    block += table
    block += tail
    block_size = int(parsed["block_size"])
    if len(block) != block_size:
        raise SystemExit(f"rebuilt block size mismatch: {len(block)} != {block_size}")
    return bytes(block)


def cmd_extract(sysdat_path: Path, out_json: Path) -> int:
    data = sysdat_path.read_bytes()
    parsed = parse_block(read_block(data, 0))
    rows = build_map_rows(parsed)
    out_json.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"output={out_json}")
    return 0


def cmd_extract_long(sysdat_path: Path, elf_path: Path, accessdb_path: Path, out_json: Path) -> int:
    rows_path = out_json
    rc = cmd_extract(sysdat_path, rows_path)
    meta_path = out_json.with_name(out_json.stem + "_extra.json")
    meta = {
        "sysdat": str(sysdat_path),
        "elf": str(elf_path),
        "accessdb": str(accessdb_path),
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"extra={meta_path}")
    return rc


def cmd_write(map_path: Path, sysdat_path: Path, out_path: Path) -> int:
    if not sysdat_path.exists():
        raise SystemExit(f"missing {sysdat_path}")
    if not map_path.exists():
        raise SystemExit(f"missing {map_path}")
    data = bytearray(sysdat_path.read_bytes())
    rows = json.loads(map_path.read_text(encoding="utf-8"))
    for row in rows:
        tr = str(row.get("translation") or "")
        if tr and int(row.get("stage", 0) or 0) != 0:
            row["translation"] = char.convert_translation(tr)
    for mode in MODE_SPECS:
        parsed = parse_block(read_block(data, mode))
        block = rebuild_block(parsed, rows)
        spec = MODE_SPECS[mode]
        start = spec["sector_off"] * SECTOR_SIZE
        end = start + spec["sector_count"] * SECTOR_SIZE
        if len(block) > end - start:
            raise SystemExit(
                f"mode {mode} block overflow: {len(block)} > {end - start}. "
                f"this map block is loaded by hardcoded sector_off/sector_count values, "
                f"so if this ever happens you need to expand the block and patch the "
                f"executable's map-load parameters, not just replace text."
            )
        data[start:end] = block
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(bytes(data))
    print(f"output={out_path}")
    return 0


def main() -> int:
    argv = sys.argv[1:]
    if argv[:1] == ["e"] and len(argv) == 3:
        return cmd_extract(Path(argv[1]), Path(argv[2]))
    if argv[:1] == ["el"] and len(argv) == 5:
        return cmd_extract_long(Path(argv[1]), Path(argv[2]), Path(argv[3]), Path(argv[4]))
    if argv[:1] == ["w"] and len(argv) == 4:
        return cmd_write(Path(argv[1]), Path(argv[2]), Path(argv[3]))
    if argv[:1] not in (["e"], ["el"], ["w"]):
        print("usage: extract_sysdat_places.py e <sysdat.bin> <out.json>")
        print("   or: extract_sysdat_places.py el <sysdat.bin> <elf> <accessdb.bin> <out.json>")
        print("   or: extract_sysdat_places.py w <map.json> <sysdat.bin> <out_sysdat.bin>")
        return 2
    print("usage: extract_sysdat_places.py e <sysdat.bin> <out.json>")
    print("   or: extract_sysdat_places.py el <sysdat.bin> <elf> <accessdb.bin> <out.json>")
    print("   or: extract_sysdat_places.py w <map.json> <sysdat.bin> <out_sysdat.bin>")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
