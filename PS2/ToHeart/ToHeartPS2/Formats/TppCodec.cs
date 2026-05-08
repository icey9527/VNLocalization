using System.Buffers.Binary;
using System.Drawing;
using System.Drawing.Imaging;
using SixLabors.ImageSharp;
using SixLabors.ImageSharp.PixelFormats;
using SixLabors.ImageSharp.Processing;
using SixLabors.ImageSharp.Processing.Processors.Quantization;
using SDRectangle = System.Drawing.Rectangle;

namespace ToHeartPS2;

internal static partial class TppCodec
{
    internal sealed class EncodeResult
    {
        public required byte[] Data { get; init; }
        public int OriginalColorCount { get; init; }
        public int PaletteLimit { get; init; }
        public bool UsedQuantization => OriginalColorCount > PaletteLimit;
    }

    internal sealed class DecodeResult
    {
        public required byte[] PngBytes { get; init; }
        public required TppMeta Meta { get; init; }
        public required int Width { get; init; }
        public required int Height { get; init; }
    }

    sealed class RgbaImage
    {
        public uint Width;
        public uint Height;
        public byte[] Data = [];
    }

    sealed class TppLayout
    {
        public uint Cols = 1;
        public uint Rows = 1;
        public uint OutWidth;
        public uint OutHeight;
        public uint OriginX;
        public uint OriginY;
        public bool SpecialStack;
    }

    public static bool IsTppPath(string relPath) =>
        string.Equals(Path.GetExtension(relPath), ".tpp", StringComparison.OrdinalIgnoreCase);

    public static DecodeResult Decode(
        string relPath,
        byte[] src,
        IReadOnlyDictionary<string, ImageMetaEntry> charMeta,
        IReadOnlyDictionary<string, ImageMetaEntry> etcMeta,
        IReadOnlyDictionary<string, IReadOnlyList<DrawSliceSpec>>? sliceSpecMap = null)
    {
        byte[] plain = TryDecompress(src) ?? src;
        if (plain.Length < 0x10)
            throw new InvalidDataException("tpp too small: " + relPath);
        if (!LooksLikeTppPlain(plain))
            throw new InvalidDataException("not a recognized tpp payload: " + relPath);

        uint parts = ReadU32(plain, 0);
        if (parts == 0)
            throw new InvalidDataException("empty tpp: " + relPath);

        bool hasPalette = ReadU32(plain, 0x10) != 0;
        string imageName = ReadAsciiZ(plain, 4, 12).ToUpperInvariant();
        string dir = Path.GetFileName(Path.GetDirectoryName(relPath) ?? "").ToUpperInvariant();

        var partsInfo = new List<(uint Pal, uint Img, uint Width, uint Height, ushort Packed, bool Is4Bit)>(checked((int)parts));
        uint maxWidth = 0;
        uint maxHeight = 0;
        for (uint i = 0; i < parts; i++)
        {
            int baseOffset = checked((int)(0x10 + i * 0x20));
            ushort packed = ReadU16(plain, baseOffset + 0x16);
            uint width = 1u << ((packed & 0x03C0) >> 6);
            uint height = 1u << ((packed & 0x3C00) >> 10);
            uint pal = ReadU32(plain, baseOffset);
            bool is4Bit = false;
            if (hasPalette)
            {
                if (checked((int)pal) + 0x20 > plain.Length)
                    throw new InvalidDataException($"palette header out of range: {relPath} part {i}");
                is4Bit = (byte)(plain[checked((int)pal) + 0x10] << 4) == 0x40;
            }

            partsInfo.Add((pal, ReadU32(plain, baseOffset + 4), width, height, packed, is4Bit));
            maxWidth = Math.Max(maxWidth, width);
            maxHeight = Math.Max(maxHeight, height);
        }

        charMeta.TryGetValue(imageName, out ImageMetaEntry? charInfo);
        etcMeta.TryGetValue(imageName, out ImageMetaEntry? etcInfo);
        TppLayout layout = CalculateLayout(relPath, imageName, parts, maxWidth, maxHeight, hasPalette, dir == "CHAR" ? charInfo : null, dir == "ETC" ? etcInfo : null);

        var canvas = new RgbaImage
        {
            Width = layout.OutWidth,
            Height = layout.OutHeight,
            Data = new byte[checked((int)(layout.OutWidth * layout.OutHeight * 4))]
        };

        var meta = new TppMeta
        {
            Name = imageName,
            HeaderReserved = ReadU32(plain, 0x0C),
            HasPalette = hasPalette,
            SpecialStack = layout.SpecialStack,
            LayoutCols = layout.Cols,
            LayoutRows = layout.Rows,
            OriginX = layout.OriginX,
            OriginY = layout.OriginY,
            CanvasWidth = layout.OutWidth,
            CanvasHeight = layout.OutHeight
        };

        for (int i = 0; i < partsInfo.Count; i++)
        {
            var info = partsInfo[i];
            byte[] rgba = hasPalette
                ? DecodeIndexedPart(plain, info.Pal, info.Img, info.Width, info.Height)
                : DecodeRgbaPart(plain, info.Img, info.Width, info.Height);

            uint col = layout.SpecialStack ? (uint)(i / Math.Max(1, (int)layout.Rows)) : (uint)(i % Math.Max(1, (int)layout.Cols));
            uint row = layout.SpecialStack ? (uint)(i % Math.Max(1, (int)layout.Rows)) : (uint)(i / Math.Max(1, (int)layout.Cols));
            uint dx = layout.OriginX + col * maxWidth;
            uint dy = layout.OriginY + row * maxHeight;
            Blit(rgba, info.Width, info.Height, canvas, dx, dy);

            meta.Parts.Add(new TppPartMeta
            {
                Width = info.Width,
                Height = info.Height,
                X = dx,
                Y = dy,
                PartName = ReadAsciiZ(plain, checked((int)(0x10 + i * 0x20 + 8)), 12),
                PartReserved = ReadU16(plain, checked((int)(0x10 + i * 0x20 + 0x14))),
                PartFlagA = ReadU32(plain, checked((int)(0x10 + i * 0x20 + 0x18))),
                PartFlagB = ReadU32(plain, checked((int)(0x10 + i * 0x20 + 0x1C))),
                Packed = info.Packed,
                Is4Bit = info.Is4Bit,
                PaletteHeaderHex = info.Pal == 0 ? "" : BytesToHex(plain, checked((int)info.Pal), 0x20),
                ImageHeaderHex = BytesToHex(plain, checked((int)info.Img), 0x20),
                PaletteDataHex = info.Pal == 0 ? "" : BytesToHex(plain, checked((int)info.Pal + 0x20), info.Is4Bit ? 0x40 : 0x400),
                ImageDataHex = BytesToHex(plain, checked((int)info.Img + 0x20), GetImageDataSize(info.Width, info.Height, hasPalette, info.Is4Bit))
            });
        }

        if (sliceSpecMap is not null && sliceSpecMap.TryGetValue(imageName, out IReadOnlyList<DrawSliceSpec>? sliceSpecs))
        {
            ApplySliceSpecs(canvas, meta, sliceSpecs);
        }

        return new DecodeResult
        {
            PngBytes = EncodePng(canvas),
            Meta = meta,
            Width = checked((int)canvas.Width),
            Height = checked((int)canvas.Height)
        };
    }

