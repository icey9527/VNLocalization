// Core/GameSource.cs — 游戏数据源：一个 ISO 文件（对齐 GA2：选 ISO 而不是文件夹）。
// 所有格式（BG/SCR/ACCESSDB）都通过这里按 ISO 内路径读字节；ISO 是只读基准，
// 回包永远只写工作区（modified\ -> packed\），不动 ISO 本身。

using System;
using System.Collections.Generic;
using System.IO;

namespace kita
{
    public sealed class GameSource
    {
        readonly string _isoPath;
        readonly Dictionary<string, IsoEntry> _files = new(StringComparer.OrdinalIgnoreCase);

        GameSource(string isoPath, IEnumerable<IsoEntry> entries)
        {
            _isoPath = isoPath;
            foreach (IsoEntry e in entries)
                if (!e.IsDirectory)
                    _files[Normalize(e.Path)] = e;
        }

        public static GameSource Open(string isoPath)
        {
            if (!File.Exists(isoPath))
                throw new FileNotFoundException($"ISO 不存在：{isoPath}");
            return new GameSource(isoPath, IsoImage.Load(isoPath));
        }

        static string Normalize(string path) => path.Replace('\\', '/').TrimStart('/');

        public string IsoPath => _isoPath;
        public int FileCount => _files.Count;

        public bool Exists(string path) => _files.ContainsKey(Normalize(path));

        /// <summary>文件大小（字节）；不存在抛异常。</summary>
        public long Size(string path) =>
            TryGet(path, out IsoEntry e) ? e.Size : throw new FileNotFoundException($"ISO 里没有 {path}");

        /// <summary>按 ISO 内路径读整个文件（按 LBA 定位，一次流式读完）。</summary>
        public byte[] ReadAllBytes(string path)
        {
            if (!TryGet(path, out IsoEntry e))
                throw new FileNotFoundException($"ISO 里没有 {path}");
            const int sectorSize = 2048;
            var data = new byte[e.Size];
            using var fs = new FileStream(_isoPath, FileMode.Open, FileAccess.Read, FileShare.Read);
            fs.Position = (long)e.Lba * sectorSize;
            int done = 0;
            while (done < data.Length)
            {
                int n = fs.Read(data, done, data.Length - done);
                if (n <= 0) throw new EndOfStreamException($"ISO 读取中断：{path}");
                done += n;
            }
            return data;
        }

        /// <summary>ISO 内文件直拷到磁盘（1MB 缓冲流式，不在内存里攒整份——CBD 单文件最大 70MB）。</summary>
        public void CopyTo(string path, string destPath)
        {
            if (!TryGet(path, out IsoEntry e))
                throw new FileNotFoundException($"ISO 里没有 {path}");
            const int sectorSize = 2048;
            var buf = new byte[1 << 20];
            using var fs = new FileStream(_isoPath, FileMode.Open, FileAccess.Read, FileShare.Read);
            fs.Position = (long)e.Lba * sectorSize;
            using var outFs = new FileStream(destPath, FileMode.Create, FileAccess.Write, FileShare.None);
            long remaining = e.Size;
            while (remaining > 0)
            {
                int n = fs.Read(buf, 0, (int)Math.Min(buf.Length, remaining));
                if (n <= 0) throw new EndOfStreamException($"ISO 读取中断：{path}");
                outFs.Write(buf, 0, n);
                remaining -= n;
            }
        }

        bool TryGet(string path, out IsoEntry entry) => _files.TryGetValue(Normalize(path), out entry);
    }
}
