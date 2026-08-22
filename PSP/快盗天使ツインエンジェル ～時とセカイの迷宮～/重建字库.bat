del /q badchars.txt 2>nul
cd font
del /q js.txt font.txt font.tbl 2>nul
python tqjs.py ..\utf8 js.txt
CharAdder.exe js.txt font.txt /removeunicode:0000,2E7F /removeunicode:2E80,33FF /removeunicode:9FFF,FFFF
MappingGen.exe Shift_JIS.tbl font.txt font.tbl /fixcode:8140,889E /fixcode:EAA5,F053
python font.py font.tbl SourceHanSansCN-Medium.otf ..\data1_chs
pause