    static bool LooksLikeTppPlain(byte[] plain)
    {
        if (plain.Length < 0x30)
            return false;

        uint parts = ReadU32(plain, 0);
        if (parts == 0 || parts > 0x400)
            return false;

        if (0x10 + (ulong)parts * 0x20 > (ulong)plain.Length)
            return false;

        for (int i = 0; i < 8; i++)
        {
            byte c = plain[4 + i];
            if (c == 0)
                break;
            if (c < 0x20 || c > 0x7E)
                return false;
        }

        for (uint i = 0; i < parts; i++)
        {
            int baseOffset = checked((int)(0x10 + i * 0x20));
            ushort packed = ReadU16(plain, baseOffset + 0x16);
            int widthShift = (packed & 0x03C0) >> 6;
            int heightShift = (packed & 0x3C00) >> 10;
            if (widthShift > 12 || heightShift > 12)
                return false;

            uint width = 1u << widthShift;
            uint height = 1u << heightShift;
            if (width == 0 || height == 0 || width > 4096 || height > 4096)
                return false;

            uint img = ReadU32(plain, baseOffset + 4);
            if (img >= plain.Length)
                return false;
        }

        return true;
    }

    public static EncodeResult EncodeFromPng(string pngPath, TppMeta meta)
    {
        RgbaImage src = ReadPngRgba(pngPath);
        uint canvasWidth = meta.CanvasWidth != 0 ? meta.CanvasWidth : src.Width;
        uint canvasHeight = meta.CanvasHeight != 0 ? meta.CanvasHeight : src.Height;
        var canvas = new RgbaImage
        {
            Width = canvasWidth,
            Height = canvasHeight,
            Data = new byte[checked((int)(canvasWidth * canvasHeight * 4))]
        };
        Blit(src.Data, src.Width, src.Height, canvas, meta.TrimX, meta.TrimY);

        var output = Enumerable.Repeat((byte)0, 0x10 + meta.Parts.Count * 0x20).ToList();
        WriteU32(output, 0, checked((uint)meta.Parts.Count));
        for (int i = 0; i < Math.Min(12, meta.Name.Length); i++)
            output[4 + i] = (byte)meta.Name[i];
        if (meta.Name.Length <= 8 && meta.HeaderReserved != 0)
            WriteU32(output, 0x0C, meta.HeaderReserved);

        Align(output, 0x10);
        int blockOffset = output.Count;
        uint maxWidth = meta.Parts.Count == 0 ? 0 : meta.Parts.Max(static p => p.Width);
        uint maxHeight = meta.Parts.Count == 0 ? 0 : meta.Parts.Max(static p => p.Height);

        int maxOriginalColorCount = 0;
        int paletteLimit = 0;
        for (int i = 0; i < meta.Parts.Count; i++)
        {
            TppPartMeta part = meta.Parts[i];
            byte[] rgba = Crop(canvas, part.X, part.Y, part.Width, part.Height);
            bool partialSource = part.X + part.Width > src.Width || part.Y + part.Height > src.Height;
            byte[]? mergedRgba = partialSource ? TryMergePartWithOriginal(rgba, src.Width, src.Height, part, meta.HasPalette) : null;
            int entryOffset = 0x10 + i * 0x20;
            WriteAsciiZ12(output, entryOffset + 8, part.PartName);
            if (meta.HasPalette)
            {
                IndexedEncodeResult indexed = MakeIndexedPart(mergedRgba ?? rgba, part, $"{pngPath} part {i}");
                maxOriginalColorCount = Math.Max(maxOriginalColorCount, indexed.OriginalColorCount);
                paletteLimit = indexed.PaletteLimit;
                WriteU32(output, entryOffset, checked((uint)blockOffset));
                output.AddRange(HexToBytes(part.PaletteHeaderHex));
                output.AddRange(indexed.Palette);
                Align(output, 0x10);
                blockOffset = output.Count;

                WriteU32(output, entryOffset + 4, checked((uint)blockOffset));
                output.AddRange(HexToBytes(part.ImageHeaderHex));
                output.AddRange(indexed.Indexes);
                Align(output, 0x10);
                blockOffset = output.Count;
            }
            else
            {
                WriteU32(output, entryOffset, 0);
                WriteU32(output, entryOffset + 4, checked((uint)blockOffset));
                output.AddRange(HexToBytes(part.ImageHeaderHex));
                output.AddRange(MakeRgbaPart(mergedRgba ?? rgba));
                Align(output, 0x10);
                blockOffset = output.Count;
            }

            WriteU16(output, entryOffset + 0x14, part.PartReserved);
            WriteU16(output, entryOffset + 0x16, part.Packed);
            WriteU32(output, entryOffset + 0x18, part.PartFlagA);
            WriteU32(output, entryOffset + 0x1C, part.PartFlagB);
        }

        return new EncodeResult
        {
            Data = Compress(output.ToArray()),
            OriginalColorCount = maxOriginalColorCount,
            PaletteLimit = paletteLimit
        };
    }

