using System.Security.Cryptography;
using System.Text;

namespace ToHeartPSE;

internal static class LeafPak
{
    const int HeaderSize = 8;
    const int EntrySize = 0x18;
    static readonly Encoding ShiftJis = Encoding.GetEncoding(932);

    public static IEnumerable<PakEntry> ReadEntries(string path)
    {
        byte[] blob = File.ReadAllBytes(path);
        if (blob.Length < 11 || !blob.AsSpan(0, 8).SequenceEqual("LEAFPACK"u8))
            throw new InvalidDataException("not a LEAF PAK archive");

        int keyLength = blob[^1];
        ushort count = (ushort)(blob[^3] | (blob[^2] << 8));
        long indexSize = (long)count * EntrySize;
        long indexOffset = blob.Length - 3 - indexSize;
        if (keyLength <= 0 || indexOffset < HeaderSize + keyLength)
            throw new InvalidDataException("invalid archive layout");

        byte[] key = blob.AsSpan(HeaderSize, keyLength).ToArray();
        byte[] index = blob.AsSpan((int)indexOffset, (int)indexSize).ToArray();
        CryptInPlace(index, key, add: false);

        for (int i = 0; i < count; i++)
        {
            int p = i * EntrySize;
            string name = DecodeName(index.AsSpan(p, 12));
            uint offset = ReadUInt32LE(index, p + 0x0C);
            uint size = ReadUInt32LE(index, p + 0x10);
            uint endOffset = ReadUInt32LE(index, p + 0x14);
            if (offset + size != endOffset || endOffset > indexOffset)
                throw new InvalidDataException($"invalid entry: {name}");

            byte[] data = blob.AsSpan((int)offset, (int)size).ToArray();
            CryptInPlace(data, key, add: false);
            yield return new PakEntry(name, data);
        }
    }

    public static void Write(Dictionary<string, byte[]> entries, string path)
    {
        byte[] key = new byte[16];
        RandomNumberGenerator.Fill(key);

        using var output = new MemoryStream();
        output.Write("LEAFPACK"u8);
        output.Write(key);

        using var plainIndex = new MemoryStream();
        foreach ((string name, byte[] plain) in entries.OrderBy(static e => e.Key, StringComparer.OrdinalIgnoreCase))
        {
            plainIndex.Write(EncodeName(name, ShiftJis));
            byte[] encrypted = (byte[])plain.Clone();
            CryptInPlace(encrypted, key, add: true);
            uint offset = checked((uint)output.Position);
            output.Write(encrypted);
            uint size = checked((uint)encrypted.Length);
            WriteUInt32LE(plainIndex, offset);
            WriteUInt32LE(plainIndex, size);
            WriteUInt32LE(plainIndex, checked(offset + size));
        }

        byte[] index = plainIndex.ToArray();
        CryptInPlace(index, key, add: true);
        output.Write(index);
        output.WriteByte((byte)(entries.Count & 0xFF));
        output.WriteByte((byte)((entries.Count >> 8) & 0xFF));
        output.WriteByte((byte)key.Length);
        File.WriteAllBytes(path, output.ToArray());
    }

    public static byte[] EncodeName(string name, Encoding enc)
    {
        string baseName = Path.GetFileNameWithoutExtension(name);
        string ext = Path.GetExtension(name);
        ext = ext.StartsWith('.') ? ext[1..] : ext;

        byte[] baseBytes = enc.GetBytes(baseName);
        byte[] extBytes = enc.GetBytes(ext);
        if (baseBytes.Length > 8)
            throw new InvalidOperationException($"name too long for LEAF PAK 8.3: {name}");
        if (extBytes.Length > 3)
            throw new InvalidOperationException($"extension too long for LEAF PAK 8.3: {name}");

        byte[] raw = new byte[12];
        Array.Fill(raw, (byte)0x20);
        Buffer.BlockCopy(baseBytes, 0, raw, 0, baseBytes.Length);
        Buffer.BlockCopy(extBytes, 0, raw, 8, extBytes.Length);
        raw[11] = 0;
        return raw;
    }

    static string DecodeName(ReadOnlySpan<byte> raw)
    {
        string name = ShiftJis.GetString(Trim(raw[..8]));
        string ext = ShiftJis.GetString(Trim(raw.Slice(8, 3)));
        return string.IsNullOrEmpty(ext) ? name : $"{name}.{ext}";
    }

    static byte[] Trim(ReadOnlySpan<byte> src)
    {
        int end = src.Length;
        while (end > 0 && (src[end - 1] == 0 || src[end - 1] == 0x20))
            end--;
        return end <= 0 ? Array.Empty<byte>() : src[..end].ToArray();
    }

    static void CryptInPlace(byte[] data, byte[] key, bool add)
    {
        for (int i = 0; i < data.Length; i++)
        {
            int k = key[i % key.Length];
            data[i] = (byte)(add ? (data[i] + k) & 0xFF : (data[i] - k) & 0xFF);
        }
    }

    static uint ReadUInt32LE(byte[] data, int offset) =>
        (uint)(data[offset] | (data[offset + 1] << 8) | (data[offset + 2] << 16) | (data[offset + 3] << 24));

    static void WriteUInt32LE(Stream stream, uint value)
    {
        stream.WriteByte((byte)value);
        stream.WriteByte((byte)(value >> 8));
        stream.WriteByte((byte)(value >> 16));
        stream.WriteByte((byte)(value >> 24));
    }
}
