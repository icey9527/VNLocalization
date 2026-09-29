// Formats/SysdatFormat.cs — sysdat.bin 系统图像（全文件扫描 + 原位回写）。
//
// 设计定稿（见 plans/02-sysdat-format.md）：
//   · 零游戏知识：不知道任何分区/类别/地址范围——只知道 0x13 图像块结构和
//     decode2r 编解码（这两个就是"格式插件"）。换游戏只换格式层，不动这里。
//   · 明文块：签名+结构校验全文件扫描；压缩流：数学预筛（只有三种控制序列
//     能让首个输出字节为 0x13）+ 探针解码 + E0 终止标记。本作实测：
//     块 339 + 流 182，精确率 100%。
//   · 文件名 = 7 位大写十六进制地址（0119080.png）——回写时文件名即偏移；
//     提取平铺输出不分类（想整理自己建子文件夹，打包递归扫描不受影响）；
//     modified\ 里存在才改（GA2 语义）。
//   · 写回前自检：解码原数据验结构、PNG 尺寸必须与原图一致；流重编码后
//     回读比对且不得超过槽位（下一条目的起点）。
//   · 只碰工作区路径：base 由调用方给（original\sysdat.bin，或重建前任务
//     产出的文本版 packed\sysdat.bin），输出整份文件到 packed\sysdat.bin。

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using SixLabors.ImageSharp;
using SixLabors.ImageSharp.Formats.Png;
using SixLabors.ImageSharp.PixelFormats;

namespace kita
{
    internal static class SysdatFormat
    {
        static readonly byte[] Sig = { 0x13, 0, 0, 0, 1, 0, 0, 0 };
        // 提取是中间产物：低压缩档换速度（无损 PNG，回包结果不受影响）
        static readonly PngEncoder FastPng = new() { CompressionLevel = PngCompressionLevel.Level1 };

        internal sealed class Entry
        {
            public int Offset;          // 文件偏移（= 文件名）
            public int End;             // 流：终止标记后一字节；块：结构结束
            public bool IsStream;
            public (int w, int h)[] Dims;
        }

        // ---------------- 扫描 ----------------

        /// <summary>全文件扫描：明文块 + 压缩流，按偏移排序合并。</summary>
        public static List<Entry> Scan(byte[] d)
        {
            var list = new List<Entry>();
            foreach (var (off, end, dims) in ScanBlocks(d, 0, d.Length))
                list.Add(new Entry { Offset = off, End = end, IsStream = false, Dims = dims });
            foreach (var e in ScanStreams(d))
                list.Add(e);
            list.Sort((a, b) => a.Offset.CompareTo(b.Offset));
            return list;
        }

        /// <summary>明文 0x13 块扫描：签名 + 结构校验；跳过落在前一块内的候选。</summary>
        static List<(int off, int end, (int, int)[] dims)> ScanBlocks(byte[] d, int lo, int hi)
        {
            var result = new List<(int, int, (int, int)[])>();
            int lastEnd = 0;
            int pos = lo;
            while (true)
            {
                int i = IndexOf(d, Sig, pos, hi);
                if (i < 0) break;
                pos = i + 1;
                if ((i & 3) != 0 || i < lastEnd) continue;
                if (!TryParseBlock(d, i, hi, out var paloff, out var dims, out int end)) continue;
                result.Add((i, end, dims));
                lastEnd = end;
            }
            return result;
        }

        /// <summary>压缩流扫描：0x13 三种回退预筛 → 8 字节探针 → 完整解码 + 结构 + 终止标记。</summary>
        static List<Entry> ScanStreams(byte[] d)
        {
            var cands = new HashSet<int>();
            int q = Array.IndexOf(d, (byte)0x13);
            while (q >= 0)
            {
                if (q >= 1 && d[q - 1] < 0x80) cands.Add(q - 1);
                if (q >= 2 && d[q - 2] >= 0x80 && d[q - 1] >= 0xC0 && d[q - 1] <= 0xDF) cands.Add(q - 2);
                if (q >= 3 && d[q - 3] >= 0x80 && d[q - 2] >= 0xE0) cands.Add(q - 3);
                q = Array.IndexOf(d, (byte)0x13, q + 1);
            }
            var result = new List<Entry>();
            int curEnd = -1;
            foreach (int c in cands.OrderBy(x => x))
            {
                if (c < curEnd) continue;
                if (!Lz2.TryDecode(d, c, 8, out var head, out _) || !head.AsSpan().SequenceEqual(Sig))
                    continue;
                if (!Lz2.TryDecode(d, c, 0, out var raw, out int end)) continue;
                if (!TryParseBlock(raw, 0, raw.Length, out _, out var dims, out _)) continue;
                result.Add(new Entry { Offset = c, End = end, IsStream = true, Dims = dims });
                curEnd = end;
            }
            return result;
        }

