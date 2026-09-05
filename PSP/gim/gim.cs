using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using System.Text;

using SixLabors.ImageSharp;
using SixLabors.ImageSharp.PixelFormats;
using SixLabors.ImageSharp.Processing;
using SixLabors.ImageSharp.Processing.Processors.Quantization;

namespace GimTool
{
    internal class Rec
    {
        public string path = "";
        public string md5 = "";
        public int bpp, fmt, swz, w, h, p, r, rb, rh, pt;
    }

    internal static class Program
    {
        // ---------- 基础小工具 ----------
        static ushort R16(byte[] p, int o) => (ushort)(p[o] | (p[o + 1] << 8));
        static uint R32(byte[] p, int o) => (uint)(p[o] | (p[o + 1] << 8) | (p[o + 2] << 16) | (p[o + 3] << 24));
        static void W16(byte[] p, int o, ushort v) { p[o] = (byte)v; p[o + 1] = (byte)(v >> 8); }
        static void W32(byte[] p, int o, uint v) { p[o] = (byte)v; p[o + 1] = (byte)(v >> 8); p[o + 2] = (byte)(v >> 16); p[o + 3] = (byte)(v >> 24); }

        static bool ReadFile(string p, out byte[] d)
        {
            d = null;
            try { d = File.ReadAllBytes(p); return true; }
            catch { return false; }
        }

        static void Mkdir(string p)
        {
            try { Directory.CreateDirectory(p); } catch { }
        }

        static string DirName(string p)
        {
            int i = Math.Max(p.LastIndexOf('\\'), p.LastIndexOf('/'));
            return i < 0 ? "" : p.Substring(0, i);
        }

        static string Md5(byte[] d)
        {
            using (MD5 md5 = MD5.Create())
            {
                byte[] h = md5.ComputeHash(d);
                var sb = new StringBuilder(32);
                for (int i = 0; i < h.Length; i++) sb.Append(h[i].ToString("x2"));
                return sb.ToString();
            }
        }

        static Encoding Gbk;
        static void InitEncoding()
        {
            try
            {
                Encoding.RegisterProvider(CodePagesEncodingProvider.Instance);
                Gbk = Encoding.GetEncoding(936);
            }
            catch { Gbk = Encoding.UTF8; }
        }

        // 读取文本：UTF-8（含 BOM）优先，非 UTF-8 回退 GBK，以兼容 gim.cpp 生成的 XML
        static string ReadAllTextSmart(string p)
        {
            byte[] b = File.ReadAllBytes(p);
            if (b.Length >= 3 && b[0] == 0xEF && b[1] == 0xBB && b[2] == 0xBF)
                return Encoding.UTF8.GetString(b, 3, b.Length - 3);
            try { return new UTF8Encoding(false, true).GetString(b); }
            catch (DecoderFallbackException) { return Gbk.GetString(b); }
        }

        static int ParseInt(string s) { int v; return int.TryParse(s, out v) ? v : 0; }

        static string Attr(string s, string k)
        {
            string q = k + "=\"";
            int z = s.IndexOf(q, StringComparison.Ordinal);
            if (z < 0) return "";
            int a = z + q.Length;
            int e = s.IndexOf('"', a);
            return e < 0 ? "" : s.Substring(a, e - a);
        }

        // ---------- PNG 读写（ImageSharp）----------
        static void SavePng(string path, byte[] rgba, int w, int h)
        {
            using (Image<Rgba32> img = Image.LoadPixelData<Rgba32>(rgba, w, h))
                img.SaveAsPng(path);
        }

        static byte[] LoadPng(string path, out int w, out int h)
        {
            try
            {
                using (Image<Rgba32> img = Image.Load<Rgba32>(path))
                {
                    w = img.Width; h = img.Height;
                    byte[] rgba = new byte[w * h * 4];
                    img.CopyPixelDataTo(rgba);
                    return rgba; // R,G,B,A
                }
            }
            catch { w = 0; h = 0; return null; }
        }