    public static bool IsCompressedPayload(byte[] src) => LooksLikeCompressedPayload(src);

    public static byte[] CompressRaw(byte[] src) => LooksLikeCompressedPayload(src) ? src : Compress(src);

    static byte[] StoreRaw(byte[] src)
    {
        byte[] output = new byte[12 + src.Length];
        BinaryPrimitives.WriteUInt32LittleEndian(output.AsSpan(0, 4), checked((uint)src.Length));
        BinaryPrimitives.WriteUInt32LittleEndian(output.AsSpan(4, 4), 0);
        BinaryPrimitives.WriteUInt32LittleEndian(output.AsSpan(8, 4), checked((uint)src.Length));
        src.CopyTo(output.AsSpan(12));
        return output;
    }

    static TppMeta CopyMeta(TppMeta src, uint trimX, uint trimY)
    {
        var meta = new TppMeta
        {
            Name = src.Name,
            HeaderReserved = src.HeaderReserved,
            HasPalette = src.HasPalette,
            SpecialStack = src.SpecialStack,
            LayoutCols = src.LayoutCols,
            LayoutRows = src.LayoutRows,
            OriginX = src.OriginX,
            OriginY = src.OriginY,
            CanvasWidth = src.CanvasWidth,
            CanvasHeight = src.CanvasHeight,
            TrimX = trimX,
            TrimY = trimY
        };
        foreach (TppPartMeta part in src.Parts)
            meta.Parts.Add(part);
        return meta;
    }

    static void ApplySliceSpecs(RgbaImage canvas, TppMeta meta, IReadOnlyList<DrawSliceSpec> sliceSpecs)
    {
        uint minX = uint.MaxValue;
        uint minY = uint.MaxValue;
        uint maxX = 0;
        uint maxY = 0;
        bool any = false;

        foreach (DrawSliceSpec spec in sliceSpecs)
        {
            if ((uint)spec.PartIndex >= meta.Parts.Count)
                continue;

            TppPartMeta part = meta.Parts[spec.PartIndex];
            uint srcX = (uint)Math.Max(0, spec.SourceX);
            uint srcY = (uint)Math.Max(0, spec.SourceY);
            if (srcX >= part.Width || srcY >= part.Height)
                continue;

            uint partWidth = Math.Min((uint)Math.Max(0, spec.Width), part.Width - srcX);
            uint partHeight = Math.Min((uint)Math.Max(0, spec.Height), part.Height - srcY);
            if (partWidth == 0 || partHeight == 0)
                continue;

            uint left = part.X + srcX;
            uint top = part.Y + srcY;
            uint right = left + partWidth;
            uint bottom = top + partHeight;
            minX = Math.Min(minX, left);
            minY = Math.Min(minY, top);
            maxX = Math.Max(maxX, right);
            maxY = Math.Max(maxY, bottom);
            any = true;
        }

        if (!any || minX >= canvas.Width || minY >= canvas.Height)
            return;

        uint width = Math.Min(maxX, canvas.Width) - minX;
        uint height = Math.Min(maxY, canvas.Height) - minY;
        if (width == 0 || height == 0)
            return;

        byte[] cropped = Crop(canvas, minX, minY, width, height);
        canvas.Data = cropped;
        canvas.Width = width;
        canvas.Height = height;
        meta.TrimX = minX;
        meta.TrimY = minY;
    }

