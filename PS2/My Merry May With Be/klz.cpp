#include <cstdint>
#include <vector>
#include <string>
#include <fstream>
#include <iostream>
#include <filesystem>
#include <algorithm>
#include <limits>
#include <cctype>

namespace fs = std::filesystem;

// ========== 工具 ==========

static inline std::string lower_ext(const fs::path& p) {
    std::string ext = p.extension().string();
    std::transform(ext.begin(), ext.end(), ext.begin(), [](unsigned char c){ return (char)std::tolower(c); });
    return ext;
}
static inline bool has_klz_ext(const fs::path& p) { return lower_ext(p) == ".klz"; }
static inline bool has_tm2_ext(const fs::path& p) { return lower_ext(p) == ".tm2"; }

// ========== 解压部分（.klz -> .tm2） ==========

static std::vector<uint8_t> decompress_lz77_block(const uint8_t* data, size_t len) {
    std::vector<uint8_t> out;
    if (len == 0) return out;
    out.reserve(len * 4); // 经验性预留，减小realloc

    size_t ptr = 1;       // data pointer
    int bit = 0;          // bit index [0..7]
    uint8_t ctrl = data[0];

    while (ptr < len) {
        uint8_t mask = 1u << bit;
        if ((ctrl & mask) == 0) {
            // 字面量
            if (ptr >= len) break;
            out.push_back(data[ptr]);
            ++ptr;
        } else {
            // LZ77 引用
            if (ptr + 1 >= len) break;
            uint8_t b1 = data[ptr];
            uint8_t b2 = data[ptr + 1];
            ptr += 2;

            uint16_t combined = (static_cast<uint16_t>(b1) << 8) | b2; // 大端
            uint16_t offset   = combined >> 5;
            int length        = (b2 & 0x1F) + 3; // 注意+3

            int src = static_cast<int>(out.size()) - static_cast<int>(offset) - 1;

            for (int i = 0; i < length; ++i) {
                size_t out_pos = out.size();
                uint16_t src_u16 = static_cast<uint16_t>(src);
                if (out_pos < 0x800 && out_pos < src_u16) {
                    out.push_back(out.empty() ? 0 : out[0]);
                } else {
                    if (src_u16 < out.size()) out.push_back(out[src_u16]);
                    else out.push_back(0);
                }
                ++src;
            }
        }

        ++bit;
        if (bit == 8) {
            bit = 0;
            if (ptr < len) {
                ctrl = data[ptr];
                ++ptr;
            } else break;
        }
    }
    return out;
}

static std::vector<uint8_t> decompress_klz_bytes(const uint8_t* data, size_t len) {
    if (len < 4) return {};
    uint32_t target = (static_cast<uint32_t>(data[0]) << 24) |
                      (static_cast<uint32_t>(data[1]) << 16) |
                      (static_cast<uint32_t>(data[2]) << 8)  |
                       static_cast<uint32_t>(data[3]);

    std::vector<uint8_t> out;
    out.reserve(target);
    size_t pos = 4;

    while (pos + 1 < len && out.size() < target) {
        uint16_t header = (static_cast<uint16_t>(data[pos]) << 8) | data[pos + 1];
        pos += 2;

        if ((header & 0x8000) == 0) {
            // LZ77 压缩块
            size_t comp_size = header;
            if (pos + comp_size > len) comp_size = len - pos;
            auto block = decompress_lz77_block(data + pos, comp_size);
            pos += comp_size;

            if (!block.empty()) {
                size_t remain = target - out.size();
                if (block.size() <= remain) {
                    out.insert(out.end(), block.begin(), block.end());
                } else {
                    out.insert(out.end(), block.begin(), block.begin() + remain);
                }
            }
        } else {
            // 原始数据块，固定 0x4000（最后一块可小于 0x4000）
            size_t raw_size = std::min<size_t>(0x4000, len - pos);
            size_t remain   = target - out.size();
            size_t to_copy  = std::min(raw_size, remain);
            out.insert(out.end(), data + pos, data + pos + to_copy);
            pos += raw_size;
        }
    }

    if (out.size() > target) out.resize(target);
    return out;
}

