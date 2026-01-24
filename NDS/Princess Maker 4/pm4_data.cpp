#include <cstdint>
#include <vector>
#include <string>
#include <fstream>
#include <iostream>
#include <filesystem>
#include <algorithm>
#include <cstdio>
#include <clocale>
#include <locale>

#ifdef _WIN32
#include <windows.h>
#include <cstring>
#endif

class LZSS {
public:
    enum class Type { LZ08, LZ12 };

    static bool decompress(const std::vector<uint8_t>& in, std::vector<uint8_t>& out) {
        if (in.size() < 8) return false;
        bool is_lz08 = in[0] == 'L' && in[1] == 'Z' && in[2] == '0' && in[3] == '8';
        bool is_lz12 = in[0] == 'L' && in[1] == 'Z' && in[2] == '1' && in[3] == '2';
        if (!is_lz08 && !is_lz12) return false;
        int n = is_lz12 ? 4096 : 512;
        int f = is_lz12 ? 18 : 130;
        uint32_t size = in[4] | (uint32_t(in[5]) << 8) | (uint32_t(in[6]) << 16) | (uint32_t(in[7]) << 24);
        std::vector<uint8_t> text_buf(4096);
        int r = n - f;
        for (int i = 0; i < r; ++i) text_buf[i] = 0;
        out.clear();
        out.reserve(size);
        size_t pos = 8;
        int flags = 0;
        while (size > 0) {
            flags >>= 1;
            if ((flags & 0x100) == 0) {
                if (pos >= in.size()) break;
                flags = in[pos++] | 0xFF00;
            }
            if (flags & 1) {
                if (pos >= in.size()) break;
                uint8_t c = in[pos++];
                out.push_back(c);
                text_buf[r] = c;
                r = (r + 1) & (n - 1);
                --size;
            } else {
                if (pos + 1 >= in.size()) break;
                int i = in[pos];
                int j = in[pos + 1];
                pos += 2;
                if (is_lz12) {
                    i |= (j & 0xF0) << 4;
                    j = (j & 0x0F) + 2;
                } else {
                    i |= (j & 0x80) << 1;
                    j = (j & 0x7F) + 2;
                }
                for (int k = 0; k <= j && size > 0; ++k) {
                    uint8_t c = text_buf[(i + k) & (n - 1)];
                    out.push_back(c);
                    text_buf[r] = c;
                    r = (r + 1) & (n - 1);
                    --size;
                }
            }
        }
        return size == 0;
    }

    static bool compress(const std::vector<uint8_t>& in, Type type, std::vector<uint8_t>& out) {
        static const Params p_lz08{512, 130, 3, 512 - 130, false, "LZ08"};
        static const Params p_lz12{4096, 18, 3, 4096 - 18, true, "LZ12"};
        const Params& p = type == Type::LZ12 ? p_lz12 : p_lz08;
        std::vector<uint8_t> body;
        encode(in, p, body);
        out.clear();
        out.reserve(8 + body.size());
        out.push_back(p.magic[0]);
        out.push_back(p.magic[1]);
        out.push_back(p.magic[2]);
        out.push_back(p.magic[3]);
        uint32_t sz = static_cast<uint32_t>(in.size());
        out.push_back(static_cast<uint8_t>(sz & 0xFF));
        out.push_back(static_cast<uint8_t>((sz >> 8) & 0xFF));
        out.push_back(static_cast<uint8_t>((sz >> 16) & 0xFF));
        out.push_back(static_cast<uint8_t>((sz >> 24) & 0xFF));
        out.insert(out.end(), body.begin(), body.end());
        return true;
    }

private:
    struct Params {
        int window;
        int max_match;
        int min_match;
        int ring_init;
        bool is_lz12;
        const char* magic;
    };

