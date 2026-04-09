namespace ToHeartPSE;

internal static class Transformers
{
    static readonly string[] _available = { "LFF", "LFB", "LCF" };
    static HashSet<string> _enabled = new(_available, StringComparer.OrdinalIgnoreCase);

    public static IReadOnlyList<string> Available => _available;

    public static bool TryConfigure(string spec, out string error)
    {
        error = "";

        if (string.IsNullOrWhiteSpace(spec) || spec.Equals("all", StringComparison.OrdinalIgnoreCase))
        {
            _enabled = new HashSet<string>(_available, StringComparer.OrdinalIgnoreCase);
            return true;
        }

        if (spec.Equals("none", StringComparison.OrdinalIgnoreCase) || spec.Equals("off", StringComparison.OrdinalIgnoreCase))
        {
            _enabled = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            return true;
        }

        List<string> tokens = SplitTokens(spec);
        if (tokens.Count == 0)
        {
            error = "转换器参数为空";
            return false;
        }

        bool baseAll = false;
        if (tokens[0].Equals("all", StringComparison.OrdinalIgnoreCase))
        {
            baseAll = true;
            tokens.RemoveAt(0);
        }
        else
        {
            foreach (string t in tokens)
            {
                if (t.Length > 0 && (t[0] == '-' || t[0] == '!'))
                {
                    baseAll = true;
                    break;
                }
            }
        }

        var set = baseAll
            ? new HashSet<string>(_available, StringComparer.OrdinalIgnoreCase)
            : new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        foreach (string raw in tokens)
        {
            if (string.IsNullOrWhiteSpace(raw))
                continue;

            bool remove = raw[0] == '-' || raw[0] == '!';
            string name = remove ? raw[1..] : raw;
            if (!_available.Contains(name, StringComparer.OrdinalIgnoreCase))
            {
                error = $"未知转换器: {name}";
                return false;
            }

            if (remove) set.Remove(name);
            else set.Add(name);
        }

        _enabled = set;
        return true;
    }

    public static bool CanTransform(string extOrName) =>
        _enabled.Contains(extOrName.TrimStart('.'));

    static List<string> SplitTokens(string spec)
    {
        var result = new List<string>();
        int i = 0;
        while (i < spec.Length)
        {
            while (i < spec.Length && IsSep(spec[i])) i++;
            if (i >= spec.Length) break;
            int j = i;
            while (j < spec.Length && !IsSep(spec[j])) j++;
            string token = spec[i..j].Trim();
            if (token.Length != 0)
                result.Add(token);
            i = j;
        }
        return result;
    }

    static bool IsSep(char c) => c == ',' || c == ';' || c == ' ' || c == '\t' || c == '\r' || c == '\n';
}
