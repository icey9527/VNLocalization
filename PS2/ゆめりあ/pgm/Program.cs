using System.Buffers.Binary;
using System.Security.Cryptography;
using System.Xml.Linq;
using SixLabors.ImageSharp;
using SixLabors.ImageSharp.PixelFormats;
using SixLabors.ImageSharp.Processing.Processors.Quantization;

// This workflow intentionally handles only PSMT8 images.
static class Program
{
    static readonly byte[] Sig = Convert.FromHexString("03000000000000100e000000");
    sealed record Header(int Width, int Height, int Cbp, int Psm, int Tbw);
    sealed record Chunk(int Offset, int End, int X, int Y, int Width, int Height)
    {
        public int Payload => Offset + 0x50;
    }

    static ushort U16(byte[] d, int o) => BinaryPrimitives.ReadUInt16LittleEndian(d.AsSpan(o));
    static uint U32(byte[] d, int o) => BinaryPrimitives.ReadUInt32LittleEndian(d.AsSpan(o));
    static Header ReadHeader(byte[] d) => new(U16(d, 10), U16(d, 12), U16(d, 14), d[16], d[17]);
    static int Find(byte[] d, int p) { var n = d.AsSpan(p).IndexOf(Sig); return n < 0 ? -1 : p + n; }

    static byte[] ReadSequential(string path)
    {
        using var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read, 64 * 1024, FileOptions.SequentialScan);
        if (stream.Length > int.MaxValue) throw new InvalidDataException("file is too large");
        var data = new byte[(int)stream.Length];
        stream.ReadExactly(data);
        return data;
    }

    static List<Chunk> ReadChunks(byte[] d)
    {
        var offsets = new List<int>();
        for (var p = Find(d, 0); p >= 0; p = Find(d, p + 1)) offsets.Add(p);
        var chunks = new List<Chunk>();
        for (var i = 0; i < offsets.Count; i++)
        {
            var o = offsets[i];
            chunks.Add(new(o, i + 1 < offsets.Count ? offsets[i + 1] : d.Length,
                (int)(U32(d, o + 20) & 0xffff), (int)(U32(d, o + 20) >> 16),
                (int)U32(d, o + 32), (int)U32(d, o + 36)));
        }
        return chunks;
    }

    static (List<Chunk> Texture, List<Chunk> Palette) Split(List<Chunk> chunks)
    {
        var texture = new List<Chunk>(); var palette = new List<Chunk>();
        foreach (var c in chunks)
            if (texture.Count > 0 && c.Width * c.Height * 4 <= 1024) palette.Add(c);
            else texture.Add(c);
        return (texture, palette);
    }

    static string Md5(string path)
    {
        using var md5 = MD5.Create();
        using var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read, 64 * 1024, FileOptions.SequentialScan);
        return Convert.ToHexString(md5.ComputeHash(stream)).ToLowerInvariant();
    }

    static int MaxAddress(Header h, List<Chunk> texture, List<Chunk> palette)
    {
        var max = GsTables.Addr(Math.Max(0, h.Width - 1), Math.Max(0, h.Height - 1), h.Tbw, 19);
        foreach (var c in texture.Concat(palette))
            for (var y = 0; y < c.Height; y++) for (var x = 0; x < c.Width; x++)
                max = Math.Max(max, GsTables.Addr(c.X + x, c.Y + y, GsTables.UploadBw, 0));
        max = Math.Max(max, h.Cbp * 64 + GsTables.ClutAddress(255));
        return max;
    }

    static void Decode(byte[] data, Header h, List<Chunk> texture, List<Chunk> paletteChunks, string target)
    {
        if (h.Psm != 19) throw new InvalidDataException($"PSMT8 only (PSM={h.Psm})");

        var vram = new byte[(MaxAddress(h, texture, paletteChunks) + 1) * 4];
        foreach (var c in texture.Concat(paletteChunks)) for (var y = 0; y < c.Height; y++) for (var x = 0; x < c.Width; x++)
        {
            var a = GsTables.Addr(c.X + x, c.Y + y, GsTables.UploadBw, 0) * 4;
            Buffer.BlockCopy(data, c.Payload + (y * c.Width + x) * 4, vram, a, 4);
        }
        var palette = new Rgba32[256];
        for (var i = 0; i < palette.Length; i++)
        {
            var a = (h.Cbp * 64 + GsTables.ClutAddress(i)) * 4;
            palette[i] = new(vram[a], vram[a + 1], vram[a + 2], FixAlpha(vram[a + 3]));
        }
        using var image = new Image<Rgba32>(h.Width, h.Height);
        for (var y = 0; y < h.Height; y++) for (var x = 0; x < h.Width; x++)
        {
            var index = vram[GsTables.Addr(x, y, h.Tbw, 19)];
            image[x, y] = palette[index];
        }
        Directory.CreateDirectory(Path.GetDirectoryName(target)!);
        image.SaveAsPng(target);
    }

    static byte FixAlpha(byte a)
    {
        var v = a * 2 - 1;
        return (byte)Math.Clamp(v, 0, 255);
    }

    static byte EncodeAlpha(byte a) => a == 0 ? (byte)0 : (byte)((a + 1) / 2);

    static float Bright(Rgba32 c) => .2126f * c.R + .7152f * c.G + .0722f * c.B;

    static (Rgba32[] Palette, byte[] Indices) MakePalette(Image<Rgba32> image)
    {
        var colors = new List<Rgba32>(); var map = new Dictionary<uint, int>();
        var indices = new byte[image.Width * image.Height];
        for (var y = 0; y < image.Height; y++) for (var x = 0; x < image.Width; x++)
        {
            var c = image[x, y]; var key = (uint)(c.R << 24 | c.G << 16 | c.B << 8 | c.A);
            if (!map.TryGetValue(key, out var i)) { i = colors.Count; map[key] = i; colors.Add(c); }
            indices[y * image.Width + x] = (byte)i;
        }
        if (colors.Count > 256)
        {
            var raw = new Rgba32[image.Width * image.Height]; image.CopyPixelDataTo(raw);
            using var one = Image.LoadPixelData<Rgba32>(raw, image.Width, image.Height);
            var options = new QuantizerOptions { MaxColors = 256, Dither = null };
            var quantizer = new WuQuantizer(options);
            using var specific = quantizer.CreatePixelSpecificQuantizer<Rgba32>(one.Configuration, options);
            QuantizerUtilities.BuildPalette(specific, new ExtensivePixelSamplingStrategy(), one.Frames[0]);
            using var quantized = specific.QuantizeFrame(one.Frames[0], new Rectangle(0, 0, image.Width, image.Height));
            colors = quantized.Palette.ToArray().Take(256).ToList();
            for (var y = 0; y < image.Height; y++)
                quantized.DangerousGetRowSpan(y).CopyTo(indices.AsSpan(y * image.Width, image.Width));
        }
        var order = Enumerable.Range(0, colors.Count).OrderByDescending(i => Bright(colors[i])).ToArray();
        var remap = new byte[colors.Count]; var sorted = new Rgba32[colors.Count];
        for (var i = 0; i < order.Length; i++) { remap[order[i]] = (byte)i; sorted[i] = colors[order[i]]; }
        for (var i = 0; i < indices.Length; i++) indices[i] = remap[indices[i]];
        return (sorted, indices);
    }

    static void Encode(string source, string png, string target)
    {
        var data = ReadSequential(source); var h = ReadHeader(data);
        if (h.Psm != 19) throw new InvalidDataException("only PSMT8 can be written");
        var chunks = ReadChunks(data); var (texture, paletteChunks) = Split(chunks);
        using var image = Image.Load<Rgba32>(png);
        if (image.Width != h.Width || image.Height != h.Height) throw new InvalidDataException("image size changed");
        var (palette, indices) = MakePalette(image);
        var vram = new byte[(MaxAddress(h, texture, paletteChunks) + 1) * 4];
        for (var y = 0; y < h.Height; y++) for (var x = 0; x < h.Width; x++)
            vram[GsTables.Addr(x, y, h.Tbw, 19)] = indices[y * h.Width + x];
        for (var i = 0; i < palette.Length; i++)
        {
            var a = (h.Cbp * 64 + GsTables.ClutAddress(i)) * 4;
            vram[a] = palette[i].R; vram[a + 1] = palette[i].G; vram[a + 2] = palette[i].B; vram[a + 3] = EncodeAlpha(palette[i].A);
        }
        foreach (var c in texture) for (var y = 0; y < c.Height; y++) for (var x = 0; x < c.Width; x++)
        {
            var a = GsTables.Addr(c.X + x, c.Y + y, GsTables.UploadBw, 0) * 4;
            Buffer.BlockCopy(vram, a, data, c.Payload + (y * c.Width + x) * 4, 4);
        }
        foreach (var c in paletteChunks) for (var y = 0; y < c.Height; y++) for (var x = 0; x < c.Width; x++)
        {
            var a = GsTables.Addr(c.X + x, c.Y + y, GsTables.UploadBw, 0) * 4;
            Buffer.BlockCopy(vram, a, data, c.Payload + (y * c.Width + x) * 4, 4);
        }
        Directory.CreateDirectory(Path.GetDirectoryName(target)!); File.WriteAllBytes(target, data);
    }

    static void Export(string source, string target)
    {
        Directory.CreateDirectory(target);
        var oldErrors = Path.Combine(target, "errors.txt");
        if (File.Exists(oldErrors)) File.Delete(oldErrors);
        var list = new XElement("pgm"); var skipped = 0; var failed = 0;
        foreach (var file in Directory.EnumerateFiles(source, "*.pgm", SearchOption.AllDirectories)) try
        {
            var rel = Path.GetRelativePath(source, file); var data = ReadSequential(file); var h = ReadHeader(data);
            if (h.Psm != 19 || h.Width <= 0 || h.Height <= 0) { skipped++; continue; }
            var (texture, palette) = Split(ReadChunks(data));
            var type = palette.Count > 0 ? "psmt8_palette" : "psmt8_embedded_palette";
            var pngRel = Path.ChangeExtension(rel, ".png"); var png = Path.Combine(target, pngRel);
            Decode(data, h, texture, palette, png);
            list.Add(new XElement("i", new XAttribute("src", rel.Replace('\\', '/')),
                new XAttribute("png", pngRel.Replace('\\', '/')), new XAttribute("md5", Md5(png)),
                new XAttribute("w", h.Width), new XAttribute("h", h.Height), new XAttribute("type", type)));
        }
        catch (Exception e) { failed++; Console.Error.WriteLine($"{Path.GetRelativePath(source, file)}: {e.Message}"); }
        list.Save(Path.Combine(target, "list.xml"));
        Console.WriteLine($"exported {list.Elements("i").Count()} skipped {skipped} failed {failed}");
    }

    static int Main(string[] args)
    {
        if (args.Length == 3 && args[0] == "d") { try { Export(args[1], args[2]); return 0; } catch (Exception e) { Console.Error.WriteLine(e.Message); return 2; } }
        if (args.Length == 4 && args[0] == "e")
        {
            try
            {
                var rows = XElement.Load(Path.Combine(args[1], "list.xml")).Elements("i"); var encoded = 0; var skipped = 0; var failed = 0;
                foreach (var row in rows)
                {
                    var source = Path.Combine(args[3], (string)row.Attribute("src")!);
                    var png = Path.Combine(args[1], (string)row.Attribute("png")!);
                    var target = Path.Combine(args[2], (string)row.Attribute("src")!);
                    if (!File.Exists(png) || !File.Exists(source)) { skipped++; continue; }
                    if (Md5(png) == row.Attribute("md5")?.Value) { Directory.CreateDirectory(Path.GetDirectoryName(target)!); File.Copy(source, target, true); skipped++; continue; }
                    try { Encode(source, png, target); encoded++; } catch (Exception e) { Console.Error.WriteLine($"{row.Attribute("src")?.Value}: {e.Message}"); failed++; }
                }
                Console.WriteLine($"encoded={encoded} skipped={skipped} failed={failed}"); return failed == 0 ? 0 : 2;
            }
            catch (Exception e) { Console.Error.WriteLine(e.Message); return 2; }
        }
        Console.WriteLine("pgm.exe d <pgm-root> <preview-root>\npgm.exe e <preview-root> <out-root> <pgm-root>");
        return 1;
    }
}
