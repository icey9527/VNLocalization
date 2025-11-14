from PIL import Image

def decode_tile(data):
    pixels = [0] * 256
    for tile_idx in range(4):
        tile = data[tile_idx*16:(tile_idx+1)*16]
        tx, ty = (tile_idx % 2) * 8, (tile_idx // 2) * 8
        for i, byte in enumerate(tile):
            y, x_offset = i // 2, (i % 2) * 4
            for j in range(4):
                pixel = (byte >> (j * 2)) & 0x03
                pixels[(ty + y) * 16 + (tx + x_offset + j)] = pixel
    return pixels

def linear_encode(pixels):
    output = bytearray(64)
    for i, p in enumerate(pixels):
        output[i // 4] |= (p << ((i % 4) * 2))
    return bytes(output)

with open('I:\\研究\\nds\\pack\\pack\\NZ\\00000255.bin', 'rb') as f:
    header = f.read(4)
    data = f.read()

total = len(data) // 64  # 改成64
new_bin = bytearray()
atlas = Image.new('RGB', (64*16, ((total+63)//64)*16))
palette = [(0,0,0), (128,128,128), (255,255,255), (255,0,255)]
index_map = [0, 2, 1, 3]

for i in range(total):
    char_data = data[i*64:(i+1)*64]  # 改成64
    pixels = decode_tile(char_data)
    remapped = [index_map[p] for p in pixels]
    
    new_bin.extend(linear_encode(remapped))
    
    img = Image.new('RGB', (16, 16))
    img.putdata([palette[p] for p in remapped])
    atlas.paste(img, ((i%64)*16, (i//64)*16))
    
    if i % 1000 == 0: print(f"{i}/{total}")

with open('font_linear.bin', 'wb') as f:
    f.write(header + new_bin)
atlas.save('font_linear.png')

print(f"✅ 总字符: {total}")
print("✅ font_linear.bin")
print("✅ font_linear.png")