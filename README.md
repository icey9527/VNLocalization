# VNLocalization

存储一些研究过游戏的汉化工具
全部由我辅助Ai编写



| 平台 | 游戏名 | 支持的功能 |
| --- | --- | --- |
| NDS | Aquarian Age Perpetual Period | script parse/rebuild, font table generation, `SNCG` -> PNG conversion |
| NDS | Princess Maker 4 | `.bin` script parse/rebuild, font generation |
| PS2 | My Merry May With Be | `.bin` script parse/rebuild, `.klz` decompress/compress |
| PS2 | サクラ大戦V ～さらば愛しき人よ～ | `.msx` decompress/compress, `.msb` text extract/insert |
| PS2 | フタコイ オルタナティブ 恋と少女とマシンガン  | script parse/rebuild, font generation |
| PS2 | 銀のエクリプス / きると 貴方と紡ぐ夢と恋のドレス | `.pac` unpack/pack, `.lzs` decompress/compress, `.bin` script parse/rebuild |
| PS2 | 花と乙女に祝福を -春風の贈り物- | `cd.bin` unpack/pack, `.1tex` <-> `.png` conversion, `.1bin` script parse/rebuild, font generation |
| PS2 | To Heart | `.sfs` unpack/pack, `.ttp` <-> `.png` conversion,`script.dat` script parse/rebuild |
| PS2 | Ever17 | `.afs` unpack/pack, `.bin`/`init.bin` script parse/rebuild, font generation |
| PSP | EDEN / 僕の心は雨のち晴れ | `.ipb` script parse/rebuild, `.ipg` <-> `.png` conversion, font generation |
| WIN | Galaxy Angel Eternal Lovers | `.isb` script parse/rebuild, `.pak` movie decrypt |
| WIN | Galaxy Angel EX | text export/insert, font generation |
| WIN | To Heart PSE | `.pak` unpack/pack, `.lcf`/`.lff`/`.lfb` <-> `.png` conversion,`.dat` script parse/rebuild, font generation |
| WIN | To Heart REMAKE | `text.ttb` text decode/encode |
| WIN | プリズムパレット | `arc` unpack/pack, `.yx` script parse/rebuild |
| WIN | 家族計画 Re：紡ぐ糸 | `.adb` text extract/insert |
| WIN | 快盗天使ツインエンジェル　～幻の少女～ / （工画堂スタジオ的引擎）| `.kgo` text extract/insert |
| WIN | 空の森 ～追憶ノ棲ム館～ / 夏音-Overture- | `.axr` / `.ax2-.ax9` unpack/pack, `.scn` text extract/insert |



| 通用工具 | 说明 | 支持的功能 |
| --- | --- | --- |
| `VNTextract` | WinForms 文本提取工具 | scan readable plain text and extract Japanese lines, supports `alltxt` / `dltxt` / `Paratranz JSON` export/import |
| `krkr_dfm` | Windows PE `RT_RCDATA` binary DFM resource tool, mainly for krkr engine executables | extract/edit/insert Delphi or C++Builder DFM layout resources |
| `RealLive1.6.5.9 (不思議の国のカノジョ)` | RealLive script tool | parse/rebuild `seen.txt` internal `seen%04d.txt` scripts |

## Credits

- https://github.com/IanusInferus/firefly
- https://github.com/punk7890/PS2-Visual-Novel-Tool