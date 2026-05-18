namespace Kid.Script;

/// <summary>PS2 tiled bitmap (bg.afs BIP files).</summary>
public static class RawBg
{
    public readonly record struct RawBgMetadata(
        int Type,
        int Width,
        int Height);

    public readonly record struct RawBgRebuildMetadata(
        int Type,
        int Width,
        int Height,
        int PixelOffset,
        string HeaderHex,
        int HeaderWords,
        int PixelDataOffsetWord,
        int EncodedPixelBytes,
        int Header0C,
        int Header14,
        int Header18,
        int Header90,
        int Header94,
        int Header98,
        int Header9C,
        int HeaderA0,
        int HeaderA4,
        IReadOnlyList<BgBlock> Blocks);

    readonly record struct LayoutParams(
        int Bpp,
        uint Dy,
        bool Sliced);

    public readonly record struct BgBlock(int BaseX, int BaseY, int Tile, int Cols, int Rows);

    public static bool IsRawBg(byte[] d)
    {
        if (d.Length < 0x100) return false;
        int type = BitConverter.ToInt32(d, 0);
        if (type != 5 && !(type >= 6 && type <= 12)) return false;

        uint fstart = BitConverter.ToUInt16(d, 0x10);
        if (fstart != 0x100) return false;

        uint realSign = type == 5 ? 0x14u : (uint)(type * 4);
        uint fcheck = (uint)(BitConverter.ToUInt16(d, (int)realSign) & 0x3FFF);
        if (fcheck != fstart) return false;

        int w = BitConverter.ToUInt16(d, 0x88);
        int h = BitConverter.ToUInt16(d, 0x8A);
        if (w < 16 || w > 2560 || h < 16 || h > 1440) return false;

        if (d.Length < 0x94)
            return false;

        uint sizeSign = BitConverter.ToUInt16(d, 0x90);
        uint sizeSignHigh = BitConverter.ToUInt16(d, 0x92);
        if (sizeSign != 0 || sizeSignHigh == 0)
            return false;

        return true;
    }

    public static byte[] ConvertToPng(byte[] d)
    {
        uint palStart = BitConverter.ToUInt16(d, 0x0C);
        int w = BitConverter.ToUInt16(d, 0x88);
        int h = BitConverter.ToUInt16(d, 0x8A);
        int type = BitConverter.ToInt32(d, 0);

        if (TryDecodeBlockAtlas(d, type, w, h, out var atlasRgba))
            return Tim2Png.WritePngRaw(w, h, atlasRgba);

        var layout = AnalyzeLayout(d);

        uint dy = layout.Dy;
        uint dx = dy * 32;
        bool sliced = layout.Sliced;

        int m_bpp = layout.Bpp / 8;
        int pxStart = BitConverter.ToUInt16(d, 0x10);
        var pixels = new byte[w * h * m_bpp];
        var src = d.AsSpan(pxStart);

        if (sliced && m_bpp == 1 && dy == 16)
            DeswizzleSliced8(src, pixels, w, h, dx, dy);
        else if (sliced)
            DeswizzleSliced32(src, pixels, w, h, dx, dy, m_bpp);
        else
            DeswizzleNonSliced(src, pixels, w, h, dx, dy, m_bpp);

        if (m_bpp == 1)
        {
            var clut = d.AsSpan((int)palStart, 1024);
            var rgba = new byte[w * h * 4];
            for (int i = 0; i < w * h; i++)
            {
                int ci = pixels[i] * 4;
                rgba[i * 4] = clut[ci];
                rgba[i * 4 + 1] = clut[ci + 1];
                rgba[i * 4 + 2] = clut[ci + 2];
                rgba[i * 4 + 3] = FixAlpha(clut[ci + 3]);
            }
            return Tim2Png.WritePngRaw(w, h, rgba);
        }

        return Tim2Png.WritePngRaw(w, h, pixels);
    }

