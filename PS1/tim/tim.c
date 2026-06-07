#include "tim.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "util.h"

static uint16_t read_u16(FILE *f) {
    unsigned char b[2];
    if (fread(b, 1, 2, f) != 2) return 0;
    return (uint16_t)(b[0] | (b[1] << 8));
}

static uint32_t read_u32(FILE *f) {
    unsigned char b[4];
    if (fread(b, 1, 4, f) != 4) return 0;
    return (uint32_t)b[0] | ((uint32_t)b[1] << 8) | ((uint32_t)b[2] << 16) | ((uint32_t)b[3] << 24);
}

static void write_u16(FILE *f, uint16_t v) {
    unsigned char b[2] = {(unsigned char)(v & 0xFF), (unsigned char)((v >> 8) & 0xFF)};
    fwrite(b, 1, 2, f);
}

static void write_u32(FILE *f, uint32_t v) {
    unsigned char b[4] = {
        (unsigned char)(v & 0xFF),
        (unsigned char)((v >> 8) & 0xFF),
        (unsigned char)((v >> 16) & 0xFF),
        (unsigned char)((v >> 24) & 0xFF)
    };
    fwrite(b, 1, 4, f);
}

static void tim16_to_rgba(uint16_t c, uint8_t *p) {
    p[0] = (uint8_t)(((c & 0x1F) << 3) | ((c & 0x1F) >> 2));
    p[1] = (uint8_t)((((c >> 5) & 0x1F) << 3) | (((c >> 5) & 0x1F) >> 2));
    p[2] = (uint8_t)((((c >> 10) & 0x1F) << 3) | (((c >> 10) & 0x1F) >> 2));
    p[3] = (c & 0x8000) ? 255 : 0;
}

void tim_image_init(TimImage *img) {
    memset(img, 0, sizeof(*img));
}

void tim_image_free(TimImage *img) {
    free(img->data);
    tim_image_init(img);
}

static size_t tim_row_bytes(TimMode mode, int width) {
    switch (mode) {
        case TIM_MODE_4BPP: return (size_t)(((width + 3) / 4) * 2);
        case TIM_MODE_8BPP: return (size_t)(((width + 1) / 2) * 2);
        case TIM_MODE_16BPP: return (size_t)width * 2;
        case TIM_MODE_24BPP: return (size_t)(((width * 3) + 1) / 2) * 2;
        default: return 0;
    }
}

int tim_read_file_w(const wchar_t *path, TimImage *out) {
    FILE *f = _wfopen(path, L"rb");
    uint32_t id, flags, block_size;
    uint8_t *data = NULL;
    size_t size = 0;
    if (!f) return -1;
    tim_image_init(out);

    id = read_u32(f);
    if (id != 0x10) {
        fclose(f);
        return -2;
    }
    flags = read_u32(f);
    out->has_clut = (flags & 0x08) ? 1 : 0;
    if (out->has_clut) {
        out->mode = (flags & 0x01) ? TIM_MODE_8BPP : TIM_MODE_4BPP;
        (void)read_u32(f);
        out->clut_x = (int)read_u16(f);
        out->clut_y = (int)read_u16(f);
        out->clut_w = (int)read_u16(f);
        out->clut_h = (int)read_u16(f);
        out->palette_count = out->clut_w * out->clut_h;
        if (out->palette_count < 0 || out->palette_count > 256) {
            fclose(f);
            tim_image_free(out);
            return -3;
        }
        for (int i = 0; i < out->palette_count; ++i) out->palette[i] = read_u16(f);
    } else {
        out->mode = (flags == 2) ? TIM_MODE_16BPP : TIM_MODE_24BPP;
    }
    block_size = read_u32(f);
    (void)block_size;
    out->image_x = (int)read_u16(f);
    out->image_y = (int)read_u16(f);
    {
        int stored_w = (int)read_u16(f);
        int stored_h = (int)read_u16(f);
        out->height = stored_h;
        if (out->mode == TIM_MODE_4BPP) out->width = stored_w * 4;
        else if (out->mode == TIM_MODE_8BPP) out->width = stored_w * 2;
        else if (out->mode == TIM_MODE_16BPP) out->width = stored_w;
        else out->width = (stored_w * 2) / 3;
    }

    size = tim_row_bytes(out->mode, out->width) * (size_t)out->height;
    data = (uint8_t *)malloc(size ? size : 1);
    if (!data) {
        fclose(f);
        tim_image_free(out);
        return -3;
    }
    if (fread(data, 1, size, f) != size) {
        free(data);
        fclose(f);
        tim_image_free(out);
        return -4;
    }
    fclose(f);
    out->data = data;
    out->data_size = size;
    return 0;
}

