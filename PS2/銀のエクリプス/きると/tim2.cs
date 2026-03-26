using System;
using System.Buffers.Binary;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Threading;
using System.Threading.Tasks;

internal static class Program
{
    private static readonly byte[] GsTex0 = { 0x00, 0x00, 0x30, 0x65, 0x02, 0x00, 0x00, 0x00 };

    private readonly struct Rgb
    {
        public readonly byte R;
        public readonly byte G;
        public readonly byte B;
        public Rgb(byte r, byte g, byte b) { R = r; G = g; B = b; }
    }

    private readonly struct Rgba
    {
        public readonly byte R;
        public readonly byte G;
        public readonly byte B;
        public readonly byte A;
        public Rgba(byte r, byte g, byte b, byte a) { R = r; G = g; B = b; A = a; }
    }

    private sealed class ColorBox
    {
        public List<int> Indices = new();
    }

    private static byte FixAlphaPs2(byte a)
    {
        var v = a * 2 - 1;
        if (v < 0) v = 0;
        if (v > 255) v = 255;
        return (byte)v;
    }

    private static byte ToPs2Alpha(byte a)
    {
        if (a == 0) return 0;
        var v = (a + 1) >> 1;
        if (v > 128) v = 128;
        return (byte)v;
    }

    private static byte[] BuildTim2FileHeader()
    {
        var h = new byte[0x10];
        h[0] = (byte)'T';
        h[1] = (byte)'I';
        h[2] = (byte)'M';
        h[3] = (byte)'2';
        h[4] = 4;
        h[5] = 0;
        BinaryPrimitives.WriteUInt16LittleEndian(h.AsSpan(6, 2), 1);
        return h;
    }

    private static byte[] BuildTim2PictureHeader(int imageSize, int clutSize, int width, int height)
    {
        var h = new byte[0x30];
        BinaryPrimitives.WriteUInt32LittleEndian(h.AsSpan(0x00, 4), (uint)(0x30 + imageSize + clutSize));
        BinaryPrimitives.WriteUInt32LittleEndian(h.AsSpan(0x04, 4), (uint)clutSize);
        BinaryPrimitives.WriteUInt32LittleEndian(h.AsSpan(0x08, 4), (uint)imageSize);
        BinaryPrimitives.WriteUInt16LittleEndian(h.AsSpan(0x0C, 2), 0x30);
        BinaryPrimitives.WriteUInt16LittleEndian(h.AsSpan(0x0E, 2), 256);
        h[0x10] = 0;
        h[0x11] = 1;
        h[0x12] = 3;
        h[0x13] = 5;
        BinaryPrimitives.WriteUInt16LittleEndian(h.AsSpan(0x14, 2), (ushort)width);
        BinaryPrimitives.WriteUInt16LittleEndian(h.AsSpan(0x16, 2), (ushort)height);
        Buffer.BlockCopy(GsTex0, 0, h, 0x18, GsTex0.Length);
        h[0x20] = (byte)((width == 256 && height == 256) ? 0x6C : 0x60);
        h[0x21] = 0x02;
        return h;
    }

    private static Rgba[] SwizzlePalette256(IReadOnlyList<Rgba> palette)
    {
        var src = new Rgba[256];
        for (var i = 0; i < 256; i++) src[i] = i < palette.Count ? palette[i] : new Rgba(0, 0, 0, 0);
        var dst = new Rgba[256];
        for (var b = 0; b < 8; b++)
        {
            var baseIdx = b * 32;
            Array.Copy(src, baseIdx + 0, dst, baseIdx + 0, 8);
            Array.Copy(src, baseIdx + 16, dst, baseIdx + 8, 8);
            Array.Copy(src, baseIdx + 8, dst, baseIdx + 16, 8);
            Array.Copy(src, baseIdx + 24, dst, baseIdx + 24, 8);
        }
        return dst;
    }

    private static Rgba[] DeswizzlePalette256(IReadOnlyList<Rgba> palette)
    {
        var src = new Rgba[256];
        for (var i = 0; i < 256; i++) src[i] = i < palette.Count ? palette[i] : new Rgba(0, 0, 0, 0);
        var dst = new List<Rgba>(256);
        for (var b = 0; b < 8; b++)
        {
            var baseIdx = b * 32;
            dst.AddRange(src.AsSpan(baseIdx + 0, 8).ToArray());
            dst.AddRange(src.AsSpan(baseIdx + 16, 8).ToArray());
            dst.AddRange(src.AsSpan(baseIdx + 8, 8).ToArray());
            dst.AddRange(src.AsSpan(baseIdx + 24, 8).ToArray());
        }
        return dst.ToArray();
    }

