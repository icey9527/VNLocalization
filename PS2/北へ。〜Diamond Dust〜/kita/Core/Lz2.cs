// Lz2.cs — decode2r 压缩流（解码 + 编码器）。算法还原自 ELF 0x1371F0 解压内核，
// 行为对照 sysdat 全部 182 条流验证；编码器为贪心 + 哈希链，经 tools/kitatest
// 全量"重编码→回读逐字节一致且不超槽位"自测。
//
// 格式（详见 plans/02-sysdat-format.md；上限按解码公式实算）：
//   · 控制字节 8 个操作位，MSB 在前；每组 = 1 控制字节 + 8 个操作的数据
//   · 位=0：字面量 1 字节
//   · 位=1：token t，按高 3 位分派：
//       0x00-0x1F 短匹配   len=(t>>4)+2 (2..3)，dist=(t&0xF)+1 (1..16)
//       0x20-0x3F RLE      len=t>>4 (2..3)，值=(t&0xF) 展开成双半字节（0x00/0x11/..）
//       0x40-0x5F RLE      len=t-61 (3..34)，值=下 1 字节
//       0x60-0x7F RLE      len=((t&0x1F)<<8|b)+3 (3..8194)，值=再下 1 字节
//       0x80-0x9F 匹配     len=(b&0xF)+3 (3..18)，dist=(16*(t&0x1F)|(b>>4))+1 (1..512)
//       0xA0-0xBF 匹配     len=(((b&0xF)<<8)|b2)+3 (3..4098)，dist 同上
//       0xC0-0xDF 字面量串 len=t-183 (9..40)
//       0xE0-0xFF 字面量串 len=((t&0x1F)<<8|b)+9 (9..8200)；E0 00 = 结束标记
//
// 性能：解码输出缓冲按线程复用；RLE/匹配用批量块拷，不逐字节。

using System;
using System.Collections.Generic;

namespace kita
{
    public static class Lz2
    {
        // 编码阈值（引擎格式，按解码公式实算）
        const int MaxOutput = 0x100000;
        const int MaxMatchLen = 4098;
        const int MaxMatchDist = 512;
        const int MaxShortDist = 16;
        const int MaxRle3 = 34;
        const int MaxRle4 = 8194;
        const int MaxRun6 = 40;
        const int MaxRun7 = 8200;
        const int ChainTries = 96;

        [ThreadStatic] static byte[] _dstBuf;

