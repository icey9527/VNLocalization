namespace Kid.Script;

public static class ChrBipLayout
{
    const int DefaultHeaderWords = 5;
    const int DefaultEntryOffset = 0x80;
    const int DefaultEntryValue08 = 0x01E00280;
    const int MinAtlasOffset = 0x100;
    const int AtlasAlignment = 0x80;

    public readonly record struct GroupMetadata(
        int LenDwords,
        int Tile,
        int DstXCells,
        int DstYCells,
        int Cols,
        int Rows);

    public readonly record struct LayoutMetadata(
        int HeaderKind,
        int HeaderWords,
        int EntryOffset,
        int AtlasOffset,
        int HeaderValue08,
        int FileSize,
        int EntryValue08,
        int GroupCount,
        IReadOnlyList<GroupMetadata> Groups);

    public readonly record struct RebuildMetadata(
        int HeaderKind,
        int HeaderWords,
        int EntryOffset,
        int AtlasOffset,
        int HeaderValue08,
        int FileSize,
        int EntryValue08,
        IReadOnlyList<GroupMetadata> Groups);

    enum HeaderKind
    {
        Legacy = 0,
        Type5 = 1,
    }

    public static bool IsLayout(byte[] d)
    {
        if (d.Length < 0x100)
            return false;

        uint headerWords = LE32(d, 0);
        if (headerWords < 5 || headerWords > 64)
            return false;

        int tableBytes = (int)headerWords * 4;
        if (tableBytes > d.Length)
            return false;

        if (!TryReadHeader(d, out var kind, out int entry0Off, out int entryEnd, out int atlasOff, out int fileSize))
            return false;

        if (entry0Off < tableBytes || entry0Off >= d.Length)
            return false;
        if (entryEnd <= entry0Off || entryEnd > d.Length)
            return false;
        if (atlasOff <= entryEnd || atlasOff > d.Length)
            return false;
        if (fileSize != d.Length)
            return false;

        int atlasBytes = d.Length - atlasOff;
        if (atlasBytes <= 0 || (atlasBytes % (512 * 4)) != 0)
            return false;

        int groupCount = LE16(d, entry0Off);
        if (groupCount <= 0 || groupCount > 256)
            return false;

        return kind == HeaderKind.Legacy || kind == HeaderKind.Type5;
    }

    public static byte[] ConvertToPng(byte[] d)
    {
        LayoutInfo info = Parse(d);
        byte[] atlas = DecodeAtlas(d, info);
        byte[] rgba = ComposeCanvas(info, atlas);
        return Tim2Png.WritePngRaw(info.Width, info.Height, rgba);
    }

    public static byte[] BuildFromPng(byte[] pngData, RebuildMetadata metadata)
    {
        var (w, h, rgba) = Tim2Png.PngDecode(pngData);
        LayoutInfo info = Parse(metadata, w, h);
        byte[] atlas = new byte[ComputeAtlasBytes(info)];

        foreach (var g in info.Groups)
        {
            int srcTileX = g.StartSrcX;
            int srcTileY = g.StartSrcY;
            for (int row = 0; row < g.Rows; row++)
            {
                for (int col = 0; col < g.Cols; col++)
                {
                    CopyTileToAtlas(rgba, info.Width, g.DstX + col * TileSize, g.DstY + row * TileSize, atlas, srcTileX, srcTileY);
                    AdvanceSourceTile(ref srcTileX, ref srcTileY);
                }
            }
        }

        int entryEnd = metadata.EntryOffset + 12 + metadata.Groups.Count * 8;
        int atlasOff = Math.Max(MinAtlasOffset, AlignUp(entryEnd, AtlasAlignment));
        int fileSize = atlasOff + atlas.Length;
        int headerWords = metadata.HeaderWords > 0 ? metadata.HeaderWords : DefaultHeaderWords;

        byte[] result = new byte[fileSize];
        Write32(result, 0x00, headerWords);
        Write32(result, 0x04, metadata.EntryOffset);
        Write32(result, 0x08, metadata.HeaderValue08 != 0 ? metadata.HeaderValue08 : entryEnd);
        Write32(result, 0x0C, atlasOff);
        if (metadata.HeaderKind == (int)HeaderKind.Type5)
        {
            Write32(result, 0x10, 0);
            Write32(result, 0x14, fileSize);
        }
        else
        {
            Write32(result, 0x10, fileSize);
        }

        int cur = metadata.EntryOffset;
        Write16(result, cur + 0x00, metadata.Groups.Count);
        Write16(result, cur + 0x02, 0);
        Write32(result, cur + 0x04, 0);
        Write32(result, cur + 0x08, metadata.EntryValue08 != 0 ? metadata.EntryValue08 : DefaultEntryValue08);
        cur += 12;

        foreach (var g in metadata.Groups)
        {
            Write16(result, cur + 0x00, g.LenDwords > 0 ? g.LenDwords : 2);
            Write16(result, cur + 0x02, g.Tile);
            result[cur + 0x04] = (byte)g.DstXCells;
            result[cur + 0x05] = (byte)g.DstYCells;
            result[cur + 0x06] = (byte)g.Cols;
            result[cur + 0x07] = (byte)g.Rows;
            cur += 8;
        }

        Array.Copy(atlas, 0, result, atlasOff, atlas.Length);
        return result;
    }