    private static int ChannelValue(Rgb c, int channel) => channel switch
    {
        0 => c.R,
        1 => c.G,
        _ => c.B
    };

    private static int ChannelValueRgba(Rgba c, int channel) => channel switch
    {
        0 => c.R,
        1 => c.G,
        2 => c.B,
        _ => c.A
    };

    private static Rgb WeightedAverage(List<int> boxIndices, IReadOnlyList<Rgb> colors, IReadOnlyList<int> counts)
    {
        long r = 0, g = 0, b = 0, total = 0;
        foreach (var idx in boxIndices)
        {
            var c = colors[idx];
            var w = counts[idx];
            r += c.R * (long)w;
            g += c.G * (long)w;
            b += c.B * (long)w;
            total += w;
        }
        if (total == 0) return new Rgb(0, 0, 0);
        return new Rgb((byte)(r / total), (byte)(g / total), (byte)(b / total));
    }

    private static Rgba WeightedAverageRgba(List<int> boxIndices, IReadOnlyList<Rgba> colors, IReadOnlyList<int> counts)
    {
        long r = 0, g = 0, b = 0, a = 0, total = 0;
        foreach (var idx in boxIndices)
        {
            var c = colors[idx];
            var w = counts[idx];
            r += c.R * (long)w;
            g += c.G * (long)w;
            b += c.B * (long)w;
            a += c.A * (long)w;
            total += w;
        }
        if (total == 0) return new Rgba(0, 0, 0, 0);
        return new Rgba((byte)(r / total), (byte)(g / total), (byte)(b / total), (byte)(a / total));
    }

    private static int BoxPriority(ColorBox box, IReadOnlyList<Rgb> colors, IReadOnlyList<int> counts)
    {
        if (box.Indices.Count == 0) return 0;
        int minR = 255, minG = 255, minB = 255, maxR = 0, maxG = 0, maxB = 0;
        var pop = 0;
        foreach (var idx in box.Indices)
        {
            var c = colors[idx];
            var w = counts[idx];
            if (c.R < minR) minR = c.R;
            if (c.G < minG) minG = c.G;
            if (c.B < minB) minB = c.B;
            if (c.R > maxR) maxR = c.R;
            if (c.G > maxG) maxG = c.G;
            if (c.B > maxB) maxB = c.B;
            pop += w;
        }
        var range = Math.Max(maxR - minR, Math.Max(maxG - minG, maxB - minB));
        return range * pop;
    }

    private static int BoxPriorityRgba(ColorBox box, IReadOnlyList<Rgba> colors, IReadOnlyList<int> counts)
    {
        if (box.Indices.Count == 0) return 0;
        int minR = 255, minG = 255, minB = 255, minA = 255, maxR = 0, maxG = 0, maxB = 0, maxA = 0;
        var pop = 0;
        foreach (var idx in box.Indices)
        {
            var c = colors[idx];
            var w = counts[idx];
            if (c.R < minR) minR = c.R;
            if (c.G < minG) minG = c.G;
            if (c.B < minB) minB = c.B;
            if (c.A < minA) minA = c.A;
            if (c.R > maxR) maxR = c.R;
            if (c.G > maxG) maxG = c.G;
            if (c.B > maxB) maxB = c.B;
            if (c.A > maxA) maxA = c.A;
            pop += w;
        }
        var range = Math.Max(Math.Max(maxR - minR, maxG - minG), Math.Max(maxB - minB, maxA - minA));
        return range * pop;
    }

    private static int DominantChannel(ColorBox box, IReadOnlyList<Rgb> colors)
    {
        int minR = 255, minG = 255, minB = 255, maxR = 0, maxG = 0, maxB = 0;
        foreach (var idx in box.Indices)
        {
            var c = colors[idx];
            if (c.R < minR) minR = c.R;
            if (c.G < minG) minG = c.G;
            if (c.B < minB) minB = c.B;
            if (c.R > maxR) maxR = c.R;
            if (c.G > maxG) maxG = c.G;
            if (c.B > maxB) maxB = c.B;
        }
        var rr = maxR - minR;
        var gr = maxG - minG;
        var br = maxB - minB;
        if (rr >= gr && rr >= br) return 0;
        if (gr >= rr && gr >= br) return 1;
        return 2;
    }

