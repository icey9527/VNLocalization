using SixLabors.ImageSharp;
using SixLabors.ImageSharp.Formats.Png;
using SixLabors.ImageSharp.PixelFormats;

namespace Kid.Script;

public static class Tim2Png
{
    public readonly record struct Tim2Metadata(
        int Version,
        int Format,
        int Reserved6,
        int Reserved7,
        int TotalSize,
        int PhClut,
        int PhImg,
        int PhHdr,
        int PhColors,
        int PhFmt,
        int MipmapCount,
        int ClutType,
        int PhImgType,
        int Width,
        int Height,
        ulong GsTex0,
        ulong GsTex1,
        int GsRegs,
        int GsTexClut);

    public readonly record struct Tim2ContainerMetadata(
        int Count,
        int HeaderSize,
        IReadOnlyList<int> SegmentLengths,
        IReadOnlyList<Tim2Metadata> Images);

    public readonly record struct Tim2Info(
        int Width,
        int Height,
        int Psm,
        int Bpp,
        int PaletteColors,
        bool Indexed,
        bool Swizzled);

    public static bool IsTim2(byte[] d) =>
        d.Length >= 4 && d[0] == 0x54 && d[1] == 0x49 && d[2] == 0x4D && d[3] == 0x32;

    public static Tim2Info Inspect(byte[] tim2)
    {
        var hdr = ReadHeader(tim2);
        return new Tim2Info(hdr.Width, hdr.Height, hdr.Psm, hdr.Bpp, hdr.PhColors, hdr.Indexed, hdr.Swizzled);
    }

    public static Tim2Metadata InspectMetadata(byte[] tim2)
    {
        var hdr = ReadHeader(tim2);
        return new Tim2Metadata(
            d8(tim2, 4),
            d8(tim2, 5),
            d8(tim2, 6),
            d8(tim2, 7),
            (int)LE32(tim2, 0x10),
            hdr.PhClut,
            hdr.PhImg,
            hdr.PhHdr,
            hdr.PhColors,
            hdr.PhFmt,
            d8(tim2, 0x1A),
            d8(tim2, 0x1B),
            hdr.PhImgType,
            hdr.Width,
            hdr.Height,
            LE64(tim2, 0x28),
            LE64(tim2, 0x30),
            (int)LE32(tim2, 0x38),
            (int)LE32(tim2, 0x3C));
    }

    public static Tim2ContainerMetadata? InspectContainerMetadata(byte[] d)
    {
        var container = ParseContainer(d);
        if (container == null)
        {
            if (!IsTim2(d))
                return null;
            return new Tim2ContainerMetadata(1, 0, new[] { d.Length }, new[] { InspectMetadata(d) });
        }

        int count = (int)LE32(d, 0);
        int headerSize = 8 + (count - 1) * 4;
        headerSize = Align16(headerSize);
        var lengths = new List<int>(container.Count);
        var images = new List<Tim2Metadata>(container.Count);
        foreach (var (offset, length) in container)
        {
            lengths.Add(length);
            var slice = new byte[length];
            Array.Copy(d, offset, slice, 0, length);
            images.Add(InspectMetadata(slice));
        }
        return new Tim2ContainerMetadata(count, headerSize, lengths, images);
    }

    public static List<Tim2Info>? InspectContainer(byte[] d)
    {
        var container = ParseContainer(d);
        if (container == null)
        {
            if (IsTim2(d))
                return new List<Tim2Info> { Inspect(d) };
            return null;
        }

        var infos = new List<Tim2Info>(container.Count);
        foreach (var (offset, length) in container)
        {
            var slice = new byte[length];
            Array.Copy(d, offset, slice, 0, length);
            infos.Add(Inspect(slice));
        }
        return infos;
    }

    public static byte[] ConvertToPng(byte[] tim2)
    {
        var (w, h, rgba) = DecodeTim2(tim2);
        return WritePngRaw(w, h, rgba);
    }

