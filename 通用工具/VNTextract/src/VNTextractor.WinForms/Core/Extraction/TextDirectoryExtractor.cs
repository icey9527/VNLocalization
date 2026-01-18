using System.Text;

namespace VNTextractor.Core.Extraction;

public sealed class TextDirectoryExtractor
{
    public ExtractionResult Extract(string inputDirectory, string? outputDirectoryToSkip, ExtractOptions options, Action<string>? log = null)
    {
        if (string.IsNullOrWhiteSpace(inputDirectory))
            throw new ArgumentException("Input directory is required.", nameof(inputDirectory));

        var inputFull = Path.GetFullPath(inputDirectory);
        string? outputFull = null;
        if (!string.IsNullOrWhiteSpace(outputDirectoryToSkip))
            outputFull = Path.GetFullPath(outputDirectoryToSkip!);

        var files = Directory.EnumerateFiles(inputFull, "*", SearchOption.AllDirectories)
            .Where(p => !IsUnderDirectory(p, outputFull))
            .OrderBy(p => p, StringComparer.OrdinalIgnoreCase)
            .ToList();

        var map = new Dictionary<string, IReadOnlyList<ExtractionItem>>(StringComparer.OrdinalIgnoreCase);

        foreach (var file in files)
        {
            var rel = Path.GetRelativePath(inputFull, file);
            var relPosix = rel.Replace('\\', '/');
            var fileName = Path.GetFileName(relPosix);

            var items = new List<ExtractionItem>();
            try
            {
                using var fs = File.OpenRead(file);
                using var sr = new StreamReader(fs, options.InputEncoding, detectEncodingFromByteOrderMarks: true);

                string? line;
                var srcLineNo = 0;
                while ((line = sr.ReadLine()) is not null)
                {
                    srcLineNo++;

                    if (ShouldSkipCommentLine(line, options))
                        continue;

                    if (!JpTextDetector.ContainsJpText(line))
                        continue;

                    items.Add(new ExtractionItem
                    {
                        RelativePath = relPosix,
                        FileName = fileName,
                        SourceLineNumber = srcLineNo,
                        Text = line
                    });
                }
            }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or DecoderFallbackException)
            {
                log?.Invoke($"[Skip] {relPosix} ({ex.GetType().Name}: {ex.Message})");
                items.Clear();
            }

            map[relPosix] = items;
        }

        return new ExtractionResult { ItemsByFile = map };
    }

    private static bool IsUnderDirectory(string filePath, string? dirFullPath)
    {
        if (string.IsNullOrWhiteSpace(dirFullPath))
            return false;

        var fileFull = Path.GetFullPath(filePath);
        var dirFull = dirFullPath!.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);

        // Ensure "C:\A\B" doesn't match "C:\A\B2".
        dirFull += Path.DirectorySeparatorChar;
        return fileFull.StartsWith(dirFull, StringComparison.OrdinalIgnoreCase);
    }

    private static bool ShouldSkipCommentLine(string line, ExtractOptions options)
    {
        // Requirement: whitespace before ';' or '//' also counts as comment.
        var s = line.TrimStart();

        if (options.SkipSemicolonComments && s.StartsWith(';'))
            return true;

        if (options.SkipDoubleSlashComments)
        {
            // Skip full-line comments: "   // comment"
            if (s.StartsWith("//", StringComparison.Ordinal))
                return true;

            // Also treat inline "//" as comment if the part after it contains JP text.
            // Example: "\tvar num; // 栞番号" => skip (comment part contains JP).
            var idx = line.IndexOf("//", StringComparison.Ordinal);
            if (idx >= 0)
            {
                var tail = line[idx..];
                if (JpTextDetector.ContainsJpText(tail))
                    return true;
            }
        }

        return false;
    }
}
