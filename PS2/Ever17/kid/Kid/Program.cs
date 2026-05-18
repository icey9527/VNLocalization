using System.Collections.Concurrent;
using System.Xml.Linq;
using AFSLib;
using Kid.Script;

if (args.Length < 2) { Usage(); return 1; }

string cmd = args[0];
var pos = args[1..].ToList();

bool noCompress = false;
for (int i = pos.Count - 1; i >= 0; i--)
{
    if (pos[i] == "-x") { noCompress = true; pos.RemoveAt(i); }
}

try
{
    switch (cmd)
    {
        case "u" when pos.Count >= 2: Unpack(pos[0], pos[1]); break;
        case "p" when pos.Count >= 2: Pack(pos[0], pos[1]); break;
        case "d" when pos.Count >= 2: DecompressFile(pos[0], pos[1]); break;
        case "c" when pos.Count >= 2: CompressFile(pos[0], pos[1]); break;
        default: Usage(); return 1;
    }
}
catch (Exception ex) { Console.Error.WriteLine($"error: {ex.Message}"); return 1; }
return 0;

void Usage()
{
    Console.Error.WriteLine("kid u [-x] <afs> <dir>   unpack AFS");
    Console.Error.WriteLine("kid p [-x] <dir> <afs>   pack AFS");
    Console.Error.WriteLine("kid d <input> <output>   decompress single file");
    Console.Error.WriteLine("kid c <input> <output>   compress single file");
    Console.Error.WriteLine("  -x   no LZSS compression");
}

