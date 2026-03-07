from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from . import core
from .parse import read_kprl_new
from .reloc import relocate_payload_best_effort


def encode_file(
    in_path: Path,
    out_path: Path,
    *,
    spec: dict,
    text_encoding: str,
    hashcall_map: dict[tuple[int, int, int, int], Any],
    opfmt_map: dict[object, list[Optional[str]]],
    reloc_mode: str = "best-effort",
) -> dict[str, Any]:
    header, ver, xlen, enc_in_file, nodes = read_kprl_new(
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
        base_path = core._find_base_seen_for_kprl(in_path)
        if base_path is not None and base_path.is_file():
            base_data = base_path.read_bytes()
            _, base_off, _ = core.parse_seen_hdr(base_data)
            base_header_off = int(base_off)
            base_payload_plain = core._decode_seen_plain_payload(base_path)
    except Exception:
        base_payload_plain = None

    work_nodes = nodes
    if reloc_mode == "len-lock":
        if base_payload_plain is None:
            raise ValueError("base seen file not found for len-lock mode")
        work_nodes = core._lock_text_nodes_to_base_lengths(
            nodes,
            base_payload_plain=base_payload_plain,
            spec=spec,
            new_text_encoding=enc,
            base_text_encoding="cp932",
        )

    new_sigs, new_offs = core._iter_op_sigs_and_offsets_from_nodes(
        work_nodes,
        spec=spec,
        text_encoding=enc,
    )
    payload = bytearray(core.encode_nodes(work_nodes, spec, text_encoding=enc, prefer_raw=True))
    report: dict[str, Any] = {
        "file": in_path.name,
        "mode": reloc_mode,
        "patched_count": 0,
        "skipped_sites": [],
        "unresolved_targets": [],
        "header_patches": 0,
        "warnings": [],
    }

    if reloc_mode not in ("off", "len-lock"):
        if base_payload_plain is None or base_header_off is None:
            msg = "base seen file not found for relocation"
            if reloc_mode == "strict":
                raise ValueError(msg)
            report["warnings"].append(msg)
        else:
            strict = reloc_mode == "strict"
            payload, header, rep2 = relocate_payload_best_effort(
                base_payload_plain=base_payload_plain,
                new_payload=payload,
                new_sigs=new_sigs,
                new_offs=new_offs,
                header=header,
                old_header_off=base_header_off,
                new_header_off=len(header),
                spec=spec,
                text_encoding=enc,
                strict=strict,
            )
            report.update(rep2)

    core.apply_seen_version_layers(payload, ver)
    if xlen:
        core.apply_seen_xor_layer(payload, xlen)
    header = core._patch_seen_payload_len_in_header(header, len(payload))
    out_path.write_bytes(header + payload)
    return report
