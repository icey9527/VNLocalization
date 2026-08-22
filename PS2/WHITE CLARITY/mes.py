import sys
import os
import re
from pathlib import Path

import char

char.MAP_PATH = Path('font/font.tbl')
JP = re.compile('[\u3000-\uFFE6]')

LINE_JOIN = b'\x00\xd5'                      # 块内换行: 行尾 00 + 分隔 d5
BLOCK_MARKS = (b'\xd0\x02', b'\xd0\x00')     # 块刷新(等待点击+清框)命令
NAME_MARKS = (b'\xd0\x1c', b'\xd0\x1b')      # 人名 / 章节标题槽
CHOICE_MARK = b'\xd0\x07'                    # 选项命令


def is_ctrl(b):
    return b <= 0x1F or 0xD0 <= b <= 0xDF or b >= 0xFD


def is_lead(b):
    return 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC


def strings(data):
    i = 0
    while i < len(data):
        if is_ctrl(data[i]):
            j = i
            while j < len(data) and is_ctrl(data[j]):
                j += 1
        else:
            j = i
            while j < len(data) and not is_ctrl(data[j]):
                j += 2 if is_lead(data[j]) else 1
            yield i, j, data[i:j].decode('cp932', 'ignore')
        i = j


def events(data):
    """[(kind, start, end)]，kind='C' 控制码连续段 / 'T' 文本段"""
    i, ev = 0, []
    while i < len(data):
        if is_ctrl(data[i]):
            j = i
            while j < len(data) and is_ctrl(data[j]):
                j += 1
            ev.append(('C', i, j))
        else:
            j = i
            while j < len(data) and not is_ctrl(data[j]):
                j += 2 if is_lead(data[j]) else 1
            ev.append(('T', i, j))
        i = j
    return ev


def jp_slots(data):
    """日文槽列表: [(start, end, text, pre_ctrl)]"""
    ev = events(data)
    out = []
    for k, (t, a, b) in enumerate(ev):
        if t != 'T':
            continue
        s = data[a:b].decode('cp932', 'ignore')
        if not JP.search(s):
            continue
        pre = data[ev[k-1][1]:ev[k-1][2]] if k > 0 and ev[k-1][0] == 'C' else b''
        out.append((a, b, s, pre))
    return out


def group_slots(slots):
    """槽分组: 人名/标题/选项槽各自独立，正文按对话块(刷新命令之间)合并。
    返回组列表，每组为 slots 下标列表。"""
    groups, choice_mode = [], False
    for n, (a, b, s, pre) in enumerate(slots):
        if any(m in pre for m in NAME_MARKS):
            groups.append([n])
            choice_mode = False
            continue
        if any(m in pre for m in BLOCK_MARKS):
            groups.append([n])
            choice_mode = CHOICE_MARK in pre
        elif pre != LINE_JOIN or choice_mode:
            groups.append([n])
        else:
            groups[-1].append(n)
    return groups


def make_encoder():
    table = {}
    for raw in Path('font/font.tbl').read_text(encoding='utf-16').splitlines():
        m = char.MAP_LINE_RE.match(raw)
        if not m:
            continue
        code = int(m.group(1), 16)
        rhs = m.group(2).replace('\\\\', '\\')
        table[rhs] = code.to_bytes(2, 'big') if code > 0xFF else bytes([code])

    def enc(line):
        out = bytearray()
        for ch in char.apply_replace_rules(line):
            if char.cp932_code(ch) is not None and not char.is_cp932_proxy_char(ch):
                out += ch.encode('cp932')
            elif ch in table:
                out += table[ch]
            else:
                char.log_bad_chars([ch])
                out += '？'.encode('cp932')
        return bytes(out)

    return enc


# ---------------- 提取（按块合并） ----------------

def extract_merged(data):
    """一个对话块 -> 一条 txt 行；块内原有的强制换行保留为 \n 标记"""
    slots = jp_slots(data)
    return ['\\n'.join(slots[i][2] for i in g) for g in group_slots(slots)]


# ---------------- 插回（按块重排） ----------------

NO_START = '、。，！？…―ー」』）］》〉”’'
NO_END = '「『（［《〈“‘'


def _greedy(text, cap):
    lines, p = [], text
    while len(p) > cap:
        cut = cap
        while cut > 1 and p[cut] in NO_START:
            cut -= 1
        while cut > 1 and p[cut - 1] in NO_END:
            cut -= 1
        lines.append(p[:cut])
        p = p[cut:]
    lines.append(p)
    return lines


