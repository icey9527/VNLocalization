namespace VNTextractor.Core.Extraction;

public sealed record ExtractionResult
{
    // Key: relative path (posix-style). Value: items in file order.
    public required IReadOnlyDictionary<string, IReadOnlyList<ExtractionItem>> ItemsByFile { get; init; }

    public int TotalItemCount => ItemsByFile.Values.Sum(v => v.Count);
}

