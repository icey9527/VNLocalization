// Lz1.cs — 游戏自带 LZSS 压缩流（解码 + 编码器），算法自 KitaAccess 原样移植
// （该实现经全部 4477 块重压缩回读自测 0 失败），仅把常量改为 LzConfig 注入。
//
// 格式（IDA decode 0x11A5A0 / decode_task 0x11A7F0，详见 研究笔记.md §3.2）：
//   · 控制字节管理 8 个操作位，LSB 在前；每组 = 1 控制字节 + 8 个操作的数据
//   · 位=0：字面量 1 字节
//   · 位=1：读 token
//       0x00..0x7F 长匹配：len=(t>>2)+3 (3..34)，dist=((t&3)<<8)|b（直接距离 1..1023）
//       0x80..0xBF 短匹配：len=((t>>4)&3)+2 (2..5)，dist=(t&0xF)+1（距离-1 编码）
//       0xC0..0xFE 字面量串：(t&0x3F)+8 (8..70) 字节原文
//       0xFF      结束：输出补零到偶数长度后返回
//
// 性能（解包热路径）：输出缓冲按线程复用（避免每块 1MB 分配+清零）；
// 匹配拷贝用块拷贝——dist≥len 时整段一次拷，重叠时按 dist 分段拷，语义与逐字节等价。

using System;
using System.Collections.Generic;
using System.Threading;

namespace kita
{
    public static class Lz1
    {
        // 编码阈值（引擎格式，同引擎游戏不变；结构说明见文件头注释）
        const int DecodeMaxOutput = 0x100000;
        const int MaxLongLen = 34;
        const int MaxLongDist = 1023;   // 距离域 10 位；1024 回读变 0，游戏会跳过
        const int MaxShortLen = 5;
        const int MaxShortDist = 16;
        const int RunMin = 8;
        const int RunMax = 70;          // 71 撞 0xFF 结束符

        // 解码输出缓冲按线程复用（并行解包时每线程一块 1MB，避免 LOH 抖动）
        [ThreadStatic] static byte[] _dstBuf;

        /// <summary>从 src 的 start 偏移解压一条流。</summary>
        public static byte[] Decode(byte[] src, int start)
        {
            byte[] dst = _dstBuf ??= new byte[DecodeMaxOutput];
            int outPos = 0;
            int pos = start;
            if (pos >= src.Length) throw new System.IO.EndOfStreamException("lz1: stream start out of range");
            int ctrl = src[pos++];
            while (true)
            {
                for (int bit = 0; bit < 8; bit++)
                {
                    bool isToken = (ctrl & 1) != 0;
                    ctrl >>= 1; // 先消耗控制位（dist==0 跳过拷贝时也照常计数，与游戏一致）
                    if (!isToken)
                    {
                        if (pos >= src.Length) throw new System.IO.EndOfStreamException("lz1: truncated literal");
                        if (outPos >= DecodeMaxOutput) throw new InvalidOperationException("lz1: output overflow");
                        dst[outPos++] = src[pos++];
                    }
                    else
                    {
                        if (pos >= src.Length) throw new System.IO.EndOfStreamException("lz1: truncated token");
                        int t = src[pos++];
                        if (t < 0x80)
                        {
                            if (pos >= src.Length) throw new System.IO.EndOfStreamException("lz1: truncated dist");
                            int copyLen = (t >> 2) + 3;
                            int dist = ((t & 3) << 8) | src[pos++];
                            if (dist != 0) // dist==0 游戏会跳过拷贝（仍消耗控制位）
                                CopyMatch(dst, ref outPos, dist, copyLen);
                        }
                        else if (t < 0xC0)
                        {
                            CopyMatch(dst, ref outPos, (t & 0xF) + 1, ((t >> 4) & 3) + 2);
                        }
                        else if (t < 0xFF)
                        {
                            int n = (t & 0x3F) + 8;
                            if (pos + n > src.Length) throw new System.IO.EndOfStreamException("lz1: truncated run");
                            if (outPos + n > DecodeMaxOutput) throw new InvalidOperationException("lz1: output overflow");
                            Array.Copy(src, pos, dst, outPos, n);
                            pos += n; outPos += n;
                        }
                        else
                        {
                            if ((outPos & 1) != 0) outPos++; // 游戏会补一个 0 到偶数长度
                            var result = new byte[outPos];
                            Array.Copy(dst, result, outPos);
                            return result;
                        }
                    }
                }
                if (pos >= src.Length) throw new System.IO.EndOfStreamException("lz1: truncated control");
                ctrl = src[pos++];
            }
        }

        /// <summary>
        /// 匹配拷贝：dist≥len 整段一次拷；重叠时按 dist 分段拷（每段与目标区不重叠，
        /// 与逐字节回引拷贝语义等价）。
        /// </summary>
        static void CopyMatch(byte[] dst, ref int outPos, int dist, int len)
        {
            int from = outPos - dist;
            if (from < 0) throw new System.IO.EndOfStreamException("lz1: invalid distance");
            if (outPos + len > DecodeMaxOutput) throw new InvalidOperationException("lz1: output overflow");
            if (dist >= len)
            {
                Buffer.BlockCopy(dst, from, dst, outPos, len);
                outPos += len;
                return;
            }
            int remaining = len;
            while (remaining > 0)
            {
                int n = Math.Min(remaining, dist);
                Buffer.BlockCopy(dst, from, dst, outPos, n);
                outPos += n;
                from += n;
                remaining -= n;
            }
        }

        enum OpKind { Literal, LongMatch, ShortMatch, LitRun, End }

