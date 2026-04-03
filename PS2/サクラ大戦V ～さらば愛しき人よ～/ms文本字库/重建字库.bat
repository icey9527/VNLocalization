del badchars.txt
cd font
del /q js.txt font.txt new.tbl FIRSTREAD.BIN 2>nul
python js.py ..\txt js.txt
CharAdder js.txt font.txt /removeunicode:0000,2E7F /removeunicode:2E80,33FF /removeunicode:9FFF,FFFF
MappingGen Shift_JIS.tbl font.txt font.tbl /fixcode:8140,889E
python refont.py FIRSTREAD.raw font.tbl FIRSTREAD.BIN