static bool decompress_klz_file(const fs::path& src, const fs::path& dst) {
    std::ifstream ifs(src, std::ios::binary);
    if (!ifs) return false;

    ifs.seekg(0, std::ios::end);
    std::streamsize size = ifs.tellg();
    if (size <= 0) return false;
    ifs.seekg(0, std::ios::beg);

    std::vector<uint8_t> data(static_cast<size_t>(size));
    if (!ifs.read(reinterpret_cast<char*>(data.data()), size)) return false;

    if (data.size() < 4) return false;
    uint32_t target = (static_cast<uint32_t>(data[0]) << 24) |
                      (static_cast<uint32_t>(data[1]) << 16) |
                      (static_cast<uint32_t>(data[2]) << 8)  |
                       static_cast<uint32_t>(data[3]);

    auto out = decompress_klz_bytes(data.data(), data.size());

    std::error_code ec;
    fs::create_directories(dst.parent_path(), ec);
    std::ofstream ofs(dst, std::ios::binary);
    if (!ofs) return false;
    ofs.write(reinterpret_cast<const char*>(out.data()), static_cast<std::streamsize>(out.size()));

    return out.size() == target;
}

static size_t process_decompress(const fs::path& input, const fs::path* out_root_opt) {
    std::vector<fs::path> files;

    std::error_code ec;
    if (fs::is_regular_file(input, ec)) {
        if (has_klz_ext(input)) files.push_back(input);
    } else if (fs::is_directory(input, ec)) {
        for (auto it = fs::recursive_directory_iterator(input, fs::directory_options::skip_permission_denied, ec);
             it != fs::recursive_directory_iterator(); ++it) {
            if (it->is_regular_file(ec) && has_klz_ext(it->path())) {
                files.push_back(it->path());
            }
        }
    } else {
        std::cout << "路径不存在: " << input << "\n";
        return 0;
    }

    const bool input_is_dir = fs::is_directory(input, ec);
    size_t ok = 0, total = files.size();

    for (const auto& p : files) {
        fs::path dst;
        if (out_root_opt) {
            if (input_is_dir) {
                fs::path rel = p.lexically_relative(input);
                dst = (*out_root_opt) / rel;
            } else {
                dst = (*out_root_opt) / p.filename();
            }
            dst.replace_extension(".tm2");
        } else {
            dst = p;
            dst.replace_extension(".tm2");
        }

        bool success = decompress_klz_file(p, dst);
        std::cout << (success ? "OK   " : "FAIL ") << ": " << p.string() << " -> " << dst.string() << "\n";
        if (success) ++ok;
    }

    std::cout << "Done. " << ok << "/" << total << " succeeded.\n";
    return ok;
}

// ========== 压缩部分（.tm2 -> .klz） ==========

static std::vector<uint8_t> ref_decompress_lz77_block(const uint8_t* data, size_t len) {
    // 与上面的解码严格一致（压缩端自检用）
    std::vector<uint8_t> out;
    if (len == 0) return out;

    size_t ptr = 1;
    int bit = 0;
    uint8_t ctrl = data[0];

    while (ptr < len) {
        uint8_t mask = 1u << bit;

        if ((ctrl & mask) == 0) {
            if (ptr >= len) break;
            out.push_back(data[ptr]);
            ++ptr;
        } else {
            if (ptr + 1 >= len) break;
            uint8_t b1 = data[ptr];
            uint8_t b2 = data[ptr + 1];
            ptr += 2;

            uint16_t combined = (uint16_t(b1) << 8) | b2; // 大端
            uint16_t offset   = combined >> 5;
            int length        = (b2 & 0x1F) + 3;

            int src = (int)out.size() - (int)offset - 1;
            for (int i = 0; i < length; ++i) {
                size_t out_pos = out.size();
                uint16_t src_u16 = (uint16_t)src;

                if (out_pos < 0x800 && out_pos < src_u16) {
                    out.push_back(out.empty() ? 0 : out[0]);
                } else {
                    if (src_u16 < out.size()) out.push_back(out[src_u16]);
                    else out.push_back(0);
                }
                ++src;
            }
        }

        ++bit;
        if (bit == 8) {
            bit = 0;
            if (ptr < len) {
                ctrl = data[ptr];
                ++ptr;
            } else break;
        }
    }
    return out;
}

// LZ77 (11-bit offset, 5-bit length, LSB-first control)
static inline uint32_t hash3(uint8_t a, uint8_t b, uint8_t c) {
    constexpr uint32_t m1 = 0x1e35a7bd, m2 = 0x9e3779b1, m3 = 0x85ebca6b;
    return (a * m1) ^ (b * m2) ^ (c * m3);
}

