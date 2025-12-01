font 22x22 4bpp

  Decompress: lzs U font22.lz font22.bin

  Compress:   lzs P font22.bin font22.lz

Unpacking code from [PS2-Visual-Novel-Tool](https://github.com/punk7890/PS2-Visual-Novel-Tool)

  Unpack: pac U <input.pac> <output_folder>
  
  Pack:   pac P <input_folder> <output.pac>


TAK SCRIPT

  Extract: python tak.py e <input_folder> <output_folder> <-t ELF NameTableAddress>
  
           python tak.py e tak csv -t slpm_669.80 0x18c718
    
  Repack: python tak.py w <original_bin_folder> <csv_folder> <output_folder> 

When dealing with complex game script formats, analyzing and rebuilding the entire instruction set can be extremely challenging. Instead of reverse-engineering every command and regenerating assembly code, I adopted a simpler "Jump Trampoline" approach.

The method uses the `0x00` instruction for unconditional jumps to redirect text display commands. When encountering a `0x42` text command, it's replaced with `0x00` that jumps to newly appended content at the file's end. After displaying the translated text, another `0x00` jumps back to resume normal execution.

This technique preserves the original file structure while allowing unlimited translation length without breaking the complex instruction dependencies.

在处理复杂的游戏脚本格式时，分析和重建整个指令集是极其困难的。我没有选择逆向工程每个命令然后重新生成汇编代码，而是采用了更简单的"跳转蹦床"方法。

该方法利用 `0x00` 指令进行无条件跳转来重定向文本显示命令。遇到 `0x42` 文本指令时，将其替换为 `0x00` 跳转到文件末尾新追加的内容。显示完翻译文本后，再用另一个 `0x00` 跳回原位置继续正常执行。

这种技术既保持了原始文件结构，又允许无限长度的翻译，而不会破坏复杂的指令依赖关系。