void Unpack(string afsPath, string outDir)
{
    Directory.CreateDirectory(outDir);
    using var afs = new AFS(afsPath);
    var xmlEntries = new List<XElement>();

    var items = new List<(string rawName, string stem, byte[] data, bool compressed)>();
    foreach (var e in afs.Entries)
    {
        var de = e as DataEntry;
        if (de == null) continue;
        string rawName = de.Name ?? "";
        string stem = Path.GetFileNameWithoutExtension(rawName);
        byte[] raw;
        using (var s = de.GetStream())
        {
            if (s == null) continue;
            var ms = new MemoryStream();
            s.CopyTo(ms);
            raw = ms.ToArray();
        }
        if (raw.Length == 0) continue;

        bool compressed = false;
        byte[] data = raw;
        if (IsCompressed(raw))
        {
            uint hdr = BitConverter.ToUInt32(raw, 0);
            if (hdr > 0 && hdr < 0x1000000)
                try { data = BipCoder.Decode(raw.AsSpan(4).ToArray(), (int)hdr); compressed = true; }
                catch { data = raw; }
        }
        items.Add((rawName, stem, data, compressed));
    }

    var results = new ConcurrentBag<(int idx, XElement xml)>();
    var printLock = new object();
    Parallel.ForEach(items, (it, _, i) =>
    {
        string rawName = it.rawName, stem = it.stem;
        byte[] data = it.data;
        bool compressed = it.compressed;

        var container = Tim2Png.ParseContainer(data);
        bool singleTim2 = container == null && Tim2Png.IsTim2(data);
        if (singleTim2)
            container = new List<(int, int)> { (0, data.Length) };

        if (container != null && container.Count > 0)
        {
            string entryExt = Path.GetExtension(rawName).TrimStart('.').ToUpperInvariant();
            var infos = Tim2Png.InspectContainer(data) ?? new List<Tim2Png.Tim2Info>();
            var tim2Meta = Tim2Png.InspectContainerMetadata(data);
            for (int ti = 0; ti < container.Count; ti++)
            {
                var (off, len) = container[ti];
                bool isT2p = rawName.EndsWith(".T2P", StringComparison.OrdinalIgnoreCase)
                    || rawName.EndsWith(".SPC", StringComparison.OrdinalIgnoreCase);
                string suffix = isT2p ? ".t2p" : "";
                if (container.Count > 1) suffix += $".{ti}";
                string outPath = Path.Combine(outDir, stem + suffix + ".png");
                try
                {
                    byte[] png = Tim2Png.ConvertToPng(data, off, len);
                    File.WriteAllBytes(outPath, png);
                    lock (printLock) Console.WriteLine($"  {rawName} -> {stem}{suffix}.png");
                }
                catch (Exception ex)
                {
                    lock (printLock) Console.Error.WriteLine($"  {rawName}{suffix}: TIM2->PNG failed ({ex.Message})");
                }
            }
            var tim2Entry = new XElement("entry",
                new XAttribute("name", stem),
                new XAttribute("comp", compressed ? "1" : "0"),
                new XAttribute("type", "tim2"),
                new XAttribute("count", container.Count),
                new XAttribute("bpp", GetTim2BppValue(infos)),
                new XAttribute("ext", entryExt));
            if (tim2Meta != null)
                AppendTim2Metadata(tim2Entry, tim2Meta.Value);
            results.Add(((int)i, tim2Entry));
        }
        else if (ChrBipLayout.IsLayout(data))
        {
            try
            {
                byte[] png = ChrBipLayout.ConvertToPng(data);
                File.WriteAllBytes(Path.Combine(outDir, stem + ".png"), png);
                var chrMeta = ChrBipLayout.InspectMetadata(data);
                lock (printLock) Console.WriteLine($"  {rawName} -> {stem}.png");
                var chrEntry = new XElement("entry",
                    new XAttribute("name", stem),
                    new XAttribute("comp", compressed ? "1" : "0"),
                    new XAttribute("type", "chr"),
                    new XAttribute("ext", "BIP"));
                AppendChrMetadata(chrEntry, chrMeta);
                results.Add(((int)i, chrEntry));
            }
            catch (Exception ex)
            {
                lock (printLock) Console.Error.WriteLine($"  {rawName}: layout->PNG failed ({ex.Message})");
                WriteResult(i, stem, data, compressed);
            }
        }
        else if (RawBg.IsRawBg(data))
        {
            try
            {
                byte[] png = RawBg.ConvertToPng(data);
                File.WriteAllBytes(Path.Combine(outDir, stem + ".png"), png);
                var bgMeta = RawBg.InspectRebuildMetadata(data);
                lock (printLock) Console.WriteLine($"  {rawName} -> {stem}.png");
                var bgEntry = new XElement("entry",
                    new XAttribute("name", stem),
                    new XAttribute("comp", compressed ? "1" : "0"),
                    new XAttribute("type", "bg"),
                    new XAttribute("ext", "BIP"));
                AppendBgMetadata(bgEntry, bgMeta);
                results.Add(((int)i, bgEntry));
            }
            catch (Exception ex)
            {
                lock (printLock) Console.Error.WriteLine($"  {rawName}: bip->PNG failed ({ex.Message})");
                WriteResult(i, stem, data, compressed);
            }
        }
        else
        {
            WriteResult(i, stem, data, compressed);
        }

        void WriteResult(long idx, string name, byte[] dat, bool cmp)
        {
            string outExt = Path.GetExtension(rawName);
            if (string.IsNullOrEmpty(outExt))
                outExt = ".BIP";
            File.WriteAllBytes(Path.Combine(outDir, name + outExt), dat);
            lock (printLock) Console.WriteLine($"  {rawName} -> {name}{outExt}");
            results.Add(((int)idx, new XElement("entry",
                new XAttribute("name", name),
                new XAttribute("comp", cmp ? "1" : "0"),
                new XAttribute("type", "data"),
                new XAttribute("ext", outExt.TrimStart('.').ToUpperInvariant()))));
        }
    });

    xmlEntries = results.OrderBy(r => r.idx).Select(r => r.xml).ToList();
    new XDocument(new XElement("afs", xmlEntries.ToArray())).Save(Path.Combine(outDir, "list.xml"));
    Console.WriteLine($"extracted {xmlEntries.Count} entries -> {outDir}");

}

string GetTim2BppValue(List<Tim2Png.Tim2Info> infos)
{
    if (infos.Count == 0)
        return "unknown";

    int first = infos[0].Bpp;
    if (infos.All(x => x.Bpp == first))
        return first.ToString();

    return string.Join(",", infos.Select(x => x.Bpp));
}