        /// <summary>
        /// 解码。limit&gt;0 时凑够 limit 字节即停（扫描探针用，不要求结束标记）；
        /// limit=0 完整解码，必须命中结束标记。数据非法一律返回 false 不抛异常。
        /// </summary>
        public static bool TryDecode(byte[] src, int start, int limit,
                                      out byte[] data, out int endPos)
        {
            byte[] dst = _dstBuf ??= new byte[MaxOutput];
            int outPos = 0, pos = start, ctrl = 0, lc = 0;
            bool marker = false;
            while (true)
            {
                if (lc == 0)
                {
                    if (pos >= src.Length) goto fail;
                    ctrl = src[pos++]; lc = 8;
                }
                bool isToken = (ctrl & 0x80) != 0;
                ctrl = (ctrl << 1) & 0xFF;
                lc--;
                if (!isToken)
                {
                    if (pos >= src.Length || outPos >= MaxOutput) goto fail;
                    dst[outPos++] = src[pos++];
                }
                else
                {
                    if (pos >= src.Length) goto fail;
                    int t = src[pos++];
                    switch (t >> 5)
                    {
                        case 0:
                            if (!TryCopyMatch(dst, ref outPos, (t & 0xF) + 1, (t >> 4) + 2)) goto fail;
                            break;
                        case 1:
                            {
                                byte v = (byte)((t & 0xF) | ((t & 0xF) << 4));
                                if (!TryFill(dst, ref outPos, v, t >> 4)) goto fail;
                                break;
                            }
                        case 2:
                            {
                                if (pos >= src.Length) goto fail;
                                if (!TryFill(dst, ref outPos, src[pos++], t - 61)) goto fail;
                                break;
                            }
                        case 3:
                            {
                                if (pos + 1 >= src.Length) goto fail;
                                int n = (((t & 0x1F) << 8) | src[pos]) + 3;
                                if (!TryFill(dst, ref outPos, src[pos + 1], n)) goto fail;
                                pos += 2;
                                break;
                            }
                        case 4:
                            {
                                if (pos >= src.Length) goto fail;
                                int b = src[pos++];
                                if (!TryCopyMatch(dst, ref outPos, (16 * (t & 0x1F) | (b >> 4)) + 1, (b & 0xF) + 3)) goto fail;
                                break;
                            }
                        case 5:
                            {
                                if (pos + 1 >= src.Length) goto fail;
                                int b = src[pos], b2 = src[pos + 1]; pos += 2;
                                if (!TryCopyMatch(dst, ref outPos, (16 * (t & 0x1F) | (b >> 4)) + 1, (((b & 0xF) << 8) | b2) + 3)) goto fail;
                                break;
                            }
                        case 6:
                            {
                                int n = t - 183;
                                if (n <= 0 || pos + n > src.Length || outPos + n > MaxOutput) goto fail;
                                Buffer.BlockCopy(src, pos, dst, outPos, n);
                                pos += n; outPos += n;
                                break;
                            }
                        default:
                            {
                                if (pos >= src.Length) goto fail;
                                int n = (((t & 0x1F) << 8) | src[pos]) + 9;
                                pos++;
                                if (n == 9 && t == 0xE0) { marker = true; goto done; }
                                if (pos + n > src.Length || outPos + n > MaxOutput) goto fail;
                                Buffer.BlockCopy(src, pos, dst, outPos, n);
                                pos += n; outPos += n;
                                break;
                            }
                    }
                }
                if (limit > 0 && outPos >= limit) break;
            }
        done:
            if (limit == 0 && !marker) goto fail;   // 完整解码必须命中结束标记
            data = new byte[outPos];
            Buffer.BlockCopy(dst, 0, data, 0, outPos);
            endPos = pos;
            return true;
        fail:
            data = null; endPos = 0;
            return false;
        }

        /// <summary>完整解码一条流（必须命中结束标记）；给回包/自检用。</summary>
        public static byte[] Decode(byte[] src, int start)
        {
            if (!TryDecode(src, start, 0, out var data, out _))
                throw new System.IO.EndOfStreamException("lz2: invalid stream");
            return data;
        }

        static bool TryFill(byte[] dst, ref int outPos, byte v, int count)
        {
            if (count <= 0 || outPos + count > MaxOutput) return false;
            if (count == 1) dst[outPos++] = v;
            else
            {
                System.Array.Fill(dst, v, outPos, count); // RLE 批量填充
                outPos += count;
            }
            return true;
        }

        static bool TryCopyMatch(byte[] dst, ref int outPos, int dist, int len)
        {
            int from = outPos - dist;
            if (dist <= 0 || len <= 0 || from < 0 || outPos + len > MaxOutput) return false;
            if (dist >= len)
            {
                Buffer.BlockCopy(dst, from, dst, outPos, len);
                outPos += len;
                return true;
            }
            int remaining = len; // 重叠匹配：按 dist 分段块拷，语义与逐字节等价
            while (remaining > 0)
            {
                int n = Math.Min(remaining, dist);
                Buffer.BlockCopy(dst, from, dst, outPos, n);
                outPos += n; from += n; remaining -= n;
            }
            return true;
        }

        enum OpKind : byte { Literal, LitRun6, LitRun7, ShortMatch, Rle2, Rle3, Rle4, Match4, Match5, End }

        readonly struct Op
        {
            public readonly OpKind Kind;
            public readonly byte B0, B1, B2;         // token 及其参数字节
            public readonly int Start, Count;        // LitRun 引用 src 区间（零拷贝）
            public Op(OpKind k, byte b0, byte b1, byte b2, int start, int count)
            { Kind = k; B0 = b0; B1 = b1; B2 = b2; Start = start; Count = count; }
        }