    static TppLayout CalculateLayout(string relPath, string imageName, uint parts, uint maxWidth, uint maxHeight, bool hasPalette, ImageMetaEntry? charMeta, ImageMetaEntry? etcMeta)
    {
        string dir = Path.GetFileName(Path.GetDirectoryName(relPath) ?? "").ToUpperInvariant();
        var layout = new TppLayout();
        if (parts == 1)
        {
            layout.Cols = 1;
            layout.Rows = 1;
        }
        else if (dir == "CHAR")
        {
            layout.SpecialStack = true;
            if (charMeta is not null)
            {
                layout.Cols = charMeta.Cols;
                layout.Rows = charMeta.Rows;
            }
            else if (parts == 4)
            {
                layout.Cols = 2;
                layout.Rows = 2;
            }
            else if (parts <= 8)
            {
                layout.Cols = 2;
                layout.Rows = Math.Max(1u, parts / 2);
            }
            else if (parts == 9)
            {
                layout.Cols = 3;
                layout.Rows = 3;
            }
            else if (parts == 0xC)
            {
                layout.Cols = 4;
                layout.Rows = 3;
            }
            else if (parts >= 0x14)
            {
                layout.Cols = 5;
                layout.Rows = (uint)Math.Ceiling(parts / 5.0);
            }
            else
            {
                layout.Cols = (uint)Math.Ceiling(Math.Sqrt(parts));
                layout.Rows = (uint)Math.Ceiling(parts / (double)layout.Cols);
            }
        }
        else if (dir is "BG" or "VISUAL")
        {
            layout.Cols = 3;
            layout.Rows = 2;
        }
        else if (dir == "ETC")
        {
            if (etcMeta is not null)
            {
                layout.Cols = etcMeta.Cols;
                layout.Rows = etcMeta.Rows;
                layout.OriginX = etcMeta.X;
                layout.OriginY = etcMeta.Y;
            }
            else if (imageName.Contains("BTL", StringComparison.OrdinalIgnoreCase) || imageName.Contains("MUL", StringComparison.OrdinalIgnoreCase))
            {
                layout.Cols = 3;
                layout.Rows = 2;
            }
            else if (imageName is "CALAN00" or "CALAN01" or "CALAN02" or "CALAN03")
            {
                layout.Cols = 3;
                layout.Rows = 3;
            }
            else if (imageName is "CALAN04" or "CALAN05")
            {
                layout.Cols = 4;
                layout.Rows = 4;
            }
            else if (imageName == "CALAN06")
            {
                layout.Cols = 5;
                layout.Rows = 4;
            }
            else if (imageName == "CALAN07")
            {
                layout.Cols = 4;
                layout.Rows = 3;
            }
            else
            {
                layout.Cols = Math.Max(1u, parts / 2);
                layout.Rows = (uint)Math.Ceiling(parts / (double)layout.Cols);
            }
            layout.SpecialStack = hasPalette || !imageName.Contains("MUL", StringComparison.OrdinalIgnoreCase);
        }
        else
        {
            layout.Cols = Math.Max(1u, parts / 2);
            layout.Rows = (uint)Math.Ceiling(parts / (double)layout.Cols);
        }

        layout.OutWidth = layout.OriginX + layout.Cols * maxWidth;
        layout.OutHeight = layout.OriginY + layout.Rows * maxHeight;
        if (dir is "BG" or "VISUAL")
        {
            layout.OutWidth = 640;
            layout.OutHeight = 448;
        }
        else if (dir == "CHAR" && charMeta is not null)
        {
            uint visibleWidth = charMeta.X < 640 ? 640 - charMeta.X : 0;
            uint visibleHeight = charMeta.Y < 448 ? 448 - charMeta.Y : 0;
            if (visibleWidth != 0)
                layout.OutWidth = Math.Min(layout.OutWidth, visibleWidth);
            if (visibleHeight != 0)
                layout.OutHeight = Math.Min(layout.OutHeight, visibleHeight);
        }
        return layout;
    }

    static byte[]? TryDecompress(byte[] src)
    {
        if (!LooksLikeCompressedPayload(src))
            return null;

        uint outputSize = ReadU32(src, 0);
        var output = new List<byte>(checked((int)(outputSize != 0 ? outputSize : (uint)src.Length)));
        int sp = 12;
        while (sp < src.Length)
        {
            byte ctrl = src[sp++];
            if (ctrl == 0)
                break;

            if ((ctrl & 0x80) != 0)
            {
                if (sp >= src.Length)
                    return null;
                int dist = (((ctrl & 0x40) != 0) ? 0x100 : 0) + src[sp++];
                if (output.Count <= dist)
                    return null;
                int pos = output.Count - dist - 1;
                int len = (ctrl & 0x3F) + 3;
                for (int i = 0; i < len; i++)
                {
                    if ((uint)pos >= (uint)output.Count)
                        return null;
                    output.Add(output[pos++]);
                }
            }
            else
            {
                int len = ctrl;
                if (sp + len > src.Length)
                    return null;
                output.AddRange(src.AsSpan(sp, len).ToArray());
                sp += len;
            }
        }

        if (outputSize != 0 && output.Count != outputSize)
            return null;
        return output.ToArray();
    }

    static bool LooksLikeCompressedPayload(byte[] src)
    {
        return src.Length >= 12
            && ReadU32(src, 4) == 1
            && ReadU32(src, 8) <= src.Length - 12;
    }

    static byte[] Compress(byte[] src)
    {
        if (src.Length == 0)
        {
            byte[] empty = new byte[16];
            BinaryPrimitives.WriteUInt32LittleEndian(empty.AsSpan(4, 4), 1);
            BinaryPrimitives.WriteUInt32LittleEndian(empty.AsSpan(8, 4), 4);
            return empty;
        }

        var body = new List<byte>(src.Length);
        var head = new int[0x10000];
        var chain = new int[src.Length];
        Array.Fill(head, -1);
        Array.Fill(chain, -1);

        static int HashAt(byte[] data, int pos) => (data[pos] << 8) | data[pos + 1];

        void AddPosition(int pos)
        {
            if ((uint)(pos + 1) >= (uint)src.Length)
                return;
            int hash = HashAt(src, pos);
            chain[pos] = head[hash];
            head[hash] = pos;
        }

        bool TryFindMatch(int pos, out int bestLen, out int bestDist)
        {
            bestLen = 0;
            bestDist = 0;
            if ((uint)(pos + 1) >= (uint)src.Length)
                return false;

            int maxLen = Math.Min(66, src.Length - pos);
            int hash = HashAt(src, pos);
            for (int prev = head[hash]; prev >= 0; prev = chain[prev])
            {
                int dist = pos - prev;
                if (dist <= 0)
                    continue;
                if (dist > 0x200)
                    break;

                int len = 0;
                while (len < maxLen && src[prev + len] == src[pos + len])
                    len++;

                if (len > bestLen && len >= 3)
                {
                    bestLen = len;
                    bestDist = dist;
                    if (len == maxLen)
                        break;
                }
            }

            return bestLen >= 3;
        }

        int sp = 0;
        while (sp < src.Length)
        {
            TryFindMatch(sp, out int bestLen, out int bestDist);

            if (bestDist == 1 && bestLen >= 3 && sp + bestLen == src.Length)
                bestLen--;

            if (bestLen >= 3)
            {
                int d = bestDist - 1;
                byte ctrl = (byte)(0x80 | (bestLen - 3));
                if (d >= 0x100)
                    ctrl |= 0x40;
                body.Add(ctrl);
                body.Add((byte)(d & 0xFF));
                for (int i = 0; i < bestLen; i++)
                    AddPosition(sp + i);
                sp += bestLen;
            }
            else
            {
                int lit = 1;
                AddPosition(sp);
                while (sp + lit < src.Length && lit < 0x7F)
                {
                    if (TryFindMatch(sp + lit, out _, out _))
                        break;
                    AddPosition(sp + lit);
                    lit++;
                }

                body.Add((byte)lit);
                body.AddRange(src.AsSpan(sp, lit).ToArray());
                sp += lit;
            }
        }

        body.Add(0);
        while (((12 + body.Count) & 3) != 0)
            body.Add(0);
        byte[] output = new byte[12 + body.Count];
        BinaryPrimitives.WriteUInt32LittleEndian(output.AsSpan(0, 4), checked((uint)src.Length));
        BinaryPrimitives.WriteUInt32LittleEndian(output.AsSpan(4, 4), 1);
        BinaryPrimitives.WriteUInt32LittleEndian(output.AsSpan(8, 4), checked((uint)body.Count));
        body.CopyTo(output, 12);
        return output;
    }