        // ---------- swizzle（矩形块平铺）----------
        // 块宽(字节)=imginfo+0x0E, 块高(行)=imginfo+0x10, 从文件头读出, 与 bpp 无关（VB 版 GIM.vb 同款逻辑）。
        // PSP GE 标准交错块 = 16字节 x 8行（仅 8bpp 时恰好 16 像素宽, 16bpp 是 8 像素宽!）;
        // 线性图 rect=16x1, Detile 后自动退化为逐行, 因此无需再判断 swz 标志。
        static byte[] Detile(byte[] s, int w, int h, int bpp, int rb, int rh)
        {
            int rowb = (w * bpp + 7) / 8, bw = (rowb + rb - 1) / rb, bh = (h + rh - 1) / rh;
            byte[] d = new byte[(long)rowb * h];
            long q = 0;
            for (int by = 0; by < bh; by++)
                for (int bx = 0; bx < bw; bx++)
                    for (int y = 0; y < rh; y++)
                    {
                        int yy = by * rh + y;
                        for (int i = 0; i < rb; i++)
                        {
                            int xx = bx * rb + i;
                            if (yy < h && xx < rowb && q < s.Length) d[(long)yy * rowb + xx] = s[q];
                            q++;
                        }
                    }
            return d;
        }

        static byte[] Tile(byte[] s, int w, int h, int bpp, int rb, int rh)
        {
            int rowb = (w * bpp + 7) / 8, bw = (rowb + rb - 1) / rb, bh = (h + rh - 1) / rh;
            byte[] d = new byte[(long)rb * rh * bw * bh];
            long q = 0;
            for (int by = 0; by < bh; by++)
                for (int bx = 0; bx < bw; bx++)
                    for (int y = 0; y < rh; y++)
                    {
                        int yy = by * rh + y;
                        for (int i = 0; i < rb; i++)
                        {
                            int xx = bx * rb + i;
                            if (yy < h && xx < rowb) d[q] = s[(long)yy * rowb + xx];
                            q++;
                        }
                    }
            return d;
        }

