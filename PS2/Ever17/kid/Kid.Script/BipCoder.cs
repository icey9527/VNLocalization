namespace Kid.Script;

/// <summary>
/// LZSS compression for BIP files.
/// Standard LZSS: 0x1000 window, 0xFEE start offset, min match 3.
/// </summary>
public static class BipCoder
{
    private const int WINDOW = 0x1000;
    private const int START = 0xFEE;
    private const int MIN = 3;
    private const int MAX = 18; // MIN + 0xF
    private const int HASH_BITS = 14;
    private const int HASH_SIZE = 1 << HASH_BITS;

    /// <summary>Decompress LZSS data.</summary>
    public static byte[] Decode(byte[] src, int outSize)
    {
        var window = new byte[WINDOW];
        var dst = new byte[outSize];
        int srcPos = 0, dstPos = 0, winPos = START;
        int flags = 0, mask = 0;

        while (dstPos < outSize && srcPos < src.Length)
        {
            if (mask == 0)
            {
                flags = src[srcPos++];
                mask = 1;
            }

            if ((flags & mask) != 0)
            {
                byte b = src[srcPos++];
                dst[dstPos++] = b;
                window[winPos] = b;
                winPos = (winPos + 1) & 0xFFF;
            }
            else
            {
                if (srcPos + 1 >= src.Length) break;
                int b0 = src[srcPos], b1 = src[srcPos + 1];
                srcPos += 2;
                int offset = b0 | ((b1 & 0xF0) << 4);
                int count = (b1 & 0x0F) + MIN;
                for (int i = 0; i < count && dstPos < outSize; i++)
                {
                    byte b = window[(offset + i) & 0xFFF];
                    dst[dstPos++] = b;
                    window[winPos] = b;
                    winPos = (winPos + 1) & 0xFFF;
                }
            }
            mask = (mask << 1) & 0xFF;
        }
        return dst;
    }

    /// <summary>Decompress a BIP file (skip 4-byte size header).</summary>
    public static byte[] DecodeBip(string path)
    {
        var raw = File.ReadAllBytes(path);
        uint outSize = BitConverter.ToUInt32(raw, 0);
        return Decode(raw.AsSpan(4).ToArray(), (int)outSize);
    }

    /// <summary>Compress data to LZSS format using hash table.</summary>
    public static byte[] Encode(byte[] src)
    {
        var dst = new List<byte>();
        int srcPos = 0;
        // Pre-allocate first flags byte
        dst.Add(0);
        int flagPos = 0;
        byte flags = 0;
        int mask = 1;

        // Hash table: maps 3-byte prefix → position in source
        var prev = new int[HASH_SIZE];
        Array.Fill(prev, -1);

        while (srcPos < src.Length)
        {
            if (mask == 0x100)
            {
                dst[flagPos] = flags;
                flags = 0;
                mask = 1;
                flagPos = dst.Count;
                dst.Add(0);
            }

            int bestLen = 0, bestOff = 0;

            if (srcPos + MIN <= src.Length)
            {
                int hash = Hash(src, srcPos);
                int match = prev[hash];
                prev[hash] = srcPos;

                if (match >= 0 && srcPos - match <= WINDOW)
                {
                    int maxLen = Math.Min(MAX, src.Length - srcPos);
                    int len = 0;
                    while (len < maxLen && src[match + len] == src[srcPos + len])
                        len++;

                    if (len >= MIN)
                    {
                        bestLen = len;
                        // Absolute window position (decompressor uses this directly)
                        bestOff = (START + match) & 0xFFF;
                    }
                }
            }

            if (bestLen >= MIN)
            {
                flags &= (byte)~mask;
                dst.Add((byte)(bestOff & 0xFF));
                dst.Add((byte)(((bestOff >> 4) & 0xF0) | (bestLen - MIN)));
                for (int i = 0; i < bestLen; i++)
                    prev[Hash(src, srcPos + i)] = srcPos + i;
                srcPos += bestLen;
            }
            else
            {
                flags |= (byte)mask;
                if (srcPos + MIN <= src.Length)
                    prev[Hash(src, srcPos)] = srcPos;
                dst.Add(src[srcPos++]);
            }

            mask <<= 1;
        }

        dst[flagPos] = flags;
        return dst.ToArray();
    }

    /// <summary>Compress and wrap with 4-byte size header for BIP file.</summary>
    public static byte[] EncodeBip(byte[] decompressed)
    {
        var header = BitConverter.GetBytes((uint)decompressed.Length);
        var body = Encode(decompressed);
        var result = new byte[header.Length + body.Length];
        Buffer.BlockCopy(header, 0, result, 0, header.Length);
        Buffer.BlockCopy(body, 0, result, header.Length, body.Length);
        return result;
    }

    private static int Hash(byte[] data, int pos)
    {
        if (pos + 2 >= data.Length) return 0;
        uint v = (uint)(data[pos] | (data[pos + 1] << 8) | (data[pos + 2] << 16));
        return (int)((v * 2654435761u) >> (32 - HASH_BITS));
    }
}
