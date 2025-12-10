/*
 * DAT Archive Packer/Unpacker (LZSS with Binary Search Tree)
 * 
 * Compile:
 *   Windows: cl /std:c++17 /O2 /EHsc dat_tool.cpp /Fe:dat_tool.exe
 *   Linux:   g++ -std=c++17 -O3 -o data data.cpp -liconv
 * 
 * Usage:
 *   dat_tool unpack <input.dat> [output_dir]
 *   dat_tool pack <input_dir> <output.dat>
 */

#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <map>
#include <cstdint>
#include <cstring>
#include <algorithm>
#include <filesystem>
#include <iconv.h>

namespace fs = std::filesystem;

// ======================== Constants ========================
constexpr uint32_t XOR_UNCOMP = 0x1f84c9af;
constexpr uint32_t XOR_COMP   = 0x9ed835ab;

constexpr int RING_SIZE  = 4096;
constexpr int RING_MASK  = 0xFFF;
constexpr int RING_INIT  = 4078;  // 0xFEE
constexpr int MAX_MATCH  = 18;
constexpr int MIN_MATCH  = 3;
constexpr int NIL        = RING_SIZE;

// ======================== Utilities ========================
std::string cp932_to_utf8(const std::string& cp932_str) {
    iconv_t cd = iconv_open("UTF-8", "CP932");
    if (cd == (iconv_t)-1) {
        std::cerr << "[ERROR] iconv_open failed" << std::endl;
        return cp932_str;
    }

    size_t in_len = cp932_str.size();
    size_t out_len = in_len * 4;
    std::vector<char> out_buf(out_len);

    char* in_ptr = const_cast<char*>(cp932_str.data());
    char* out_ptr = out_buf.data();
    size_t in_left = in_len;
    size_t out_left = out_len;

    if (iconv(cd, &in_ptr, &in_left, &out_ptr, &out_left) == (size_t)-1) {
        std::cerr << "[ERROR] iconv failed" << std::endl;
        iconv_close(cd);
        return cp932_str;
    }

    iconv_close(cd);
    return std::string(out_buf.data(), out_len - out_left);
}

std::string utf8_to_cp932(const std::string& utf8_str) {
    iconv_t cd = iconv_open("CP932", "UTF-8");
    if (cd == (iconv_t)-1) return utf8_str;

    size_t in_len = utf8_str.size();
    size_t out_len = in_len * 2;
    std::vector<char> out_buf(out_len);

    char* in_ptr = const_cast<char*>(utf8_str.data());
    char* out_ptr = out_buf.data();
    size_t in_left = in_len;
    size_t out_left = out_len;

    if (iconv(cd, &in_ptr, &in_left, &out_ptr, &out_left) == (size_t)-1) {
        iconv_close(cd);
        return utf8_str;
    }

    iconv_close(cd);
    return std::string(out_buf.data(), out_len - out_left);
}

uint32_t calc_checksum(const uint8_t* data, size_t len) {
    uint32_t result = 0x23456789;
    for (size_t i = 0; i < len; i++) {
        uint32_t v3 = result + data[i];
        int shift = (v3 + i) % 32;
        uint32_t rotated = (v3 << shift) | (v3 >> (32 - shift));
        result += rotated;
    }
    return result;
}

uint8_t calc_xor_key(uint32_t checksum) {
    uint8_t key = (checksum & 0xFF) + 
                  ((checksum >> 8) & 0xFF) + 
                  ((checksum >> 16) & 0xFF) + 
                  ((checksum >> 24) & 0xFF);
    return key ? key : 0xAA;
}

void xor_bytes(uint8_t* data, size_t len, uint8_t key) {
    for (size_t i = 0; i < len; i++) {
        data[i] ^= key;
    }
}

std::string to_native_path(const std::string& path) {
    std::string result = path;
    #ifdef _WIN32
    std::replace(result.begin(), result.end(), '/', '\\');
    #else
    std::replace(result.begin(), result.end(), '\\', '/');
    #endif
    return result;
}

std::string to_archive_path(const std::string& path) {
    std::string result = path;
    std::replace(result.begin(), result.end(), '/', '\\');
    return result;
}