        // ---------- 解码：.gim -> PNG ----------
        static bool Decode(string src, string pngout, Rec r)
        {
            byte[] d;
            if (!ReadFile(src, out d) || d.Length < 32) return false;

            int io = 0, po = 0, pe = 0, ie = 0;
            for (int o = 16; o + 16 <= d.Length; )
            {
                int id = R16(d, o), sz = (int)R32(d, o + 4), nx = (int)R32(d, o + 8), hs = (int)R32(d, o + 12);
                if (id == 255 || nx == 0 || o + sz > d.Length) break;
                if (id == 4 && io == 0) { io = o + hs; ie = o + sz; }
                if (id == 5 && po == 0) { po = o + hs; pe = o + sz; }
                o += nx;
            }
            if (io == 0) return false;

            int fmt = R16(d, io + 4), sw = R16(d, io + 6), w = R16(d, io + 8), h = R16(d, io + 10), bp = R16(d, io + 12);
            int off = io + (int)R32(d, io + 28);
            int rb = R16(d, io + 14), rh = R16(d, io + 16);   // 矩形块宽(字节)/高(行)
            if (rb < 1) rb = 16;
            if (rh < 1) rh = sw != 0 ? 8 : 1;
            if (w <= 0 || h <= 0 || off < 0 || off >= d.Length) return false;

            // 调色板: 类型在 palinfo+4 (0=B5G6R5, 1=A1B5G5R5, 2=A4B4G4R4, 3=A8B8G8R8), 条目数在 +8。
            // 前 3 种每条目 2 字节, 第 4 种 4 字节; 位序遵循 PSP GE 标准(名称首字母在高位): R 恒在低位, B 在高位。
            byte[] pal = new byte[1024]; // 内部统一 RGBA
            int pc = 0, pt = 0;
            if ((fmt == 4 || fmt == 5) && po != 0)
            {
                pt = R16(d, po + 4);
                int ncol = R16(d, po + 8);
                int esz = pt == 3 ? 4 : 2;
                int q = po + (int)R32(d, po + 28);
                pc = ncol > 0 ? ncol : (pe - q) / esz;
                if (pc > (fmt == 4 ? 16 : 256)) pc = fmt == 4 ? 16 : 256;
                if (q < 0 || q + pc * esz > d.Length) return false;
                for (int i = 0; i < pc; i++)
                {
                    int o4 = i * 4;
                    if (pt == 3) // A8B8G8R8: 文件字节序 = R,G,B,A
                    {
                        pal[o4] = d[q + i * 4]; pal[o4 + 1] = d[q + i * 4 + 1];
                        pal[o4 + 2] = d[q + i * 4 + 2]; pal[o4 + 3] = d[q + i * 4 + 3];
                        continue;
                    }
                    ushort v = R16(d, q + i * 2);
                    if (pt == 0) // B5G6R5: B高5, G中6, R低5
                    {
                        int b = (v >> 11) & 31, g = (v >> 5) & 63, rr = v & 31;
                        pal[o4] = (byte)((rr << 3) | (rr >> 2));
                        pal[o4 + 1] = (byte)((g << 2) | (g >> 4));
                        pal[o4 + 2] = (byte)((b << 3) | (b >> 2));
                        pal[o4 + 3] = 255;
                    }
                    else if (pt == 1) // A1B5G5R5: A位15, B高5, G中5, R低5
                    {
                        int b = (v >> 10) & 31, g = (v >> 5) & 31, rr = v & 31;
                        pal[o4] = (byte)((rr << 3) | (rr >> 2));
                        pal[o4 + 1] = (byte)((g << 3) | (g >> 2));
                        pal[o4 + 2] = (byte)((b << 3) | (b >> 2));
                        pal[o4 + 3] = (byte)(((v >> 15) & 1) != 0 ? 255 : 0);
                    }
                    else // A4B4G4R4: A高4, B次4, G次4, R低4
                    {
                        pal[o4] = (byte)((v & 15) * 17);
                        pal[o4 + 1] = (byte)(((v >> 4) & 15) * 17);
                        pal[o4 + 2] = (byte)(((v >> 8) & 15) * 17);
                        pal[o4 + 3] = (byte)(((v >> 12) & 15) * 17);
                    }
                }
            }

            int bytes = (int)(((long)w * h * bp + 7) / 8);
            int rend = Math.Min(d.Length, Math.Max(off + bytes, ie));
            if (rend < off) rend = off;

            byte[] raw = new byte[rend - off];
            Array.Copy(d, off, raw, 0, rend - off);
            raw = Detile(raw, w, h, bp, rb, rh);

            byte[] outp = new byte[w * h * 4]; // R,G,B,A
            int np = w * h;
            for (int i = 0; i < np; i++)
            {
                if (bp == 32) // GIM 32bpp 存 RGBA
                {
                    outp[i * 4] = raw[i * 4];
                    outp[i * 4 + 1] = raw[i * 4 + 1];
                    outp[i * 4 + 2] = raw[i * 4 + 2];
                    outp[i * 4 + 3] = raw[i * 4 + 3];
                    continue;
                }
                if (bp == 16)
                {
                    ushort v = R16(raw, i * 2);
                    if (fmt == 0) // B5G6R5: B高5, G中6, R低5 (位复制展开, 与 Firefly/VB 一致)
                    {
                        int b = (v >> 11) & 31, g = (v >> 5) & 63, rr = v & 31;
                        outp[i * 4] = (byte)((rr << 3) | (rr >> 2));
                        outp[i * 4 + 1] = (byte)((g << 2) | (g >> 4));
                        outp[i * 4 + 2] = (byte)((b << 3) | (b >> 2));
                        outp[i * 4 + 3] = 255;
                    }
                    else if (fmt == 2) // A4B4G4R4: A高4, B次4, G次4, R低4
                    {
                        outp[i * 4] = (byte)((v & 15) * 17);
                        outp[i * 4 + 1] = (byte)(((v >> 4) & 15) * 17);
                        outp[i * 4 + 2] = (byte)(((v >> 8) & 15) * 17);
                        outp[i * 4 + 3] = (byte)(((v >> 12) & 15) * 17);
                    }
                    else // A1B5G5R5: A位15, B高5, G中5, R低5
                    {
                        int b = (v >> 10) & 31, g = (v >> 5) & 31, rr = v & 31;
                        outp[i * 4] = (byte)((rr << 3) | (rr >> 2));
                        outp[i * 4 + 1] = (byte)((g << 3) | (g >> 2));
                        outp[i * 4 + 2] = (byte)((b << 3) | (b >> 2));
                        outp[i * 4 + 3] = (byte)((v >> 15) != 0 ? 255 : 0);
                    }
                    continue;
                }
                // 调色板（pal 存 RGBA）
                int ix = -1;
                if (bp == 8) ix = raw[i];
                else if (bp == 4) { byte z = raw[i / 2]; ix = (i & 1) != 0 ? (z >> 4) : (z & 15); }
                if (ix >= 0 && ix < pc)
                {
                    outp[i * 4] = pal[ix * 4];
                    outp[i * 4 + 1] = pal[ix * 4 + 1];
                    outp[i * 4 + 2] = pal[ix * 4 + 2];
                    outp[i * 4 + 3] = pal[ix * 4 + 3];
                }
            }

            SavePng(pngout, outp, w, h);
            r.bpp = bp; r.fmt = fmt; r.swz = sw; r.w = w; r.h = h; r.p = pc; r.r = rend - off; r.rb = rb; r.rh = rh; r.pt = pt;
            return true;
        }