    static (int w, int h, byte[] rgba) DecodeTim2(byte[] d)
    {
        var hdr = ReadHeader(d);
        int dataPos = hdr.DataPos;
        byte[]? clut = null;
        if (hdr.PhClut > 0 && hdr.PhColors > 0)
        {
            clut = new byte[hdr.PhColors * 4];
            Array.Copy(d, dataPos, clut, 0, Math.Min(clut.Length, d.Length - dataPos));
            if (hdr.Psm == 0x13 && hdr.PhColors >= 256)
                clut = DeswizzlePalette256(clut);
            dataPos += (int)hdr.PhClut;
            dataPos = Align16(dataPos);
        }

        byte[] imgData = new byte[hdr.PhImg];
        Array.Copy(d, dataPos, imgData, 0, Math.Min(imgData.Length, d.Length - dataPos));
        if (hdr.Swizzled)
            imgData = Deswizzle(imgData, hdr.Width, hdr.Height, hdr.Bpp, hdr.Tbw);

        return DecodePixels(imgData, clut, hdr.Width, hdr.Height, hdr.Bpp, hdr.Psm);
    }

    static byte[] Deswizzle(byte[] src, int w, int h, int bpp, int tbw)
    {
        byte[] dst = new byte[src.Length];
        int bufW = tbw * 64;
        if (bpp == 8)
        {
            for (int y = 0; y < h; y++)
            for (int x = 0; x < w; x++)
            {
                int si = Swizzle8(x, y, bufW);
                if ((uint)si < (uint)src.Length)
                    dst[y * w + x] = src[si];
            }
        }
        else if (bpp == 4)
        {
            int stride = (w + 1) / 2;
            for (int y = 0; y < h; y++)
            for (int x = 0; x < w; x += 2)
            {
                int si = Swizzle4(x / 2, y, bufW / 2);
                if ((uint)si < (uint)src.Length)
                    dst[y * stride + x / 2] = src[si];
            }
        }
        return dst;
    }

    static byte[] Swizzle(byte[] src, int w, int h, int bpp, int tbw)
    {
        byte[] dst = new byte[src.Length];
        int bufW = tbw * 64;
        if (bpp == 8)
        {
            for (int y = 0; y < h; y++)
            for (int x = 0; x < w; x++)
            {
                int di = Swizzle8(x, y, bufW);
                if ((uint)di < (uint)dst.Length)
                    dst[di] = src[y * w + x];
            }
        }
        else if (bpp == 4)
        {
            int stride = (w + 1) / 2;
            for (int y = 0; y < h; y++)
            for (int x = 0; x < w; x += 2)
            {
                int di = Swizzle4(x / 2, y, bufW / 2);
                int si = y * stride + x / 2;
                if ((uint)di < (uint)dst.Length && (uint)si < (uint)src.Length)
                    dst[di] = src[si];
            }
        }
        return dst;
    }

    static int Swizzle8(int x, int y, int bufW)
    {
        int bx = x >> 4, by = y >> 3, px = x & 15, py = y & 7;
        int pair = (px + py * 16) / 16;
        int off = px % 4 + ((px >> 2) & 1) * 4 + pair * 8;
        return (by * bufW + bx) * 128 + off;
    }

    static int Swizzle4(int x, int y, int bufW)
    {
        int bx = x >> 5, by = y >> 3, px = x & 31, py = y & 7;
        int pair = (px + py * 32) / 32;
        int off = px % 8 + ((px >> 3) & 1) * 8 + pair * 16;
        return (by * bufW + bx) * 128 + off;
    }

