# ToHeart PSE Tools

## `.pak` file

```bash
ToHeartPSE file.pak outdir    # unpack (auto-converts images)
ToHeartPSE indir out.pak      # pack (auto-converts images)
```

## `.dat` script

```bash
python dat.py d indir outdir   # decode to .asm + .txt
python dat.py e indir outdir   # rebuild .dat
```

Add `-e cp932` for Japanese encoding.

## Translation

- Edit only `.txt` files
- Do not add or remove lines
- Use fullwidth characters only

## Quick jump

Add `dat_call(...)` at top of `.asm` to jump to another script.

## Font

```bash
cd font
python refont.py
```