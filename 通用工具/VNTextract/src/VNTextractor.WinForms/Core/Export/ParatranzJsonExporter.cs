using System.Text;
using System.Text.Encodings.Web;
using System.Text.Unicode;
using System.Text.Json;
using VNTextractor.Core.Extraction;

namespace VNTextractor.Core.Export;

public sealed class ParatranzJsonExporter : IExporter
{
    public string Name => "paratranz-json";

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
        // Keep full-width spaces, kana, etc. unescaped for readability.
        Encoder = JavaScriptEncoder.Create(UnicodeRanges.All)
    };

    private sealed record ParatranzItem(string key, string original, string translation, int stage);

    public void Export(string outputRoot, ExtractionResult result, ExportOptions options, Action<string>? log = null)
    {
        var outDir = outputRoot;
        Directory.CreateDirectory(outDir);

        if (options.MergeOutput)
        {
            var path = Path.Combine(outDir, "all.json");
            var list = MakeAll(result, merged: true);
            WriteJson(path, list);
        }
        else
        {
            foreach (var (rel, items) in result.ItemsByFile.OrderBy(kv => kv.Key, StringComparer.OrdinalIgnoreCase))
            {
                var outPath = MakePerFileJsonPath(outDir, rel);
                Directory.CreateDirectory(Path.GetDirectoryName(outPath)!);

                var list = items.Select(i => ToParatranz(i, merged: false)).ToList();
                WriteJson(outPath, list);
            }
        }

        log?.Invoke($"[paratranz] wrote {result.TotalItemCount} items (stage=0)");
    }

    private static List<ParatranzItem> MakeAll(ExtractionResult result, bool merged)
    {
        var list = new List<ParatranzItem>(capacity: result.TotalItemCount);
        foreach (var (_, items) in result.ItemsByFile.OrderBy(kv => kv.Key, StringComparer.OrdinalIgnoreCase))
            list.AddRange(items.Select(i => ToParatranz(i, merged)));
        return list;
    }

    private static ParatranzItem ToParatranz(ExtractionItem item, bool merged)
    {
        var key = merged ? $"{item.FileName}@{item.SourceLineNumber}" : item.SourceLineNumber.ToString();
        return new ParatranzItem(key, item.Text, translation: "", stage: 0);
    }

    private static void WriteJson(string path, List<ParatranzItem> list)
    {
        var utf8NoBom = new UTF8Encoding(encoderShouldEmitUTF8Identifier: false);
        var json = JsonSerializer.Serialize(list, JsonOptions);
        File.WriteAllText(path, json + "\n", utf8NoBom);
    }

    private static string MakePerFileJsonPath(string jsonDir, string relPosix)
        => Core.PathNaming.MakeParatranzPerFilePath(jsonDir, relPosix);

    // outputJsonPath: exact output file path (merged mode).
    public void ExportMergedToFile(string outputJsonPath, ExtractionResult result)
    {
        var dir = Path.GetDirectoryName(Path.GetFullPath(outputJsonPath))!;
        Directory.CreateDirectory(dir);

        var list = MakeAll(result, merged: true);
        WriteJson(outputJsonPath, list);
    }
}
