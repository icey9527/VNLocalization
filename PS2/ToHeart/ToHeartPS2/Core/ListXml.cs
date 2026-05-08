using System.Buffers.Binary;
using System.Globalization;
using System.Xml.Linq;

namespace ToHeartPS2;

internal static class ListXml
{
    public static void Save(string path, IReadOnlyList<ListEntry> entries)
    {
        var root = new XElement("thps2");
        foreach (ListEntry entry in entries.OrderBy(static e => e.Index))
        {
            var file = new XElement("file",
                new XAttribute("index", entry.Index),
                new XAttribute("path", entry.Path.Replace('\\', '/')));
            foreach ((string key, string value) in entry.Attributes.OrderBy(static kv => kv.Key, StringComparer.OrdinalIgnoreCase))
                file.SetAttributeValue(key, value);
            root.Add(file);
        }

        new XDocument(new XDeclaration("1.0", "utf-8", null), root).Save(path);
    }

    public static IReadOnlyList<string> LoadOrderOrScan(string inputDir)
    {
        string xmlPath = Path.Combine(inputDir, "list.xml");
        if (File.Exists(xmlPath))
        {
            XDocument doc = XDocument.Load(xmlPath);
            XElement root = doc.Root ?? throw new InvalidOperationException("list.xml missing root");
            return root.Elements("file")
                .Select(static node => node.Attribute("path")?.Value ?? "")
                .Where(static path => !string.IsNullOrWhiteSpace(path))
                .ToList();
        }

        return Directory.EnumerateFiles(inputDir, "*", SearchOption.AllDirectories)
            .Select(path => Path.GetRelativePath(inputDir, path).Replace('\\', '/'))
            .Where(static rel => !string.Equals(Path.GetFileName(rel), "list.xml", StringComparison.OrdinalIgnoreCase))
            .Where(static rel => !string.Equals(Path.GetExtension(rel), ".png", StringComparison.OrdinalIgnoreCase))
            .OrderBy(static rel => rel, StringComparer.OrdinalIgnoreCase)
            .ToList();
    }

