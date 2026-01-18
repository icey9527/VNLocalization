namespace VNTextractor.Core.Extraction;

public sealed record ExtractionItem
{
    public required string RelativePath { get; init; } // posix-style (/) for stable export
    public required string FileName { get; init; }
    public required int SourceLineNumber { get; init; } // 1-based
    public required string Text { get; init; } // unchanged line text (except newline removed by ReadLine)
}
