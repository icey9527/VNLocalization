using System.Text;
using VNTextractor.Core.Extraction;

namespace VNTextractor.Core.Export;

public sealed class AllTxtExporter : IExporter
{
    public string Name => "alltxt";

    private const string IndexFileName = "lines.txt";

    // outputRoot: directory (split mode)
    public void Export(string outputRoot, ExtractionResult result, ExportOptions options, Action<string>? log = null)
    {
        var outDir = outputRoot;
        Directory.CreateDirectory(outDir);

        var utf8NoBom = new UTF8Encoding(encoderShouldEmitUTF8Identifier: false);

        var indexRows = new List<string>();

        if (options.MergeOutput)
        {
            var allPath = Path.Combine(outDir, "all.txt");
            using var sw = new StreamWriter(allPath, append: false, encoding: utf8NoBom);

            var mergedLineNo = 0;
            foreach (var (rel, items) in result.ItemsByFile.OrderBy(kv => kv.Key, StringComparer.OrdinalIgnoreCase))
            {
                foreach (var item in items)
                {
                    mergedLineNo++;
                    sw.WriteLine(item.Text);
                    indexRows.Add($"{rel} {mergedLineNo} {item.SourceLineNumber}");
                }
            }
        }
        else
        {
            foreach (var (rel, items) in result.ItemsByFile.OrderBy(kv => kv.Key, StringComparer.OrdinalIgnoreCase))
            {
                var outTextPath = MakePerFileAllTxtPath(outDir, rel);
                Directory.CreateDirectory(Path.GetDirectoryName(outTextPath)!);

                using var sw = new StreamWriter(outTextPath, append: false, encoding: utf8NoBom);
                var textLineNo = 0;
                foreach (var item in items)
                {
                    textLineNo++;
                    sw.WriteLine(item.Text);
                    indexRows.Add($"{rel} {textLineNo} {item.SourceLineNumber}");
                }
            }
        }

        var indexPath = Path.Combine(outDir, IndexFileName);
        File.WriteAllText(indexPath, string.Join("\n", indexRows) + (indexRows.Count > 0 ? "\n" : ""), utf8NoBom);

        log?.Invoke($"[alltxt] wrote {result.TotalItemCount} lines");
    }

    private static string MakePerFileAllTxtPath(string alltxtDir, string relPosix)
        => Core.PathNaming.MakeAllTxtPerFilePath(alltxtDir, relPosix);

    // outputAllTxtPath: exact output file path (merged mode).
    // Will also write lines.txt next to it.
    public void ExportMergedToFile(string outputAllTxtPath, ExtractionResult result)
    {
        var dir = Path.GetDirectoryName(Path.GetFullPath(outputAllTxtPath))!;
        Directory.CreateDirectory(dir);

        var utf8NoBom = new UTF8Encoding(encoderShouldEmitUTF8Identifier: false);
        var indexRows = new List<string>();

        using (var sw = new StreamWriter(outputAllTxtPath, append: false, encoding: utf8NoBom))
        {
            var mergedLineNo = 0;
            foreach (var (rel, items) in result.ItemsByFile.OrderBy(kv => kv.Key, StringComparer.OrdinalIgnoreCase))
            {
                foreach (var item in items)
                {
                    mergedLineNo++;
                    sw.WriteLine(item.Text);
                    indexRows.Add($"{rel} {mergedLineNo} {item.SourceLineNumber}");
                }
            }
        }

        var indexPath = Path.Combine(dir, IndexFileName);
        File.WriteAllText(indexPath, string.Join("\n", indexRows) + (indexRows.Count > 0 ? "\n" : ""), utf8NoBom);
    }
}
