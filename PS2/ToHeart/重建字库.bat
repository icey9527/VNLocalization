del badchars.txt
cd font
del /q js.txt font.txt new.tbl font22.new 2>nul
python tqjs.py ..\script js.txt
CharAdder js.txt font.txt /removeunicode:0000,2E7F /removeunicode:2E80,33FF /removeunicode:9FFF,FFFF
MappingGen 26x26x4.tbl font.txt font.tbl /fixcode:8140,889E
python wtfont.py