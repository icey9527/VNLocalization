using System.Text;
using System.Text.Json;

namespace VNTextractor.Core.WriteBack;

public static class ParatranzWriteBack
{
    private sealed class ParatranzItem
    {
        public string? key { get; set; }
        public string? original { get; set; }
        public string? translation { get; set; }
        public int stage { get; set; }
    }

    public static int WriteBackSplit(string sourceDir, string jsonDir, string outputDir, Encoding sourceEncoding, Encoding outputEncoding, Action<string>? log = null)
    {
        Directory.CreateDirectory(outputDir);

        var appliedFiles = 0;
        foreach (var path in Directory.EnumerateFiles(jsonDir, "*.json", SearchOption.AllDirectories))
        {
            var rel = Path.GetRelativePath(jsonDir, path);
            var relPosix = Core.PathNaming.ToPosixPath(rel);
            var fileName = Path.GetFileName(relPosix);

            // json export file is "<originalName>.json" (original extension kept)
            var srcFileName = Core.PathNaming.StripTrailingExtension(fileName, ".json");

            var relDir = Path.GetDirectoryName(relPosix)?.Replace('\\', '/');
            var srcRel = relDir is null ? srcFileName : $"{relDir}/{srcFileName}";
            var srcPath = Path.Combine(sourceDir, Core.PathNaming.ToNativePath(srcRel));
            if (!File.Exists(srcPath))
            {
                var matches = Directory.EnumerateFiles(sourceDir, srcFileName, SearchOption.AllDirectories).ToList();
                if (matches.Count == 1)
                {
                    log?.Invoke($"[json-split] fallback match: {srcRel} -> {Path.GetRelativePath(sourceDir, matches[0]).Replace('\\', '/')}");
                    srcPath = matches[0];
                    srcRel = Core.PathNaming.ToPosixPath(Path.GetRelativePath(sourceDir, srcPath));
                }
                else
                {
                    log?.Invoke($"[json-split] skip (source not found): in={relPosix} expect={srcRel} matches={matches.Count}");
                    continue;
                }
            }

            var replacements = ParseSplitJson(path);
            if (replacements.Count == 0)
                continue;
            log?.Invoke($"[json-split] apply: in={relPosix} -> src={srcRel} entries={replacements.Count}");
            ApplyReplacementsToFile(srcPath, Path.Combine(outputDir, Core.PathNaming.ToNativePath(srcRel)), replacements, sourceEncoding, outputEncoding);
            appliedFiles++;
        }

        return appliedFiles;
    }

    public static int WriteBackMerged(string sourceDir, string mergedJsonPath, string outputDir, Encoding sourceEncoding, Encoding outputEncoding, Action<string>? log = null)
    {
        Directory.CreateDirectory(outputDir);

        var appliedFiles = 0;
        var byFile = ParseMergedJson(mergedJsonPath);
        foreach (var (fileName, replacements) in byFile)
        {
            var matches = Directory.EnumerateFiles(sourceDir, fileName, SearchOption.AllDirectories).ToList();
            if (matches.Count == 0)
                throw new InvalidDataException($"Source file not found for key '{fileName}@...': {fileName}");
            if (matches.Count > 1)
                throw new InvalidDataException($"Ambiguous source file name '{fileName}' (found {matches.Count} matches). Use unique file names or change key strategy.");

            var srcPath = matches[0];
            var rel = Path.GetRelativePath(sourceDir, srcPath);
            var outPath = Path.Combine(outputDir, rel);
            log?.Invoke($"[json-merged] apply: src={Core.PathNaming.ToPosixPath(rel)} entries={replacements.Count}");
            ApplyReplacementsToFile(srcPath, outPath, replacements, sourceEncoding, outputEncoding);
            appliedFiles++;
        }

        return appliedFiles;
    }

    private static Dictionary<int, string> ParseSplitJson(string path)
    {
        try
        {
            var json = File.ReadAllText(path, new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
            var items = JsonSerializer.Deserialize<List<ParatranzItem>>(json) ?? [];

            var map = new Dictionary<int, string>();
            foreach (var it in items)
            {
                if (it.key is null) continue;
                var key = it.key;
                var at = key.LastIndexOf('@');
                if (at >= 0)
                    key = key[(at + 1)..];
                if (!int.TryParse(key, out var lineNo)) continue;
                // stage decides which text to write back:
                // stage=1 => translation (fallback to original if empty)
                // otherwise => original
                var text = (it.stage == 1 && !string.IsNullOrEmpty(it.translation)) ? it.translation! : (it.original ?? "");
                map[lineNo] = text;
            }
            return map;
        }
        catch (JsonException ex)
        {
            throw new InvalidDataException($"Invalid JSON: {path}\n{ex.Message}");
        }
    }

    private static Dictionary<string, Dictionary<int, string>> ParseMergedJson(string path)
    {
        try
        {
            var json = File.ReadAllText(path, new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
            var items = JsonSerializer.Deserialize<List<ParatranzItem>>(json) ?? [];

            var map = new Dictionary<string, Dictionary<int, string>>(StringComparer.OrdinalIgnoreCase);
            foreach (var it in items)
            {
                if (it.key is null) continue;

                var at = it.key.LastIndexOf('@');
                if (at <= 0) continue;
                var fileName = it.key[..at];
                if (!int.TryParse(it.key[(at + 1)..], out var lineNo)) continue;

                if (!map.TryGetValue(fileName, out var dict))
                {
                    dict = new Dictionary<int, string>();
                    map[fileName] = dict;
                }
                var text = (it.stage == 1 && !string.IsNullOrEmpty(it.translation)) ? it.translation! : (it.original ?? "");
                dict[lineNo] = text;
            }
            return map;
        }
        catch (JsonException ex)
        {
            throw new InvalidDataException($"Invalid JSON: {path}\n{ex.Message}");
        }
    }

    private static void ApplyReplacementsToFile(string srcPath, string outPath, Dictionary<int, string> replacements, Encoding sourceEncoding, Encoding outputEncoding)
    {
        var read = TextIo.ReadForEdit(srcPath, sourceEncoding);
        var srcLines = read.Lines;

        foreach (var (lineNo, trans) in replacements)
        {
            if (lineNo < 1 || lineNo > srcLines.Length)
                continue;
            srcLines[lineNo - 1] = trans;
        }

        TextIo.WriteEdited(outPath, srcLines, read.AppendNewlines, outputEncoding);
    }
}
