@echo off
rem ============================================================
rem  写回文本.bat - prepack entry (called by kita pack, cwd = workspace)
rem  NOTE: keep this file ASCII-only! cmd parses bat with the system
rem  ANSI codepage; Chinese comments break it. Python output is forced
rem  to UTF-8 via PYTHONIOENCODING so the kita log stays clean.
rem  Any step failing exits non-zero and kita aborts the pack.
rem ============================================================
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

echo ==== [1/5] scn_txt ====
python scn_txt.py w work\raw\asm work\utf8\scr work\raw\asm_cn || exit /b 1

echo ==== [2/5] bg_name ====
python bg_name.py w work\raw\asm_cn work\utf8\bg_name.json || exit /b 1

echo ==== [3/5] scn blocks ====
python scn.py e work\raw\asm_cn work || exit /b 1

echo ==== [4/5] sysdat map text (original -^> packed) ====
python sysdat.py w work\utf8\map.json work\original\sysdat.bin work\packed\sysdat.bin || exit /b 1

echo ==== [5/5] elf_string ====
python elf_string.py w kita\SLPM_654.04 work\utf8\SLPM_654.04.json kita\SLPM_654.04 || exit /b 1

echo ==== prepack all done ====