    static byte[] DecodeRgbaPart(byte[] src, uint imageOffset, uint width, uint height)
    {
        int off = checked((int)imageOffset + 0x20);
        int size = checked((int)(width * height * 4));
        if (off + size > src.Length)
            throw new InvalidDataException("rgba part out of range");

        byte[] rgba = src.AsSpan(off, size).ToArray();
        for (int i = 3; i < rgba.Length; i += 4)
            rgba[i] = FixAlphaPs2(rgba[i]);
        return rgba;
    }

    static int GetImageDataSize(uint width, uint height, bool hasPalette, bool is4Bit)
    {
        uint pixels = checked(width * height);
        if (!hasPalette)
            return checked((int)(pixels * 4));
        return checked((int)(is4Bit ? (pixels + 1) / 2 : pixels));
    }

    static byte[] DecodeIndexedPart(byte[] src, uint paletteOffset, uint imageOffset, uint width, uint height)
    {
        if (checked((int)paletteOffset) + 0x20 > src.Length)
            throw new InvalidDataException("palette header out of range");

        bool is4Bit = (byte)(src[checked((int)paletteOffset) + 0x10] << 4) == 0x40;
        int paletteSize = is4Bit ? 0x40 : 0x400;
        int paletteDataOffset = checked((int)paletteOffset + 0x20);
        int pixelOffset = checked((int)imageOffset + 0x20);
        if (paletteDataOffset + paletteSize > src.Length)
            throw new InvalidDataException("palette out of range");

        byte[] palette = src.AsSpan(paletteDataOffset, paletteSize).ToArray();
        FixAlpha(palette);
        if (!is4Bit)
            palette = UnswizzlePalette(palette);

        byte[] rgba = new byte[checked((int)(width * height * 4))];
        if (is4Bit)
        {
            int p = pixelOffset;
            for (uint y = 0; y < height; y++)
            {
                for (uint x = 0; x < width; x += 2)
                {
                    byte value = src[p++];
                    byte lo = (byte)(value & 0x0F);
                    byte hi = (byte)((value >> 4) & 0x0F);
                    WritePaletteColor(palette, lo, rgba, checked((int)((y * width + x) * 4)));
                    if (x + 1 < width)
                        WritePaletteColor(palette, hi, rgba, checked((int)((y * width + x + 1) * 4)));
                }
            }
        }
        else
        {
            int pixelCount = checked((int)(width * height));
            if (pixelOffset + pixelCount > src.Length)
                throw new InvalidDataException("pixel data out of range");
            for (int i = 0; i < pixelCount; i++)
                WritePaletteColor(palette, src[pixelOffset + i], rgba, i * 4);
        }

        return rgba;
    }

    static void WritePaletteColor(byte[] palette, byte index, byte[] rgba, int rgbaOffset)
    {
        int srcOffset = index * 4;
        if (srcOffset + 4 > palette.Length)
        {
            Array.Clear(rgba, rgbaOffset, 4);
            return;
        }
        Buffer.BlockCopy(palette, srcOffset, rgba, rgbaOffset, 4);
    }

    static byte[] UnswizzlePalette(byte[] palette)
    {
        byte[] output = new byte[palette.Length];
        for (int i = 0; i < 256 && i * 4 + 4 <= palette.Length; i++)
        {
            int pos = (i & 0xE7) | ((i & 0x08) << 1) | ((i & 0x10) >> 1);
            Buffer.BlockCopy(palette, i * 4, output, pos * 4, 4);
        }
        return output;
    }

    static byte[] SwizzlePalette(byte[] palette)
    {
        byte[] output = new byte[palette.Length];
        for (int i = 0; i < 256 && i * 4 + 4 <= palette.Length; i++)
        {
            int pos = (i & 0xE7) | ((i & 0x08) << 1) | ((i & 0x10) >> 1);
            Buffer.BlockCopy(palette, pos * 4, output, i * 4, 4);
        }
        return output;
    }

    static byte FixAlphaPs2(byte value)
    {
        int v = value * 2 - 1;
        return (byte)Math.Clamp(v, 0, 255);
    }

    static byte ToPs2Alpha(byte value)
    {
        if (value == 0)
            return 0;
        return (byte)Math.Min((value + 1) >> 1, 128);
    }

    static void FixAlpha(byte[] palette)
    {
        for (int i = 3; i < palette.Length; i += 4)
            palette[i] = FixAlphaPs2(palette[i]);
    }

