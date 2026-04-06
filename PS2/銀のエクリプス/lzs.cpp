#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <cstring>
#include <vector>
#include <algorithm>

std::vector<uint8_t> decompress_lzss(const uint8_t* src, size_t comp_size, size_t decomp_size) {
    std::vector<uint8_t> output(decomp_size);
    std::vector<uint8_t> dict(0x1000, 0x20);
    
    size_t src_pos = 0;
    size_t dst_pos = 0;
    size_t dic_off = 0xFEE;
    
    uint8_t cb = 0;
    uint8_t mask = 0;
    
    while (dst_pos < decomp_size && src_pos < comp_size) {
        if (mask == 0) {
            cb = src[src_pos++];
            mask = 1;
        }
        
        if (cb & mask) {
            uint8_t byte = src[src_pos++];
            output[dst_pos++] = byte;
            dict[dic_off] = byte;
            dic_off = (dic_off + 1) & 0xFFF;
        } else {
            if (src_pos + 1 >= comp_size) break;
            
            uint8_t b1 = src[src_pos++];
            uint8_t b2 = src[src_pos++];
            
            int len = (b2 & 0x0F) + 3;
            int loc = b1 | ((b2 & 0xF0) << 4);
            
            for (int i = 0; i < len; i++) {
                if (dst_pos >= decomp_size) break;
                uint8_t byte = dict[(loc + i) & 0xFFF];
                output[dst_pos++] = byte;
                dict[dic_off] = byte;
                dic_off = (dic_off + 1) & 0xFFF;
            }
        }
        
        mask = (mask << 1) & 0xFF;
    }
    
    return output;
}

std::vector<uint8_t> compress_lzss(const uint8_t* src, size_t src_size) {
    std::vector<uint8_t> output;
    if (src_size == 0) {
        return output;
    }

    static const int RING_SIZE = 0x1000;
    static const int RING_MASK = 0x0FFF;
    static const int RING_INIT = 0x0FEE;
    static const int MAX_BACK = 0x0FEE;
    static const int MIN_MATCH = 3;
    static const int MAX_MATCH = 18;
    static const int CANDIDATE_LIMIT = 128;

    const int n = (int)src_size;
    std::vector<int> head(1 << 16, -1);
    std::vector<int> chain(RING_SIZE, -1);

    output.reserve(src_size + (src_size / 8) + 16);

    int sp = 0;

    while (sp < n) {
        size_t flag_pos = output.size();
        output.push_back(0);
        uint8_t flag = 0;
        uint8_t mask = 1;

        for (int bit = 0; bit < 8 && sp < n; bit++) {
            int best = 0;
            int off = 0;

            if (sp + 1 < n) {
                int h = ((int)src[sp] << 8) | src[sp + 1];
                int c = CANDIDATE_LIMIT;

                for (int p = head[h];
                     p >= 0 && sp - p <= MAX_BACK && c-- > 0;
                     p = chain[p & RING_MASK]) {
                    int len = 0;
                    while (len < MAX_MATCH &&
                           sp + len < n &&
                           src[p + len] == src[sp + len]) {
                        ++len;
                    }
                    if (len > best) {
                        best = len;
                        off = (RING_INIT + p) & RING_MASK;
                        if (len == MAX_MATCH) {
                            break;
                        }
                    }
                }
            }

            if (best >= MIN_MATCH) {
                output.push_back((uint8_t)off);
                output.push_back((uint8_t)(((off >> 4) & 0xF0) | (best - 3)));

                int limit = std::min(best, n - sp - 1);
                for (int i = 0; i < limit; ++i) {
                    int hh = ((int)src[sp + i] << 8) | src[sp + i + 1];
                    int idx = (sp + i) & RING_MASK;
                    chain[idx] = head[hh];
                    head[hh] = sp + i;
                }
                sp += best;
            } else {
                flag |= mask;
                if (sp + 1 < n) {
                    int h = ((int)src[sp] << 8) | src[sp + 1];
                    int idx = sp & RING_MASK;
                    chain[idx] = head[h];
                    head[h] = sp;
                }
                output.push_back(src[sp]);
                ++sp;
            }

            mask <<= 1;
        }

        output[flag_pos] = flag;
    }

    return output;
}

int main(int argc, char* argv[]) {
    if (argc != 4) {
        printf("LZS Tool\n");
        printf("  Decompress: %s U <input> <output>\n", argv[0]);
        printf("  Compress:   %s P <input> <output>\n", argv[0]);
        return 1;
    }
    
    char mode = argv[1][0];
    const char* input_path = argv[2];
    const char* output_path = argv[3];
    
    FILE* fp = fopen(input_path, "rb");
    if (!fp) {
        printf("Error: Cannot open %s\n", input_path);
        return 1;
    }
    
    fseek(fp, 0, SEEK_END);
    size_t file_size = ftell(fp);
    fseek(fp, 0, SEEK_SET);
    
    std::vector<uint8_t> input_data(file_size);
    fread(input_data.data(), 1, file_size, fp);
    fclose(fp);
    
    std::vector<uint8_t> output_data;
    
    if (mode == 'U' || mode == 'u') {
        if (file_size < 8 || memcmp(input_data.data(), "LZS", 3) != 0) {
            printf("Error: Not a valid LZS file\n");
            return 1;
        }
        
        uint32_t decomp_size = *(uint32_t*)(input_data.data() + 4);
        printf("Decompressing: %zu -> %u bytes\n", file_size - 8, decomp_size);
        
        output_data = decompress_lzss(input_data.data() + 8, file_size - 8, decomp_size);
        
    } else if (mode == 'P' || mode == 'p') {
        printf("Compressing: %zu bytes\n", file_size);
        
        std::vector<uint8_t> compressed = compress_lzss(input_data.data(), file_size);
        
        output_data.resize(8 + compressed.size());
        memcpy(output_data.data(), "LZS", 3);
        output_data[3] = 0;
        *(uint32_t*)(output_data.data() + 4) = (uint32_t)file_size;
        memcpy(output_data.data() + 8, compressed.data(), compressed.size());
        
        printf("Compressed: %zu -> %zu bytes\n", file_size, output_data.size());
        
    } else {
        printf("Error: Unknown mode '%c'\n", mode);
        return 1;
    }
    
    fp = fopen(output_path, "wb");
    if (!fp) {
        printf("Error: Cannot create %s\n", output_path);
        return 1;
    }
    
    fwrite(output_data.data(), 1, output_data.size(), fp);
    fclose(fp);
    
    printf("Done: %s\n", output_path);
    return 0;
}