void Pack(string inDir, string afsPath)
{
    string? outParent = Path.GetDirectoryName(Path.GetFullPath(afsPath));
    if (!string.IsNullOrEmpty(outParent))
        Directory.CreateDirectory(outParent);

    string xmlPath = Path.Combine(inDir, "list.xml");
    using var afs = new AFS();
    var ownedStreams = new List<MemoryStream>();
    try
    {
        string? sourceAfsPath = FindOriginalAfsForDirectory(inDir);
        if (sourceAfsPath != null)
        {
            using var srcAfs = new AFS(sourceAfsPath);
            afs.HeaderMagicType = srcAfs.HeaderMagicType;
            afs.AttributesInfoType = srcAfs.AttributesInfoType;
            afs.EntryBlockAlignment = srcAfs.EntryBlockAlignment;
        }

        if (File.Exists(xmlPath))
        {
            var entries = XDocument.Load(xmlPath).Root!.Elements("entry").ToList();
            foreach (var xe in entries)
            {
                string name = xe.Attribute("name")?.Value ?? "";
                string type = xe.Attribute("type")?.Value ?? "data";
                bool comp = (xe.Attribute("comp")?.Value ?? "0") == "1";
                string entryExt = xe.Attribute("ext")?.Value ?? "BIP";

                if (type == "bg")
                {
                    string pngPath = Path.Combine(inDir, name + ".png");
                    var bgMeta = ReadBgMetadata(xe);
                    if (bgMeta != null && File.Exists(pngPath))
                    {
                        byte[] png = File.ReadAllBytes(pngPath);
                        byte[] data = RawBg.BuildFromPng(png, bgMeta.Value);
                        if (comp && !noCompress)
                            data = BipCoder.EncodeBip(data);
                        AddOwnedEntry(data, name + "." + entryExt);
                        Console.WriteLine($"  {name}.png -> {name}.{entryExt}");
                    }
                    else
                    {
                        Console.Error.WriteLine($"  {name}: bg metadata or .png not found");
                        afs.AddNullEntry();
                    }
                }
                else if (type == "chr")
                {
                    string pngPath = Path.Combine(inDir, name + ".png");
                    var chrMeta = ReadChrMetadata(xe);
                    if (chrMeta != null && File.Exists(pngPath))
                    {
                        byte[] png = File.ReadAllBytes(pngPath);
                        byte[] data = ChrBipLayout.BuildFromPng(png, chrMeta.Value);
                        if (comp && !noCompress)
                            data = BipCoder.EncodeBip(data);
                        AddOwnedEntry(data, name + "." + entryExt);
                        Console.WriteLine($"  {name}.png -> {name}.{entryExt}");
                    }
                    else
                    {
                        Console.Error.WriteLine($"  {name}: chr metadata or .png not found");
                        afs.AddNullEntry();
                    }
                }
                else if (type == "tim2")
                {
                    int count = int.TryParse(xe.Attribute("count")?.Value, out int parsedCount) ? parsedCount : 0;
                    var tim2Meta = ReadTim2Metadata(xe);
                    if (tim2Meta != null)
                    {
                        byte[] data;
                        if (count <= 1)
                        {
                            string pngPath = Path.Combine(inDir, name + ".t2p.png");
                            if (!File.Exists(pngPath))
                                pngPath = Path.Combine(inDir, name + ".png");
                            if (!File.Exists(pngPath))
                            {
                                Console.Error.WriteLine($"  {name}: .png not found");
                                afs.AddNullEntry();
                                continue;
                            }

                            byte[] png = File.ReadAllBytes(pngPath);
                            data = Tim2Png.BuildFromPng(png, tim2Meta.Value.Images[0]);
                            Console.WriteLine($"  {name}.png -> {name}.{entryExt}");
                        }
                        else
                        {
                            data = RebuildTim2ContainerFromPngs(inDir, name, tim2Meta.Value, entryExt);
                            Console.WriteLine($"  {name}.*.png -> {name}.{entryExt}");
                        }

                        if (comp && !noCompress)
                            data = BipCoder.EncodeBip(data);
                        AddOwnedEntry(data, name + "." + entryExt);
                    }
                    else
                    {
                        Console.Error.WriteLine($"  {name}: tim2 metadata not found");
                        afs.AddNullEntry();
                    }
                }
                else
                {
                    var matches = Directory.GetFiles(inDir, name + ".*");
                    string? file = matches.FirstOrDefault(f => f.EndsWith(".BIP", StringComparison.OrdinalIgnoreCase))
                        ?? matches.FirstOrDefault();
                    if (file != null && File.Exists(file))
                    {
                        byte[] data = File.ReadAllBytes(file);
                        if (comp && !noCompress)
                            data = BipCoder.EncodeBip(data);
                        string ext = Path.GetExtension(file);
                        AddOwnedEntry(data, name + ext);
                        Console.WriteLine($"  {Path.GetFileName(file)} -> AFS");
                    }
                    else
                    {
                        Console.Error.WriteLine($"  {name}: file not found");
                        afs.AddNullEntry();
                    }
                }
            }
        }
        else
        {
            foreach (var f in Directory.GetFiles(inDir))
            {
                string n = Path.GetFileName(f);
                if (n == "list.xml") continue;
                byte[] data = File.ReadAllBytes(f);
                if (!noCompress)
                    data = BipCoder.EncodeBip(data);
                AddOwnedEntry(data, n);
                Console.WriteLine($"  {n} -> AFS");
            }
        }

        afs.SaveToFile(afsPath);
        Console.WriteLine($"packed -> {afsPath}");
    }
    finally
    {
        foreach (var s in ownedStreams)
            s.Dispose();
    }

    void AddOwnedEntry(byte[] data, string entryName)
    {
        var ms = new MemoryStream(data, writable: false);
        ownedStreams.Add(ms);
        afs.AddEntryFromStream(ms, entryName);
    }
}

