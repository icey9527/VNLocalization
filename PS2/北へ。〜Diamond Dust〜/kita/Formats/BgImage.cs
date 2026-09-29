// Formats/BgImage.cs — 解压后块 <-> PNG 的转换，以及调色板量化。
// 逻辑自 KitaAccess 原样移植（已全量验证）；块结构偏移是引擎格式，全部为本文件常量。
//
// 量化策略：
//   · 唯一颜色数（不含全透明）≤256 时直接无损建调色板
//   · >256 时用 ImageSharp 的 WuQuantizer，显式全量采样，关闭抖动；
//     全透明像素（A=0）不参与量化，固定占用索引 0。
//   · 文件调色板 alpha 是 0..0x80 半程值，互逆换算。

using System;
using System.Collections.Generic;
using System.Linq;
using SixLabors.ImageSharp;
using SixLabors.ImageSharp.PixelFormats;
using SixLabors.ImageSharp.Processing.Processors.Quantization;

namespace kita
{
    public static class BgImage
    {
        // 块结构（引擎格式，详见 研究笔记.md §3）
        internal const int BlkPalOffset = 0x08;   // 块内：调色板偏移字段
        internal const int BlkPartCount = 0x0C;   // 块内：部件数字段
        internal const int BlkPartTable = 0x10;   // 块内：部件偏移表字段
        internal const int PalEntries = 256;      // 调色板项数
        internal const byte AlphaOpaque = 0x80;   // 文件侧 alpha 满程（半程 alpha）
        internal const int PartW = 0x30;          // 部件头：宽 u16
        internal const int PartH = 0x34;          // 部件头：高 u16
        internal const int PartCompFlag = 0x68;   // 部件头：二次压缩标志（BG 恒 0）
        internal const int PartCompMode = 0x69;   // 部件头：二次压缩模式
        internal const int PartHeaderBytes = 0x70;// 部件头长度 = 像素起点

        /// <summary>GS CSM1 调色板 swizzle（自逆）：索引 bit3 与 bit4 互换。</summary>
        public static int SwizzleIndex(int i) =>
            (i & 0xE7) | ((i & 0x08) << 1) | ((i & 0x10) >> 1);

        /// <summary>文件调色板(0x400 字节，swizzle 顺序) -> 逻辑顺序 RGBA。</summary>
        public static Rgba32[] UnswizzlePalette(byte[] block, int palOffset)
        {
            var pal = new Rgba32[PalEntries];
            for (int fileIdx = 0; fileIdx < PalEntries && palOffset + fileIdx * 4 + 4 <= block.Length; fileIdx++)
            {
                int o = palOffset + fileIdx * 4;
                byte r = block[o], g = block[o + 1], b = block[o + 2];
                byte a = (byte)Math.Min(block[o + 3] * 255 / AlphaOpaque, 255);
                pal[SwizzleIndex(fileIdx)] = new Rgba32(r, g, b, a);
            }
            return pal;
        }

        /// <summary>逻辑顺序 RGBA -> 文件调色板（swizzle 顺序 + 半程 alpha）。</summary>
        public static byte[] SwizzlePalette(Rgba32[] logical)
        {
            var data = new byte[PalEntries * 4];
            for (int i = 0; i < PalEntries; i++)
            {
                var col = i < logical.Length ? logical[i] : default;
                int o = SwizzleIndex(i) * 4;
                data[o] = col.R;
                data[o + 1] = col.G;
                data[o + 2] = col.B;
                data[o + 3] = (byte)Math.Min((col.A * AlphaOpaque + 127) / 255, AlphaOpaque);
            }
            return data;
        }

        /// <summary>把块内像素（各部件纵向堆叠）铺成 RGBA 像素数组。</summary>
        public static Rgba32[] BlockToPixels(byte[] block, out int width, out int height)
        {
            int palOffset = BitConverter.ToInt32(block, BlkPalOffset);
            int partCount = BitConverter.ToInt32(block, BlkPartCount);
            var pal = UnswizzlePalette(block, palOffset);

            width = -1;
            height = 0;
            var partInfo = new (int off, int w, int h)[partCount];
            for (int i = 0; i < partCount; i++)
            {
                int poff = BitConverter.ToInt32(block, BlkPartTable + i * 4);
                int w = BitConverter.ToUInt16(block, poff + PartW);
                int h = BitConverter.ToUInt16(block, poff + PartH);
                if (width >= 0 && w != width) throw new InvalidOperationException($"part {i} width {w} != {width}");
                width = w;
                height += h;
                partInfo[i] = (poff, w, h);
            }

            var pixels = new Rgba32[width * height];
            Span<Rgba32> dst = pixels;
            ReadOnlySpan<Rgba32> palette = pal;
            int rowBase = 0;
            foreach (var (poff, w, h) in partInfo)
            {
                int pixOff = poff + PartHeaderBytes;
                for (int y = 0; y < h; y++)
                {
                    int rowStart = (rowBase + y) * width;
                    int srcIdx = pixOff + y * w;
                    for (int x = 0; x < w; x++)
                        dst[rowStart + x] = palette[block[srcIdx + x]];
                }
                rowBase += h;
            }
            return pixels;
        }

