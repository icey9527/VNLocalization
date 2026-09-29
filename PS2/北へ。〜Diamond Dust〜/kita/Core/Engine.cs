// Engine.cs — 引擎布局（写死的格式知识）+ 档案自动发现。
//
// 原则：同一引擎的游戏零配置。索引表布局 / 命名规则 / 扇区 / 加密都是引擎常量，
// 写在代码里；唯一会变的"文件数量"通过扫描 DATA 目录自动发现。
// 换引擎的游戏 = 在 Formats/ 写新插件 + 这里加一种 ArchiveKind，不存在"改配置适配"。

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace kita
{
    /// <summary>一种档案的知识：目录、命名、在索引表里的位置。</summary>
    public sealed class ArchiveKind
    {
        public required string Name { get; init; }            // "bg" / "scr"
        public required string Dir { get; init; }             // DATA 下的子目录
        public required string Pattern { get; init; }         // 编号 -> 文件名
        public required int FirstSection { get; init; }       // 记录表首 section（+槽序）
        public required int[] SlotTable { get; init; }        // 引擎槽位表（BG 跳 6/7）
        public int EventMapFirst { get; init; } = -1;         // EVE_NoDB 首 section（scr 用）
        public string BinName(int slotIndex) => string.Format(Pattern, SlotTable[slotIndex] * 100);
    }

        /// <summary>发现到的一个档案文件（ISO 内的一个 BIN）。</summary>
    public sealed record ArchiveBin(
        ArchiveKind Kind,
        int SlotIndex,     // 槽序（0 起，决定 section = FirstSection + SlotIndex）
        string BinName,    // "BG800.BIN"（显示/命名用）
        string IsoPath,    // ISO 内路径 "DATA/BG/BG800.BIN"
        GameSource Source, // 数据源（从 ISO 读字节）
        long Size);        // 字节数（来自 ISO 目录项）

    /// <summary>工作区里的一个档案（提取/打包用；字节一律来自工作区 original\，不碰 ISO）。</summary>
    public sealed record WsArchive(ArchiveKind Kind, int SlotIndex, string BinName);

    public static class Engine
    {
        /// <summary>从工作区 original\ 发现档案：BG = original\BGxxx\ 目录，SCR = original\scr\scrXXX.bin 备份。</summary>
        public static List<WsArchive> DiscoverWorkspace(string workspace)
        {
            var result = new List<WsArchive>();
            string origRoot = Path.Combine(workspace, OriginalDir);
            for (int i = 0; i < Bg.SlotTable.Length; i++)
                if (Directory.Exists(Path.Combine(origRoot, Path.GetFileNameWithoutExtension(Bg.BinName(i)))))
                    result.Add(new WsArchive(Bg, i, Bg.BinName(i)));
            string scrDir = Path.Combine(origRoot, "scr");
            for (int i = 0; i < Scr.SlotTable.Length; i++)
                if (File.Exists(Path.Combine(scrDir, Scr.BinName(i))))
                    result.Add(new WsArchive(Scr, i, Scr.BinName(i)));
            return result;
        }

        // ---- 索引表布局（Eve_FDBInitial 0x13D230，见 研究笔记.md §2）----
        // section 0..7  BG 记录表（槽位 0,1,2,3,4,5,8,9——6/7 永远不用，无 BG600/700）
        // section 25..33 SCR 记录表；51..59 事件->记录号（EVE_NoDB）
        public static readonly ArchiveKind Bg = new()
        {
            Name = "bg",
            Dir = "BG",
            Pattern = "BG{0:D3}.BIN",
            FirstSection = 0,
            SlotTable = new[] { 0, 1, 2, 3, 4, 5, 8, 9 },
        };

        public static readonly ArchiveKind Scr = new()
        {
            Name = "scr",
            Dir = "SCR",
            Pattern = "scr{0:D3}.bin",
            FirstSection = 25,
            SlotTable = new[] { 0, 1, 2, 3, 4, 5, 6, 7, 8 },
            EventMapFirst = 51,
        };

        public static readonly ArchiveKind[] Kinds = { Bg, Scr };

        // ---- 工作区固定结构（照搬 GalaxyAngel2Localization，名字不可改）----
        // <工作目录>/original  原始：按记录切的原始字节（未解码未重压）+ scr 块 + scr 清单
        // <工作目录>/extract   提取：从 original 解码出的 PNG（BGxxx\RRRR.B.png）
        // <工作目录>/modified  替换：只放改过的文件（PNG / scr 块），有 = 改，没有 = 原始字节
        // <工作目录>/packed    输出：回包产物（BG\ SCR\ ACCESSDB.BIN）
        public const string OriginalDir = "original";
        public const string ExtractDir = "extract";
        public const string ModifiedDir = "modified";
        public const string PackedDir = "packed";

        // ---- SCR 命名（引擎格式）----
        public const int EventGroupStep = 1000;               // 事件号 = 组*1000 + 序
        public const string EventPattern = "ev{0:D4}.bin";

        /// <summary>扫描 ISO，发现实际存在的档案文件（按 kind、槽序）。</summary>
        public static List<ArchiveBin> Discover(GameSource source) =>
            Kinds
                .SelectMany(kind => kind.SlotTable
                    .Select((slot, i) => (kind, i))
                    .Where(t => source.Exists($"DATA/{t.kind.Dir}/{t.kind.BinName(t.i)}")))
                .Select(t =>
                {
                    string isoPath = $"DATA/{t.kind.Dir}/{t.kind.BinName(t.i)}";
                    return new ArchiveBin(t.kind, t.i, t.kind.BinName(t.i), isoPath, source, source.Size(isoPath));
                })
                .ToList();

        /// <summary>按用户给的筛选词挑档案：BG800 / bg800.bin / bg / scr（不分大小写）。</summary>
        public static List<ArchiveBin> Filter(List<ArchiveBin> bins, IEnumerable<string> words)
        {
            var result = new List<ArchiveBin>();
            foreach (string raw in words)
            {
                string w = raw.Trim().ToLowerInvariant();
                var hit = bins.Where(b =>
                    b.Kind.Name == w ||
                    b.BinName.ToLowerInvariant() == w ||
                    Path.GetFileNameWithoutExtension(b.BinName).ToLowerInvariant() == w).ToList();
                if (hit.Count == 0)
                    throw new FileNotFoundException(
                        $"找不到档案 {raw}（可用：{string.Join(" ", bins.Select(b => b.BinName))}）");
                result.AddRange(hit);
            }
            return result.Distinct().ToList();
        }
    }
}