    static bool TryDecodeBlockAtlas(byte[] d, int type, int w, int h, out byte[] rgba)
    {
        rgba = Array.Empty<byte>();
        if (type < 6 || type > 12)
            return false;

        int headerWords = BitConverter.ToInt32(d, 0);
        if (headerWords < 6)
            return false;

        int pixelBase = BitConverter.ToInt32(d, (headerWords - 1) * 4);
        if (pixelBase < 0x100 || pixelBase >= d.Length)
            return false;

        int pixelBytes = d.Length - pixelBase;
        if (pixelBytes <= 0 || (pixelBytes % (512 * 4)) != 0)
            return false;

        var blocks = new List<BgBlock>();
        for (int i = 0; i < headerWords - 4; i++)
        {
            int blockOff = BitConverter.ToInt32(d, (i + 1) * 4);
            if (blockOff <= 0 || blockOff + 12 > pixelBase || blockOff + 12 > d.Length)
                continue;

            int groupCount = BitConverter.ToUInt16(d, blockOff);
            int baseY = 0;
            int baseX = 0;
            if (blockOff + 6 <= d.Length)
                baseX = BitConverter.ToInt16(d, blockOff + 4) * -2;

            int cur = blockOff + 12;
            for (int g = 0; g < groupCount; g++)
            {
                if (cur + 8 > pixelBase || cur + 8 > d.Length)
                    return false;

                int lenDwords = BitConverter.ToUInt16(d, cur);
                if (lenDwords < 2 || cur + lenDwords * 4 > pixelBase || cur + lenDwords * 4 > d.Length)
                    return false;

                int tile = BitConverter.ToUInt16(d, cur + 2);
                int dstX = baseX + d[cur + 4] * 16;
                int dstY = baseY + d[cur + 5] * 16;
                int cols = d[cur + 6];
                int rows = d[cur + 7];
                if (cols > 0 && rows > 0)
                    blocks.Add(new BgBlock(dstX, dstY, tile, cols, rows));
                cur += lenDwords * 4;
            }
        }

        if (blocks.Count == 0)
            return false;

        byte[] atlas = DecodeAtlas32(d, pixelBase);
        rgba = ComposeBlockAtlas(w, h, atlas, blocks);
        return true;
    }

    static byte[] DecodeAtlas32(byte[] d, int pixelBase)
    {
        const int atlasWidth = 512;
        int pixelBytes = d.Length - pixelBase;
        int atlasHeight = pixelBytes / (atlasWidth * 4);
        byte[] atlas = new byte[pixelBytes];
        DeswizzleNonSliced(d.AsSpan(pixelBase), atlas, atlasWidth, atlasHeight, 512, 16, 4);
        return atlas;
    }

    static byte[] ComposeBlockAtlas(int width, int height, byte[] atlas, IReadOnlyList<BgBlock> blocks)
    {
        const int atlasWidth = 512;
        const int tileSize = 16;
        int atlasHeight = atlas.Length / (atlasWidth * 4);
        byte[] rgba = new byte[width * height * 4];

        foreach (var block in blocks)
        {
            int srcTileX = (block.Tile & 0x1F) * tileSize;
            int srcTileY = (block.Tile >> 5) * tileSize;
            for (int row = 0; row < block.Rows; row++)
            {
                for (int col = 0; col < block.Cols; col++)
                {
                    int dstX = block.BaseX + col * tileSize;
                    int dstY = block.BaseY + row * tileSize;
                    if (dstX < 0 || dstY < 0 || dstX + tileSize > width || dstY + tileSize > height)
                    {
                        AdvanceTile(ref srcTileX, ref srcTileY, atlasWidth, tileSize);
                        continue;
                    }

                    for (int y = 0; y < tileSize; y++)
                    {
                        int ay = srcTileY + y;
                        if (ay >= atlasHeight) break;
                        int srcRow = (ay * atlasWidth + srcTileX) * 4;
                        int dstRow = ((dstY + y) * width + dstX) * 4;
                        for (int x = 0; x < tileSize; x++)
                        {
                            int srcPx = srcRow + x * 4;
                            int dstPx = dstRow + x * 4;
                            byte a = atlas[srcPx + 3];
                            if (a == 0 && rgba[dstPx + 3] != 0)
                                continue;
                            rgba[dstPx] = atlas[srcPx];
                            rgba[dstPx + 1] = atlas[srcPx + 1];
                            rgba[dstPx + 2] = atlas[srcPx + 2];
                            rgba[dstPx + 3] = a;
                        }
                    }
                    AdvanceTile(ref srcTileX, ref srcTileY, atlasWidth, tileSize);
                }
            }
        }
        return rgba;
    }

