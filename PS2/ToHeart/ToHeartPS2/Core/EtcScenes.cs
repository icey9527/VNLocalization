using System.Text;

namespace ToHeartPS2;

internal sealed record EtcRenderNote(
    string Name,
    uint Address,
    string Notes);

internal static class EtcScenes
{
    public static IReadOnlyList<EtcRenderNote> GetKnownNotes()
    {
        return
        [
            new(
                "menu_bg2_and_menu_sbg",
                0x00294210,
                "MENU_BG2 and MENU_SBG already have explicit 6-entry draw tables at 0x294210 and 0x2942A0. "
                    + "Current exporter is already using those tables, which is why these two are much closer to correct final output."),
            new(
                "m_album",
                0x00290780,
                "M_ALBUM uses a dedicated 22-entry draw table at 0x290780 and is referenced by sub_11FA20. "
                    + "Current exporter already applies this table."),
            new(
                "month00_02",
                0x001333D0,
                "MONTH00, MONTH01 and MONTH02 are loaded by sub_1333D0 together with CALANxx and DAY/WEEK assets. "
                    + "This strongly suggests calendar composition logic rather than plain atlas export."),
            new(
                "matirin",
                0x00117440,
                "MATIRIN is handled by sub_117440. The game issues runtime draws through sub_13ECD0 at 0x11779C and 0x11784C "
                    + "using animated indices derived from timers, so MATIRIN is a scene/animation asset, not a static crop."),
            new(
                "menu_bg",
                0x002F2848,
                "MENU_BG has multiple string/data references around 0x2E53F8, 0x2E5400, 0x2E5530, 0x2E5FB8, 0x2E60D0 and 0x2F2848. "
                    + "A nearby batch of 6-word draw descriptors at 0x28F980, 0x28F9B0, 0x28FA10 and 0x28FB78 first looked related, "
                    + "but after integration they decode as M_OPTION slices rather than MENU_BG slices. "
                    + "So MENU_BG itself is still unresolved and likely uses a different table or a later scene-side draw step."),
            new(
                "m_option",
                0x0028F980,
                "The 4 small tables at 0x28F980, 0x28F9B0, 0x28FA10 and 0x28FB78 are confirmed 6-word draw descriptor tables for M_OPTION. "
                    + "They use the same { name_ptr, part_index, src_x, src_y, width, height } layout as the other integrated menu tables."),
            new(
                "map03_05_and_mul_080_082",
                0x002ED4D0,
                "MAP03-05 and MUL_080-082 do appear in the ETC 0x24 metadata table at 0x2ED4D0, but that table only explains atlas layout "
                    + "(origin/cols/rows). It does not explain the final visible crop, so an additional draw table or per-scene function is still missing.")
        ];
    }

    public static string FormatForText()
    {
        var sb = new StringBuilder();
        sb.AppendLine("# ETC render notes");
        sb.AppendLine("# These are assembly-grounded observations about assets that do not behave like plain atlas exports.");
        sb.AppendLine();

        foreach (EtcRenderNote note in GetKnownNotes())
        {
            sb.AppendLine($"[{note.Name}] 0x{note.Address:X8}");
            sb.AppendLine($"notes = {note.Notes}");
            sb.AppendLine();
        }

        return sb.ToString();
    }
}
