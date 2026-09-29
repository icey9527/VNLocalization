// Formats/BgFormat.cs — BG*.BIN 档案：解包原始（BIN->original\记录字节）、
// 提取（original->extract\PNG）、打包（modified\PNG->packed\BIN）。内核逻辑自
// KitaAccess 原样移植（已全量验证）；布局/命名走 Engine。
//
// 工作区结构（照搬 GA2，四个平级目录，名字固定）：
//   解包 d：记录原始字节（未解码未重压）-> original\BGxxx\RRRR.bin
//   提取 x：解码成图                      -> extract\BGxxx\RRRR.B.png + 根 list.xml（bpp）
//   打包 e：modified\BGxxx\RRRR.B.png 存在 = 该块重建；没有的记录取 original\ 原始字节
//          （无 original 时回落数据目录原 BIN），输出 -> packed\BG\BGxxx.BIN
//   未改动块复用原始压缩流字节，改动块重新量化/压缩（内部先回读比对）——差分最小。

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using SixLabors.ImageSharp;
using SixLabors.ImageSharp.Formats.Png;
using SixLabors.ImageSharp.PixelFormats;

namespace kita
{
    internal static class BgFormat
    {
        // 格式常量（引擎格式，详见 研究笔记.md §3）
        const int MaxRecordBytes = 0x80000;       // dat_load3 DMA 加载窗口
        const int RecordHeaderBytes = 0x10;       // 记录头 u32 块偏移表
        const int MaxRecordBlocks = 4;            // 解析上限（数据里实际 ≤2）
        const int FirstBlockOffset = 0x10;        // 首块压缩流固定偏移

        // 提取是中间产物：低压缩档换速度（无损 PNG，像素不变，回包结果不受影响）
        static readonly PngEncoder FastPng = new() { CompressionLevel = PngCompressionLevel.Level1 };

        // ---------------- 解包：原始字节 -> original ----------------

        /// <summary>把选中档案的每条记录按索引表切成原始字节写到 original\BGxxx\RRRR.bin。</summary>
        public static void UnpackOriginal(List<ArchiveBin> bins, AccessDb db, string workspace, Action<string> log)
        {
            foreach (ArchiveBin bin in bins)
            {
                string stem = Path.GetFileNameWithoutExtension(bin.BinName);
                string origDir = Path.Combine(workspace, Engine.OriginalDir, stem);
                Directory.CreateDirectory(origDir);

                byte[] data = bin.Source.ReadAllBytes(bin.IsoPath);
                var records = db.ReadRecords(bin.Kind.FirstSection + bin.SlotIndex);
                int ss = AccessDb.SectorSize;
                int written = 0;
                for (int rid = 0; rid < records.Count; rid++)
                {
                    var (sector, size) = records[rid];
                    if (size == 0) continue;
                    int off = sector * ss;
                    int len = (int)Math.Min((long)size * ss, (long)data.Length - off);
                    if (len <= 0) continue;
                    using var fs = new FileStream(Path.Combine(origDir, $"{rid:D4}.bin"),
                        FileMode.Create, FileAccess.Write, FileShare.None);
                    fs.Write(data, off, len);
                    written++;
                }
                log($"{stem}: {written} 条记录原始字节 -> {Engine.OriginalDir}\\{stem}");
            }
        }

        // ---------------- 提取：original -> extract（PNG）----------------