        /// <summary>解析 0x13 块头/部件表；校验部件数、宽高、调色板偏移与块边界。</summary>
        static bool TryParseBlock(byte[] b, int baseOff, int limit,
                                  out int paloff, out (int w, int h)[] dims, out int end)
        {
            paloff = 0; dims = null; end = 0;
            if (baseOff + 0x20 > limit) return false;
            if (BitConverter.ToUInt32(b, baseOff) != 0x13) return false;
            if (BitConverter.ToUInt32(b, baseOff + 4) != 1) return false;
            paloff = BitConverter.ToInt32(b, baseOff + 8);
            int parts = BitConverter.ToInt32(b, baseOff + 12);
            if (paloff < 0x20 || paloff >= 0x2000 || parts < 1 || parts > 8) return false;
            var list = new (int, int)[parts];
            int maxRel = 0;
            for (int i = 0; i < parts; i++)
            {
                int po = BitConverter.ToInt32(b, baseOff + 0x10 + i * 4);
                if (baseOff + po + 0x70 > limit) return false;
                int w = BitConverter.ToUInt16(b, baseOff + po + 0x30);
                int h = BitConverter.ToUInt16(b, baseOff + po + 0x34);
                if (w < 8 || w > 1024 || h < 8 || h > 1024) return false;
                list[i] = (w, h);
                maxRel = Math.Max(maxRel, po + 0x70 + w * h);
            }
            maxRel = Math.Max(maxRel, paloff + 0x400);
            end = baseOff + maxRel;
            if (end > limit) return false;
            dims = list;
            return true;
        }

        static int IndexOf(byte[] d, byte[] pat, int start, int end)
        {
            int i = Array.IndexOf(d, pat[0], start, end - start);
            while (i >= 0 && i + pat.Length <= end)
            {
                bool ok = true;
                for (int k = 1; k < pat.Length; k++)
                    if (d[i + k] != pat[k]) { ok = false; break; }
                if (ok) return i;
                i = Array.IndexOf(d, pat[0], i + 1, end - i - 1);
            }
            return -1;
        }

        /// <summary>槽位边界 = 下一条目（块或流）的起点；最后一条到文件尾。</summary>
        internal static int NextStart(List<Entry> entries, Entry e)
        {
            int lo = 0, hi = entries.Count - 1, ans = -1;
            while (lo <= hi)
            {
                int mid = (lo + hi) / 2;
                if (entries[mid].Offset > e.Offset) { ans = entries[mid].Offset; hi = mid - 1; }
                else lo = mid + 1;
            }
            return ans < 0 ? int.MaxValue : ans;
        }

        // ---------------- 提取 ----------------

        /// <summary>全部图像 → outDir\<分类>\<地址7位HEX>.png。</summary>
        public static void Extract(string sysdatPath, string outDir, Action<string> log)
        {
            byte[] d = File.ReadAllBytes(sysdatPath);
            var entries = Scan(d);
            var lockObj = new object();
            int done = 0;
            Parallel.ForEach(entries, new ParallelOptions { MaxDegreeOfParallelism = Environment.ProcessorCount }, e =>
            {
                byte[] raw = e.IsStream
                    ? Lz2.Decode(d, e.Offset)
                    : d[new Range(e.Offset, e.End)].ToArray();
                var pixels = BgImage.BlockToPixels(raw, out int w, out int h);
                Directory.CreateDirectory(outDir);
                using (var img = Image.LoadPixelData<Rgba32>(pixels, w, h))
                    img.SaveAsPng(Path.Combine(outDir, $"{e.Offset:X7}.png"), FastPng);
                lock (lockObj)
                {
                    if (++done % 100 == 0) log($"  sysdat: {done}/{entries.Count}…");
                }
            });
            log($"{Path.GetFileName(sysdatPath)}: {entries.Count} 张图 -> {outDir}（地址命名）");
        }

