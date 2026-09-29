// Formats/ScrFormat.cs — SCR 脚本档案：切块（-> original\scr\）与拼块（modified\ -> packed\）。
//
// 职责边界：本类只按 ACCESSDB 索引表搬运字节——切出的块保持"加密原样"（每块
// 0x30..0x3F 自带明文密钥、0x40 起为密文，自包含）。解密与文本处理是 Python 的领地
// （scn.py 现状不变）。
//
// 工作区结构（GA2 同款四目录）：
//   解包 d：原始块 -> original\scr\ev????.bin + original\scr\list.xml（g/e/r/s/n/f/alias）
//   打包 e：modified\scr\ev????.bin 存在 = 该块替换（与原始字节相同则视为未改）；
//          其余记录取 original\（回落数据目录原 BIN），输出 -> packed\SCR\scr???00.bin

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;

namespace kita
{
    internal static class ScrFormat
    {
        const string ScrDirName = "scr"; // 工作区里脚本块的子目录名（original\scr、modified\scr）

        public static void UnpackOriginal(List<ArchiveBin> bins, AccessDb db, string workspace, Action<string> log)
        {
            string scrOut = Path.Combine(workspace, Engine.OriginalDir, ScrDirName);
            Directory.CreateDirectory(scrOut);
            var rows = new List<ScrRow>();

            foreach (ArchiveBin bin in bins)
            {
                int group = bin.Kind.SlotTable[bin.SlotIndex];
                if (bin.Kind.EventMapFirst < 0)
                    throw new InvalidDataException("scr 档案缺 EventMapFirst（引擎布局不完整）");
                byte[] data = bin.Source.ReadAllBytes(bin.IsoPath);

                // real -> 事件号列表（EVE_NoDB：多事件共享同一块）
                var reverse = new Dictionary<int, List<int>>();
                List<ushort> emap = db.ReadU16Table(bin.Kind.EventMapFirst + bin.SlotIndex);
                for (int eventId = 0; eventId < emap.Count; eventId++)
                {
                    if (!reverse.TryGetValue(emap[eventId], out var bucket))
                        reverse[emap[eventId]] = bucket = new List<int>();
                    bucket.Add(eventId);
                }

                var entries = db.ReadRecords(bin.Kind.FirstSection + bin.SlotIndex);
                int count = 0;
                for (int real = 0; real < entries.Count; real++)
                {
                    if (!reverse.TryGetValue(real, out var events) || events.Count == 0) continue;
                    var (sector, size) = entries[real];
                    // 注意：scn.py 回包后可能有"过期记录"（无文本记录保留旧表项，指向旧文件位置）。
                    // Python 切片越界静默变空，这里同样钳制保持行为一致（本作 6 个空块）。
                    byte[] chunk = Slice(data, (long)sector * AccessDb.SectorSize, (long)size * AccessDb.SectorSize);
                    int logical = group * Engine.EventGroupStep + events[0];
                    string name = string.Format(Engine.EventPattern, logical);
                    File.WriteAllBytes(Path.Combine(scrOut, name), chunk);
                    rows.Add(new ScrRow
                    {
                        Group = group,
                        Event = logical,
                        Real = real,
                        Sector = sector,
                        Size = size,
                        File = name, // 相对 list.xml 所在目录（original\scr\）
                        Alias = events.Skip(1).Select(x => group * Engine.EventGroupStep + x).ToList(),
                    });
                    count++;
                }
                // 组 BIN 整份备份（九个共 2.6MB）：打包重排时，没有事件名的记录
                // （EVE_NoDB 未映射/过期表项）从这份备份切原始字节——工作区自包含，打包不碰 ISO
                File.WriteAllBytes(Path.Combine(scrOut, bin.BinName),
                    bin.Source.ReadAllBytes(bin.IsoPath));
                log($"{bin.BinName}: {count} 块 -> {Engine.OriginalDir}\\{ScrDirName}");
            }

            Manifest.WriteScr(Path.Combine(scrOut, "list.xml"), rows);
        }

