#include <algorithm>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace fs = std::filesystem;

static constexpr uint32_t FLAG_COMPRESSED = 0x0400;
static constexpr uint32_t ALIGN_PAYLOAD = 16;

struct Chunk {
    std::array<uint8_t, 4> cid{};
    uint32_t data_size = 0;
    uint32_t hdr_size = 0;
    uint32_t flags = 0;
    std::vector<uint8_t> extra;
    std::vector<uint8_t> payload;
};

static uint32_t rd_u32(const std::vector<uint8_t>& b, size_t off) {
    return static_cast<uint32_t>(b.at(off)) |
           (static_cast<uint32_t>(b.at(off + 1)) << 8) |
           (static_cast<uint32_t>(b.at(off + 2)) << 16) |
           (static_cast<uint32_t>(b.at(off + 3)) << 24);
}

static void wr_u32(std::vector<uint8_t>& out, uint32_t v) {
    out.push_back(static_cast<uint8_t>(v & 0xFF));
    out.push_back(static_cast<uint8_t>((v >> 8) & 0xFF));
    out.push_back(static_cast<uint8_t>((v >> 16) & 0xFF));
    out.push_back(static_cast<uint8_t>((v >> 24) & 0xFF));
}

static std::vector<uint8_t> read_file(const fs::path& p) {
    std::ifstream f(p, std::ios::binary);
    if (!f) throw std::runtime_error("open failed: " + p.string());
    f.seekg(0, std::ios::end);
    std::streamsize n = f.tellg();
    f.seekg(0, std::ios::beg);
    if (n < 0) throw std::runtime_error("tell failed: " + p.string());
    std::vector<uint8_t> b(static_cast<size_t>(n));
    if (n && !f.read(reinterpret_cast<char*>(b.data()), n)) {
        throw std::runtime_error("read failed: " + p.string());
    }
    return b;
}

static void write_file(const fs::path& p, const std::vector<uint8_t>& b) {
    fs::create_directories(p.parent_path());
    std::ofstream f(p, std::ios::binary);
    if (!f) throw std::runtime_error("create failed: " + p.string());
    if (!b.empty() && !f.write(reinterpret_cast<const char*>(b.data()), static_cast<std::streamsize>(b.size()))) {
        throw std::runtime_error("write failed: " + p.string());
    }
}

static std::vector<Chunk> parse_chunks(const std::vector<uint8_t>& blob) {
    std::vector<Chunk> out;
    size_t off = 0, n = blob.size();
    while (off + 16 <= n) {
        Chunk c{};
        std::copy_n(blob.begin() + static_cast<std::ptrdiff_t>(off), 4, c.cid.begin());
        c.data_size = rd_u32(blob, off + 4);
        c.hdr_size = rd_u32(blob, off + 8);
        c.flags = rd_u32(blob, off + 12);
        if (c.hdr_size < 16) throw std::runtime_error("invalid hdr_size");
        size_t end = off + static_cast<size_t>(c.hdr_size) + static_cast<size_t>(c.data_size);
        if (end > n) throw std::runtime_error("chunk out of range");
        c.extra.assign(blob.begin() + static_cast<std::ptrdiff_t>(off + 16), blob.begin() + static_cast<std::ptrdiff_t>(off + c.hdr_size));
        c.payload.assign(blob.begin() + static_cast<std::ptrdiff_t>(off + c.hdr_size), blob.begin() + static_cast<std::ptrdiff_t>(end));
        out.push_back(std::move(c));
        off = end;
        if (out.back().cid == std::array<uint8_t, 4>{'E', 'O', 'F', 'C'}) break;
    }
    return out;
}

static std::vector<uint8_t> build_chunks(const std::vector<Chunk>& chunks) {
    std::vector<uint8_t> out;
    for (const auto& c : chunks) {
        out.insert(out.end(), c.cid.begin(), c.cid.end());
        wr_u32(out, c.data_size);
        wr_u32(out, c.hdr_size);
        wr_u32(out, c.flags);
        out.insert(out.end(), c.extra.begin(), c.extra.end());
        out.insert(out.end(), c.payload.begin(), c.payload.end());
    }
    return out;
}

struct BitReaderInv {
    const std::vector<uint8_t>& s;
    size_t sp = 0;
    uint8_t bits_left = 1;
    uint8_t cur = 0;

    explicit BitReaderInv(const std::vector<uint8_t>& src) : s(src) {}

    uint8_t read_inv_byte() {
        if (sp >= s.size()) throw std::runtime_error("compressed stream truncated");
        return static_cast<uint8_t>(~s[sp++]);
    }