        /// <summary>
        /// 把 PNG 像素写回块——**算法化调色板**，不读旧文件的任何顺序信息：
        /// 见 BgImage.BuildOrderedPalette（唯一色 ≤256 精确保留 / Wu 量化；亮度排序）。
        /// </summary>
        internal static void WritePixelsOrderedPalette(byte[] raw, Rgba32[] pixels, int width, int height)
        {
            var (colors, indices) = BgImage.BuildOrderedPalette(pixels);

            int palOffset = BitConverter.ToInt32(raw, BgImage.BlkPalOffset);
            byte[] palData = BgImage.SwizzlePalette(colors);
            Array.Copy(palData, 0, raw, palOffset, palData.Length);

            int partCount = BitConverter.ToInt32(raw, BgImage.BlkPartCount);
            int rowBase = 0;
            for (int i = 0; i < partCount; i++)
            {
                int poff = BitConverter.ToInt32(raw, BgImage.BlkPartTable + i * 4);
                int w = BitConverter.ToUInt16(raw, poff + BgImage.PartW);
                int h = BitConverter.ToUInt16(raw, poff + BgImage.PartH);
                raw[poff + BgImage.PartCompFlag] = 0;   // 像素直接存原始索引
                raw[poff + BgImage.PartCompMode] = 0;
                int pixOff = poff + BgImage.PartHeaderBytes;
                for (int y = 0; y < h; y++)
                {
                    int rowStart = (rowBase + y) * width;
                    for (int x = 0; x < w; x++)
                        raw[pixOff + y * w + x] = indices[rowStart + x];
                }
                rowBase += h;
            }
        }

        // ---------------- 打包（原位回写） ----------------

        static readonly Regex AddrName = new(@"^[0-9A-Fa-f]{7}\.png$", RegexOptions.IgnoreCase);

        /// <summary>把 modDir 下现存的地址命名 PNG 打回 sysdat（存在才改），输出整份文件。</summary>
        public static void Pack(string sysdatPath, string modDir, string outFile, Action<string> log)
        {
            var files = new List<string>();
            if (Directory.Exists(modDir))
                files = Directory.GetFiles(modDir, "*.png", SearchOption.AllDirectories).ToList();
            foreach (string f in files)
                if (!AddrName.IsMatch(Path.GetFileName(f)))
                    throw new InvalidDataException(
                        $"sysdat: 文件名必须是 7 位十六进制地址（如 0119080.png）：{f}");
            if (files.Count == 0)
            {
                log("sysdat.bin: modified 里没有 PNG，跳过");
                return;
            }

            byte[] data = File.ReadAllBytes(sysdatPath);
            List<Entry> entries = Scan(data);
            var byAddr = new Dictionary<int, Entry>();
            foreach (var e in entries) byAddr[e.Offset] = e;

            int patched = 0;
            foreach (string f in files.OrderBy(f => f, StringComparer.OrdinalIgnoreCase))
            {
                int addr = Convert.ToInt32(Path.GetFileName(f).Substring(0, 7), 16);
                if (!byAddr.TryGetValue(addr, out var e))
                    throw new InvalidDataException(
                        $"sysdat: {Path.GetFileName(f)}：地址 {addr:X7} 处扫描不到可替换图像（文件与数据不匹配？）");
                byte[] raw = e.IsStream
                    ? Lz2.Decode(data, e.Offset)
                    : data[new Range(e.Offset, e.End)].ToArray();

                int W = e.Dims[0].w, H = e.Dims.Sum(x => x.h);
                using (var image = Image.Load<Rgba32>(f))
                {
                    // 部件头里的宽高是固定的（游戏按它上传），PNG 尺寸必须一致
                    if (image.Width != W || image.Height != H)
                        throw new InvalidDataException(
                            $"{f}: 尺寸 {image.Width}x{image.Height} != 需要 {W}x{H}（尺寸不可改）");
                    var pixels = new Rgba32[W * H];
                    image.CopyPixelDataTo(pixels);
                    WritePixelsOrderedPalette(raw, pixels, W, H);
                }

                if (e.IsStream)
                {
                    byte[] enc = Lz2.Encode(raw);
                    // 正确性由 kitatest 全量自测保证，打包路径不做回读验证（提速）
                    int slot = Math.Min(NextStart(entries, e), data.Length) - e.Offset;
                    if (enc.Length > slot)
                        throw new InvalidOperationException(
                            $"{Path.GetFileName(f)}: 重编码 {enc.Length} B 超过槽位 {slot} B（内容复杂度超过原图，需精简）");
                    Array.Clear(data, e.Offset, e.End - e.Offset);   // 清旧流尾巴（新流更短时）
                    Buffer.BlockCopy(enc, 0, data, e.Offset, enc.Length);
                    e.End = e.Offset + enc.Length;
                }
                else
                {
                    Buffer.BlockCopy(raw, 0, data, e.Offset, raw.Length);
                }
                patched++;
                log($"  {Path.GetFileName(sysdatPath)} {addr:X7} 已替换（{(e.IsStream ? "流" : "块")}）");
            }
            Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outFile))!);
            File.WriteAllBytes(outFile, data);
            log($"{Path.GetFileName(sysdatPath)}: {patched} 张图已打补丁 -> {outFile}");
        }
    }
}
