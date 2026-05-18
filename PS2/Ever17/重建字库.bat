cd font
python tqtxt.py ..\txt_chs js.txt
CharAdder js.txt font.txt /removeunicode:0000,2E7F /removeunicode:2E80,33FF /removeunicode:9FFF,FFFF
MappingGen Shift_JIS.tbl font.txt font.tbl /fixcode:8140,889E
python font.py c font.ttf font.tbl ..\new\etc\FNT2626.FOP -b FNT2626.FOP -n
pause
