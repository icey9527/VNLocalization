// Formats/CbdFormat.cs — CBD 立绘（记录式布局 + 部件像素 RLE mode8）。
//
// 格式（汇编验证 CBD_Set 0x121F60 + 全量文件考察，见 plans/03-cbd-p2x.md）：
//   · 文件 = 连续记录：[0x10 前缀(1,0…0)][0x100 描述符][0x13 图像块][补零到 0x800 对齐]；
//     记录内还可能跟着子块（表情/眼/嘴变体，前置 0x110 区域结构略有出入）。
//     扫描不区分记录/子块；回写只做块内原位替换，槽位边界 = 下一块起点 − 0x110
//     （保护后继块的描述符/前缀区，宁可少用 0x110 也不碰它）。
//   · 块结构与 sysdat 相同（0x13|1|调色板偏移|部件数|部件表|0x400 调色板|部件），
//     差别在部件像素：+0x68=1 且 (+0x69>>3)==1 时为 RLE mode8，+0x60 = 压缩长度，
//     按输入耗尽解压（解出必须恰好 = w*h）。flag=0 为原始索引（实测仅 4 处）。
//   · RLE 语义：token c → n=(c&0x7F)+1；c&0x80 → 读 1 字节重复 n 次，否则拷 n 字节。
//
// 调色板策略与 sysdat 相同：算法化亮度排序（见 BgImage.BuildOrderedPalette）。

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
    internal static class CbdFormat
    {
        static readonly byte[] Sig = { 0x13, 0, 0, 0, 1, 0, 0, 0 };
        static readonly PngEncoder FastPng = new() { CompressionLevel = PngCompressionLevel.Level1 };

        internal sealed class Entry
        {
            public int Offset;              // 文件偏移（= 文件名）
            public int End;                 // 结构结束（末部件数据尾）
            public (int w, int h)[] Dims;
        }

        internal struct PartMeta
        {
            public int Off;                 // 块内部件偏移
            public int W, H;
            public int DataOff;             // 块内像素数据偏移（Off+0x70）
            public int DataLen;             // 字节数（flag=1 时 = 压缩长度）
            public bool Compressed;
        }

        // ---------------- RLE mode8 编解码 ----------------

        /// <summary>解压一段 RLE 数据（按游戏语义：输入驱动、输出不设上限）。
        /// 产出取前 need 字节；成功条件 = 输入恰好耗尽且产出 ≥ need。
        /// 实测有一块原始数据末 token 悬出 csz 1 字节、输出多 5 字节（原版编码器手抖，
        /// 游戏不检查输出上限照写），故对末 token 的参数越界和输出过冲做有限容错。</summary>
        internal static bool TryRleDecode(byte[] d, int start, int len, int need, out byte[] pixels)
        {
            pixels = new byte[need];
            int p = start, end = start + len, o = 0;
            while (p < end)
            {
                byte c = d[p++];
                int n = (c & 0x7F) + 1;
                int w = Math.Min(n, need - o);
                if ((c & 0x80) != 0)
                {
                    if (p >= d.Length) return false;
                    byte v = d[p++];
                    for (int k = 0; k < w; k++) pixels[o + k] = v;
                }
                else
                {
                    if (p + w > d.Length) return false;
                    Buffer.BlockCopy(d, p, pixels, o, w);
                    p += n;
                }
                o += n;
                if (o > need + 1024) return false;   // 过冲超出一个 token 的量级 = 数据不对
            }
            return o >= need;
        }

        /// <summary>贪心编码：同值游程 ≥3 出填充 token，其余攒字面段（每段 ≤128）。</summary>
        internal static byte[] RleEncode(byte[] src, int off, int len)
        {
            var body = new List<byte>(len + len / 64 + 16);
            int i = 0;
            while (i < len)
            {
                byte v = src[off + i];
                int run = 1;
                while (run < 128 && i + run < len && src[off + i + run] == v) run++;
                if (run >= 3)
                {
                    body.Add((byte)(0x80 | (run - 1)));
                    body.Add(v);
                    i += run;
                }
                else
                {
                    // 字面段：一直攒到遇到 ≥3 游程或末尾
                    int start = i;
                    i += run;
                    while (i < len)
                    {
                        byte v2 = src[off + i];
                        int r2 = 1;
                        while (r2 < 128 && i + r2 < len && src[off + i + r2] == v2) r2++;
                        if (r2 >= 3) break;
                        i += r2;
                    }
                    int total = i - start;
                    int q = start;
                    while (total > 0)
                    {
                        int n = Math.Min(total, 128);
                        body.Add((byte)(n - 1));
                        for (int k = 0; k < n; k++) body.Add(src[off + q + k]);
                        q += n; total -= n;
                    }
                }
            }
            return body.ToArray();
        }

        /// <summary>扫描期校验：token 流恰好耗尽输入、产出 ≥ need（与 TryRleDecode 同语义，不落盘）。</summary>
        static bool RleValidate(byte[] d, int p, int len, int need)
        {
            int end = p + len, o = 0;
            while (p < end)
            {
                byte c = d[p++];
                int n = (c & 0x7F) + 1;
                if ((c & 0x80) != 0)
                {
                    if (p >= d.Length) return false;
                    p += 1;
                }
                else p += n;
                o += n;
                if (o > need + 1024) return false;
            }
            return o >= need;
        }

        // ---------------- 扫描 ----------------

        /// <summary>全文件扫描 0x13 块（含 RLE 部件校验），按偏序返回。</summary>
        public static List<Entry> Scan(byte[] d)
        {
            var result = new List<Entry>();
            int lastEnd = 0;
            int pos = 0;
            while (true)
            {
                int i = IndexOf(d, Sig, pos, d.Length);
                if (i < 0) break;
                pos = i + 1;
                if ((i & 15) != 0 || i < lastEnd) continue;   // CBD 块起点一律 16 对齐
                if (!TryParseBlock(d, i, d.Length, out var dims, out int end)) continue;
                result.Add(new Entry { Offset = i, End = end, Dims = dims });
                lastEnd = end;
            }
            result.Sort((a, b) => a.Offset.CompareTo(b.Offset));
            return result;
        }

        /// <summary>解析块头/部件表；CBD 变体：部件像素可能是 RLE，extent 用 +0x60 压缩长度。</summary>
        static bool TryParseBlock(byte[] b, int baseOff, int limit,
                                  out (int w, int h)[] dims, out int end)
        {
            dims = null; end = 0;
            if (baseOff + 0x20 > limit) return false;
            if (BitConverter.ToUInt32(b, baseOff) != 0x13) return false;
            if (BitConverter.ToUInt32(b, baseOff + 4) != 1) return false;
            int paloff = BitConverter.ToInt32(b, baseOff + 8);
            int parts = BitConverter.ToInt32(b, baseOff + 12);
            if (paloff < 0x20 || paloff >= 0x2000 || parts < 1 || parts > 8) return false;
            var list = new (int, int)[parts];
            int maxRel = Math.Max(paloff + 0x400, 0x10 + parts * 4);
            for (int i = 0; i < parts; i++)
            {
                int po = BitConverter.ToInt32(b, baseOff + 0x10 + i * 4);
                if (po < 0x20 || po >= 0x100000 || baseOff + po + 0x70 > limit) return false;
                int w = BitConverter.ToUInt16(b, baseOff + po + 0x30);
                int h = BitConverter.ToUInt16(b, baseOff + po + 0x34);
                // 宽松界：实测有 1 像素高的细条部件（608×1）；假阳性防线是 RLE 精确耗尽校验
                if (w < 1 || w > 2048 || h < 1 || h > 2048) return false;
                int dataOff = po + 0x70;
                int dataLen;
                if (b[baseOff + po + 0x68] != 0)
                {
                    // 压缩部件：仅接受 mode8（实测全部如此）；校验 token 流恰好覆盖 w*h
                    if ((b[baseOff + po + 0x69] >> 3) != 1) return false;
                    dataLen = BitConverter.ToInt32(b, baseOff + po + 0x60);
                    if (dataLen < 1 || dataLen > w * h + w * h / 64 + 64) return false;
                    if (baseOff + dataOff + dataLen > limit) return false;
                    if (!RleValidate(b, baseOff + dataOff, dataLen, w * h)) return false;
                }
                else
                {
                    dataLen = w * h;
                    if (baseOff + dataOff + dataLen > limit) return false;
                }
                list[i] = (w, h);
                maxRel = Math.Max(maxRel, dataOff + dataLen);
            }
            end = baseOff + maxRel;
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

        /// <summary>槽位上界 = 下一个块起点 − 0x110（后继的描述符/前缀区不许碰）；
        /// 不低于自身现长；最后一块到文件尾。</summary>
        internal static int SlotEnd(List<Entry> entries, Entry e, int fileLen)
        {
            int next = int.MaxValue;
            foreach (var x in entries)
                if (x.Offset > e.Offset && x.Offset < next) next = x.Offset;
            int bound = next == int.MaxValue ? fileLen : next - 0x110;
            return Math.Max(bound, e.End);
        }

        // ---------------- 提取 ----------------

        /// <summary>块内像素（RLE 部件解码后纵向堆叠）→ RGBA。直接在全文件上解析
        /// （带块基址），因为个别原始块的末 token 参数会悬进块后的补零区。</summary>
        internal static Rgba32[] BlockToPixels(byte[] d, int baseOff, int endOff, out int width, out int height)
        {
            int paloff = BitConverter.ToInt32(d, baseOff + 0x08);
            var pal = BgImage.UnswizzlePalette(d, baseOff + paloff);
            var metas = ParseParts(d, baseOff);
            width = metas[0].W;
            height = metas.Sum(m => m.H);
            var pixels = new Rgba32[width * height];
            ReadOnlySpan<Rgba32> palette = pal;
            int rowBase = 0;
            foreach (var m in metas)
            {
                if (m.W != width) throw new InvalidOperationException($"cbd: part 宽 {m.W} != {width}");
                byte[] idx;
                if (m.Compressed)
                {
                    if (!TryRleDecode(d, m.DataOff, m.DataLen, m.W * m.H, out idx))
                        throw new InvalidOperationException("cbd: 部件解码长度错位");
                }
                else
                {
                    idx = new byte[m.W * m.H];
                    Buffer.BlockCopy(d, m.DataOff, idx, 0, m.W * m.H);
                }
                for (int y = 0; y < m.H; y++)
                {
                    int rowStart = (rowBase + y) * width;
                    for (int x = 0; x < m.W; x++)
                        pixels[rowStart + x] = palette[idx[y * m.W + x]];
                }
                rowBase += m.H;
            }
            return pixels;
        }

        static PartMeta[] ParseParts(byte[] d, int baseOff)
        {
            int parts = BitConverter.ToInt32(d, baseOff + 0x0C);
            var metas = new PartMeta[parts];
            for (int i = 0; i < parts; i++)
            {
                int po = baseOff + BitConverter.ToInt32(d, baseOff + 0x10 + i * 4);
                int w = BitConverter.ToUInt16(d, po + 0x30);
                int h = BitConverter.ToUInt16(d, po + 0x34);
                bool comp = d[po + 0x68] != 0;
                metas[i] = new PartMeta
                {
                    Off = po, W = w, H = h, DataOff = po + 0x70, Compressed = comp,
                    DataLen = comp ? BitConverter.ToInt32(d, po + 0x60) : w * h,
                };
            }
            return metas;
        }

        /// <summary>全部图像 → outDir\<4位序号>.png（每块一张，部件纵向堆叠；
        /// 序号 = 扫描序，与 BG 的 RRRR 同思路——CBD 是记录式结构可扩容重排，
        /// 块身份用序号而不是地址）。</summary>
        public static void Extract(string path, string outDir, Action<string> log)
        {
            byte[] d = File.ReadAllBytes(path);
            var entries = Scan(d);
            var lockObj = new object();
            int done = 0;
            Directory.CreateDirectory(outDir);
            Parallel.For(0, entries.Count, new ParallelOptions { MaxDegreeOfParallelism = Environment.ProcessorCount }, i =>
            {
                var e = entries[i];
                var pixels = BlockToPixels(d, e.Offset, e.End, out int w, out int h);
                using (var img = Image.LoadPixelData<Rgba32>(pixels, w, h))
                    img.SaveAsPng(Path.Combine(outDir, $"{i:D4}.png"), FastPng);
                lock (lockObj)
                {
                    if (++done % 200 == 0) log($"  {Path.GetFileName(path)}: {done}/{entries.Count}…");
                }
            });
            log($"{Path.GetFileName(path)}: {entries.Count} 张图 -> {outDir}（序号命名）");
        }

        // ---------------- 打包（原位回写） ----------------

        static readonly Regex IndexName = new(@"^\d{4}\.png$", RegexOptions.IgnoreCase);

        /// <summary>把 modDir 下现存的序号命名 PNG（0000.png…）打回 CBD（存在才改），输出整份文件。</summary>
        public static void Pack(string path, string modDir, string outFile, Action<string> log)
        {
            var files = new List<string>();
            if (Directory.Exists(modDir))
                files = Directory.GetFiles(modDir, "*.png", SearchOption.AllDirectories).ToList();
            foreach (string f in files)
                if (!IndexName.IsMatch(Path.GetFileName(f)))
                    throw new InvalidDataException(
                        $"cbd: 文件名必须是 4 位序号（如 0021.png）：{f}");
            if (files.Count == 0)
            {
                log($"{Path.GetFileName(path)}: modified 里没有 PNG，跳过");
                return;
            }

            byte[] data = File.ReadAllBytes(path);
            List<Entry> entries = Scan(data);

            int patched = 0;
            foreach (string f in files.OrderBy(f => f, StringComparer.OrdinalIgnoreCase))
            {
                int idx = int.Parse(Path.GetFileName(f).Substring(0, 4));
                if (idx < 0 || idx >= entries.Count)
                    throw new InvalidDataException(
                        $"cbd: {Path.GetFileName(f)}：序号 {idx} 超出范围（该文件共 {entries.Count} 块）");
                var e = entries[idx];
                byte[] raw = data[e.Offset..e.End];

                int W = e.Dims[0].w, H = e.Dims.Sum(x => x.h);
                byte[] newBlock;
                using (var image = Image.Load<Rgba32>(f))
                {
                    if (image.Width != W || image.Height != H)
                        throw new InvalidDataException(
                            $"{f}: 尺寸 {image.Width}x{image.Height} != 需要 {W}x{H}（尺寸不可改）");
                    var pixels = new Rgba32[W * H];
                    image.CopyPixelDataTo(pixels);
                    newBlock = ComposeBlock(raw, pixels, W, H);
                }

                int slot = SlotEnd(entries, e, data.Length) - e.Offset;
                if (newBlock.Length > slot)
                    throw new InvalidOperationException(
                        $"{Path.GetFileName(f)}: 重编码 {newBlock.Length} B 超过槽位 {slot} B（内容复杂度超过原图，需精简）");
                // 新块更短时清掉自己旧数据的尾巴（新块更长时越过的是原槽内补零区，直接覆盖）
                int clearLen = Math.Max(0, e.End - (e.Offset + newBlock.Length));
                if (clearLen > 0) Array.Clear(data, e.Offset + newBlock.Length, clearLen);
                Buffer.BlockCopy(newBlock, 0, data, e.Offset, newBlock.Length);
                e.End = e.Offset + newBlock.Length;
                patched++;
                log($"  {Path.GetFileName(path)} #{idx:D4} 已替换（{e.Offset:X7}，RLE 块）");
            }
            Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outFile))!);
            File.WriteAllBytes(outFile, data);
            log($"{Path.GetFileName(path)}: {patched} 张图已打补丁 -> {outFile}");
        }

        /// <summary>重建整块：保留原块头/部件头，算法化调色板，部件像素重排为 16 对齐 + RLE mode8。</summary>
        static byte[] ComposeBlock(byte[] raw, Rgba32[] pixels, int width, int height)
        {
            int paloff = BitConverter.ToInt32(raw, 0x08);
            var metas = ParseParts(raw, 0);
            var (colors, indices) = BgImage.BuildOrderedPalette(pixels);

            // 先逐部件编码（行切片 → RLE），再定布局
            var encoded = new byte[metas.Length][];
            int rowBase = 0;
            for (int i = 0; i < metas.Length; i++)
            {
                var m = metas[i];
                var seg = new byte[m.W * m.H];
                for (int y = 0; y < m.H; y++)
                    Buffer.BlockCopy(indices, (rowBase + y) * width, seg, y * m.W, m.W);
                encoded[i] = RleEncode(seg, 0, seg.Length);
                // 正确性由 kitatest 全量自测保证，打包路径不做回读验证（提速）
                rowBase += m.H;
            }

            int cur = (paloff + 0x400 + 15) & ~15;
            int total = cur;
            for (int i = 0; i < metas.Length; i++)
                total = (total + 0x70 + encoded[i].Length + 15) & ~15;
            if (total < paloff + 0x400) total = paloff + 0x400;

            var block = new byte[total];
            // 头 + 部件表 + 调色板前区域原样保留
            Array.Copy(raw, 0, block, 0, Math.Min(raw.Length, paloff + 0x400));
            byte[] palData = BgImage.SwizzlePalette(colors);
            Array.Copy(palData, 0, block, paloff, palData.Length);

            for (int i = 0; i < metas.Length; i++)
            {
                var m = metas[i];
                BitConverter.GetBytes(cur).CopyTo(block, 0x10 + i * 4);
                Array.Copy(raw, m.Off, block, cur, 0x70);   // 部件头原样（含 GS 目标页等）
                BitConverter.GetBytes(encoded[i].Length).CopyTo(block, cur + 0x60);
                block[cur + 0x68] = 1;                        // RLE 压缩标志
                block[cur + 0x69] = 8;                        // mode8
                Buffer.BlockCopy(encoded[i], 0, block, cur + 0x70, encoded[i].Length);
                cur = (cur + 0x70 + encoded[i].Length + 15) & ~15;
            }
            return block;
        }
    }
}