    static void TrimAlphaBounds(RgbaImage image, out uint trimX, out uint trimY)
    {
        uint minX = image.Width;
        uint minY = image.Height;
        uint maxX = 0;
        uint maxY = 0;
        bool any = false;
        for (uint y = 0; y < image.Height; y++)
        {
            for (uint x = 0; x < image.Width; x++)
            {
                if (image.Data[checked((int)((y * image.Width + x) * 4 + 3))] == 0)
                    continue;
                if (!any)
                {
                    minX = maxX = x;
                    minY = maxY = y;
                    any = true;
                }
                else
                {
                    minX = Math.Min(minX, x);
                    minY = Math.Min(minY, y);
                    maxX = Math.Max(maxX, x);
                    maxY = Math.Max(maxY, y);
                }
            }
        }

        if (!any)
        {
            image.Width = 1;
            image.Height = 1;
            image.Data = [0, 0, 0, 0];
            trimX = 0;
            trimY = 0;
            return;
        }

        if (minX == 0 && minY == 0 && maxX + 1 == image.Width && maxY + 1 == image.Height)
        {
            trimX = 0;
            trimY = 0;
            return;
        }

        uint newWidth = maxX - minX + 1;
        uint newHeight = maxY - minY + 1;
        byte[] output = new byte[checked((int)(newWidth * newHeight * 4))];
        for (uint y = 0; y < newHeight; y++)
        {
            int srcOffset = checked((int)(((minY + y) * image.Width + minX) * 4));
            int dstOffset = checked((int)(y * newWidth * 4));
            Buffer.BlockCopy(image.Data, srcOffset, output, dstOffset, checked((int)(newWidth * 4)));
        }
        image.Width = newWidth;
        image.Height = newHeight;
        image.Data = output;
        trimX = minX;
        trimY = minY;
    }

    static void Blit(byte[] src, uint srcWidth, uint srcHeight, RgbaImage dst, uint dx, uint dy)
    {
        for (uint y = 0; y < srcHeight && dy + y < dst.Height; y++)
        {
            uint copyWidth = Math.Min(srcWidth, dst.Width - dx);
            if (copyWidth == 0)
                continue;
            int srcOffset = checked((int)(y * srcWidth * 4));
            int dstOffset = checked((int)(((dy + y) * dst.Width + dx) * 4));
            Buffer.BlockCopy(src, srcOffset, dst.Data, dstOffset, checked((int)(copyWidth * 4)));
        }
    }

    static byte[] Crop(RgbaImage src, uint x, uint y, uint width, uint height)
    {
        byte[] output = new byte[checked((int)(width * height * 4))];
        for (uint yy = 0; yy < height; yy++)
        {
            if (y + yy >= src.Height)
                break;
            if (x >= src.Width)
                break;

            uint copyWidth = Math.Min(width, src.Width - x);
            if (copyWidth == 0)
                continue;

            int srcOffset = checked((int)(((y + yy) * src.Width + x) * 4));
            int dstOffset = checked((int)(yy * width * 4));
            Buffer.BlockCopy(src.Data, srcOffset, output, dstOffset, checked((int)(copyWidth * 4)));
        }
        return output;
    }

    sealed class IndexedEncodeResult
    {
        public required byte[] Palette { get; init; }
        public required byte[] Indexes { get; init; }
        public required int OriginalColorCount { get; init; }
        public required int PaletteLimit { get; init; }
    }

    static IndexedEncodeResult MakeIndexedPart(byte[] rgba, TppPartMeta part, string what)
        => MakeIndexedPartDynamic(rgba, part.Is4Bit, what);

    static IndexedEncodeResult MakeIndexedPartDynamic(byte[] rgba, bool is4Bit, string what)
    {
        int limit = is4Bit ? 16 : 256;
        int originalColorCount = CountUniqueRgba(rgba);
        if (originalColorCount <= limit)
            return BuildExactIndexedPart(rgba, is4Bit, limit);
        return BuildQuantizedIndexedPart(rgba, is4Bit, limit);
    }

    static IndexedEncodeResult BuildExactIndexedPart(byte[] rgba, bool is4Bit, int limit)
    {
        var lut = new Dictionary<uint, uint>();
        var palette = new List<byte>();
        var indexes = new List<byte>();

        uint PutColor(byte r, byte g, byte b, byte a)
        {
            uint key = PackPs2Color(r, g, b, a);
            if (lut.TryGetValue(key, out uint existing))
                return existing;
            uint id = checked((uint)lut.Count);
            lut[key] = id;
            palette.Add((byte)(key & 0xFF));
            palette.Add((byte)((key >> 8) & 0xFF));
            palette.Add((byte)((key >> 16) & 0xFF));
            palette.Add((byte)((key >> 24) & 0xFF));
            return id;
        }

        if (is4Bit)
        {
            for (int i = 0; i < rgba.Length; i += 8)
            {
                uint a = PutColor(rgba[i], rgba[i + 1], rgba[i + 2], rgba[i + 3]);
                uint b = i + 7 < rgba.Length ? PutColor(rgba[i + 4], rgba[i + 5], rgba[i + 6], rgba[i + 7]) : 0;
                indexes.Add((byte)((b << 4) | a));
            }
            while (palette.Count < 0x40)
                palette.Add(0);
            return new IndexedEncodeResult
            {
                Palette = palette.ToArray(),
                Indexes = indexes.ToArray(),
                OriginalColorCount = lut.Count,
                PaletteLimit = limit
            };
        }

        for (int i = 0; i < rgba.Length; i += 4)
            indexes.Add((byte)PutColor(rgba[i], rgba[i + 1], rgba[i + 2], rgba[i + 3]));
        while (palette.Count < 0x400)
            palette.Add(0);
        return new IndexedEncodeResult
        {
            Palette = SwizzlePalette(palette.ToArray()),
            Indexes = indexes.ToArray(),
            OriginalColorCount = lut.Count,
            PaletteLimit = limit
        };
    }