// ======================== LZSS Decompression ========================
bool lzss_decompress(const uint8_t* src, size_t src_len, 
                     uint8_t* dst, size_t dst_len) {
    uint8_t ring[RING_SIZE] = {0};
    int ring_pos = RING_INIT;
    int flags = 0;
    size_t src_pos = 0;
    size_t dst_pos = 0;

    while (dst_pos < dst_len && src_pos < src_len) {
        flags >>= 1;
        if ((flags & 0x100) == 0) {
            if (src_pos >= src_len) break;
            flags = src[src_pos++] | 0xFF00;
        }

        if (flags & 1) {
            // Literal
            if (src_pos >= src_len) break;
            uint8_t b = src[src_pos++];
            dst[dst_pos++] = b;
            ring[ring_pos] = b;
            ring_pos = (ring_pos + 1) & RING_MASK;
        } else {
            // Match
            if (src_pos + 1 >= src_len) break;
            uint8_t lo = src[src_pos++];
            uint8_t hi = src[src_pos++];
            int offset = ((hi & 0xF0) << 4) | lo;
            int length = (hi & 0x0F) + 3;

            for (int i = 0; i < length && dst_pos < dst_len; i++) {
                uint8_t b = ring[(offset + i) & RING_MASK];
                dst[dst_pos++] = b;
                ring[ring_pos] = b;
                ring_pos = (ring_pos + 1) & RING_MASK;
            }
        }
    }
    return dst_pos == dst_len;
}

// ======================== LZSS Compression (BST) ========================
class LZSSCompressor {
public:
    bool compress(const uint8_t* src, size_t src_len, std::vector<uint8_t>& dst) {
        if (src_len <= 16) {
            dst.clear();
            return false;
        }

        const int n = static_cast<int>(src_len);
        std::vector<int> head(1 << 16, -1);
        std::vector<int> chain(RING_SIZE, -1);

        dst.clear();
        dst.reserve(n + (n >> 3) + 16);

        int sp = 0;

        while (sp < n) {
            size_t fp = dst.size();
            dst.push_back(0);
            uint8_t flags = 0;

            for (int bit = 0; bit < 8 && sp < n; ++bit) {
                int best = 0;
                int off  = 0;

                if (sp + 1 < n) {
                    int h = (static_cast<int>(src[sp]) << 8) | src[sp + 1];
                    int c = 128;

                    for (int p = head[h];
                         p >= 0 && sp - p <= RING_SIZE && c-- > 0;
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
                            if (len == MAX_MATCH) break;
                        }
                    }
                }

                if (best >= MIN_MATCH) {
                    dst.push_back(static_cast<uint8_t>(off));
                    dst.push_back(static_cast<uint8_t>(((off >> 4) & 0xF0) | (best - 3)));

                    int limit = std::min(best, n - sp - 1);
                    for (int i = 0; i < limit; ++i) {
                        int hh = (static_cast<int>(src[sp + i]) << 8) | src[sp + i + 1];
                        int idx = (sp + i) & RING_MASK;
                        chain[idx] = head[hh];
                        head[hh] = sp + i;
                    }

                    sp += best;
                } else {
                    flags |= static_cast<uint8_t>(1u << bit);

                    if (sp + 1 < n) {
                        int h = (static_cast<int>(src[sp]) << 8) | src[sp + 1];
                        int idx = sp & RING_MASK;
                        chain[idx] = head[h];
                        head[h] = sp;
                    }

                    dst.push_back(src[sp]);
                    ++sp;
                }
            }

            dst[fp] = flags;
        }

        return dst.size() < src_len;
    }
};

// ======================== File List ========================
std::map<uint32_t, std::string> parse_file_list(const uint8_t* data, size_t len) {
    std::map<uint32_t, std::string> files;
    size_t pos = 0;

    while (pos + 8 <= len) {
        uint32_t name_len = *(uint32_t*)(data + pos);
        uint32_t addr = *(uint32_t*)(data + pos + 4);
        pos += 8;

        if (pos + name_len > len) break;

        std::string name((char*)(data + pos), name_len);
        pos += name_len + 1;

        files[addr] = cp932_to_utf8(name);
    }
    return files;
}

std::vector<uint8_t> build_file_list(const std::vector<std::pair<uint32_t, std::string>>& entries) {
    std::vector<uint8_t> output;

    for (const auto& [offset, filename] : entries) {
        uint32_t name_len = static_cast<uint32_t>(filename.size());
        
        // name_length (4 bytes)
        output.insert(output.end(), (uint8_t*)&name_len, (uint8_t*)&name_len + 4);
        // offset (4 bytes)
        output.insert(output.end(), (uint8_t*)&offset, (uint8_t*)&offset + 4);
        // filename
        output.insert(output.end(), filename.begin(), filename.end());
        // null terminator
        output.push_back(0);
    }
    return output;
}

