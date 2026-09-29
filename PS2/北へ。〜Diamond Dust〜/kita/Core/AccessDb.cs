// AccessDb.cs — ACCESSDB.BIN（FDB）公用索引表：全项目唯一读写点。
//
// 这是全局索引表：BG/CBD/VOC/SCR/NoDB 所有档案共用。三条安全规则（防把表改坏）：
//   1. 表头永不写 —— 前 SectionCount 个 u32 偏移是静态布局，代码不提供写它的路径；
//   2. 分区所有权 —— BeginUpdate(ownedSections) 声明本次允许改动的 section，
//      WriteRecord 越权直接抛异常；
//   3. 落盘前自检 —— Save 时与读入时的原始字节逐字节 diff，只有自己 section
//      记录区内的字节允许变化，其余任何差异（含表头）拒绝写出。
// 宁可不写，不能写坏：没改到的档案的 section 记录永远原样保留，游戏才能读。

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace kita
{
    public sealed class AccessDb
    {
        /// <summary>索引表头 u32 偏移个数（引擎格式，同引擎游戏不变）。</summary>
        public const int SectionCount = 60;
        /// <summary>扇区单位（引擎格式）。</summary>
        public const int SectorSize = 0x800;

        readonly byte[] _original;      // 读入时的原始字节（Save 自检的基准）
        readonly byte[] _data;          // 工作副本（Updater 在这上面改）
        readonly int[] _offsets;

        AccessDb(byte[] data)
        {
            _original = (byte[])data.Clone();
            _data = data;
            if (_data.Length < SectionCount * 4)
                throw new InvalidDataException($"ACCESSDB.BIN 太小（{_data.Length} < {SectionCount * 4}）");
            _offsets = new int[SectionCount];
            for (int i = 0; i < _offsets.Length; i++)
            {
                _offsets[i] = BitConverter.ToInt32(_data, i * 4);
                if (_offsets[i] < 0 || _offsets[i] > _data.Length)
                    throw new InvalidDataException($"ACCESSDB.BIN 偏移表异常：section {i} = 0x{_offsets[i]:X}");
            }
        }

        public static AccessDb Load(string path) => new(File.ReadAllBytes(path));

        /// <summary>从 ISO 数据源读 ACCESSDB.BIN（对齐 GA2：ISO 是只读基准）。</summary>
        public static AccessDb Load(GameSource source) => new(source.ReadAllBytes("DATA/ACCESSDB.BIN"));

        public byte[] Data => _data;
        public int[] Offsets => _offsets;
        public int SectionStart(int section) => _offsets[section];

        /// <summary>section 结束位置 = 比它大的最小偏移，否则文件尾。</summary>
        public int SectionEnd(int section)
        {
            int start = _offsets[section];
            int end = _data.Length;
            foreach (int o in _offsets)
                if (o > start && o < end) end = o;
            return end;
        }

        /// <summary>读某 section 的 (sector, size) 记录表。</summary>
        public List<(int Sector, int Size)> ReadRecords(int section)
        {
            var list = new List<(int, int)>();
            int off = SectionStart(section), end = SectionEnd(section);
            for (int p = off; p + 8 <= end; p += 8)
                list.Add((BitConverter.ToInt32(_data, p), BitConverter.ToInt32(_data, p + 4)));
            return list;
        }

        /// <summary>读某 section 的 u16 表（NoDB / EVE_NoDB）。</summary>
        public List<ushort> ReadU16Table(int section)
        {
            var list = new List<ushort>();
            int off = SectionStart(section), end = SectionEnd(section);
            for (int p = off; p + 2 <= end; p += 2)
                list.Add(BitConverter.ToUInt16(_data, p));
            return list;
        }

        /// <summary>开始一次索引表更新：只有 ownedSections 内的记录允许改。</summary>
        public Updater BeginUpdate(IEnumerable<int> ownedSections)
        {
            var owned = ownedSections.ToHashSet();
            foreach (int s in owned)
                if (s < 0 || s >= SectionCount)
                    throw new InvalidDataException($"BeginUpdate 的 section {s} 越界");
            return new Updater(this, owned);
        }

        public sealed class Updater
        {
            readonly AccessDb _db;
            readonly HashSet<int> _owned;

            internal Updater(AccessDb db, HashSet<int> owned)
            {
                _db = db;
                _owned = owned;
            }

            /// <summary>回写某 section 第 index 条记录（记录数固定，section 偏移不变）。</summary>
            public void WriteRecord(int section, int index, int sector, int size)
            {
                if (!_owned.Contains(section))
                    throw new InvalidDataException($"索引表越权写：section {section} 不在本次声明的改动范围内");
                int off = _db._offsets[section] + index * 8;
                if (off + 8 > _db.SectionEnd(section))
                    throw new InvalidDataException(
                        $"索引表越界写：section {section}#{index} 超出记录区（off=0x{off:X}）");
                if (sector < 0 || size < 0)
                    throw new InvalidDataException($"非法记录值：section {section}#{index} = ({sector},{size})");
                WriteU32(off, (uint)sector);
                WriteU32(off + 4, (uint)size);
            }

            void WriteU32(int off, uint v)
            {
                _db._data[off] = (byte)v;
                _db._data[off + 1] = (byte)(v >> 8);
                _db._data[off + 2] = (byte)(v >> 16);
                _db._data[off + 3] = (byte)(v >> 24);
            }

            /// <summary>落盘（带自检）：只有自己 section 记录区内的字节允许变化。</summary>
            public void Save(string outputPath)
            {
                byte[] data = _db._data, original = _db._original;
                bool[] allowed = new bool[data.Length];
                foreach (int s in _owned)
                {
                    int start = _db._offsets[s], end = _db.SectionEnd(s);
                    for (int i = start; i < end; i++) allowed[i] = true;
                }

                int header = SectionCount * 4; // 表头绝对禁区
                int firstBad = -1, badCount = 0;
                for (int i = 0; i < data.Length; i++)
                {
                    if (data[i] == original[i] || allowed[i]) continue;
                    if (firstBad < 0) firstBad = i;
                    badCount++;
                }
                if (badCount > 0)
                {
                    string where = firstBad < header
                        ? $"表头区（0x{firstBad:X}）"
                        : $"section 外数据区（0x{firstBad:X}）";
                    throw new InvalidDataException(
                        $"索引表自检失败：{where} 有 {badCount} 处预料外的字节改动，拒绝写出 ACCESSDB.BIN");
                }

                File.WriteAllBytes(outputPath, data);
            }
        }
    }
}
