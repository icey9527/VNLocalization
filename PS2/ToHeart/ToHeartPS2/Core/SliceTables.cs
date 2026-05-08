using System.Text;

namespace ToHeartPS2;

internal sealed record DrawSliceSpec(string TextureName, int PartIndex, int SourceX, int SourceY, int Width, int Height);

internal sealed record KnownSliceTable(string Name, uint Address, IReadOnlyList<DrawSliceSpec> Specs);

internal static class SliceTables
{
    public static IReadOnlyList<KnownSliceTable> ReadKnownTables(byte[] elf, Config config)
    {
        return
        [
            ReadTable(elf, config.SaveMenuSpecAddr, config.SaveMenuSpecCount, "save_menu_specs"),
            ReadTable(elf, config.AlbumSpecAddr, config.AlbumSpecCount, "album_specs"),
            ReadTable(elf, config.MenuBg2SpecAddr, config.MenuBg2SpecCount, "menu_bg2_specs"),
            ReadTable(elf, config.OptionMenuSpecAAddr, config.OptionMenuSpecACount, "option_menu_specs_a"),
            ReadTable(elf, config.OptionMenuSpecBAddr, config.OptionMenuSpecBCount, "option_menu_specs_b"),
            ReadTable(elf, config.OptionMenuSpecCAddr, config.OptionMenuSpecCCount, "option_menu_specs_c"),
            ReadTable(elf, config.OptionMenuSpecDAddr, config.OptionMenuSpecDCount, "option_menu_specs_d"),
            ReadTable(elf, config.MenuSbgSpecAddr, config.MenuSbgSpecCount, "menu_sbg_specs"),
            ReadTable(elf, config.MenuFrameSpecAddr, config.MenuFrameSpecCount, "menu_frame_specs")
        ];
    }

    public static string FormatForText(IReadOnlyList<KnownSliceTable> tables)
    {
        var sb = new StringBuilder();
        sb.AppendLine("# Known TPP draw descriptor tables");
        sb.AppendLine("# format: texture, part_index, src_x, src_y, width, height");
        sb.AppendLine();

        foreach (KnownSliceTable table in tables)
        {
            sb.AppendLine($"[{table.Name}] 0x{table.Address:X8} ({table.Specs.Count} entries)");
            for (int i = 0; i < table.Specs.Count; i++)
            {
                DrawSliceSpec spec = table.Specs[i];
                sb.AppendLine(
                    $"{i:D3}: {spec.TextureName}, part={spec.PartIndex}, src=({spec.SourceX},{spec.SourceY}), size={spec.Width}x{spec.Height}");
            }

            sb.AppendLine();
        }

        return sb.ToString();
    }

    public static IReadOnlyDictionary<string, IReadOnlyList<DrawSliceSpec>> BuildSpecMap(IReadOnlyList<KnownSliceTable> tables)
    {
        var map = new Dictionary<string, List<DrawSliceSpec>>(StringComparer.OrdinalIgnoreCase);
        foreach (KnownSliceTable table in tables)
        {
            foreach (IGrouping<string, DrawSliceSpec> group in table.Specs.GroupBy(static s => s.TextureName, StringComparer.OrdinalIgnoreCase))
            {
                if (!map.TryGetValue(group.Key, out List<DrawSliceSpec>? list))
                {
                    list = [];
                    map[group.Key] = list;
                }

                list.AddRange(group);
            }
        }

        return map.ToDictionary(
            static pair => pair.Key,
            static pair => (IReadOnlyList<DrawSliceSpec>)pair.Value,
            StringComparer.OrdinalIgnoreCase);
    }

    static KnownSliceTable ReadTable(byte[] elf, uint tableAddr, uint count, string name)
    {
        IReadOnlyList<DrawSliceSpec> specs = ElfReader.ReadDrawSliceSpecs(elf, tableAddr, count);
        return new KnownSliceTable(name, tableAddr, specs);
    }
}