// ======================== Block I/O ========================
struct Block {
    std::vector<uint8_t> data;
    size_t next_offset;
    size_t block_size;
    bool valid;
};

Block read_block(std::ifstream& f, size_t offset) {
    Block block = {{}, 0, 0, false};

    f.seekg(offset);
    uint8_t header[12];
    if (!f.read(reinterpret_cast<char*>(header), sizeof(header))) {
        return block;
    }

    uint32_t uncomp   = *reinterpret_cast<uint32_t*>(&header[0]) ^ XOR_UNCOMP;
    uint32_t f_size   = *reinterpret_cast<uint32_t*>(&header[4]) ^ XOR_COMP;
    uint32_t checksum = *reinterpret_cast<uint32_t*>(&header[8]);

    bool is_enc = (checksum != 0);  // 这里的判断参考自https://github.com/punk7890/PS2-Visual-Novel-Tool/blob/main/src/scenes/headlock.gd

    if (f_size > 0) {
        std::vector<uint8_t> buf(f_size);
        if (!f.read(reinterpret_cast<char*>(buf.data()), f_size)) {
            return block;
        }

        if (is_enc) {
            uint8_t xor_key = calc_xor_key(checksum);
            xor_bytes(buf.data(), f_size, xor_key);
        }

        block.data.resize(uncomp);
        if (!lzss_decompress(buf.data(), f_size, block.data.data(), uncomp)) {
            std::cerr << "Warning: Decompression mismatch at offset "
                      << offset << std::endl;
        }

        block.block_size = 12 + f_size;
    } else {
        block.data.resize(uncomp);
        if (!f.read(reinterpret_cast<char*>(block.data.data()), uncomp)) {
            return block;
        }

        if (is_enc) { 
            uint8_t xor_key = calc_xor_key(checksum);
            xor_bytes(block.data.data(), block.data.size(), xor_key);
        }

        block.block_size = 12 + uncomp;
    }

    block.next_offset = offset + block.block_size;
    block.valid = true;
    return block;
}

std::vector<uint8_t> write_block(const uint8_t* data, size_t len, bool try_compress = true) {
    std::vector<uint8_t> output;
    uint8_t header[12];

    if (try_compress && len > 0) {
        LZSSCompressor compressor;
        std::vector<uint8_t> compressed;

        if (compressor.compress(data, len, compressed)) {
            uint32_t checksum = calc_checksum(compressed.data(), compressed.size());
            uint8_t xor_key = calc_xor_key(checksum);
            xor_bytes(compressed.data(), compressed.size(), xor_key);

            *(uint32_t*)&header[0] = static_cast<uint32_t>(len) ^ XOR_UNCOMP;
            *(uint32_t*)&header[4] = static_cast<uint32_t>(compressed.size()) ^ XOR_COMP;
            *(uint32_t*)&header[8] = checksum;

            output.insert(output.end(), header, header + 12);
            output.insert(output.end(), compressed.begin(), compressed.end());
            return output;
        }
    }

    // Uncompressed
    *(uint32_t*)&header[0] = static_cast<uint32_t>(len) ^ XOR_UNCOMP;
    *(uint32_t*)&header[4] = XOR_COMP;  // comp_size = 0
    *(uint32_t*)&header[8] = 0;

    output.insert(output.end(), header, header + 12);
    output.insert(output.end(), data, data + len);
    return output;
}

// ======================== Commands ========================
int unpack(const std::string& input_file, const std::string& output_dir) {
    std::ifstream f(input_file, std::ios::binary);
    if (!f) {
        std::cerr << "Error: Cannot open file: " << input_file << std::endl;
        return 1;
    }

    fs::create_directories(output_dir);

    // Read file list (first block)
    Block index_block = read_block(f, 0);
    if (!index_block.valid) {
        std::cerr << "Error: Cannot read file list" << std::endl;
        return 1;
    }

    auto file_list = parse_file_list(index_block.data.data(), index_block.data.size());
    size_t idx_size = index_block.block_size;

    std::cout << "[INDEX] " << file_list.size() << " files" << std::endl;

    // Extract files
    size_t offset = idx_size;
    int count = 0;

    while (true) {
        Block block = read_block(f, offset);
        if (!block.valid) break;

        uint32_t file_key = static_cast<uint32_t>(offset - idx_size);
        std::string filename;

        auto it = file_list.find(file_key);
        if (it != file_list.end()) {
            filename = it->second;
        } else {
            char buf[32];
            snprintf(buf, sizeof(buf), "unknown_%08X.bin", file_key);
            filename = buf;
        }

        fs::path out_path = fs::path(output_dir) / to_native_path(filename);
        fs::create_directories(out_path.parent_path());

        std::ofstream out(out_path, std::ios::binary);
        out.write((char*)block.data.data(), block.data.size());

        std::cout << "  " << filename << " (" << block.data.size() << " bytes)" << std::endl;

        offset = block.next_offset;
        count++;
    }

    std::cout << "\nExtracted " << count << " files" << std::endl;
    return 0;
}