    static (int w, int h, byte[] rgba) DecodePixels(byte[] img, byte[]? clut, int w, int h, int bpp, int psm)
    {
        var rgba = new byte[w * h * 4];
        if (psm == 0)
        {
            int bytesPerPixel = img.Length / (w * h);
            if (bytesPerPixel >= 4)
            {
                for (int i = 0; i < w * h; i++)
                {
                    uint px = BitConverter.ToUInt32(img, i * 4);
                    rgba[i * 4] = (byte)(px & 0xFF);
                    rgba[i * 4 + 1] = (byte)((px >> 8) & 0xFF);
                    rgba[i * 4 + 2] = (byte)((px >> 16) & 0xFF);
                    rgba[i * 4 + 3] = FixA((byte)(px >> 24));
                }
            }
            else
            {
                for (int i = 0; i < w * h; i++)
                {
                    rgba[i * 4] = img[i * 3];
                    rgba[i * 4 + 1] = img[i * 3 + 1];
                    rgba[i * 4 + 2] = img[i * 3 + 2];
                    rgba[i * 4 + 3] = 255;
                }
            }
        }
        else if (psm == 2 && bpp == 16)
        {
            for (int i = 0; i < w * h; i++)
            {
                ushort px = BitConverter.ToUInt16(img, i * 2);
                rgba[i * 4] = (byte)((px & 0x1F) * 255 / 31);
                rgba[i * 4 + 1] = (byte)(((px >> 5) & 0x1F) * 255 / 31);
                rgba[i * 4 + 2] = (byte)(((px >> 10) & 0x1F) * 255 / 31);
                rgba[i * 4 + 3] = (px & 0x8000) != 0 ? (byte)255 : (byte)0;
            }
        }
        else if (clut != null && clut.Length >= 4)
        {
            int mask = bpp == 4 ? 0x0F : 0xFF;
            int maxIdx = bpp == 4 ? 16 : 256;
            for (int i = 0; i < w * h; i++)
            {
                int bo = bpp == 4 ? i / 2 : i;
                int nb = bpp == 4 ? ((i & 1) != 0 ? 0 : 4) : 0;
                int idx = Math.Min((img[bo] >> nb) & mask, maxIdx - 1) * 4;
                if (idx + 3 < clut.Length)
                {
                    rgba[i * 4] = clut[idx];
                    rgba[i * 4 + 1] = clut[idx + 1];
                    rgba[i * 4 + 2] = clut[idx + 2];
                    rgba[i * 4 + 3] = FixA(clut[idx + 3]);
                }
            }
        }
        return (w, h, rgba);
    }

    public static (int w, int h, byte[] rgba) PngDecode(byte[] png)
    {
        using var image = Image.Load<Rgba32>(png);
        var rgba = new byte[image.Width * image.Height * 4];
        image.CopyPixelDataTo(rgba);
        return (image.Width, image.Height, rgba);
    }

    public static byte[] WritePngRaw(int w, int h, byte[] rgba)
    {
        using var image = Image.LoadPixelData<Rgba32>(rgba, w, h);
        using var ms = new MemoryStream();
        image.Save(ms, new PngEncoder());
        return ms.ToArray();
    }

    public static byte[] BuildFromPng(byte[] pngData, byte[] tmpl)
    {
        var (w, h, rgba) = PngDecode(pngData);
        var hdr = ReadHeader(tmpl);
        if (w != hdr.Width || h != hdr.Height)
            throw new InvalidDataException($"PNG size mismatch: got {w}x{h}, expected {hdr.Width}x{hdr.Height}");

        var result = new byte[tmpl.Length];
        Array.Copy(tmpl, result, tmpl.Length);

        if (hdr.Indexed)
        {
            WriteIndexed(result, tmpl, hdr, rgba);
            return result;
        }

        if (hdr.Psm == 2)
        {
            for (int i = 0; i < w * h; i++)
            {
                ushort px = EncodePsmct16(rgba, i * 4);
                WriteLE16(result, hdr.ImageDataPos + i * 2, px);
            }
            return result;
        }

        int bpp = (hdr.Psm == 0 && hdr.PhImg >= w * h * 3 && hdr.PhImg < w * h * 4) ? 3 : 4;
        for (int i = 0; i < w * h; i++)
        {
            int dstOff = hdr.ImageDataPos + i * bpp;
            result[dstOff] = rgba[i * 4];
            result[dstOff + 1] = rgba[i * 4 + 1];
            result[dstOff + 2] = rgba[i * 4 + 2];
            if (bpp == 4)
                result[dstOff + 3] = ToPs2(rgba[i * 4 + 3]);
        }

        return result;
    }

