import sys
from pathlib import Path


def read(path):
    return path.read_bytes().decode("utf-16-le").splitlines()


def write(path, lines):
    text = "\r\n".join(lines)
    if lines:
        text += "\r\n"
    path.write_bytes(text.encode("utf-16-le"))


def code(line):
    value, sep, _ = line.partition("=")
    if not sep:
        return None

    try:
        return int(value.strip(), 16)
    except ValueError:
        return None


def valid_sjis(value):
    if not 0 <= value <= 0xFFFF:
        return False

    raw = (
        bytes((value,))
        if value <= 0xFF
        else bytes((value >> 8, value & 0xFF))
    )

    try:
        raw.decode("cp932")
    except UnicodeDecodeError:
        return False

    return True


def main():
    if len(sys.argv) < 4:
        raise SystemExit(
            "usage: mapping_tables.py filter INPUT OUTPUT | "
            "merge GENERATED FULL_SOURCE OUTPUT"
        )

    mode = sys.argv[1]

    if mode == "filter":
        source = Path(sys.argv[2])
        target = Path(sys.argv[3])

        lines = read(source)
        output = []

        for line in lines:
            value = code(line)
            if value is None or valid_sjis(value):
                output.append(line)

        write(target, output)
        return

    if mode == "merge":
        if len(sys.argv) != 5:
            raise SystemExit(
                "usage: mapping_tables.py merge GENERATED FULL_SOURCE OUTPUT"
            )

        generated_path = Path(sys.argv[2])
        source_path = Path(sys.argv[3])
        output_path = Path(sys.argv[4])

        generated = {}

        for line in read(generated_path):
            value = code(line)
            if value is not None:
                generated[value] = line

        output = []

        for line in read(source_path):
            value = code(line)

            if value is not None and valid_sjis(value):
                output.append(generated.get(value, line))
            else:
                output.append(line)

        write(output_path, output)
        return

    raise SystemExit(
        "usage: mapping_tables.py filter INPUT OUTPUT | "
        "merge GENERATED FULL_SOURCE OUTPUT"
    )


if __name__ == "__main__":
    main()