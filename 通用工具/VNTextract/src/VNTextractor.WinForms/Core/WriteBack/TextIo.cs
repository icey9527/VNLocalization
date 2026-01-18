using System.Text;

namespace VNTextractor.Core.WriteBack;

public static class TextIo
{
    public sealed record ReadResult(string[] Lines, int AppendNewlines);

    public static ReadResult ReadForEdit(string path, Encoding encoding)
    {
        // Read full text once so we can preserve trailing newline count (including multiple blank lines at EOF).
        var text = File.ReadAllText(path, encoding);

        var rawTrailingBreaks = CountTrailingLineBreaks(text);

        // Normalize line separators for splitting (content stays unchanged except line terminators).
        var normalized = text.Replace("\r\n", "\n").Replace("\r", "\n");
        var parts = normalized.Split('\n', StringSplitOptions.None);

        // Mimic StreamReader.ReadLine(): if file ends with a terminator, Split adds a final "" which ReadLine wouldn't return.
        if (normalized.Length > 0 && normalized[^1] == '\n' && parts.Length > 0 && parts[^1].Length == 0)
            parts = parts[..^1];

        var emptyAtEnd = 0;
        for (var i = parts.Length - 1; i >= 0; i--)
        {
            if (parts[i].Length != 0)
                break;
            emptyAtEnd++;
        }

        var append = Math.Max(0, rawTrailingBreaks - emptyAtEnd);
        return new ReadResult(parts, append);
    }

    public static void WriteEdited(string path, string[] lines, int appendNewlines, Encoding encoding)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(path))!);

        var sb = new StringBuilder();
        if (lines.Length > 0)
            sb.Append(string.Join("\n", lines));
        if (appendNewlines > 0)
            sb.Append(new string('\n', appendNewlines));

        File.WriteAllText(path, sb.ToString(), encoding);
    }

    private static int CountTrailingLineBreaks(string text)
    {
        var count = 0;
        for (var i = text.Length - 1; i >= 0;)
        {
            var c = text[i];
            if (c == '\n')
            {
                count++;
                i--;
                if (i >= 0 && text[i] == '\r')
                    i--;
                continue;
            }
            if (c == '\r')
            {
                count++;
                i--;
                continue;
            }
            break;
        }
        return count;
    }
}

