import os
import tkinter as tk
from tkinter.filedialog import askopenfilename

def make_file_id(s):
    v2 = v3 = 0
    for ch in s.lower():
        v = ord(ch)
        v3 += v
        v2 = (v + (v2 << 8)) & 0xFFFFFFFF
        if v2 & 0xFF800000:
            v2 %= 0xFFF9D7
    return (v2 | (v3 << 24)) & 0xFFFFFFFF

def mt19937(seed):
    mt = [0] * 624
    mt[0] = (1103515245 * seed + 12345) & 0xFFFFFFFF
    for i in range(1, 624):
        mt[i] = (1812433253 * (mt[i - 1] ^ (mt[i - 1] >> 30)) + i) & 0xFFFFFFFF
    
    def temper(y):
        y ^= y >> 11
        y ^= (y << 7) & 0x9D2C5680
        y ^= (y << 15) & 0xEFC60000
        return (y ^ (y >> 18)) & 0xFFFFFFFF

    yield temper(mt[0])
    i = 1
    while True:
        if i == 624:
            for j in range(624):
                y = (mt[j] & 0x80000000) | (mt[(j + 1) % 624] & 0x7FFFFFFF)
                mt[j] = mt[(j + 397) % 624] ^ (y >> 1) ^ (0x9908B0DF if y & 1 else 0)
            i = 0
        yield temper(mt[i])
        i += 1

def decrypt(path):
    with open(path, 'rb') as f:
        data = bytearray(f.read())
        
    gen = mt19937(make_file_id(os.path.basename(path)))
    v = next(gen)
    
    for i in range(0, min(len(data), 0x10000) & ~3, 4):
        v = (1103515245 * v + 12345) & 0xFFFFFFFF if v & 1 else next(gen)
        data[i:i+4] = (int.from_bytes(data[i:i+4], 'little') ^ v).to_bytes(4, 'little')
        
    with open(os.path.splitext(path)[0] + '.mpg', 'wb') as f:
        f.write(data)

if __name__ == '__main__':
    tk.Tk().withdraw()
    if p := askopenfilename():
        decrypt(p)