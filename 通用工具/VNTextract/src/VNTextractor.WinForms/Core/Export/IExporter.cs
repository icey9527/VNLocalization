using VNTextractor.Core.Extraction;

namespace VNTextractor.Core.Export;

public interface IExporter
{
    string Name { get; }

    void Export(string outputRoot, ExtractionResult result, ExportOptions options, Action<string>? log = null);
}