        /// <summary>最优解析编码：每位置枚举候选 token（成本 = 负载 + 1/8 控制位），
        /// 后向动态规划取全局最优路径，字面量段事后合并成串（≥9 才划算）。
        /// 候选：RLE2/3/4（游程）、短匹配（len2-3 dist≤16，1 字节）、
        /// Match4（len3-18，2 字节）、Match5（len≤4098，3 字节）。
        /// 短匹配是原版编码器的主力 token，16 字节窗内直扫（哈希找不着长度 2）。</summary>
        public static byte[] Encode(byte[] src)
        {
            int len = src.Length;
            int[] head = new int[0x10000];
            int[] chain = new int[len + 1];
            for (int i = 0; i < head.Length; i++) head[i] = -1;
            for (int i = 0; i < chain.Length; i++) chain[i] = -1;

            // ---- 前向：每位置收集候选（≤5 个） ----
            const int MaxCand = 16;
            const double CtrlBit = 0.125;               // 每个操作占 1/8 个控制字节
            var candLen = new short[MaxCand * Math.Max(len, 1)];
            var candArg = new short[MaxCand * Math.Max(len, 1)];  // 短匹配/匹配的距离
            var candKind = new byte[MaxCand * Math.Max(len, 1)];  // 1=RLE 2=短匹配 3=M4 4=M5
            var candCount = new byte[Math.Max(len, 1)];

            // 游程长度一次性后向预计算（避免长游程里逐位置重扫的 O(n²)）
            var runLen = new int[Math.Max(len, 1)];
            if (len > 0)
            {
                runLen[len - 1] = 1;
                for (int i = len - 2; i >= 0; i--)
                    runLen[i] = src[i + 1] == src[i] ? runLen[i + 1] + 1 : 1;
            }

            for (int sp = 0; sp < len; sp++)
            {
                int run = runLen[sp];                    // 等值游程

                int k = sp * MaxCand, cnt = 0;
                bool dbl = (src[sp] & 0xF) == (src[sp] >> 4);
                if (run >= 3)
                {
                    if (run <= 3 && dbl) { candLen[k + cnt] = (short)run; candKind[k + cnt] = 1; cnt++; }
                    candLen[k + cnt] = (short)Math.Min(run, MaxRle3); candKind[k + cnt] = 1; cnt++;
                    if (run > MaxRle3) { candLen[k + cnt] = (short)Math.Min(run, MaxRle4); candKind[k + cnt] = 1; cnt++; }
                }
                else if (run == 2 && dbl) { candLen[k + cnt] = 2; candKind[k + cnt] = 1; cnt++; }

                if (sp + 1 < len)                        // 短匹配：16 字节窗直扫
                {
                    int cap = Math.Min(3, len - sp);
                    int shortLen = 0, shortDist = 0;
                    for (int dist = 1; dist <= MaxShortDist; dist++)
                    {
                        int from = sp - dist;
                        if (from < 0) break;
                        int m = 0;
                        while (m < cap && src[from + m] == src[sp + m]) m++;
                        if (m > shortLen) { shortLen = m; shortDist = dist; }
                        if (shortLen == cap) break;
                    }
                    if (shortLen >= 2)
                    { candLen[k + cnt] = (short)shortLen; candKind[k + cnt] = 2; candArg[k + cnt] = (short)shortDist; cnt++; }
                }

                if ((run < 9 || sp == 0 || src[sp - 1] != src[sp]) && sp + 2 < len)
                    // 周期图案里长匹配可能跨过游程——只在游程起点搜（DP 会整段取走），
                    // 游程内部位置的链尝试全是同哈希白比，O(run×tries) 会拖垮大平区
                {
                    int ml = FindMatch(src, head, chain, sp, len, out int md);
                    if (ml >= 3)
                    {
                        candLen[k + cnt] = (short)Math.Min(ml, 18); candKind[k + cnt] = 3; candArg[k + cnt] = (short)md; cnt++;
                        if (ml > 18)
                        {
                            candLen[k + cnt] = (short)ml; candKind[k + cnt] = 4; candArg[k + cnt] = (short)md; cnt++;
                            // 周期梯子：匹配距离的整数倍处常是图案边界——原版编码器
                            // 就靠精确落点赢字节（实测 4094×15 优于 4098×14）
                            for (int L = 2 * md; L < ml && cnt < MaxCand; L += md)
                            { candLen[k + cnt] = (short)L; candKind[k + cnt] = 4; candArg[k + cnt] = (short)md; cnt++; }
                        }
                    }
                }
                candCount[sp] = (byte)cnt;
                Insert(head, chain, src, sp);
            }

            // ---- 后向 DP：cost[i] = 从 i 到末尾的最小字节数 ----
            var cost = new double[len + 1];
            for (int i = len - 1; i >= 0; i--)
            {
                double best = 1 + CtrlBit + cost[i + 1]; // 字面量
                int k = i * MaxCand;
                for (int c = 0; c < candCount[i]; c++)
                {
                    int L = candLen[k + c];
                    if (i + L > len) continue;
                    double v = PayloadBytes(candKind[k + c], L, src[i]) + CtrlBit + cost[i + L];
                    if (v < best) best = v;
                }
                cost[i] = best;
            }

            // ---- 前向重建（与 DP 同序同判，路径一致） ----
            var ops = new List<Op>(len / 4 + 16);
            int pendStart = -1;
            int p = 0;
            while (p < len)
            {
                double best = 1 + CtrlBit + cost[p + 1];
                int pick = -1;
                int k = p * MaxCand;
                for (int c = 0; c < candCount[p]; c++)
                {
                    int L = candLen[k + c];
                    if (p + L > len) continue;
                    double v = PayloadBytes(candKind[k + c], L, src[p]) + CtrlBit + cost[p + L];
                    if (v < best) { best = v; pick = c; }
                }
                if (pick < 0)                            // 字面量：攒段，出 token 前冲刷
                {
                    if (pendStart < 0) pendStart = p;
                    p++;
                    continue;
                }
                FlushPend(ops, src, ref pendStart, p);
                int kind = candKind[k + pick], tlen = candLen[k + pick], dist = candArg[k + pick];
                if (kind == 1)
                {
                    if (tlen <= 3 && (src[p] & 0xF) == (src[p] >> 4))
                        ops.Add(new Op(OpKind.Rle2, (byte)(0x20 | (tlen << 4) | (src[p] & 0xF)), 0, 0, 0, tlen));
                    else if (tlen <= MaxRle3)
                        ops.Add(new Op(OpKind.Rle3, (byte)(61 + tlen), src[p], 0, 0, tlen));
                    else
                        ops.Add(new Op(OpKind.Rle4, (byte)(0x60 | ((tlen - 3) >> 8)), (byte)((tlen - 3) & 0xFF), src[p], 0, tlen));
                }
                else if (kind == 2)
                    ops.Add(new Op(OpKind.ShortMatch, (byte)(((tlen - 2) << 4) | (dist - 1)), 0, 0, 0, tlen));
                else if (kind == 3)
                    ops.Add(new Op(OpKind.Match4, (byte)(0x80 | ((dist - 1) >> 4)),
                        (byte)((((dist - 1) & 0xF) << 4) | (tlen - 3)), 0, 0, tlen));
                else
                    ops.Add(new Op(OpKind.Match5, (byte)(0xA0 | ((dist - 1) >> 4)),
                        (byte)((((dist - 1) & 0xF) << 4) | ((tlen - 3) >> 8)), (byte)((tlen - 3) & 0xFF), 0, tlen));
                p += tlen;
            }
            FlushPend(ops, src, ref pendStart, p);
            ops.Add(new Op(OpKind.End, 0xE0, 0, 0, 0, 0));

            // 织入控制字节（MSB 在前）：每组 = 1 控制字节 + 8 个操作的数据
            var body = new byte[len + len / 4 + 64];
            int bp = 1, bit = 0;                        // bp=1：给控制字节让位
            byte ctrl = 0;
            int groupStart = 1;                         // 预留控制字节
            foreach (var op in ops)
            {
                if (bit == 8)
                {
                    body[groupStart - 1] = ctrl;
                    ctrl = 0; bit = 0; groupStart = bp + 1; bp++;
                }
                if (op.Kind != OpKind.Literal) ctrl |= (byte)(0x80 >> bit);
                bit++;
                switch (op.Kind)
                {
                    case OpKind.Literal: body[bp++] = op.B0; break;
                    case OpKind.LitRun6:
                        body[bp++] = (byte)(0xC0 | (op.Count - 9));
                        Buffer.BlockCopy(src, op.Start, body, bp, op.Count); bp += op.Count;
                        break;
                    case OpKind.LitRun7:
                        body[bp++] = (byte)(0xE0 | ((op.Count - 9) >> 8));
                        body[bp++] = (byte)((op.Count - 9) & 0xFF);
                        Buffer.BlockCopy(src, op.Start, body, bp, op.Count); bp += op.Count;
                        break;
                    case OpKind.ShortMatch: body[bp++] = op.B0; break;
                    case OpKind.Rle2: body[bp++] = op.B0; break;
                    case OpKind.Rle3: body[bp++] = op.B0; body[bp++] = op.B1; break;
                    case OpKind.Rle4: body[bp++] = op.B0; body[bp++] = op.B1; body[bp++] = op.B2; break;
                    case OpKind.Match4: body[bp++] = op.B0; body[bp++] = op.B1; break;
                    case OpKind.Match5: body[bp++] = op.B0; body[bp++] = op.B1; body[bp++] = op.B2; break;
                    case OpKind.End: body[bp++] = 0xE0; body[bp++] = 0x00; break;
                }
            }
            if (bit > 0) body[groupStart - 1] = ctrl;
            var result = new byte[bp];
            Buffer.BlockCopy(body, 0, result, 0, bp);
            return result;
        }

