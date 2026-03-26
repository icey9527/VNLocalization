#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <cstring>
#include <vector>
#include <string>
#include <algorithm>
#include <thread>
#include <atomic>

#ifdef _WIN32
#include <windows.h>
#include <direct.h>
#define PATH_SEP '\\'
#define mkdir_p(path) _mkdir(path)
#else
#include <dirent.h>
#include <sys/stat.h>
#define PATH_SEP '/'
#define mkdir_p(path) mkdir(path, 0755)
#endif

static inline uint32_t read_u32_le(const uint8_t* p) {
    return (uint32_t)p[0] |
           ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) |
           ((uint32_t)p[3] << 24);
}

static inline void write_u32_le(uint8_t* p, uint32_t v) {
    p[0] = (uint8_t)(v & 0xFF);
    p[1] = (uint8_t)((v >> 8) & 0xFF);
    p[2] = (uint8_t)((v >> 16) & 0xFF);
    p[3] = (uint8_t)((v >> 24) & 0xFF);
}

std::vector<uint8_t> decompress_lzss(const uint8_t* src, size_t comp_size, size_t decomp_size) {
    std::vector<uint8_t> output(decomp_size);
    std::vector<uint8_t> dict(0x1000, 0);
    
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

std::vector<uint8_t> make_lzs(const uint8_t* src, size_t src_size) {
    std::vector<uint8_t> compressed = compress_lzss(src, src_size);
    
    std::vector<uint8_t> result(8 + compressed.size());
    memcpy(result.data(), "LZS", 3);
    result[3] = 0;
    write_u32_le(result.data() + 4, (uint32_t)src_size);
    memcpy(result.data() + 8, compressed.data(), compressed.size());
    
    return result;
}

void make_dir(const std::string& path) {
    std::string p = path;
    for (size_t i = 1; i < p.size(); i++) {
        if (p[i] == '/' || p[i] == '\\') {
            p[i] = '\0';
            mkdir_p(p.c_str());
            p[i] = PATH_SEP;
        }
    }
    mkdir_p(p.c_str());
}

std::vector<std::string> list_files(const char* dir_path) {
    std::vector<std::string> files;
    
#ifdef _WIN32
    std::string pattern = std::string(dir_path) + "\\*";
    WIN32_FIND_DATAA fd;
    HANDLE hFind = FindFirstFileA(pattern.c_str(), &fd);
    
    if (hFind != INVALID_HANDLE_VALUE) {
        do {
            if (!(fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)) {
                files.push_back(fd.cFileName);
            }
        } while (FindNextFileA(hFind, &fd));
        FindClose(hFind);
    }
#else
    DIR* dir = opendir(dir_path);
    if (dir) {
        struct dirent* entry;
        while ((entry = readdir(dir)) != nullptr) {
            if (entry->d_type == DT_REG) {
                files.push_back(entry->d_name);
            }
        }
        closedir(dir);
    }
#endif
    
    std::sort(files.begin(), files.end());
    return files;
}

int extract_pac(const char* input_path, const char* output_dir) {
    FILE* fp = fopen(input_path, "rb");
    if (!fp) {
        printf("Error: Cannot open %s\n", input_path);
        return 1;
    }
    
    fseek(fp, 0, SEEK_END);
    size_t file_size = ftell(fp);
    fseek(fp, 0, SEEK_SET);
    
    std::vector<uint8_t> data(file_size);
    fread(data.data(), 1, file_size, fp);
    fclose(fp);
    
    if (file_size < 12 || memcmp(data.data(), "PAC", 3) != 0) {
        printf("Error: Invalid PAC header\n");
        return 1;
    }
    
    uint32_t name_tbl_off = read_u32_le(data.data() + 4);
    uint32_t num_files = read_u32_le(data.data() + 8);
    uint32_t file_tbl = 12;
    
    printf("Files: %u\n", num_files);
    make_dir(output_dir);
    
    for (uint32_t i = 0; i < num_files; i++) {
        uint32_t offset = read_u32_le(data.data() + file_tbl + i * 8);
        uint32_t size = read_u32_le(data.data() + file_tbl + i * 8 + 4);
        if ((size_t)offset + (size_t)size > data.size()) {
            printf("[%04u] invalid range: off=0x%08X size=%u\n", i, offset, size);
            continue;
        }
        
        char filename[0x41] = {0};
        memcpy(filename, data.data() + name_tbl_off + i * 0x40, 0x40);
        
        std::vector<uint8_t> file_data(data.begin() + offset, data.begin() + offset + size);
        
        bool was_lzs = false;
        if (size >= 8 && memcmp(file_data.data(), "LZS", 3) == 0) {
            uint32_t decomp_size = read_u32_le(file_data.data() + 4);
            file_data = decompress_lzss(file_data.data() + 8, size - 8, decomp_size);
            was_lzs = true;
        }
        
        std::string out_path = std::string(output_dir) + PATH_SEP + filename;
        
        FILE* out_fp = fopen(out_path.c_str(), "wb");
        if (out_fp) {
            fwrite(file_data.data(), 1, file_data.size(), out_fp);
            fclose(out_fp);
        }
        
        printf("[%04u] 0x%08X %8u -> %s%s\n", i, offset, size, filename, was_lzs ? " (LZS)" : "");
    }
    
    return 0;
}

int create_pac(const char* input_dir, const char* output_path) {
    struct PackedFile {
        bool ready = false;
        size_t orig_size = 0;
        std::vector<uint8_t> store_data;
    };

    std::vector<std::string> files = list_files(input_dir);
    
    if (files.empty()) {
        printf("Error: No files found in %s\n", input_dir);
        return 1;
    }
    
    printf("Packing %zu files (LZS)\n", files.size());
    
    uint32_t num_files = (uint32_t)files.size();
    uint32_t header_size = 12;
    uint32_t file_tbl_size = num_files * 8;
    uint32_t name_tbl_off = header_size + file_tbl_size;
    uint32_t name_tbl_size = num_files * 0x40;
    uint32_t data_start = name_tbl_off + name_tbl_size;
    data_start = (data_start + 0x7FF) & ~0x7FF;
    
    std::vector<PackedFile> packed(num_files);
    std::atomic<uint32_t> next_index(0);

    unsigned int thread_count = std::thread::hardware_concurrency();
    if (thread_count == 0) {
        thread_count = 4;
    }
    thread_count = std::min<unsigned int>(thread_count, num_files);

    std::vector<std::thread> workers;
    workers.reserve(thread_count);
    for (unsigned int t = 0; t < thread_count; t++) {
        workers.emplace_back([&]() {
            while (true) {
                uint32_t i = next_index.fetch_add(1);
                if (i >= num_files) {
                    break;
                }

                std::string file_path = std::string(input_dir) + PATH_SEP + files[i];
                FILE* in_fp = fopen(file_path.c_str(), "rb");
                if (!in_fp) {
                    continue;
                }

                fseek(in_fp, 0, SEEK_END);
                size_t orig_size = ftell(in_fp);
                fseek(in_fp, 0, SEEK_SET);

                std::vector<uint8_t> file_data(orig_size);
                fread(file_data.data(), 1, orig_size, in_fp);
                fclose(in_fp);

                packed[i].orig_size = orig_size;
                packed[i].store_data = make_lzs(file_data.data(), file_data.size());
                packed[i].ready = true;
            }
        });
    }
    for (size_t t = 0; t < workers.size(); t++) {
        workers[t].join();
    }

    std::vector<uint8_t> output;
    output.resize(data_start, 0);
    
    memcpy(output.data(), "PAC", 3);
    output[3] = 0;
    write_u32_le(output.data() + 4, name_tbl_off);
    write_u32_le(output.data() + 8, num_files);
    
    uint32_t current_offset = data_start;
    
    for (uint32_t i = 0; i < num_files; i++) {
        if (!packed[i].ready) {
            printf("[%04u] failed to pack: %s\n", i, files[i].c_str());
            continue;
        }

        size_t orig_size = packed[i].orig_size;
        std::vector<uint8_t>& store_data = packed[i].store_data;
        size_t store_size = store_data.size();

        write_u32_le(output.data() + header_size + i * 8, current_offset);
        write_u32_le(output.data() + header_size + i * 8 + 4, (uint32_t)store_size);
        
        strncpy((char*)(output.data() + name_tbl_off + i * 0x40), files[i].c_str(), 0x3F);
        
        size_t old_size = output.size();
        output.resize(old_size + store_size);
        if (store_size > 0) {
            memcpy(output.data() + old_size, store_data.data(), store_size);
        }
        
        uint32_t padding = ((store_size + 0x7FF) & ~0x7FF) - store_size;
        if (padding > 0) {
            output.resize(output.size() + padding, 0);
        }
        
        printf("[%04u] %8zu -> %8zu <- %s\n", i, orig_size, store_size, files[i].c_str());
        current_offset += (uint32_t)store_size + padding;
    }
    
    FILE* out_fp = fopen(output_path, "wb");
    if (!out_fp) {
        printf("Error: Cannot create %s\n", output_path);
        return 1;
    }
    
    fwrite(output.data(), 1, output.size(), out_fp);
    fclose(out_fp);
    
    printf("Done: %s (%zu bytes)\n", output_path, output.size());
    return 0;
}

int main(int argc, char* argv[]) {
    if (argc != 4) {
        printf("PAC Tool\n");
        printf("  Unpack: %s U <input.pac> <output_folder>\n", argv[0]);
        printf("  Pack:   %s P <input_folder> <output.pac>\n", argv[0]);
        return 1;
    }
    
    char mode = argv[1][0];
    
    if (mode == 'U' || mode == 'u') {
        return extract_pac(argv[2], argv[3]);
    } else if (mode == 'P' || mode == 'p') {
        return create_pac(argv[2], argv[3]);
    } else {
        printf("Error: Unknown mode '%c'\n", mode);
        return 1;
    }
}