    public static byte[] BuildFromPng(byte[] pngData, Tim2Metadata meta)
    {
        var (w, h, rgba) = PngDecode(pngData);
        if (w != meta.Width || h != meta.Height)
            throw new InvalidDataException($"PNG size mismatch: got {w}x{h}, expected {meta.Width}x{meta.Height}");

        if (meta.PhClut != 0 || meta.PhColors != 0)
            throw new NotSupportedException("Indexed TIM2 rebuild is not implemented for metadata-only path");

        int pixelBytes = meta.PhImg switch
        {
            var n when n == w * h * 4 => 4,
            var n when n == w * h * 3 => 3,
            var n when n == w * h * 2 => 2,
            _ => throw new NotSupportedException($"Unsupported TIM2 image size for metadata-only path: PhImg={meta.PhImg}")
        };

        int totalSize = 0x10 + meta.PhHdr + meta.PhImg;
        byte[] result = new byte[totalSize];
        result[0] = 0x54;
        result[1] = 0x49;
        result[2] = 0x4D;
        result[3] = 0x32;
        result[4] = (byte)meta.Version;
        result[5] = (byte)meta.Format;
        result[6] = (byte)meta.Reserved6;
        result[7] = (byte)meta.Reserved7;

        WriteLE32(result, 0x10, (uint)totalSize);
        WriteLE32(result, 0x14, (uint)meta.PhClut);
        WriteLE32(result, 0x18, (uint)meta.PhImg);
        WriteLE16(result, 0x1C, (ushort)meta.PhHdr);
        WriteLE16(result, 0x1E, (ushort)meta.PhColors);
        result[0x20] = (byte)meta.PhFmt;
        result[0x21] = 0;
        result[0x22] = (byte)meta.MipmapCount;
        result[0x23] = (byte)meta.PhImgType;
        WriteLE16(result, 0x24, (ushort)meta.Width);
        WriteLE16(result, 0x26, (ushort)meta.Height);
        WriteLE64(result, 0x28, meta.GsTex0);
        WriteLE64(result, 0x30, meta.GsTex1);
        WriteLE32(result, 0x38, (uint)meta.GsRegs);
        WriteLE32(result, 0x3C, (uint)meta.GsTexClut);

        int dstOff = 0x10 + meta.PhHdr;
        for (int i = 0; i < w * h; i++)
        {
            int srcOff = i * 4;
            if (pixelBytes == 2)
            {
                ushort px = EncodePsmct16(rgba, srcOff);
                WriteLE16(result, dstOff, px);
            }
            else
            {
                result[dstOff] = rgba[srcOff];
                result[dstOff + 1] = rgba[srcOff + 1];
                result[dstOff + 2] = rgba[srcOff + 2];
                if (pixelBytes == 4)
                    result[dstOff + 3] = ToPs2(rgba[srcOff + 3]);
            }
            dstOff += pixelBytes;
        }

        return result;
    }

    public static byte[] BuildContainerFromPngs(IReadOnlyList<byte[]> pngs, Tim2ContainerMetadata meta)
    {
        if (pngs.Count != meta.Images.Count || meta.Count != meta.Images.Count || meta.SegmentLengths.Count != meta.Images.Count)
            throw new InvalidDataException("TIM2 container metadata/image count mismatch");

        if (meta.Count == 1 && meta.HeaderSize == 0)
            return BuildFromPng(pngs[0], meta.Images[0]);

        var segments = new List<byte[]>(pngs.Count);
        for (int i = 0; i < pngs.Count; i++)
        {
            byte[] slice = BuildFromPng(pngs[i], meta.Images[i]);
            if (slice.Length != meta.SegmentLengths[i])
                throw new InvalidDataException($"TIM2 slice length mismatch at {i}: got {slice.Length}, expected {meta.SegmentLengths[i]}");
            segments.Add(slice);
        }

        int total = meta.HeaderSize + segments.Sum(x => x.Length);
        byte[] result = new byte[total];
        WriteLE32(result, 0, (uint)meta.Count);
        WriteLE32(result, 4, 0);
        int cursor = meta.HeaderSize;
        for (int i = 0; i < segments.Count - 1; i++)
        {
            cursor += segments[i].Length;
            WriteLE32(result, 8 + i * 4, (uint)((cursor - meta.HeaderSize) / 16));
        }
        cursor = meta.HeaderSize;
        foreach (var segment in segments)
        {
            Array.Copy(segment, 0, result, cursor, segment.Length);
            cursor += segment.Length;
        }
        return result;
    }

