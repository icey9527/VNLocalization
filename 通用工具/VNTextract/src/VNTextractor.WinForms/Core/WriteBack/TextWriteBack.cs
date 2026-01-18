using System.Text;
using VNTextractor.Core.Extraction;

namespace VNTextractor.Core.WriteBack;

public static class TextWriteBack
{
    public sealed record WriteBackOptions
    {
        public required Encoding SourceEncoding { get; init; }
        public required Encoding OutputEncoding { get; init; }
    }

    public static void WriteBackAllTxt(string sourceDir, string linesTxtPath, string outputDir, WriteBackOptions options)
    {
        if (!Directory.Exists(sourceDir))
            throw new DirectoryNotFoundException($"SourceDir not found: {sourceDir}");
        if (!File.Exists(linesTxtPath))
            throw new FileNotFoundException("lines.txt not found", linesTxtPath);

        Directory.CreateDirectory(outputDir);

        var alltxtDir = Path.GetDirectoryName(Path.GetFullPath(linesTxtPath))!;
        var mergedAllPath = Path.Combine(alltxtDir, "all.txt");
        var mergedTextLines = File.Exists(mergedAllPath)
            ? TextIo.ReadForEdit(mergedAllPath, Encoding.UTF8).Lines
            : null;

        var groups = new Dictionary<string, List<(int TextLineNo, int SourceLineNo)>>(StringComparer.OrdinalIgnoreCase);
        foreach (var raw in File.ReadAllLines(linesTxtPath, Encoding.UTF8))
        {
            var row = raw.Trim();
            if (row.Length == 0)
                continue;
            var parts = row.Split(' ', StringSplitOptions.RemoveEmptyEntries);
            if (parts.Length != 3)
                continue;

            var rel = parts[0];
            if (!int.TryParse(parts[1], out var tNo)) continue;
            if (!int.TryParse(parts[2], out var sNo)) continue;

            if (!groups.TryGetValue(rel, out var list))
            {
                list = new List<(int, int)>();
                groups[rel] = list;
            }
            list.Add((tNo, sNo));
        }

        foreach (var (relPosix, mappings) in groups)
        {
            var relNative = Core.PathNaming.ToNativePath(relPosix);
            var srcPath = Path.Combine(sourceDir, relNative);
            if (!File.Exists(srcPath))
                continue;

            var srcRead = TextIo.ReadForEdit(srcPath, options.SourceEncoding);
            var srcLines = srcRead.Lines;

            string[] textLines;
            if (mergedTextLines is not null)
            {
                textLines = mergedTextLines;
            }
            else
            {
                var perFileTextPath = Core.PathNaming.MakeAllTxtPerFilePath(alltxtDir, relPosix);
                if (!File.Exists(perFileTextPath))
                    continue;
                textLines = TextIo.ReadForEdit(perFileTextPath, Encoding.UTF8).Lines;
            }

            foreach (var (textLineNo, srcLineNo) in mappings)
            {
                if (srcLineNo < 1 || srcLineNo > srcLines.Length) continue;
                if (textLineNo < 1 || textLineNo > textLines.Length) continue;
                srcLines[srcLineNo - 1] = textLines[textLineNo - 1];
            }

            var outPath = Path.Combine(outputDir, relNative);
            TextIo.WriteEdited(outPath, srcLines, srcRead.AppendNewlines, options.OutputEncoding);
        }
    }
}