    static IndexedEncodeResult BuildQuantizedIndexedPart(byte[] rgba, bool is4Bit, int limit)
    {
        int originalColorCount = CountUniqueRgba(rgba);
        QuantizedImage quantized = QuantizeRgba(rgba, limit);
        List<uint> paletteKeys = quantized.PaletteKeys;

        var indexBytes = new List<byte>(quantized.Indices.Length / (is4Bit ? 2 : 1));
        if (is4Bit)
        {
            for (int i = 0; i < quantized.Indices.Length; i += 2)
            {
                byte a = quantized.Indices[i];
                byte b = i + 1 < quantized.Indices.Length
                    ? quantized.Indices[i + 1]
                    : (byte)0;
                indexBytes.Add((byte)((b << 4) | a));
            }
        }
        else
        {
            indexBytes.AddRange(quantized.Indices);
        }

        var paletteBytes = new List<byte>(is4Bit ? 0x40 : 0x400);
        foreach (uint key in paletteKeys)
        {
            paletteBytes.Add((byte)(key & 0xFF));
            paletteBytes.Add((byte)((key >> 8) & 0xFF));
            paletteBytes.Add((byte)((key >> 16) & 0xFF));
            paletteBytes.Add((byte)((key >> 24) & 0xFF));
        }

        int targetSize = is4Bit ? 0x40 : 0x400;
        while (paletteBytes.Count < targetSize)
            paletteBytes.Add(0);

        return new IndexedEncodeResult
        {
            Palette = is4Bit ? paletteBytes.ToArray() : SwizzlePalette(paletteBytes.ToArray()),
            Indexes = indexBytes.ToArray(),
            OriginalColorCount = originalColorCount,
            PaletteLimit = limit
        };
    }

    sealed class QuantizedImage
    {
        public required byte[] Indices { get; init; }
        public required List<uint> PaletteKeys { get; init; }
    }

    static QuantizedImage QuantizeRgba(byte[] rgba, int limit)
    {
        int pixelCount = rgba.Length / 4;
        using var image = SixLabors.ImageSharp.Image.LoadPixelData<Rgba32>(ToImageSharpPixels(rgba), pixelCount, 1);
        var quantizer = new WuQuantizer(new QuantizerOptions { MaxColors = limit, Dither = null });
        image.Mutate(x => x.Quantize(quantizer));

        var pixels = new Rgba32[pixelCount];
        image.CopyPixelDataTo(pixels);

        var paletteKeys = new List<uint>(limit);
        var paletteMap = new Dictionary<uint, byte>(limit);
        byte[] indices = new byte[pixelCount];
        for (int i = 0; i < pixels.Length; i++)
        {
            Rgba32 p = pixels[i];
            uint key = PackPs2Color(p.R, p.G, p.B, p.A);
            if (!paletteMap.TryGetValue(key, out byte index))
            {
                index = checked((byte)paletteKeys.Count);
                paletteKeys.Add(key);
                paletteMap[key] = index;
            }
            indices[i] = index;
        }

        return new QuantizedImage
        {
            Indices = indices,
            PaletteKeys = paletteKeys
        };
    }

    static Rgba32[] ToImageSharpPixels(byte[] rgba)
    {
        var pixels = new Rgba32[rgba.Length / 4];
        for (int i = 0, p = 0; i < rgba.Length; i += 4, p++)
            pixels[p] = new Rgba32(rgba[i], rgba[i + 1], rgba[i + 2], rgba[i + 3]);
        return pixels;
    }

    static byte[] MakeRgbaPart(byte[] rgba)
    {
        byte[] output = (byte[])rgba.Clone();
        for (int i = 3; i < output.Length; i += 4)
            output[i] = ToPs2Alpha(output[i]);
        return output;
    }

    static byte[]? TryMergePartWithOriginal(byte[] rgba, uint srcWidth, uint srcHeight, TppPartMeta part, bool hasPalette)
    {
        if (part.ImageDataHex.Length == 0 || part.ImageHeaderHex.Length == 0)
            return null;
        if (part.X >= srcWidth || part.Y >= srcHeight)
            return DecodeOriginalPartRgba(part, hasPalette);

        uint coveredWidth = Math.Min(part.Width, srcWidth - part.X);
        uint coveredHeight = Math.Min(part.Height, srcHeight - part.Y);
        if (coveredWidth >= part.Width && coveredHeight >= part.Height)
            return null;

        byte[] baseRgba = DecodeOriginalPartRgba(part, hasPalette);
        for (uint y = 0; y < coveredHeight; y++)
        {
            int srcOffset = checked((int)(y * part.Width * 4));
            int dstOffset = srcOffset;
            Buffer.BlockCopy(rgba, srcOffset, baseRgba, dstOffset, checked((int)(coveredWidth * 4)));
        }
        return baseRgba;
    }

    static byte[] DecodeOriginalPartRgba(TppPartMeta part, bool hasPalette)
    {
        byte[] imageHeader = HexToBytes(part.ImageHeaderHex);
        byte[] imageData = HexToBytes(part.ImageDataHex);
        if (hasPalette)
        {
            if (part.PaletteHeaderHex.Length == 0 || part.PaletteDataHex.Length == 0)
                throw new InvalidDataException("missing indexed part source data");
            byte[] paletteHeader = HexToBytes(part.PaletteHeaderHex);
            byte[] paletteData = HexToBytes(part.PaletteDataHex);
            byte[] payload = new byte[paletteHeader.Length + paletteData.Length + imageHeader.Length + imageData.Length];
            Buffer.BlockCopy(paletteHeader, 0, payload, 0, paletteHeader.Length);
            Buffer.BlockCopy(paletteData, 0, payload, paletteHeader.Length, paletteData.Length);
            int imageOffset = paletteHeader.Length + paletteData.Length;
            Buffer.BlockCopy(imageHeader, 0, payload, imageOffset, imageHeader.Length);
            Buffer.BlockCopy(imageData, 0, payload, imageOffset + imageHeader.Length, imageData.Length);
            return DecodeIndexedPart(payload, 0, checked((uint)imageOffset), part.Width, part.Height);
        }

        byte[] rgbaPayload = new byte[imageHeader.Length + imageData.Length];
        Buffer.BlockCopy(imageHeader, 0, rgbaPayload, 0, imageHeader.Length);
        Buffer.BlockCopy(imageData, 0, rgbaPayload, imageHeader.Length, imageData.Length);
        return DecodeRgbaPart(rgbaPayload, 0, part.Width, part.Height);
    }