    uint8_t next_bit() {
        --bits_left;
        if (bits_left == 0) {
            cur = read_inv_byte();
            bits_left = 8;
        }
        uint8_t b = cur & 1;
        cur >>= 1;
        return b;
    }
};

static std::array<uint32_t, 4> parse_comp_header16(const std::vector<uint8_t>& p, size_t& used) {
    if (p.size() < 16) throw std::runtime_error("compressed payload too short for header");
    size_t pos = 0;
    uint8_t bits_left = 0, cur = 0;
    auto next_bit = [&]() -> uint8_t {
        if (bits_left == 0) {
            if (pos >= p.size()) throw std::runtime_error("header truncated");
            cur = p[pos++];
            bits_left = 8;
        }
        --bits_left;
        return static_cast<uint8_t>((cur >> bits_left) & 1);
    };
    std::array<uint32_t, 4> v{};
    for (int k = 0; k < 4; ++k) {
        uint32_t x = 0;
        for (int i = 0; i < 32; ++i) x |= (static_cast<uint32_t>(next_bit()) << i);
        v[k] = x;
    }
    used = pos;
    return v;
}

static std::vector<uint8_t> build_comp_header16(uint32_t w0, uint32_t w1, uint32_t w2, uint32_t w3) {
    std::vector<uint8_t> out;
    out.reserve(16);
    uint8_t cur = 0;
    int bit_in_byte = 0;
    auto put_bit = [&](uint8_t b) {
        cur = static_cast<uint8_t>((cur << 1) | (b & 1));
        ++bit_in_byte;
        if (bit_in_byte == 8) {
            out.push_back(cur);
            cur = 0;
            bit_in_byte = 0;
        }
    };
    const uint32_t vals[4] = {w0, w1, w2, w3};
    for (uint32_t x : vals) {
        for (int i = 0; i < 32; ++i) put_bit(static_cast<uint8_t>((x >> i) & 1));
    }
    if (bit_in_byte) out.push_back(static_cast<uint8_t>(cur << (8 - bit_in_byte)));
    if (out.size() != 16) throw std::runtime_error("header build size error");
    return out;
}

static std::pair<std::vector<uint8_t>, size_t> prs_decompress_inv_strict(const std::vector<uint8_t>& src, uint32_t expected_len) {
    BitReaderInv br(src);
    std::vector<uint8_t> out;
    out.reserve(expected_len);
    std::vector<uint8_t> win(0x2000, 0);
    uint32_t wp = 0;

    for (;;) {
        while (br.next_bit() == 1) {
            uint8_t b = br.read_inv_byte();
            out.push_back(b);
            win[wp & 0x1FFF] = b;
            ++wp;
        }

        int disp = 0;
        int len = 0;
        if (br.next_bit() == 1) {
            uint8_t b0 = br.read_inv_byte();
            uint8_t b1 = br.read_inv_byte();
            if (b0 == 0 && b1 == 0) break;
            len = b0 & 7;
            disp = ((static_cast<int>(b1) << 5) + (b0 >> 3)) - 0x2000;
            if (len == 0) {
                len = static_cast<int>(br.read_inv_byte()) + 1;
            } else {
                len += 2;
            }
        } else {
            int b0 = br.next_bit();
            int b1 = br.next_bit();
            len = ((b0 << 1) | b1) + 2;
            disp = static_cast<int>(br.read_inv_byte()) - 0x100;
        }

        for (int i = 0; i < len; ++i) {
            uint8_t c = win[(wp + static_cast<uint32_t>(disp)) & 0x1FFF];
            out.push_back(c);
            win[wp & 0x1FFF] = c;
            ++wp;
        }
    }
    if (out.size() != expected_len) throw std::runtime_error("decoded size mismatch");
    return {out, br.sp};
}

