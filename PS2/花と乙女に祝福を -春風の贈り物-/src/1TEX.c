#define _CRT_SECURE_NO_WARNINGS
#include <windows.h>
#include <gdiplus.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <wchar.h>
#include "1TEX.h"

typedef struct {
    uint8_t *data;
    size_t size;
    size_t cap;
} Buf;

typedef struct {
    uint16_t width;
    uint16_t height;
    uint16_t bpp;
    uint16_t x;
    uint16_t y;
    uint16_t pages;
    int16_t end;
    uint16_t cbp;
    uint16_t cx;
    uint16_t cy;
    uint16_t cpsm;
    size_t offset;
    size_t size;
    uint8_t *data;
} T2;

typedef struct {
    char tex[16];
    uint16_t index;
    uint16_t bpp;
    uint16_t x;
    uint16_t y;
    uint16_t pages;
    uint16_t cbp;
    uint16_t cx;
    uint16_t cy;
    uint16_t cpsm;
    int palette;
    uint16_t pal_x;
    uint16_t pal_y;
    uint16_t pal_pages;
    uint16_t pal_cbp;
    uint16_t pal_cx;
    uint16_t pal_cy;
    uint16_t pal_cpsm;
} ImageMeta;

typedef struct {
    ImageMeta *items;
    size_t count;
} XmlDoc;

typedef struct {
    wchar_t path[1024];
    char id[16];
} TexJob;

typedef struct {
    char id[16];
    size_t start;
    size_t count;
} TexGroup;

typedef struct {
    uint8_t rgba[4];
    uint32_t count;
} QColor;

typedef struct {
    int *idx;
    int count;
} QBox;

typedef struct liq_attr liq_attr;
typedef struct liq_image liq_image;
typedef struct liq_result liq_result;

typedef struct {
    uint8_t r, g, b, a;
} liq_color;

typedef struct {
    uint32_t count;
    liq_color entries[256];
} liq_palette;

typedef struct {
    HMODULE dll;
    liq_attr *(__cdecl *attr_create)(void);
    void (__cdecl *attr_destroy)(liq_attr *);
    int (__cdecl *set_max_colors)(liq_attr *, int);
    liq_image *(__cdecl *image_create_rgba)(liq_attr *, void *, int, int, double);
    void (__cdecl *image_destroy)(liq_image *);
    int (__cdecl *quantize_image)(liq_attr *, liq_image *, liq_result **);
    const liq_palette *(__cdecl *get_palette)(liq_result *);
    int (__cdecl *set_dithering_level)(liq_result *, float);
    int (__cdecl *write_remapped_image)(liq_result *, liq_image *, void *, size_t);
    void (__cdecl *result_destroy)(liq_result *);
} LiqApi;

typedef struct {
    TexJob *jobs;
    size_t job_count;
    volatile LONG next;
    const wchar_t *out_dir;
    ImageMeta *meta;
    size_t meta_count;
    CRITICAL_SECTION log_lock;
    CRITICAL_SECTION meta_lock;
} ExportCtx;

typedef struct {
    const wchar_t *src_dir;
    const wchar_t *out_dir;
    XmlDoc *doc;
    TexGroup *groups;
    size_t group_count;
    volatile LONG next;
    CRITICAL_SECTION log_lock;
} ImportCtx;

static void fail(const char *msg) {
    fprintf(stderr, "%s\n", msg);
    exit(1);
}

static const uint8_t tex_tail[16] = {
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0xFF, 0xFF
};
static LiqApi liq;
static int liq_ready = -1;

static int meta_cmp(const void *a, const void *b) {
    const ImageMeta *x = (const ImageMeta *)a;
    const ImageMeta *y = (const ImageMeta *)b;
    int c = _stricmp(x->tex, y->tex);
    if (c)
        return c;
    return (x->index > y->index) - (x->index < y->index);
}

static DWORD thread_count(void) {
    SYSTEM_INFO si;
    GetSystemInfo(&si);
    if (!si.dwNumberOfProcessors)
        return 1;
    if (si.dwNumberOfProcessors > 16)
        return 16;
    return si.dwNumberOfProcessors;
}

static FARPROC must_proc(HMODULE dll, const char *name) {
    FARPROC p = GetProcAddress(dll, name);
    if (!p)
        fail("libimagequant proc missing");
    return p;
}

static int ensure_liq(void) {
    if (liq_ready >= 0)
        return liq_ready;
    memset(&liq, 0, sizeof(liq));
    liq.dll = LoadLibraryW(L"libimagequant.dll");
    if (!liq.dll) {
        liq_ready = 0;
        return 0;
    }
    liq.attr_create = (void *)must_proc(liq.dll, "liq_attr_create");
    liq.attr_destroy = (void *)must_proc(liq.dll, "liq_attr_destroy");
    liq.set_max_colors = (void *)must_proc(liq.dll, "liq_set_max_colors");
    liq.image_create_rgba = (void *)must_proc(liq.dll, "liq_image_create_rgba");
    liq.image_destroy = (void *)must_proc(liq.dll, "liq_image_destroy");
    liq.quantize_image = (void *)must_proc(liq.dll, "liq_quantize_image");
    liq.get_palette = (void *)must_proc(liq.dll, "liq_get_palette");
    liq.set_dithering_level = (void *)must_proc(liq.dll, "liq_set_dithering_level");
    liq.write_remapped_image = (void *)must_proc(liq.dll, "liq_write_remapped_image");
    liq.result_destroy = (void *)must_proc(liq.dll, "liq_result_destroy");
    liq_ready = 1;
    return 1;
}

static void *xmalloc(size_t size) {
    void *p = malloc(size ? size : 1);
    if (!p)
        fail("out of memory");
    return p;
}

static void *xrealloc(void *ptr, size_t size) {
    void *p = realloc(ptr, size ? size : 1);
    if (!p)
        fail("out of memory");
    return p;
}

static void buf_reserve(Buf *b, size_t need) {
    if (need <= b->cap)
        return;
    size_t cap = b->cap ? b->cap : 256;
    while (cap < need)
        cap *= 2;
    b->data = xrealloc(b->data, cap);
    b->cap = cap;
}

static void buf_append(Buf *b, const void *data, size_t size) {
    buf_reserve(b, b->size + size);
    memcpy(b->data + b->size, data, size);
    b->size += size;
}

static void buf_push(Buf *b, uint8_t v) {
    buf_append(b, &v, 1);
}

static uint16_t rd16(const uint8_t *p) {
    return (uint16_t)(p[0] | (p[1] << 8));
}

static uint32_t rd32be(const uint8_t *p) {
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | p[3];
}

static void wr16(uint8_t *p, uint16_t v) {
    p[0] = (uint8_t)v;
    p[1] = (uint8_t)(v >> 8);
}

static void wr32be(uint8_t *p, uint32_t v) {
    p[0] = (uint8_t)(v >> 24);
    p[1] = (uint8_t)(v >> 16);
    p[2] = (uint8_t)(v >> 8);
    p[3] = (uint8_t)v;
}

