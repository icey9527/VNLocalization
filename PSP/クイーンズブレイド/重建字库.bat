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
pause