    static void WriteIndexed(byte[] result, byte[] tmpl, Tim2Header hdr, byte[] rgba)
    {
        int palettePos = hdr.DataPos;
        int paletteEntries = Math.Min(hdr.PhColors, Math.Max(1, hdr.PhClut / 4));
        byte[] palette = new byte[paletteEntries * 4];
        Array.Copy(tmpl, palettePos, palette, 0, Math.Min(palette.Length, tmpl.Length - palettePos));
        if (hdr.Psm == 0x13 && paletteEntries >= 256)
            palette = DeswizzlePalette256(palette);

        byte[] linear = hdr.Psm switch
        {
            0x13 => BuildIndexed8Linear(rgba, palette, paletteEntries),
            0x14 => BuildIndexed4Linear(rgba, palette, paletteEntries),
            _ => throw new NotSupportedException($"Unsupported indexed PSM: 0x{hdr.Psm:X}")
        };

        byte[] img = hdr.Swizzled ? Swizzle(linear, hdr.Width, hdr.Height, hdr.Bpp, hdr.Tbw) : linear;
        Array.Copy(img, 0, result, hdr.ImageDataPos, Math.Min(img.Length, result.Length - hdr.ImageDataPos));
    }

    static byte[] BuildIndexed8Linear(byte[] rgba, byte[] palette, int paletteEntries)
    {
        byte[] linear = new byte[rgba.Length / 4];
        for (int i = 0; i < linear.Length; i++)
            linear[i] = (byte)FindBestPaletteIndex(rgba, i * 4, palette, paletteEntries);
        return linear;
    }

    static byte[] BuildIndexed4Linear(byte[] rgba, byte[] palette, int paletteEntries)
    {
        int pxCount = rgba.Length / 4;
        byte[] linear = new byte[(pxCount + 1) / 2];
        for (int i = 0; i < pxCount; i++)
        {
            int idx = FindBestPaletteIndex(rgba, i * 4, palette, paletteEntries) & 0x0F;
            int bo = i / 2;
            if ((i & 1) == 0)
                linear[bo] = (byte)(idx << 4);
            else
                linear[bo] |= (byte)idx;
        }
        return linear;
    }

    static int FindBestPaletteIndex(byte[] rgba, int pxOff, byte[] palette, int paletteEntries)
    {
        int bestIdx = 0;
        int bestDist = int.MaxValue;
        byte r = rgba[pxOff];
        byte g = rgba[pxOff + 1];
        byte b = rgba[pxOff + 2];
        byte a = ToPs2(rgba[pxOff + 3]);
        for (int i = 0; i < paletteEntries; i++)
        {
            int po = i * 4;
            int dr = r - palette[po];
            int dg = g - palette[po + 1];
            int db = b - palette[po + 2];
            int da = a - palette[po + 3];
            int dist = dr * dr + dg * dg + db * db + da * da * 4;
            if (dist < bestDist)
            {
                bestDist = dist;
                bestIdx = i;
                if (dist == 0)
                    break;
            }
        }
        return bestIdx;
    }

    static byte[] DeswizzlePalette256(byte[] paletteBytes)
    {
        byte[] dst = new byte[paletteBytes.Length];
        for (int b = 0; b < 8; b++)
        {
            int srcBase = b * 32 * 4;
            CopyPaletteBlock(paletteBytes, srcBase + 0 * 4, dst, srcBase + 0 * 4, 8);
            CopyPaletteBlock(paletteBytes, srcBase + 8 * 4, dst, srcBase + 16 * 4, 8);
            CopyPaletteBlock(paletteBytes, srcBase + 16 * 4, dst, srcBase + 8 * 4, 8);
            CopyPaletteBlock(paletteBytes, srcBase + 24 * 4, dst, srcBase + 24 * 4, 8);
        }
        return dst;
    }

    static void CopyPaletteBlock(byte[] src, int srcOff, byte[] dst, int dstOff, int count) =>
        Array.Copy(src, srcOff, dst, dstOff, count * 4);

    public static List<(int offset, int length)>? ParseContainer(byte[] d)
    {
        if (d.Length < 8) return null;
        int count = (int)LE32(d, 0);
        if (count < 1 || count > 100) return null;
        if (LE32(d, 4) != 0) return null;
        int hdrSize = 8 + (count - 1) * 4;
        hdrSize = Align16(hdrSize);
        if (hdrSize >= d.Length) return null;
        if (!IsTim2At(d, hdrSize)) return null;
        var images = new List<(int, int)>();
        int prevEnd = hdrSize;
        for (int i = 0; i < count - 1; i++)
        {
            uint v = LE32(d, 8 + i * 4);
            if (v == 0) break;
            int end = hdrSize + (int)v * 16;
            if (end <= prevEnd || end > d.Length) return null;
            images.Add((prevEnd, end - prevEnd));
            prevEnd = end;
        }
        images.Add((prevEnd, d.Length - prevEnd));
        return images;
    }

