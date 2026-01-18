using System.Text;
using VNTextractor.Core.Extraction;

namespace VNTextractor.Core.Export;

public sealed class DlTxtExporter : IExporter
{
    public string Name => "dltxt";

    public void Export(string outputRoot, ExtractionResult result, ExportOptions options, Action<string>? log = null)
    {
        var outDir = outputRoot;
        Directory.CreateDirectory(outDir);

        var utf8NoBom = new UTF8Encoding(encoderShouldEmitUTF8Identifier: false);

        if (options.MergeOutput)
        {
            var path = Path.Combine(outDir, "all.txt");
            using var sw = new StreamWriter(path, append: false, encoding: utf8NoBom);
            WriteAll(sw, result, merged: true);
        }
        else
        {
            foreach (var (rel, items) in result.ItemsByFile.OrderBy(kv => kv.Key, StringComparer.OrdinalIgnoreCase))
            {
                var outPath = MakePerFileDlTxtPath(outDir, rel);
                Directory.CreateDirectory(Path.GetDirectoryName(outPath)!);

                using var sw = new StreamWriter(outPath, append: false, encoding: utf8NoBom);
                WriteFile(sw, items, merged: false);
            }
        }

        log?.Invoke($"[dltxt] wrote {result.TotalItemCount} entries");
    }

    private static void WriteAll(StreamWriter sw, ExtractionResult result, bool merged)
    {
        foreach (var (_, items) in result.ItemsByFile.OrderBy(kv => kv.Key, StringComparer.OrdinalIgnoreCase))
            WriteFile(sw, items, merged);
    }

    private static void WriteFile(StreamWriter sw, IReadOnlyList<ExtractionItem> items, bool merged)
    {
        const string origPrefix = "\u25C7"; // ◇
        const string transPrefix = "\u25C6"; // ◆

        foreach (var item in items)
        {
            sw.Write('#');
            sw.WriteLine(merged ? $"{item.FileName}@{item.SourceLineNumber}" : item.SourceLineNumber.ToString());

            sw.Write(origPrefix);
            sw.WriteLine(item.Text);

            // Requirement: translation line is pre-filled with original.
            sw.Write(transPrefix);
            sw.WriteLine(item.Text);

            sw.WriteLine();
        }
    }

    private static string MakePerFileDlTxtPath(string dltxtDir, string relPosix)
        => Core.PathNaming.MakeDlTxtPerFilePath(dltxtDir, relPosix);

    // outputDlTxtPath: exact output file path (merged mode).
    public void ExportMergedToFile(string outputDlTxtPath, ExtractionResult result)
    {
        var dir = Path.GetDirectoryName(Path.GetFullPath(outputDlTxtPath))!;
        Directory.CreateDirectory(dir);

        var utf8NoBom = new UTF8Encoding(encoderShouldEmitUTF8Identifier: false);
        using var sw = new StreamWriter(outputDlTxtPath, append: false, encoding: utf8NoBom);
        WriteAll(sw, result, merged: true);
    }
}