    public static LayoutMetadata InspectMetadata(byte[] d)
    {
        if (!TryReadHeader(d, out var kind, out int entryOff, out _, out int atlasOff, out int fileSize))
            throw new InvalidDataException("Unsupported chr header");

        int headerWords = (int)LE32(d, 0);
        int groupCount = LE16(d, entryOff);
        int cur = entryOff + 12;
        var groups = new List<GroupMetadata>(groupCount);
        for (int i = 0; i < groupCount; i++)
        {
            int lenDwords = LE16(d, cur);
            groups.Add(new GroupMetadata(
                lenDwords,
                LE16(d, cur + 2),
                d[cur + 4],
                d[cur + 5],
                d[cur + 6],
                d[cur + 7]));
            cur += lenDwords * 4;
        }
        return new LayoutMetadata(
            (int)kind,
            headerWords,
            entryOff,
            atlasOff,
            (int)LE32(d, 8),
            fileSize,
            (int)LE32(d, entryOff + 8),
            groupCount,
            groups);
    }

    static byte[] ComposeCanvas(LayoutInfo info, byte[] atlas)
    {
        byte[] rgba = new byte[info.Width * info.Height * 4];
        foreach (var g in info.Groups)
        {
            int srcTileX = g.StartSrcX;
            int srcTileY = g.StartSrcY;
            for (int row = 0; row < g.Rows; row++)
            {
                for (int col = 0; col < g.Cols; col++)
                {
                    CopyTileFromAtlas(atlas, srcTileX, srcTileY, rgba, info.Width, g.DstX + col * TileSize, g.DstY + row * TileSize);
                    AdvanceSourceTile(ref srcTileX, ref srcTileY);
                }
            }
        }
        return rgba;
    }

    static byte[] DecodeAtlas(byte[] d, LayoutInfo info)
    {
        byte[] atlas = new byte[d.Length - info.AtlasOffset];
        Array.Copy(d, info.AtlasOffset, atlas, 0, atlas.Length);
        return atlas;
    }

    static LayoutInfo Parse(byte[] d)
    {
        if (!TryReadHeader(d, out _, out int entryOff, out int entryEnd, out int atlasOff, out _))
            throw new InvalidDataException("Unsupported chr header");

        int groupCount = LE16(d, entryOff);
        int cur = entryOff + 12;
        var groups = new List<Group>(groupCount);
        int maxX = 0, maxY = 0;

        for (int i = 0; i < groupCount; i++)
        {
            int lenDwords = LE16(d, cur);
            if (lenDwords < 2 || cur + lenDwords * 4 > entryEnd)
                throw new InvalidDataException($"Invalid group descriptor at 0x{cur:X}");

            int tile = LE16(d, cur + 2);
            int dstX = d[cur + 4] * 16;
            int dstY = d[cur + 5] * 16;
            int cols = d[cur + 6];
            int rows = d[cur + 7];
            int srcX = (tile & 0x1F) * 16;
            int srcY = (tile >> 5) * 16;
            int width = cols * 16;
            int height = rows * 16;
            groups.Add(new Group(srcX, srcY, dstX, dstY, cols, rows, width, height));
            maxX = Math.Max(maxX, dstX + width);
            maxY = Math.Max(maxY, dstY + height);
            cur += lenDwords * 4;
        }

        if (cur > entryEnd || entryEnd > atlasOff)
            throw new InvalidDataException("Invalid chr entry/header bounds");

        return new LayoutInfo(atlasOff, maxX, maxY, groups);
    }

    static LayoutInfo Parse(RebuildMetadata metadata, int width, int height)
    {
        int entryEnd = metadata.EntryOffset + 12 + metadata.Groups.Count * 8;
        int atlasOff = metadata.AtlasOffset > 0 ? metadata.AtlasOffset : Math.Max(MinAtlasOffset, AlignUp(entryEnd, AtlasAlignment));
        var groups = new List<Group>(metadata.Groups.Count);
        foreach (var gm in metadata.Groups)
        {
            int srcX = (gm.Tile & 0x1F) * 16;
            int srcY = (gm.Tile >> 5) * 16;
            int dstX = gm.DstXCells * 16;
            int dstY = gm.DstYCells * 16;
            int pixelWidth = gm.Cols * 16;
            int pixelHeight = gm.Rows * 16;
            groups.Add(new Group(srcX, srcY, dstX, dstY, gm.Cols, gm.Rows, pixelWidth, pixelHeight));
        }
        return new LayoutInfo(atlasOff, width, height, groups);
    }