    static void encode(const std::vector<uint8_t>& in, const Params& p, std::vector<uint8_t>& out) {
        const uint8_t* src = in.data();
        int n = static_cast<int>(in.size());
        const int RING_SIZE = p.window;
        const int RING_MASK = RING_SIZE - 1;
        const int MAX_MATCH = p.max_match;
        const int MIN_MATCH = p.min_match;
        const int RING_INIT = p.ring_init;
        std::vector<int> head(1 << 16, -1);
        std::vector<int> chain(RING_SIZE, -1);
        out.clear();
        out.reserve(n + (n >> 3) + 16);
        int sp = 0;
        while (sp < n) {
            size_t fp = out.size();
            out.push_back(0);
            uint8_t flags = 0;
            for (int bit = 0; bit < 8 && sp < n; ++bit) {
                int best = 0;
                int off = 0;
                if (sp + 1 < n) {
                    int h = (static_cast<int>(src[sp]) << 8) | src[sp + 1];
                    int c = 128;
                    for (int pos = head[h];
                         pos >= 0 && sp - pos <= RING_SIZE && c-- > 0;
                         pos = chain[pos & RING_MASK]) {
                        int len = 0;
                        while (len < MAX_MATCH && sp + len < n && src[pos + len] == src[sp + len]) ++len;
                        if (len > best) {
                            best = len;
                            off = (RING_INIT + pos) & RING_MASK;
                            if (len == MAX_MATCH) break;
                        }
                    }
                }
                if (best >= MIN_MATCH) {
                    if (p.is_lz12) {
                        uint8_t b1 = static_cast<uint8_t>(off);
                        uint8_t b2 = static_cast<uint8_t>(((off >> 4) & 0xF0) | (best - 3));
                        out.push_back(b1);
                        out.push_back(b2);
                    } else {
                        uint8_t b1 = static_cast<uint8_t>(off);
                        uint8_t b2 = static_cast<uint8_t>(((off & 0x100) >> 1) | (best - 3));
                        out.push_back(b1);
                        out.push_back(b2);
                    }
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
                    out.push_back(src[sp]);
                    ++sp;
                }
            }
            out[fp] = flags;
        }
    }
};

namespace fs = std::filesystem;

struct CsvRow {
    std::string path;
    std::string type;
};

static bool read_file(const fs::path& p, std::vector<uint8_t>& data) {
    std::ifstream f(p, std::ios::binary);
    if (!f) return false;
    f.seekg(0, std::ios::end);
    std::streamsize size = f.tellg();
    if (size < 0) return false;
    f.seekg(0, std::ios::beg);
    data.resize(static_cast<size_t>(size));
    if (size > 0) f.read(reinterpret_cast<char*>(data.data()), size);
    return true;
}

static bool write_file(const fs::path& p, const std::vector<uint8_t>& data) {
    fs::create_directories(p.parent_path());
    std::ofstream f(p, std::ios::binary);
    if (!f) return false;
    if (!data.empty()) f.write(reinterpret_cast<const char*>(data.data()), static_cast<std::streamsize>(data.size()));
    return true;
}

static bool write_empty_file(const fs::path& p) {
    fs::create_directories(p.parent_path());
    std::ofstream f(p, std::ios::binary);
    return bool(f);
}

static bool write_csv(const fs::path& p, const std::vector<CsvRow>& rows) {
    fs::create_directories(p.parent_path());
    std::ofstream f(p);
    if (!f) return false;
    for (const auto& r : rows) f << r.path << "," << r.type << "\n";
    return true;
}

static std::vector<CsvRow> read_csv(const fs::path& p) {
    std::vector<CsvRow> rows;
    std::ifstream f(p);
    if (!f) return rows;
    std::string line;
    while (std::getline(f, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.empty()) continue;
        auto pos = line.rfind(',');
        if (pos == std::string::npos) continue;
        CsvRow r;
        r.path = line.substr(0, pos);
        r.type = line.substr(pos + 1);
        rows.push_back(std::move(r));
    }
    return rows;
}

static uint32_t parse_u32(const std::string& s) {
    size_t idx = 0;
    unsigned long v = std::stoul(s, &idx, 0);
    return static_cast<uint32_t>(v);
}

#ifdef _WIN32
static fs::path make_path(const char* s) {
    if (!s) return fs::path();
    int lenA = static_cast<int>(std::strlen(s));
    if (lenA == 0) return fs::path();
    int lenW = MultiByteToWideChar(CP_ACP, 0, s, lenA, nullptr, 0);
    if (!lenW) return fs::path();
    std::wstring ws(lenW, L'\0');
    MultiByteToWideChar(CP_ACP, 0, s, lenA, &ws[0], lenW);
    return fs::path(ws);
}
#else
static fs::path make_path(const char* s) {
    return fs::u8path(s);
}
#endif