static uint8_t *read_file(const wchar_t *path, size_t *size) {
    FILE *fp = _wfopen(path, L"rb");
    if (!fp)
        fail("cannot open file");
    fseek(fp, 0, SEEK_END);
    long len = ftell(fp);
    fseek(fp, 0, SEEK_SET);
    if (len < 0)
        fail("bad file length");
    uint8_t *data = xmalloc((size_t)len);
    if (fread(data, 1, (size_t)len, fp) != (size_t)len)
        fail("cannot read file");
    fclose(fp);
    *size = (size_t)len;
    return data;
}

static void write_file(const wchar_t *path, const void *data, size_t size) {
    FILE *fp = _wfopen(path, L"wb");
    if (!fp)
        fail("cannot create file");
    if (size && fwrite(data, 1, size, fp) != size)
        fail("cannot write file");
    fclose(fp);
}

static void join_path(wchar_t *out, size_t cap, const wchar_t *dir, const wchar_t *name) {
    (void)cap;
    swprintf(out, L"%ls\\%ls", dir, name);
}

static void ensure_dir(const wchar_t *path) {
    CreateDirectoryW(path, NULL);
}

static void hex4_from_name(char out[16], const wchar_t *name) {
    char buf[16];
    int i = 0;
    while (name[i] && name[i] != L'.' && i < 4) {
        wchar_t c = name[i];
        buf[i] = (char)(c <= 0x7F ? c : '_');
        i++;
    }
    buf[i] = 0;
    strcpy(out, buf);
}

static int same_id(const char *a, const char *b) {
    return !_stricmp(a, b);
}

static void step_dims(uint16_t *w, uint16_t *h, uint16_t bpp) {
    if (bpp == 16) {
        if (*h < *w)
            *w >>= 1;
        else
            *h >>= 1;
    } else if (bpp == 8) {
        *w >>= 1;
        *h >>= 1;
    } else if (bpp == 4) {
        if (*h < *w) {
            *w >>= 2;
            *h >>= 1;
        } else {
            *w >>= 1;
            *h >>= 2;
        }
    }
}

static uint8_t *unpack_1tex(const uint8_t *src, size_t src_size, size_t *out_size) {
    if (src_size < 8 || memcmp(src, "1tex", 4) != 0)
        fail("bad 1tex magic");
    size_t want = rd32be(src + 4);
    Buf out = {0};
    size_t sp = 8;
    while (sp < src_size) {
        uint8_t ctl = src[sp++];
        if (!ctl)
            break;
        if (ctl < 0x80) {
            if (sp + ctl > src_size)
                fail("truncated literal");
            buf_append(&out, src + sp, ctl);
            sp += ctl;
        } else {
            if (sp >= src_size)
                fail("truncated backref");
            int span = 0x102 - ctl;
            int back = src[sp++] + 1;
            if ((size_t)back > out.size)
                fail("bad backref");
            size_t pos = out.size - back;
            for (int i = 0; i < span; i++) {
                buf_push(&out, out.data[pos++]);
            }
        }
    }
    if (out.size != want)
        fail("decompress size mismatch");
    *out_size = out.size;
    return out.data;
}

static uint8_t *pack_1tex(const uint8_t *src, size_t src_size, size_t *out_size) {
    int *head = xmalloc(0x10000 * sizeof(int));
    int *chain = xmalloc((src_size ? src_size : 1) * sizeof(int));
    for (int i = 0; i < 0x10000; i++)
        head[i] = -1;
    for (size_t i = 0; i < src_size; i++)
        chain[i] = -1;
    Buf body = {0};
    size_t pos = 0;
    while (pos < src_size) {
        int best_len = 0;
        int best_dist = 0;
        if (pos + 1 < src_size) {
            int h = (src[pos] << 8) | src[pos + 1];
            int depth = 0;
            for (int prev = head[h]; prev >= 0 && depth < 64; prev = chain[prev], depth++) {
                int dist = (int)pos - prev;
                if (dist <= 0)
                    continue;
                if (dist > 0x100)
                    break;
                int limit = (int)(src_size - pos);
                if (limit > 0x82)
                    limit = 0x82;
                int len = 0;
                while (len < limit && src[prev + len] == src[pos + len])
                    len++;
                if (len >= 3 && len > best_len) {
                    best_len = len;
                    best_dist = dist;
                    if (len == limit)
                        break;
                }
            }
        }
        if (best_len >= 3) {
            buf_push(&body, (uint8_t)(0x102 - best_len));
            buf_push(&body, (uint8_t)(best_dist - 1));
            for (int i = 0; i < best_len; i++) {
                size_t p = pos + (size_t)i;
                if (p + 1 < src_size) {
                    int h = (src[p] << 8) | src[p + 1];
                    chain[p] = head[h];
                    head[h] = (int)p;
                }
            }
            pos += (size_t)best_len;
        } else {
            size_t lit = 1;
            if (pos + 1 < src_size) {
                int h = (src[pos] << 8) | src[pos + 1];
                chain[pos] = head[h];
                head[h] = (int)pos;
            }
            while (pos + lit < src_size && lit < 0x7F) {
                int next_match = 0;
                size_t p = pos + lit;
                if (p + 1 < src_size) {
                    int h = (src[p] << 8) | src[p + 1];
                    int depth = 0;
                    for (int prev = head[h]; prev >= 0 && depth < 64; prev = chain[prev], depth++) {
                        int dist = (int)p - prev;
                        if (dist <= 0)
                            continue;
                        if (dist > 0x100)
                            break;
                        int limit = (int)(src_size - p);
                        if (limit > 0x82)
                            limit = 0x82;
                        int len = 0;
                        while (len < limit && src[prev + len] == src[p + len])
                            len++;
                        if (len >= 3) {
                            next_match = 1;
                            break;
                        }
                    }
                    chain[p] = head[h];
                    head[h] = (int)p;
                }
                if (next_match)
                    break;
                lit++;
            }
            buf_push(&body, (uint8_t)lit);
            buf_append(&body, src + pos, lit);
            pos += lit;
        }
    }
    buf_push(&body, 0);
    free(head);
    free(chain);
    Buf out = {0};
    buf_append(&out, "1tex", 4);
    uint8_t size_be[4];
    wr32be(size_be, (uint32_t)src_size);
    buf_append(&out, size_be, 4);
    buf_append(&out, body.data, body.size);
    free(body.data);
    *out_size = out.size;
    return out.data;
}

