from __future__ import annotations

from typing import Any
import bisect

from . import core


def _apply_relocation_sites_detailed(
    payload: bytearray,
    *,
    old_op_offsets: list[int],
    new_op_offsets: list[int],
    off_map: dict[int, int],
    sites: list[tuple[int, int, int, int]],
) -> tuple[int, int, list[dict[str, Any]]]:
    patched = 0
    patched_fallback = 0
    skipped: list[dict[str, Any]] = []
    for op_i, delta, width, old_val in sites:
        if op_i < 0 or op_i >= len(new_op_offsets):
            skipped.append({"op_index": op_i, "delta": delta, "width": width, "old_value": old_val, "reason": "op_index_oob"})
            continue
        pos = new_op_offsets[op_i] + delta
        if pos < 0 or pos + width > len(payload):
            skipped.append({"op_index": op_i, "delta": delta, "width": width, "old_value": old_val, "reason": "site_oob"})
            continue
        if width == 5:
            if not (pos + 5 <= len(payload) and payload[pos] == 0xFF):
                skipped.append({"op_index": op_i, "delta": delta, "width": width, "old_value": old_val, "reason": "imm32_prefix_missing"})
                continue
            cur = core.u32le(payload, pos + 1)
        elif width == 4:
            cur = core.u32le(payload, pos)
        elif width == 3:
            cur = core.u24le(payload, pos)
        else:
            cur = core.u16le(payload, pos)
        if cur != old_val:
            skipped.append({"op_index": op_i, "delta": delta, "width": width, "old_value": old_val, "reason": "value_mismatch", "current_value": cur})
            continue
        new_val = off_map.get(old_val)
        if new_val is None:
            # Fallback for targets that are not exact op starts:
            # keep the intra-op delta against the nearest preceding op anchor.
            k = bisect.bisect_right(old_op_offsets, old_val) - 1
            if 0 <= k < len(new_op_offsets):
                inner = old_val - old_op_offsets[k]
                cand = new_op_offsets[k] + inner
                if 0 <= cand <= len(payload):
                    new_val = cand
                    patched_fallback += 1
        if new_val is None:
            skipped.append({"op_index": op_i, "delta": delta, "width": width, "old_value": old_val, "reason": "missing_off_map"})
            continue
        if width == 5:
            payload[pos + 1 : pos + 5] = core.p32le(new_val)
        elif width == 4:
            payload[pos : pos + 4] = core.p32le(new_val)
        elif width == 3:
            payload[pos : pos + 3] = core.p24le(new_val)
        else:
            payload[pos : pos + 2] = core.p16le(new_val)
        patched += 1
    return patched, patched_fallback, skipped


def relocate_payload_best_effort(
    *,
    base_payload_plain: bytes,
    new_payload: bytearray,
    new_sigs: list[tuple[Any, ...]] | None,
    new_offs: list[int] | None,
    header: bytes,
    old_header_off: int,
    new_header_off: int,
    spec: dict,
    text_encoding: str,
    strict: bool,
) -> tuple[bytearray, bytes, dict[str, Any]]:
    report: dict[str, Any] = {
        "mode": "strict" if strict else "best-effort",
        "patched_count": 0,
        "patched_fallback_count": 0,
        "skipped_sites": [],
        "unresolved_targets": [],
        "header_patches": 0,
        "warnings": [],
    }

    base_sigs, base_offs = core._iter_op_sigs_and_offsets_from_payload(
        base_payload_plain, spec=spec, text_encoding="cp932"
    )
    if new_sigs is None or new_offs is None:
        new_sigs, new_offs = core._iter_op_sigs_and_offsets_from_payload(
            bytes(new_payload), spec=spec, text_encoding="cp932"
        )
    if base_sigs != new_sigs:
        msg = f"opcode stream mismatch (base_ops={len(base_sigs)} new_ops={len(new_sigs)})"
        if strict:
            raise ValueError(msg)
        report["warnings"].append(msg)
        return new_payload, header, report

    off_map = {base_offs[i]: new_offs[i] for i in range(len(base_offs))}
    # Use precise jump/control-flow relocation sites to avoid over-patching
    # constants that coincidentally equal an old offset.
    sites = core._collect_relocation_sites_jump_only(
        base_payload_plain,
        spec=spec,
        text_encoding="cp932",
    )
    patched, patched_fallback, skipped = _apply_relocation_sites_detailed(
        new_payload,
        old_op_offsets=base_offs,
        new_op_offsets=new_offs,
        off_map=off_map,
        sites=sites,
    )
    report["patched_count"] = patched
    report["patched_fallback_count"] = patched_fallback
    report["skipped_sites"] = skipped
    unresolved: list[dict[str, int]] = []
    report["unresolved_targets"] = unresolved

    if strict:
        hard_skips: list[dict[str, Any]] = []
        if hard_skips or unresolved:
            raise ValueError(
                f"strict relocation failed, hard_skips={len(hard_skips)}, unresolved_targets={len(unresolved)}"
            )

    header2 = core._patch_header_offsets(
        header,
        off_map=off_map,
        old_header_off=old_header_off,
        new_header_off=new_header_off,
    )
    # Count changed dwords for visibility.
    hp = 0
    lim = min(len(header), len(header2))
    for i in range(0, lim - 3, 4):
        if header[i : i + 4] != header2[i : i + 4]:
            hp += 1
    report["header_patches"] = hp
    return new_payload, header2, report
