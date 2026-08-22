import re
import sys
from pathlib import Path

from char import make_translation_converter


PATTERN = re.compile(r'[\u3000-\uFFE6]')
INDEX_NAME = 'lines.txt'


def read_text(path, encoding, errors='strict'):
    data = path.read_bytes()
    return data.decode(encoding, errors)


def write_text(path, text, encoding):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = text.encode(encoding)
    path.write_bytes(data)


def split_text_lines(text):
    lines = text.split('\n')

    if lines and lines[-1] == '':
        lines.pop()

    result = []
    for line in lines:
        if line.endswith('\r'):
            line = line[:-1]
        result.append(line)

    return result


def get_line_ending(line):
    if line.endswith('\r\n'):
        return '\r\n'
    if line.endswith('\n'):
        return '\n'
    if line.endswith('\r'):
        return '\r'
    return ''


def extract(source_directory, text_directory):
    index_lines = []
    source_files = sorted(source_directory.rglob('*.txt'))

    for source_path in source_files:
        relative_path = source_path.relative_to(source_directory)
        source_text = read_text(source_path, 'cp932', 'ignore')
        source_lines = split_text_lines(source_text)
        extracted_lines = []

        for line_number, line in enumerate(source_lines, 1):
            if not line:
                continue
            if line.startswith('#F'):
                continue
            if not PATTERN.search(line):
                continue

            extracted_lines.append(line)
            index_line = '%s %d\n' % (relative_path.as_posix(), line_number)
            index_lines.append(index_line)

        if not extracted_lines:
            continue

        output_path = text_directory / relative_path
        output_text = ''
        for line in extracted_lines:
            output_text += line + '\n'

        write_text(output_path, output_text, 'utf-8')
        print(output_path)

    index_path = text_directory / INDEX_NAME
    write_text(index_path, ''.join(index_lines), 'utf-8')


def read_index(text_directory):
    index_path = text_directory / INDEX_NAME
    index_text = read_text(index_path, 'utf-8')
    index_lines = split_text_lines(index_text)
    files = {}

    for index_line in index_lines:
        relative_path, line_number = index_line.rsplit(' ', 1)

        if relative_path not in files:
            files[relative_path] = []

        files[relative_path].append(int(line_number))

    return files


def replace(source_directory, text_directory, output_directory):
    files = read_index(text_directory)
    convert = make_translation_converter()

    for relative_name, line_numbers in files.items():
        relative_path = Path(relative_name)
        source_path = source_directory / relative_path
        translation_path = text_directory / relative_path
        output_path = output_directory / relative_path

        source_text = read_text(source_path, 'cp932', 'ignore')
        source_lines = source_text.splitlines(keepends=True)
        translation_text = read_text(translation_path, 'utf-8')
        translation_lines = split_text_lines(translation_text)

        if len(translation_lines) != len(line_numbers):
            message = '%s: expected %d lines, got %d'
            values = (translation_path, len(line_numbers), len(translation_lines))
            raise ValueError(message % values)

        for index in range(len(line_numbers)):
            line_number = line_numbers[index]
            translated_line = translation_lines[index]
            source_line = source_lines[line_number - 1]
            line_ending = get_line_ending(source_line)
            source_lines[line_number - 1] = convert(translated_line) + line_ending

        output_text = ''.join(source_lines)
        write_text(output_path, output_text, 'cp932')
        print(output_path)


def show_usage():
    print('python all.py e source text')
    print('python all.py w source text output')


def main():
    if len(sys.argv) < 2:
        show_usage()
        return

    mode = sys.argv[1]

    if mode == 'e' and len(sys.argv) == 4:
        source_directory = Path(sys.argv[2])
        text_directory = Path(sys.argv[3])
        extract(source_directory, text_directory)
        return

    if mode == 'w' and len(sys.argv) == 5:
        source_directory = Path(sys.argv[2])
        text_directory = Path(sys.argv[3])
        output_directory = Path(sys.argv[4])
        replace(source_directory, text_directory, output_directory)
        return

    show_usage()


if __name__ == '__main__':
    main()
