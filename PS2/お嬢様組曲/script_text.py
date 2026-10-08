"""PS2 Sweet Concert: export/import scene text without index files."""
from collections import defaultdict
import json
from pathlib import Path
import re
import struct
import sys
import char

char.MAP_PATH = Path('font/font.tbl')


# Display nameplate IDs. Add confirmed names here.
SPEAKERS = {
  1: "姫名子",
  2: "司",
  3: "香津美",
  4: "沙絵",
  5: "小雪",
  6: "舞鈴",
  7: "睦子",
  8: "裕理",
  9: "綾瀬",
  10: "薫",
  11: "スーザン",
  12: "ナンシー",
  13: "ピエール",
  14: "フランソワーズ",
  15: "チャボ",
  16: "女の声",
  17: "男の声",
  18: "女の子",
  19: "女の人",
  20: "男の子",
  21: "男の人",
  22: "父",
  23: "母",
  24: "祖母",
  25: "祖父",
  26: "妹",
  27: "弟",
  28: "姉",
  29: "兄",
  30: "叔母",
  31: "叔父",
  32: "女生徒",
  33: "教師",
  34: "先生",
  35: "猫",
  36: "アナウンス",
  37: "執事",
  38: "ウェイトレス",
  39: "ウェイター",
  40: "おじさん",
  41: "おばさん",
  42: "女生徒A",
  43: "女生徒B",
  44: "女生徒C",
  45: "女生徒D",
  46: "女生徒E",
  47: "女生徒たち",
  48: "文恵",
  49: "西村",
  50: "美鈴",
  51: "声",
  52: "泣き声",
  53: "相河",
  54: "一ノ瀬",
  55: "宇田川",
  56: "笹原",
  57: "白河",
  58: "瀬口",
  59: "瀬能",
  60: "母親",
  61: "父親",
  62: "門下生A",
  63: "門下生B",
  64: "店の人",
  65: "管理人",
  66: "薫＆香津美",
  67: "薫＆沙絵",
  68: "香津美＆睦子",
  69: "薫＆睦子",
  70: "女生徒達",
  71: "一般生徒",
  72: "下級生A",
  73: "下級生B",
  74: "下級生C",
  75: "上級生A",
  76: "上級生B",
  77: "上級生C",
  78: "?",
  79: "???",
  80: "ニワトリ",
  81: "審判",
  82: "クラスメイト",
  83: "奈々瀬",
  101: "スタッフA",
  102: "スタッフB",
  103: "スタッフC"
}

def speaker_context(speaker):
    """tlk/tlknk call pt (hide), then nameplate with their first argument."""
    if speaker < 0 or 84 <= speaker <= 93 or speaker == 100:
        return ''
    if speaker in (94, 96, 97, 98, 99):
        speaker = 18
    elif speaker == 95:
        speaker = 19
    return SPEAKERS.get(speaker, str(speaker))


def decode(raw):
    """One physical line; preserve invalid and noncanonical cp932 bytes."""
    try:
        text = raw.decode('cp932')
        if text.encode('cp932') == raw:
            return text.replace('\\', '\\\\').replace('{', '\\{').replace('\r', '\\r').replace('\n', '\\n')
    except UnicodeError:
        pass
    out, pos = [], 0
    while pos < len(raw):
        width = 2 if 0x81 <= raw[pos] <= 0x9F or 0xE0 <= raw[pos] <= 0xFC else 1
        chunk = raw[pos:pos + width]
        try:
            char = chunk.decode('cp932')
            if char.encode('cp932') != chunk:
                raise UnicodeError('noncanonical byte sequence')
        except UnicodeError:
            # An invalid lead must not swallow the following valid character.
            width, chunk, char = 1, raw[pos:pos+1], None
        if char is None:
            out.append('{' + chunk.hex().upper() + '}')
        else:
            out.append(char.replace('\\', '\\\\').replace('{', '\\{').replace('\r', '\\r').replace('\n', '\\n'))
        pos += width
    return ''.join(out)


def encode(line, converter=None):
    out, pos = bytearray(), 0
    while pos < len(line):
        char = line[pos]
        if char == '\\':
            pos += 1
            if pos >= len(line) or line[pos] not in '\\{rn':
                raise ValueError('invalid backslash escape; use \\\\ for a literal backslash')
            out.extend({'r': b'\r', 'n': b'\n', '\\': b'\\', '{': b'{' }[line[pos]])
        elif char == '{':
            end = line.find('}', pos)
            token = line[pos+1:end] if end >= 0 else ''
            if not token or len(token) % 2 or not re.fullmatch('[0-9a-fA-F]+', token):
                raise ValueError('expected raw bytes such as {8140}; use \\{ for a literal brace')
            out.extend(bytes.fromhex(token))
            pos = end
        else:
            end = pos + 1
            while end < len(line) and line[end] not in '\\{':
                end += 1
            text = line[pos:end]
            out.extend(converter(text) if converter else text.encode('cp932'))
            pos = end - 1
        pos += 1
    if 0 in out:
        raise ValueError('00 is the string terminator and cannot appear inside text')
    return bytes(out)