static std::vector<uint8_t> prs_compress_inv_literal_only(const std::vector<uint8_t>& raw) {
    std::vector<uint8_t> plain(1, 0);
    size_t ctrl_pos = 0;
    uint8_t bitpos = 0;

    auto put_bit = [&](uint8_t bit, bool save_after) {
        plain[ctrl_pos] = static_cast<uint8_t>(plain[ctrl_pos] >> 1);
        plain[ctrl_pos] = static_cast<uint8_t>(plain[ctrl_pos] | ((bit ? 1u : 0u) << 7));
        ++bitpos;
        if (save_after && bitpos >= 8) {
            bitpos = 0;
            ctrl_pos = plain.size();
            plain.push_back(0);
        }
    };
    auto put_data = [&](uint8_t b) { plain.push_back(b); };
    auto control_save = [&]() {
        if (bitpos >= 8) {
            bitpos = 0;
            ctrl_pos = plain.size();
            plain.push_back(0);
        }
    };

    for (uint8_t b : raw) {
        put_bit(1, false);
        put_data(b);
        control_save();
    }

    put_bit(0, true);
    put_bit(1, true);
    if (bitpos != 0) {
        plain[ctrl_pos] = static_cast<uint8_t>(((static_cast<uint16_t>(plain[ctrl_pos]) << bitpos) >> 8) & 0xFF);
    } else if (!plain.empty()) {
        plain.pop_back();
    }
    plain.push_back(0);
    plain.push_back(0);

    std::vector<uint8_t> out;
    out.reserve(plain.size());
    for (uint8_t b : plain) out.push_back(static_cast<uint8_t>(~b));
    return out;
}

static std::vector<uint8_t> prs_compress_inv(const std::vector<uint8_t>& raw) {
    std::vector<uint8_t> plain(1, 0);
    size_t ctrl_pos = 0;
    uint8_t bitpos = 0;

    auto put_bit = [&](uint8_t bit, bool save_after) {
        plain[ctrl_pos] = static_cast<uint8_t>(plain[ctrl_pos] >> 1);
        plain[ctrl_pos] = static_cast<uint8_t>(plain[ctrl_pos] | ((bit ? 1u : 0u) << 7));
        ++bitpos;
        if (save_after && bitpos >= 8) {
            bitpos = 0;
            ctrl_pos = plain.size();
            plain.push_back(0);
        }
    };
    auto control_save = [&]() {
        if (bitpos >= 8) {
            bitpos = 0;
            ctrl_pos = plain.size();
            plain.push_back(0);
        }
    };
    auto put_data = [&](uint8_t b) { plain.push_back(b); };
    auto emit_literal = [&](uint8_t b) {
        put_bit(1, false);
        put_data(b);
        control_save();
    };
    auto emit_short = [&](int disp, int len) {
        int v = len - 2;
        put_bit(0, true);
        put_bit(0, true);
        put_bit(static_cast<uint8_t>((v >> 1) & 1), true);
        put_bit(static_cast<uint8_t>(v & 1), false);
        put_data(static_cast<uint8_t>(disp + 0x100));
        control_save();
    };
    auto emit_long = [&](int disp, int len) {
        int off = disp + 0x2000;
        uint8_t b0 = static_cast<uint8_t>((off & 0x1F) << 3);
        uint8_t b1 = static_cast<uint8_t>((off >> 5) & 0xFF);
        put_bit(0, true);
        put_bit(1, false);
        if (len >= 2 && len <= 9) {
            b0 = static_cast<uint8_t>(b0 | ((len - 2) & 7));
            put_data(b0);
            put_data(b1);
            control_save();
        } else {
            put_data(b0);
            put_data(b1);
            put_data(static_cast<uint8_t>(len - 1));
            control_save();
        }
    };

    const int n = static_cast<int>(raw.size());
    int i = 0;
    while (i < n) {
        int best_len = 0;
        int best_disp = 0;
        int y_min = std::max(0, i - 0x1FFF);
        for (int y = i - 1; y >= y_min; --y) {
            if (raw[y] != raw[i]) continue;
            int l = 1;
            while (l < 256 && i + l < n && y + l < i && raw[y + l] == raw[i + l]) ++l;
            if (l >= 3 && l > best_len) {
                best_len = l;
                best_disp = y - i;
                if (best_len == 255) break;
            }
        }
        if (best_len >= 3) {
            if (best_disp >= -0x100 && best_len <= 5) emit_short(best_disp, best_len);
            else emit_long(best_disp, best_len);
            i += best_len;
        } else {
            emit_literal(raw[i]);
            ++i;
        }
    }

    put_bit(0, true);
    put_bit(1, true);
    if (bitpos != 0) {
        plain[ctrl_pos] = static_cast<uint8_t>(((static_cast<uint16_t>(plain[ctrl_pos]) << bitpos) >> 8) & 0xFF);
    } else if (!plain.empty()) {
        plain.pop_back();
    }
    plain.push_back(0);
    plain.push_back(0);

    std::vector<uint8_t> out;
    out.reserve(plain.size());
    for (uint8_t b : plain) out.push_back(static_cast<uint8_t>(~b));
    return out;
}

