# VNTextractor (明文文本提取/写回工具)

WinForms UI + 可扩展的导出器结构（后续支持二进制时，可以新增解析器/导出器，不需要推翻 UI）。

## 运行

- 已发布可执行文件（单文件）：`dist/VNTextractor.exe`
- 自行打包（单文件、不带运行时）：`dotnet publish src/VNTextractor.WinForms/VNTextractor.WinForms.csproj -c Release -r win-x64 --self-contained false -o dist`

## 配置

- 会在 exe 同目录生成/读取：`VNTextractor.ini`（选项变化会自动更新）

## 提取规则

- 逐行读取，不使用 `Trim()` 之类的“通用去除特殊字符”方式；只去掉换行（`ReadLine()` 自带）。
- 判断是否包含日文/全角符号：使用字符范围正则（与 `scn.py` 一致）。
- 可勾选跳过注释：` ; `、` // `（允许行首有空白/Tab；`//` 支持行内注释判定）。

## 导出

分开导出：输出目录不再创建 `alltxt/ dltxt/ paratranz/` 这类分类子文件夹（只会按源文件相对路径创建必要的子目录）。

- `alltxt/`
  - 分开导出：每个源文件生成一个 `原文件名 + .txt`，并生成 `lines.txt`
  - 合并导出：生成 `all.txt` 和 `lines.txt`
- `dltxt/`
  - 双行格式：每条包含 `#key`、`◇原文`、`◆译文(预填原文)`、空行
- `paratranz/`
  - Paratranz JSON：`[{ key, original, translation, stage }]`
  - `stage` 默认输出为 `0`（按你的要求不处理翻译状态）

合并导出：输出直接写到你选择的“输出文件”（alltxt 合并时会在同目录生成 `lines.txt`）。

## 写回

- UI 的“导入(写回)”页：支持 alltxt / dltxt / Paratranz JSON（分开/合并两种输入方式）。
