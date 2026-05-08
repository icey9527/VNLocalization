# ToHeart PS2 Tools

## `.sfs` file

```bash
ToHeartPS2 SLPS_254.12 ToH_DATA.sfs ToH_DATA    # unpack (auto-converts images)
ToHeartPS2 SLPS_254.12 ToH_DATA new\ToH_DATA.sfs new\SLPS_254.12    # pack (auto-converts images)
```

## `script.dat` script

```bash
python scn.py d script.dat script SLPS_254.12   # decode to .asm + .txt
python scn.py e script new\script.dat SLPS_254.12 new\SLPS_254.12 [mapping table]   # rebuild .dat
```



## Translation

- Edit only `.txt` files
- Do not add or remove lines
- Use fullwidth characters only


## Font（中文）

```bash
重建字库.bat
```