static Chunk decode_chunk_u(const Chunk& c) {
    if ((c.flags & FLAG_COMPRESSED) == 0) return c;
    size_t hsz = 0;
    auto h = parse_comp_header16(c.payload, hsz);
    std::vector<uint8_t> body(c.payload.begin() + static_cast<std::ptrdiff_t>(hsz), c.payload.end());
    auto dec = prs_decompress_inv_strict(body, h[0]);
    const size_t used = dec.second;
    for (size_t i = used; i < body.size(); ++i) {
        if (body[i] != 0) throw std::runtime_error("non-zero trailing bytes in compressed chunk");
    }
    Chunk o = c;
    o.flags &= ~FLAG_COMPRESSED;
    o.payload = std::move(dec.first);
    o.data_size = static_cast<uint32_t>(o.payload.size());
    return o;
}

static Chunk encode_chunk_p(const Chunk& c) {
    if (c.cid == std::array<uint8_t, 4>{'E', 'O', 'F', 'C'} || c.payload.empty()) return c;
    auto prs = prs_compress_inv(c.payload);
    auto hdr = build_comp_header16(static_cast<uint32_t>(c.payload.size()), 0x100u, 0xFFFFFFFFu, 0xFFFFFFFFu);
    std::vector<uint8_t> payload;
    payload.reserve(hdr.size() + prs.size() + 16);
    payload.insert(payload.end(), hdr.begin(), hdr.end());
    payload.insert(payload.end(), prs.begin(), prs.end());
    size_t pad = (ALIGN_PAYLOAD - (payload.size() % ALIGN_PAYLOAD)) % ALIGN_PAYLOAD;
    payload.insert(payload.end(), pad, 0);
    Chunk o = c;
    o.flags |= FLAG_COMPRESSED;
    o.payload = std::move(payload);
    o.data_size = static_cast<uint32_t>(o.payload.size());
    return o;
}

static std::vector<fs::path> collect_msx(const fs::path& root) {
    std::vector<fs::path> files;
    for (auto& e : fs::recursive_directory_iterator(root)) {
        if (!e.is_regular_file()) continue;
        std::string ext = e.path().extension().string();
        std::transform(ext.begin(), ext.end(), ext.begin(), [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
        if (ext == ".msx") files.push_back(e.path());
    }
    std::sort(files.begin(), files.end());
    return files;
}

static int run_u(const fs::path& in_dir, const fs::path& out_dir) {
    auto files = collect_msx(in_dir);
    for (const auto& src : files) {
        try {
            auto raw = read_file(src);
            auto chunks = parse_chunks(raw);
            std::vector<Chunk> out;
            out.reserve(chunks.size());
            for (const auto& c : chunks) out.push_back(decode_chunk_u(c));
            auto blob = build_chunks(out);
            auto rel = src.lexically_relative(in_dir);
            if (rel.empty()) rel = src.filename();
            write_file(out_dir / rel, blob);
            std::cout << src.filename().string() << "\n";
        } catch (const std::exception& e) {
            (void)e;
        }
    }
    return 0;
}

static int run_p(const fs::path& in_dir, const fs::path& out_dir) {
    auto files = collect_msx(in_dir);
    for (const auto& src : files) {
        try {
            auto raw = read_file(src);
            auto chunks = parse_chunks(raw);
            std::vector<Chunk> out;
            out.reserve(chunks.size());
            for (const auto& c : chunks) out.push_back(encode_chunk_p(c));
            auto blob = build_chunks(out);
            auto rel = src.lexically_relative(in_dir);
            if (rel.empty()) rel = src.filename();
            write_file(out_dir / rel, blob);
            std::cout << src.filename().string() << "\n";
        } catch (const std::exception& e) {
            (void)e;
        }
    }
    return 0;
}

int main(int argc, char** argv) {
    try {
        if (argc != 4) {
            std::cerr << "Usage: msx <u|p> <input_dir> <output_dir>\n";
            return 2;
        }
        std::string mode = argv[1];
        fs::path in_dir = fs::absolute(fs::path(argv[2]));
        fs::path out_dir = fs::absolute(fs::path(argv[3]));
        if (!fs::is_directory(in_dir)) {
            std::cerr << "input is not a folder: " << in_dir.string() << "\n";
            return 2;
        }
        if (mode == "u") return run_u(in_dir, out_dir);
        if (mode == "p") return run_p(in_dir, out_dir);
        std::cerr << "invalid mode: " << mode << "\n";
        return 2;
    } catch (const std::exception& e) {
        std::cerr << "fatal: " << e.what() << "\n";
        return 1;
    }
}
