using System.Drawing;
using System.Drawing.Imaging;
using System.Text;

namespace ToHeartPSE;

internal static class App
{
    static readonly Encoding ShiftJis = Encoding.GetEncoding(932);

    public static void Unpack(string pakPath, string outputDir)
    {
        Directory.CreateDirectory(outputDir);
        var list = new ListXml();

        foreach (PakEntry entry in LeafPak.ReadEntries(pakPath))
        {
            string diskName = FlattenEntryName(entry.Name);
            if (TryConvertSpecialImage(entry.Name, diskName, entry.Data, out Bitmap? image, out ListEntry? listEntry)
                && image != null
                && listEntry != null)
            {
                image.Save(Path.Combine(outputDir, listEntry.Name), ImageFormat.Png);
                image.Dispose();
                list.Add(listEntry);
                Console.WriteLine($"{entry.Name} -> {listEntry.Name}");
                continue;
            }

            File.WriteAllBytes(Path.Combine(outputDir, diskName), entry.Data);
        }

        if (list.HasAny)
            list.Save(Path.Combine(outputDir, "list.xml"));
    }

    public static void Pack(string inputDir, string pakPath)
    {
        if (Directory.EnumerateDirectories(inputDir).Any())
            throw new InvalidOperationException("nested directories are not supported for LEAF PAK packing");

        var entries = new Dictionary<string, byte[]>(StringComparer.OrdinalIgnoreCase);
        var consumed = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        string listPath = Path.Combine(inputDir, "list.xml");
        if (File.Exists(listPath))
        {
            var list = ListXml.Load(listPath);
            consumed.Add(listPath);
            foreach (ListEntry item in list.AllEntries)
            {
                if (!Transformers.CanTransform(item.Section))
                    continue;

                string pngPath = Path.Combine(inputDir, item.Name);
                string rawName = ChangeExtensionToOriginal(item.Name, item.Section);
                string rawPath = Path.Combine(inputDir, rawName);
                byte[] data = File.Exists(pngPath)
                    ? EncodeSpecialImage(item, pngPath)
                    : File.Exists(rawPath)
                        ? File.ReadAllBytes(rawPath)
                        : throw new FileNotFoundException($"missing converted or raw file for {item.Name}");

                AddPackedEntry(entries, rawName, data);
                Console.WriteLine(File.Exists(pngPath) ? $"{item.Name} -> {rawName}" : rawName);
                consumed.Add(pngPath);
                if (File.Exists(rawPath))
                    consumed.Add(rawPath);
            }
        }

        foreach (string filePath in Directory.EnumerateFiles(inputDir).OrderBy(static p => p, StringComparer.OrdinalIgnoreCase))
        {
            if (consumed.Contains(filePath))
                continue;

            string fileName = Path.GetFileName(filePath);
            if (fileName.Equals("list.xml", StringComparison.OrdinalIgnoreCase))
                continue;

            AddPackedEntry(entries, fileName, File.ReadAllBytes(filePath));
            Console.WriteLine(fileName);
        }

        if (entries.Count == 0)
            throw new InvalidOperationException("input directory is empty");

        string? dir = Path.GetDirectoryName(pakPath);
        if (!string.IsNullOrEmpty(dir))
            Directory.CreateDirectory(dir);

        LeafPak.Write(entries, pakPath);
    }

    static bool TryConvertSpecialImage(string archiveName, string diskName, byte[] data, out Bitmap? image, out ListEntry? listEntry)
    {
        image = null;
        listEntry = null;
        string ext = Path.GetExtension(archiveName).TrimStart('.');
        if (!Transformers.CanTransform(ext))
            return false;

        switch (ext.ToLowerInvariant())
        {
            case "lff":
                return TryConvertLff(archiveName, diskName, data, out image, out listEntry);
            case "lfb":
                return TryConvertLfb(archiveName, diskName, data, out image, out listEntry);
            case "lcf":
                return TryConvertLcf(archiveName, diskName, data, out image, out listEntry);
            default:
                return false;
        }
    }

    static bool TryConvertLff(string archiveName, string diskName, byte[] data, out Bitmap? image, out ListEntry? listEntry)
    {
        image = null;
        listEntry = null;
        if (!LeafFormats.TryInspectLff(data, out _))
            return false;
        image = LeafFormats.DecodeLff(data);
        listEntry = new ListEntry("lff", ChangeExtensionToPng(diskName));
        return true;
    }

    static bool TryConvertLfb(string archiveName, string diskName, byte[] data, out Bitmap? image, out ListEntry? listEntry)
    {
        image = null;
        listEntry = null;
        if (!LeafFormats.TryInspectLfb(data, out LfbMeta meta))
            return false;
        image = LeafFormats.DecodeLfb(data);
        listEntry = new ListEntry("lfb", ChangeExtensionToPng(diskName));
        if (meta.Kind == "custom-indexed-alpha")
            listEntry["t"] = "1";
        return true;
    }

    static bool TryConvertLcf(string archiveName, string diskName, byte[] data, out Bitmap? image, out ListEntry? listEntry)
    {
        image = null;
        listEntry = null;
        if (!LeafFormats.TryInspectLcf(data, out LcfMeta meta))
            return false;
        image = LeafFormats.DecodeLcf(data);
        listEntry = new ListEntry("lcf", ChangeExtensionToPng(diskName));
        listEntry["ox"] = meta.OffsetX.ToString();
        listEntry["oy"] = meta.OffsetY.ToString();
        if (meta.TailBytes.Length != 0)
            listEntry["tail"] = Convert.ToHexString(meta.TailBytes);
        return true;
    }

    static byte[] EncodeSpecialImage(ListEntry item, string pngPath)
    {
        using var bitmap = new Bitmap(pngPath);
        return item.Section switch
        {
            "lff" => LeafFormats.EncodeLff(item, bitmap),
            "lfb" => LeafFormats.EncodeLfb(item, bitmap),
            "lcf" => LeafFormats.EncodeLcf(item, bitmap),
            _ => throw new InvalidOperationException($"unsupported list.xml section: {item.Section}")
        };
    }

    static void AddPackedEntry(Dictionary<string, byte[]> entries, string name, byte[] data)
    {
        string flatName = Path.GetFileName(name);
        LeafPak.EncodeName(flatName, ShiftJis);
        if (!entries.TryAdd(flatName, data))
            throw new InvalidOperationException($"duplicate output entry: {flatName}");
    }

    static string FlattenEntryName(string name) => name.Replace('\\', '_').Replace('/', '_');
    static string ChangeExtensionToPng(string name) => Path.ChangeExtension(name, ".png") ?? $"{name}.png";
    static string ChangeExtensionToOriginal(string pngName, string section) => Path.ChangeExtension(pngName, "." + section.ToUpperInvariant()) ?? (pngName + "." + section.ToUpperInvariant());
}