    private static int DominantChannelRgba(ColorBox box, IReadOnlyList<Rgba> colors)
    {
        int minR = 255, minG = 255, minB = 255, minA = 255, maxR = 0, maxG = 0, maxB = 0, maxA = 0;
        foreach (var idx in box.Indices)
        {
            var c = colors[idx];
            if (c.R < minR) minR = c.R;
            if (c.G < minG) minG = c.G;
            if (c.B < minB) minB = c.B;
            if (c.A < minA) minA = c.A;
            if (c.R > maxR) maxR = c.R;
            if (c.G > maxG) maxG = c.G;
            if (c.B > maxB) maxB = c.B;
            if (c.A > maxA) maxA = c.A;
        }
        var rr = maxR - minR;
        var gr = maxG - minG;
        var br = maxB - minB;
        var ar = maxA - minA;
        if (rr >= gr && rr >= br && rr >= ar) return 0;
        if (gr >= rr && gr >= br && gr >= ar) return 1;
        if (br >= rr && br >= gr && br >= ar) return 2;
        return 3;
    }

    private static List<Rgb> QuantizeMedianCut(Rgb[] pixels, int maxColors)
    {
        var hist = new Dictionary<int, int>(pixels.Length / 2 + 1);
        foreach (var p in pixels)
        {
            var key = (p.R << 16) | (p.G << 8) | p.B;
            hist.TryGetValue(key, out var cnt);
            hist[key] = cnt + 1;
        }

        var colors = new List<Rgb>(hist.Count);
        var counts = new List<int>(hist.Count);
        foreach (var kv in hist)
        {
            colors.Add(new Rgb((byte)(kv.Key >> 16), (byte)(kv.Key >> 8), (byte)kv.Key));
            counts.Add(kv.Value);
        }

        if (colors.Count <= maxColors)
        {
            while (colors.Count < maxColors) colors.Add(new Rgb(0, 0, 0));
            return colors;
        }

        var boxes = new List<ColorBox> { new() { Indices = Enumerable.Range(0, colors.Count).ToList() } };
        while (boxes.Count < maxColors)
        {
            var target = boxes
                .Where(b => b.Indices.Count > 1)
                .OrderByDescending(b => BoxPriority(b, colors, counts))
                .FirstOrDefault();
            if (target == null) break;

            var ch = DominantChannel(target, colors);
            target.Indices.Sort((a, b) => ChannelValue(colors[a], ch).CompareTo(ChannelValue(colors[b], ch)));
            var total = target.Indices.Sum(i => counts[i]);
            var half = total / 2;
            var acc = 0;
            var split = 0;
            for (var i = 0; i < target.Indices.Count; i++)
            {
                acc += counts[target.Indices[i]];
                if (acc >= half)
                {
                    split = i + 1;
                    break;
                }
            }
            if (split <= 0 || split >= target.Indices.Count) break;
            var left = new ColorBox { Indices = target.Indices.Take(split).ToList() };
            var right = new ColorBox { Indices = target.Indices.Skip(split).ToList() };
            boxes.Remove(target);
            boxes.Add(left);
            boxes.Add(right);
        }

        var palette = boxes.Select(b => WeightedAverage(b.Indices, colors, counts)).ToList();
        while (palette.Count < maxColors) palette.Add(new Rgb(0, 0, 0));
        return palette;
    }

    private static List<Rgba> QuantizeMedianCutRgba(Rgba[] pixels, int maxColors)
    {
        var hist = new Dictionary<uint, int>(pixels.Length / 2 + 1);
        foreach (var p in pixels)
        {
            var key = ((uint)p.R << 24) | ((uint)p.G << 16) | ((uint)p.B << 8) | p.A;
            hist.TryGetValue(key, out var cnt);
            hist[key] = cnt + 1;
        }

        var colors = new List<Rgba>(hist.Count);
        var counts = new List<int>(hist.Count);
        foreach (var kv in hist)
        {
            var k = kv.Key;
            colors.Add(new Rgba((byte)(k >> 24), (byte)(k >> 16), (byte)(k >> 8), (byte)k));
            counts.Add(kv.Value);
        }

        if (colors.Count <= maxColors)
        {
            while (colors.Count < maxColors) colors.Add(new Rgba(0, 0, 0, 0));
            return colors;
        }

        var boxes = new List<ColorBox> { new() { Indices = Enumerable.Range(0, colors.Count).ToList() } };
        while (boxes.Count < maxColors)
        {
            var target = boxes
                .Where(b => b.Indices.Count > 1)
                .OrderByDescending(b => BoxPriorityRgba(b, colors, counts))
                .FirstOrDefault();
            if (target == null) break;

            var ch = DominantChannelRgba(target, colors);
            target.Indices.Sort((a, b) => ChannelValueRgba(colors[a], ch).CompareTo(ChannelValueRgba(colors[b], ch)));
            var total = target.Indices.Sum(i => counts[i]);
            var half = total / 2;
            var acc = 0;
            var split = 0;
            for (var i = 0; i < target.Indices.Count; i++)
            {
                acc += counts[target.Indices[i]];
                if (acc >= half)
                {
                    split = i + 1;
                    break;
                }
            }
            if (split <= 0 || split >= target.Indices.Count) break;
            var left = new ColorBox { Indices = target.Indices.Take(split).ToList() };
            var right = new ColorBox { Indices = target.Indices.Skip(split).ToList() };
            boxes.Remove(target);
            boxes.Add(left);
            boxes.Add(right);
        }

        var palette = boxes.Select(b => WeightedAverageRgba(b.Indices, colors, counts)).ToList();
        while (palette.Count < maxColors) palette.Add(new Rgba(0, 0, 0, 0));
        return palette;
    }

