import os
import sys

def merge_files(src_dir, out_file):
    with open(out_file, 'w', encoding='utf-8-sig') as f_out:
        for root, _, files in os.walk(src_dir):
            for f in files:
                if f.endswith('.txt'):
                    with open(os.path.join(root, f), 'r', encoding='utf-8') as f_in:
                        f_out.write(f_in.read() + '\n')

if __name__ == "__main__":
    if len(sys.argv) > 2:
        merge_files(sys.argv[1], sys.argv[2])