class Reader:
    def __init__(self, data):
        self.data, self.pos = data, 0
    def take(self, size):
        if self.pos + size > len(self.data):
            raise ValueError(f'truncated bytecode at {self.pos:#x}')
        result = self.data[self.pos:self.pos+size]
        self.pos += size
        return result
    def byte(self):
        return self.take(1)[0]
    def expression(self):
        return [self.token() for _ in range(self.byte())]
    def token(self):
        typ = self.byte()
        kind = typ & 15
        if kind == 1:
            return ('int', self.take({1: 1, 2: 2}.get(typ >> 4, 4)))
        if kind == 2:
            return ('text', int.from_bytes(self.take(2), 'little'))
        if kind == 3:
            return ('nested', self.node())
        if kind == 4:
            return ('operator', self.byte())
        if kind == 6:
            return ('raw32', self.take(4))
        if kind == 7:
            return ('inline', self.take(self.byte()))
        raise ValueError(f'unknown token {typ:#x} at {self.pos-1:#x}')
    def node(self):
        opcode, argc = self.byte(), self.byte()
        return opcode, [self.expression() for _ in range(argc)]


class Script:
    def __init__(self, data):
        self.data = data
        u32 = lambda p: struct.unpack_from('<I', data, p)[0]
        self.code_size = u32(0)
        self.table = self.code_size + 8
        count = u32(self.code_size + 4)
        if not 0 < count <= 65536:
            raise ValueError('invalid string count')
        self.pool = self.table + 4*count
        offsets = [0] + [u32(self.table+4*i) for i in range(count-1)]
        pool_size = u32(self.table+4*(count-1))
        self.tail = self.pool + pool_size
        if not self.pool <= self.tail <= len(data):
            raise ValueError('invalid pool size')
        self.texts = []
        # Independent NUL split, then compare every segment against the offset table.
        pool_bytes = data[self.pool:self.tail]
        if not pool_bytes.endswith(b'\0'):
            raise ValueError('string pool has no final NUL')
        segments = pool_bytes[:-1].split(b'\0')
        for start, end in zip(offsets, offsets[1:] + [pool_size]):
            raw = data[self.pool+start:self.pool+end]
            if end <= start or not raw.endswith(b'\0') or b'\0' in raw[:-1]:
                raise ValueError('string boundaries do not match NUL terminators')
            self.texts.append(raw[:-1])
        if self.texts != segments:
            raise ValueError('NUL segments and offset table disagree')
        groups = defaultdict(list)
        label_count = u32(self.tail)
        names = self.tail+4+12*label_count
        for i in range(label_count):
            co, no, length = struct.unpack_from('<III', data, self.tail+4+12*i)
            if names+no+length > len(data):
                raise ValueError('invalid label name')
            groups[co].append(data[names+no:names+no+length].decode('cp932'))
        starts = sorted(groups)
        if not starts or starts[0] != 0 or starts[-1] >= self.code_size:
            raise ValueError('invalid code labels')
        self.scenes = {}
        self.entries = {}
        self.references = defaultdict(set)
        def collect_refs(node, location):
            op, expressions = node
            for expr in expressions:
                for kind, value in expr:
                    if kind == 'text':
                        if value >= count:
                            raise ValueError(f'invalid text id {value}')
                        self.references[value].add(location)
                    elif kind == 'nested':
                        collect_refs(value, location)
        for start, end in zip(starts, starts[1:] + [self.code_size]):
            reader = Reader(data[4+start:4+end])
            ids = []
            rows = []
            while reader.pos < len(reader.data):
                code_offset = start + reader.pos
                opcode, args = reader.node()
                collect_refs((opcode, args), f'{groups[start][-1]}@{code_offset:06X}')
                # Native text-setting instruction, also used by the item wrapper.
                if opcode == 0x6B and len(args) == 2 and len(args[1]) == 1 and args[1][0][0] == 'text':
                    tid = args[1][0][1]
                    ids.append(tid)
                    rows.append({'key': f'op6B_{len(rows):04X}',
                                 'original': decode(self.texts[tid]), 'translation': '',
                                 'stage': 0, 'context': ''})
                    continue
                if opcode != 7 or not args or len(args[0]) != 1 or args[0][0][0] != 'inline':
                    continue
                cmd = args[0][0][1]
                if cmd not in (b'mes', b'tlk', b'tlknk', b'item'):
                    continue
                expr = args[1] if cmd == b'item' else args[-1]
                if len(expr) != 1 or expr[0][0] != 'text':
                    raise ValueError(f'unsupported {cmd!r} text argument at code {start+reader.pos:#x}')
                tid = expr[0][1]
                if tid >= count:
                    raise ValueError(f'invalid text id {tid}')
                ids.append(tid)
                context = ''
                if cmd in (b'tlk', b'tlknk'):
                    if len(args[1]) != 1 or args[1][0][0] != 'int':
                        raise ValueError('unsupported speaker parameter')
                    speaker = int.from_bytes(args[1][0][1], 'little', signed=True)
                    context = speaker_context(speaker)
                rows.append({'key': f'{cmd.decode()}_{len(rows):04X}',
                             'original': decode(self.texts[tid]), 'translation': '',
                             'stage': 0, 'context': context})
            if ids:
                name = next((s for s in groups[start] if s.isascii()), groups[start][0])
                name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name).rstrip(' .')
                if name + '.json' in self.scenes:
                    raise ValueError(f'duplicate output name {name}')
                self.scenes[name + '.json'] = ids
                self.entries[name + '.json'] = rows

    def export(self, folder):
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        for name, rows in self.entries.items():
            content = json.dumps(rows, ensure_ascii=False, indent=2) + '\n'
            (folder/name).write_bytes(content.encode('utf-8'))
        return sum(map(len, self.scenes.values()))

    def rebuild(self, folder):
        changes = {}
        converter = None
        for name, ids in self.scenes.items():
            items = load_items(Path(folder)/name, self.entries[name])
            for tid, expected in zip(ids, self.entries[name]):
                key = expected['key']
                item = items[key]
                if not isinstance(item.get('stage', 0), int):
                    raise ValueError(f'{name}:{key}: stage must be an integer')
                translated = item.get('stage', 0) != 0
                line = item.get('translation') if translated else item.get('original')
                if not isinstance(line, str):
                    raise ValueError(f'{name}:{key}: selected text must be a string')
                try:
                    if translated and converter is None:
                        converter = char.make_translation_converter()
                    raw = encode(line, converter if translated else None)
                except (ValueError, UnicodeError) as error:
                    raise ValueError(f'{name}:{key}: {error}') from error
                if tid in changes and changes[tid] != raw:
                    raise ValueError(f'{name}:{key}: conflicting edits for shared text id {tid}')
                changes[tid] = raw
        offsets, pool = [], bytearray()
        for tid, original in enumerate(self.texts):
            offsets.append(len(pool))
            pool.extend(changes.get(tid, original) + b'\0')
        table = offsets[1:] + [len(pool)]
        return self.data[:self.table] + struct.pack('<' + 'I'*len(table), *table) + pool + self.data[self.tail:]

