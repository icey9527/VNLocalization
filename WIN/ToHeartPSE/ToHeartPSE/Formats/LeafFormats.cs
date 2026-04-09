using System.Drawing;
using System.Drawing.Imaging;

namespace ToHeartPSE;

internal static class LeafFormats
{
    public static bool TryInspectLff(byte[] data, out LffMeta meta)
    {
        meta = default;
        if (data.Length < 20 || !data.AsSpan(0, 8).SequenceEqual("LEAFFUL\0"u8))
            return false;
        meta = new LffMeta(ReadUInt16LE(data, 8), ReadUInt16LE(data, 10), ReadUInt16LE(data, 12), ReadUInt16LE(data, 14));
        return true;
    }

    public static Bitmap DecodeLff(byte[] data)
    {
        int width = ReadUInt16LE(data, 12);
        int height = ReadUInt16LE(data, 14);
        int dataOffset = ReadInt32LE(data, 16);
        byte[] pixels = LeafCodec.Decompress(data.AsSpan(dataOffset).ToArray(), checked(width * height * 3));
        return BitmapTools.FromBottomUpBgr24(width, height, pixels);
    }

    public static byte[] EncodeLff(ListEntry item, Bitmap source)
    {
        using var bitmap = BitmapTools.CloneToArgb(source);
        int width = bitmap.Width;
        int height = bitmap.Height;
        if (bitmap.Width != width || bitmap.Height != height)
            throw new InvalidOperationException($"{item.Name}: expected {width}x{height}");

        byte[] pixels = BitmapTools.ExtractBottomUpBgr24(bitmap);
        byte[] compressed = LeafCodec.Compress(pixels);
        using var ms = new MemoryStream();
        using var bw = new BinaryWriter(ms, System.Text.Encoding.ASCII, leaveOpen: true);
        bw.Write("LEAFFUL\0"u8);
        bw.Write((ushort)item.GetIntOrDefault("x", 0));
        bw.Write((ushort)item.GetIntOrDefault("y", 0));
        bw.Write((ushort)width);
        bw.Write((ushort)height);
        bw.Write(20);
        bw.Write(compressed);
        return ms.ToArray();
    }

    public static bool TryInspectLcf(byte[] data, out LcfMeta meta)
    {
        meta = null!;
        if (data.Length < 24 || !data.AsSpan(0, 8).SequenceEqual("LEAFCFL\0"u8))
            return false;
        int width = ReadUInt16LE(data, 12);
        int height = ReadUInt16LE(data, 14);
        int unpacked = ReadInt32LE(data, 0x14);
        byte[] pixels = LeafCodec.Decompress(data.AsSpan(24).ToArray(), unpacked);
        int consumed = MeasureLcfPixelStream(pixels, width, height);
        byte[] tail = consumed < pixels.Length ? pixels.AsSpan(consumed).ToArray() : Array.Empty<byte>();
        meta = new LcfMeta(unchecked((short)ReadUInt16LE(data, 8)), unchecked((short)ReadUInt16LE(data, 10)), width, height, tail);
        return true;
    }

    public static Bitmap DecodeLcf(byte[] data)
    {
        int width = ReadUInt16LE(data, 12);
        int height = ReadUInt16LE(data, 14);
        int unpacked = ReadInt32LE(data, 0x14);
        byte[] pixels = LeafCodec.Decompress(data.AsSpan(24).ToArray(), unpacked);
        var bmp = BitmapTools.CreateArgb(width, height, out BitmapData bmpData, out int stride);
        try
        {
            byte[] row = new byte[width * 4];
            int src = 0;
            for (int y = 0; y < height; y++)
            {
                Array.Clear(row);
                for (int x = 0; x < width; x++)
                {
                    byte control = pixels[src++];
                    if (control == 0)
                        continue;
                    int dst = x * 4;
                    row[dst + 0] = pixels[src++];
                    row[dst + 1] = pixels[src++];
                    row[dst + 2] = pixels[src++];
                    row[dst + 3] = control == 0xFF ? (byte)0xFF : control;
                }
                BitmapTools.CopyRow(bmpData, height - 1 - y, row, stride);
            }
        }
        finally
        {
            bmp.UnlockBits(bmpData);
        }
        return bmp;
    }