        // ---------- 遍历目录 ----------
        static void Walk(string s, string o, string rel, List<Rec> v)
        {
            string[] entries;
            try { entries = Directory.GetFileSystemEntries(s); }
            catch { return; }

            foreach (string entry in entries)
            {
                string name = Path.GetFileName(entry);
                if (name == "." || name == "..") continue;
                string a = Path.Combine(s, name);
                string b = Path.Combine(o, name);
                string rn = rel + name;

                if (Directory.Exists(entry))
                {
                    Walk(entry, b, rn + "\\", v);
                }
                else if (name.Length > 4 && string.Equals(name.Substring(name.Length - 4), ".gim", StringComparison.OrdinalIgnoreCase))
                {
                    Rec r = new Rec();
                    r.path = rn;
                    string p = b.Substring(0, b.Length - 4) + ".png";
                    Mkdir(DirName(p));
                    if (Decode(a, p, r))
                    {
                        byte[] dd;
                        if (ReadFile(p, out dd)) r.md5 = Md5(dd);
                        v.Add(r);
                        Console.WriteLine(rn);
                    }
                    else Console.WriteLine(rn + " failed");
                }
            }
        }

        // ---------- XML 读写（格式与 gim.cpp 完全一致）----------
        static void WriteXml(string p, List<Rec> v)
        {
            var sb = new StringBuilder();
            sb.Append("<gim>\n");
            foreach (Rec r in v)
            {
                sb.Append("<i n=\"").Append(r.path)
                  .Append("\" b=\"").Append(r.bpp)
                  .Append("\" f=\"").Append(r.fmt)
                  .Append("\" s=\"").Append(r.swz)
                  .Append("\" m=\"").Append(r.md5)
                  .Append("\" w=\"").Append(r.w)
                  .Append("\" h=\"").Append(r.h)
                  .Append("\" p=\"").Append(r.p)
                  .Append("\" r=\"").Append(r.r)
                  .Append("\" rb=\"").Append(r.rb)
                  .Append("\" rh=\"").Append(r.rh)
                  .Append("\" pt=\"").Append(r.pt)
                  .Append("\"/>\n");
            }
            sb.Append("</gim>\n");
            File.WriteAllText(p, sb.ToString(), new UTF8Encoding(false));
        }