def load_items(path, expected):
    rows = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(rows, list) or any(not isinstance(row, dict) or not isinstance(row.get('key'), str) for row in rows):
        raise ValueError(f'{path}: expected an array of keyed objects')
    items = {row['key']: row for row in rows}
    if len(items) != len(rows):
        raise ValueError(f'{path}: duplicate keys')
    wanted = {row['key'] for row in expected}
    if set(items) != wanted:
        raise ValueError(f'{path}: missing keys {sorted(wanted-set(items))}; unexpected keys {sorted(set(items)-wanted)}')
    return items


def script_files(folder):
    if not folder.is_dir():
        raise ValueError(f'not an input folder: {folder}')
    files = sorted(p for p in folder.rglob('*') if p.is_file() and p.name.lower() in ('script', 'script.bin'))
    if not files:
        raise ValueError('no script or script.bin found in input folder')
    if len({p.parent for p in files}) != len(files):
        raise ValueError('script and script.bin in one directory would share JSON filenames')
    return files


def separate_output(output, *inputs):
    for folder in inputs:
        if output.resolve().is_relative_to(folder.resolve()) or folder.resolve().is_relative_to(output.resolve()):
            raise ValueError('output folder and input folders must not contain each other')


def export_folder(source, output):
    separate_output(output, source)
    count, files = 0, 0
    for path in script_files(source):
        script = Script(path.read_bytes())
        count += script.export(output / path.parent.relative_to(source))
        files += len(script.scenes)
    print(f'Exported {files} UTF-8 JSON files, {count} entries.')


def import_folder(source, texts, output):
    separate_output(output, source, texts)
    rebuilt_files = {}
    for path in script_files(source):
        script = Script(path.read_bytes())
        rebuilt = script.rebuild(texts / path.parent.relative_to(source))
        if Script(rebuilt).scenes != script.scenes:
            raise ValueError('rebuilt script changed the scene mapping')
        rebuilt_files[path] = rebuilt
    # Validate edits before writing; preserve label and other companion files.
    for path in source.rglob('*'):
        if path.is_file():
            target = output / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(rebuilt_files[path] if path in rebuilt_files else path.read_bytes())
    print(f'Imported {len(rebuilt_files)} script files; companion files preserved.')


def main():
    args = sys.argv[1:]
    if not args or args[0] not in ('e', 'i') or len(args) != (4 if args[0] == 'i' else 3):
        print('Usage:\n  python script_text.py e INPUT_FOLDER OUTPUT_FOLDER\n  python script_text.py i ORIGINAL_FOLDER JSON_FOLDER OUTPUT_FOLDER')
        return 1
    try:
        if args[0] == 'e':
            export_folder(*map(Path, args[1:]))
        else:
            import_folder(*map(Path, args[1:]))
    except (ValueError, OSError, UnicodeError, struct.error) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
