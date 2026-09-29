// Manifest.cs — 清单写入（目录参考用，只记录"从产物文件里查不到"的字段）。
//
// BG 的 list.xml：file/record/block/png/bpp。长宽、大小都能从 PNG 取，不记；
// bpp（8bpp=256色调色板 / 4bpp=16色）块头里有、PNG 里没有，必须记。
// 本作 BG 数据全是 8bpp（引擎支持 4bpp 路径，数据未用），字段留作扩展。
// SCR 的 scr/list.xml：g/e/r/s/n/f/alias，与 scn.py 同 schema，供 Python 适配器消费。
// 两者打包都不依赖清单——BG 打包从原始块读结构，改动检测靠文件存在性（modified 语义）。

using System;
using System.Collections.Generic;
using System.IO;

namespace kita
{
    public sealed class ManifestRow
    {
        public string File = "";
        public int Record, Block;
        public string Png = "";
        public int Bpp = 8;
    }

    public sealed class ScrRow
    {
        public int Group, Event, Real, Sector, Size;
        public string File = "";
        public List<int> Alias = new();
    }

    public static class Manifest
    {
        public static void WriteBg(string path, List<ManifestRow> rows)
        {
            rows.Sort((a, b) =>
            {
                int c = string.Compare(a.File, b.File, StringComparison.Ordinal);
                if (c != 0) return c;
                c = a.Record.CompareTo(b.Record);
                return c != 0 ? c : a.Block.CompareTo(b.Block);
            });
            using var w = new StreamWriter(path);
            w.WriteLine("<?xml version='1.0' encoding='utf-8'?>");
            w.WriteLine("<images>");
            foreach (var r in rows)
                w.WriteLine($"  <image file=\"{r.File}\" record=\"{r.Record}\" block=\"{r.Block}\" png=\"{r.Png}\" bpp=\"{r.Bpp}\" />");
            w.WriteLine("</images>");
        }

        public static void WriteScr(string path, List<ScrRow> rows)
        {
            rows.Sort((a, b) => a.Group != b.Group
                ? a.Group.CompareTo(b.Group)
                : a.Event.CompareTo(b.Event));
            using var w = new StreamWriter(path);
            w.WriteLine("<?xml version='1.0' encoding='utf-8'?>");
            w.WriteLine("<scn>");
            foreach (var r in rows)
            {
                string alias = r.Alias.Count > 0
                    ? $" alias=\"{string.Join(",", r.Alias)}\""
                    : "";
                w.WriteLine($"  <item g=\"{r.Group}\" e=\"{r.Event}\" r=\"{r.Real}\" s=\"{r.Sector}\" n=\"{r.Size}\" f=\"{r.File}\"{alias} />");
            }
            w.WriteLine("</scn>");
        }
    }
}
