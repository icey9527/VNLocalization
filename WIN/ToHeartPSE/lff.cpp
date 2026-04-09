#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <iostream>
#include <optional>
#include <string>
#include <vector>

#include <windows.h>
#include <gdiplus.h>

namespace fs = std::filesystem;
using Gdiplus::Bitmap;
using Gdiplus::BitmapData;
using Gdiplus::Color;
using Gdiplus::GdiplusShutdown;
using Gdiplus::GdiplusStartup;
using Gdiplus::GdiplusStartupInput;
using Gdiplus::ImageLockModeRead;
using Gdiplus::ImageLockModeWrite;
using Gdiplus::Rect;
using Gdiplus::Status;

namespace {

constexpr std::uint16_t kWidth = 640;
constexpr std::uint16_t kHeight = 480;
constexpr std::uint16_t kX = 0;
constexpr std::uint16_t kY = 0;
constexpr std::uint32_t kHeaderSize = 20;
constexpr int kRingSize = 0x1000;
constexpr int kRingMask = kRingSize - 1;
constexpr int kRingInit = 4078;
constexpr int kMinMatch = 3;
constexpr int kMaxMatch = 18;

struct LffImage {
    std::uint16_t x = 0;
    std::uint16_t y = 0;
    std::uint16_t width = 0;
    std::uint16_t height = 0;
    std::uint32_t data_offset = 0;
    std::vector<std::uint8_t> pixels_bgr_bottom_up;
};

std::wstring widen(const fs::path& path) {
    return path.wstring();
}

std::string narrow(const fs::path& path) {
    return path.string();
}

std::string ascii_lower(std::string s) {
    std::transform(s.begin(), s.end(), s.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
    return s;
}

void write_u16le(std::vector<std::uint8_t>& out, std::uint16_t value) {
    out.push_back(static_cast<std::uint8_t>(value & 0xFF));
    out.push_back(static_cast<std::uint8_t>((value >> 8) & 0xFF));
}

void write_u32le(std::vector<std::uint8_t>& out, std::uint32_t value) {
    out.push_back(static_cast<std::uint8_t>(value & 0xFF));
    out.push_back(static_cast<std::uint8_t>((value >> 8) & 0xFF));
    out.push_back(static_cast<std::uint8_t>((value >> 16) & 0xFF));
    out.push_back(static_cast<std::uint8_t>((value >> 24) & 0xFF));
}

std::uint16_t read_u16le(const std::uint8_t* p) {
    return static_cast<std::uint16_t>(p[0] | (static_cast<std::uint16_t>(p[1]) << 8));
}

std::uint32_t read_u32le(const std::uint8_t* p) {
    return static_cast<std::uint32_t>(p[0])
         | (static_cast<std::uint32_t>(p[1]) << 8)
         | (static_cast<std::uint32_t>(p[2]) << 16)
         | (static_cast<std::uint32_t>(p[3]) << 24);
}

std::vector<std::uint8_t> read_file(const fs::path& path) {
    FILE* fp = std::fopen(path.string().c_str(), "rb");
    if (!fp) {
        throw std::runtime_error("failed to open " + narrow(path));
    }
    if (std::fseek(fp, 0, SEEK_END) != 0) {
        std::fclose(fp);
        throw std::runtime_error("failed to seek " + narrow(path));
    }
    long size = std::ftell(fp);
    if (size < 0) {
        std::fclose(fp);
        throw std::runtime_error("failed to tell " + narrow(path));
    }
    if (std::fseek(fp, 0, SEEK_SET) != 0) {
        std::fclose(fp);
        throw std::runtime_error("failed to rewind " + narrow(path));
    }
    std::vector<std::uint8_t> data(static_cast<std::size_t>(size));
    if (!data.empty() && std::fread(data.data(), 1, data.size(), fp) != data.size()) {
        std::fclose(fp);
        throw std::runtime_error("failed to read " + narrow(path));
    }
    std::fclose(fp);
    return data;
}

void write_file(const fs::path& path, const std::vector<std::uint8_t>& data) {
    fs::create_directories(path.parent_path());
    FILE* fp = std::fopen(path.string().c_str(), "wb");
    if (!fp) {
        throw std::runtime_error("failed to create " + narrow(path));
    }
    if (!data.empty() && std::fwrite(data.data(), 1, data.size(), fp) != data.size()) {
        std::fclose(fp);
        throw std::runtime_error("failed to write " + narrow(path));
    }
    std::fclose(fp);
}

bool lff_decompress(const std::uint8_t* src, std::size_t src_len, std::uint8_t* dst, std::size_t dst_len) {
    std::array<std::uint8_t, kRingSize> ring{};
    int ring_pos = kRingInit;
    std::size_t src_pos = 0;
    std::size_t dst_pos = 0;

    while (dst_pos < dst_len) {
        if (src_pos >= src_len) {
            return false;
        }

        std::uint16_t flags = static_cast<std::uint16_t>(((~src[src_pos]) & 0xFF) << 8) | 0x00FFu;
        ++src_pos;

        while (dst_pos < dst_len) {
            const bool literal = (flags & 0x8000u) != 0;
            flags = static_cast<std::uint16_t>((flags << 1) & 0xFFFFu);

            if (literal) {
                if (src_pos >= src_len) {
                    return false;
                }
                const std::uint8_t b = static_cast<std::uint8_t>(~src[src_pos++]);
                dst[dst_pos++] = b;
                ring[ring_pos] = b;
                ring_pos = (ring_pos + 1) & kRingMask;
            } else {
                if (src_pos + 1 >= src_len) {
                    return false;
                }
                const std::uint16_t pair = static_cast<std::uint16_t>(
                    ~(static_cast<std::uint16_t>(src[src_pos])
                    | (static_cast<std::uint16_t>(src[src_pos + 1]) << 8)));
                src_pos += 2;
                int offset = pair >> 4;
                int length = (pair & 0x0F) + kMinMatch;
                for (int i = 0; i < length && dst_pos < dst_len; ++i) {
                    const std::uint8_t b = ring[(offset + i) & kRingMask];
                    dst[dst_pos++] = b;
                    ring[ring_pos] = b;
                    ring_pos = (ring_pos + 1) & kRingMask;
                }
            }

            if ((flags & 0x00FFu) == 0) {
                break;
            }
        }
    }

    return true;
}

class LzssCompressor {
public:
    bool compress(const std::uint8_t* src, std::size_t src_len, std::vector<std::uint8_t>& dst) const {
        if (src_len == 0) {
            dst.clear();
            return true;
        }

        std::vector<int> head(1 << 16, -1);
        std::vector<int> chain(kRingSize, -1);
        dst.clear();
        dst.reserve(src_len + (src_len >> 3) + 16);

        int sp = 0;
        const int n = static_cast<int>(src_len);

        while (sp < n) {
            const std::size_t flag_pos = dst.size();
            dst.push_back(0);
            std::uint8_t control_inv = 0;

            for (int bit = 0; bit < 8 && sp < n; ++bit) {
                int best_len = 0;
                int best_off = 0;

                if (sp + 1 < n) {
                    const int h = (static_cast<int>(src[sp]) << 8) | src[sp + 1];
                    int budget = 128;
                    for (int p = head[h]; p >= 0 && sp - p <= kRingSize && budget-- > 0; p = chain[p & kRingMask]) {
                        int len = 0;
                        while (len < kMaxMatch && sp + len < n && src[p + len] == src[sp + len]) {
                            ++len;
                        }
                        if (len > best_len) {
                            best_len = len;
                            best_off = (kRingInit + p) & kRingMask;
                            if (len == kMaxMatch) {
                                break;
                            }
                        }
                    }
                }

                if (best_len >= kMinMatch) {
                    const std::uint16_t pair =
                        static_cast<std::uint16_t>((best_off << 4) | (best_len - kMinMatch));
                    write_u16le_inverted(dst, pair);

                    const int limit = std::min(best_len, n - sp - 1);
                    for (int i = 0; i < limit; ++i) {
                        add_index(head, chain, src, n, sp + i);
                    }
                    sp += best_len;
                } else {
                    control_inv |= static_cast<std::uint8_t>(1u << (7 - bit));
                    dst.push_back(static_cast<std::uint8_t>(~src[sp]));
                    add_index(head, chain, src, n, sp);
                    ++sp;
                }
            }

            dst[flag_pos] = static_cast<std::uint8_t>(~control_inv);
        }

        return true;
    }

private:
    static void write_u16le_inverted(std::vector<std::uint8_t>& out, std::uint16_t value) {
        out.push_back(static_cast<std::uint8_t>(~(value & 0xFF)));
        out.push_back(static_cast<std::uint8_t>(~((value >> 8) & 0xFF)));
    }

    static void add_index(std::vector<int>& head, std::vector<int>& chain, const std::uint8_t* src, int n, int pos) {
        if (pos + 1 >= n) {
            return;
        }
        const int h = (static_cast<int>(src[pos]) << 8) | src[pos + 1];
        const int idx = pos & kRingMask;
        chain[idx] = head[h];
        head[h] = pos;
    }
};

LffImage parse_lff(const fs::path& path) {
    const auto blob = read_file(path);
    if (blob.size() < kHeaderSize) {
        throw std::runtime_error("file too small: " + narrow(path));
    }
    if (std::memcmp(blob.data(), "LEAFFUL\0", 8) != 0) {
        throw std::runtime_error("bad magic: " + narrow(path));
    }

    LffImage image;
    image.x = read_u16le(blob.data() + 8);
    image.y = read_u16le(blob.data() + 10);
    image.width = read_u16le(blob.data() + 12);
    image.height = read_u16le(blob.data() + 14);
    image.data_offset = read_u32le(blob.data() + 16);

    if (image.data_offset < kHeaderSize || image.data_offset > blob.size()) {
        throw std::runtime_error("bad data offset: " + narrow(path));
    }

    const std::size_t pixel_size = static_cast<std::size_t>(image.width) * image.height * 3;
    image.pixels_bgr_bottom_up.resize(pixel_size);
    if (!lff_decompress(blob.data() + image.data_offset, blob.size() - image.data_offset,
                        image.pixels_bgr_bottom_up.data(), image.pixels_bgr_bottom_up.size())) {
        throw std::runtime_error("decompression failed: " + narrow(path));
    }

    return image;
}

std::vector<std::uint8_t> build_lff(const LffImage& image) {
    if (image.width != kWidth || image.height != kHeight || image.x != kX || image.y != kY) {
        throw std::runtime_error("only 640x480 LFF images with origin (0,0) are supported");
    }

    LzssCompressor compressor;
    std::vector<std::uint8_t> compressed;
    if (!compressor.compress(image.pixels_bgr_bottom_up.data(), image.pixels_bgr_bottom_up.size(), compressed)) {
        throw std::runtime_error("compression failed");
    }

    std::vector<std::uint8_t> out;
    out.reserve(kHeaderSize + compressed.size());
    out.insert(out.end(), {'L', 'E', 'A', 'F', 'F', 'U', 'L', '\0'});
    write_u16le(out, image.x);
    write_u16le(out, image.y);
    write_u16le(out, image.width);
    write_u16le(out, image.height);
    write_u32le(out, kHeaderSize);
    out.insert(out.end(), compressed.begin(), compressed.end());
    return out;
}

int get_png_encoder_clsid(CLSID* clsid) {
    UINT count = 0;
    UINT bytes = 0;
    if (Gdiplus::GetImageEncodersSize(&count, &bytes) != Gdiplus::Ok || bytes == 0) {
        return -1;
    }
    std::vector<std::uint8_t> buffer(bytes);
    auto* encoders = reinterpret_cast<Gdiplus::ImageCodecInfo*>(buffer.data());
    if (Gdiplus::GetImageEncoders(count, bytes, encoders) != Gdiplus::Ok) {
        return -1;
    }
    for (UINT i = 0; i < count; ++i) {
        if (std::wcscmp(encoders[i].MimeType, L"image/png") == 0) {
            *clsid = encoders[i].Clsid;
            return static_cast<int>(i);
        }
    }
    return -1;
}

void save_png(const LffImage& image, const fs::path& out_path) {
    Bitmap bitmap(image.width, image.height, PixelFormat24bppRGB);
    Rect rect(0, 0, image.width, image.height);
    BitmapData data{};
    if (bitmap.LockBits(&rect, ImageLockModeWrite, PixelFormat24bppRGB, &data) != Gdiplus::Ok) {
        throw std::runtime_error("LockBits failed for PNG save");
    }

    const int src_stride = image.width * 3;
    auto* dst_base = static_cast<std::uint8_t*>(data.Scan0);
    for (int y = 0; y < image.height; ++y) {
        const auto* src_row = image.pixels_bgr_bottom_up.data() + (image.height - 1 - y) * src_stride;
        auto* dst_row = dst_base + y * data.Stride;
        std::memcpy(dst_row, src_row, src_stride);
    }

    bitmap.UnlockBits(&data);

    CLSID clsid{};
    if (get_png_encoder_clsid(&clsid) < 0) {
        throw std::runtime_error("PNG encoder not found");
    }

    fs::create_directories(out_path.parent_path());
    if (bitmap.Save(widen(out_path).c_str(), &clsid, nullptr) != Gdiplus::Ok) {
        throw std::runtime_error("failed to save PNG: " + narrow(out_path));
    }
}

LffImage load_png_as_lff(const fs::path& path) {
    Bitmap bitmap(widen(path).c_str());
    if (bitmap.GetLastStatus() != Gdiplus::Ok) {
        throw std::runtime_error("failed to load PNG: " + narrow(path));
    }
    if (bitmap.GetWidth() != kWidth || bitmap.GetHeight() != kHeight) {
        throw std::runtime_error("PNG must be exactly 640x480: " + narrow(path));
    }

    Rect rect(0, 0, kWidth, kHeight);
    BitmapData data{};
    if (bitmap.LockBits(&rect, ImageLockModeRead, PixelFormat32bppARGB, &data) != Gdiplus::Ok) {
        throw std::runtime_error("LockBits failed for PNG load");
    }

    LffImage image;
    image.x = kX;
    image.y = kY;
    image.width = kWidth;
    image.height = kHeight;
    image.data_offset = kHeaderSize;
    image.pixels_bgr_bottom_up.resize(static_cast<std::size_t>(kWidth) * kHeight * 3);

    for (int y = 0; y < kHeight; ++y) {
        const auto* src_row = static_cast<const std::uint8_t*>(data.Scan0) + y * data.Stride;
        auto* dst_row = image.pixels_bgr_bottom_up.data() + (kHeight - 1 - y) * kWidth * 3;
        for (int x = 0; x < kWidth; ++x) {
            dst_row[x * 3 + 0] = src_row[x * 4 + 0];
            dst_row[x * 3 + 1] = src_row[x * 4 + 1];
            dst_row[x * 3 + 2] = src_row[x * 4 + 2];
        }
    }

    bitmap.UnlockBits(&data);
    return image;
}

std::vector<fs::path> collect_inputs(const fs::path& root, const std::string& extension) {
    std::vector<fs::path> paths;
    if (!fs::exists(root)) {
        throw std::runtime_error("input path does not exist: " + narrow(root));
    }
    if (fs::is_regular_file(root)) {
        if (ascii_lower(root.extension().string()) == extension) {
            paths.push_back(root);
        }
        return paths;
    }
    for (const auto& entry : fs::recursive_directory_iterator(root)) {
        if (!entry.is_regular_file()) {
            continue;
        }
        if (ascii_lower(entry.path().extension().string()) == extension) {
            paths.push_back(entry.path());
        }
    }
    std::sort(paths.begin(), paths.end());
    return paths;
}

fs::path make_output_path(const fs::path& input_root, const fs::path& output_root, const fs::path& input_file, const std::string& new_ext) {
    fs::path rel = fs::is_directory(input_root) ? fs::relative(input_file, input_root) : input_file.filename();
    rel.replace_extension(new_ext);
    return output_root / rel;
}

int unpack_mode(const fs::path& input_root, const fs::path& output_root) {
    const auto inputs = collect_inputs(input_root, ".lff");
    for (const auto& input : inputs) {
        const auto image = parse_lff(input);
        const auto out_path = make_output_path(input_root, output_root, input, ".png");
        save_png(image, out_path);
        std::cout << input.string() << " -> " << out_path.string() << "\n";
    }
    return 0;
}

int pack_mode(const fs::path& input_root, const fs::path& output_root) {
    const auto inputs = collect_inputs(input_root, ".png");
    for (const auto& input : inputs) {
        const auto image = load_png_as_lff(input);
        const auto out_path = make_output_path(input_root, output_root, input, ".lff");
        const auto blob = build_lff(image);
        write_file(out_path, blob);
        std::cout << input.string() << " -> " << out_path.string() << "\n";
    }
    return 0;
}

void print_usage() {
    std::cout << "Usage:\n";
    std::cout << "  lff u <input_dir_or_file> <output_dir>\n";
    std::cout << "  lff p <input_dir_or_file> <output_dir>\n";
}

class GdiplusSession {
public:
    GdiplusSession() {
        GdiplusStartupInput input;
        if (GdiplusStartup(&token_, &input, nullptr) != Gdiplus::Ok) {
            throw std::runtime_error("failed to initialize GDI+");
        }
    }

    ~GdiplusSession() {
        if (token_ != 0) {
            GdiplusShutdown(token_);
        }
    }

private:
    ULONG_PTR token_ = 0;
};

}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc != 4) {
            print_usage();
            return 1;
        }

        GdiplusSession gdiplus;
        const std::string mode = argv[1];
        const fs::path input_root = argv[2];
        const fs::path output_root = argv[3];

        if (mode == "u") {
            return unpack_mode(input_root, output_root);
        }
        if (mode == "p") {
            return pack_mode(input_root, output_root);
        }

        print_usage();
        return 1;
    } catch (const std::exception& e) {
        std::cerr << "error: " << e.what() << "\n";
        return 1;
    }
}