    static byte[] ComposeAtlasFromImage(byte[] rgba, int width, int height, IReadOnlyList<BgBlock> blocks, int encodedPixelBytes)
    {
        const int atlasWidth = 512;
        const int tileSize = 16;
        byte[] atlas = new byte[encodedPixelBytes];

        foreach (var block in blocks)
        {
            int dstTileX = (block.Tile & 0x1F) * tileSize;
            int dstTileY = (block.Tile >> 5) * tileSize;
            for (int row = 0; row < block.Rows; row++)
            {
                for (int col = 0; col < block.Cols; col++)
                {
                    int srcX = block.BaseX + col * tileSize;
                    int srcY = block.BaseY + row * tileSize;
                    for (int y = 0; y < tileSize; y++)
                    {
                        int imgY = srcY + y;
                        if ((uint)imgY >= (uint)height)
                            continue;
                        int atlasY = dstTileY + y;
                        int dstRow = (atlasY * atlasWidth + dstTileX) * 4;
                        int srcRow = (imgY * width + srcX) * 4;
                        for (int x = 0; x < tileSize; x++)
                        {
                            int imgX = srcX + x;
                            if ((uint)imgX >= (uint)width)
                                continue;
                            int srcPx = srcRow + x * 4;
                            int dstPx = dstRow + x * 4;
                            atlas[dstPx] = rgba[srcPx];
                            atlas[dstPx + 1] = rgba[srcPx + 1];
                            atlas[dstPx + 2] = rgba[srcPx + 2];
                            atlas[dstPx + 3] = rgba[srcPx + 3];
                        }
                    }
                    AdvanceTile(ref dstTileX, ref dstTileY, atlasWidth, tileSize);
                }
            }
        }

        return atlas;
    }

    static void AdvanceTile(ref int srcX, ref int srcY, int atlasWidth, int tileSize)
    {
        srcX += tileSize;
        if (srcX >= atlasWidth)
        {
            srcX = 0;
            srcY += tileSize;
        }
    }

    // Non-sliced: simple 512×16 tiling, no overlap
    static void DeswizzleNonSliced(Span<byte> src, byte[] dst, int w, int h, uint dx, uint dy, int bpp)
    {
        long focusH = ((long)w * h + dx - 1) / dx;
        long focusT = (focusH + dy - 1) / dy;
        int srcOff = 0;

        for (int t = 0; t < focusT; t++)
        {
            for (int y = 0; y < dy; y++)
            {
                for (int x = 0; x < dx; x++)
                {
                    long i2x = x + t * dx;
                    long i3t = i2x / w;
                    long i3x = i2x - i3t * w;
                    long i3y = i3t * dy + y;
                    if (i3x >= w || i3y >= h) { srcOff += bpp; continue; }
                    int dstOff = (int)((i3x + i3y * w) * bpp);
                    if (bpp == 4)
                    {
                        dst[dstOff] = src[srcOff];
                        dst[dstOff + 1] = src[srcOff + 1];
                        dst[dstOff + 2] = src[srcOff + 2];
                        dst[dstOff + 3] = FixAlpha(src[srcOff + 3]);
                    }
                    else
                    {
                        for (int k = 0; k < bpp; k++)
                            dst[dstOff + k] = src[srcOff + k];
                    }
                    srcOff += bpp;
                }
            }
        }
    }