        public static bool Pack(List<WsArchive> bins, AccessDb db, AccessDb.Updater updater,
                                string workspace, string outDir, Action<string> log)
        {
            string modDir = Path.Combine(workspace, Engine.ModifiedDir, ScrDirName);
            // 事件号 -> (组, real)；扫 modified\scr\，出现即视为"要替换"
            var blocks = ScanBlockFiles(bins, modDir, db, log);

            bool anyChanged = false;
            foreach (WsArchive bin in bins)
            {
                int group = bin.Kind.SlotTable[bin.SlotIndex];
                var entries = db.ReadRecords(bin.Kind.FirstSection + bin.SlotIndex);

                var replacements = new Dictionary<int, string>();
                foreach (var ((g, real), file) in blocks)
                    if (g == group && real >= 0 && real < entries.Count)
                        replacements[real] = file;
                if (replacements.Count == 0)
                {
                    log($"{bin.BinName}: {Engine.ModifiedDir}\\{ScrDirName} 里没有本组的块，跳过");
                    continue;
                }

                bool changed = false;
                var newChunks = new byte[entries.Count][];
                for (int real = 0; real < entries.Count; real++)
                {
                    var (sector, size) = entries[real];
                    byte[] original = LoadBlockBytes(bin, db, workspace, real);
                    if (!replacements.TryGetValue(real, out string blockFile))
                    {
                        newChunks[real] = original;
                        continue;
                    }
                    byte[] chunk = File.ReadAllBytes(Path.Combine(modDir, blockFile));
                    if (chunk.Length % AccessDb.SectorSize != 0)
                        throw new InvalidDataException(
                            $"{blockFile}: 长度 {chunk.Length} 不是扇区({AccessDb.SectorSize})整数倍，拒绝拼块");
                    if (chunk.Length == original.Length && chunk.AsSpan().SequenceEqual(original))
                    {
                        newChunks[real] = original; // 内容没变，按原样
                        continue;
                    }
                    newChunks[real] = chunk;
                    changed = true;
                    log($"  replace {bin.BinName}#{real} <- {Engine.ModifiedDir}\\{ScrDirName}\\{blockFile}");
                }
                if (!changed)
                {
                    log($"{bin.BinName}: 块内容与原始一致，跳过");
                    continue;
                }
                anyChanged = true;

                // 该组重排：所有记录（含未替换的）按新顺序落盘
                var output = new MemoryStream();
                var newEntries = new List<(int Sector, int Size)>(entries.Count);
                foreach (byte[] chunk in newChunks)
                {
                    int sector = (int)(output.Length / AccessDb.SectorSize);
                    output.Write(chunk, 0, chunk.Length);
                    newEntries.Add((sector, chunk.Length / AccessDb.SectorSize));
                }

                string outDirFull = Path.Combine(outDir, bin.Kind.Dir);
                Directory.CreateDirectory(outDirFull);
                File.WriteAllBytes(Path.Combine(outDirFull, bin.BinName), output.ToArray());
                for (int i = 0; i < newEntries.Count; i++)
                    updater.WriteRecord(bin.Kind.FirstSection + bin.SlotIndex, i, newEntries[i].Sector, newEntries[i].Size);
                log($"{bin.BinName}: {entries.Count} records relaid");
            }
            return anyChanged;
        }

        /// <summary>取一块的原始字节：original\scr\ 优先，回落数据目录原 BIN。</summary>
        static byte[] LoadBlockBytes(WsArchive bin, AccessDb db, string workspace, int real)
        {
            string origFile = Path.Combine(workspace, Engine.OriginalDir, ScrDirName,
                string.Format(Engine.EventPattern, LogicalOf(bin, db, real)));
            if (LogicalOf(bin, db, real) >= 0 && File.Exists(origFile))
                return File.ReadAllBytes(origFile);
            // 没有事件名的记录：从 original\scr 的组 BIN 备份切原始字节
            var (sector, size) = db.ReadRecords(bin.Kind.FirstSection + bin.SlotIndex)[real];
            string groupBin = Path.Combine(workspace, Engine.OriginalDir, ScrDirName, bin.BinName);
            if (!File.Exists(groupBin))
                throw new FileNotFoundException(
                    $"{groupBin} 缺失——工作区不完整，请到「新建项目」重新处理脚本档案");
            byte[] src = File.ReadAllBytes(groupBin);
            return Slice(src, (long)sector * AccessDb.SectorSize, (long)size * AccessDb.SectorSize);
        }

        /// <summary>记录号 -> 主事件号（找不到返回 -1，该记录本来就没有事件名）。</summary>
        static int LogicalOf(WsArchive bin, AccessDb db, int real)
        {
            List<ushort> emap = db.ReadU16Table(bin.Kind.EventMapFirst + bin.SlotIndex);
            for (int eventId = 0; eventId < emap.Count; eventId++)
                if (emap[eventId] == real)
                {
                    int group = bin.Kind.SlotTable[bin.SlotIndex];
                    return group * Engine.EventGroupStep + eventId;
                }
            return -1;
        }

        /// <summary>扫 modified\scr\ 里符合事件命名的块文件 -> (组, real)。</summary>
        static Dictionary<(int Group, int Real), string> ScanBlockFiles(List<WsArchive> bins, string modDir, AccessDb db, Action<string> log)
        {
            var map = new Dictionary<(int, int), string>();
            if (!Directory.Exists(modDir)) return map;

            // 与 Engine.EventPattern 配套的事件名正则（引擎常量，两个写在一起维护）
            var regex = new Regex(@"^ev(\d{4})\.bin$", RegexOptions.IgnoreCase);

            foreach (string file in Directory.GetFiles(modDir, "*", SearchOption.TopDirectoryOnly))
            {
                Match m = regex.Match(Path.GetFileName(file));
                if (!m.Success) continue;
                int logical = int.Parse(m.Groups[1].Value);
                int group = logical / Engine.EventGroupStep;
                WsArchive bin = bins.FirstOrDefault(b => b.Kind.SlotTable[b.SlotIndex] == group);
                if (bin == null || bin.Kind.EventMapFirst < 0)
                {
                    log($"  [跳过] {Path.GetFileName(file)}: 组 {group} 不在本次打包范围");
                    continue;
                }
                List<ushort> emap = db.ReadU16Table(bin.Kind.EventMapFirst + bin.SlotIndex);
                int eventId = logical % Engine.EventGroupStep;
                if (eventId >= emap.Count)
                {
                    log($"  [跳过] {Path.GetFileName(file)}: 事件号超出映射表");
                    continue;
                }
                map[(group, emap[eventId])] = Path.GetFileName(file);
            }
            return map;
        }

        /// <summary>越界安全切片（long 入参，钳制到 [0, src.Length]，与 Python 切片语义一致）。</summary>
        static byte[] Slice(byte[] src, long off, long len)
        {
            long start = Math.Clamp(off, 0, src.Length);
            long stop = Math.Clamp(off + Math.Max(len, 0), start, src.Length);
            var dst = new byte[stop - start];
            if (dst.Length > 0) Array.Copy(src, start, dst, 0, dst.Length);
            return dst;
        }
    }
}