static std::vector<uint8_t> compress_lz77_block(const uint8_t* in, size_t n) {
    const int WINDOW = 2048, MIN_LEN = 3, MAX_LEN = 34;
    const int HASH_BITS = 12, HASH_SIZE = 1 << HASH_BITS, MAX_CHAIN = 64;

    std::vector<int> head(HASH_SIZE, -1), next(n, -1);
    auto insert_pos = [&](int p){
        if (p + 2 >= (int)n) return;
        uint32_t h = hash3(in[p], in[p+1], in[p+2]) & (HASH_SIZE - 1);
        next[p] = head[h]; head[h] = p;
    };

    std::vector<uint8_t> out;
    out.reserve(n + n/8 + 32);

    uint8_t ctrl = 0;
    int bit = 0;
    size_t ctrl_pos = std::numeric_limits<size_t>::max();

    auto begin_group_if_needed = [&]() {
        if (bit == 0) { ctrl = 0; ctrl_pos = out.size(); out.push_back(0); }
    };
    auto finish_bit_and_maybe_flush = [&]() {
        ++bit;
        if (bit == 8) { out[ctrl_pos] = ctrl; bit = 0; }
    };
    auto flush_tail_ctrl = [&]() {
        if (bit != 0 && ctrl_pos != std::numeric_limits<size_t>::max()) out[ctrl_pos] = ctrl;
    };

    int pos = 0;
    while (pos < (int)n) {
        int best_len = 0, best_pos = -1;

        if (pos + MIN_LEN <= (int)n) {
            uint32_t h = hash3(in[pos], in[pos+1], in[pos+2]) & (HASH_SIZE - 1);
            int cand = head[h], steps = 0;
            while (cand != -1 && steps < MAX_CHAIN) {
                int offset = pos - cand - 1;
                if (offset > WINDOW - 1) break;
                if (in[cand] == in[pos]) {
                    int max_l = std::min(MAX_LEN, (int)n - pos);
                    int l = 1;
                    while (l < max_l && in[cand + l] == in[pos + l]) ++l;
                    if (l >= MIN_LEN && l > best_len) {
                        best_len = l; best_pos = cand;
                        if (best_len == MAX_LEN) break;
                    }
                }
                cand = next[cand]; ++steps;
            }
        }

        if (best_len >= MIN_LEN) {
            int offset = pos - best_pos - 1; // 0..2047
            uint16_t combined = uint16_t((offset << 5) | ((best_len - 3) & 0x1F));

            begin_group_if_needed();
            ctrl |= (1u << bit); // 1=引用
            out.push_back(uint8_t(combined >> 8));
            out.push_back(uint8_t(combined & 0xFF));
            finish_bit_and_maybe_flush();

            for (int i = 0; i < best_len; ++i) { insert_pos(pos); ++pos; }
        } else {
            begin_group_if_needed();
            out.push_back(in[pos]);          // 0=字面量
            finish_bit_and_maybe_flush();
            insert_pos(pos);
            ++pos;
        }
    }

    flush_tail_ctrl();
    return out;
}

// 容器写入（严格遵循老解压器约定）
static inline void write_u16_be(std::ostream& os, uint16_t v) {
    char b[2] = { static_cast<char>(v >> 8), static_cast<char>(v & 0xFF) };
    os.write(b, 2);
}
static inline void write_u32_be(std::ostream& os, uint32_t v) {
    char b[4] = {
        static_cast<char>((v >> 24) & 0xFF),
        static_cast<char>((v >> 16) & 0xFF),
        static_cast<char>((v >> 8)  & 0xFF),
        static_cast<char>(v & 0xFF)
    };
    os.write(b, 4);
}

