namespace ToHeartPSE;

internal static class LeafCodec
{
    const int RingSize = 0x1000;
    const int RingMask = RingSize - 1;
    const int RingInit = 4078;
    const int MinMatch = 3;
    const int MaxMatch = 18;

    public static byte[] Decompress(byte[] data, int outputSize)
    {
        byte[] output = new byte[outputSize];
        byte[] ring = new byte[RingSize];
        int ringPos = RingInit;
        int src = 0;
        int dst = 0;

        while (dst < outputSize)
        {
            ushort flags = (ushort)((((~data[src++]) & 0xFF) << 8) | 0x00FF);
            while (dst < outputSize)
            {
                bool literal = (flags & 0x8000) != 0;
                flags = (ushort)(flags << 1);
                if (literal)
                {
                    byte value = (byte)~data[src++];
                    output[dst++] = value;
                    ring[ringPos] = value;
                    ringPos = (ringPos + 1) & RingMask;
                }
                else
                {
                    ushort pair = (ushort)~(data[src++] | (data[src++] << 8));
                    int offset = pair >> 4;
                    int length = (pair & 0x0F) + MinMatch;
                    for (int i = 0; i < length && dst < outputSize; i++)
                    {
                        byte value = ring[(offset + i) & RingMask];
                        output[dst++] = value;
                        ring[ringPos] = value;
                        ringPos = (ringPos + 1) & RingMask;
                    }
                }

                if ((flags & 0x00FF) == 0)
                    break;
            }
        }

        return output;
    }

    public static byte[] Compress(byte[] src)
    {
        if (src.Length == 0)
            return Array.Empty<byte>();

        var dst = new List<byte>(src.Length + (src.Length >> 3) + 16);
        var head = new int[1 << 16];
        var chain = new int[RingSize];
        Array.Fill(head, -1);
        Array.Fill(chain, -1);

        int sp = 0;
        while (sp < src.Length)
        {
            int flagPos = dst.Count;
            dst.Add(0);
            byte controlInv = 0;
            for (int bit = 0; bit < 8 && sp < src.Length; bit++)
            {
                int bestLen = 0;
                int bestOff = 0;

                if (sp + 1 < src.Length)
                {
                    int h = (src[sp] << 8) | src[sp + 1];
                    for (int p = head[h], budget = 128; p >= 0 && sp - p <= RingSize && budget-- > 0; p = chain[p & RingMask])
                    {
                        int len = 0;
                        while (len < MaxMatch && sp + len < src.Length && src[p + len] == src[sp + len])
                            len++;
                        if (len > bestLen)
                        {
                            bestLen = len;
                            bestOff = (RingInit + p) & RingMask;
                            if (len == MaxMatch)
                                break;
                        }
                    }
                }

                if (bestLen >= MinMatch)
                {
                    ushort pair = (ushort)((bestOff << 4) | (bestLen - MinMatch));
                    dst.Add((byte)~(pair & 0xFF));
                    dst.Add((byte)~((pair >> 8) & 0xFF));
                    int limit = Math.Min(bestLen, src.Length - sp - 1);
                    for (int i = 0; i < limit; i++)
                        AddIndex(head, chain, src, sp + i);
                    sp += bestLen;
                }
                else
                {
                    controlInv |= (byte)(1 << (7 - bit));
                    dst.Add((byte)~src[sp]);
                    AddIndex(head, chain, src, sp);
                    sp++;
                }
            }
            dst[flagPos] = (byte)~controlInv;
        }

        return dst.ToArray();
    }

    static void AddIndex(int[] head, int[] chain, byte[] src, int pos)
    {
        if (pos + 1 >= src.Length)
            return;
        int h = (src[pos] << 8) | src[pos + 1];
        chain[pos & RingMask] = head[h];
        head[h] = pos;
    }
}