    static int CountUniqueRgba(byte[] rgba)
    {
        var colors = new HashSet<uint>();
        for (int i = 0; i < rgba.Length; i += 4)
            colors.Add(PackPs2Color(rgba[i], rgba[i + 1], rgba[i + 2], rgba[i + 3]));
        return colors.Count;
    }

    static uint PackPs2Color(byte r, byte g, byte b, byte a)
    {
        byte aa = ToPs2Alpha(a);
        return (uint)(r | (g << 8) | (b << 16) | (aa << 24));
    }

    static byte[] EncodePng(RgbaImage image)
    {
        using var bitmap = new Bitmap(checked((int)image.Width), checked((int)image.Height), PixelFormat.Format32bppArgb);
        SDRectangle rect = new(0, 0, bitmap.Width, bitmap.Height);
        BitmapData data = bitmap.LockBits(rect, ImageLockMode.WriteOnly, PixelFormat.Format32bppArgb);
        try
        {
            byte[] bgra = new byte[bitmap.Width * bitmap.Height * 4];
            for (int y = 0; y < bitmap.Height; y++)
            {
                int srcOffset = y * bitmap.Width * 4;
                for (int x = 0; x < bitmap.Width; x++)
                {
                    int p = srcOffset + x * 4;
                    bgra[p + 0] = image.Data[p + 2];
                    bgra[p + 1] = image.Data[p + 1];
                    bgra[p + 2] = image.Data[p + 0];
                    bgra[p + 3] = image.Data[p + 3];
                }
            }

            for (int y = 0; y < bitmap.Height; y++)
            {
                int srcOffset = y * bitmap.Width * 4;
                System.Runtime.InteropServices.Marshal.Copy(bgra, srcOffset, data.Scan0 + y * data.Stride, bitmap.Width * 4);
            }
        }
        finally
        {
            bitmap.UnlockBits(data);
        }

        using var ms = new MemoryStream();
        bitmap.Save(ms, ImageFormat.Png);
        return ms.ToArray();
    }

    static RgbaImage ReadPngRgba(string path)
    {
        using var src = new Bitmap(path);
        using var bitmap = src.Clone(new SDRectangle(0, 0, src.Width, src.Height), PixelFormat.Format32bppArgb);
        SDRectangle rect = new(0, 0, bitmap.Width, bitmap.Height);
        BitmapData data = bitmap.LockBits(rect, ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
        try
        {
            byte[] rgba = new byte[bitmap.Width * bitmap.Height * 4];
            byte[] bgra = new byte[bitmap.Width * bitmap.Height * 4];
            for (int y = 0; y < bitmap.Height; y++)
            {
                int dstOffset = y * bitmap.Width * 4;
                System.Runtime.InteropServices.Marshal.Copy(data.Scan0 + y * data.Stride, bgra, dstOffset, bitmap.Width * 4);
            }

            for (int i = 0; i < bgra.Length; i += 4)
            {
                rgba[i + 0] = bgra[i + 2];
                rgba[i + 1] = bgra[i + 1];
                rgba[i + 2] = bgra[i + 0];
                rgba[i + 3] = bgra[i + 3];
            }

            return new RgbaImage
            {
                Width = checked((uint)bitmap.Width),
                Height = checked((uint)bitmap.Height),
                Data = rgba
            };
        }
        finally
        {
            bitmap.UnlockBits(data);
        }
    }

    static string BytesToHex(byte[] data, int offset, int count) => Convert.ToHexString(data.AsSpan(offset, count));
    static byte[] HexToBytes(string hex) => string.IsNullOrEmpty(hex) ? [] : Convert.FromHexString(hex);
    static uint ReadU32(byte[] data, int offset) => BinaryPrimitives.ReadUInt32LittleEndian(data.AsSpan(offset, 4));
    static ushort ReadU16(byte[] data, int offset) => BinaryPrimitives.ReadUInt16LittleEndian(data.AsSpan(offset, 2));

    static void WriteAsciiZ12(List<byte> data, int offset, string text)
    {
        for (int i = 0; i < 12; i++)
            data[offset + i] = 0;

        int count = Math.Min(12, text.Length);
        for (int i = 0; i < count; i++)
            data[offset + i] = (byte)text[i];
    }

    static void WriteU16(List<byte> data, int offset, ushort value)
    {
        while (data.Count < offset + 2)
            data.Add(0);
        Span<byte> buf = stackalloc byte[2];
        BinaryPrimitives.WriteUInt16LittleEndian(buf, value);
        for (int i = 0; i < 2; i++)
            data[offset + i] = buf[i];
    }

    static void WriteU32(List<byte> data, int offset, uint value)
    {
        while (data.Count < offset + 4)
            data.Add(0);
        Span<byte> buf = stackalloc byte[4];
        BinaryPrimitives.WriteUInt32LittleEndian(buf, value);
        for (int i = 0; i < 4; i++)
            data[offset + i] = buf[i];
    }

    static void Align(List<byte> data, int align)
    {
        while ((data.Count & (align - 1)) != 0)
            data.Add(0);
    }

    static string ReadAsciiZ(byte[] data, int offset)
    {
        return ReadAsciiZ(data, offset, data.Length - offset);
    }

    static string ReadAsciiZ(byte[] data, int offset, int maxLength)
    {
        int end = offset;
        int limit = Math.Min(data.Length, offset + maxLength);
        while (end < limit && data[end] != 0)
            end++;
        return System.Text.Encoding.ASCII.GetString(data, offset, end - offset);
    }
}