        static List<Rec> ReadXml(string p)
        {
            var v = new List<Rec>();
            if (!File.Exists(p)) return v;
            string content = ReadAllTextSmart(p);
            foreach (string line in content.Split('\n'))
            {
                if (line.IndexOf("<i ", StringComparison.Ordinal) < 0) continue;
                Rec r = new Rec();
                r.path = Attr(line, "n");
                r.md5 = Attr(line, "m");
                r.bpp = ParseInt(Attr(line, "b"));
                r.fmt = ParseInt(Attr(line, "f"));
                r.swz = ParseInt(Attr(line, "s"));
                r.w = ParseInt(Attr(line, "w"));
                r.h = ParseInt(Attr(line, "h"));
                r.p = ParseInt(Attr(line, "p"));
                r.r = ParseInt(Attr(line, "r"));
                r.rb = ParseInt(Attr(line, "rb"));
                r.rh = ParseInt(Attr(line, "rh"));
                r.pt = ParseInt(Attr(line, "pt"));
                v.Add(r);
            }
            return v;
        }

        // ================= encode =================
        // 官方文件结构(本游戏 2510 个文件实测均无末尾 EOF 块):
        //   MIG头(0x10) | 块2(sz=文件长-0x10) | 块3(sz=文件长-0x20) | 块4(图像, info 0x30 + 帧表 0x10 + 数据, rel=0x40) | 块5(调色板, info 0x40 + 数据)
        static void Block(byte[] g, int at, int id, int size, int next)
        {
            W16(g, at, (ushort)id);
            W32(g, at + 4, (uint)size);
            W32(g, at + 8, (uint)next);
            W32(g, at + 12, 0x10);
        }

        static readonly byte[] DEF_IMG =
        {
            0x30,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,0x10,0,
            1,0,2,0, 0,0,0,0, 0x30,0,0,0, 0x40,0,0,0,
            0,0,0,0, 0,0,0,0, 1,0,1,0, 3,0,1,0
        };

        static void DefPal(byte[] p, int bpp, int pc, int pt, int esz)
        {
            Array.Clear(p, 0, 0x40);
            W32(p, 0, 0x30);
            W16(p, 4, (ushort)pt);                              // 调色板类型, 按原文件回写
            W16(p, 8, (ushort)pc);                              // 条目数
            W16(p, 10, 1);
            W16(p, 12, (ushort)(esz == 4 ? 0x20 : 0x10));       // 条目位深
            W16(p, 14, 0x10);
            W16(p, 16, 1);
            W16(p, 18, 2);
            W32(p, 0x18, 0x30);
            W32(p, 0x1C, 0x40);
            W32(p, 0x20, (uint)(0x40 + pc * esz));
            p[0x2A] = 1;
            p[0x2E] = 1;
            W32(p, 0x30, 0x40);
        }