static size_t parse_t2(const uint8_t *raw, size_t raw_size, T2 **out_items, size_t *out_count) {
    size_t cap = 16;
    size_t count = 0;
    size_t off = 0;
    T2 *items = xmalloc(cap * sizeof(T2));
    while (off + 0x20 <= raw_size && raw[off] == 'T' && raw[off + 1] == '2') {
        if (count == cap) {
            cap *= 2;
            items = xrealloc(items, cap * sizeof(T2));
        }
        T2 *t = &items[count++];
        memset(t, 0, sizeof(*t));
        t->width = rd16(raw + off + 2);
        t->height = rd16(raw + off + 4);
        t->bpp = rd16(raw + off + 6);
        t->x = rd16(raw + off + 8);
        t->y = rd16(raw + off + 10);
        t->pages = rd16(raw + off + 12);
        t->end = (int16_t)rd16(raw + off + 14);
        t->cbp = rd16(raw + off + 16);
        t->cx = rd16(raw + off + 18);
        t->cy = rd16(raw + off + 20);
        t->cpsm = rd16(raw + off + 22);
        t->offset = off;
        uint16_t nw = t->width;
        uint16_t nh = t->height;
        step_dims(&nw, &nh, t->bpp);
        t->size = 0x20 + (size_t)4 * nw * nh;
        if (off + t->size > raw_size)
            fail("bad t2 size");
        t->data = xmalloc(t->size);
        memcpy(t->data, raw + off, t->size);
        off += t->size;
    }
    *out_items = items;
    *out_count = count;
    return off;
}

static void rgba_from_ps2(const uint8_t *src, uint8_t *dst, size_t count) {
    for (size_t i = 0; i < count; i++) {
        dst[i * 4 + 0] = src[i * 4 + 0];
        dst[i * 4 + 1] = src[i * 4 + 1];
        dst[i * 4 + 2] = src[i * 4 + 2];
        dst[i * 4 + 3] = src[i * 4 + 3] == 0x80 ? 255 : (uint8_t)(src[i * 4 + 3] * 2);
    }
}

static void rgba_to_ps2(const uint8_t *src, uint8_t *dst, size_t count) {
    for (size_t i = 0; i < count; i++) {
        dst[i * 4 + 0] = src[i * 4 + 0];
        dst[i * 4 + 1] = src[i * 4 + 1];
        dst[i * 4 + 2] = src[i * 4 + 2];
        uint8_t a = src[i * 4 + 3];
        dst[i * 4 + 3] = a >= 255 ? 0x80 : (uint8_t)((a + 1) / 2);
    }
}

static void unswizzle_palette(uint8_t *rgba, size_t count) {
    uint8_t tmp[1024];
    memcpy(tmp, rgba, count * 4);
    for (size_t i = 0; i < count; i++) {
        size_t j = (i & ~0x1Fu) | (i & 7u) | ((i & 8u) << 1u) | ((i & 0x10u) >> 1u);
        if (j < count)
            memcpy(rgba + j * 4, tmp + i * 4, 4);
    }
}

static void swizzle_palette(uint8_t *rgba, size_t count) {
    uint8_t tmp[1024];
    memcpy(tmp, rgba, count * 4);
    for (size_t i = 0; i < count; i++) {
        size_t j = (i & ~0x1Fu) | (i & 7u) | ((i & 8u) << 1u) | ((i & 0x10u) >> 1u);
        if (j < count)
            memcpy(rgba + i * 4, tmp + j * 4, 4);
    }
}

static ULONG_PTR gdip_token;
static int gdip_ready;

static CLSID png_encoder_clsid(void) {
    UINT count = 0, bytes = 0;
    CLSID clsid = {0};
    if (GdipGetImageEncodersSize(&count, &bytes) != Ok || !bytes)
        fail("GDI+ encoders unavailable");
    ImageCodecInfo *info = xmalloc(bytes);
    if (GdipGetImageEncoders(count, bytes, info) != Ok)
        fail("GDI+ encoder list failed");
    for (UINT i = 0; i < count; i++) {
        if (info[i].MimeType && !wcscmp(info[i].MimeType, L"image/png")) {
            clsid = info[i].Clsid;
            break;
        }
    }
    free(info);
    return clsid;
}

static void ensure_gdip(void) {
    static int done;
    if (!done) {
        GdiplusStartupInput in;
        memset(&in, 0, sizeof(in));
        in.GdiplusVersion = 1;
        if (GdiplusStartup(&gdip_token, &in, NULL) != Ok)
            fail("GdiplusStartup failed");
        done = 1;
        gdip_ready = 1;
    }
}

static void save_png(const wchar_t *path, const uint8_t *rgba, UINT w, UINT h) {
    ensure_gdip();
    CLSID enc = png_encoder_clsid();
    GpBitmap *bmp = NULL;
    uint8_t *argb = xmalloc((size_t)w * h * 4);
    for (size_t i = 0; i < (size_t)w * h; i++) {
        argb[i * 4 + 0] = rgba[i * 4 + 2];
        argb[i * 4 + 1] = rgba[i * 4 + 1];
        argb[i * 4 + 2] = rgba[i * 4 + 0];
        argb[i * 4 + 3] = rgba[i * 4 + 3];
    }
    if (GdipCreateBitmapFromScan0((INT)w, (INT)h, (INT)(w * 4), PixelFormat32bppARGB, argb, &bmp) != Ok)
        fail("GdipCreateBitmapFromScan0 failed");
    if (GdipSaveImageToFile((GpImage *)bmp, path, &enc, NULL) != Ok)
        fail("GdipSaveImageToFile failed");
    GdipDisposeImage((GpImage *)bmp);
    free(argb);
}

static uint8_t *load_png(const wchar_t *path, UINT *w, UINT *h) {
    ensure_gdip();
    GpImage *img = NULL;
    if (GdipLoadImageFromFile(path, &img) != Ok)
        fail("GdipLoadImageFromFile failed");
    GdipGetImageWidth(img, w);
    GdipGetImageHeight(img, h);
    GpRect rect = {0, 0, (INT)*w, (INT)*h};
    BitmapData bd;
    if (GdipBitmapLockBits((GpBitmap *)img, &rect, ImageLockModeRead, PixelFormat32bppARGB, &bd) != Ok)
        fail("GdipBitmapLockBits failed");
    uint8_t *rgba = xmalloc((size_t)(*w) * (*h) * 4);
    for (UINT y = 0; y < *h; y++) {
        const uint8_t *row = (const uint8_t *)bd.Scan0 + (size_t)y * bd.Stride;
        for (UINT x = 0; x < *w; x++) {
            const uint8_t *p = row + x * 4;
            size_t i = ((size_t)y * (*w) + x) * 4;
            rgba[i + 0] = p[2];
            rgba[i + 1] = p[1];
            rgba[i + 2] = p[0];
            rgba[i + 3] = p[3];
        }
    }
    GdipBitmapUnlockBits((GpBitmap *)img, &bd);
    GdipDisposeImage(img);
    return rgba;
}

