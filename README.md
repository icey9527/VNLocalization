# VNLocalization

仓库内主要是视觉小说/ADV 游戏汉化相关工具，按平台和游戏分类整理。

## 游戏

| 平台 | 游戏名 | 支持的功能 |
| --- | --- | --- |
| NDS | Aquarian Age Perpetual Period | script parse/rebuild, font table generation, SNCG -> PNG conversion |
| NDS | Princess Maker 4 | `.bin` <-> `.asm`, script text extract/insert, font generation |
| PS2 | My Merry May With Be | `.bin` script parse/rebuild, `.klz` decompress/compress |
| PS2 | サクラ大戦V ～さらば愛しき人よ～ | `.msx` decompress/compress, `.msb` text editing |
| PS2 | 双恋 | script parse/rebuild, font generation |
| PS2 | 銀のエクリプス / きると 貴方と紡ぐ夢と恋のドレス | `.pac` unpack/pack, `.lzs` decompress/compress, `.bin` script parse/rebuild |
| PSP | EDEN / 僕の心は雨のち晴れ | `.ipb` script parse/rebuild, `.ipg` -> `.png` conversion, font generation |
| WIN | Galaxy Angel Eternal Lovers | `.isb` script parse/rebuild, `.pak` movie decrypt |
| WIN | Galaxy Angel EX | text export/insert, font generation |
| WIN | ToHeartPSE | `.pak` unpack/pack, `.dat` script parse/rebuild, font generation |
| WIN | プリズムパレット | `arc` unpack/pack, `.yx` text export/insert |
| WIN | 家族計画 Re：紡ぐ糸 | `.adb` text extract/insert |
| WIN | 快盗天使ツインエンジェル　～幻の少女～ | `.kgo` text extract/insert |
| WIN | 空の森 ~追憶ノ棲ム館~ / 夏音-Overture- | `.axr` / `.ax2-.ax9` unpack/pack, `.scn` text extract/insert |

## 通用工具

| 工具 | 说明 | 支持的功能 |
| --- | --- | --- |
| `VNTextract` | WinForms 文本提取工具 | scan readable plain text and extract Japanese lines, supports `alltxt` / `dltxt` / `Paratranz JSON` export/import |
| `krkr_dfm` | Windows PE `RT_RCDATA` binary DFM resource tool, mainly for krkr engine executables | extract/edit/insert Delphi or C++Builder DFM layout resources |
| `RealLive1.6.5.9 (不思議の国のカノジョ)` | RealLive script tool | parse/rebuild `seen.txt` internal `seen%04d.txt` scripts |