byte[] RebuildTim2ContainerFromPngs(string inDir, string name, Tim2Png.Tim2ContainerMetadata meta, string entryExt)
{
    bool isT2p = entryExt.Equals("T2P", StringComparison.OrdinalIgnoreCase)
        || entryExt.Equals("SPC", StringComparison.OrdinalIgnoreCase);
    var pngs = new List<byte[]>(meta.Images.Count);

    for (int i = 0; i < meta.Images.Count; i++)
    {
        string suffix = isT2p ? ".t2p" : "";
        if (meta.Images.Count > 1)
            suffix += $".{i}";
        string pngPath = Path.Combine(inDir, name + suffix + ".png");
        if (!File.Exists(pngPath))
            throw new FileNotFoundException($"{name}: missing PNG for image {i}", pngPath);
        pngs.Add(File.ReadAllBytes(pngPath));
    }

    return Tim2Png.BuildContainerFromPngs(pngs, meta);
}

void AppendTim2Metadata(XElement entry, Tim2Png.Tim2ContainerMetadata meta)
{
    entry.Add(new XAttribute("tim2HeaderSize", meta.HeaderSize));
    for (int i = 0; i < meta.Images.Count; i++)
    {
        var image = meta.Images[i];
        entry.Add(new XElement("tim2",
            new XAttribute("index", i),
            new XAttribute("len", meta.SegmentLengths[i]),
            new XAttribute("img", image.PhImg),
            new XAttribute("mip", image.MipmapCount),
            new XAttribute("imgType", image.PhImgType),
            new XAttribute("w", image.Width),
            new XAttribute("h", image.Height),
            new XAttribute("tex0", $"0x{image.GsTex0:X16}")));
    }
}

void AppendChrMetadata(XElement entry, ChrBipLayout.LayoutMetadata meta)
{
    entry.Add(
        new XAttribute("headerKind", meta.HeaderKind),
        new XAttribute("headerWords", meta.HeaderWords),
        new XAttribute("entryOff", meta.EntryOffset),
        new XAttribute("atlasOff", meta.AtlasOffset),
        new XAttribute("h08", $"0x{meta.HeaderValue08:X8}"),
        new XAttribute("fileSize", meta.FileSize),
        new XAttribute("entry08", $"0x{meta.EntryValue08:X8}"),
        new XAttribute("groups", meta.GroupCount));
    for (int i = 0; i < meta.Groups.Count; i++)
    {
        var g = meta.Groups[i];
        entry.Add(new XElement("grp",
            new XAttribute("i", i),
            new XAttribute("tile", g.Tile),
            new XAttribute("x", g.DstXCells),
            new XAttribute("y", g.DstYCells),
            new XAttribute("w", g.Cols),
            new XAttribute("h", g.Rows)));
    }
}