static void cmd_extract(const fs::path& arm9_path,
                        const fs::path& data_path,
                        const fs::path& out_dir,
                        uint32_t offset_start,
                        int file_count) {
    offset_start &= ~3u;
    std::ifstream f_arm9(arm9_path, std::ios::binary);
    if (!f_arm9) {
        std::cout << "open arm9 fail\n";
        return;
    }
    f_arm9.seekg(0, std::ios::end);
    std::streamsize arm9_size = f_arm9.tellg();
    f_arm9.seekg(0, std::ios::beg);
    if (offset_start + uint32_t(file_count) * 4 > static_cast<uint32_t>(arm9_size)) {
        std::cout << "offset table out of range\n";
        return;
    }
    f_arm9.seekg(offset_start, std::ios::beg);
    std::vector<uint32_t> offsets(file_count);
    for (int i = 0; i < file_count; ++i) {
        uint8_t b[4];
        f_arm9.read(reinterpret_cast<char*>(b), 4);
        offsets[i] = uint32_t(b[0]) | (uint32_t(b[1]) << 8) | (uint32_t(b[2]) << 16) | (uint32_t(b[3]) << 24);
    }
    std::vector<uint8_t> data_content;
    if (!read_file(data_path, data_content)) {
        std::cout << "read data fail\n";
        return;
    }
    size_t data_size = data_content.size();
    fs::create_directories(out_dir);
    std::vector<CsvRow> rows;
    rows.reserve(file_count);
    for (int i = 0; i < file_count; ++i) {
        uint32_t file_start = offsets[i];
        if (file_start + 4 > data_size) file_start = 0;
        uint32_t start = 0;
        uint32_t end = 0;
        if (file_start + 4 <= data_size) {
            start = file_start + 4;
            if (i + 1 < file_count) end = offsets[i + 1];
            else end = static_cast<uint32_t>(data_size);
            if (end > data_size || end < start) start = end = 0;
        }
        std::vector<uint8_t> file_data;
        if (start < end) file_data.assign(data_content.begin() + start, data_content.begin() + end);
        std::string comp = "NZ";
        if (file_data.size() >= 4) {
            if (file_data[0] == 'L' && file_data[1] == 'Z' && file_data[2] == '0' && file_data[3] == '8') comp = "LZ08";
            else if (file_data[0] == 'L' && file_data[1] == 'Z' && file_data[2] == '1' && file_data[3] == '2') comp = "LZ12";
        }
        std::vector<uint8_t> out_data = file_data;
        if (comp == "LZ08" || comp == "LZ12") {
            std::vector<uint8_t> dec;
            if (LZSS::decompress(file_data, dec)) out_data.swap(dec);
        }
        char name[16];
        std::snprintf(name, sizeof(name), "%08X.bin", i);
        fs::path subdir = out_dir / comp;
        fs::create_directories(subdir);
        fs::path out_path = subdir / name;
        if (!out_data.empty()) write_file(out_path, out_data);
        else write_empty_file(out_path);
        CsvRow row;
        row.path = (fs::path(comp) / name).generic_string();
        row.type = comp;
        rows.push_back(std::move(row));
        if ((i + 1) % 500 == 0 || i == 0) {
            std::cout << "extract " << (i + 1) << "/" << file_count << "\n";
        }
    }
    write_csv(out_dir / "file_list.csv", rows);
}