    // Sliced 32-bit (or 8-bit/dy=32): tiling with -2 pixel overlap
    static void DeswizzleSliced32(Span<byte> src, byte[] dst, int w, int h, uint dx, uint dy, int bpp)
    {
        long dw = ((w + (dy - 2) - 1) / (dy - 2)) * dy;
        long dh = ((h + (dy - 2) - 1) / (dy - 2)) * dy;
        long focusH = (dw * dh + dx - 1) / dx;
        long focusT = (focusH + dy - 1) / dy;
        int srcOff = 0;

        for (int t = 0; t < focusT; t++)
        {
            for (int y = 0; y < dy; y++)
            {
                for (int x = 0; x < dx; x++)
                {
                    long i2x = x + t * dx;
                    long i3t = i2x / dw;
                    long i3x = i2x - i3t * dw;
                    long i3y = i3t * (dy - 2) + y;
                    long i4x = i3x - i3x / dy * dy + i3x / dy * (dy - 2);
                    if (i3x >= dw || i4x >= w || i3y >= h) { srcOff += bpp; continue; }
                    int dstOff = (int)((i4x + i3y * w) * bpp);
                    if (bpp == 4)
                    {
                        dst[dstOff] = src[srcOff];
                        dst[dstOff + 1] = src[srcOff + 1];
                        dst[dstOff + 2] = src[srcOff + 2];
                        dst[dstOff + 3] = FixAlpha(src[srcOff + 3]);
                    }
                    else
                    {
                        for (int k = 0; k < bpp; k++)
                            dst[dstOff + k] = src[srcOff + k];
                    }
                    srcOff += bpp;
                }
            }
        }
    }

    // Sliced 8-bit (dy=16)
    static void DeswizzleSliced8(Span<byte> src, byte[] dst, int w, int h, uint dx, uint dy)
    {
        long dytemp = dy * 2;
        long dw = ((w + (dytemp - 2) - 1) / (dytemp - 2)) * dytemp;
        long dh = ((h + (dytemp - 2) - 1) / (dytemp - 2)) * dytemp;
        long focusH = (dw * dh + dx - 1) / dx;
        long focusT = (focusH + dy - 1) / dy;
        if (focusT % 2 == 1) focusT++;
        int srcOff = 0;

        for (int t = 0; t < focusT; t++)
        {
            for (int y = 0; y < dy; y++)
            {
                for (int x = 0; x < dx; x++)
                {
                    byte pixel = src[srcOff++];
                    long i2x = x + (t >> 1) * dx;
                    long i3t = i2x / dw;
                    long i3x = i2x - i3t * dw;
                    long i3y = i3t * (dytemp - 2) + y + (t % 2) * dy - 1;
                    long i4x = i3x - i3x / dytemp * dytemp + i3x / dytemp * (dytemp - 2) - 1;
                    if (i3x >= dw || i4x >= w || i3y >= h || i4x < 0 || i3y < 0) continue;
                    dst[i4x + i3y * w] = pixel;
                }
            }
        }
    }

    /// <summary>Rebuild raw BIP from PNG pixels + original header template.</summary>
    public static RawBgMetadata InspectMetadata(byte[] d)
    {
        return new RawBgMetadata(
            BitConverter.ToInt32(d, 0),
            BitConverter.ToUInt16(d, 0x88),
            BitConverter.ToUInt16(d, 0x8A));
    }

