using System.Text;

namespace VNTextractor.Core.WriteBack;

public static class DlTxtWriteBack
{
    public static int WriteBackSplit(string sourceDir, string dltxtDir, string outputDir, Encoding sourceEncoding, Encoding outputEncoding, Action<string>? log = null)
    {
        Directory.CreateDirectory(outputDir);

        var appliedFiles = 0;
        var seenTxtFiles = 0;
        foreach (var path in Directory.EnumerateFiles(dltxtDir, "*.txt", SearchOption.AllDirectories))
        {
            seenTxtFiles++;
            var rel = Path.GetRelativePath(dltxtDir, path);
            var relPosix = Core.PathNaming.ToPosixPath(rel);
            var fileName = Path.GetFileName(relPosix);

            // dltxt export file is "<originalName>.txt"
            var srcFileName = Core.PathNaming.StripTrailingExtension(fileName, ".txt");

            var relDir = Path.GetDirectoryName(relPosix)?.Replace('\\', '/');
            var srcRel = relDir is null ? srcFileName : $"{relDir}/{srcFileName}";
            var srcPath = Path.Combine(sourceDir, Core.PathNaming.ToNativePath(srcRel));
            if (!File.Exists(srcPath))
            {
                // Fallback: find by file name anywhere under sourceDir (split export might not preserve subdirs).
                var matches = Directory.EnumerateFiles(sourceDir, srcFileName, SearchOption.AllDirectories).ToList();
                if (matches.Count == 1)
                {
                    log?.Invoke($"[dltxt-split] fallback match: {srcRel} -> {Path.GetRelativePath(sourceDir, matches[0]).Replace('\\', '/')}");
                    srcPath = matches[0];
                    srcRel = Core.PathNaming.ToPosixPath(Path.GetRelativePath(sourceDir, srcPath));
                }
                else
                {
                    log?.Invoke($"[dltxt-split] skip (source not found): in={relPosix} expect={srcRel} matches={matches.Count}");
                    continue;
                }
            }

            var replacements = ParseDlTxtFile(path);
            if (replacements.Count == 0)
            {
                log?.Invoke($"[dltxt-split] skip (not dltxt): {relPosix}");
                continue; // not a dltxt file or nothing to apply
            }

            log?.Invoke($"[dltxt-split] apply: in={relPosix} -> src={srcRel} entries={replacements.Count}");
            ApplyReplacementsToFile(srcPath, Path.Combine(outputDir, Core.PathNaming.ToNativePath(srcRel)), replacements, sourceEncoding, outputEncoding);
            appliedFiles++;
        }

        // Help diagnose "Done but nothing happened" cases.
        if (seenTxtFiles == 0)
            throw new InvalidDataException($"输入目录里没有找到任何 .txt 文件：{dltxtDir}");

        return appliedFiles;
    }

    public static int WriteBackMerged(string sourceDir, string mergedDlTxtPath, string outputDir, Encoding sourceEncoding, Encoding outputEncoding, Action<string>? log = null)
    {
        Directory.CreateDirectory(outputDir);

        var appliedFiles = 0;
        var byFile = ParseMergedDlTxt(mergedDlTxtPath);
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
            log?.Invoke($"[dltxt-merged] apply: src={Core.PathNaming.ToPosixPath(rel)} entries={replacements.Count}");
            ApplyReplacementsToFile(srcPath, outPath, replacements, sourceEncoding, outputEncoding);
            appliedFiles++;
        }

        return appliedFiles;
    }

    private static Dictionary<int, string> ParseDlTxtFile(string path)
    {
        var lines = File.ReadAllLines(path, new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
        var map = new Dictionary<int, string>();

        for (var i = 0; i < lines.Length; i++)
        {
            var line = lines[i];
            if (!line.StartsWith('#'))
                continue;

            var key = line[1..].Trim();
            // Split files may still contain "<file>@<line>" keys (e.g. user mixed/converted).
            // For split writeback we only need the numeric line number.
            var at = key.LastIndexOf('@');
            if (at >= 0)
                key = key[(at + 1)..];
            if (!int.TryParse(key, out var lineNo))
                continue;

            // Expect next two lines: ◇..., ◆...
            if (i + 2 >= lines.Length)
                continue;

            var transLine = lines[i + 2];
            var trans = ExtractPrefixedText(transLine, '\u25C6'); // ◆
            map[lineNo] = trans;
        }

        return map;
    }

    private static Dictionary<string, Dictionary<int, string>> ParseMergedDlTxt(string path)
    {
        var lines = File.ReadAllLines(path, new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
        var map = new Dictionary<string, Dictionary<int, string>>(StringComparer.OrdinalIgnoreCase);

        for (var i = 0; i < lines.Length; i++)
        {
            var line = lines[i];
            if (!line.StartsWith('#'))
                continue;

            var key = line[1..].Trim();
            var at = key.LastIndexOf('@');
            if (at <= 0)
                continue;

            var fileName = key[..at];
            if (!int.TryParse(key[(at + 1)..], out var lineNo))
                continue;

            if (i + 2 >= lines.Length)
                continue;

            var transLine = lines[i + 2];
            var trans = ExtractPrefixedText(transLine, '\u25C6'); // ◆

            if (!map.TryGetValue(fileName, out var dict))
            {
                dict = new Dictionary<int, string>();
                map[fileName] = dict;
            }
            dict[lineNo] = trans;
        }

        return map;
    }

    private static string ExtractPrefixedText(string line, char prefix)
    {
        if (line.Length > 0 && line[0] == prefix)
            return line[1..]; // keep whitespace exactly as-is
        return line;
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
