namespace ToHeartPS2;

internal static class App
{
    static int GetWorkerCount()
    {
        int cpu = Environment.ProcessorCount;
        return Math.Clamp(cpu - 1, 2, 12);
    }

    public static void Unpack(string elfPath, string sfsPath, string outputDir)
    {
        Directory.CreateDirectory(outputDir);
        Config config = Config.Load();
        string archiveName = Path.GetFileName(sfsPath);

        if (string.Equals(archiveName, "TOHSOUND.SFS", StringComparison.OrdinalIgnoreCase))
        {
            var items = new List<ListEntry>();
            foreach ((uint index, byte[] data) in SfsArchive.ReadSoundEntries(sfsPath))
            {
                string rel = SfsArchive.GetSoundFileName(data, index);
                string fullPath = Path.Combine(outputDir, rel);
                Directory.CreateDirectory(Path.GetDirectoryName(fullPath)!);
                File.WriteAllBytes(fullPath, data);
                items.Add(new ListEntry(index, rel, data.Length));
                Console.WriteLine(rel);
            }

            ListXml.Save(Path.Combine(outputDir, "list.xml"), items);
            return;
        }

        byte[] elfBytes = File.ReadAllBytes(elfPath);
        IReadOnlyList<ElfNamedEntry> names = ElfReader.ReadNamedEntries(elfBytes, config);
        IReadOnlyDictionary<string, ImageMetaEntry> charMeta = ElfReader.ReadImageMetaTable(elfBytes, config.CharMetaAddr, config.CharMetaCountAddr);
        IReadOnlyDictionary<string, ImageMetaEntry> etcMeta = ElfReader.ReadImageMetaTable(elfBytes, config.EtcMetaAddr, config.EtcMetaCountAddr);
        IReadOnlyList<KnownSliceTable> knownSliceTables = SliceTables.ReadKnownTables(elfBytes, config);
        IReadOnlyDictionary<string, IReadOnlyList<DrawSliceSpec>> sliceSpecMap = SliceTables.BuildSpecMap(knownSliceTables);
        bool numberedOnly = string.Equals(archiveName, "TOHDATA2.SFS", StringComparison.OrdinalIgnoreCase)
            || SfsArchive.LooksLikeData2(sfsPath, elfBytes, config, names);
        int workerCount = GetWorkerCount();

        var list = new System.Collections.Concurrent.ConcurrentBag<ListEntry>();
        Parallel.ForEach(
            names,
            new ParallelOptions { MaxDegreeOfParallelism = workerCount },
            item =>
        {
            SfsIndexedEntry? entry = SfsArchive.TryReadDataEntry(sfsPath, elfBytes, config, item, numberedOnly);
            if (entry is null)
                return;

            string rel = entry.Path.Replace('\\', '/');
            if (Transformers.CanTransform("TPP") && TppCodec.IsTppPath(rel))
            {
                try
                {
                    TppCodec.DecodeResult decoded = TppCodec.Decode(rel, entry.Data, charMeta, etcMeta, sliceSpecMap);
                    string pngRel = Path.ChangeExtension(rel, ".png")!.Replace('\\', '/');
                    string pngPath = Path.Combine(outputDir, pngRel);
                    Directory.CreateDirectory(Path.GetDirectoryName(pngPath)!);
                    File.WriteAllBytes(pngPath, decoded.PngBytes);

                    var listEntry = new ListEntry(entry.Index, pngRel, decoded.PngBytes.Length);
                    string defaultTppName = TppNameCodec.InferTppName(pngRel);
                    if (!string.Equals(decoded.Meta.Name, defaultTppName, StringComparison.OrdinalIgnoreCase))
                        listEntry.Attributes["tpp_name"] = decoded.Meta.Name;
                    if (decoded.Meta.HeaderReserved != 0)
                        listEntry.Attributes["tpp_u0c"] = $"0x{decoded.Meta.HeaderReserved:X}";
                    string[] partNames = decoded.Meta.Parts.Select(static p => p.PartName).ToArray();
                    if (!TppNameCodec.IsDefaultSequence(rel, decoded.Meta.Name, partNames))
                    {
                        if (TppNameCodec.TryEncode(partNames, out string nameMode, out string nameValue))
                        {
                            listEntry.Attributes["part_name_mode"] = nameMode;
                            listEntry.Attributes["part_name_value"] = nameValue;
                        }
                        else
                        {
                            listEntry.Attributes["part_names"] = string.Join(";", partNames);
                        }
                    }

                    uint[] partFlagA = decoded.Meta.Parts.Select(static p => p.PartFlagA).ToArray();
                    uint[] partFlagB = decoded.Meta.Parts.Select(static p => p.PartFlagB).ToArray();
                    ushort[] partReserved = decoded.Meta.Parts.Select(static p => p.PartReserved).ToArray();
                    listEntry.Attributes["part_flag_a"] = partFlagA.All(v => v == partFlagA[0])
                        ? $"0x{partFlagA[0]:X}"
                        : string.Join(";", partFlagA.Select(static v => $"0x{v:X}"));
                    listEntry.Attributes["part_flag_b"] = partFlagB.All(v => v == partFlagB[0])
                        ? $"0x{partFlagB[0]:X}"
                        : string.Join(";", partFlagB.Select(static v => $"0x{v:X}"));
                    if (partReserved.Any(static v => v != 0))
                    {
                        listEntry.Attributes["part_u14"] = partReserved.All(v => v == partReserved[0])
                            ? $"0x{partReserved[0]:X}"
                            : string.Join(";", partReserved.Select(static v => $"0x{v:X}"));
                    }
                    listEntry.Attributes["part_meta"] = string.Join(";", decoded.Meta.Parts.Select(static p =>
                        $"{p.X},{p.Y},{p.Packed:X},{TppHeaderCatalog.EncodePalette(p.PaletteHeaderHex)},{TppHeaderCatalog.EncodeImage(p.ImageHeaderHex)}"));
                    listEntry.Attributes["part_data"] = string.Join(";", decoded.Meta.Parts.Select(static p =>
                        $"{p.PaletteDataHex},{p.ImageDataHex}"));
                    list.Add(listEntry);
                    Console.WriteLine($"{rel} -> {pngRel}");
                    return;
                }
                catch (Exception ex)
                {
                    Console.Error.WriteLine($"warn: tpp decode fallback for {rel}: {ex.Message}");
                }
            }

            string fullPath = Path.Combine(outputDir, rel);
            Directory.CreateDirectory(Path.GetDirectoryName(fullPath)!);
            File.WriteAllBytes(fullPath, entry.Data);
            list.Add(new ListEntry(entry.Index, rel, entry.Data.Length));
            Console.WriteLine(rel);
        });

        ListXml.Save(Path.Combine(outputDir, "list.xml"), list.OrderBy(static item => item.Index).ToList());
    }