        // 量化：先统计全图唯一 RGBA 色（含 A=0 的像素——其 RGB 一并保留，避免“带色透明”被写成纯黑）。
        // 颜色数未超上限时不量化、原色直接入板（无损，未改动的图重编码可逐像素还原）；
        // 超上限才走 Wu：可见像素参与 RGBA 全通道量化，全透明像素固定映射到保留的 0 号条目。
        // d 为 RGBA 缓冲（R,G,B,A）。
        static int BuildPal(byte[] d, int w, int h, int maxc, byte[] pal, byte[] idx)
        {
            int np = w * h;
            var colorMap = new Dictionary<uint, int>();   // packed RGBA -> 序号
            var colorList = new List<Rgba32>();           // 唯一颜色（首次出现顺序）
            int[] pixIdx = new int[np];
            for (int i = 0; i < np; i++)
            {
                uint key = (uint)((d[i * 4] << 24) | (d[i * 4 + 1] << 16) | (d[i * 4 + 2] << 8) | d[i * 4 + 3]);
                if (!colorMap.TryGetValue(key, out int ci))
                {
                    ci = colorList.Count;
                    colorMap[key] = ci;
                    colorList.Add(new Rgba32(d[i * 4], d[i * 4 + 1], d[i * 4 + 2], d[i * 4 + 3]));
                }
                pixIdx[i] = ci;
            }

            if (colorList.Count <= maxc)
            {
                // 颜色数未超上限：不量化，原色直接入调色板（无损）
                for (int j = 0; j < colorList.Count; j++)
                {
                    Rgba32 c = colorList[j];
                    pal[j * 4] = c.R;
                    pal[j * 4 + 1] = c.G;
                    pal[j * 4 + 2] = c.B;
                    pal[j * 4 + 3] = c.A;
                }
                for (int i = 0; i < np; i++) idx[i] = (byte)pixIdx[i];
                return colorList.Count;
            }

            bool hasA0 = false;
            int vis = 0;
            for (int i = 0; i < np; i++)
            {
                if (d[i * 4 + 3] != 0) vis++;
                else hasA0 = true;
            }
            int reserve = hasA0 ? 1 : 0;
            int qcolors = maxc - reserve;
            if (qcolors < 1) qcolors = 1;

            // 可见像素连同 alpha 压成一行
            byte[] src = new byte[vis * 4];       // R,G,B,A
            int[] srcpos = new int[vis];
            int k = 0;
            for (int i = 0; i < np; i++)
            {
                if (d[i * 4 + 3] == 0) continue;
                src[k * 4] = d[i * 4];
                src[k * 4 + 1] = d[i * 4 + 1];
                src[k * 4 + 2] = d[i * 4 + 2];
                src[k * 4 + 3] = d[i * 4 + 3];
                srcpos[k] = i;
                k++;
            }

            byte[] qpal;      // 调色板（R,G,B,A）
            byte[] qidx;      // 每个可见像素的索引
            int used;

            // 颜色数超上限：Wu 量化到 qcolors 色（RGBA 全通道，alpha 参与量化）
            using (Image<Rgba32> img = Image.LoadPixelData<Rgba32>(src, vis, 1))
            {
                var options = new QuantizerOptions { MaxColors = qcolors, Dither = null };
                var quantizer = new WuQuantizer(options);
                using (IQuantizer<Rgba32> q = quantizer.CreatePixelSpecificQuantizer<Rgba32>(img.Configuration, options))
                {
                    // 必须显式全量采样：默认 DefaultPixelSamplingStrategy 有 MaximumPixels 阈值，
                    // 像素多时只拿部分像素建调色板，会把颜色塌缩成十几个、alpha 渐变全丢。
                    QuantizerUtilities.BuildPalette(q, new ExtensivePixelSamplingStrategy(), img.Frames[0]);

                    using (IndexedImageFrame<Rgba32> quantized = q.QuantizeFrame(img.Frames[0], new Rectangle(0, 0, vis, 1)))
                    {
                        ReadOnlyMemory<Rgba32> palette = quantized.Palette;
                        used = palette.Length;
                        if (used > qcolors) used = qcolors;
                        if (used < 1) used = 1;

                        qpal = new byte[used * 4];
                        for (int j = 0; j < used; j++)
                        {
                            Rgba32 c = palette.Span[j];
                            qpal[j * 4] = c.R;
                            qpal[j * 4 + 1] = c.G;
                            qpal[j * 4 + 2] = c.B;
                            qpal[j * 4 + 3] = c.A;   // alpha 由 Wu 直接量化产生，保留渐变
                        }

                        qidx = new byte[vis];
                        ReadOnlySpan<byte> row = quantized.DangerousGetRowSpan(0);
                        for (int x = 0; x < vis; x++) qidx[x] = row[x];
                    }
                }
            }

            int out0 = hasA0 ? 1 : 0;
            if (hasA0) { pal[0] = 0; pal[1] = 0; pal[2] = 0; pal[3] = 0; }

            for (int j = 0; j < used; j++)
            {
                pal[(j + out0) * 4] = qpal[j * 4];
                pal[(j + out0) * 4 + 1] = qpal[j * 4 + 1];
                pal[(j + out0) * 4 + 2] = qpal[j * 4 + 2];
                pal[(j + out0) * 4 + 3] = qpal[j * 4 + 3];
            }

            for (int j = 0; j < vis; j++) idx[srcpos[j]] = (byte)(qidx[j] + out0);
            for (int i = 0; i < np; i++) if (d[i * 4 + 3] == 0) idx[i] = 0;

            return used + out0;
        }

