# PrismPalette プリズムパレット

## `.arc` Archive

```bash
python arc1.py u file.arc outdir    # unpack
python arc1.py p indir out.arc      # pack
python arc1.py u file.arc outdir -e cp932  # specify encoding
```

## `.GH` Images

```bash
python GH3.py d file.GH outdir      # decode to PNG
python GH3.py e file.png outdir     # encode to GH (requires list.xml)
```

## `.yx` Scripts

```bash
python yx.py d indir outdir         # disassemble to .asm
python yx.py e indir outdir         # assemble back to .yx
```

## Text Extraction & Rewriting

```bash
python yx_text.py e asm_dir txt_dir      # extract text
python yx_text.py w asm_dir txt_dir new_asm_dir  # write back modified text
```