static void write_xml(const wchar_t *path, ImageMeta *items, size_t count) {
    Buf b = {0};
    size_t last = (size_t)-1;
    {
        const char *head = "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n<texs>\n";
        buf_append(&b, head, strlen(head));
    }
    for (size_t i = 0; i < count; i++) {
        char line[640];
        ImageMeta *m = &items[i];
        if (last == (size_t)-1 || !same_id(items[last].tex, m->tex)) {
            if (last != (size_t)-1)
                buf_append(&b, "  </tex>\n", 9);
            sprintf(line, "  <tex id=\"%s\">\n", m->tex);
            buf_append(&b, line, strlen(line));
        }
        if (m->palette >= 0) {
            sprintf(line,
                "    <image id=\"%02X\" bpp=\"%u\" x=\"%u\" y=\"%u\" pages=\"%u\" cbp=\"%u\" cx=\"%u\" cy=\"%u\" cpsm=\"%u\" pal_x=\"%u\" pal_y=\"%u\" pal_pages=\"%u\" pal_cbp=\"%u\" pal_cx=\"%u\" pal_cy=\"%u\" pal_cpsm=\"%u\" />\n",
                m->index, m->bpp, m->x, m->y, m->pages, m->cbp, m->cx, m->cy, m->cpsm,
                m->pal_x, m->pal_y, m->pal_pages, m->pal_cbp, m->pal_cx, m->pal_cy, m->pal_cpsm);
        } else {
            sprintf(line,
                "    <image id=\"%02X\" bpp=\"%u\" x=\"%u\" y=\"%u\" pages=\"%u\" cbp=\"%u\" cx=\"%u\" cy=\"%u\" cpsm=\"%u\" />\n",
                m->index, m->bpp, m->x, m->y, m->pages, m->cbp, m->cx, m->cy, m->cpsm);
        }
        buf_append(&b, line, strlen(line));
        last = i;
    }
    if (last != (size_t)-1)
        buf_append(&b, "  </tex>\n", 9);
    {
        const char *tail = "</texs>\n";
        buf_append(&b, tail, strlen(tail));
    }
    write_file(path, b.data, b.size);
    free(b.data);
}

static char *build_xml_text(ImageMeta *items, size_t count, size_t *out_size) {
    Buf b = {0};
    size_t last = (size_t)-1;
    const char *head = "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n<texs>\n";
    buf_append(&b, head, strlen(head));
    for (size_t i = 0; i < count; i++) {
        char line[640];
        ImageMeta *m = &items[i];
        if (last == (size_t)-1 || !same_id(items[last].tex, m->tex)) {
            if (last != (size_t)-1)
                buf_append(&b, "  </tex>\n", 9);
            sprintf(line, "  <tex id=\"%s\">\n", m->tex);
            buf_append(&b, line, strlen(line));
        }
        if (m->palette >= 0) {
            sprintf(line,
                "    <image id=\"%02X\" bpp=\"%u\" x=\"%u\" y=\"%u\" pages=\"%u\" cbp=\"%u\" cx=\"%u\" cy=\"%u\" cpsm=\"%u\" pal_x=\"%u\" pal_y=\"%u\" pal_pages=\"%u\" pal_cbp=\"%u\" pal_cx=\"%u\" pal_cy=\"%u\" pal_cpsm=\"%u\" />\n",
                m->index, m->bpp, m->x, m->y, m->pages, m->cbp, m->cx, m->cy, m->cpsm,
                m->pal_x, m->pal_y, m->pal_pages, m->pal_cbp, m->pal_cx, m->pal_cy, m->pal_cpsm);
        } else {
            sprintf(line,
                "    <image id=\"%02X\" bpp=\"%u\" x=\"%u\" y=\"%u\" pages=\"%u\" cbp=\"%u\" cx=\"%u\" cy=\"%u\" cpsm=\"%u\" />\n",
                m->index, m->bpp, m->x, m->y, m->pages, m->cbp, m->cx, m->cy, m->cpsm);
        }
        buf_append(&b, line, strlen(line));
        last = i;
    }
    if (last != (size_t)-1)
        buf_append(&b, "  </tex>\n", 9);
    buf_append(&b, "</texs>\n", 8);
    buf_push(&b, 0);
    if (out_size)
        *out_size = b.size - 1;
    return (char *)b.data;
}

static char *attr_value(const char *line, const char *name, char *buf, size_t cap) {
    char pat[64];
    sprintf(pat, "%s=\"", name);
    const char *p = strstr(line, pat);
    if (!p)
        return NULL;
    p += strlen(pat);
    const char *q = strchr(p, '"');
    if (!q)
        return NULL;
    size_t n = (size_t)(q - p);
    if (n >= cap)
        n = cap - 1;
    memcpy(buf, p, n);
    buf[n] = 0;
    return buf;
}

static XmlDoc read_xml(const wchar_t *path) {
    size_t size;
    uint8_t *raw = read_file(path, &size);
    char *txt = xmalloc(size + 1);
    memcpy(txt, raw, size);
    txt[size] = 0;
    free(raw);
    XmlDoc doc = {0};
    char tmp[8192];
    size_t cap = 16;
    doc.items = xmalloc(cap * sizeof(ImageMeta));
    char *p = txt;
    char cur_tex[16] = "";
    while (*p) {
        char *tex = strstr(p, "<tex ");
        char *img = strstr(p, "<image ");
        if (tex && (!img || tex < img)) {
            char *e = strstr(tex, ">");
            char line[256];
            size_t len = e ? (size_t)(e - tex + 1) : 0;
            if (!len || len >= sizeof(line))
                break;
            memcpy(line, tex, len);
            line[len] = 0;
            attr_value(line, "id", cur_tex, sizeof(cur_tex));
            p = tex + len;
            continue;
        }
        if (!img)
            break;
        p = img;
        char *e = strstr(p, "/>");
        if (!e)
            break;
        size_t len = (size_t)(e - p + 2);
        char line[1024];
        if (len >= sizeof(line))
            fail("xml line too long");
        memcpy(line, p, len);
        line[len] = 0;
        if (doc.count == cap) {
            cap *= 2;
            doc.items = xrealloc(doc.items, cap * sizeof(ImageMeta));
        }
        ImageMeta *m = &doc.items[doc.count++];
        memset(m, 0, sizeof(*m));
        m->palette = -1;
        strcpy(m->tex, cur_tex);
        m->index = (uint16_t)strtoul(attr_value(line, "id", tmp, sizeof(tmp)), NULL, 16);
        m->bpp = (uint16_t)atoi(attr_value(line, "bpp", tmp, sizeof(tmp)));
        m->x = (uint16_t)atoi(attr_value(line, "x", tmp, sizeof(tmp)));
        m->y = (uint16_t)atoi(attr_value(line, "y", tmp, sizeof(tmp)));
        m->pages = (uint16_t)atoi(attr_value(line, "pages", tmp, sizeof(tmp)));
        m->cbp = (uint16_t)atoi(attr_value(line, "cbp", tmp, sizeof(tmp)));
        m->cx = (uint16_t)atoi(attr_value(line, "cx", tmp, sizeof(tmp)));
        m->cy = (uint16_t)atoi(attr_value(line, "cy", tmp, sizeof(tmp)));
        m->cpsm = (uint16_t)atoi(attr_value(line, "cpsm", tmp, sizeof(tmp)));
        if (attr_value(line, "pal_cbp", tmp, sizeof(tmp))) {
            m->palette = 1;
            m->pal_x = (uint16_t)atoi(attr_value(line, "pal_x", tmp, sizeof(tmp)));
            m->pal_y = (uint16_t)atoi(attr_value(line, "pal_y", tmp, sizeof(tmp)));
            m->pal_pages = (uint16_t)atoi(attr_value(line, "pal_pages", tmp, sizeof(tmp)));
            m->pal_cbp = (uint16_t)atoi(attr_value(line, "pal_cbp", tmp, sizeof(tmp)));
            m->pal_cx = (uint16_t)atoi(attr_value(line, "pal_cx", tmp, sizeof(tmp)));
            m->pal_cy = (uint16_t)atoi(attr_value(line, "pal_cy", tmp, sizeof(tmp)));
            m->pal_cpsm = (uint16_t)atoi(attr_value(line, "pal_cpsm", tmp, sizeof(tmp)));
        }
        p = e + 2;
    }
    free(txt);
    return doc;
}

