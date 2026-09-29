del /q badchars.txt 2>nul
cd font
del /q js.txt font.txt font.tbl 2>nul
python tqjs.py ..\utf8\QBSC js.txt
CharAdder.exe js.txt font.txt /removeunicode:0000,2E7F /removeunicode:2E80,33FF /removeunicode:9FFF,FFFF
python mapping_tables.py filter Shift_JIS.tbl Shift_JIS.valid.tbl
MappingGen.exe Shift_JIS.valid.tbl font.txt font.generated.tbl /N /fixcode:8140,889E /fixcode:EAA5,F053
python mapping_tables.py merge font.generated.tbl Shift_JIS.tbl font.tbl
del /q Shift_JIS.valid.tbl font.generated.tbl 2>nul
python font.py SourceHanSansCN-Medium.otf font.tbl 0002.bin ..\extracted\shared.bin\0002.bin --offset -1
python rl16_map.py font.tbl 0000.rl16 ..\extracted\shared.bin\0006.lice\0000.rl16
cd ..
python logo.py w extracted utf8\QBSC extracted
python fixh.py w extracted utf8\QBSC extracted
python bin.py w extracted utf8\QBSC extracted
python mpak.py w extracted\map.bin utf8\QBSC\map.bin extracted\map.bin
python debug.py png\shared.bin\0008.lice\0000.png
gim e png extracted
qbsc.exe c BOOT.BIN extracted rebuilt
python elf_string.py w rebuilt\PSP_GAME\SYSDIR\EBOOT.BIN utf8\QBSC\EBOOT.json rebuilt\PSP_GAME\SYSDIR\EBOOT.BIN
armips backup\QBSC.asm
Ìæ»»¾µÏñÎÄ¼þ.bat
pause