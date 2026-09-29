import sys
import json
from pathlib import Path


def main():
    source = Path(sys.argv[1])
    output = Path(sys.argv[2])
    texts = [path.read_text(encoding='utf-8') for path in sorted(source.rglob('*.txt'))]
    for path in sorted(source.rglob('*.json')):
        value = json.loads(path.read_text(encoding='utf-8-sig'))
        def collect(item):
            if isinstance(item, str):
                texts.append(item)
            elif isinstance(item, list):
                for child in item:
                    collect(child)
            elif isinstance(item, dict):
                for child in item.values():
                    collect(child)
        collect(value)
    output.write_text('\n'.join(texts), encoding='utf-8-sig')
    print('%d text sources' % len(texts))


if __name__ == '__main__':
    main()
