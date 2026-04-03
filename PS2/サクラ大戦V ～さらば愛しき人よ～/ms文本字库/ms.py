#!/usr/bin/env python3
import sys, struct, re
from pathlib import Path
import char

char.MAP_PATH = Path('font/font.tbl')

u32 = lambda b, o: struct.unpack_from("<I", b, o)[0]
p32 = lambda v: struct.pack("<I", v)

def parse(p: Path):
    b = p.read_bytes()
    if b[:4] != b"MSCR": raise ValueError("Not MSCR")
    ds, hs = u32(b, 4), u32(b, 8)
    py = b[hs:hs+ds]
    so, sc, mo, mc = u32(py, 8), u32(py, 12), u32(py, 16), u32(py, 20)
    
    m_ref = max((max(u32(py, mo+i*16+4), u32(py, mo+i*16+12)) for i in range(mc)), default=0)
    if m_ref >= so: raise ValueError("Bad layout")
    
    txts = [py[so+u32(py, so+i*4):py.find(0, so+u32(py, so+i*4))].decode("cp932", "ignore") for i in range(sc)]
    return b, hs, py, so, sc, txts

def extract(src_d: Path, dst_d: Path, rm_tags: bool):
    for f in src_d.rglob("*"):
        if f.suffix.lower() not in (".msx", ".msb"): continue
        try:
            txts = parse(f)[5]
            if rm_tags:
                txts = [re.sub(r"<SPD=[^>]+>", "", t) for t in txts]
            txts = [t.replace("//", "\\n") for t in txts]
            out = dst_d / f.relative_to(src_d).with_name(f.name + ".txt")
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text("\n".join(txts), "utf-8")
        except Exception as e:
            print(f"E: {f.name} - {e}")

def write(txt_d: Path, base_d: Path, out_d: Path):
    for f in txt_d.rglob("*.txt"):
        rel = f.relative_to(txt_d)
        base = base_d / rel.with_suffix('')
        if not base.exists(): continue
        try:
            lines = [conv(x.replace("\\n", "//")) for x in f.read_text("utf-8").splitlines()]
            
            b, hs, py, so, sc, _ = parse(base)
            if len(lines) != sc: raise ValueError("Count mismatch")
            
            offs, uniq, t_dat, cur = [], {}, bytearray(), sc * 4
            for s in lines:
                enc = s.encode("cp932", "ignore") + b'\0'
                if enc not in uniq:
                    uniq[enc] = cur
                    t_dat += enc
                    cur += len(enc)
                offs.append(uniq[enc])
            
            n_py = py[:so] + b"".join(p32(o) for o in offs) + t_dat
            out = bytearray(b[:hs]) + n_py + b[hs+len(py):]
            out[4:8] = p32(len(n_py))
            
            dst = out_d / rel.with_suffix('')
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(out)
        except Exception as e:
            print(f"E: {f.name} - {e}")

if __name__ == "__main__":
    a = sys.argv[1:]
    if not a: sys.exit(0)
    
    if a[0] == "e":
        rm = "-l" in a
        a = [x for x in a if x != "-l"]
        extract(Path(a[1]), Path(a[2]), rm)
    elif a[0] == "w":
        conv = char.make_translation_converter()
        write(Path(a[1]), Path(a[2]), Path(a[3]))