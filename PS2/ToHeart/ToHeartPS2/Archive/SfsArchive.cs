using System.Buffers.Binary;
using System.Text;

namespace ToHeartPS2;

internal static class SfsArchive
{
    const int Step = 0x10;
    const int Sector = 0x800;

    public static IEnumerable<(uint Index, byte[] Data)> ReadSoundEntries(string path)
    {
        using var stream = File.OpenRead(path);
        byte[] entryBuf = new byte[0x0C];
        for (uint index = 0; ; index++)
        {
            int entry = checked((int)(index * Step));
            if (entry + 0x0C > stream.Length)
                yield break;

            stream.Position = entry;
            stream.ReadExactly(entryBuf);
            uint size = BinaryPrimitives.ReadUInt32LittleEndian(entryBuf[0x00..0x04]);
            if (size == 0)
                yield break;

            uint off = BinaryPrimitives.ReadUInt32LittleEndian(entryBuf[0x08..0x0C]) * Sector;
            if ((ulong)off + size > (ulong)stream.Length)
                yield break;

            byte[] data = new byte[checked((int)size)];
            stream.Position = off;
            stream.ReadExactly(data);
            yield return (index, data);
        }
    }

    public static IEnumerable<SfsIndexedEntry> ReadDataEntries(string sfsPath, byte[] elf, Config config, IReadOnlyList<ElfNamedEntry> names, bool numberedOnly)
    {
        int entryOff = ElfReader.GetElfOffset(elf, config.EntryAddr);
        using var stream = File.OpenRead(sfsPath);

        foreach (ElfNamedEntry item in names)
        {
            int ent = entryOff + checked((int)(item.Index * 0x20)) + 0x10;
            uint size = ReadU32(elf, ent + 0x00);
            uint sector = ReadU32(elf, ent + 0x08);
            ulong off = (ulong)sector * Sector;
            if (size == 0 || off + size > (ulong)stream.Length)
            {
                if (numberedOnly)
                    yield break;
                continue;
            }

            string rel = numberedOnly ? $"{item.Index:0000}.bin" : item.Path;
            byte[] data = new byte[checked((int)size)];
            stream.Position = checked((long)off);
            stream.ReadExactly(data);
            yield return new SfsIndexedEntry(item.Index, rel, data);
        }
    }

    public static SfsIndexedEntry? TryReadDataEntry(string sfsPath, byte[] elf, Config config, ElfNamedEntry item, bool numberedOnly)
    {
        int entryOff = ElfReader.GetElfOffset(elf, config.EntryAddr);
        int ent = entryOff + checked((int)(item.Index * 0x20)) + 0x10;
        uint size = ReadU32(elf, ent + 0x00);
        uint sector = ReadU32(elf, ent + 0x08);
        if (size == 0)
            return null;

        ulong off = (ulong)sector * Sector;
        using var stream = File.OpenRead(sfsPath);
        if (off + size > (ulong)stream.Length)
        {
            if (numberedOnly)
                return null;
            return null;
        }

        string rel = numberedOnly ? $"{item.Index:0000}.bin" : item.Path;
        byte[] data = new byte[checked((int)size)];
        stream.Position = checked((long)off);
        stream.ReadExactly(data);
        return new SfsIndexedEntry(item.Index, rel, data);
    }

    public static byte[] BuildSoundArchive(IReadOnlyList<NamedData> files)
    {
        int tableSize = AlignUp((files.Count + 1) * Step, Sector);
        using var ms = new MemoryStream();
        ms.Write(new byte[tableSize]);

        for (int i = 0; i < files.Count; i++)
        {
            byte[] data = files[i].Data;
            long dataOffset = ms.Position;
            ms.Write(data);
            Pad(ms, Sector);

            long back = ms.Position;
            ms.Position = i * Step;
            WriteU32(ms, checked((uint)data.Length));
            WriteU32(ms, checked((uint)(AlignUp(data.Length, Sector) / Sector)));
            WriteU32(ms, checked((uint)(dataOffset / Sector)));
            ms.Position = back;
        }

        return ms.ToArray();
    }

