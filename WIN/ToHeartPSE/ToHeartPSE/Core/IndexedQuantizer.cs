// Core/IndexedQuantizer.cs
// ---------------------------------------------------------------
// 通用索引色量化，与 GalaxyAngel2 的 Utils.IndexedQuantizer 同一套策略：
// 精确调色板优先（去重后颜色数装得下即零损失，按亮度排序），
// 仅当去重后颜色数超过 maxColors 才走 ImageSharp Wu 量化（无抖动）。
// 输入是 32bpp BGRA 逐像素（top-down）；alpha 不参与量化（LFB 的
// alpha 独立于调色板，由调用方按像素单独保留）。
// ---------------------------------------------------------------

using SixLabors.ImageSharp;
using SixLabors.ImageSharp.PixelFormats;
using SixLabors.ImageSharp.Processing;
using SixLabors.ImageSharp.Processing.Processors.Quantization;

namespace ToHeartPSE;

internal static class IndexedQuantizer
{
    public static byte[] Build(byte[] bgra, int width, int height, int maxColors,
        out List<(byte R, byte G, byte B)> palette)
    {
        var pixels = new (byte R, byte G, byte B, byte A)[bgra.Length / 4];
        for (int i = 0; i < pixels.Length; i++)
        {
            int p = i * 4;
            pixels[i] = (bgra[p + 2], bgra[p + 1], bgra[p], 255);
        }

        if (TryBuildBrightnessSortedPalette(pixels, maxColors, out byte[] indices, out var exact))
        {
            palette = exact.Select(c => (c.R, c.G, c.B)).ToList();
            return indices;
        }

        using var image = Image.LoadPixelData<Rgba32>(
            pixels.Select(c => new Rgba32(c.R, c.G, c.B, c.A)).ToArray(), width, height);
        image.Mutate(x => x.Quantize(new WuQuantizer(new QuantizerOptions
        {
            MaxColors = maxColors,
            Dither = null
        })));
        var quantized = new Rgba32[pixels.Length];
        image.CopyPixelDataTo(quantized);
        var round = new (byte R, byte G, byte B, byte A)[pixels.Length];
        for (int i = 0; i < quantized.Length; i++)
            round[i] = (quantized[i].R, quantized[i].G, quantized[i].B, 255);

        if (!TryBuildBrightnessSortedPalette(round, maxColors, out indices, out exact))
            throw new InvalidDataException($"量化后仍超过 {maxColors} 色");
        palette = exact.Select(c => (c.R, c.G, c.B)).ToList();
        return indices;
    }

    static bool TryBuildBrightnessSortedPalette(
        (byte R, byte G, byte B, byte A)[] pixels,
        int maxColors,
        out byte[] indices,
        out List<(byte R, byte G, byte B, byte A)> palette)
    {
        indices = new byte[pixels.Length];
        palette = new List<(byte, byte, byte, byte)>(maxColors);

        var distinct = new Dictionary<uint, int>(maxColors);
        var colors = new List<(byte R, byte G, byte B, byte A)>(maxColors);
        for (int i = 0; i < pixels.Length; i++)
        {
            var c = pixels[i];
            uint key = ((uint)c.A << 24) | ((uint)c.R << 16) | ((uint)c.G << 8) | c.B;
            if (!distinct.ContainsKey(key))
            {
                if (colors.Count == maxColors)
                    return false;
                distinct.Add(key, colors.Count);
                colors.Add(c);
            }
        }

        int[] order = new int[colors.Count];
        for (int i = 0; i < order.Length; i++) order[i] = i;
        Array.Sort(order, Comparer<int>.Create((a, b) =>
        {
            var ca = colors[a];
            var cb = colors[b];
            int la = ca.R * 299 + ca.G * 587 + ca.B * 114;
            int lb = cb.R * 299 + cb.G * 587 + cb.B * 114;
            if (la != lb) return lb.CompareTo(la);      // 亮色在前
            return a.CompareTo(b);                       // 同亮度按首次出现
        }));

        var slotOfOrder = new byte[colors.Count];
        for (int slot = 0; slot < order.Length; slot++)
        {
            slotOfOrder[order[slot]] = (byte)slot;
            palette.Add(colors[order[slot]]);
        }
        while (palette.Count < maxColors)
            palette.Add(default);

        for (int i = 0; i < pixels.Length; i++)
        {
            var c = pixels[i];
            uint key = ((uint)c.A << 24) | ((uint)c.R << 16) | ((uint)c.G << 8) | c.B;
            indices[i] = slotOfOrder[distinct[key]];
        }
        return true;
    }
}