    public static RawBgRebuildMetadata InspectRebuildMetadata(byte[] d)
    {
        int type = BitConverter.ToInt32(d, 0);
        int width = BitConverter.ToUInt16(d, 0x88);
        int height = BitConverter.ToUInt16(d, 0x8A);
        int headerWords = BitConverter.ToInt32(d, 0);
        int pixelOffsetWord = BitConverter.ToInt32(d, (headerWords - 1) * 4);
        int pixelOffset = pixelOffsetWord;
        int encodedPixelBytes = d.Length - pixelOffset;
        var blocks = ParseBlocks(d, type, pixelOffset);

        return new RawBgRebuildMetadata(
            type,
            width,
            height,
            pixelOffset,
            Convert.ToHexString(d, 0, pixelOffset),
            headerWords,
            pixelOffsetWord,
            encodedPixelBytes,
            ReadLE32(d, 0x0C),
            ReadLE32(d, 0x14),
            ReadLE32(d, 0x18),
            ReadLE32(d, 0x90),
            ReadLE32(d, 0x94),
            ReadLE32(d, 0x98),
            ReadLE32(d, 0x9C),
            ReadLE32(d, 0xA0),
            ReadLE32(d, 0xA4),
            blocks);
    }

    public static byte[] BuildFromPng(byte[] pngData, RawBgMetadata meta)
    {
        var (w, h, rgba) = Tim2Png.PngDecode(pngData);
        if (w != meta.Width || h != meta.Height)
            throw new InvalidDataException($"PNG size mismatch: got {w}x{h}, expected {meta.Width}x{meta.Height}");

        byte[] headerProbe = BuildHeaderProbe(meta.Type, w, h);
        var layout = AnalyzeLayout(headerProbe);
        uint dy = layout.Dy;
        uint dx = dy * 32;
        bool sliced = layout.Sliced;
        int bpp = layout.Bpp / 8;
        int pixelBytes = ComputeEncodedPixelBytes(meta.Type, w, h, dx, dy, bpp);
        byte[] result = new byte[0x100 + pixelBytes];

        WriteHeader(result, meta.Type, w, h);
        var dst = result.AsSpan(0x100);
        if (sliced)
            ReswizzleSliced32(rgba, dst, w, h, dx, dy, bpp);
        else
            ReswizzleNonSliced(rgba, dst, w, h, dx, dy, bpp);
        return result;
    }

    public static byte[] BuildFromPng(byte[] pngData, RawBgRebuildMetadata meta)
    {
        var (w, h, rgba) = Tim2Png.PngDecode(pngData);
        if (w != meta.Width || h != meta.Height)
            throw new InvalidDataException($"PNG size mismatch: got {w}x{h}, expected {meta.Width}x{meta.Height}");

        byte[] header = Convert.FromHexString(meta.HeaderHex);
        if (header.Length != meta.PixelOffset)
            throw new InvalidDataException("RawBg header size mismatch");

        byte[] result = new byte[meta.PixelOffset + meta.EncodedPixelBytes];
        Buffer.BlockCopy(header, 0, result, 0, header.Length);
        var dst = result.AsSpan(meta.PixelOffset, meta.EncodedPixelBytes);

        if (meta.Blocks.Count > 0)
        {
            byte[] atlas = ComposeAtlasFromImage(rgba, meta.Width, meta.Height, meta.Blocks, meta.EncodedPixelBytes);
            ReswizzleNonSliced(atlas, dst, 512, atlas.Length / (512 * 4), 512, 16, 4);
            return result;
        }

        var layout = AnalyzeLayout(header);
        uint dy = layout.Dy;
        uint dx = dy * 32;
        bool sliced = layout.Sliced;
        int bpp = layout.Bpp / 8;
        if (sliced && bpp == 1 && dy == 16)
            ReswizzleSliced8(rgba, dst, w, h, dx, dy);
        else if (sliced)
            ReswizzleSliced32(rgba, dst, w, h, dx, dy, bpp);
        else
            ReswizzleNonSliced(rgba, dst, w, h, dx, dy, bpp);
        return result;
    }