int tim_write_file_w(const wchar_t *path, const TimImage *img) {
    FILE *f = _wfopen(path, L"wb");
    size_t size;
    int palette_count = img->palette_count;
    if (!f) return -1;

    write_u32(f, 0x10);
    if (img->mode == TIM_MODE_4BPP || img->mode == TIM_MODE_8BPP) {
        int expected_palette_count = (img->clut_w > 0 && img->clut_h > 0) ? (img->clut_w * img->clut_h) : 0;
        if (expected_palette_count <= 0 || expected_palette_count > 256) {
            fclose(f);
            return -2;
        }
        palette_count = expected_palette_count;
        if (palette_count < 0) palette_count = 0;
        uint32_t flags = 0x08 | ((img->mode == TIM_MODE_8BPP) ? 0x01 : 0x00);
        write_u32(f, flags);
        write_u32(f, 12u + (uint32_t)(palette_count * 2));
        write_u16(f, (uint16_t)img->clut_x);
        write_u16(f, (uint16_t)img->clut_y);
        write_u16(f, (uint16_t)img->clut_w);
        write_u16(f, (uint16_t)img->clut_h);
        for (int i = 0; i < palette_count; ++i) write_u16(f, img->palette[i]);
    } else {
        write_u32(f, img->mode == TIM_MODE_16BPP ? 2u : 3u);
    }

    size = tim_row_bytes(img->mode, img->width) * (size_t)img->height;
    write_u32(f, (uint32_t)(12 + size));
    write_u16(f, (uint16_t)img->image_x);
    write_u16(f, (uint16_t)img->image_y);
    if (img->mode == TIM_MODE_24BPP) write_u16(f, (uint16_t)(((img->width * 3) + 1) / 2));
    else if (img->mode == TIM_MODE_4BPP) write_u16(f, (uint16_t)((img->width + 3) / 4));
    else if (img->mode == TIM_MODE_8BPP) write_u16(f, (uint16_t)((img->width + 1) / 2));
    else write_u16(f, (uint16_t)img->width);
    write_u16(f, (uint16_t)img->height);
    if (size && fwrite(img->data, 1, size, f) != size) {
        fclose(f);
        return -2;
    }
    fclose(f);
    return 0;
}

int tim_to_rgba(const TimImage *img, uint8_t **rgba_out, int *w_out, int *h_out) {
    size_t pixels = (size_t)img->width * (size_t)img->height;
    uint8_t *rgba = (uint8_t *)malloc(pixels * 4);
    if (!rgba) return -1;
    if (img->mode == TIM_MODE_16BPP) {
        for (size_t i = 0; i < pixels; ++i) tim16_to_rgba((uint16_t)(img->data[i * 2] | (img->data[i * 2 + 1] << 8)), rgba + i * 4);
    } else if (img->mode == TIM_MODE_24BPP) {
        size_t row_bytes = tim_row_bytes(img->mode, img->width);
        for (int y = 0; y < img->height; ++y) {
            const uint8_t *row = img->data + (size_t)y * row_bytes;
            for (int x = 0; x < img->width; ++x) {
                size_t i = ((size_t)y * (size_t)img->width + (size_t)x) * 4;
                size_t o = (size_t)x * 3;
                rgba[i + 0] = row[o + 0];
                rgba[i + 1] = row[o + 1];
                rgba[i + 2] = row[o + 2];
                rgba[i + 3] = 255;
            }
        }
    } else {
        size_t row_bytes = tim_row_bytes(img->mode, img->width);
        for (int y = 0; y < img->height; ++y) {
            const uint8_t *row = img->data + (size_t)y * row_bytes;
            for (int x = 0; x < img->width; ++x) {
                size_t i = (size_t)y * (size_t)img->width + (size_t)x;
                uint8_t idx = (img->mode == TIM_MODE_4BPP) ? ((x & 1) ? (row[x / 2] >> 4) & 0x0F : row[x / 2] & 0x0F) : row[x];
                uint16_t c = img->palette[idx];
                tim16_to_rgba(c, rgba + i * 4);
                if (!(c & 0x8000)) rgba[i * 4 + 3] = 0;
            }
        }
    }
    *rgba_out = rgba;
    if (w_out) *w_out = img->width;
    if (h_out) *h_out = img->height;
    return 0;
}