static XmlDoc read_xml_text(const char *txt) {
    XmlDoc doc = {0};
    char tmp[8192];
    size_t cap = 16;
    char *buf = _strdup(txt);
    char *p;
    char cur_tex[16] = "";
    if (!buf)
        fail("out of memory");
    doc.items = xmalloc(cap * sizeof(ImageMeta));
    p = buf;
    while (*p) {
        char *tex = strstr(p, "<tex ");
        char *img = strstr(p, "<image ");
        if (tex && (!img || tex < img)) {
            char *e = strstr(tex, ">");
            char line[256];
            size_t len = e ? (size_t)(e - tex + 1) : 0;
            if (!len || len >= sizeof(line))
                break;
            memcpy(line, tex, len);
            line[len] = 0;
            attr_value(line, "id", cur_tex, sizeof(cur_tex));
            p = tex + len;
            continue;
        }
        if (!img)
            break;
        p = img;
        {
            char *e = strstr(p, "/>");
            size_t len;
            char line[1024];
            ImageMeta *m;
            if (!e)
                break;
            len = (size_t)(e - p + 2);
            if (len >= sizeof(line))
                fail("xml line too long");
            memcpy(line, p, len);
            line[len] = 0;
            if (doc.count == cap) {
                cap *= 2;
                doc.items = xrealloc(doc.items, cap * sizeof(ImageMeta));
            }
            m = &doc.items[doc.count++];
            memset(m, 0, sizeof(*m));
            m->palette = -1;
            strcpy(m->tex, cur_tex);
            m->index = (uint16_t)strtoul(attr_value(line, "id", tmp, sizeof(tmp)), NULL, 16);
            m->bpp = (uint16_t)atoi(attr_value(line, "bpp", tmp, sizeof(tmp)));
            m->x = (uint16_t)atoi(attr_value(line, "x", tmp, sizeof(tmp)));
            m->y = (uint16_t)atoi(attr_value(line, "y", tmp, sizeof(tmp)));
            m->pages = (uint16_t)atoi(attr_value(line, "pages", tmp, sizeof(tmp)));
            m->cbp = (uint16_t)atoi(attr_value(line, "cbp", tmp, sizeof(tmp)));
            m->cx = (uint16_t)atoi(attr_value(line, "cx", tmp, sizeof(tmp)));
            m->cy = (uint16_t)atoi(attr_value(line, "cy", tmp, sizeof(tmp)));
            m->cpsm = (uint16_t)atoi(attr_value(line, "cpsm", tmp, sizeof(tmp)));
            if (attr_value(line, "pal_cbp", tmp, sizeof(tmp))) {
                m->palette = 1;
                m->pal_x = (uint16_t)atoi(attr_value(line, "pal_x", tmp, sizeof(tmp)));
                m->pal_y = (uint16_t)atoi(attr_value(line, "pal_y", tmp, sizeof(tmp)));
                m->pal_pages = (uint16_t)atoi(attr_value(line, "pal_pages", tmp, sizeof(tmp)));
                m->pal_cbp = (uint16_t)atoi(attr_value(line, "pal_cbp", tmp, sizeof(tmp)));
                m->pal_cx = (uint16_t)atoi(attr_value(line, "pal_cx", tmp, sizeof(tmp)));
                m->pal_cy = (uint16_t)atoi(attr_value(line, "pal_cy", tmp, sizeof(tmp)));
                m->pal_cpsm = (uint16_t)atoi(attr_value(line, "pal_cpsm", tmp, sizeof(tmp)));
            }
            p = e + 2;
        }
    }
    free(buf);
    return doc;
}

static void export_one_tex(const wchar_t *src, const wchar_t *out_dir, const char *tex_id, ImageMeta **meta, size_t *meta_count) {
    size_t comp_size, raw_size, t2_count;
    uint8_t *comp = read_file(src, &comp_size);
    uint8_t *raw = unpack_1tex(comp, comp_size, &raw_size);
    free(comp);
    ensure_dir(out_dir);
    T2 *items;
    parse_t2(raw, raw_size, &items, &t2_count);
    size_t img_count = 0;
    for (size_t i = 0; i < t2_count; i++) {
        T2 *t = &items[i];
        uint8_t *rgba = NULL;
        size_t px = (size_t)t->width * t->height;
        int used_palette = 0;
        if (t->bpp == 32) {
            rgba = xmalloc(px * 4);
            rgba_from_ps2(t->data + 0x20, rgba, px);
        } else if (t->bpp == 8 && i + 1 < t2_count) {
            T2 *p = &items[i + 1];
            if (p->bpp == 32 && p->width == 16 && p->height == 16) {
                uint8_t pal[1024];
                memcpy(pal, p->data + 0x20, 1024);
                rgba_from_ps2(pal, pal, 256);
                unswizzle_palette(pal, 256);
                rgba = xmalloc(px * 4);
                const uint8_t *idx = t->data + 0x20;
                for (size_t j = 0; j < px; j++)
                    memcpy(rgba + j * 4, pal + idx[j] * 4, 4);
                used_palette = 1;
            }
        }
        if (!rgba)
            continue;
        if (t->bpp == 32 && i > 0) {
            T2 *prev = &items[i - 1];
            if (prev->bpp == 8 && t->width == 16 && t->height == 16)
                continue;
        }
        *meta = xrealloc(*meta, (*meta_count + 1) * sizeof(ImageMeta));
        ImageMeta *m = &(*meta)[*meta_count];
        memset(m, 0, sizeof(*m));
        strcpy(m->tex, tex_id);
        m->index = (uint16_t)img_count;
        m->bpp = t->bpp;
        m->x = t->x;
        m->y = t->y;
        m->pages = t->pages;
        m->cbp = t->cbp;
        m->cx = t->cx;
        m->cy = t->cy;
        m->cpsm = t->cpsm;
        if (used_palette) {
            T2 *p = &items[i + 1];
            m->palette = 1;
            m->pal_x = p->x;
            m->pal_y = p->y;
            m->pal_pages = p->pages;
            m->pal_cbp = p->cbp;
            m->pal_cx = p->cx;
            m->pal_cy = p->cy;
            m->pal_cpsm = p->cpsm;
        } else {
            m->palette = -1;
        }
        {
            wchar_t name[64], path[1024];
            swprintf(name, L"%hs.%02X.png", tex_id, (unsigned)img_count);
            join_path(path, 1024, out_dir, name);
            save_png(path, rgba, t->width, t->height);
        }
        free(rgba);
        (*meta_count)++;
        img_count++;
    }
    for (size_t i = 0; i < t2_count; i++)
        free(items[i].data);
    free(items);
    free(raw);
}