    public static void Pack(string elfPath, string inputDir, string sfsPath, string outputElfPath)
    {
        Config config = Config.Load();
        string archiveName = Path.GetFileName(sfsPath);

        if (string.Equals(archiveName, "TOHSOUND.SFS", StringComparison.OrdinalIgnoreCase))
        {
            IReadOnlyList<string> order = ListXml.LoadOrderOrScan(inputDir);
            var files = order.Select(name =>
            {
                string path = Path.Combine(inputDir, name);
                if (!File.Exists(path))
                    throw new FileNotFoundException("missing input file: " + path);
                return new NamedData(name, File.ReadAllBytes(path));
            }).ToList();

            Directory.CreateDirectory(Path.GetDirectoryName(sfsPath) ?? inputDir);
            File.WriteAllBytes(sfsPath, SfsArchive.BuildSoundArchive(files));
            return;
        }

        byte[] elfBytes = File.ReadAllBytes(elfPath);
        IReadOnlyList<ElfNamedEntry> names = ElfReader.ReadNamedEntries(elfBytes, config);
        bool numberedOnly = string.Equals(archiveName, "TOHDATA2.SFS", StringComparison.OrdinalIgnoreCase)
            || SfsArchive.IsNumberedBinDirectory(inputDir);
        IReadOnlyDictionary<string, TppMeta> pngMeta = ListXml.LoadTppMeta(inputDir);
        int workerCount = GetWorkerCount();
        string stageDir = Path.Combine(Path.GetTempPath(), "ToHeartPS2_stage_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(stageDir);
        var passthroughPaths = new System.Collections.Concurrent.ConcurrentDictionary<uint, string>();
        var stagedPaths = new System.Collections.Concurrent.ConcurrentDictionary<uint, string>();

        try
        {
            Parallel.ForEach(
                names,
                new ParallelOptions { MaxDegreeOfParallelism = workerCount },
                item =>
            {
                string rel = numberedOnly ? $"{item.Index:0000}.bin" : item.Path.Replace('/', Path.DirectorySeparatorChar);
                string fullPath = Path.Combine(inputDir, rel);
                byte[]? data = null;
                if (Transformers.CanTransform("TPP") && TppCodec.IsTppPath(rel) && !File.Exists(fullPath))
                {
                    string pngRel = Path.ChangeExtension(rel, ".png")!.Replace('\\', '/');
                    string pngPath = Path.Combine(inputDir, pngRel.Replace('/', Path.DirectorySeparatorChar));
                    if (File.Exists(pngPath) && pngMeta.TryGetValue(pngRel, out TppMeta? meta))
                    {
                        TppCodec.EncodeResult encoded = TppCodec.EncodeFromPng(pngPath, meta);
                        data = encoded.Data;
                        string suffix = encoded.UsedQuantization
                            ? $" (>{encoded.PaletteLimit})"
                            : "";
                        Console.WriteLine($"{pngRel} -> {rel}{suffix}");
                        string stagePath = Path.Combine(stageDir, item.Index.ToString("D8") + ".bin");
                        File.WriteAllBytes(stagePath, data);
                        stagedPaths[item.Index] = stagePath;
                        return;
                    }
                }

                if (data is null)
                {
                    if (!File.Exists(fullPath))
                    {
                        if (numberedOnly)
                            return;
                        throw new FileNotFoundException("missing input file: " + fullPath);
                    }

                    passthroughPaths[item.Index] = fullPath;
                    Console.WriteLine(rel.Replace('\\', '/'));
                }
            });

            byte[]? LoadPackedData(ElfNamedEntry item)
            {
                if (stagedPaths.TryGetValue(item.Index, out string? stagePath) && File.Exists(stagePath))
                    return File.ReadAllBytes(stagePath);

                if (!passthroughPaths.TryGetValue(item.Index, out string? sourcePath) || !File.Exists(sourcePath))
                    return null;

                byte[] data = File.ReadAllBytes(sourcePath);
                if (Transformers.CanTransform("TPP") && TppCodec.IsTppPath(item.Path))
                    data = TppCodec.CompressRaw(data);
                return data;
            }

            Directory.CreateDirectory(Path.GetDirectoryName(sfsPath) ?? inputDir);
            byte[] outElf = SfsArchive.BuildDataArchive(sfsPath, elfBytes, config, names, LoadPackedData, numberedOnly);

            string elfOutPath = Path.GetFullPath(outputElfPath);
            Directory.CreateDirectory(Path.GetDirectoryName(elfOutPath) ?? inputDir);
            File.WriteAllBytes(elfOutPath, outElf);
        }
        finally
        {
            if (Directory.Exists(stageDir))
                Directory.Delete(stageDir, recursive: true);
        }
    }
}