    static LayoutParams AnalyzeLayout(byte[] d)
    {
        int type = BitConverter.ToInt32(d, 0);
        uint palStart = BitConverter.ToUInt16(d, 0x0C);
        uint fstart = BitConverter.ToUInt16(d, 0x10);
        int bpp = (fstart - palStart == 1024) ? 8 : 32;
        int w = BitConverter.ToUInt16(d, 0x88);
        int h = BitConverter.ToUInt16(d, 0x8A);

        bool multi = type >= 6 && type <= 0x0C;
        int realSign = type == 5 ? 0x14 : type * 4;
        uint sign = BitConverter.ToUInt16(d, realSign + 2);
        long denominator = d.Length;
        if (multi && d.Length >= 0xA4)
        {
            uint f2start = BitConverter.ToUInt16(d, 0xA2);
            denominator = f2start * 1024L + fstart + 0x100;
        }

        double oversize = (double)w * h * 4 / denominator;
        uint sizesign = BitConverter.ToUInt16(d, 0x90);
        uint sizesignHigh = BitConverter.ToUInt16(d, 0x92);
        if (sizesign != 0 || sizesignHigh == 0)
            throw new InvalidDataException("Invalid RawBg size signature");

        uint pixelSize = (sizesignHigh & 0x00FF) * 0x10000;
        uint dy;
        bool sliced = true;
        if (oversize > 0.87)
        {
            dy = 16;
            sliced = false;
        }
        else if (sign > 0x50)
        {
            throw new InvalidDataException($"Unsupported RawBg sign: 0x{sign:X}");
        }
        else if ((double)pixelSize / denominator <= 1.045 && sign != 0x2E && sign != 0x33)
        {
            dy = 32;
        }
        else
        {
            dy = 16;
        }

        if (bpp == 8)
        {
            sliced = true;
            oversize = (double)w * h / (d.Length - fstart);
            dy = (oversize > 0.85 || w == 480 || h == 360) ? 16u : 32u;
        }

        return new LayoutParams(bpp, dy, sliced);
    }

    static IReadOnlyList<BgBlock> ParseBlocks(byte[] d, int type, int pixelOffset)
    {
        if (type < 6 || type > 12)
            return Array.Empty<BgBlock>();

        int headerWords = BitConverter.ToInt32(d, 0);
        var blocks = new List<BgBlock>();
        for (int i = 0; i < headerWords - 4; i++)
        {
            int blockOff = BitConverter.ToInt32(d, (i + 1) * 4);
            if (blockOff <= 0 || blockOff + 12 > pixelOffset || blockOff + 12 > d.Length)
                continue;

            int groupCount = BitConverter.ToUInt16(d, blockOff);
            int baseX = -2 * BitConverter.ToInt16(d, blockOff + 4);
            int cur = blockOff + 12;
            for (int g = 0; g < groupCount; g++)
            {
                if (cur + 8 > pixelOffset || cur + 8 > d.Length)
                    throw new InvalidDataException("RawBg group record is out of range");

                int lenDwords = BitConverter.ToUInt16(d, cur);
                if (lenDwords < 2 || cur + lenDwords * 4 > pixelOffset || cur + lenDwords * 4 > d.Length)
                    throw new InvalidDataException("RawBg group size is invalid");

                int tile = BitConverter.ToUInt16(d, cur + 2);
                int dstX = baseX + d[cur + 4] * 16;
                int dstY = d[cur + 5] * 16;
                int cols = d[cur + 6];
                int rows = d[cur + 7];
                if (cols > 0 && rows > 0)
                    blocks.Add(new BgBlock(dstX, dstY, tile, cols, rows));
                cur += lenDwords * 4;
            }
        }
        return blocks;
    }

    static int ReadLE32(byte[] d, int off)
    {
        if (off < 0 || off + 4 > d.Length)
            return 0;
        return BitConverter.ToInt32(d, off);
    }