static void export_one_tex_mem(const uint8_t *src, size_t src_size, const wchar_t *out_dir, const char *tex_id, ImageMeta **meta, size_t *meta_count) {
    size_t raw_size, t2_count;
    uint8_t *raw = unpack_1tex(src, src_size, &raw_size);
    T2 *items;
    size_t img_count = 0;
    ensure_dir(out_dir);
    parse_t2(raw, raw_size, &items, &t2_count);
    for (size_t i = 0; i < t2_count; i++) {
        T2 *t = &items[i];
        uint8_t *rgba = NULL;
        size_t px = (size_t)t->width * t->height;
        int used_palette = 0;
        if (t->bpp == 32) {
            rgba = xmalloc(px * 4);
            rgba_from_ps2(t->data + 0x20, rgba, px);
        } else if (t->bpp == 8 && i + 1 < t2_count) {
            T2 *p = &items[i + 1];
            if (p->bpp == 32 && p->width == 16 && p->height == 16) {
                uint8_t pal[1024];
                memcpy(pal, p->data + 0x20, 1024);
                rgba_from_ps2(pal, pal, 256);
                unswizzle_palette(pal, 256);
                rgba = xmalloc(px * 4);
                {
                    const uint8_t *idx = t->data + 0x20;
                    for (size_t j = 0; j < px; j++)
                        memcpy(rgba + j * 4, pal + idx[j] * 4, 4);
                }
                used_palette = 1;
            }
        }
        if (!rgba)
            continue;
        if (t->bpp == 32 && i > 0) {
            T2 *prev = &items[i - 1];
            if (prev->bpp == 8 && t->width == 16 && t->height == 16) {
                free(rgba);
                continue;
            }
        }
        *meta = xrealloc(*meta, (*meta_count + 1) * sizeof(ImageMeta));
        {
            ImageMeta *m = &(*meta)[*meta_count];
            wchar_t name[64], path[1024];
            memset(m, 0, sizeof(*m));
            strcpy(m->tex, tex_id);
            m->index = (uint16_t)img_count;
            m->bpp = t->bpp;
            m->x = t->x;
            m->y = t->y;
            m->pages = t->pages;
            m->cbp = t->cbp;
            m->cx = t->cx;
            m->cy = t->cy;
            m->cpsm = t->cpsm;
            if (used_palette) {
                T2 *p = &items[i + 1];
                m->palette = 1;
                m->pal_x = p->x;
                m->pal_y = p->y;
                m->pal_pages = p->pages;
                m->pal_cbp = p->cbp;
                m->pal_cx = p->cx;
                m->pal_cy = p->cy;
                m->pal_cpsm = p->cpsm;
            } else {
                m->palette = -1;
            }
            swprintf(name, L"%hs.%02X.png", tex_id, (unsigned)img_count);
            join_path(path, 1024, out_dir, name);
            save_png(path, rgba, t->width, t->height);
        }
        free(rgba);
        (*meta_count)++;
        img_count++;
    }
    for (size_t i = 0; i < t2_count; i++)
        free(items[i].data);
    free(items);
    free(raw);
}

static int find_color(uint8_t *pal, int count, const uint8_t *c) {
    for (int i = 0; i < count; i++) {
        if (!memcmp(pal + i * 4, c, 4))
            return i;
    }
    return -1;
}

static int nearest_color(const uint8_t *pal, int count, const uint8_t *c) {
    int best = 0;
    uint32_t best_d = 0xFFFFFFFFu;
    for (int i = 0; i < count; i++) {
        int dr = (int)pal[i * 4 + 0] - c[0];
        int dg = (int)pal[i * 4 + 1] - c[1];
        int db = (int)pal[i * 4 + 2] - c[2];
        int da = (int)pal[i * 4 + 3] - c[3];
        uint32_t d = (uint32_t)(dr * dr + dg * dg + db * db + da * da);
        if (d < best_d) {
            best_d = d;
            best = i;
        }
    }
    return best;
}

static int quantize_with_liq(const uint8_t *rgba, UINT w, UINT h, uint8_t *idx, uint8_t *pal) {
    liq_attr *attr;
    liq_image *img;
    liq_result *res = NULL;
    const liq_palette *lp;
    if (!ensure_liq())
        return 0;
    attr = liq.attr_create();
    if (!attr)
        return 0;
    if (liq.set_max_colors(attr, 256)) {
        liq.attr_destroy(attr);
        return 0;
    }
    img = liq.image_create_rgba(attr, (void *)rgba, (int)w, (int)h, 0.0);
    if (!img) {
        liq.attr_destroy(attr);
        return 0;
    }
    if (liq.quantize_image(attr, img, &res) || !res) {
        liq.image_destroy(img);
        liq.attr_destroy(attr);
        return 0;
    }
    liq.set_dithering_level(res, 0.0f);
    if (liq.write_remapped_image(res, img, idx, (size_t)w * h)) {
        liq.result_destroy(res);
        liq.image_destroy(img);
        liq.attr_destroy(attr);
        return 0;
    }
    lp = liq.get_palette(res);
    if (!lp || lp->count > 256) {
        liq.result_destroy(res);
        liq.image_destroy(img);
        liq.attr_destroy(attr);
        return 0;
    }
    memset(pal, 0, 1024);
    for (uint32_t i = 0; i < lp->count; i++) {
        pal[i * 4 + 0] = lp->entries[i].r;
        pal[i * 4 + 1] = lp->entries[i].g;
        pal[i * 4 + 2] = lp->entries[i].b;
        pal[i * 4 + 3] = lp->entries[i].a;
    }
    liq.result_destroy(res);
    liq.image_destroy(img);
    liq.attr_destroy(attr);
    return 1;
}

static void make_t2_header(uint8_t *hdr, UINT w, UINT h, ImageMeta *m, int palette) {
    memset(hdr, 0, 0x20);
    hdr[0] = 'T';
    hdr[1] = '2';
    wr16(hdr + 2, (uint16_t)w);
    wr16(hdr + 4, (uint16_t)h);
    wr16(hdr + 6, palette ? 32 : m->bpp);
    wr16(hdr + 8, palette ? m->pal_x : m->x);
    wr16(hdr + 10, palette ? m->pal_y : m->y);
    wr16(hdr + 12, palette ? m->pal_pages : m->pages);
    wr16(hdr + 14, 0);
    wr16(hdr + 16, palette ? m->pal_cbp : m->cbp);
    wr16(hdr + 18, palette ? m->pal_cx : m->cx);
    wr16(hdr + 20, palette ? m->pal_cy : m->cy);
    wr16(hdr + 22, palette ? m->pal_cpsm : m->cpsm);
}