        readonly struct Op
        {
            public readonly OpKind Kind;
            public readonly byte B0;      // token（Literal 时为字节本身）
            public readonly byte B1;      // LongMatch 的距离低字节
            public readonly byte[] Data;  // LitRun 的字面量数据
            public readonly int Run;      // LitRun 长度

            Op(OpKind kind, byte b0, byte b1, byte[] data, int run)
            {
                Kind = kind; B0 = b0; B1 = b1; Data = data; Run = run;
            }

            public static Op Literal(byte b) => new(OpKind.Literal, b, 0, null, 0);
            public static Op LongMatch(byte token, byte distLow) => new(OpKind.LongMatch, token, distLow, null, 0);
            public static Op ShortMatch(byte token) => new(OpKind.ShortMatch, token, 0, null, 0);
            public static Op LitRun(byte[] data, int count) =>
                new(OpKind.LitRun, (byte)(0xC0 | (count - 8)), 0, data, count);
            public static Op End => new(OpKind.End, 0xFF, 0, null, 0);
        }

        /// <summary>
        /// 按游戏格式压缩：贪心 + 哈希链。优先长匹配(≤max_long_len/距离≤max_long_dist)，
        /// 其次短匹配(2..max_short_len/距离≤max_short_dist)，连续字面量攒成字面量串。
        /// </summary>
        public static byte[] Encode(byte[] src)
        {
            int len = src.Length;
            var head = new int[0x10000];
            var chain = new int[len + 1];
            for (int i = 0; i < head.Length; i++) head[i] = -1;
            for (int i = 0; i < chain.Length; i++) chain[i] = -1;

            var ops = new List<Op>(len / 4 + 16);
            var pend = new List<byte>(RunMax);
            int sp = 0;

            while (sp < len)
            {
                int bestLen = 0, bestDist = 0;
                if (sp + 1 < len)
                {
                    int hash = (src[sp] << 8) | src[sp + 1];
                    int maxLen = Math.Min(len - sp, MaxLongLen);
                    for (int prev = head[hash]; prev >= 0; prev = chain[prev])
                    {
                        int dist = sp - prev;
                        if (dist <= 0) continue;
                        if (dist > MaxLongDist) break;
                        int m = 0;
                        while (m < maxLen && src[prev + m] == src[sp + m]) m++;
                        if (m > bestLen)
                        {
                            bestLen = m; bestDist = dist;
                            if (m == maxLen) break;
                        }
                    }
                }
                // 长度 2 只有距离 ≤max_short_dist 且不在末尾才划算（短匹配省 1 字节，末尾省不出）
                if (bestLen == 2 && (bestDist > MaxShortDist || sp + bestLen == len)) bestLen = 0;

                if (bestLen >= 2)
                {
                    FlushPend(ops, pend);
                    if (bestLen >= 3)
                        // 长匹配的距离域是直接距离（0 会被游戏跳过）
                        ops.Add(Op.LongMatch((byte)(((bestLen - 3) << 2) | (bestDist >> 8)), (byte)(bestDist & 0xFF)));
                    else
                        // 短匹配的距离域是距离-1
                        ops.Add(Op.ShortMatch((byte)(0x80 | ((bestLen - 2) << 4) | (bestDist - 1))));
                    for (int k = 0; k < bestLen && sp + k < len; k++) InsertPos(head, chain, src, sp + k);
                    sp += bestLen;
                }
                else
                {
                    InsertPos(head, chain, src, sp);
                    pend.Add(src[sp]);
                    if (pend.Count == RunMax) FlushPend(ops, pend);
                    sp++;
                }
            }
            FlushPend(ops, pend);
            ops.Add(Op.End);

            // 织入控制字节并输出：每组 = 1 个控制字节 + 8 个操作的数据
            var body = new List<byte>(len / 2 + 64);
            var group = new List<byte>(224);
            byte ctrl = 0; int bit = 0;
            foreach (var op in ops)
            {
                if (bit == 8)
                {
                    body.Add(ctrl);
                    body.AddRange(group);
                    ctrl = 0; bit = 0; group.Clear();
                }
                if (op.Kind != OpKind.Literal) ctrl |= (byte)(1 << bit);
                bit++;
                switch (op.Kind)
                {
                    case OpKind.Literal: group.Add(op.B0); break;
                    case OpKind.LongMatch: group.Add(op.B0); group.Add(op.B1); break;
                    case OpKind.ShortMatch: group.Add(op.B0); break;
                    case OpKind.LitRun:
                        group.Add(op.B0);
                        for (int i = 0; i < op.Run; i++) group.Add(op.Data[i]);
                        break;
                    case OpKind.End: group.Add(0xFF); break;
                }
            }
            if (bit > 0) { body.Add(ctrl); body.AddRange(group); }
            while (body.Count % 4 != 0) body.Add(0); // 流补到 4 字节对齐（整条记录还有扇区对齐）
            return body.ToArray();
        }

        static void FlushPend(List<Op> ops, List<byte> pend)
        {
            int i = 0;
            while (pend.Count - i >= RunMin)
            {
                int n = Math.Min(pend.Count - i, RunMax);
                var seg = new byte[n];
                pend.CopyTo(i, seg, 0, n);
                ops.Add(Op.LitRun(seg, n));
                i += n;
            }
            while (i < pend.Count)
            {
                ops.Add(Op.Literal(pend[i]));
                i++;
            }
            pend.Clear();
        }

        static void InsertPos(int[] head, int[] chain, byte[] src, int pos)
        {
            if (pos + 1 >= src.Length) return;
            int h = (src[pos] << 8) | src[pos + 1];
            chain[pos] = head[h];
            head[h] = pos;
        }
    }
}
