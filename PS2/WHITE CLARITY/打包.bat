del badchars.txt
cd font
del /q js.txt font.txt font.tbl 2>nul
python js.py ..\txt js.txt
CharAdder js.txt font.txt /removeunicode:0000,2E7F /removeunicode:2E80,33FF /removeunicode:9FFF,FFFF
MappingGen k24.tbl font.txt font.tbl /fixcode:8140,889E /fixcode:9873,989E
python wtfont.py

cd ..

python mes.py i mes txt bind
AFSPacker -c bind chs\bind.afs
pause