    private sealed class WuBox
    {
        public int R0;
        public int R1;
        public int G0;
        public int G1;
        public int B0;
        public int B1;
        public double Variance;
    }

    private const int WuSide = 33;

    private static int WuIndex(int r, int g, int b) => (r * WuSide + g) * WuSide + b;

    private static long WuVolume(WuBox box, long[] moment)
    {
        return moment[WuIndex(box.R1, box.G1, box.B1)]
             - moment[WuIndex(box.R1, box.G1, box.B0)]
             - moment[WuIndex(box.R1, box.G0, box.B1)]
             + moment[WuIndex(box.R1, box.G0, box.B0)]
             - moment[WuIndex(box.R0, box.G1, box.B1)]
             + moment[WuIndex(box.R0, box.G1, box.B0)]
             + moment[WuIndex(box.R0, box.G0, box.B1)]
             - moment[WuIndex(box.R0, box.G0, box.B0)];
    }

    private static double WuVariance(WuBox box, long[] wt, long[] mr, long[] mg, long[] mb, long[] m2)
    {
        var w = WuVolume(box, wt);
        if (w == 0) return 0.0;
        var r = WuVolume(box, mr);
        var g = WuVolume(box, mg);
        var b = WuVolume(box, mb);
        var x = WuVolume(box, m2);
        return x - (r * (double)r + g * (double)g + b * (double)b) / w;
    }

    private static bool WuTryCut(WuBox box, out WuBox first, out WuBox second, long[] wt, long[] mr, long[] mg, long[] mb, long[] m2)
    {
        first = new WuBox();
        second = new WuBox();
        var best = double.NegativeInfinity;
        var bestDir = -1;
        var bestPos = -1;

        for (var i = box.R0 + 1; i < box.R1; i++)
        {
            var b1 = new WuBox { R0 = box.R0, R1 = i, G0 = box.G0, G1 = box.G1, B0 = box.B0, B1 = box.B1 };
            var b2 = new WuBox { R0 = i, R1 = box.R1, G0 = box.G0, G1 = box.G1, B0 = box.B0, B1 = box.B1 };
            var w1 = WuVolume(b1, wt);
            var w2 = WuVolume(b2, wt);
            if (w1 == 0 || w2 == 0) continue;
            var v = WuVariance(b1, wt, mr, mg, mb, m2) + WuVariance(b2, wt, mr, mg, mb, m2);
            if (v > best)
            {
                best = v;
                bestDir = 0;
                bestPos = i;
            }
        }

        for (var i = box.G0 + 1; i < box.G1; i++)
        {
            var b1 = new WuBox { R0 = box.R0, R1 = box.R1, G0 = box.G0, G1 = i, B0 = box.B0, B1 = box.B1 };
            var b2 = new WuBox { R0 = box.R0, R1 = box.R1, G0 = i, G1 = box.G1, B0 = box.B0, B1 = box.B1 };
            var w1 = WuVolume(b1, wt);
            var w2 = WuVolume(b2, wt);
            if (w1 == 0 || w2 == 0) continue;
            var v = WuVariance(b1, wt, mr, mg, mb, m2) + WuVariance(b2, wt, mr, mg, mb, m2);
            if (v > best)
            {
                best = v;
                bestDir = 1;
                bestPos = i;
            }
        }

        for (var i = box.B0 + 1; i < box.B1; i++)
        {
            var b1 = new WuBox { R0 = box.R0, R1 = box.R1, G0 = box.G0, G1 = box.G1, B0 = box.B0, B1 = i };
            var b2 = new WuBox { R0 = box.R0, R1 = box.R1, G0 = box.G0, G1 = box.G1, B0 = i, B1 = box.B1 };
            var w1 = WuVolume(b1, wt);
            var w2 = WuVolume(b2, wt);
            if (w1 == 0 || w2 == 0) continue;
            var v = WuVariance(b1, wt, mr, mg, mb, m2) + WuVariance(b2, wt, mr, mg, mb, m2);
            if (v > best)
            {
                best = v;
                bestDir = 2;
                bestPos = i;
            }
        }

        if (bestDir < 0) return false;

        first = new WuBox { R0 = box.R0, R1 = box.R1, G0 = box.G0, G1 = box.G1, B0 = box.B0, B1 = box.B1 };
        second = new WuBox { R0 = box.R0, R1 = box.R1, G0 = box.G0, G1 = box.G1, B0 = box.B0, B1 = box.B1 };
        if (bestDir == 0)
        {
            first.R1 = bestPos;
            second.R0 = bestPos;
        }
        else if (bestDir == 1)
        {
            first.G1 = bestPos;
            second.G0 = bestPos;
        }
        else
        {
            first.B1 = bestPos;
            second.B0 = bestPos;
        }
        first.Variance = WuVariance(first, wt, mr, mg, mb, m2);
        second.Variance = WuVariance(second, wt, mr, mg, mb, m2);
        return true;
    }