        /// <summary>从 original\ 的记录字节解码出 PNG 到 extract\BGxxx\RRRR.B.png，
        /// 并写工作区根 list.xml（file/record/block/png/bpp——PNG 里查不到的字段才记）。</summary>
        public static void Extract(List<WsArchive> bins, AccessDb db, string workspace, Action<string> log)
        {
            string extractDir = Path.Combine(workspace, Engine.ExtractDir);
            Directory.CreateDirectory(extractDir);
            var allRows = new List<ManifestRow>();

            foreach (WsArchive bin in bins)
            {
                string stem = Path.GetFileNameWithoutExtension(bin.BinName);
                string outArc = Path.Combine(extractDir, stem);
                Directory.CreateDirectory(outArc);

                var records = db.ReadRecords(bin.Kind.FirstSection + bin.SlotIndex);
                var workItems = Enumerable.Range(0, records.Count)
                    .Where(rid => records[rid].Size != 0).ToList();

                var rows = new List<ManifestRow>();
                var lockObj = new object();
                int done = 0;
                Parallel.ForEach(workItems, new ParallelOptions { MaxDegreeOfParallelism = Environment.ProcessorCount }, rid =>
                {
                    byte[] blob = LoadRecordBytes(bin, workspace, rid);
                    List<byte[]> blocks = ParseRecordBlocks(blob, 0, blob.Length);
                    var local = new List<ManifestRow>();
                    // 废记录（如 BG200 #542）解析失败 -> 无 PNG；打包时按原始字节处理
                    if (blocks != null)
                    {
                        for (int bi = 0; bi < blocks.Count; bi++)
                        {
                            string pngName = $"{rid:D4}.{bi}.png";
                            var pixels = BgImage.BlockToPixels(blocks[bi], out int w, out int h);
                            using (var img = Image.LoadPixelData<Rgba32>(pixels, w, h))
                                img.SaveAsPng(Path.Combine(outArc, pngName), FastPng);
                            local.Add(new ManifestRow
                            {
                                File = bin.BinName,
                                Record = rid,
                                Block = bi,
                                Png = $"{stem}/{pngName}",
                                // bpp：块首 u32 非 0（实测 0x13）= 256 色调色板 8bpp；0 = 16 色 4bpp（本作未用）
                                Bpp = BitConverter.ToUInt32(blocks[bi], 0) != 0 ? 8 : 4,
                            });
                        }
                    }
                    lock (lockObj)
                    {
                        rows.AddRange(local);
                        if (++done % 200 == 0) log($"  {stem}: {done} records...");
                    }
                });
                rows.Sort((a, b) => a.Record != b.Record ? a.Record.CompareTo(b.Record) : a.Block.CompareTo(b.Block));
                allRows.AddRange(rows);
                log($"{stem}: {rows.Count} 张 PNG -> {Engine.ExtractDir}\\{stem}");
            }
            // list.xml 只是目录参考（PNG 与记录的对应 + bpp），打包不依赖它
            Manifest.WriteBg(Path.Combine(workspace, "list.xml"), allRows);
        }

        /// <summary>取一条记录的原始字节（只从工作区 original\；缺失即报错，提示重新解包）。</summary>
        static byte[] LoadRecordBytes(WsArchive bin, string workspace, int rid)
        {
            string origFile = Path.Combine(workspace, Engine.OriginalDir,
                Path.GetFileNameWithoutExtension(bin.BinName), $"{rid:D4}.bin");
            if (!File.Exists(origFile))
                throw new FileNotFoundException(
                    $"{origFile} 缺失——工作区不完整，请到「新建项目」重新处理该档案");
            return File.ReadAllBytes(origFile); // 原始字节，未重压
        }

        // ---------------- 打包：modified -> packed ----------------