static DWORD WINAPI export_worker(void *arg) {
    ExportCtx *ctx = (ExportCtx *)arg;
    for (;;) {
        LONG i = InterlockedIncrement(&ctx->next) - 1;
        if ((size_t)i >= ctx->job_count)
            break;
        ImageMeta *local = NULL;
        size_t local_count = 0;
#ifndef ONETEX_SILENT
        EnterCriticalSection(&ctx->log_lock);
        printf("%s.1tex\n", ctx->jobs[i].id);
        LeaveCriticalSection(&ctx->log_lock);
#endif
        export_one_tex(ctx->jobs[i].path, ctx->out_dir, ctx->jobs[i].id, &local, &local_count);
        EnterCriticalSection(&ctx->meta_lock);
        ctx->meta = xrealloc(ctx->meta, (ctx->meta_count + local_count) * sizeof(ImageMeta));
        memcpy(ctx->meta + ctx->meta_count, local, local_count * sizeof(ImageMeta));
        ctx->meta_count += local_count;
        LeaveCriticalSection(&ctx->meta_lock);
        free(local);
    }
    return 0;
}

static DWORD WINAPI import_worker(void *arg) {
    ImportCtx *ctx = (ImportCtx *)arg;
    for (;;) {
        LONG gi = InterlockedIncrement(&ctx->next) - 1;
        if ((size_t)gi >= ctx->group_count)
            break;
        Buf raw = {0};
        const char *tex_id = ctx->groups[gi].id;
#ifndef ONETEX_SILENT
        EnterCriticalSection(&ctx->log_lock);
        printf("%s.1tex\n", tex_id);
        LeaveCriticalSection(&ctx->log_lock);
#endif
        for (size_t j = 0; j < ctx->groups[gi].count; j++) {
            ImageMeta *m = &ctx->doc->items[ctx->groups[gi].start + j];
            wchar_t png_name[64], png_path[1024];
            UINT w, h;
            uint8_t *rgba;
            uint8_t hdr[0x20];
            swprintf(png_name, L"%hs.%02X.png", tex_id, m->index);
            join_path(png_path, 1024, ctx->src_dir, png_name);
            rgba = load_png(png_path, &w, &h);
            if (m->bpp == 32) {
                make_t2_header(hdr, w, h, m, 0);
                buf_append(&raw, hdr, 0x20);
                {
                    uint8_t *ps2 = xmalloc((size_t)w * h * 4);
                    rgba_to_ps2(rgba, ps2, (size_t)w * h);
                    buf_append(&raw, ps2, (size_t)w * h * 4);
                    free(ps2);
                }
            } else if (m->bpp == 8 && m->palette >= 0) {
                uint8_t *pal = xmalloc(1024);
                uint8_t *idx = xmalloc((size_t)w * h);
                int count = 0;
                int quantized = 0;
                memset(pal, 0, 1024);
                for (size_t p = 0; p < (size_t)w * h; p++) {
                    int found = find_color(pal, count, rgba + p * 4);
                    if (found < 0) {
                        if (count < 256) {
                            memcpy(pal + count * 4, rgba + p * 4, 4);
                            found = count++;
                        } else {
                            quantized = 1;
                            break;
                        }
                    }
                    idx[p] = (uint8_t)found;
                }
                if (quantized) {
                    if (!quantize_with_liq(rgba, w, h, idx, pal)) {
                        memset(pal, 0, 1024);
                        count = 0;
                        for (size_t p = 0; p < (size_t)w * h; p++) {
                            int found = find_color(pal, count, rgba + p * 4);
                            if (found < 0) {
                                if (count < 256) {
                                    memcpy(pal + count * 4, rgba + p * 4, 4);
                                    found = count++;
                                } else {
                                    found = nearest_color(pal, count, rgba + p * 4);
                                }
                            }
                            idx[p] = (uint8_t)found;
                        }
                    }
                }
                if (quantized) {
                    EnterCriticalSection(&ctx->log_lock);
                    printf("%s.%02X.png quantized\n", tex_id, m->index);
                    LeaveCriticalSection(&ctx->log_lock);
                }
                make_t2_header(hdr, w, h, m, 0);
                buf_append(&raw, hdr, 0x20);
                buf_append(&raw, idx, (size_t)w * h);
                swizzle_palette(pal, 256);
                {
                    uint8_t ps2pal[1024];
                    rgba_to_ps2(pal, ps2pal, 256);
                    make_t2_header(hdr, 16, 16, m, 1);
                    buf_append(&raw, hdr, 0x20);
                    buf_append(&raw, ps2pal, 1024);
                }
                free(idx);
                free(pal);
            } else {
                fail("unsupported import format");
            }
            free(rgba);
        }
        buf_append(&raw, tex_tail, sizeof(tex_tail));
        {
            size_t out_size;
            uint8_t *out = pack_1tex(raw.data, raw.size, &out_size);
            char out_name[64];
            wchar_t out_path[1024], wout[64];
            sprintf(out_name, "%s.1tex", tex_id);
            MultiByteToWideChar(CP_ACP, 0, out_name, -1, wout, 64);
            join_path(out_path, 1024, ctx->out_dir, wout);
            write_file(out_path, out, out_size);
            free(out);
        }
        free(raw.data);
    }
    return 0;
}

void onetex_extract_dir(const wchar_t *src_dir, const wchar_t *out_dir) {
    wchar_t pat[1024];
    WIN32_FIND_DATAW fd;
    HANDLE h;
    HANDLE *threads;
    DWORD n;
    ExportCtx ctx;
    TexJob *jobs = NULL;
    size_t job_count = 0;
    ImageMeta *meta = NULL;
    size_t meta_count = 0;
    ensure_dir(out_dir);
    join_path(pat, 1024, src_dir, L"*.1tex");
    h = FindFirstFileW(pat, &fd);
    if (h == INVALID_HANDLE_VALUE)
        fail("no 1tex files found");
    do {
        if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)
            continue;
        jobs = xrealloc(jobs, (job_count + 1) * sizeof(TexJob));
        join_path(jobs[job_count].path, 1024, src_dir, fd.cFileName);
        hex4_from_name(jobs[job_count].id, fd.cFileName);
        job_count++;
    } while (FindNextFileW(h, &fd));
    FindClose(h);
    memset(&ctx, 0, sizeof(ctx));
    ctx.jobs = jobs;
    ctx.job_count = job_count;
    ctx.out_dir = out_dir;
    ctx.next = 0;
    InitializeCriticalSection(&ctx.log_lock);
    InitializeCriticalSection(&ctx.meta_lock);
    n = thread_count();
    if ((size_t)n > job_count && job_count)
        n = (DWORD)job_count;
    if (!n)
        n = 1;
    threads = xmalloc((size_t)n * sizeof(HANDLE));
    for (DWORD i = 0; i < n; i++)
        threads[i] = CreateThread(NULL, 0, export_worker, &ctx, 0, NULL);
    WaitForMultipleObjects(n, threads, TRUE, INFINITE);
    for (DWORD i = 0; i < n; i++)
        CloseHandle(threads[i]);
    DeleteCriticalSection(&ctx.log_lock);
    DeleteCriticalSection(&ctx.meta_lock);
    free(threads);
    meta = ctx.meta;
    meta_count = ctx.meta_count;
    qsort(meta, meta_count, sizeof(ImageMeta), meta_cmp);
    wchar_t xml_path[1024];
    join_path(xml_path, 1024, out_dir, L"1tex.xml");
    write_xml(xml_path, meta, meta_count);
    free(jobs);
    free(meta);
}

