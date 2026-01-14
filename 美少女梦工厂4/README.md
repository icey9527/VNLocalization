1) pm4_asm.py（脚本反汇编/汇编）

- 反汇编：bin → asm

python pm4_asm.py d bin目录 asm输出目录 码表.tbl


- 汇编：asm → bin

python pm4_asm.py e asm目录 bin输出目录 码表.tbl



2) createfont.py（生成字库）

修改脚本末尾参数后直接运行：

python createfont.py


3) pm4_all.py（文本提取/写回）

- 提取（从 asm 目录生成 all.txt / lines.txt / MESSAGE_NAME.json / SELECT.json，输出在当前目录）

python pm4_all.py e asm目录


- 写回（读取当前目录的 all.txt / lines.txt / MESSAGE_NAME.json / SELECT.json，写回到输出目录）

python pm4_all.py w asm目录 输出目录




打包：pm4_data p output arm9.bin I:\研究\nds\dump2\pack_data\arm9.bin I:\研究\nds\dump2\pack_data\data\data.bin 0x9143C