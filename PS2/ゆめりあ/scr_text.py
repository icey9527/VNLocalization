#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scr_text.py -- Yumeria SCR 脚本 文本提取 / 回写 (支持变长扩容)

用法:
    python scr_text.py m <输入目录> <输出目录>
        提取:
          * 按脚本【编号连续段】分组: 0280,0281,...,0290 -> "0280-0290.txt"
            孤立编号 -> "XXXX.txt"; 段内内容完全相同的脚本只保留一份文本
          * 文本按引擎语义【顺序】读取(与解密器 sub_159B08 一致),
            并与索引表逐条交叉校验, 不符自动回退 —— 不做任何扫描
          * 生成 lines.list: 每行 "<相对路径> <段文件> <起始行(0基)> <行数>"
            回写时: 脚本的第 i 条串 = 段文件的第 (起始行+i) 行

    python scr_text.py i <输入目录> <文本目录> [<输出目录>] [--fix-args]
        回写: 按 lines.list 把段文件的连续若干行写回对应 .scr
        支持变长: 放不下的串自动追加到文件尾

        默认只重建索引表, opcode/args 区一个字节都不动 ——
        游戏取文本走索引表, opcode 里的 args 不是文本指针(实测平移必闪退)。
        --fix-args 是备用的旧行为, 仅用于实验。

        <输出目录> 省略 = 就地覆盖输入目录。
        推荐做法: 输入目录给"原版备份"，输出目录给真正要打包的目录 ——
        每次都从原版重来，改多少次翻译都不会在上一次结果上叠加。
          python scr_text.py i backup/scr_orig txt cdimage/A

    python scr_text.py d <file.scr>
        调试: 按索引表打印单文件的字符串

SCR 布局 (详见 docs/SCR脚本格式.md):
    [0x00,0x2C)          头 (含密钥 +0x0C)
    [0x2C,tbl)           字节码/数据区 (明文)
    [tbl, tbl+4N)        字符串偏移表 (明文, offs[i] 相对 tbl, 恒有 offs[0]=4N)
    [tbl+4N, opoff)      字符串区 (加密; 顺序存 N 个 0x00 结尾串; 尾部明文填充)
    [opoff, opoff+ncmd)  opcode 字节 (明文)
    [ALIGN(opoff+ncmd,4), +4*ncmd)  args 数组 (明文) = 文件末尾
    (扩容时, 新串明文追加在文件末尾之后)

编码: 码表映射。汉字区的码位由 MappingGen 重新分配过(简繁互换/填空洞),
      一律查 font/font.tbl; ASCII/假名/标点等用原 cp932 码位。
      字符<->码位的唯一权威实现是根目录的 char.py, 字库生成共用同一份规则。

加密 (仅字符串区):
    密 = ((((明 ^ K0) + K1) & 0xFF) ^ K2) - K3) & 0xFF
    明 = ((((密 + K3) & 0xFF) ^ K2) - K1) & 0xFF) ^ K0
    密钥 K0..K3 = 文件头 +0x0C

写回默认【只重建字符串索引表】, opcode/args 区一个字节都不动。
  依据 (2026-09-28 实机验证):
    只重建索引表                -> 游戏正常
    额外平移消息类指令的 arg     -> 闪退 (等长重排也一样)
  数据上也说不通: op=5 的 arg 落在字符串区的比例只有 4.81%, 比随机基准 11.7% 还低,
  "恰好指向串起点"的 44 个也在随机范围内 => 那些"看着像文件偏移"的 args
  绝大多数是数值巧合。游戏取文本走的是索引表 (sub_159A5C = script + tbl + offs[i])。
  => 好处: 文本可以自由变长, 不必担心"串移动把引用搞坏"。
  (--fix-args 保留旧行为: 额外平移 MSG_OPS 里指向串的参数, 仅供实验, 默认不用)