        static bool Encode(string outp, Rec r, byte[] d, int w, int h, bool f8)
        {
            if (r.w <= 0 || r.h <= 0 || r.r <= 0)
            {
                Console.WriteLine(r.path + " xml missing params, re-run: gim d input output");
                return false;
            }
            int bpp = r.bpp, fmt = r.fmt, swz = r.swz, pc = r.p;
            int blkB = r.rb > 0 ? r.rb : 16, blkH = r.rh > 0 ? r.rh : (swz != 0 ? 8 : 1);  // 矩形块宽(字节)/高(行); 旧 gim.xml 无字段时按 GE 标准块推导
            int pt = r.pt > 0 && r.pt <= 3 ? r.pt : 0;   // 调色板类型按原文件; 旧 gim.xml 无字段时按 B5G6R5 处理
            int esz = pt == 3 ? 4 : 2;
            if (f8 && bpp == 4) { bpp = 8; fmt = 5; pc = 0; }  // -8: 有改动的 4bpp 图转 8bpp
            if (bpp != 4 && bpp != 8 && bpp != 16 && bpp != 32)
            {
                Console.WriteLine(r.path + " unsupported bpp " + bpp);
                return false;
            }
            if (w != r.w || h != r.h)
                Console.WriteLine(r.path + " size changed " + r.w + "x" + r.h + " -> " + w + "x" + h + ", rebuilding");

            int np = w * h;
            byte[] raw;
            byte[] pal = null, palF = null;

            if (bpp == 4 || bpp == 8)
            {
                int maxc = bpp == 4 ? 16 : 256;
                if (pc > 0 && pc < maxc) maxc = pc;  // 调色板条目数按官方文件，条目内容总由 PNG 重新生成
                pal = new byte[maxc * 4];
                byte[] idx = new byte[np];
                BuildPal(d, w, h, maxc, pal, idx);
                // 内部 RGBA 调色板 -> 按原文件类型写回(2/4 字节条目, B 高位 R 低位)
                palF = new byte[maxc * esz];
                for (int j = 0; j < maxc; j++)
                {
                    byte R = pal[j * 4], G = pal[j * 4 + 1], B = pal[j * 4 + 2], A = pal[j * 4 + 3];
                    if (pt == 3) { palF[j * 4] = R; palF[j * 4 + 1] = G; palF[j * 4 + 2] = B; palF[j * 4 + 3] = A; }
                    else
                    {
                        ushort v;
                        if (pt == 0) v = (ushort)(((B >> 3) << 11) | ((G >> 2) << 5) | (R >> 3));
                        else if (pt == 1) v = (ushort)((A >= 128 ? 0x8000 : 0) | ((B >> 3) << 10) | ((G >> 3) << 5) | (R >> 3));
                        else v = (ushort)(((A >> 4) << 12) | ((B >> 4) << 8) | ((G >> 4) << 4) | (R >> 4));
                        W16(palF, j * 2, v);
                    }
                }
                if (bpp == 8)
                {
                    raw = idx;
                }
                else
                {
                    int rb = (w + 1) / 2;
                    raw = new byte[(long)rb * h];
                    for (int i = 0; i < np; i++)
                    {
                        if ((i & 1) != 0) raw[i / 2] |= (byte)(idx[i] << 4);
                        else raw[i / 2] |= (byte)(idx[i] & 15);
                    }
                }
            }
            else if (bpp == 16)
            {
                raw = new byte[np * 2];
                for (int i = 0; i < np; i++)
                {
                    byte R = d[i * 4], G = d[i * 4 + 1], B = d[i * 4 + 2], A = d[i * 4 + 3];
                    ushort v;
                    if (fmt == 0) v = (ushort)(((B >> 3) << 11) | ((G >> 2) << 5) | (R >> 3));
                    else if (fmt == 2) v = (ushort)(((A >> 4) << 12) | ((B >> 4) << 8) | ((G >> 4) << 4) | (R >> 4));
                    else v = (ushort)((A >= 128 ? 0x8000 : 0) | ((B >> 3) << 10) | ((G >> 3) << 5) | (R >> 3));
                    W16(raw, i * 2, v);
                }
            }
            else
            {
                // 32bpp：GIM 存 RGBA，与缓冲一致，直接拷贝
                raw = new byte[np * 4];
                Array.Copy(d, raw, np * 4);
            }

            byte[] dat = swz != 0 ? Tile(raw, w, h, bpp, blkB, blkH) : raw;
            if (w == r.w && h == r.h && r.r > dat.Length)
                Array.Resize(ref dat, r.r);  // 个别官方文件像素区存了补齐大小

            long datLen = dat.Length;
            long blk4 = 0x50 + datLen;
            long blk5 = palF == null || palF.Length == 0 ? 0 : 0x50 + palF.Length;
            long total = 0x30 + blk4 + blk5;

            byte[] g = new byte[total];
            byte[] mag = Encoding.ASCII.GetBytes("MIG.00.1PSP");
            Array.Copy(mag, g, mag.Length);   // 11 字节，其余保持 0

            Block(g, 0x10, 2, (int)(total - 0x10), 0x10);
            Block(g, 0x20, 3, (int)(total - 0x20), 0x10);
            Block(g, 0x30, 4, (int)blk4, (int)blk4);

            byte[] info = new byte[0x30];
            Array.Copy(DEF_IMG, info, 0x30);
            W16(info, 4, (ushort)fmt);
            W16(info, 6, (ushort)swz);
            W16(info, 8, (ushort)w);
            W16(info, 10, (ushort)h);
            W16(info, 12, (ushort)bpp);
            W16(info, 14, (ushort)blkB);
            W16(info, 16, (ushort)blkH);
            W32(info, 0x20, (uint)(0x40 + datLen));
            Array.Copy(info, 0, g, 0x40, 0x30);
            W32(g, 0x70, 0x40);                 // imginfo 后固定 16 字节
            Array.Copy(dat, 0, g, 0x80, dat.Length);

            if (blk5 != 0)
            {
                int b5 = (int)(0x30 + blk4);
                Block(g, b5, 5, (int)blk5, (int)blk5);
                byte[] pi = new byte[0x40];
                DefPal(pi, bpp, palF.Length / esz, pt, esz);
                Array.Copy(pi, 0, g, b5 + 0x10, 0x40);
                Array.Copy(palF, 0, g, b5 + 0x50, palF.Length);
            }

            File.WriteAllBytes(outp, g);
            return true;
        }

