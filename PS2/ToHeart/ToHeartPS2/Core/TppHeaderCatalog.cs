namespace ToHeartPS2;

internal static class TppHeaderCatalog
{
    static readonly string[] PaletteHeaders =
    [
        "",
        "0000000000000000000000004100005040800000000000080000000000000000",
        "0000000000000000000000000500005004800000000000080000000000000000"
    ];

    static readonly string[] ImageHeaders =
    [
        "0000000000000000000000000101005000810000000000080000000000000000",
        "0000000000000000000000000102005000820000000000080000000000000000",
        "0000000000000000000000000104005000840000000000080000000000000000",
        "0000000000000000000000000108005000880000000000080000000000000000",
        "0000000000000000000000000110005000900000000000080000000000000000",
        "0000000000000000000000000120005000A00000000000080000000000000000",
        "0000000000000000000000000140005000C00000000000080000000000000000"
    ];

    public static string EncodePalette(string hex) => Encode("p", PaletteHeaders, hex);
    public static string EncodeImage(string hex) => Encode("i", ImageHeaders, hex);
    public static string DecodePalette(string code) => Decode("p", PaletteHeaders, code);
    public static string DecodeImage(string code) => Decode("i", ImageHeaders, code);

    static string Encode(string prefix, IReadOnlyList<string> table, string value)
    {
        for (int i = 0; i < table.Count; i++)
        {
            if (string.Equals(table[i], value, StringComparison.OrdinalIgnoreCase))
                return prefix + i.ToString();
        }

        return value;
    }

    static string Decode(string prefix, IReadOnlyList<string> table, string value)
    {
        if (value.StartsWith(prefix, StringComparison.OrdinalIgnoreCase)
            && int.TryParse(value[1..], out int index)
            && (uint)index < table.Count)
        {
            return table[index];
        }

        return value;
    }
}
