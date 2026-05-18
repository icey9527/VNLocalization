chcp 65001
if not exist txt_chs (echo txt_chs不存在，请把txt文件夹改名成txt_chs && pause && exit /b)
xcopy /E /Y scn\asm scn\new_asm
python txt.py w txt_chs scn\new_asm
kid_opcode e scn\new_asm new
pause