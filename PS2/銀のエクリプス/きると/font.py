#!/usr/bin/env python3
# -*- coding: utf-8 -*-

def sub_101BC8(code: int) -> int:
    low = code & 0xFF
    high = (code >> 8) & 0xFF

    v1 = high - 0x81
    if 0 <= high - 0xE0 < 0x10:
        v1 = high - 0xC1
    elif not (0 <= high - 0x81 < 0x1F):
        raise ValueError("invalid high")

    v0 = 2 * v1

    if 0 <= low - 0x40 < 0x3F:
        a0 = low - 0x40
    elif 0 <= low - 0x80 < 0x1F:
        a0 = low - 0x41
    elif 0 <= low - 0x9F < 0x5E:
        a0 = low - 0x9F
        v0 += 1
    else:
        raise ValueError("invalid low")

    return (((v0 + 1) << 8) + a0 + 0x2021)


def generate_font_tbl(out_path="font.tbl"):
    lines = []

    for high in range(0x00, 0x100):
        for low in range(0x00, 0x100):
            code = (high << 8) | low
            try:
                jis = sub_101BC8(code)
                ch = bytes([high, low]).decode("cp932")
                lines.append(f"{jis:04X}={ch}")
            except Exception:
                continue

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"已生成: {out_path}")


if __name__ == "__main__":
    generate_font_tbl()