    static byte[] BuildHeaderProbe(int type, int w, int h)
    {
        byte[] d = new byte[0x100];
        WriteLE32(d, 0x00, (uint)type);
        WriteLE32(d, 0x0C, type == 6 ? 0xA8u : 0x100u);
        WriteLE32(d, 0x10, 0x100);
        WriteLE32(d, 0x88, (uint)((h << 16) | w));
        if (type == 5)
            WriteLE32(d, 0x14, 0x100);
        else if (type == 6)
        {
            WriteLE32(d, 0x18, 0x258100);
            WriteLE32(d, 0x90, 0x1E280000);
            WriteLE32(d, 0xA0, 0x04B00002);
            d[0x1A] = 0x25;
            d[0xA2] = 0xB0;
            d[0xA3] = 0x04;
        }
        return d;
    }

    static int ComputeEncodedPixelBytes(int type, int w, int h, uint dx, uint dy, int bpp)
    {
        if (type == 5)
        {
            long focusH = ((long)w * h + dx - 1) / dx;
            long focusT = (focusH + dy - 1) / dy;
            return checked((int)(focusT * dy * dx * bpp));
        }

        long dw = ((w + (dy - 2) - 1) / (dy - 2)) * dy;
        long dh = ((h + (dy - 2) - 1) / (dy - 2)) * dy;
        long focusH2 = (dw * dh + dx - 1) / dx;
        long focusT2 = (focusH2 + dy - 1) / dy;
        return checked((int)(focusT2 * dy * dx * bpp));
    }

    static void WriteHeader(byte[] d, int type, int w, int h)
    {
        int fileSize = d.Length;
        WriteLE32(d, 0x00, (uint)type);
        WriteLE32(d, 0x04, 0x80);
        WriteLE32(d, 0x08, 0x94);
        WriteLE32(d, 0x10, 0x100);
        WriteLE32(d, 0x80, 1);
        WriteLE32(d, 0x88, (uint)((h << 16) | w));
        WriteLE32(d, 0x8C, 2);
        WriteLE32(d, 0x90, (uint)(((h / 16) << 24) | ((w / 16) << 16)));

        if (type == 5)
        {
            WriteLE32(d, 0x0C, 0x100);
            WriteLE32(d, 0x14, (uint)fileSize);
            WriteLE32(d, 0x18, 0);
        }
        else if (type == 6)
        {
            WriteLE32(d, 0x0C, 0xA8);
            WriteLE32(d, 0x14, 0x100);
            WriteLE32(d, 0x18, (uint)fileSize);
            WriteLE32(d, 0x94, 1);
            WriteLE32(d, 0x9C, (uint)((h << 16) | w));
            WriteLE32(d, 0xA0, (uint)((((w * h) / 256) << 16) | 2));
            WriteLE32(d, 0xA4, (uint)(((h / 16) << 24) | ((w / 16) << 16)));
        }
        else
        {
            throw new NotSupportedException($"Unsupported RawBg type for metadata-only rebuild: {type}");
        }
    }

    // Reverse non-sliced tiling
    static void ReswizzleNonSliced(byte[] src, Span<byte> dst, int w, int h, uint dx, uint dy, int bpp)
    {
        long focusH = ((long)w * h + dx - 1) / dx;
        long focusT = (focusH + dy - 1) / dy;
        int dstOff = 0;

        for (int t = 0; t < focusT; t++)
        {
            for (int y = 0; y < dy; y++)
            {
                for (int x = 0; x < dx; x++)
                {
                    long i2x = x + t * dx;
                    long i3t = i2x / w;
                    long i3x = i2x - i3t * w;
                    long i3y = i3t * dy + y;
                    if (i3x >= w || i3y >= h)
                    {
                        for (int k = 0; k < bpp; k++) dst[dstOff++] = 0;
                        continue;
                    }
                    int srcOff = (int)((i3x + i3y * w) * bpp);
                    if (bpp == 4)
                    {
                        dst[dstOff++] = src[srcOff];
                        dst[dstOff++] = src[srcOff + 1];
                        dst[dstOff++] = src[srcOff + 2];
                        dst[dstOff++] = ToPs2Alpha(src[srcOff + 3]);
                    }
                    else
                    {
                        for (int k = 0; k < bpp; k++)
                            dst[dstOff++] = src[srcOff + k];
                    }
                }
            }
        }
    }

