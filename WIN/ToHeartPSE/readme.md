# ToHeart PSE Tools

## Usage

### `pak.py`

Unpack a `.pak` file:

```bash
python pak.py u input.pak output_dir
```

Pack a folder back to `.pak`:

```bash
python pak.py p input_dir output.pak
```

### `dat.py`

Decode DAT scripts to `.asm` and `.txt`:

```bash
python dat.py d input_dir output_dir
```

Rebuild DAT scripts from `.asm` and `.txt`:

```bash
python dat.py e input_dir output_dir
```

Optional encoding:

```bash
python dat.py d input_dir output_dir -e cp932
python dat.py e input_dir output_dir -e cp932
```

## Translation Notes

`dat.py` converts script files into `.asm` and `.txt`.

In most cases, translation only needs to edit the `.txt` files.

Keep the line numbers exactly the same. The `.asm` script references text by line number, so adding or removing lines will break the script.

The game does not support halfwidth characters. Do not use ASCII letters, ASCII numbers, or halfwidth kana in translated text. Use fullwidth characters only.

## Quick Script Jump

If you want to test a script quickly, you can edit the `.asm` file and add a `dat_call(...)` command near the beginning of the script to jump to another script.


## Font

Font files are in the `font` folder.

Build the font data:

```bash
cd font
python refont.py
```

`refont.py` reads `gbk.tbl`, uses the font file configured inside the script, and generates `FONTEX24.FD0`.

If `psth.exe` is in the same folder, the script will also patch the character range table inside the executable.
