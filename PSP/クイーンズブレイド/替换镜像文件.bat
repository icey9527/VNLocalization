@echo off
setlocal
set "ISO=Queen's Blade - Spiral Chaos (Japan).iso"

python iso_replace.py "%ISO%" rebuilt --dry-run || goto end
python iso_replace.py "%ISO%" rebuilt || goto end

:end
pause