void AppendBgMetadata(XElement entry, RawBg.RawBgRebuildMetadata meta)
{
    entry.Add(
        new XAttribute("bgType", meta.Type),
        new XAttribute("w", meta.Width),
        new XAttribute("h", meta.Height),
        new XAttribute("pixelOff", meta.PixelOffset),
        new XAttribute("headerHex", meta.HeaderHex),
        new XAttribute("headerWords", meta.HeaderWords),
        new XAttribute("pixelWord", meta.PixelDataOffsetWord),
        new XAttribute("encBytes", meta.EncodedPixelBytes));

    if (meta.Type >= 6)
    {
        entry.Add(
            new XAttribute("h0C", $"0x{meta.Header0C:X8}"),
            new XAttribute("h14", $"0x{meta.Header14:X8}"),
            new XAttribute("h18", $"0x{meta.Header18:X8}"),
            new XAttribute("h90", $"0x{meta.Header90:X8}"),
            new XAttribute("h94", $"0x{meta.Header94:X8}"),
            new XAttribute("h98", $"0x{meta.Header98:X8}"),
            new XAttribute("h9C", $"0x{meta.Header9C:X8}"),
            new XAttribute("hA0", $"0x{meta.HeaderA0:X8}"),
            new XAttribute("hA4", $"0x{meta.HeaderA4:X8}"));

        for (int i = 0; i < meta.Blocks.Count; i++)
        {
            var b = meta.Blocks[i];
            entry.Add(new XElement("blk",
                new XAttribute("i", i),
                new XAttribute("x", b.BaseX),
                new XAttribute("y", b.BaseY),
                new XAttribute("tile", b.Tile),
                new XAttribute("w", b.Cols),
                new XAttribute("h", b.Rows)));
        }
    }
}

Tim2Png.Tim2ContainerMetadata? ReadTim2Metadata(XElement entry)
{
    var nodes = entry.Elements("tim2").OrderBy(x => ParseInt(x.Attribute("index")?.Value)).ToList();
    if (nodes.Count == 0)
        return null;

    int count = ParseInt(entry.Attribute("count")?.Value);
    int headerSize = ParseInt(entry.Attribute("tim2HeaderSize")?.Value);
    var lengths = new List<int>(nodes.Count);
    var images = new List<Tim2Png.Tim2Metadata>(nodes.Count);
    foreach (var node in nodes)
    {
        lengths.Add(ParseInt(node.Attribute("len")?.Value));
        images.Add(new Tim2Png.Tim2Metadata(
            4,
            0,
            0,
            0,
            16 + 48 + ParseInt(node.Attribute("img")?.Value),
            0,
            ParseInt(node.Attribute("img")?.Value),
            48,
            0,
            0,
            ParseInt(node.Attribute("mip")?.Value),
            0,
            ParseInt(node.Attribute("imgType")?.Value),
            ParseInt(node.Attribute("w")?.Value),
            ParseInt(node.Attribute("h")?.Value),
            ParseULong(node.Attribute("tex0")?.Value),
            0,
            0,
            0));
    }

    return new Tim2Png.Tim2ContainerMetadata(count, headerSize, lengths, images);
}

ChrBipLayout.RebuildMetadata? ReadChrMetadata(XElement entry)
{
    var groups = entry.Elements("grp")
        .OrderBy(x => ParseInt(x.Attribute("i")?.Value))
        .Select(x => new ChrBipLayout.GroupMetadata(
            2,
            ParseInt(x.Attribute("tile")?.Value),
            ParseInt(x.Attribute("x")?.Value),
            ParseInt(x.Attribute("y")?.Value),
            ParseInt(x.Attribute("w")?.Value),
            ParseInt(x.Attribute("h")?.Value)))
        .ToList();

    if (groups.Count == 0)
        return null;

    int entryOff = ParseInt(entry.Attribute("entryOff")?.Value);
    int headerWords = ParseInt(entry.Attribute("headerWords")?.Value);
    int headerKind = ParseInt(entry.Attribute("headerKind")?.Value);
    int atlasOff = ParseInt(entry.Attribute("atlasOff")?.Value);
    int h08 = ParseInt(entry.Attribute("h08")?.Value);
    int fileSize = ParseInt(entry.Attribute("fileSize")?.Value);
    int entry08 = ParseInt(entry.Attribute("entry08")?.Value);

    return new ChrBipLayout.RebuildMetadata(
        headerKind,
        headerWords,
        entryOff,
        atlasOff,
        h08,
        fileSize,
        entry08,
        groups);
}