static bool compress_klz_stream(std::istream& is, std::ostream& os, uint64_t total_size) {
    if (total_size > 0xFFFFFFFFull) {
        std::cerr << "文件过大（>4GB），不支持。\n";
        return false;
    }
    write_u32_be(os, static_cast<uint32_t>(total_size));

    const size_t CHUNK = 0x4000;
    std::vector<uint8_t> buf(CHUNK);

    uint64_t remaining = total_size;
    while (remaining > 0) {
        size_t to_read = static_cast<size_t>(std::min<uint64_t>(CHUNK, remaining));
        is.read(reinterpret_cast<char*>(buf.data()), static_cast<std::streamsize>(to_read));
        if (is.gcount() != static_cast<std::streamsize>(to_read)) return false;

        // 先尝试压缩
        auto comp = compress_lz77_block(buf.data(), to_read);

        // 关键：压缩块必须“可按老解码器还原到同样长度”，否则回退为原始块
        bool use_compressed = (comp.size() < to_read) && (comp.size() <= 0x7FFF);
        if (use_compressed) {
            auto test = ref_decompress_lz77_block(comp.data(), comp.size());
            if (test.size() != to_read) {
                use_compressed = false; // 不匹配则回退
            }
        }

        if (use_compressed) {
            write_u16_be(os, static_cast<uint16_t>(comp.size())); // 高位=0 → 压缩块
            os.write(reinterpret_cast<const char*>(comp.data()), static_cast<std::streamsize>(comp.size()));
        } else {
            // 原始块：头固定 0x8000；数据必须是 0x4000 字节（仅最后一块可小于 0x4000）
            write_u16_be(os, 0x8000);
            os.write(reinterpret_cast<const char*>(buf.data()), static_cast<std::streamsize>(to_read));
        }

        remaining -= to_read;
    }
    return true;
}

static bool compress_one_file(const fs::path& src, const fs::path& dst) {
    std::ifstream ifs(src, std::ios::binary);
    if (!ifs) return false;

    std::error_code ec;
    uint64_t size = fs::file_size(src, ec);
    if (ec) {
        ifs.seekg(0, std::ios::end);
        size = static_cast<uint64_t>(ifs.tellg());
        ifs.seekg(0, std::ios::beg);
    }

    fs::create_directories(dst.parent_path(), ec);
    std::ofstream ofs(dst, std::ios::binary);
    if (!ofs) return false;

    return compress_klz_stream(ifs, ofs, size);
}

static size_t process_compress(const fs::path& input, const fs::path* out_root_opt) {
    std::vector<fs::path> files;
    std::error_code ec;

    if (fs::is_regular_file(input, ec)) {
        if (has_tm2_ext(input)) files.push_back(input);
    } else if (fs::is_directory(input, ec)) {
        for (auto it = fs::recursive_directory_iterator(input, fs::directory_options::skip_permission_denied, ec);
             it != fs::recursive_directory_iterator(); ++it) {
            if (it->is_regular_file(ec) && has_tm2_ext(it->path())) {
                files.push_back(it->path());
            }
        }
    } else {
        std::cout << "路径不存在: " << input << "\n";
        return 0;
    }

    const bool input_is_dir = fs::is_directory(input, ec);
    size_t ok = 0, total = files.size();

    for (const auto& p : files) {
        fs::path dst;
        if (out_root_opt) {
            if (input_is_dir) {
                fs::path rel = p.lexically_relative(input);
                dst = (*out_root_opt) / rel;
            } else {
                dst = (*out_root_opt) / p.filename();
            }
            dst.replace_extension(".klz");
        } else {
            dst = p; dst.replace_extension(".klz");
        }

        bool success = compress_one_file(p, dst);
        std::cout << (success ? "OK   " : "FAIL ") << ": " << p.string() << " -> " << dst.string() << "\n";
        if (success) ++ok;
    }

    std::cout << "Done. " << ok << "/" << total << " succeeded.\n";
    return ok;
}

// ========== 主程序 ==========

static void print_usage(const char* argv0) {
    std::cout << "用法:\n"
              << "  " << argv0 << " d <文件或目录> [输出根目录]   # .klz -> .tm2\n"
              << "  " << argv0 << " e <文件或目录> [输出根目录]   # .tm2 -> .klz\n";
}

int main(int argc, char* argv[]) {
    if (argc < 3) {
        print_usage(argv[0]);
        return 1;
    }

    char mode = argv[1][0];
    fs::path src = fs::path(argv[2]);
    fs::path out_root;
    fs::path* out_root_opt = nullptr;
    if (argc >= 4) {
        out_root = fs::path(argv[3]);
        out_root_opt = &out_root;
    }

    if (mode == 'd' || mode == 'D') {
        process_decompress(src, out_root_opt);
        return 0;
    } else if (mode == 'e' || mode == 'E') {
        process_compress(src, out_root_opt);
        return 0;
    } else {
        print_usage(argv[0]);
        return 1;
    }
}