    private static List<Rgb> QuantizeWuRgb(Rgba[] pixels, int maxColors)
    {
        var size = WuSide * WuSide * WuSide;
        var wt = new long[size];
        var mr = new long[size];
        var mg = new long[size];
        var mb = new long[size];
        var m2 = new long[size];

        foreach (var p in pixels)
        {
            var r = (p.R >> 3) + 1;
            var g = (p.G >> 3) + 1;
            var b = (p.B >> 3) + 1;
            var idx = WuIndex(r, g, b);
            wt[idx]++;
            mr[idx] += p.R;
            mg[idx] += p.G;
            mb[idx] += p.B;
            m2[idx] += p.R * p.R + p.G * p.G + p.B * p.B;
        }

        for (var r = 1; r < WuSide; r++)
        {
            var area = new long[WuSide];
            var areaR = new long[WuSide];
            var areaG = new long[WuSide];
            var areaB = new long[WuSide];
            var area2 = new long[WuSide];
            for (var g = 1; g < WuSide; g++)
            {
                long line = 0, lineR = 0, lineG = 0, lineB = 0, line2 = 0;
                for (var b = 1; b < WuSide; b++)
                {
                    var idx = WuIndex(r, g, b);
                    line += wt[idx];
                    lineR += mr[idx];
                    lineG += mg[idx];
                    lineB += mb[idx];
                    line2 += m2[idx];
                    area[b] += line;
                    areaR[b] += lineR;
                    areaG[b] += lineG;
                    areaB[b] += lineB;
                    area2[b] += line2;
                    var idxPrev = WuIndex(r - 1, g, b);
                    wt[idx] = wt[idxPrev] + area[b];
                    mr[idx] = mr[idxPrev] + areaR[b];
                    mg[idx] = mg[idxPrev] + areaG[b];
                    mb[idx] = mb[idxPrev] + areaB[b];
                    m2[idx] = m2[idxPrev] + area2[b];
                }
            }
        }

        var boxes = new List<WuBox>(maxColors) { new() { R0 = 0, R1 = 32, G0 = 0, G1 = 32, B0 = 0, B1 = 32 } };
        boxes[0].Variance = WuVariance(boxes[0], wt, mr, mg, mb, m2);
        while (boxes.Count < maxColors)
        {
            var index = -1;
            var bestVar = 0.0;
            for (var i = 0; i < boxes.Count; i++)
            {
                if (boxes[i].Variance > bestVar)
                {
                    bestVar = boxes[i].Variance;
                    index = i;
                }
            }
            if (index < 0) break;
            if (!WuTryCut(boxes[index], out var b1, out var b2, wt, mr, mg, mb, m2)) break;
            boxes[index] = b1;
            boxes.Add(b2);
        }

        var palette = new List<Rgb>(maxColors);
        foreach (var box in boxes)
        {
            var w = WuVolume(box, wt);
            if (w == 0)
            {
                palette.Add(new Rgb(0, 0, 0));
                continue;
            }
            var r = WuVolume(box, mr) / w;
            var g = WuVolume(box, mg) / w;
            var b = WuVolume(box, mb) / w;
            palette.Add(new Rgb((byte)r, (byte)g, (byte)b));
        }
        while (palette.Count < maxColors) palette.Add(new Rgb(0, 0, 0));
        return palette;
    }