    public static byte[] ConvertToPng(byte[] data, int offset, int length)
    {
        var slice = new byte[length];
        Array.Copy(data, offset, slice, 0, length);
        return ConvertToPng(slice);
    }

    static ushort EncodePsmct16(byte[] rgba, int off)
    {
        int r = rgba[off] * 31 / 255;
        int g = rgba[off + 1] * 31 / 255;
        int b = rgba[off + 2] * 31 / 255;
        int a = rgba[off + 3] >= 128 ? 1 : 0;
        return (ushort)(r | (g << 5) | (b << 10) | (a << 15));
    }

    static Tim2Header ReadHeader(byte[] d)
    {
        int phPos = 0x10;
        _ = LE32(d, phPos); phPos += 4;
        int phClut = (int)LE32(d, phPos); phPos += 4;
        int phImg = (int)LE32(d, phPos); phPos += 4;
        ushort phHdr = LE16(d, phPos); phPos += 2;
        ushort phColors = LE16(d, phPos); phPos += 2;
        byte phFmt = d[phPos]; phPos += 1;
        _ = d[phPos]; phPos += 1;
        _ = d[phPos]; phPos += 1;
        byte phImgType = d[phPos]; phPos += 1;
        ushort width = LE16(d, phPos); phPos += 2;
        ushort height = LE16(d, phPos); phPos += 2;
        ulong gsTex0 = LE64(d, phPos);
        int psm = (int)(gsTex0 & 0x3F);
        int tbw = (int)((gsTex0 >> 14) & 0x3F);
        int bpp = psm switch
        {
            0 => 32,
            2 => 16,
            0x13 => 8,
            0x14 => 4,
            0x30 => 32,
            _ => phFmt switch { 0x50 => 8, _ => 32 }
        };
        int dataPos = 0x10 + phHdr;
        int imageDataPos = dataPos;
        if (phClut > 0 && phColors > 0)
        {
            imageDataPos += phClut;
            imageDataPos = Align16(imageDataPos);
        }
        return new Tim2Header(phClut, phImg, phHdr, phColors, phFmt, phImgType, width, height, psm, tbw, bpp, dataPos, imageDataPos);
    }

    static int Align16(int v) => (v + 15) & ~15;
    static byte FixA(byte a) { int v = a * 2 - 1; if (v < 0) v = 0; if (v > 255) v = 255; return (byte)v; }
    static byte ToPs2(byte a) { if (a == 0) return 0; int v = (a + 1) >> 1; if (v > 128) v = 128; return (byte)v; }
    static bool IsTim2At(byte[] d, int off) => off + 4 <= d.Length && d[off] == 0x54 && d[off + 1] == 0x49 && d[off + 2] == 0x4D && d[off + 3] == 0x32;
    static ushort LE16(byte[] d, int o) => (ushort)(d[o] | (d[o + 1] << 8));
    static uint LE32(byte[] d, int o) => (uint)(d[o] | (d[o + 1] << 8) | (d[o + 2] << 16) | (d[o + 3] << 24));
    static ulong LE64(byte[] d, int o) => LE32(d, o) | ((ulong)LE32(d, o + 4) << 32);
    static byte d8(byte[] d, int o) => d[o];
    static void WriteLE16(byte[] d, int o, ushort v) { d[o] = (byte)v; d[o + 1] = (byte)(v >> 8); }
    static void WriteLE32(byte[] d, int o, uint v) { d[o] = (byte)v; d[o + 1] = (byte)(v >> 8); d[o + 2] = (byte)(v >> 16); d[o + 3] = (byte)(v >> 24); }
    static void WriteLE64(byte[] d, int o, ulong v) { WriteLE32(d, o, (uint)(v & 0xFFFFFFFF)); WriteLE32(d, o + 4, (uint)(v >> 32)); }

    readonly record struct Tim2Header(
        int PhClut,
        int PhImg,
        ushort PhHdr,
        ushort PhColors,
        byte PhFmt,
        byte PhImgType,
        ushort Width,
        ushort Height,
        int Psm,
        int Tbw,
        int Bpp,
        int DataPos,
        int ImageDataPos)
    {
        public bool Indexed => PhColors > 0 && PhClut > 0;
        public bool Swizzled => (PhImgType & 0x04) != 0;
    }
}