def split_lines(text, count, cap):
    """把合并后的译文流式重排到 count 个显示行、每行至多 cap 字。
    译文里的 \n 为显式断行，优先尊重；放不下时整体重排。返回 (行列表, 是否忽略显式断行)。"""
    parts = text.split('\\n')
    rough = []
    for p in parts:
        rough.extend(_greedy(p, cap) if len(p) > cap else [p])
    ignored = False
    if len(rough) > count:
        ignored = True
        rough = _greedy(''.join(parts), cap)
        if len(rough) > count:
            return None, ignored
    rough += [''] * (count - len(rough))
    return rough[:count], ignored
    rough += [''] * (count - len(rough))
    return rough[:count]


def insert_merged(data, lines, name, enc):
    slots = jp_slots(data)
    groups = group_slots(slots)
    if len(groups) != len(lines):
        raise SystemExit(f'{name}: txt has {len(lines)} lines, expect {len(groups)} '
                         f'({len(slots)} slots in {len(groups)} groups)')
    cap = max((len(s) for _, _, s, _ in slots), default=0)
    parts = [None] * len(slots)
    for gi, (g, line) in enumerate(zip(groups, lines)):
        if len(g) == 1:
            parts[g[0]] = line
            continue
        cut, ignored = split_lines(line, len(g), cap)
        if cut is None:
            raise SystemExit(f'{name}: line {gi + 1} too long for {len(g)}x{cap}: '
                             f'{line[:24]}...')
        if ignored:
            print(f'[警告] {name}: 第{gi + 1}行的显式断行放不下，已自动重排: '
                  f'{line[:24]}...')
        parts[g[0]:g[-1] + 1] = cut
    out, pos = bytearray(), 0
    for (a, b, s, pre), part in zip(slots, parts):
        out += data[pos:a]
        out += enc(part)
        pos = b
    return bytes(out + data[pos:])


def verify(orig, new, name):
    """控制码字节流必须逐字节一致（文本段允许变长/变空）"""
    co = b''.join(orig[a:b] for t, a, b in events(orig) if t == 'C')
    cn = b''.join(new[a:b] for t, a, b in events(new) if t == 'C')
    if co != cn:
        n = min(len(co), len(cn))
        for i in range(n):
            if co[i] != cn[i]:
                raise SystemExit(f'{name}: ctrl differs at byte {i}: '
                                 f'{co[i]:02X} vs {cn[i]:02X}')
        raise SystemExit(f'{name}: ctrl length {len(co)} vs {len(cn)}')


def main():
    if sys.argv[1] == 'e':
        src, dst = sys.argv[2], sys.argv[3]
        os.makedirs(dst, exist_ok=True)
        for name in sorted(os.listdir(src)):
            if name.endswith('.mes'):
                lines = extract_merged(open(os.path.join(src, name), 'rb').read())
                if lines:
                    with open(os.path.join(dst, name[:-4] + '.txt'), 'w',
                              encoding='utf-8-sig') as f:
                        f.write('\n'.join(lines))
    else:
        src, txt, dst = sys.argv[2], sys.argv[3], sys.argv[4]
        enc = make_encoder()
        os.makedirs(dst, exist_ok=True)
        errors, done = [], set()
        for name in sorted(os.listdir(txt)):
            if not name.endswith('.txt'):
                continue
            base = name[:-4]
            if not os.path.exists(os.path.join(src, base + '.mes')):
                errors.append(f'{name}: no matching mes')
                continue
            data = open(os.path.join(src, base + '.mes'), 'rb').read()
            with open(os.path.join(txt, name), encoding='utf-8-sig') as f:
                lines = f.read().split('\n')
            if lines and not lines[-1]:
                lines.pop()
            try:
                new = insert_merged(data, lines, name, enc)
                verify(data, new, name)
            except SystemExit as e:
                errors.append(str(e))
                continue
            with open(os.path.join(dst, base + '.mes'), 'wb') as f:
                f.write(new)
            done.add(base + '.mes')
        for name in sorted(os.listdir(src)):
            if name.endswith('.mes') and name not in done:
                with open(os.path.join(src, name), 'rb') as f:
                    data = f.read()
                with open(os.path.join(dst, name), 'wb') as f:
                    f.write(data)
        if errors:
            raise SystemExit('\n'.join(errors))


if __name__ == '__main__':
    main()
