namespace ToHeartPS2;

internal static class TppNameCodec
{
    public static string InferTppName(string relPath)
    {
        return Path.GetFileNameWithoutExtension(relPath).ToUpperInvariant();
    }

    public static IReadOnlyList<string> InferDefaults(string relPath, string tppName, int partCount)
    {
        if (partCount <= 0)
            return [];

        string dir = Path.GetFileName(Path.GetDirectoryName(relPath) ?? "").ToUpperInvariant();
        if (partCount == 1)
            return [tppName];

        return dir switch
        {
            "CHAR" => Enumerable.Range(0, partCount).Select(i => $"{tppName}{i:00}").ToArray(),
            "BG" or "VISUAL" => Enumerable.Range(0, partCount).Select(i => $"{tppName}_{i:00}").ToArray(),
            _ => []
        };
    }

    public static bool IsDefaultSequence(string relPath, string tppName, IReadOnlyList<string> names)
    {
        IReadOnlyList<string> expected = InferDefaults(relPath, tppName, names.Count);
        if (expected.Count != names.Count)
            return false;
        for (int i = 0; i < names.Count; i++)
        {
            if (!string.Equals(expected[i], names[i], StringComparison.OrdinalIgnoreCase))
                return false;
        }

        return true;
    }

    public static bool TryEncode(IReadOnlyList<string> names, out string mode, out string value)
    {
        mode = "";
        value = "";
        if (names.Count == 0)
            return false;

        if (names.All(name => string.Equals(name, names[0], StringComparison.OrdinalIgnoreCase)))
        {
            mode = "same";
            value = names[0];
            return true;
        }

        if (TryEncodeSeq2(names, out string prefix))
        {
            mode = "seq2";
            value = prefix;
            return true;
        }

        return false;
    }

    public static IReadOnlyList<string> Decode(string relPath, string tppName, int partCount, string mode, string value)
    {
        if (partCount <= 0)
            return [];

        if (string.IsNullOrWhiteSpace(mode))
            return InferDefaults(relPath, tppName, partCount);

        return mode.ToLowerInvariant() switch
        {
            "same" => Enumerable.Repeat(value, partCount).ToArray(),
            "seq2" => Enumerable.Range(0, partCount).Select(i => $"{value}{i:00}").ToArray(),
            _ => []
        };
    }

    static bool TryEncodeSeq2(IReadOnlyList<string> names, out string prefix)
    {
        prefix = "";
        if (names.Count == 0)
            return false;

        string first = names[0];
        if (first.Length < 2)
            return false;
        prefix = first[..^2];
        if (!SuffixEqualsIndex(first, 0))
            return false;

        for (int i = 1; i < names.Count; i++)
        {
            string name = names[i];
            if (name.Length != prefix.Length + 2)
                return false;
            if (!name.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
                return false;
            if (!SuffixEqualsIndex(name, i))
                return false;
        }

        return true;
    }

    static bool SuffixEqualsIndex(string name, int index)
    {
        if (name.Length < 2)
            return false;
        ReadOnlySpan<char> suffix = name.AsSpan(name.Length - 2, 2);
        return suffix[0] == (char)('0' + ((index / 10) % 10))
            && suffix[1] == (char)('0' + (index % 10));
    }
}