    private static int NearestColorIndex(IReadOnlyList<Rgb> palette, byte r, byte g, byte b)
    {
        var best = 0;
        var bestDist = int.MaxValue;
        for (var i = 0; i < palette.Count; i++)
        {
            var c = palette[i];
            var dr = r - c.R;
            var dg = g - c.G;
            var db = b - c.B;
            var d = dr * dr + dg * dg + db * db;
            if (d < bestDist)
            {
                bestDist = d;
                best = i;
                if (d == 0) break;
            }
        }
        return best;
    }

    private static int NearestColorIndexRgba(IReadOnlyList<Rgba> palette, byte r, byte g, byte b, byte a)
    {
        var best = 0;
        var bestDist = int.MaxValue;
        for (var i = 0; i < palette.Count; i++)
        {
            var c = palette[i];
            var dr = r - c.R;
            var dg = g - c.G;
            var db = b - c.B;
            var da = a - c.A;
            var d = dr * dr + dg * dg + db * db + da * da * 4;
            if (d < bestDist)
            {
                bestDist = d;
                best = i;
                if (d == 0) break;
            }
        }
        return best;
    }

    private static bool TryBuildExact8bpp(Rgba[] pixels, out byte[] indices, out List<Rgba> palette)
    {
        indices = new byte[pixels.Length];
        palette = new List<Rgba>(256);
        var map = new Dictionary<uint, byte>(256);
        for (var i = 0; i < pixels.Length; i++)
        {
            var p = pixels[i];
            var key = ((uint)p.R << 24) | ((uint)p.G << 16) | ((uint)p.B << 8) | p.A;
            if (!map.TryGetValue(key, out var pi))
            {
                if (palette.Count >= 256) return false;
                pi = (byte)palette.Count;
                palette.Add(p);
                map[key] = pi;
            }
            indices[i] = pi;
        }
        while (palette.Count < 256) palette.Add(new Rgba(0, 0, 0, 0));
        return true;
    }

    private static int CountUniqueRgba(Rgba[] pixels)
    {
        var set = new HashSet<uint>();
        for (var i = 0; i < pixels.Length; i++)
        {
            var p = pixels[i];
            var key = ((uint)p.R << 24) | ((uint)p.G << 16) | ((uint)p.B << 8) | p.A;
            set.Add(key);
        }
        return set.Count;
    }