        /// <summary>
        /// 从 RGBA 像素建 ≤256 色调色板 + 每像素索引。
        /// 唯一色（不含透明）≤256 时无损；否则 Wu 量化。
        /// </summary>
        public static void BuildPalette(Rgba32[] pixels, out Rgba32[] palette, out byte[] indices)
        {
            int np = pixels.Length;
            var visible = new List<Rgba32>(np);
            var visiblePos = new List<int>(np);
            bool hasTransparent = false;
            for (int i = 0; i < np; i++)
            {
                if (pixels[i].A == 0) { hasTransparent = true; continue; }
                visible.Add(pixels[i]);
                visiblePos.Add(i);
            }

            int reserve = hasTransparent ? 1 : 0;
            int maxColors = PalEntries - reserve;

            var qpal = new List<Rgba32>();
            var qidx = new byte[visible.Count];

            var seen = new Dictionary<Rgba32, byte>();
            foreach (var col in visible)
                if (!seen.ContainsKey(col)) seen[col] = 0;

            if (seen.Count + reserve <= PalEntries)
            {
                // 无损：唯一色按首次出现顺序入表
                seen.Clear();
                for (int j = 0; j < visible.Count; j++)
                {
                    if (!seen.TryGetValue(visible[j], out byte idx))
                    {
                        idx = (byte)qpal.Count;
                        seen[visible[j]] = idx;
                        qpal.Add(visible[j]);
                    }
                    qidx[j] = idx;
                }
            }
            else
            {
                // Wu 量化（可见像素连同 alpha 一起参与，全量采样，无抖动）
                var src = new Rgba32[visible.Count];
                for (int j = 0; j < visible.Count; j++) src[j] = visible[j];
                using (var img = Image.LoadPixelData<Rgba32>(src, visible.Count, 1))
                {
                    var options = new QuantizerOptions { MaxColors = maxColors, Dither = null };
                    var quantizer = new WuQuantizer(options);
                    using (IQuantizer<Rgba32> q =
                           quantizer.CreatePixelSpecificQuantizer<Rgba32>(img.Configuration, options))
                    {
                        QuantizerUtilities.BuildPalette(q, new ExtensivePixelSamplingStrategy(), img.Frames.RootFrame);
                        using (IndexedImageFrame<Rgba32> quantized =
                               q.QuantizeFrame(img.Frames.RootFrame, new Rectangle(0, 0, visible.Count, 1)))
                        {
                            var span = quantized.DangerousGetRowSpan(0);
                            for (int j = 0; j < visible.Count; j++) qidx[j] = span[j];
                            var memPal = quantized.Palette;
                            for (int j = 0; j < memPal.Length && j < maxColors; j++) qpal.Add(memPal.Span[j]);
                        }
                    }
                }
            }

            palette = new Rgba32[qpal.Count + reserve];
            if (hasTransparent) palette[0] = default;
            for (int j = 0; j < qpal.Count; j++) palette[j + reserve] = qpal[j];

            indices = new byte[np];
            for (int j = 0; j < visible.Count; j++) indices[visiblePos[j]] = (byte)(qidx[j] + reserve);
            // 透明像素保持 0
        }

        /// <summary>
        /// 算法化有序调色板（sysdat 流 / CBD 共用）：先 BuildPalette（唯一色 ≤256 精确保留，
        /// 否则 Wu 量化 + 透明保护），再按亮度排序。原理：LZSS/RLE 对索引的一一映射不变，
        /// 受顺序影响的只有调色板块/数据本身的可压缩性——按亮度排（RGB 平滑渐变 → 索引
        /// 集中）即可稳定复现原版可压缩性，且对新增颜色同样成立。
        /// </summary>
        public static (Rgba32[] Colors, byte[] Indices) BuildOrderedPalette(Rgba32[] pixels)
        {
            BuildPalette(pixels, out var pal0, out var idx0);
            // 亮度排序（透明色 luma=0 自然排最前；同亮度按 RGB 字典序稳定）
            var order = System.Linq.Enumerable.Range(0, pal0.Length)
                .OrderBy(i => OrderedLuma(pal0[i]))
                .ThenBy(i => pal0[i].R).ThenBy(i => pal0[i].G).ThenBy(i => pal0[i].B)
                .ToArray();
            var remap = new byte[pal0.Length];
            var colors = new Rgba32[pal0.Length];
            for (int n = 0; n < order.Length; n++)
            {
                remap[order[n]] = (byte)n;
                colors[n] = pal0[order[n]];
            }
            var indices = new byte[idx0.Length];
            for (int i = 0; i < idx0.Length; i++) indices[i] = remap[idx0[i]];
            return (colors, indices);
        }

        static int OrderedLuma(Rgba32 c) =>
            c.A == 0 ? 0 : (c.R * 299 + c.G * 587 + c.B * 114) / 1000;

        /// <summary>把 RGBA 像素按部件行切片写回块字节（保留原部件头），并写调色板。</summary>
        public static void WritePixelsToBlock(byte[] block, Rgba32[] pixels, int width, int height)
        {
            int partCount = BitConverter.ToInt32(block, BlkPartCount);
            BuildPalette(pixels, out var pal, out var indices);
            byte[] palData = SwizzlePalette(pal);
            int palOffset = BitConverter.ToInt32(block, BlkPalOffset);
            Array.Copy(palData, 0, block, palOffset, palData.Length);

            int rowBase = 0;
            for (int i = 0; i < partCount; i++)
            {
                int poff = BitConverter.ToInt32(block, BlkPartTable + i * 4);
                int w = BitConverter.ToUInt16(block, poff + PartW);
                int h = BitConverter.ToUInt16(block, poff + PartH);
                block[poff + PartCompFlag] = 0; // 像素直接存原始索引
                block[poff + PartCompMode] = 0;
                int pixOff = poff + PartHeaderBytes;
                for (int y = 0; y < h; y++)
                {
                    int rowStart = (rowBase + y) * width;
                    for (int x = 0; x < w; x++)
                        block[pixOff + y * w + x] = indices[rowStart + x];
                }
                rowBase += h;
            }
        }
    }
}