        public static bool Pack(List<WsArchive> bins, AccessDb db, AccessDb.Updater updater,
                                string workspace, string outDir, Action<string> log)
        {
            bool anyChanged = false;
            foreach (WsArchive bin in bins)
            {
                string stem = Path.GetFileNameWithoutExtension(bin.BinName);
                string modDir = Path.Combine(workspace, Engine.ModifiedDir, stem);
                string origDir = Path.Combine(workspace, Engine.OriginalDir, stem);
                var records = db.ReadRecords(bin.Kind.FirstSection + bin.SlotIndex);

                // modified\ 里现存的 (记录, 块) -> PNG 路径；出现即视为"要重建"
                var pngs = ScanPngs(modDir, stem, records.Count);
                if (pngs.Count == 0)
                {
                    log($"{bin.BinName}: {Engine.ModifiedDir}\\{stem} 里没有 PNG，跳过");
                    continue;
                }
                anyChanged = true;

                var newRecords = new List<(int Sector, int Size)>(records.Count);
                var output = new MemoryStream();
                int rebuilt = 0;
                for (int rid = 0; rid < records.Count; rid++)
                {
                    var (sector, size) = records[rid];
                    int newSector = (int)(output.Length / AccessDb.SectorSize);
                    if (size == 0)
                    {
                        if (pngs.TryGetValue(rid, out var zero) && zero.Count > 0)
                            throw new InvalidDataException($"{stem}/{rid:D4}: 原始记录是空的，不能替换");
                        newRecords.Add((newSector, 0));
                        continue;
                    }
                    string origFile = Path.Combine(origDir, $"{rid:D4}.bin");
                    if (!File.Exists(origFile))
                        throw new FileNotFoundException(
                            $"{origFile} 缺失——工作区不完整，请到「新建项目」重新处理该档案");
                    byte[] blob = File.ReadAllBytes(origFile); // 原始字节，未重压

                    byte[] newBlob = pngs.TryGetValue(rid, out var blockPngs)
                        ? RebuildRecord(blob, blockPngs, rid, stem, ref rebuilt, log)
                        : null;
                    if (newBlob == null)
                    {
                        output.Write(blob, 0, blob.Length); // 没改的记录：原始字节原样
                        newRecords.Add((newSector, blob.Length / AccessDb.SectorSize));
                        continue;
                    }
                    if (newBlob.Length > MaxRecordBytes)
                        throw new InvalidOperationException(
                            $"{bin.BinName} record {rid}: rebuilt {newBlob.Length} bytes exceeds load window {MaxRecordBytes}");
                    if (newBlob.Length > blob.Length)
                        log($"{bin.BinName} record {rid}: {size} -> {newBlob.Length / AccessDb.SectorSize} sectors (grew)");
                    output.Write(newBlob, 0, newBlob.Length);
                    newRecords.Add((newSector, newBlob.Length / AccessDb.SectorSize));
                }

                string outArcDir = Path.Combine(outDir, bin.Kind.Dir);
                Directory.CreateDirectory(outArcDir);
                File.WriteAllBytes(Path.Combine(outArcDir, bin.BinName), output.ToArray());
                for (int rid = 0; rid < newRecords.Count; rid++)
                    updater.WriteRecord(bin.Kind.FirstSection + bin.SlotIndex, rid, newRecords[rid].Sector, newRecords[rid].Size);
                log($"{bin.BinName}: {records.Count} records, {pngs.Count} 条被替换（{rebuilt} 块重建）");
            }
            return anyChanged;
        }

        /// <summary>扫描 modified\<stem>\ 下的 RRRR.B.png；rid 越界直接报错（防工作目录与数据不匹配）。</summary>
        static Dictionary<int, Dictionary<int, string>> ScanPngs(string modDir, string stem, int recordCount)
        {
            var map = new Dictionary<int, Dictionary<int, string>>();
            if (!Directory.Exists(modDir)) return map;
            var regex = new Regex(@"^(\d{4})\.(\d+)\.png$", RegexOptions.IgnoreCase);
            foreach (string file in Directory.GetFiles(modDir, "*.png"))
            {
                Match m = regex.Match(Path.GetFileName(file));
                if (!m.Success) continue;
                int rid = int.Parse(m.Groups[1].Value);
                int bi = int.Parse(m.Groups[2].Value);
                if (rid >= recordCount)
                    throw new InvalidDataException(
                        $"{stem}/{Path.GetFileName(file)}: 记录号 {rid} 超出该档案（共 {recordCount} 条）——modified 与数据目录不匹配？");
                if (!map.TryGetValue(rid, out var blocks))
                    map[rid] = blocks = new Dictionary<int, string>();
                blocks[bi] = file;
            }
            return map;
        }