char *onetex_extract_one_mem(const uint8_t *src, size_t src_size, const wchar_t *out_dir, const char *tex_id, size_t *xml_size) {
    ImageMeta *meta = NULL;
    size_t meta_count = 0;
    char *xml;
    export_one_tex_mem(src, src_size, out_dir, tex_id, &meta, &meta_count);
    qsort(meta, meta_count, sizeof(ImageMeta), meta_cmp);
    xml = build_xml_text(meta, meta_count, xml_size);
    free(meta);
    return xml;
}

void onetex_pack_dir(const wchar_t *src_dir, const wchar_t *out_dir) {
    wchar_t xml_path[1024];
    XmlDoc doc;
    HANDLE *threads;
    DWORD n;
    ImportCtx ctx;
    TexGroup *groups = NULL;
    size_t group_count = 0;
    ensure_dir(out_dir);
    join_path(xml_path, 1024, src_dir, L"1tex.xml");
    doc = read_xml(xml_path);
    for (size_t i = 0; i < doc.count;) {
        size_t start = i;
        groups = xrealloc(groups, (group_count + 1) * sizeof(TexGroup));
        strcpy(groups[group_count].id, doc.items[i].tex);
        while (i < doc.count && same_id(doc.items[i].tex, groups[group_count].id))
            i++;
        groups[group_count].start = start;
        groups[group_count].count = i - start;
        group_count++;
    }
    memset(&ctx, 0, sizeof(ctx));
    ctx.src_dir = src_dir;
    ctx.out_dir = out_dir;
    ctx.doc = &doc;
    ctx.groups = groups;
    ctx.group_count = group_count;
    ctx.next = 0;
    InitializeCriticalSection(&ctx.log_lock);
    n = thread_count();
    if ((size_t)n > group_count && group_count)
        n = (DWORD)group_count;
    if (!n)
        n = 1;
    threads = xmalloc((size_t)n * sizeof(HANDLE));
    for (DWORD i = 0; i < n; i++)
        threads[i] = CreateThread(NULL, 0, import_worker, &ctx, 0, NULL);
    WaitForMultipleObjects(n, threads, TRUE, INFINITE);
    for (DWORD i = 0; i < n; i++)
        CloseHandle(threads[i]);
    DeleteCriticalSection(&ctx.log_lock);
    free(threads);
    free(groups);
    free(doc.items);
}

uint8_t *onetex_pack_one_mem(const wchar_t *src_dir, const char *xml_text, size_t xml_size, const char *tex_id, size_t *out_size) {
    XmlDoc doc;
    Buf raw = {0};
    (void)xml_size;
    doc = read_xml_text(xml_text);
    for (size_t j = 0; j < doc.count; j++) {
        ImageMeta *m = &doc.items[j];
        wchar_t png_name[64], png_path[1024];
        UINT w, h;
        uint8_t *rgba;
        uint8_t hdr[0x20];
        if (_stricmp(m->tex, tex_id))
            continue;
        swprintf(png_name, L"%hs.%02X.png", tex_id, m->index);
        join_path(png_path, 1024, src_dir, png_name);
        rgba = load_png(png_path, &w, &h);
        if (m->bpp == 32) {
            uint8_t *ps2 = xmalloc((size_t)w * h * 4);
            make_t2_header(hdr, w, h, m, 0);
            buf_append(&raw, hdr, 0x20);
            rgba_to_ps2(rgba, ps2, (size_t)w * h);
            buf_append(&raw, ps2, (size_t)w * h * 4);
            free(ps2);
        } else if (m->bpp == 8 && m->palette >= 0) {
            uint8_t *pal = xmalloc(1024);
            uint8_t *idx = xmalloc((size_t)w * h);
            int count = 0;
            int quantized = 0;
            memset(pal, 0, 1024);
            for (size_t p = 0; p < (size_t)w * h; p++) {
                int found = find_color(pal, count, rgba + p * 4);
                if (found < 0) {
                    if (count < 256) {
                        memcpy(pal + count * 4, rgba + p * 4, 4);
                        found = count++;
                    } else {
                        quantized = 1;
                        break;
                    }
                }
                idx[p] = (uint8_t)found;
            }
            if (quantized && !quantize_with_liq(rgba, w, h, idx, pal)) {
                memset(pal, 0, 1024);
                count = 0;
                for (size_t p = 0; p < (size_t)w * h; p++) {
                    int found = find_color(pal, count, rgba + p * 4);
                    if (found < 0) {
                        if (count < 256) {
                            memcpy(pal + count * 4, rgba + p * 4, 4);
                            found = count++;
                        } else {
                            found = nearest_color(pal, count, rgba + p * 4);
                        }
                    }
                    idx[p] = (uint8_t)found;
                }
            }
            make_t2_header(hdr, w, h, m, 0);
            buf_append(&raw, hdr, 0x20);
            buf_append(&raw, idx, (size_t)w * h);
            swizzle_palette(pal, 256);
            {
                uint8_t ps2pal[1024];
                rgba_to_ps2(pal, ps2pal, 256);
                make_t2_header(hdr, 16, 16, m, 1);
                buf_append(&raw, hdr, 0x20);
                buf_append(&raw, ps2pal, 1024);
            }
            free(idx);
            free(pal);
        } else {
            fail("unsupported import format");
        }
        free(rgba);
    }
    buf_append(&raw, tex_tail, sizeof(tex_tail));
    free(doc.items);
    {
        uint8_t *out = pack_1tex(raw.data, raw.size, out_size);
        free(raw.data);
        return out;
    }
}

#ifndef ONETEX_NO_MAIN
static wchar_t *argw(const char *s) {
    int n = MultiByteToWideChar(CP_ACP, 0, s, -1, NULL, 0);
    wchar_t *w = xmalloc((size_t)n * sizeof(wchar_t));
    MultiByteToWideChar(CP_ACP, 0, s, -1, w, n);
    return w;
}

int main(int argc, char **argv) {
    wchar_t *mode = NULL, *a = NULL, *b = NULL;
    if (argc == 4) {
        mode = argw(argv[1]);
        a = argw(argv[2]);
        b = argw(argv[3]);
    }
    if (argc != 4 || (wcscmp(mode, L"d") && wcscmp(mode, L"e"))) {
        fwprintf(stderr, L"1TEX d input_dir output_dir\n1TEX e input_dir output_dir\n");
        return 1;
    }
    if (!wcscmp(mode, L"d"))
        onetex_extract_dir(a, b);
    else
        onetex_pack_dir(a, b);
    free(mode);
    free(a);
    free(b);
    return 0;
}
#endif