    public static byte[] BuildDataArchive(string sfsPath, byte[] elfBytes, Config config, IReadOnlyList<ElfNamedEntry> names, Func<ElfNamedEntry, byte[]?> getData, bool numberedOnly)
    {
        byte[] elf = (byte[])elfBytes.Clone();
        int entryOff = ElfReader.GetElfOffset(elf, config.EntryAddr);
        int tableSize = AlignUp((checked((int)names[^1].Index) + 2) * Step, Sector);

        using var stream = new FileStream(sfsPath, FileMode.Create, FileAccess.ReadWrite, FileShare.None);
        stream.Write(new byte[tableSize]);

        foreach (ElfNamedEntry item in names)
        {
            byte[]? data = getData(item);
            if (data is null)
            {
                if (numberedOnly)
                    break;
                continue;
            }

            long dataOffset = stream.Position;
            stream.Write(data);
            Pad(stream, Sector);

            int pkgEnt = checked((int)(item.Index * Step));
            int elfEnt = entryOff + checked((int)(item.Index * 0x20)) + 0x10;
            uint size = checked((uint)data.Length);
            uint sectors = checked((uint)(AlignUp(data.Length, Sector) / Sector));
            uint offsetSector = checked((uint)(dataOffset / Sector));

            long back = stream.Position;
            stream.Position = pkgEnt + 0x00;
            WriteU32(stream, size);
            WriteU32(stream, sectors);
            WriteU32(stream, offsetSector);
            stream.Position = back;

            ElfReader.WriteU32(elf, elfEnt + 0x00, size);
            ElfReader.WriteU32(elf, elfEnt + 0x04, sectors);
            ElfReader.WriteU32(elf, elfEnt + 0x08, offsetSector);
        }

        return elf;
    }

    public static bool LooksLikeData2(string sfsPath, byte[] elf, Config config, IReadOnlyList<ElfNamedEntry> names)
    {
        if (names.Count == 0)
            return false;

        int entryOff = ElfReader.GetElfOffset(elf, config.EntryAddr);
        using var stream = File.OpenRead(sfsPath);
        int ok = 0;
        foreach (ElfNamedEntry item in names)
        {
            int ent = entryOff + checked((int)(item.Index * 0x20)) + 0x10;
            uint size = ReadU32(elf, ent + 0x00);
            uint sector = ReadU32(elf, ent + 0x08);
            ulong off = (ulong)sector * Sector;
            if (size == 0 || off + size > (ulong)stream.Length)
                break;
            ok++;
        }

        return ok > 0 && ok < names.Count / 4;
    }

    public static bool IsNumberedBinDirectory(string inputDir)
    {
        IReadOnlyList<string> order = ListXml.LoadOrderOrScan(inputDir);
        if (order.Count == 0)
            return false;

        foreach (string item in order)
        {
            if (item.Contains('/') || item.Contains('\\'))
                return false;
            if (!string.Equals(Path.GetExtension(item), ".bin", StringComparison.OrdinalIgnoreCase))
                return false;
            string stem = Path.GetFileNameWithoutExtension(item);
            if (string.IsNullOrWhiteSpace(stem) || !stem.All(char.IsDigit))
                return false;
        }

        return true;
    }

    public static string GetSoundFileName(byte[] data, uint index)
    {
        if (data.Length >= 0x30 && data.AsSpan(0, 4).SequenceEqual("STER"u8))
            return (ReadAsciiName(data, 0x20, 0x10) is string s1 && s1.Length != 0 ? s1 : $"{index:0000}") + ".STER";
        if (data.Length >= 0x30 && data.AsSpan(0, 4).SequenceEqual("VAGp"u8))
            return (ReadAsciiName(data, 0x20, 0x10) is string s2 && s2.Length != 0 ? s2 : $"{index:0000}") + ".VAG";
        if (data.Length >= 4 && ReadU32(data, 0) == 0)
            return $"{index:0000}.ADPCM";
        return $"{index:0000}.BIN";
    }

    static string ReadAsciiName(byte[] data, int offset, int maxLen)
    {
        int len = 0;
        while (len < maxLen && offset + len < data.Length && data[offset + len] != 0)
            len++;
        return Encoding.ASCII.GetString(data, offset, len).Trim();
    }

    static uint ReadU32(byte[] data, int offset) => BinaryPrimitives.ReadUInt32LittleEndian(data.AsSpan(offset, 4));

    static void WriteU32(byte[] data, int offset, uint value) => BinaryPrimitives.WriteUInt32LittleEndian(data.AsSpan(offset, 4), value);

    static void WriteU32(Stream stream, uint value)
    {
        Span<byte> buf = stackalloc byte[4];
        BinaryPrimitives.WriteUInt32LittleEndian(buf, value);
        stream.Write(buf);
    }

    static int AlignUp(int value, int align) => ((value + align - 1) / align) * align;

    static void Pad(Stream stream, int align)
    {
        int pad = AlignUp(checked((int)stream.Position), align) - checked((int)stream.Position);
        if (pad > 0)
            stream.Write(new byte[pad]);
    }
}
