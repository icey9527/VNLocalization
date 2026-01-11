空の森 ～追憶ノ棲ム館～ / 夏音-Overture-


AX*文件采用多文件映射同一路径，命中即止（有点类似krkr之类的引擎）。游戏查找顺序为ax9→ax2→axr）。


解包：python axr.py u *.axr/ax[2~9] output_dir

打包：python axr.py p input_dir .*axr/ax[2~9]


提取文本：python scn.py d scn_dir output_dir

写回文本：python scn.py e scn_dir txt_dir output_dir 