    public static byte[] EncodeLcf(ListEntry item, Bitmap source)
    {
        using var bitmap = BitmapTools.CloneToArgb(source);
        int width = bitmap.Width;
        int height = bitmap.Height;
        if (bitmap.Width != width || bitmap.Height != height)
            throw new InvalidOperationException($"{item.Name}: expected {width}x{height}");

        byte[] topDown = BitmapTools.ExtractTopDownBgra32(bitmap);
        using var pixelData = new MemoryStream();
        for (int y = height - 1; y >= 0; y--)
        {
            int row = y * width * 4;
            for (int x = 0; x < width; x++)
            {
                int p = row + x * 4;
                byte b = topDown[p + 0];
                byte g = topDown[p + 1];
                byte r = topDown[p + 2];
                byte a = topDown[p + 3];
                if (a == 0)
                {
                    pixelData.WriteByte(0);
                    continue;
                }
                pixelData.WriteByte(a == 255 ? (byte)0xFF : a);
                pixelData.WriteByte(b);
                pixelData.WriteByte(g);
                pixelData.WriteByte(r);
            }
        }

        byte[] raw = pixelData.ToArray();
        byte[] tail = ParseHex(item.Get("tail"));
        if (tail.Length != 0)
        {
            byte[] merged = new byte[raw.Length + tail.Length];
            Buffer.BlockCopy(raw, 0, merged, 0, raw.Length);
            Buffer.BlockCopy(tail, 0, merged, raw.Length, tail.Length);
            raw = merged;
        }

        byte[] compressed = LeafCodec.Compress(raw);
        using var ms = new MemoryStream();
        using var bw = new BinaryWriter(ms, System.Text.Encoding.ASCII, leaveOpen: true);
        bw.Write("LEAFCFL\0"u8);
        bw.Write((short)item.GetIntOrDefault("ox", 0));
        bw.Write((short)item.GetIntOrDefault("oy", 0));
        bw.Write((ushort)width);
        bw.Write((ushort)height);
        bw.Write(24);
        bw.Write(raw.Length);
        bw.Write(compressed);
        return ms.ToArray();
    }

    public static bool TryInspectLfb(byte[] data, out LfbMeta meta)
    {
        meta = default;
        if (data.Length < 4)
            return false;
        int outputSize = ReadInt32LE(data, 0);
        if (outputSize <= 0)
            return false;

        byte[] bmp = LeafCodec.Decompress(data.AsSpan(4).ToArray(), outputSize);
        if (bmp.Length < 54 || bmp[0] != (byte)'B' || bmp[1] != (byte)'M')
            return false;

        meta = new LfbMeta(ReadInt32LE(bmp, 18), Math.Abs(ReadInt32LE(bmp, 22)), IsCustomIndexedAlphaBmp(bmp) ? "custom-indexed-alpha" : "standard-bmp");
        return true;
    }