        /// <summary>按 PNG 重建一条记录；该记录没有任何 PNG 时调用方走原始字节。</summary>
        static byte[] RebuildRecord(byte[] blob, Dictionary<int, string> blockPngs, int rid, string stem,
            ref int rebuilt, Action<string> log)
        {
            List<byte[]> blocks = ParseRecordBlocks(blob, 0, blob.Length);
            if (blocks == null)
                throw new InvalidOperationException($"{stem}#{rid}: 原始记录解不开（废数据），不能替换");
            foreach (int bi in blockPngs.Keys)
                if (bi >= blocks.Count)
                    throw new InvalidDataException(
                        $"{stem}/{rid:D4}.{bi}.png: 该记录只有 {blocks.Count} 块，没有块 {bi} ——modified 与数据目录不匹配？");

            // 原始压缩流的边界（未改动块原样复用）
            int tableCount = blocks.Count;
            var streamRanges = new List<(int start, int end)>();
            for (int i = 0; i < tableCount; i++)
            {
                int start = (int)BitConverter.ToUInt32(blob, i * 4);
                int end = i + 1 < tableCount ? (int)BitConverter.ToUInt32(blob, (i + 1) * 4) : blob.Length;
                streamRanges.Add((start, end));
            }

            var streams = new byte[tableCount][];
            for (int bi = 0; bi < tableCount; bi++)
            {
                if (!blockPngs.TryGetValue(bi, out string pngPath))
                {
                    var (start, end) = streamRanges[bi];
                    streams[bi] = Slice(blob, start, end - start);
                    continue;
                }
                byte[] raw = blocks[bi];
                using (var image = Image.Load<Rgba32>(pngPath))
                {
                    var pixels = BgImage.BlockToPixels(raw, out int w, out int h);
                    // 部件头里的宽高是固定的（游戏按它上传），PNG 尺寸必须一致
                    if (image.Width != w || image.Height != h)
                        throw new InvalidOperationException(
                            $"{stem}/{Path.GetFileName(pngPath)}: 尺寸 {image.Width}x{image.Height} != 需要 {w}x{h}（尺寸不可改）");
                    image.CopyPixelDataTo(pixels); // PNG 像素才是数据源
                    BgImage.WritePixelsToBlock(raw, pixels, w, h);
                }
                streams[bi] = Lz1.Encode(raw);
                // 编码正确性保险：回读比对
                byte[] check = Lz1.Decode(streams[bi], 0);
                if (!check.AsSpan().SequenceEqual(raw))
                    throw new InvalidOperationException($"{stem}/{Path.GetFileName(pngPath)}: lz1 roundtrip mismatch");
                log($"  rebuilt {stem}/{rid:D4}.{bi}");
                rebuilt++;
            }

            // 记录头：u32 偏移表，首项恒为记录头长度，末尾补 0
            var outBlob = new MemoryStream();
            int headerSlots = RecordHeaderBytes / 4;
            int off = RecordHeaderBytes;
            for (int i = 0; i < headerSlots; i++)
            {
                uint v = i < tableCount ? (uint)off : 0;
                outBlob.Write(BitConverter.GetBytes(v), 0, 4);
                if (i < tableCount) off += streams[i].Length;
            }
            foreach (var s in streams) outBlob.Write(s, 0, s.Length);
            var bytes = outBlob.ToArray();
            int sectorSize = AccessDb.SectorSize;
            int pad = (sectorSize - bytes.Length % sectorSize) % sectorSize;
            if (pad > 0)
            {
                var padded = new byte[bytes.Length + pad];
                Array.Copy(bytes, padded, bytes.Length);
                return padded;
            }
            return bytes;
        }

        /// <summary>解析记录：返回各块解压结果；记录头不合法/解压失败返回 null。
        /// 直接传源数组 + 记录起点，避免先切片再解压的多一次拷贝。</summary>
        static List<byte[]> ParseRecordBlocks(byte[] src, int baseOff, int recLen)
        {
            var blocks = new List<byte[]>();
            for (int slot = 0; slot < MaxRecordBlocks; slot++)
            {
                int off = baseOff + slot * 4;
                if (off + 4 > src.Length) break;
                uint v = BitConverter.ToUInt32(src, off);
                if (v == 0) break;
                if (v < FirstBlockOffset || v >= recLen) return null;
                try
                {
                    blocks.Add(Lz1.Decode(src, baseOff + (int)v));
                }
                catch (EndOfStreamException)
                {
                    return null;
                }
            }
            if (blocks.Count == 0) return null;
            foreach (var b in blocks)
                if (BitConverter.ToUInt32(b, BgImage.BlkPartTable) == 0 || BitConverter.ToInt32(b, BgImage.BlkPartCount) <= 0)
                    return null;
            return blocks;
        }

        static byte[] Slice(byte[] src, int off, int len)
        {
            if (off + len > src.Length) len = src.Length - off;
            var dst = new byte[len];
            Array.Copy(src, off, dst, 0, len);
            return dst;
        }
    }
}