    static bool TryReadHeader(byte[] d, out HeaderKind kind, out int entryOff, out int entryEnd, out int atlasOff, out int fileSize)
    {
        kind = HeaderKind.Legacy;
        entryOff = entryEnd = atlasOff = fileSize = 0;

        if (d.Length < 0x18)
            return false;

        int headerWords = (int)LE32(d, 0);
        if (headerWords < 5 || headerWords > 64)
            return false;

        int legacyEntryOff = (int)LE32(d, 4);
        int legacyEntryEnd = (int)LE32(d, 8);
        int legacyAtlasOff = (int)LE32(d, 12);
        int legacyFileSize = (int)LE32(d, 16);
        if (legacyEntryOff >= headerWords * 4
            && legacyEntryEnd > legacyEntryOff
            && legacyAtlasOff > legacyEntryEnd
            && legacyFileSize == d.Length)
        {
            kind = HeaderKind.Legacy;
            entryOff = legacyEntryOff;
            entryEnd = legacyEntryEnd;
            atlasOff = legacyAtlasOff;
            fileSize = legacyFileSize;
            return true;
        }

        int type5EntryOff = (int)LE32(d, 4);
        int type5EntryEnd = (int)LE32(d, 8);
        int type5AtlasOff = (int)LE32(d, 12);
        int type5FileSize = (int)LE32(d, 20);
        if (LE32(d, 0) == 5
            && type5EntryOff >= headerWords * 4
            && type5EntryEnd > type5EntryOff
            && type5AtlasOff > type5EntryEnd
            && type5FileSize == d.Length)
        {
            kind = HeaderKind.Type5;
            entryOff = type5EntryOff;
            entryEnd = type5EntryEnd;
            atlasOff = type5AtlasOff;
            fileSize = type5FileSize;
            return true;
        }

        return false;
    }

    static int ComputeAtlasBytes(LayoutInfo info)
    {
        int maxTileBottom = 0;
        foreach (var g in info.Groups)
        {
            int srcTileX = g.StartSrcX;
            int srcTileY = g.StartSrcY;
            for (int row = 0; row < g.Rows; row++)
            {
                for (int col = 0; col < g.Cols; col++)
                {
                    maxTileBottom = Math.Max(maxTileBottom, srcTileY + TileSize);
                    AdvanceSourceTile(ref srcTileX, ref srcTileY);
                }
            }
        }
        return AtlasWidth * maxTileBottom * 4;
    }

    static int AlignUp(int value, int alignment) => ((value + alignment - 1) / alignment) * alignment;

    static void CopyTileFromAtlas(byte[] atlas, int srcX, int srcY, byte[] rgba, int canvasWidth, int dstX, int dstY)
    {
        for (int y = 0; y < TileSize; y++)
        {
            int srcRow = (srcY + y) * AtlasWidth;
            int dstRow = (dstY + y) * canvasWidth;
            for (int x = 0; x < TileSize; x++)
            {
                int srcPx = (srcRow + srcX + x) * 4;
                int dstPx = (dstRow + dstX + x) * 4;
                rgba[dstPx] = atlas[srcPx];
                rgba[dstPx + 1] = atlas[srcPx + 1];
                rgba[dstPx + 2] = atlas[srcPx + 2];
                rgba[dstPx + 3] = FixAlpha(atlas[srcPx + 3]);
            }
        }
    }

    static void CopyTileToAtlas(byte[] rgba, int canvasWidth, int srcX, int srcY, byte[] atlas, int dstX, int dstY)
    {
        for (int y = 0; y < TileSize; y++)
        {
            int srcRow = (srcY + y) * canvasWidth;
            int dstRow = (dstY + y) * AtlasWidth;
            for (int x = 0; x < TileSize; x++)
            {
                int srcPx = (srcRow + srcX + x) * 4;
                int dstPx = (dstRow + dstX + x) * 4;
                atlas[dstPx] = rgba[srcPx];
                atlas[dstPx + 1] = rgba[srcPx + 1];
                atlas[dstPx + 2] = rgba[srcPx + 2];
                atlas[dstPx + 3] = ToPs2Alpha(rgba[srcPx + 3]);
            }
        }
    }

    static void AdvanceSourceTile(ref int srcX, ref int srcY)
    {
        srcX += TileSize;
        if (srcX >= AtlasWidth)
        {
            srcX = 0;
            srcY += TileSize;
        }
    }

    static uint LE32(byte[] d, int o) => (uint)(d[o] | (d[o + 1] << 8) | (d[o + 2] << 16) | (d[o + 3] << 24));
    static ushort LE16(byte[] d, int o) => (ushort)(d[o] | (d[o + 1] << 8));
    static void Write32(byte[] d, int o, int v)
    {
        d[o] = (byte)v;
        d[o + 1] = (byte)(v >> 8);
        d[o + 2] = (byte)(v >> 16);
        d[o + 3] = (byte)(v >> 24);
    }

    static void Write16(byte[] d, int o, int v)
    {
        d[o] = (byte)v;
        d[o + 1] = (byte)(v >> 8);
    }

    static byte FixAlpha(byte a)
    {
        int v = a * 2 - 1;
        if (v < 0) v = 0;
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

    const int AtlasWidth = 512;
    const int TileSize = 16;

    readonly record struct Group(int StartSrcX, int StartSrcY, int DstX, int DstY, int Cols, int Rows, int PixelWidth, int PixelHeight);
    readonly record struct LayoutInfo(int AtlasOffset, int Width, int Height, List<Group> Groups);
}