        static void FlushPend(List<Op> ops, byte[] src, ref int pendStart, int pendEnd)
        {
            if (pendStart < 0) return;
            int i = pendStart, rem = pendEnd - i;
            while (rem >= 9)
            {
                // 9..40 用 1 字节头；41..48 拆 40+散字节更省；≥49 用 2 字节头
                //（n==9 的 E0 00 形式是结束标记，LitRun7 只在 >40 出现，天然避开）
                int n = rem <= MaxRun6 ? rem : (rem <= 48 ? MaxRun6 : Math.Min(rem, MaxRun7));
                ops.Add(new Op(n <= MaxRun6 ? OpKind.LitRun6 : OpKind.LitRun7, 0, 0, 0, i, n));
                i += n; rem -= n;
            }
            for (; i < pendEnd; i++) ops.Add(new Op(OpKind.Literal, src[i], 0, 0, i, 1));
            pendStart = -1;
        }

        /// <summary>候选 token 的负载字节数（与重建时的 token 选择规则严格一致）。</summary>
        static double PayloadBytes(int kind, int len, byte v)
        {
            switch (kind)
            {
                case 1:
                    if (len <= 3 && (v & 0xF) == (v >> 4)) return 1;   // RLE2
                    return len <= MaxRle3 ? 2 : 3;                      // RLE3 / RLE4
                case 2: return 1;                                       // 短匹配
                case 3: return 2;                                       // Match4
                default: return 3;                                      // Match5
            }
        }

        static int FindMatch(byte[] src, int[] head, int[] chain, int sp, int len, out int bestDist)
        {
            bestDist = 0;
            int bestLen = 0;
            if (sp + 2 >= len) return 0;
            int hash = ((src[sp] << 10) ^ (src[sp + 1] << 5) ^ src[sp + 2]) & 0xFFFF;
            int maxLen = Math.Min(len - sp, MaxMatchLen);
            for (int prev = head[hash], tries = 0;
                 prev >= 0 && tries < ChainTries;
                 prev = chain[prev], tries++)
            {
                int dist = sp - prev;
                if (dist <= 0) continue;
                if (dist > MaxMatchDist) break;
                int m = 0;
                while (m < maxLen && src[prev + m] == src[sp + m]) m++;
                if (m > bestLen)
                {
                    bestLen = m; bestDist = dist;
                    if (m == maxLen) break;
                }
            }
            return bestLen;
        }

        static void Insert(int[] head, int[] chain, byte[] src, int pos)
        {
            if (pos + 2 >= src.Length) return;
            int h = ((src[pos] << 10) ^ (src[pos + 1] << 5) ^ src[pos + 2]) & 0xFFFF;
            chain[pos] = head[h];
            head[h] = pos;
        }
    }
}