    public static IReadOnlyDictionary<string, TppMeta> LoadTppMeta(string inputDir)
    {
        string xmlPath = Path.Combine(inputDir, "list.xml");
        if (!File.Exists(xmlPath))
            return new Dictionary<string, TppMeta>(StringComparer.OrdinalIgnoreCase);

        XDocument doc = XDocument.Load(xmlPath);
        XElement root = doc.Root ?? throw new InvalidOperationException("list.xml missing root");
        var map = new Dictionary<string, TppMeta>(StringComparer.OrdinalIgnoreCase);
        foreach (XElement node in root.Elements("file"))
        {
            string path = node.Attribute("path")?.Value ?? "";
            if (!string.Equals(Path.GetExtension(path), ".png", StringComparison.OrdinalIgnoreCase))
                continue;

            string name = node.Attribute("tpp_name")?.Value ?? "";
            if (name.Length == 0)
                name = TppNameCodec.InferTppName(path);

            var meta = new TppMeta
            {
                Name = name,
                HeaderReserved = ParseUInt(node, "tpp_u0c"),
                HasPalette = ParseUInt(node, "has_palette") != 0,
                SpecialStack = ParseUInt(node, "special_stack") != 0,
                LayoutCols = ParseUInt(node, "layout_cols"),
                LayoutRows = ParseUInt(node, "layout_rows"),
                OriginX = ParseUInt(node, "origin_x"),
                OriginY = ParseUInt(node, "origin_y"),
                CanvasWidth = ParseUInt(node, "canvas_w"),
                CanvasHeight = ParseUInt(node, "canvas_h"),
                TrimX = ParseUInt(node, "trim_x"),
                TrimY = ParseUInt(node, "trim_y")
            };

            string partMeta = node.Attribute("part_meta")?.Value ?? "";
            foreach (string part in partMeta.Split(';', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
            {
                string[] bits = part.Contains(',')
                    ? part.Split(',')
                    : part.Split('x');
                if (bits.Length is not (5 or 8 or 9))
                    throw new InvalidOperationException("bad part_meta: " + part);

                uint x;
                uint y;
                ushort packed;
                string paletteCode;
                string imageCode;
                bool is4Bit;
                uint width;
                uint height;
                if (bits.Length == 5)
                {
                    x = ParseUInt(bits[0]);
                    y = ParseUInt(bits[1]);
                    packed = checked((ushort)ParseUInt("0x" + bits[2]));
                    paletteCode = bits[3];
                    imageCode = bits[4];
                    is4Bit = Is4BitFromPaletteCode(paletteCode);
                    (width, height) = UnpackSize(packed);
                }
                else
                {
                    width = ParseUInt(bits[0]);
                    height = ParseUInt(bits[1]);
                    x = ParseUInt(bits[2]);
                    y = ParseUInt(bits[3]);
                    packed = checked((ushort)ParseUInt("0x" + bits[4]));
                    is4Bit = ParseUInt(bits[5]) == 4;
                    paletteCode = bits[6];
                    imageCode = bits[^1];
                }

                meta.Parts.Add(new TppPartMeta
                {
                    Width = width,
                    Height = height,
                    X = x,
                    Y = y,
                    Packed = packed,
                    Is4Bit = is4Bit,
                    PaletteHeaderHex = TppHeaderCatalog.DecodePalette(paletteCode),
                    ImageHeaderHex = TppHeaderCatalog.DecodeImage(imageCode)
                });
            }

            if (meta.Parts.Count != 0 && !AttributeExists(node, "has_palette"))
                meta.HasPalette = meta.Parts.Any(static p => p.PaletteHeaderHex.Length != 0);

            string[] partNames = SplitAttr(node, "part_names");
            string partNameMode = node.Attribute("part_name_mode")?.Value ?? "";
            string partNameValue = node.Attribute("part_name_value")?.Value ?? "";
            string[] partFlagA = SplitAttr(node, "part_flag_a");
            string[] partFlagB = SplitAttr(node, "part_flag_b");
            string[] partReserved = SplitAttr(node, "part_u14");
            string[] partExtra = SplitAttr(node, "part_extra");
            string[] partData = SplitAttr(node, "part_data");
            if (partNames.Length == 0)
            {
                IReadOnlyList<string> inferred = TppNameCodec.Decode(path, name, meta.Parts.Count, partNameMode, partNameValue);
                partNames = inferred.Count == 0 ? [] : inferred.ToArray();
            }
            if (partFlagA.Length == 1 && meta.Parts.Count > 1)
                partFlagA = Enumerable.Repeat(partFlagA[0], meta.Parts.Count).ToArray();
            if (partFlagB.Length == 1 && meta.Parts.Count > 1)
                partFlagB = Enumerable.Repeat(partFlagB[0], meta.Parts.Count).ToArray();
            if (partReserved.Length == 1 && meta.Parts.Count > 1)
                partReserved = Enumerable.Repeat(partReserved[0], meta.Parts.Count).ToArray();
            for (int i = 0; i < meta.Parts.Count; i++)
            {
                TppPartMeta src = meta.Parts[i];
                string partName = i < partNames.Length ? partNames[i] : "";
                ushort reserved = i < partReserved.Length ? checked((ushort)ParseUInt(partReserved[i])) : (ushort)0;
                uint flagA = i < partFlagA.Length ? ParseUInt(partFlagA[i]) : 3;
                uint flagB = i < partFlagB.Length ? ParseUInt(partFlagB[i]) : 0;
                string paletteDataHex = "";
                string imageDataHex = "";
                if (i < partData.Length)
                {
                    string[] dataBits = partData[i].Split(',', 2);
                    paletteDataHex = dataBits.Length > 0 ? dataBits[0] : "";
                    imageDataHex = dataBits.Length > 1 ? dataBits[1] : "";
                }

                if ((partName.Length == 0 || flagA == 0 && flagB == 0) && i < partExtra.Length && partExtra[i].Length >= 48)
                {
                    byte[] raw = Convert.FromHexString(partExtra[i]);
                    partName = ReadAsciiZ(raw, 0, 12);
                    reserved = BinaryPrimitives.ReadUInt16LittleEndian(raw.AsSpan(0x0C, 2));
                    flagA = BinaryPrimitives.ReadUInt32LittleEndian(raw.AsSpan(0x10, 4));
                    flagB = BinaryPrimitives.ReadUInt32LittleEndian(raw.AsSpan(0x14, 4));
                }

                meta.Parts[i] = new TppPartMeta
                {
                    Width = src.Width,
                    Height = src.Height,
                    X = src.X,
                    Y = src.Y,
                    PartName = partName,
                    PartReserved = reserved,
                    PartFlagA = flagA,
                    PartFlagB = flagB,
                    Packed = src.Packed,
                    Is4Bit = src.Is4Bit,
                    PaletteHeaderHex = src.PaletteHeaderHex,
                    ImageHeaderHex = src.ImageHeaderHex,
                    PaletteDataHex = paletteDataHex,
                    ImageDataHex = imageDataHex
                };
            }

            map[path.Replace('\\', '/')] = meta;
        }

        return map;
    }

    static uint ParseUInt(XElement node, string key)
    {
        string? value = node.Attribute(key)?.Value;
        return string.IsNullOrWhiteSpace(value) ? 0 : ParseUInt(value);
    }

    static uint ParseUInt(string value)
    {
        if (value.StartsWith("0x", StringComparison.OrdinalIgnoreCase))
            return uint.Parse(value[2..], NumberStyles.HexNumber, CultureInfo.InvariantCulture);
        return uint.Parse(value, NumberStyles.Integer, CultureInfo.InvariantCulture);
    }

    static string[] SplitAttr(XElement node, string key)
    {
        string value = node.Attribute(key)?.Value ?? "";
        return value.Length == 0 ? [] : value.Split(';', StringSplitOptions.TrimEntries);
    }

    static bool AttributeExists(XElement node, string key) => node.Attribute(key) is not null;

    static (uint Width, uint Height) UnpackSize(ushort packed)
    {
        uint width = 1u << ((packed & 0x03C0) >> 6);
        uint height = 1u << ((packed & 0x3C00) >> 10);
        return (width, height);
    }

    static bool Is4BitFromPaletteCode(string paletteCode)
    {
        string hex = TppHeaderCatalog.DecodePalette(paletteCode);
        return string.Equals(hex, "0000000000000000000000000500005004800000000000080000000000000000", StringComparison.OrdinalIgnoreCase);
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
