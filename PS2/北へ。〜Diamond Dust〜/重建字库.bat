chcp 65001
del badchars.txt
cd font
del /q js.txt font.txt font.tbl  2>nul
python tqjs.py ..\work\utf8 js.txt
CharAdder js.txt font.txt /removeunicode:0020,007F /removeunicode:2000,2FFF /removeunicode:9FFF,FFFF
MappingGen Shift_JIS.tbl font.txt font.tbl /fixcode:8140,889E /fixcode:EAA5,F053
python font.py font.tbl HKStdW9.ttf SLPM_654 ..\kita\SLPM_654.04 0xbaa20
pause