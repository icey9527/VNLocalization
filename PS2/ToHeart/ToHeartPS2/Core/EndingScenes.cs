using System.Text;

namespace ToHeartPS2;

internal static class EndingScenes
{
    public static readonly RuntimeDrawEntryLayout DrawQueueLayout = new(
        "flags",
        "name_ptr",
        "dst_x",
        "dst_y",
        "layer",
        "dst_w",
        "dst_h",
        "src_x",
        "src_y",
        "src_w",
        "src_h",
        "color");

    public static IReadOnlyList<EndingSceneSpec> GetKnownSceneSpecs()
    {
        return
        [
            new(
                "case_01_siho_intro",
                0x11B0BC,
                "sub_11AE30 case 1. Opens with SIHOEND_SEPI full-screen, then queues SIHOEND and four SIHO_UTA strips. "
                    + "The SIHO_UTA rows still need one more renderer-side decode step because width fields are zero in the queue data.",
                [
                    new("SIHOEND_SEPI", 0, 0, 16, 640, 448, 0, 0, 512, 448, 0x00808080),
                    new("SIHOEND", 0, 0, 16, 0, 0, 0, 0, 512, 448, 0x80808080, "Queued with zero destination size; renderer semantics still under investigation."),
                    new("SIHO_UTA", 64, 120, 16, 0, 48, 0, 0, 0, 48, 0x80808080, "Strip 0; queue width is zero in RAM."),
                    new("SIHO_UTA", 64, 168, 16, 0, 48, 0, 48, 0, 48, 0x80808080, "Strip 1; queue width is zero in RAM."),
                    new("SIHO_UTA", 64, 216, 16, 0, 48, 0, 96, 0, 48, 0x80808080, "Strip 2; queue width is zero in RAM."),
                    new("SIHO_UTA", 64, 264, 16, 0, 48, 0, 144, 0, 48, 0x80808080, "Strip 3; queue width is zero in RAM.")
                ]),
            new(
                "case_08_end01_end02_transition",
                0x11B808,
                "sub_11AE30 case 8. Two 512x448 sources are drawn into 640x448 destinations. "
                    + "END01 starts on-screen and END02 starts below the screen at y=448, then case 9 scrolls both upward.",
                [
                    new("END01", 0, 0, 16, 640, 448, 0, 0, 512, 448, 0x80808080),
                    new("END02", 0, 448, 16, 640, 448, 0, 0, 512, 448, 0x80808080)
                ]),
            new(
                "case_11_four_panel_intro",
                0x11BC84,
                "sub_11AE30 case 11. Uses either SPIC2/SPIC3/SPIC4/EH00 or SPIC2_SIHO/SPIC3_SIHO/SPIC4_SIHO/EH01 depending on ending route. "
                    + "These are explicit scene composites rather than a single atlas crop.",
                [
                    new("route+0", 0, 0, 16, 640, 448, 0, 0, 256, 224, 0x00808080, "Actual texture = off_28DC20[v14]."),
                    new("route+2", 304, 208, 16, 320, 224, 0, 0, 256, 224, 0x00808080, "Actual texture = off_28DC20[v14 + 2]."),
                    new("route+4", 288, 32, 16, 320, 224, 0, 0, 256, 224, 0x00808080, "Actual texture = off_28DC20[v14 + 4]."),
                    new("route+6", 32, 192, 16, 320, 224, 0, 0, 256, 224, 0x00808080, "Actual texture = off_28DC20[v14 + 6].")
                ]),
            new(
                "case_24_sk00_sk01_crossfade",
                0x11C87C,
                "sub_11AE30 case 24. SK00 and SK01 are both queued as full-screen 640x448 draws from 512x448 sources, with case 25/26 driving the fade and wipe.",
                [
                    new("SK00", 0, 0, 16, 640, 448, 0, 0, 512, 448, 0x80808080),
                    new("SK01", 0, 0, 16, 640, 448, 0, 0, 512, 448, 0x00808080)
                ]),
            new(
                "case_26_sk02_vertical_slice_wipe",
                0x11CAF4,
                "sub_11AE30 case 26/27. SK02 is not exported as one simple crop. The game builds 16 queue rows of 16-pixel vertical strips and advances them over time.",
                [
                    new("SK02", 0, 0, 17, 0, 448, 0, 0, 0, 448, 0x80808080, "Base row uses dynamic width. Cases 27-29 populate 16 additional strip rows.")
                ]),
            new(
                "case_28_sk03_vertical_slice_wipe",
                0x11D1C8,
                "sub_11AE30 case 28/29 mirrors the same 16-strip reveal logic for SK03, then swaps to SK04.",
                [
                    new("SK03", 0, 0, 16, 0, 448, 0, 0, 0, 448, 0x80808080, "16 additional strip rows are generated dynamically."),
                    new("SK04", 0, 0, 17, 0, 448, 0, 0, 0, 448, 0x80808080, "Loaded once the SK03 wipe completes.")
                ]),
            new(
                "case_31_ending_roll_frames",
                0x11E148,
                "sub_11AE30 case 31+. E0100..E0B09 are treated as individual full-screen frames scaled from 512x448 to 800x560.",
                [
                    new("E0xYY", 0, 0, 16, 800, 560, 0, 0, 512, 448, 0x00808080, "Exact texture name is chosen from off_28DC20 based on dword_398238 and the current frame index.")
                ])
        ];
    }