        static int Main(string[] args)
        {
            InitEncoding();

            bool f8 = false;
            var av = new List<string> { "" };
            foreach (string a in args)
            {
                if (a == "-8") f8 = true;
                else av.Add(a);
            }
            if (av.Count != 4 || (av[1] != "d" && av[1] != "e"))
            {
                Console.Error.WriteLine("gim d input output");
                Console.Error.WriteLine("gim e [-8] input output  (-8: changed 4bpp images saved as 8bpp)");
                return 1;
            }

            string mode = av[1], input = av[2], output = av[3];
            Mkdir(output);
            string xml = Path.Combine(output, "gim.xml");

            if (mode == "d")
            {
                var list = new List<Rec>();
                Walk(input, output, "", list);
                WriteXml(xml, list);
                return 0;
            }

            var a2 = ReadXml(Path.Combine(input, "gim.xml"));
            foreach (Rec r in a2)
            {
                string p = Path.Combine(input, r.path.Substring(0, r.path.Length - 4) + ".png");
                string o = Path.Combine(output, r.path);
                byte[] z;
                if (!ReadFile(p, out z)) { Console.WriteLine(r.path + " missing"); continue; }
                if (Md5(z) == r.md5) { Console.WriteLine(r.path + " skipped"); continue; }
                int w, h;
                byte[] d = LoadPng(p, out w, out h);
                if (d == null) { Console.WriteLine(r.path + " bad png"); continue; }
                Mkdir(DirName(o));
                if (Encode(o, r, d, w, h, f8))
                    Console.WriteLine(r.path + ((f8 && r.bpp == 4) ? " -> 8bpp" : ""));
            }
            return 0;
        }
    }
}
