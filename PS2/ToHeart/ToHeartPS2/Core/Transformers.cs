namespace ToHeartPS2;

internal static class Transformers
{
    static readonly string[] _available = { "TPP" };
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

        var set = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (string token in spec.Split([',', ';', ' '], StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
        {
            if (!_available.Contains(token, StringComparer.OrdinalIgnoreCase))
            {
                error = $"unknown transformer: {token}";
                return false;
            }

            set.Add(token);
        }

        _enabled = set;
        return true;
    }

    public static bool CanTransform(string name) => _enabled.Contains(name.TrimStart('.'));
}
