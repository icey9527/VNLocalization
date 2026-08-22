import sys
from pathlib import Path


def main():
    source = Path(sys.argv[1])
    output = Path(sys.argv[2])
    texts = [path.read_text(encoding='utf-8') for path in sorted(source.rglob('*.txt'))]
    output.write_text('\n'.join(texts), encoding='utf-8-sig')
    print('%d files' % len(texts))


if __name__ == '__main__':
    main()