RawBg.RawBgRebuildMetadata? ReadBgMetadata(XElement entry)
{
    int type = ParseInt(entry.Attribute("bgType")?.Value);
    int w = ParseInt(entry.Attribute("w")?.Value);
    int h = ParseInt(entry.Attribute("h")?.Value);
    int pixelOff = ParseInt(entry.Attribute("pixelOff")?.Value);
    int headerWords = ParseInt(entry.Attribute("headerWords")?.Value);
    int pixelWord = ParseInt(entry.Attribute("pixelWord")?.Value);
    int encBytes = ParseInt(entry.Attribute("encBytes")?.Value);
    string headerHex = entry.Attribute("headerHex")?.Value ?? "";
    if (type == 0 || w == 0 || h == 0 || pixelOff == 0 || encBytes == 0 || string.IsNullOrEmpty(headerHex))
        return null;

    var blocks = entry.Elements("blk")
        .OrderBy(x => ParseInt(x.Attribute("i")?.Value))
        .Select(x => new RawBg.BgBlock(
            ParseInt(x.Attribute("x")?.Value),
            ParseInt(x.Attribute("y")?.Value),
            ParseInt(x.Attribute("tile")?.Value),
            ParseInt(x.Attribute("w")?.Value),
            ParseInt(x.Attribute("h")?.Value)))
        .ToList();

    return new RawBg.RawBgRebuildMetadata(
        type,
        w,
        h,
        pixelOff,
        headerHex,
        headerWords,
        pixelWord,
        encBytes,
        ParseInt(entry.Attribute("h0C")?.Value),
        ParseInt(entry.Attribute("h14")?.Value),
        ParseInt(entry.Attribute("h18")?.Value),
        ParseInt(entry.Attribute("h90")?.Value),
        ParseInt(entry.Attribute("h94")?.Value),
        ParseInt(entry.Attribute("h98")?.Value),
        ParseInt(entry.Attribute("h9C")?.Value),
        ParseInt(entry.Attribute("hA0")?.Value),
        ParseInt(entry.Attribute("hA4")?.Value),
        blocks);
}

static int ParseInt(string? s)
{
    if (string.IsNullOrWhiteSpace(s))
        return 0;
    if (s.StartsWith("0x", StringComparison.OrdinalIgnoreCase))
        return Convert.ToInt32(s, 16);
    return int.Parse(s);
}

static ulong ParseULong(string? s)
{
    if (string.IsNullOrWhiteSpace(s))
        return 0;
    if (s.StartsWith("0x", StringComparison.OrdinalIgnoreCase))
        return Convert.ToUInt64(s[2..], 16);
    return ulong.Parse(s);
}

bool IsCompressed(byte[] d) =>
    d.Length >= 4 && BitConverter.ToUInt32(d, 0) > d.Length;

void DecompressFile(string inputPath, string outputPath)
{
    string? outParent = Path.GetDirectoryName(Path.GetFullPath(outputPath));
    if (!string.IsNullOrEmpty(outParent))
        Directory.CreateDirectory(outParent);

    byte[] raw = File.ReadAllBytes(inputPath);
    if (raw.Length < 5)
        throw new InvalidDataException("input is too small");

    uint outSize = BitConverter.ToUInt32(raw, 0);
    if (outSize == 0 || outSize >= 0x1000000)
        throw new InvalidDataException($"invalid output size in header: {outSize}");

    byte[] data = BipCoder.Decode(raw.AsSpan(4).ToArray(), (int)outSize);
    File.WriteAllBytes(outputPath, data);
    Console.WriteLine($"decompressed -> {outputPath}");
}

void CompressFile(string inputPath, string outputPath)
{
    string? outParent = Path.GetDirectoryName(Path.GetFullPath(outputPath));
    if (!string.IsNullOrEmpty(outParent))
        Directory.CreateDirectory(outParent);

    byte[] raw = File.ReadAllBytes(inputPath);
    byte[] data = BipCoder.EncodeBip(raw);
    File.WriteAllBytes(outputPath, data);
    Console.WriteLine($"compressed -> {outputPath}");
}

string? FindOriginalAfsForDirectory(string inDir)
{
    string full = Path.GetFullPath(inDir).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
    var dir = new DirectoryInfo(full);
    while (dir != null)
    {
        if (!string.IsNullOrEmpty(dir.Name))
        {
            string candidate = Path.Combine(Environment.CurrentDirectory, "input_afs", dir.Name + ".afs");
            if (File.Exists(candidate))
                return candidate;
        }
        dir = dir.Parent;
    }
    return null;
}
