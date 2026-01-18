using System.Text;

namespace VNTextractor.Core.Extraction;

public sealed record ExtractOptions
{
    public required Encoding InputEncoding { get; init; }

    // .NET ReadLine() already strips newline; we must not trim any other whitespace.
    public bool SkipSemicolonComments { get; init; }
    public bool SkipDoubleSlashComments { get; init; }
}