"""
import sys, os, struct
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import char as charm                                # 码位映射（和 ELF 文本共用同一套）

# bat 里设了 PYTHONIOENCODING=gbk（cmd 936 码页），报错信息里可能有日文汉字，
# 直接 print 会报 UnicodeEncodeError，这里兜一下底。
try:
    sys.stdout.reconfigure(errors='replace')
except Exception:
    pass

# 消息类指令: aScript::SetScript @0x159E0C 里"把 arg 注册进资源表"的 opcode。
#
# 【只给 --fix-args 实验用】默认不启用 —— 实测平移这些参数会导致游戏闪退，
# 详见文首"写回默认只重建字符串索引表"那段。保留这份清单是为了将来复现实验。
#
# 依据 (IDA 反汇编):
#   op=2/5/10/14 -> sub_1593B0  (结构体类型标记 v6 = 0)
#   op=3         -> sub_159358
#   op=1         -> sub_159300  (类型标记 v6 = 1)  <- 和 sub_1593B0 是同一族函数，
#                              只有那个标记不同，arg 走 $a2 一路传下去
#   三者都: sub_15924C -> sub_158024 -> sub_157D40
#           sub_157D40 拿 arg 当 key 在资源表里查/新建表项。
MSG_OPS = frozenset((1, 2, 3, 5, 10, 14))

# 码位映射：直接用 char.py 的成品 converter（和 ELF 文本共用同一套规则）：
#   等价替换(·→・、—→─ 等) -> 查码表映射成该码位的"日文等值字符" -> cp932 编码，
#   编出来的字节就是码表里的码位。
# char.MAP_PATH 默认是 Path('font.tbl')（相对当前目录），这里改成相对本脚本的
# 绝对路径，免得换个目录跑就找不到码表。必须在建 converter 之前设好。
# 写回前记得先跑一遍 重建字库.bat，保证字库和码表是同一份。
charm.MAP_PATH = Path(HERE) / 'font' / 'font.tbl'

_CONV = None


def _conv():
    """char.py 的 converter，只建一次（内部会 load_map，单次 ~13ms）。"""
    global _CONV
    if _CONV is None:
        _CONV = charm.make_translation_converter()
    return _CONV


def enc_text(s):
    """文本 -> (字节, [编码不了的字符])

    直接用 char.make_translation_converter，规则：
      1) 先做等价替换（·→・、—→─ 等）
      2) 码位 < 0x889F 的字符直接用它的 cp932 码位
      3) 其余查码表，把它映射成"该码位的日文等值字符"，再 cp932 编码

    char.py 编不出来的字会降级成半角 '?'，并追加进 badchars.txt，
    所以这里恒返回空清单（不再中断写回）。
    """
    return _conv()(s).encode("cp932"), []

def dec_text(b):
    """字节 -> 文本。

    原版文本是标准 Shift-JIS，直接 cp932 解码即可（码表只用于编码方向：
    中文 -> 码位）。出现坏字节时用 replace 兜底，不抛异常中断提取。
    """
    try:
        return b.decode("cp932")
    except UnicodeDecodeError:
        return b.decode("cp932", "replace")

# ------------------------------------------------------------------ 基础

def _u32(d, o):
    return struct.unpack_from('<I', d, o)[0]

def key_of(d):
    return d[0x0C], d[0x0D], d[0x0E], d[0x0F]

def dec_byte(x, k):
    k0, k1, k2, k3 = k
    return (((((x + k3) & 0xFF) ^ k2) - k1) & 0xFF) ^ k0

def enc_byte(y, k):
    k0, k1, k2, k3 = k
    return (((((y ^ k0) + k1) & 0xFF) ^ k2) - k3) & 0xFF

def dec_bytes(bs, k):
    return bytes(dec_byte(b, k) for b in bs)

def enc_bytes(bs, k):
    return bytes(enc_byte(b, k) for b in bs)

def parse(d):
    """解析头部; 失败返回 None"""
    if len(d) < 0x2C or d[:3] != b'SCR':
        return None
    h = dict(N=_u32(d, 0x10), tbl=_u32(d, 0x14), ncmd=_u32(d, 0x18),
             opoff=_u32(d, 0x1C), args_off=0)
    if not (0x2C <= h['tbl'] < len(d) and h['tbl'] + 4 * h['N'] <= h['opoff'] <= len(d)):
        return None
    h['args_off'] = (h['opoff'] + h['ncmd'] + 3) & ~3
    if h['args_off'] + 4 * h['ncmd'] > len(d):
        return None
    return h

def read_str_at(d, addr, opoff, k):
    """按游戏语义读一个 0x00 结尾串: 区内=解密读; 区外(溢出区)=明文读"""
    out = bytearray()
    p = addr
    n = len(d)
    decrypt = addr < opoff
    while p < n:
        b = d[p]
        if decrypt:
            b = dec_byte(b, k)
        if b == 0:
            break
        out.append(b)
        p += 1
    return dec_text(bytes(out))

def strings_of(d):
    """按引擎语义读全部字符串(完全按结构, 不做任何扫描)。

    引擎的解密器 sub_159B08 是: 取第 0 条串的地址, 然后【顺序】读 N 个
    0x00 结尾串(每读一条跳过一个 0)。这里用同样的顺序读法,
    并与索引表逐条交叉校验(第 i 条的起点必须 == tbl+offs[i]);
    只要有一处不符就回退到"按索引表逐条读"(兼容本工具自己的扩容文件)。
    """
    h = parse(d)
    if h is None:
        return None
    N, tbl, opoff, k = h['N'], h['tbl'], h['opoff'], key_of(d)
    if N == 0:
        return []
    offs = [_u32(d, tbl + 4 * i) for i in range(N)]
    starts = [tbl + o for o in offs]

    # --- 顺序读(与解密器 sub_159B08 一致) ---
    out = []
    p = starts[0]
    for i in range(N):
        if p != starts[i]:           # 与索引表不符 -> 顺序不可信
            break
        buf = bytearray()
        while p < opoff:
            b = dec_byte(d[p], k)
            if b == 0:
                break
            buf.append(b)
            p += 1
        out.append(dec_text(bytes(buf)))
        p += 1
    if len(out) == N:
        return out

    # --- 回退: 按索引表逐条读(处理扩容溢出串) ---
    return [read_str_at(d, a, opoff, k) for a in starts]

# ------------------------------------------------------------------ 文本文件

def read_lines(path):
    with open(path, 'r', encoding='utf-8-sig', newline='') as f:
        t = f.read()
    if '\r' in t:
        t = t.replace('\r\n', '\n').replace('\r', '\n')
    lines = t.split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    return lines

def write_lines(path, strs):
    with open(path, 'w', encoding='utf-8-sig', newline='\n') as f:
        for s in strs:
            f.write(s + '\n')

# ------------------------------------------------------------------ 回写引擎

def repack(d, lines, fix_args=False):
    """
    重建 SCR。返回 (新字节串, 统计dict)。
    - 字符串区保持原大小, 顺序重排(紧凑);
    - 放不下的串追加到文件末尾(明文), 并重定位其索引表项与所有绝对引用。

    fix_args=False (默认): 只重建"字符串索引表", opcode/args 区一个字节都不动
    fix_args=True  (--fix-args, 备用): 额外把消息类指令(MSG_OPS)里指向串的参数平移

    【为什么默认不动 args】
      实测(2026-09-28): 只重建索引表 -> 游戏正常;
      额外平移 args(等长重排也一样) -> 游戏闪退。
      数据上也说不通: op=5 的 arg 落在字符串区的比例只有 4.81%,
      比随机基准 11.7% 还低, "恰好指向串起点"的 44 个也在随机范围内。
      => 那些"看着像文件偏移"的 args 绝大多数是数值巧合, 不是引用;
         游戏取文本走的是索引表 (sub_159A5C = script + tbl + offs[i])。
         去平移它们纯属帮倒忙。
    """
    h = parse(d)
    if h is None:
        raise ValueError('不是有效的 SCR')
    N, tbl, ncmd, opoff = h['N'], h['tbl'], h['ncmd'], h['opoff']
    aoff = h['args_off']
    if len(lines) != N:
        raise ValueError('行数 %d != 原字符串数 %d' % (len(lines), N))
    k = key_of(d)
    R = opoff - (tbl + 4 * N)                 # 原字符串区容量
    if N == 0:
        if any(lines):
            raise ValueError('该脚本无字符串表(N=0), 不能写入文本')
        return bytes(d), dict(moved=0, overflow=0, refs=0)

    # ---- 旧布局信息 ----
    base_end = aoff + 4 * ncmd                 # 主体末尾(= args 数组末尾)
    old_offs = [_u32(d, tbl + 4 * i) for i in range(N)]
    old_start = [tbl + o for o in old_offs]
    old_enc = []
    for i in range(N):
        a = old_start[i]
        p = a
        if a < opoff:                          # 区内: 解密读, 以明文 0 结尾
            while p < opoff and dec_byte(d[p], k) != 0:
                p += 1
            old_enc.append(dec_bytes(d[a:p], k))
        else:                                  # 溢出池: 明文读(上次扩容留下的)
            while p < len(d) and d[p] != 0:
                p += 1
            old_enc.append(bytes(d[a:p]))
    old_len = [len(b) for b in old_enc]
    # 原区尾部(最后一个"区内"串的结束符之后..opoff), 保留非零残留;
    # 末尾的 0x00 填充一律丢弃并在下面重新生成 —— 否则"改短再改长"时
    # 填充会越滚越多, 导致本可放下的串被误判为溢出。
    last = max([s for s in old_start if s < opoff], default=tbl + 4 * N)
    p = last
    while p < opoff and dec_byte(d[p], k) != 0:
        p += 1
    tail = d[p + 1:opoff].rstrip(b'\x00')

    # ---- 新字符串编码 ----
    enc = []
    for i, s in enumerate(lines):
        b, bad = enc_text(s)
        if b is None or bad:
            raise ValueError('无法编码的字符: %s' % ''.join(bad[:8]))
        enc.append(b)
    new_len = [len(b) for b in enc]

    # ---- 放置策略 ----
    # 区内必须恰好含 N 个 0 结尾串(解密器顺序扫描 N 个), 因此:
    #   * 能放下的串按顺序紧凑排列;
    #   * 放不下的串在区内留 1 字节空串占位, 内容(明文)追加到文件末尾。
    # 若总需求超过容量, 优先把"最长的串"移出(每次溢出可省 len 字节), 直到能装下。
    cap = R - len(tail)
    need_all = sum(len(b) + 1 for b in enc)
    over_set = set()
    if need_all > cap:
        freed = 0
        # 【下标 0 的串绝对不能溢出】游戏解密器 sub_159B08 是从"串0的地址"开始
        # 顺序解密的(遇到"解密后为 0"的字节才算一条串)。串0一旦被挪到区外(明文区),
        # 明文里的 0x00 解密出来不是 0, 解密器就永远停不下来, 会一路冲出文件 -> 黑屏。
        # (2026-09-28 实测踩过: 把 0280 全部 33 条串都挪到末尾, 游戏直接黑屏)
        cands = sorted((j for j in range(N) if j != 0), key=lambda j: -len(enc[j]))
        for i in cands:
            if need_all - freed <= cap:
                break
            freed += len(enc[i])          # 溢出串把 (len+1) 换成 1, 省 len
            over_set.add(i)
        if need_all - freed > cap:
            raise ValueError('字符串区容量不足(即使全部溢出也无法装下 %d 个占位)' % N)

    region = bytearray()
    new_offs = [0] * N
    overflow = []
    for i in range(N):
        if i in over_set:
            overflow.append(i)
            new_offs[i] = None
            region += enc_bytes(b'\x00', k)          # 占位空串
        else:
            new_offs[i] = 4 * N + len(region)        # 索引相对 tbl: 区从 tbl+4N 开始
            region += enc_bytes(enc[i] + b'\x00', k)
    # 尾部(原样) + 零填充
    if len(region) + len(tail) <= R:
        region += tail
    region += b'\x00' * (R - len(region))
    if len(region) != R:
        raise ValueError('字符串区排布失败(容量不足)')

    # ---- 溢出区: 追加到文件末尾(明文) ----
    # 先裁掉上一次扩容留下的旧溢出池, 保证反复回写结果稳定(幂等)
    out = bytearray(d[:base_end])
    while len(out) % 4:
        out.append(0)
    for i in overflow:
        new_offs[i] = len(out) - tbl
        out += enc[i] + b'\x00'

    # ---- 写回索引表 + 字符串区 ----
    if N:
        for i in range(N):
            struct.pack_into('<I', out, tbl + 4 * i, new_offs[i])
    out[tbl + 4 * N:opoff] = region

    # ---- 重定位绝对引用 ----
    # 默认(fix_args=False)只统计"哪些串的地址变了"(moved, 给报告用);
    # 下面 remap / MSG_OPS 那套只有 --fix-args 实验才会真正执行。
    new_start = [tbl + o for o in new_offs]

    def remap(addr):
        """旧绝对地址 -> 新绝对地址; 找不到返回 None"""
        for j in range(N):
            a = old_start[j]
            if a <= addr <= a + old_len[j]:
                off = addr - a
                if off > new_len[j]:
                    off = new_len[j]
                return new_start[j] + off
        return None

    refs = 0
    args_moved = []                            # (arg序号, 旧值, 新值)
    moved = [j for j in range(N) if new_start[j] != old_start[j]]
    # 逐条指令取参数: 只有消息类指令(MSG_OPS)的参数可能是指向文本的偏移;
    # 落在旧串字节区间内 -> 按串内偏移平移。其余指令参数为 ID/标量, 不动。
    if fix_args:
        ops = d[opoff:opoff + ncmd]
        for i in range(ncmd):
            if ops[i] not in MSG_OPS:
                continue
            pos = aoff + 4 * i
            v = _u32(out, pos)
            nv = remap(v)
            if nv is not None and nv != v:
                struct.pack_into('<I', out, pos, nv)
                refs += 1
                args_moved.append((i, v, nv))

    return bytes(out), dict(moved=len(moved), overflow=len(overflow), refs=refs,
                            args_moved=args_moved)

# ------------------------------------------------------------------ 目录扫描

def walk_scr(root):
    for dirpath, _, files in os.walk(root):
        for fn in sorted(files):
            if fn.lower().endswith('.scr'):
                yield os.path.join(dirpath, fn)

# ---------------------------------------------------------------- 提取

def cmd_m(indir, outdir):
    """合并提取: 按脚本编号的【连续段】分组合并, 每段一个 txt"""
    os.makedirs(outdir, exist_ok=True)

    # 1) 扫描全部脚本: 编号(全部, 用于分段) + 内容(有文本的)
    ids_all = []
    items = []                       # (id, relpath, strs)
    n_empty = 0
    for p in walk_scr(indir):
        base = os.path.splitext(os.path.basename(p))[0]
        try:
            idn = int(base, 16)
        except ValueError:
            continue
        ids_all.append(idn)
        d = open(p, 'rb').read()
        h = parse(d)
        if h is None:
            continue
        strs = strings_of(d)
        if strs is None:
            continue
        if not strs or all(s == '' for s in strs):
            n_empty += 1
            continue
        rel = os.path.relpath(p, indir).replace(os.sep, '/')
        items.append((idn, rel, strs))
    items.sort(key=lambda x: x[0])
    ids_all.sort()

    # 2) 按【全部脚本】编号的物理连续性分段(无文本文件不造成断裂)
    segs = []                        # [lo, hi]
    for idn in ids_all:
        if segs and idn == segs[-1][1] + 1:
            segs[-1][1] = idn
        else:
            segs.append([idn, idn])
    los = [s[0] for s in segs]
    import bisect as _bs

    def seg_of(idn):
        i = _bs.bisect_right(los, idn) - 1
        return i if i >= 0 and segs[i][0] <= idn <= segs[i][1] else -1

    # 3) 有文本的文件按段归类
    groups = [None] * len(segs)      # seg_index -> [items]
    for it in items:
        i = seg_of(it[0])
        if i < 0:
            continue
        if groups[i] is None:
            groups[i] = []
        groups[i].append(it)

    # 4) 逐段写文件; 段内内容完全相同的脚本只存一份
    entries = []                     # (rel, 段文件, 起始行(0基), 行数)
    seg_info = []                    # (段文件名, 行数, 脚本数)
    for i, g in enumerate(groups):
        if not g:
            continue
        name = ('%04X.txt' % segs[i][0]) if segs[i][0] == segs[i][1] \
            else ('%04X-%04X.txt' % (segs[i][0], segs[i][1]))
        lines_out = []
        seen = {}
        for idn, rel, strs in g:
            key = tuple(strs)
            if key in seen:
                entries.append((rel, name, seen[key], len(strs)))
                continue
            seen[key] = len(lines_out)
            entries.append((rel, name, len(lines_out), len(strs)))
            lines_out += strs
        write_lines(os.path.join(outdir, name), lines_out)
        seg_info.append((name, len(lines_out), len(g)))

    # 5) lines.list
    entries.sort(key=lambda e: e[0])
    with open(os.path.join(outdir, 'lines.list'), 'w',
              encoding='utf-8-sig', newline='\n') as f:
        for rel, name, st, ct in entries:
            f.write('%s %s %d %d\n' % (rel, name, st, ct))

    # 6) 报告
    total_lines = sum(n for _, n, _ in seg_info)
    print('合并提取 -> %s' % outdir)
    print('  脚本 %d 个 (全空跳过 %d) -> 物理连续段 %d 个, 其中有文本的 %d 个'
          % (len(items), n_empty, len(segs), len(seg_info)))
    print('  文本行数: %d' % total_lines)
    print('  最大的段文件:')
    for name, n, cnt in sorted(seg_info, key=lambda x: -x[1])[:10]:
        print('    %-16s %5d 行  (%3d 个脚本)' % (name, n, cnt))
    print('  lines.list: %d 条映射' % len(entries))

# ---------------------------------------------------------------- 回写

def write_refs_log(txtdir, args_log):
    """记录被平移的消息指令参数(只有 --fix-args 实验时才会有内容), 便于审计"""
    if args_log:
        with open(os.path.join(txtdir, 'refs.args.list'), 'w',
                  encoding='utf-8-sig', newline='\n') as f:
            f.write('# 文件 args序号 旧值 新值  (消息类指令中随串移动被平移的参数)\n')
            for rel, i, a, b in sorted(args_log):
                f.write('%s %d %#x %#x\n' % (rel, i, a, b))

def dest_path(p, indir, outdir):
    """回写目标路径。outdir=None(或与 indir 相同) = 就地覆盖。"""
    if not outdir or os.path.abspath(outdir) == os.path.abspath(indir):
        return p
    q = os.path.join(outdir, os.path.relpath(p, indir))
    d = os.path.dirname(q)
    if d:
        os.makedirs(d, exist_ok=True)
    return q

def cmd_i(indir, txtdir, outdir=None, fix_args=False):
    """回写: 按 lines.list 把段文件的连续若干行写回对应 .scr"""
    listfile = os.path.join(txtdir, 'lines.list')
    if not os.path.exists(listfile):
        print('  找不到 lines.list (回写只支持合并模式, 请先用 m 命令提取):', listfile)
        return 1
    entries = []
    with open(listfile, 'r', encoding='utf-8-sig') as f:
        for ln in f:
            ln = ln.rstrip('\n')
            if not ln.strip():
                continue
            parts = ln.rsplit(None, 3)          # 路径里可能有空格 -> 从右切
            if len(parts) != 4:
                print('  lines.list 格式错:', ln)
                continue
            rel, name, st, ct = parts
            entries.append((rel, name, int(st), int(ct)))

    cache = {}
    n_ok = n_skip = n_fail = 0
    t_moved = t_over = t_refs = 0
    args_log = []
    for rel, name, st, ct in entries:
        rp = rel.replace('/', os.sep)
        p = os.path.join(indir, rp)
        if not os.path.exists(p):                 # 兼容 "A/xxxx.scr" 式路径
            p = os.path.join(indir, 'A', rp)
        if not os.path.exists(p):
            n_skip += 1
            continue
        if name not in cache:
            cp = os.path.join(txtdir, name)
            if not os.path.exists(cp):
                print('  缺少章文件:', name)
                n_fail += 1
                continue
            cache[name] = read_lines(cp)
        lines = cache[name]
        if st + ct > len(lines):
            print('  行号越界 %s: %s[%d:%d] 但文件只有 %d 行' % (rel, name, st, st + ct, len(lines)))
            n_fail += 1
            continue
        chunk = lines[st:st + ct]

        d = open(p, 'rb').read()
        if parse(d) is None:
            print('  跳过(解析失败):', rel)
            n_fail += 1
            continue
        try:
            new, stt = repack(d, chunk, fix_args)
        except (ValueError, UnicodeEncodeError) as ex:
            print('  失败 %s: %s' % (rel, ex))
            n_fail += 1
            continue
        q = dest_path(p, indir, outdir)
        if new != d or q != p:
            open(q, 'wb').write(new)
        n_ok += 1
        t_moved += stt['moved']; t_over += stt['overflow']; t_refs += stt['refs']
        if stt.get('args_moved'):
            for i, oldv, newv in stt['args_moved']:
                args_log.append((rel, i, oldv, newv))

    print('回写(合并模式): 成功 %d, 文件缺失跳过 %d, 失败 %d' % (n_ok, n_skip, n_fail))
    if t_moved:
        print('  重定位: 移动字符串 %d, 溢出到文件尾 %d, 修正 args 引用 %d'
              % (t_moved, t_over, t_refs))
    write_refs_log(txtdir, args_log)
    return n_fail

# ---------------------------------------------------------------- 调试 / 入口

def cmd_d(path):
    d = open(path, 'rb').read()
    h = parse(d)
    strs = strings_of(d)
    if h is None or strs is None:
        print('解析失败:', path); return
    print('# %s N=%d tbl=%#x opoff=%#x ncmd=%d' % (path, h['N'], h['tbl'], h['opoff'], h['ncmd']))
    for i, s in enumerate(strs):
        print('[%d] %s' % (i, s))

def main():
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    c = sys.argv[1]
    nfail = 0
    if c == 'm' and len(sys.argv) >= 4: cmd_m(sys.argv[2], sys.argv[3])
    elif c == 'i' and len(sys.argv) >= 4:
        rest = [a for a in sys.argv[4:] if not a.startswith('--')]
        fix = '--fix-args' in sys.argv          # 默认不动 args（见 repack 注释）
        outdir = rest[0] if rest else None
        if fix:
            print('  (--fix-args: 额外平移 MSG_OPS 里指向串的参数 —— 默认不做，'
                  '实测会闪退，仅供实验)')
        nfail = cmd_i(sys.argv[2], sys.argv[3], outdir, fix) or 0
    elif c == 'd' and len(sys.argv) >= 3: cmd_d(sys.argv[2])
    else:
        print(__doc__); sys.exit(1)
    sys.exit(1 if nfail else 0)

if __name__ == '__main__':
    main()
