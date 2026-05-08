using System.Buffers.Binary;

namespace ToHeartPS2;

internal static class ElfReader
{
    public static IReadOnlyList<ElfNamedEntry> ReadNamedEntries(byte[] elf, Config config)
    {
        int entryOffset = GetElfOffset(elf, config.EntryAddr);
        int nameOffset = GetElfOffset(elf, config.NameAddr);
        var list = new List<ElfNamedEntry>();

        for (uint index = 0; ; index++)
        {
            int entryPos = entryOffset + checked((int)(index * 0x20)) + 0x10;
            int namePos = nameOffset + checked((int)(index * 4));
            if (entryPos + 0x0C > elf.Length || namePos + 4 > elf.Length)
                break;

            uint size = ReadU32(elf, entryPos + 0x00);
            uint ptr = ReadU32(elf, namePos);
            if (size == 0 && ptr == 0)
                break;
            if (ptr < config.BaseAddr)
                break;

            string name = ReadAsciiZ(elf, checked((int)(ptr - config.BaseAddr)));
            if (string.IsNullOrWhiteSpace(name))
                break;

            name = name.Replace('\\', '/').TrimStart('/', '\\');
            list.Add(new ElfNamedEntry(index, name));
        }

        return list;
    }

    public static int GetElfOffset(byte[] elf, uint vaddr)
    {
        if (elf.Length < 0x34 || elf[0] != 0x7F || elf[1] != (byte)'E' || elf[2] != (byte)'L' || elf[3] != (byte)'F')
            throw new InvalidDataException("expected 32-bit little-endian elf");

        uint phoff = ReadU32(elf, 0x1C);
        ushort entsz = ReadU16(elf, 0x2A);
        ushort phnum = ReadU16(elf, 0x2C);
        for (int i = 0; i < phnum; i++)
        {
            int off = checked((int)phoff + i * entsz);
            uint type = ReadU32(elf, off + 0x00);
            uint fileOff = ReadU32(elf, off + 0x04);
            uint addr = ReadU32(elf, off + 0x08);
            uint fileSz = ReadU32(elf, off + 0x10);
            uint memSz = ReadU32(elf, off + 0x14);
            uint maxSz = Math.Max(fileSz, memSz);
            if (type == 1 && addr <= vaddr && vaddr < addr + maxSz)
                return checked((int)(fileOff + (vaddr - addr)));
        }

        throw new InvalidDataException($"elf address not mapped: 0x{vaddr:X8}");
    }

    public static uint ReadU32(byte[] data, int offset) => BinaryPrimitives.ReadUInt32LittleEndian(data.AsSpan(offset, 4));

    public static ushort ReadU16(byte[] data, int offset) => BinaryPrimitives.ReadUInt16LittleEndian(data.AsSpan(offset, 2));

    public static void WriteU32(byte[] data, int offset, uint value) => BinaryPrimitives.WriteUInt32LittleEndian(data.AsSpan(offset, 4), value);

    public static IReadOnlyDictionary<string, ImageMetaEntry> ReadImageMetaTable(byte[] elf, uint tableAddr, uint countAddr)
    {
        if (tableAddr == 0 || countAddr == 0)
            return new Dictionary<string, ImageMetaEntry>(StringComparer.OrdinalIgnoreCase);

        int tableOffset = GetElfOffset(elf, tableAddr);
        int countOffset = GetElfOffset(elf, countAddr);
        uint count = ReadU32(elf, countOffset);
        var map = new Dictionary<string, ImageMetaEntry>(StringComparer.OrdinalIgnoreCase);
        for (uint i = 0; i < count; i++)
        {
            int off = tableOffset + checked((int)(i * 0x24));
            if (off + 0x24 > elf.Length)
                break;

            string name = ReadAsciiZ(elf, off).ToUpperInvariant();
            uint x = ReadU32(elf, off + 0x14);
            uint y = ReadU32(elf, off + 0x18);
            uint cols = ReadU32(elf, off + 0x1C);
            uint rows = ReadU32(elf, off + 0x20);
            if (name.Length == 0 || cols == 0 || rows == 0)
                continue;

            map[name] = new ImageMetaEntry(name, x, y, cols, rows);
        }

        return map;
    }

    public static IReadOnlyList<DrawSliceSpec> ReadDrawSliceSpecs(byte[] elf, uint tableAddr, uint count)
    {
        if (tableAddr == 0 || count == 0)
            return [];

        int tableOffset = GetElfOffset(elf, tableAddr);
        var list = new List<DrawSliceSpec>(checked((int)count));
        for (uint i = 0; i < count; i++)
        {
            int off = tableOffset + checked((int)(i * 0x18));
            if (off + 0x18 > elf.Length)
                break;

            uint namePtr = ReadU32(elf, off + 0x00);
            if (namePtr is 0 or 0xFFFFFFFF || namePtr < 0x1000)
                break;

            int nameOffset;
            try
            {
                nameOffset = GetElfOffset(elf, namePtr);
            }
            catch (InvalidDataException)
            {
                // These scene tables are often packed back-to-back and may end with
                // sentinel or unrelated data. Stop the current table once the name
                // pointer no longer maps into the ELF image.
                break;
            }

            string textureName = ReadAsciiZ(elf, nameOffset);
            if (string.IsNullOrWhiteSpace(textureName))
                break;

            list.Add(new DrawSliceSpec(
                textureName,
                checked((int)ReadU32(elf, off + 0x04)),
                checked((int)ReadU32(elf, off + 0x08)),
                checked((int)ReadU32(elf, off + 0x0C)),
                checked((int)ReadU32(elf, off + 0x10)),
                checked((int)ReadU32(elf, off + 0x14))));
        }

        return list;
    }

    public static IReadOnlyList<string> ReadNamePointerArray(byte[] elf, uint tableAddr, int maxCount = 256)
    {
        if (tableAddr == 0 || maxCount <= 0)
            return [];

        int tableOffset = GetElfOffset(elf, tableAddr);
        var list = new List<string>(maxCount);
        for (int i = 0; i < maxCount; i++)
        {
            int off = tableOffset + i * 4;
            if (off + 4 > elf.Length)
                break;

            uint ptr = ReadU32(elf, off);
            if (ptr is 0 or 0xFFFFFFFF)
                break;

            int nameOffset;
            try
            {
                nameOffset = GetElfOffset(elf, ptr);
            }
            catch (InvalidDataException)
            {
                break;
            }

            string value = ReadAsciiZ(elf, nameOffset).ToUpperInvariant();
            if (string.IsNullOrWhiteSpace(value))
                break;

            if (value.IndexOfAny(['\\', '/', '.']) >= 0)
                break;

            list.Add(value);
        }

        return list;
    }

    static string ReadAsciiZ(byte[] data, int offset)
    {
        int end = offset;
        while (end < data.Length && data[end] != 0)
            end++;
        return System.Text.Encoding.ASCII.GetString(data, offset, end - offset);
    }
}