int tim_from_rgba(const uint8_t *rgba, int width, int height, TimMode mode, int image_x, int image_y, int clut_x, int clut_y, const uint16_t *palette, int palette_count, const uint8_t *indices, TimImage *out) {
    size_t pixels = (size_t)width * (size_t)height;
    tim_image_init(out);
    out->mode = mode;
    out->width = width;
    out->height = height;
    out->image_x = image_x;
    out->image_y = image_y;
    out->clut_x = clut_x;
    out->clut_y = clut_y;
    if (mode == TIM_MODE_4BPP || mode == TIM_MODE_8BPP) {
        out->has_clut = 1;
        out->palette_count = palette_count;
        memcpy(out->palette, palette, (size_t)palette_count * sizeof(uint16_t));
        if (mode == TIM_MODE_4BPP) {
            size_t row_bytes = tim_row_bytes(mode, width);
            out->data_size = row_bytes * (size_t)height;
            out->data = (uint8_t *)malloc(out->data_size ? out->data_size : 1);
            if (!out->data) return -1;
            memset(out->data, 0, out->data_size);
            for (int y = 0; y < height; ++y) {
                uint8_t *row = out->data + (size_t)y * row_bytes;
                for (int x = 0; x < width; ++x) {
                    size_t i = (size_t)y * (size_t)width + (size_t)x;
                    size_t b = (size_t)x / 2;
                    if ((x & 1) == 0) row[b] = (uint8_t)(indices[i] & 0x0F);
                    else row[b] = (uint8_t)(row[b] | ((indices[i] & 0x0F) << 4));
                }
            }
        } else {
            size_t row_bytes = tim_row_bytes(mode, width);
            out->data_size = row_bytes * (size_t)height;
            out->data = (uint8_t *)malloc(out->data_size ? out->data_size : 1);
            if (!out->data) return -1;
            memset(out->data, 0, out->data_size);
            for (int y = 0; y < height; ++y) {
                uint8_t *row = out->data + (size_t)y * row_bytes;
                for (int x = 0; x < width; ++x) {
                    row[x] = indices[(size_t)y * (size_t)width + (size_t)x];
                }
            }
        }
    } else if (mode == TIM_MODE_16BPP) {
        out->data_size = pixels * 2;
        out->data = (uint8_t *)malloc(out->data_size ? out->data_size : 1);
        if (!out->data) return -1;
        for (size_t i = 0; i < pixels; ++i) {
            uint16_t c = (uint16_t)(((rgba[i * 4 + 2] >> 3) << 10) | ((rgba[i * 4 + 1] >> 3) << 5) | (rgba[i * 4 + 0] >> 3));
            if (rgba[i * 4 + 3]) c |= 0x8000;
            out->data[i * 2 + 0] = (uint8_t)(c & 0xFF);
            out->data[i * 2 + 1] = (uint8_t)((c >> 8) & 0xFF);
        }
    } else {
        size_t row_bytes = tim_row_bytes(mode, width);
        out->data_size = row_bytes * (size_t)height;
        out->data = (uint8_t *)malloc(out->data_size ? out->data_size : 1);
        if (!out->data) return -1;
        memset(out->data, 0, out->data_size);
        for (int y = 0; y < height; ++y) {
            uint8_t *row = out->data + (size_t)y * row_bytes;
            for (int x = 0; x < width; ++x) {
                size_t o = (size_t)x * 3;
                row[o + 0] = rgba[(size_t)y * (size_t)width * 4 + (size_t)x * 4 + 0];
                row[o + 1] = rgba[(size_t)y * (size_t)width * 4 + (size_t)x * 4 + 1];
                row[o + 2] = rgba[(size_t)y * (size_t)width * 4 + (size_t)x * 4 + 2];
            }
        }
    }
    return 0;
}

void tim_print_info(const TimImage *img, const wchar_t *path) {
    const wchar_t *mode = L"unknown";
    if (img->mode == TIM_MODE_4BPP) mode = L"4bpp";
    else if (img->mode == TIM_MODE_8BPP) mode = L"8bpp";
    else if (img->mode == TIM_MODE_16BPP) mode = L"16bpp";
    else if (img->mode == TIM_MODE_24BPP) mode = L"24bpp";
    wprintf(L"%ls\n", path);
    wprintf(L"  mode: %ls\n", mode);
    wprintf(L"  size: %dx%d\n", img->width, img->height);
    wprintf(L"  image: %d,%d\n", img->image_x, img->image_y);
    if (img->has_clut) {
        wprintf(L"  clut: %d,%d\n", img->clut_x, img->clut_y);
        wprintf(L"  colors: %d\n", img->palette_count);
    }
}