    static void ReswizzleSliced32(byte[] src, Span<byte> dst, int w, int h, uint dx, uint dy, int bpp)
    {
        long dw = ((w + (dy - 2) - 1) / (dy - 2)) * dy;
        long dh = ((h + (dy - 2) - 1) / (dy - 2)) * dy;
        long focusH = (dw * dh + dx - 1) / dx;
        long focusT = (focusH + dy - 1) / dy;
        int dstOff = 0;

        for (int t = 0; t < focusT; t++)
        {
            for (int y = 0; y < dy; y++)
            {
                for (int x = 0; x < dx; x++)
                {
                    long i2x = x + t * dx;
                    long i3t = i2x / dw;
                    long i3x = i2x - i3t * dw;
                    long i3y = i3t * (dy - 2) + y;
                    long i4x = i3x - i3x / dy * dy + i3x / dy * (dy - 2);
                    if (i3x >= dw || i4x >= w || i3y >= h)
                    {
                        for (int k = 0; k < bpp; k++) dst[dstOff++] = 0;
                        continue;
                    }
                    int srcOff = (int)((i4x + i3y * w) * bpp);
                    if (bpp == 4)
                    {
                        dst[dstOff++] = src[srcOff];
                        dst[dstOff++] = src[srcOff + 1];
                        dst[dstOff++] = src[srcOff + 2];
                        dst[dstOff++] = ToPs2Alpha(src[srcOff + 3]);
                    }
                    else
                    {
                        for (int k = 0; k < bpp; k++)
                            dst[dstOff++] = src[srcOff + k];
                    }
                }
            }
        }
    }

    static void ReswizzleSliced8(byte[] src, Span<byte> dst, int w, int h, uint dx, uint dy)
    {
        long dytemp = dy * 2;
        long dw = ((w + (dytemp - 2) - 1) / (dytemp - 2)) * dytemp;
        long dh = ((h + (dytemp - 2) - 1) / (dytemp - 2)) * dytemp;
        long focusH = (dw * dh + dx - 1) / dx;
        long focusT = (focusH + dy - 1) / dy;
        if (focusT % 2 == 1) focusT++;
        int dstOff = 0;

        for (int t = 0; t < focusT; t++)
        {
            for (int y = 0; y < dy; y++)
            {
                for (int x = 0; x < dx; x++)
                {
                    long i2x = x + (t >> 1) * dx;
                    long i3t = i2x / dw;
                    long i3x = i2x - i3t * dw;
                    long i3y = i3t * (dytemp - 2) + y + (t % 2) * dy - 1;
                    long i4x = i3x - i3x / dytemp * dytemp + i3x / dytemp * (dytemp - 2) - 1;
                    if (i3x >= dw || i4x >= w || i3y >= h || i4x < 0 || i3y < 0)
                        dst[dstOff++] = 0;
                    else
                        dst[dstOff++] = src[i4x + i3y * w];
                }
            }
        }
    }

    static byte FixAlpha(byte a)
    {
        if (a >= 0x80) return 0xFF;
        int v = a << 1;
        if (v > 255) v = 255;
        return (byte)v;
    }

    static byte ToPs2Alpha(byte a)
    {
        if (a == 0) return 0;
        int v = (a + 1) >> 1;
        if (v > 128) v = 128;
        return (byte)v;
    }

    static void WriteLE32(byte[] d, int o, uint v)
    {
        d[o] = (byte)v;
        d[o + 1] = (byte)(v >> 8);
        d[o + 2] = (byte)(v >> 16);
        d[o + 3] = (byte)(v >> 24);
    }
}
