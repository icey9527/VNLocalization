using System.Text.RegularExpressions;

namespace VNTextractor.Core.Extraction;

public static class JpTextDetector
{
    // From user's Python regex:
    // [\u4e00-\u9fff\u3040-\u30ff\u31f0-\u31ff\uff61-\uff9f\uff01-\uff60\uffe0-\uffe6]
    private static readonly Regex Pattern = new(
        //@"[\u4e00-\u9fff\u3040-\u30ff\u31f0-\u31ff\uff61-\uff9f\uff01-\uff60\uffe0-\uffe6]",
        @"[\u3000-\uFFE6]",
        RegexOptions.Compiled | RegexOptions.CultureInvariant
    );

    public static bool ContainsJpText(string line) => Pattern.IsMatch(line);
}