    public static IReadOnlyList<NamePointerArray> ReadKnownNameArrays(byte[] elf, Config config)
    {
        return
        [
            ReadArray(elf, config.EndingMainNameArrayAddr, "ending_main_names"),
            ReadArray(elf, config.EndingSkNameArrayAddr, "ending_sk_names"),
            ReadArray(elf, config.EndingSihoEndNameArrayAddr, "ending_sihoend_names"),
            ReadArray(elf, config.EndingSihoEndSepiaNameArrayAddr, "ending_sihoend_sepia_names"),
            ReadArray(elf, config.EndingRollNameArrayAddr, "ending_roll_names")
        ];
    }

    public static string FormatForText(IReadOnlyList<NamePointerArray> arrays)
    {
        IReadOnlyList<EndingSceneSpec> sceneSpecs = GetKnownSceneSpecs();
        var sb = new StringBuilder();
        sb.AppendLine("# Ending scene arrays used by sub_11AE30");
        sb.AppendLine("# These are pointer slices into one larger name list.");
        sb.AppendLine();
        sb.AppendLine("[draw_queue_layout]");
        sb.AppendLine("entry_size = 0x50 bytes (20 dwords)");
        sb.AppendLine("field_00 = flags");
        sb.AppendLine("field_01 = name_ptr");
        sb.AppendLine("field_02 = dst_x");
        sb.AppendLine("field_03 = dst_y");
        sb.AppendLine("field_04 = layer");
        sb.AppendLine("field_05 = dst_w");
        sb.AppendLine("field_06 = dst_h");
        sb.AppendLine("field_07 = src_x");
        sb.AppendLine("field_08 = src_y");
        sb.AppendLine("field_09 = src_w");
        sb.AppendLine("field_10 = src_h");
        sb.AppendLine("field_11 = color");
        sb.AppendLine();

        foreach (NamePointerArray array in arrays)
        {
            sb.AppendLine($"[{array.Name}] 0x{array.Address:X8} ({array.Values.Count} names)");
            for (int i = 0; i < array.Values.Count; i++)
                sb.AppendLine($"{i:D3}: {array.Values[i]}");
            sb.AppendLine();
        }

        sb.AppendLine("# Known scene composites from sub_11AE30");
        sb.AppendLine("# These are the cases that definitely are not plain 'flatten TPP then crop' outputs.");
        sb.AppendLine();
        foreach (EndingSceneSpec scene in sceneSpecs)
        {
            sb.AppendLine($"[{scene.Name}] 0x{scene.CaseAddress:X8}");
            sb.AppendLine($"notes = {scene.Notes}");
            for (int i = 0; i < scene.Ops.Count; i++)
            {
                EndingDrawOp op = scene.Ops[i];
                sb.AppendLine(
                    $"{i:D2}: tex={op.TextureName}, dst=({op.DestX},{op.DestY},{op.DestWidth},{op.DestHeight}), "
                    + $"src=({op.SourceX},{op.SourceY},{op.SourceWidth},{op.SourceHeight}), layer={op.Layer}, color=0x{op.Color:X8}"
                    + (string.IsNullOrWhiteSpace(op.Notes) ? "" : $", note={op.Notes}"));
            }

            sb.AppendLine();
        }

        return sb.ToString();
    }

    static NamePointerArray ReadArray(byte[] elf, uint addr, string name)
    {
        return new(name, addr, ElfReader.ReadNamePointerArray(elf, addr));
    }
}