    public static Bitmap DecodeLfb(byte[] data)
    {
        int outputSize = ReadInt32LE(data, 0);
        byte[] bmp = LeafCodec.Decompress(data.AsSpan(4).ToArray(), outputSize);
        if (!IsCustomIndexedAlphaBmp(bmp))
            return new Bitmap(new MemoryStream(bmp, writable: false));

        int width = ReadInt32LE(bmp, 18);
        int heightRaw = ReadInt32LE(bmp, 22);
        int height = Math.Abs(heightRaw);
        bool bottomUp = heightRaw > 0;
        byte[] palette = bmp[54..(54 + 256 * 4)];
        int pixelOffset = ReadInt32LE(bmp, 10);
        int srcStride = width * 2;

        var outBmp = BitmapTools.CreateArgb(width, height, out BitmapData bmpData, out int stride);
        try
        {
            byte[] row = new byte[width * 4];
            for (int y = 0; y < height; y++)
            {
                int srcY = bottomUp ? (height - 1 - y) : y;
                int srcRow = pixelOffset + srcY * srcStride;
                for (int x = 0; x < width; x++)
                {
                    int src = srcRow + x * 2;
                    int dst = x * 4;
                    int pal = bmp[src + 1] * 4;
                    row[dst + 0] = palette[pal + 0];
                    row[dst + 1] = palette[pal + 1];
                    row[dst + 2] = palette[pal + 2];
                    row[dst + 3] = bmp[src];
                }
                BitmapTools.CopyRow(bmpData, y, row, stride);
            }
        }
        finally
        {
            outBmp.UnlockBits(bmpData);
        }
        return outBmp;
    }

    public static byte[] EncodeLfb(ListEntry item, Bitmap source)
    {
        using var bitmap = BitmapTools.CloneToArgb(source);
        int type = item.GetIntOrDefault("t", 0);
        byte[] bmp = type == 1
            ? BitmapTools.BuildCustomIndexedAlphaBmp(bitmap)
            : BitmapTools.BuildStandardBmp32(bitmap);
        byte[] compressed = LeafCodec.Compress(bmp);
        using var ms = new MemoryStream();
        using var bw = new BinaryWriter(ms, System.Text.Encoding.ASCII, leaveOpen: true);
        bw.Write(bmp.Length);
        bw.Write(compressed);
        return ms.ToArray();
    }

    static bool IsCustomIndexedAlphaBmp(byte[] bmp) =>
        bmp.Length >= 54
        && ReadInt32LE(bmp, 10) == 14 + 40 + 256 * 4
        && ReadInt32LE(bmp, 14) == 40
        && ReadUInt16LE(bmp, 26) == 1
        && ReadUInt16LE(bmp, 28) == 16
        && ReadInt32LE(bmp, 30) == 0;

    static int MeasureLcfPixelStream(byte[] pixels, int width, int height)
    {
        int src = 0;
        int count = checked(width * height);
        for (int i = 0; i < count; i++)
        {
            if (src >= pixels.Length)
                throw new InvalidDataException("LCF pixel stream ended early");
            byte control = pixels[src++];
            if (control == 0)
                continue;
            if (src + 3 > pixels.Length)
                throw new InvalidDataException("LCF pixel stream is truncated");
            src += 3;
        }
        return src;
    }

    static byte[] ParseHex(string? text)
    {
        if (string.IsNullOrWhiteSpace(text))
            return Array.Empty<byte>();

        string value = text.Trim();
        if ((value.Length & 1) != 0)
            throw new InvalidOperationException("LCF tail hex must have even length");

        byte[] result = new byte[value.Length / 2];
        for (int i = 0; i < result.Length; i++)
        {
            int hi = ParseHexNibble(value[i * 2]);
            int lo = ParseHexNibble(value[i * 2 + 1]);
            if (hi < 0 || lo < 0)
                throw new InvalidOperationException("LCF tail hex contains non-hex characters");
            result[i] = (byte)((hi << 4) | lo);
        }
        return result;
    }

    static int ParseHexNibble(char c) =>
        c is >= '0' and <= '9' ? c - '0' :
        c is >= 'A' and <= 'F' ? c - 'A' + 10 :
        c is >= 'a' and <= 'f' ? c - 'a' + 10 : -1;

    static ushort ReadUInt16LE(byte[] data, int offset) => (ushort)(data[offset] | (data[offset + 1] << 8));
    static int ReadInt32LE(byte[] data, int offset) => data[offset] | (data[offset + 1] << 8) | (data[offset + 2] << 16) | (data[offset + 3] << 24);
}