static void cmd_pack(const fs::path& in_dir,
                     const fs::path& orig_arm9,
                     const fs::path& out_arm9,
                     const fs::path& out_data,
                     uint32_t offset_start) {
    offset_start &= ~3u;

    auto rows = read_csv(in_dir / "file_list.csv");
    if (rows.empty()) {
        std::cout << "no file_list.csv\n";
        return;
    }

    if (!out_data.parent_path().empty())
        fs::create_directories(out_data.parent_path());

    std::ofstream f_data(out_data, std::ios::binary);
    if (!f_data) {
        std::cout << "open out_data fail\n";
        return;
    }

    std::vector<uint32_t> new_offsets;
    new_offsets.reserve(rows.size());
    uint32_t current_offset = 0;

    for (size_t i = 0; i < rows.size(); ++i) {
        new_offsets.push_back(current_offset);

        fs::path p = in_dir / rows[i].path;
        std::vector<uint8_t> file_data;
        read_file(p, file_data);

        bool is_lz = (rows[i].type == "LZ08" || rows[i].type == "LZ12");

        std::vector<uint8_t> final_data;
        if (is_lz) {
            LZSS::Type t = rows[i].type == "LZ08" ? LZSS::Type::LZ08 : LZSS::Type::LZ12;
            LZSS::compress(file_data, t, final_data);
        } else {
            final_data = file_data;
        }

        size_t raw_size    = final_data.size();
        size_t stored_size = raw_size;

        if (is_lz) {
            stored_size = (raw_size + 3) & ~size_t(3); // 4 字节对齐
        }

        uint32_t sz = static_cast<uint32_t>(stored_size);
        uint8_t b[4] = {
            static_cast<uint8_t>(sz & 0xFF),
            static_cast<uint8_t>((sz >> 8) & 0xFF),
            static_cast<uint8_t>((sz >> 16) & 0xFF),
            static_cast<uint8_t>((sz >> 24) & 0xFF)
        };
        f_data.write(reinterpret_cast<char*>(b), 4);
        current_offset += 4;

        if (!final_data.empty()) {
            f_data.write(reinterpret_cast<const char*>(final_data.data()),
                         static_cast<std::streamsize>(final_data.size()));
        }

        if (stored_size > raw_size) {
            size_t pad = stored_size - raw_size;
            static const uint8_t zeros[4] = {0, 0, 0, 0};
            while (pad > 0) {
                size_t chunk = std::min(pad, sizeof(zeros));
                f_data.write(reinterpret_cast<const char*>(zeros),
                             static_cast<std::streamsize>(chunk));
                pad -= chunk;
            }
        }

        current_offset += static_cast<uint32_t>(stored_size);

        if ((i + 1) % 500 == 0 || i == 0) {
            std::cout << "pack " << (i + 1) << "/" << rows.size() << "\n";
        }
    }

    f_data.close();

    std::vector<uint8_t> arm9;
    if (!read_file(orig_arm9, arm9)) {
        std::cout << "read arm9 fail\n";
        return;
    }

    size_t need = offset_start + new_offsets.size() * 4;
    if (need > arm9.size()) {
        std::cout << "offset table too small\n";
        return;
    }

    for (size_t i = 0; i < new_offsets.size(); ++i) {
        uint32_t v = new_offsets[i];
        size_t pos = offset_start + i * 4;
        arm9[pos]     = static_cast<uint8_t>(v & 0xFF);
        arm9[pos + 1] = static_cast<uint8_t>((v >> 8) & 0xFF);
        arm9[pos + 2] = static_cast<uint8_t>((v >> 16) & 0xFF);
        arm9[pos + 3] = static_cast<uint8_t>((v >> 24) & 0xFF);
    }

    write_file(out_arm9, arm9);
}

int main(int argc, char** argv) {
    std::setlocale(LC_ALL, "");
    std::cout << "NDS LZ08/LZ12 extract+pack tool\n";
    if (argc < 2) {
        std::cout << "Usage:\n";
        std::cout << "  " << argv[0] << " u <arm9.bin> <data.bin> <out_dir> <offset> <file_count>\n";
        std::cout << "  " << argv[0] << " p <in_dir> <orig_arm9.bin> <out_arm9.bin> <out_data.bin> <offset>\n";
        return 1;
    }
    std::string mode = argv[1];
    try {
        if (mode == "u") {
            if (argc != 7) {
                std::cout << "args: u <arm9> <data> <out_dir> <offset> <file_count>\n";
                return 1;
            }
            fs::path arm9    = make_path(argv[2]);
            fs::path data    = make_path(argv[3]);
            fs::path out_dir = make_path(argv[4]);
            uint32_t offset  = parse_u32(argv[5]);
            int file_count   = std::stoi(argv[6]);
            cmd_extract(arm9, data, out_dir, offset, file_count);
        } else if (mode == "p") {
            if (argc != 7) {
                std::cout << "args: p <in_dir> <orig_arm9> <out_arm9> <out_data> <offset>\n";
                return 1;
            }
            fs::path in_dir    = make_path(argv[2]);
            fs::path orig_arm9 = make_path(argv[3]);
            fs::path out_arm9  = make_path(argv[4]);
            fs::path out_data  = make_path(argv[5]);
            uint32_t offset    = parse_u32(argv[6]);
            cmd_pack(in_dir, orig_arm9, out_arm9, out_data, offset);
        } else {
            std::cout << "unknown mode\n";
            return 1;
        }
    } catch (const std::exception& e) {
        std::cout << "error: " << e.what() << "\n";
        return 1;
    }
    return 0;
}