    private static (Rgb[] rgbPixels, byte[] alphaPixels, int width, int height) ReadRgbaBitmap(string path)
    {
        using var src = new Bitmap(path);
        var width = src.Width;
        var height = src.Height;
        using var bmp = src.Clone(new Rectangle(0, 0, width, height), PixelFormat.Format32bppArgb);
        var rect = new Rectangle(0, 0, width, height);
        var data = bmp.LockBits(rect, ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
        try
        {
            var stride = data.Stride;
            var bytes = Math.Abs(stride) * height;
            var raw = new byte[bytes];
            Marshal.Copy(data.Scan0, raw, 0, bytes);
            var rgb = new Rgb[width * height];
            var alpha = new byte[width * height];
            var p = 0;
            for (var y = 0; y < height; y++)
            {
                var row = y * stride;
                for (var x = 0; x < width; x++, p++)
                {
                    var i = row + x * 4;
                    var b = raw[i + 0];
                    var g = raw[i + 1];
                    var r = raw[i + 2];
                    var a = raw[i + 3];
                    rgb[p] = new Rgb(r, g, b);
                    alpha[p] = a;
                }
            }
            return (rgb, alpha, width, height);
        }
        finally
        {
            bmp.UnlockBits(data);
        }
    }

    private static (int uniqueColorCount, bool quantized) PngToTm2(string src, string dst, bool convertAlpha)
    {
        var (rgbPixels, alphaPixels, width, height) = ReadRgbaBitmap(src);
        var rgbaPixels = new Rgba[rgbPixels.Length];
        for (var i = 0; i < rgbPixels.Length; i++)
        {
            var p = rgbPixels[i];
            var a = convertAlpha ? ToPs2Alpha(alphaPixels[i]) : alphaPixels[i];
            rgbaPixels[i] = new Rgba(p.R, p.G, p.B, a);
        }
        var uniqueColorCount = CountUniqueRgba(rgbaPixels);

        byte[] indices;
        List<Rgba> finalPalette;
        var quantized = uniqueColorCount > 256;
        if (!quantized && TryBuildExact8bpp(rgbaPixels, out var exactIndices, out var exactPalette))
        {
            indices = exactIndices;
            finalPalette = exactPalette;
        }
        else
        {
            var paletteRgb = QuantizeWuRgb(rgbaPixels, 256);
            indices = new byte[rgbPixels.Length];
            var indexCache = new Dictionary<uint, byte>(4096);
            var paletteAlphaMax = new int[256];
            Array.Fill(paletteAlphaMax, -1);
            for (var i = 0; i < rgbPixels.Length; i++)
            {
                var p = rgbaPixels[i];
                var key = ((uint)p.R << 16) | ((uint)p.G << 8) | p.B;
                if (!indexCache.TryGetValue(key, out var idxByte))
                {
                    idxByte = (byte)NearestColorIndex(paletteRgb, p.R, p.G, p.B);
                    indexCache[key] = idxByte;
                }
                indices[i] = idxByte;
                var idx = idxByte;
                if (p.A > paletteAlphaMax[idx]) paletteAlphaMax[idx] = p.A;
            }
            finalPalette = new List<Rgba>(256);
            for (var i = 0; i < 256; i++)
            {
                var c = paletteRgb[i];
                var a = paletteAlphaMax[i] >= 0 ? (byte)paletteAlphaMax[i] : (byte)0;
                finalPalette.Add(new Rgba(c.R, c.G, c.B, a));
            }
        }
        var swizzled = SwizzlePalette256(finalPalette);
        var paletteBytes = new byte[256 * 4];
        for (var i = 0; i < 256; i++)
        {
            paletteBytes[i * 4 + 0] = swizzled[i].R;
            paletteBytes[i * 4 + 1] = swizzled[i].G;
            paletteBytes[i * 4 + 2] = swizzled[i].B;
            paletteBytes[i * 4 + 3] = swizzled[i].A;
        }

        using var fs = File.Create(dst);
        fs.Write(BuildTim2FileHeader());
        fs.Write(BuildTim2PictureHeader(indices.Length, paletteBytes.Length, width, height));
        fs.Write(indices);
        fs.Write(paletteBytes);
        return (uniqueColorCount, quantized);
    }

    private static void Tm2ToPng(string src, string dst, bool convertAlpha)
    {
        using var fs = File.OpenRead(src);
        using var br = new BinaryReader(fs);
        var magic = br.ReadBytes(4);
        if (magic.Length != 4 || magic[0] != 'T' || magic[1] != 'I' || magic[2] != 'M' || magic[3] != '2') throw new InvalidDataException("Not a TIM2 file");
        var version = br.ReadByte();
        var alignment = br.ReadByte();
        var textureCount = br.ReadUInt16();
        _ = version;
        _ = textureCount;
        fs.Seek(8, SeekOrigin.Current);
        if (alignment != 0) fs.Seek(0x70, SeekOrigin.Current);

        var header = br.ReadBytes(0x30);
        if (header.Length < 0x30) throw new EndOfStreamException("Invalid TIM2 picture header");
        var paletteSize = BinaryPrimitives.ReadInt32LittleEndian(header.AsSpan(0x04, 4));
        var imageSize = BinaryPrimitives.ReadInt32LittleEndian(header.AsSpan(0x08, 4));
        var headerSize = BinaryPrimitives.ReadUInt16LittleEndian(header.AsSpan(0x0C, 2));
        var width = BinaryPrimitives.ReadUInt16LittleEndian(header.AsSpan(0x14, 2));
        var height = BinaryPrimitives.ReadUInt16LittleEndian(header.AsSpan(0x16, 2));
        if (headerSize > 0x30) fs.Seek(headerSize - 0x30, SeekOrigin.Current);

        var imageData = br.ReadBytes(imageSize);
        var paletteData = br.ReadBytes(paletteSize);
        if (imageData.Length != imageSize || paletteData.Length != paletteSize) throw new EndOfStreamException("Unexpected EOF");

        var swizzled = new Rgba[256];
        for (var i = 0; i < 256 && i * 4 + 3 < paletteData.Length; i++)
        {
            swizzled[i] = new Rgba(paletteData[i * 4 + 0], paletteData[i * 4 + 1], paletteData[i * 4 + 2], paletteData[i * 4 + 3]);
        }
        var palette = DeswizzlePalette256(swizzled);

        var bmp = new Bitmap(width, height, PixelFormat.Format32bppArgb);
        var rect = new Rectangle(0, 0, width, height);
        var data = bmp.LockBits(rect, ImageLockMode.WriteOnly, PixelFormat.Format32bppArgb);
        try
        {
            var stride = data.Stride;
            var raw = new byte[Math.Abs(stride) * height];
            var p = 0;
            for (var y = 0; y < height; y++)
            {
                var row = y * stride;
                for (var x = 0; x < width; x++, p++)
                {
                    var index = p < imageData.Length ? imageData[p] : (byte)0;
                    var c = palette[index];
                    var i = row + x * 4;
                    raw[i + 0] = c.B;
                    raw[i + 1] = c.G;
                    raw[i + 2] = c.R;
                    raw[i + 3] = convertAlpha ? FixAlphaPs2(c.A) : c.A;
                }
            }
            Marshal.Copy(raw, 0, data.Scan0, raw.Length);
        }
        finally
        {
            bmp.UnlockBits(data);
        }
        bmp.Save(dst, ImageFormat.Png);
        bmp.Dispose();
    }

    private static void BatchDecode(string srcDir, string dstDir, bool convertAlpha)
    {
        Directory.CreateDirectory(dstDir);
        var files = Directory.EnumerateFiles(srcDir, "*.tm2", SearchOption.TopDirectoryOnly).OrderBy(x => x, StringComparer.OrdinalIgnoreCase).ToList();
        if (files.Count == 0)
        {
            Console.WriteLine("No tm2 files found");
            return;
        }
        var ok = 0;
        var fail = 0;
        var logLock = new object();
        var options = new ParallelOptions { MaxDegreeOfParallelism = Environment.ProcessorCount };
        Parallel.ForEach(files, options, f =>
        {
            var outPath = Path.Combine(dstDir, Path.GetFileNameWithoutExtension(f) + ".png");
            try
            {
                Tm2ToPng(f, outPath, convertAlpha);
                Interlocked.Increment(ref ok);
                lock (logLock) Console.WriteLine($"[OK] {Path.GetFileName(f)} -> {Path.GetFileName(outPath)}");
            }
            catch (Exception e)
            {
                Interlocked.Increment(ref fail);
                lock (logLock) Console.WriteLine($"[ERR] {Path.GetFileName(f)}: {e.Message}");
            }
        });
        Console.WriteLine($"Done: success={ok}, failed={fail}");
    }

    private static void BatchEncode(string srcDir, string dstDir, bool convertAlpha)
    {
        Directory.CreateDirectory(dstDir);
        var files = Directory.EnumerateFiles(srcDir, "*.png", SearchOption.TopDirectoryOnly).OrderBy(x => x, StringComparer.OrdinalIgnoreCase).ToList();
        if (files.Count == 0)
        {
            Console.WriteLine("No png files found");
            return;
        }
        var ok = 0;
        var fail = 0;
        var logLock = new object();
        var options = new ParallelOptions { MaxDegreeOfParallelism = Environment.ProcessorCount };
        Parallel.ForEach(files, options, f =>
        {
            var outPath = Path.Combine(dstDir, Path.GetFileNameWithoutExtension(f) + ".tm2");
            try
            {
                var info = PngToTm2(f, outPath, convertAlpha);
                Interlocked.Increment(ref ok);
                if (info.quantized) lock (logLock) Console.WriteLine($"[QTZ] {Path.GetFileName(f)} colors={info.uniqueColorCount} (>256)");
                lock (logLock) Console.WriteLine($"[OK] {Path.GetFileName(f)} -> {Path.GetFileName(outPath)}");
            }
            catch (Exception e)
            {
                Interlocked.Increment(ref fail);
                lock (logLock) Console.WriteLine($"[ERR] {Path.GetFileName(f)}: {e.Message}");
            }
        });
        Console.WriteLine($"Done: success={ok}, failed={fail}");
    }

    private static int Main(string[] args)
    {
        var argList = new List<string>(args);
        var convertAlpha = argList.Remove("-a");
        if (argList.Count != 3 || (argList[0] != "d" && argList[0] != "e"))
        {
            Console.WriteLine("Usage:");
            Console.WriteLine("tim2 [-a] d <tm2_dir> <png_dir>");
            Console.WriteLine("tim2 [-a] e <png_dir> <tm2_dir>");
            return 1;
        }

        var mode = argList[0];
        var srcDir = argList[1];
        var dstDir = argList[2];
        if (!Directory.Exists(srcDir))
        {
            Console.WriteLine($"Source directory not found: {srcDir}");
            return 1;
        }

        if (mode == "d") BatchDecode(srcDir, dstDir, convertAlpha);
        else BatchEncode(srcDir, dstDir, convertAlpha);
        return 0;
    }
}