int pack(const std::string& input_dir, const std::string& output_file) {
    if (!fs::is_directory(input_dir)) {
        std::cerr << "Error: Not a directory: " << input_dir << std::endl;
        return 1;
    }

    // Collect all files
    std::vector<fs::path> all_files;
    for (const auto& entry : fs::recursive_directory_iterator(input_dir)) {
        if (entry.is_regular_file()) {
            all_files.push_back(entry.path());
        }
    }
    std::sort(all_files.begin(), all_files.end());

    if (all_files.empty()) {
        std::cerr << "Error: No files to pack" << std::endl;
        return 1;
    }

    std::cout << "Packing " << all_files.size() << " files..." << std::endl;

    // Build blocks and calculate offsets
    std::vector<std::vector<uint8_t>> file_blocks;
    std::vector<std::pair<uint32_t, std::string>> file_entries;
    uint32_t current_offset = 0;

    for (const auto& file_path : all_files) {
        // Read file
        std::ifstream in(file_path, std::ios::binary | std::ios::ate);
        size_t file_size = in.tellg();
        in.seekg(0);

        std::vector<uint8_t> file_data(file_size);
        in.read((char*)file_data.data(), file_size);

        // Compress
        auto block = write_block(file_data.data(), file_data.size());

        // Get relative path with backslashes
        fs::path rel_path = fs::relative(file_path, input_dir);
        std::string archive_path = to_archive_path(rel_path.string());
        archive_path = utf8_to_cp932(archive_path);

        file_entries.emplace_back(current_offset, archive_path);
        file_blocks.push_back(std::move(block));

        size_t comp_size = file_blocks.back().size() - 12;
        double ratio = file_size > 0 ? (comp_size * 100.0 / file_size) : 0;
        const char* status = comp_size < file_size ? "compressed" : "stored";

        std::cout << "  " << archive_path << ": " << file_size 
                  << " -> " << comp_size << " (" << (int)ratio << "%) [" << status << "]" << std::endl;

        current_offset += static_cast<uint32_t>(file_blocks.back().size());
    }

    // Build file list
    auto namelist_data = build_file_list(file_entries);
    auto namelist_block = write_block(namelist_data.data(), namelist_data.size());

    // Write output
    std::ofstream out(output_file, std::ios::binary);
    if (!out) {
        std::cerr << "Error: Cannot create output file" << std::endl;
        return 1;
    }

    out.write((char*)namelist_block.data(), namelist_block.size());
    for (const auto& block : file_blocks) {
        out.write((char*)block.data(), block.size());
    }

    size_t total_size = namelist_block.size();
    for (const auto& b : file_blocks) total_size += b.size();

    std::cout << "\n✓ Packed " << all_files.size() << " files to '" 
              << output_file << "' (" << total_size << " bytes)" << std::endl;
    return 0;
}

// ======================== Main ========================
void print_usage(const char* prog) {
    std::cout << "DAT Archive Tool (LZSS)\n\n"
              << "Usage:\n"
              << "  " << prog << " u <input.dat> [output_dir]\n"
              << "  " << prog << " p <input_dir> <output.dat>\n";
}

int main(int argc, char* argv[]) {
    if (argc < 3) {
        print_usage(argv[0]);
        return 1;
    }

    std::string cmd = argv[1];

    if (cmd == "u") {
        std::string output = argc > 3 ? argv[3] : "unpacked";
        return unpack(argv[2], output);
    } else if (cmd == "p") {
        if (argc < 4) {
            print_usage(argv[0]);
            return 1;
        }
        return pack(argv[2], argv[3]);
    } else {
        std::cerr << "Unknown command: " << cmd << std::endl;
        print_usage(argv[0]);
        return 1;
    }
}