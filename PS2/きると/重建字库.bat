del badchars.txt
cd font
del /q js.txt font.txt new.tbl font22.new 2>nul
python tqjs.py ..\txt_chs js.txt
CharAdder js.txt font.txt /removeunicode:0000,2E7F /removeunicode:2E80,33FF /removeunicode:9FFF,FFFF
MappingGen Shift_JIS.tbl font.txt font.tbl /fixcode:8140,889E
python wtfont.py
lzs p font22.new ..\chs\font22.lz 