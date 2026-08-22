#define _CRT_SECURE_NO_WARNINGS
#include <windows.h>
#include <gdiplus.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

typedef struct {
    char name[260];
    int bpp;
    int raw;
} Entry;

typedef struct {
    const char *src;
    const char *dst;
    char (*paths)[1024];
    Entry *entries;
    size_t count;
    volatile LONG next;
    CRITICAL_SECTION lock;
    CRITICAL_SECTION log_lock;
    int errors;
} Ctx;

typedef struct liq_attr liq_attr;
typedef struct liq_image liq_image;
typedef struct liq_result liq_result;
typedef struct { uint8_t r, g, b, a; } liq_color;
typedef struct { uint32_t count; liq_color entries[256]; } liq_palette;

typedef struct {
    HMODULE dll;
    liq_attr *(*attr_create)(void);
    void (*attr_destroy)(liq_attr *);
    int (*set_max_colors)(liq_attr *, int);
    liq_image *(*image_create_rgba)(liq_attr *, void *, int, int, double);
    void (*image_destroy)(liq_image *);
    int (*quantize_image)(liq_attr *, liq_image *, liq_result **);
    const liq_palette *(*get_palette)(liq_result *);
    int (*set_dithering_level)(liq_result *, float);
    int (*write_remapped_image)(liq_result *, liq_image *, void *, size_t);
    void (*result_destroy)(liq_result *);
} LiqApi;

static LiqApi liq;
static int liq_ready = -1;
static ULONG_PTR gdip_token;

static void fail(const char *msg) {
    fprintf(stderr, "%s\n", msg);
    exit(1);
}

static void *xmalloc(size_t n) {
    void *p = malloc(n ? n : 1);
    if (!p) fail("out of memory");
    return p;
}

static uint8_t *read_file(const char *path, size_t *size) {
    FILE *f = fopen(path, "rb");
    long len;
    uint8_t *d;
    if (!f) fail("cannot open file");
    fseek(f, 0, SEEK_END);
    len = ftell(f);
    fseek(f, 0, SEEK_SET);
    d = xmalloc(len);
    if (fread(d, 1, len, f) != (size_t)len) fail("cannot read file");
    fclose(f);
    *size = len;
    return d;
}

static void write_file(const char *path, const void *d, size_t n) {
    FILE *f = fopen(path, "wb");
    if (!f) fail("cannot create file");
    if (n && fwrite(d, 1, n, f) != n) fail("cannot write file");
    fclose(f);
}

static int ensure_liq(void) {
    if (liq_ready >= 0) return liq_ready;
    memset(&liq, 0, sizeof(liq));
    liq.dll = LoadLibraryA("libimagequant.dll");
    if (!liq.dll) { liq_ready = 0; return 0; }
#define LIQ(n) do { liq.n = (void *)GetProcAddress(liq.dll, "liq_" #n); if (!liq.n) fail("libimagequant proc missing"); } while (0)
    LIQ(attr_create); LIQ(attr_destroy); LIQ(set_max_colors); LIQ(image_create_rgba);
    LIQ(image_destroy); LIQ(quantize_image); LIQ(get_palette); LIQ(set_dithering_level);
    LIQ(write_remapped_image); LIQ(result_destroy);
#undef LIQ
    liq_ready = 1;
    return 1;
}

static int quantize_liq(const uint8_t *rgba, uint32_t w, uint32_t h, uint8_t *idx, uint8_t *pal) {
    liq_attr *attr;
    liq_image *img;
    liq_result *res = NULL;
    const liq_palette *lp;
    uint32_t i;
    if (!ensure_liq()) return 0;
    attr = liq.attr_create();
    if (!attr) return 0;
    if (liq.set_max_colors(attr, 256)) { liq.attr_destroy(attr); return 0; }
    img = liq.image_create_rgba(attr, (void *)rgba, (int)w, (int)h, 0.0);
    if (!img) { liq.attr_destroy(attr); return 0; }
    if (liq.quantize_image(attr, img, &res) || !res) { liq.image_destroy(img); liq.attr_destroy(attr); return 0; }
    liq.set_dithering_level(res, 0.0f);
    if (liq.write_remapped_image(res, img, idx, (size_t)w * h)) {
        liq.result_destroy(res); liq.image_destroy(img); liq.attr_destroy(attr);
        return 0;
    }
    lp = liq.get_palette(res);
    if (!lp || lp->count > 256) { liq.result_destroy(res); liq.image_destroy(img); liq.attr_destroy(attr); return 0; }
    memset(pal, 0, 1024);
    for (i = 0; i < lp->count; i++) {
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

static int find_color(const uint8_t *pal, int count, const uint8_t *c) {
    int i;
    for (i = 0; i < count; i++)
        if (!memcmp(pal + i * 4, c, 4)) return i;
    return -1;
}

static int nearest_color(const uint8_t *pal, int count, const uint8_t *c) {
    int i, best = 0;
    uint32_t bd = 0xFFFFFFFFu;
    for (i = 0; i < count; i++) {
        int dr = pal[i * 4 + 0] - c[0], dg = pal[i * 4 + 1] - c[1];
        int db = pal[i * 4 + 2] - c[2], da = pal[i * 4 + 3] - c[3];
        uint32_t d = (uint32_t)(dr * dr + dg * dg + db * db + da * da);
        if (d < bd) { bd = d; best = i; }
    }
    return best;
}

static void ensure_gdip(void) {
    static int done;
    if (!done) {
        GdiplusStartupInput in;
        memset(&in, 0, sizeof(in));
        in.GdiplusVersion = 1;
        if (GdiplusStartup(&gdip_token, &in, NULL) != Ok) fail("GdiplusStartup failed");
        done = 1;
    }
}

static CLSID png_clsid(void) {
    UINT count = 0, bytes = 0, i;
    CLSID clsid;
    ImageCodecInfo *info;
    memset(&clsid, 0, sizeof(clsid));
    if (GdipGetImageEncodersSize(&count, &bytes) != Ok || !bytes) fail("GDI+ encoders unavailable");
    info = xmalloc(bytes);
    if (GdipGetImageEncoders(count, bytes, info) != Ok) fail("GDI+ encoder list failed");
    for (i = 0; i < count; i++)
        if (info[i].MimeType && !wcscmp(info[i].MimeType, L"image/png")) { clsid = info[i].Clsid; break; }
    free(info);
    return clsid;
}

static void save_png(const char *path, const uint8_t *rgba, uint32_t w, uint32_t h) {
    CLSID enc = png_clsid();
    GpBitmap *bmp = NULL;
    uint8_t *argb = xmalloc((size_t)w * h * 4);
    wchar_t wpath[1024];
    size_t i;
    for (i = 0; i < (size_t)w * h; i++) {
        argb[i * 4 + 0] = rgba[i * 4 + 2];
        argb[i * 4 + 1] = rgba[i * 4 + 1];
        argb[i * 4 + 2] = rgba[i * 4 + 0];
        argb[i * 4 + 3] = rgba[i * 4 + 3];
    }
    if (GdipCreateBitmapFromScan0((INT)w, (INT)h, (INT)(w * 4), PixelFormat32bppARGB, argb, &bmp) != Ok)
        fail("GdipCreateBitmapFromScan0 failed");
    MultiByteToWideChar(CP_ACP, 0, path, -1, wpath, 1024);
    if (GdipSaveImageToFile((GpImage *)bmp, wpath, &enc, NULL) != Ok)
        fail("GdipSaveImageToFile failed");
    GdipDisposeImage((GpImage *)bmp);
    free(argb);
}

static uint8_t *load_png(const char *path, uint32_t *W, uint32_t *H) {
    GpImage *img = NULL;
    wchar_t wpath[1024];
    UINT w, h, y, x;
    GpRect rect;
    BitmapData bd;
    uint8_t *rgba;
    ensure_gdip();
    MultiByteToWideChar(CP_ACP, 0, path, -1, wpath, 1024);
    if (GdipLoadImageFromFile(wpath, &img) != Ok) fail("GdipLoadImageFromFile failed");
    GdipGetImageWidth(img, &w);
    GdipGetImageHeight(img, &h);
    rect.X = 0; rect.Y = 0; rect.Width = (INT)w; rect.Height = (INT)h;
    if (GdipBitmapLockBits((GpBitmap *)img, &rect, ImageLockModeRead, PixelFormat32bppARGB, &bd) != Ok)
        fail("GdipBitmapLockBits failed");
    rgba = xmalloc((size_t)w * h * 4);
    for (y = 0; y < h; y++) {
        const uint8_t *row = (const uint8_t *)bd.Scan0 + (size_t)y * bd.Stride;
        for (x = 0; x < w; x++) {
            const uint8_t *p = row + x * 4;
            uint8_t *q = rgba + ((size_t)y * w + x) * 4;
            q[0] = p[2]; q[1] = p[1]; q[2] = p[0]; q[3] = p[3];
        }
    }
    GdipBitmapUnlockBits((GpBitmap *)img, &bd);
    GdipDisposeImage(img);
    *W = w; *H = h;
    return rgba;
}

static uint8_t *rle_decode(const uint8_t *d, size_t n, size_t count, size_t ps) {
    uint8_t *out = xmalloc(count * ps);
    size_t pos = 54, got = 0, take, k;
    size_t cnt = 0, rep = 0;
    uint8_t pix[4];
    while (got < count) {
        if (!cnt) {
            uint8_t c = pos < n ? d[pos] : 0;
            pos++;
            rep = c & 0x80;
            cnt = c & 0x7F;
            if (rep) {
                for (k = 0; k < ps; k++) pix[k] = pos + k < n ? d[pos + k] : 0;
                pos += ps;
            }
        }
        take = cnt < count - got ? cnt : count - got;
        if (rep) {
            for (k = 0; k < take; k++) memcpy(out + (got + k) * ps, pix, ps);
        } else {
            for (k = 0; k < take * ps; k++) out[got * ps + k] = pos + k < n ? d[pos + k] : 0;
            pos += take * ps;
        }
        got += take;
        cnt = 0;
    }
    return out;
}

static uint8_t *rle_encode(const uint8_t *flat, size_t total, size_t ps, size_t *out_size) {
    size_t cap = total * ps + total * ps / 8 + 1024;
    uint8_t *out = xmalloc(cap);
    size_t i = 0, run, q = 0;
    while (i < total) {
        run = 1;
        while (i + run < total && run < 127 && !memcmp(flat + i * ps, flat + (i + run) * ps, ps)) run++;
        if (run > 1) {
            out[q++] = (uint8_t)(0x80 | run);
            memcpy(out + q, flat + i * ps, ps); q += ps;
            i += run;
        } else {
            run = 0;
            while (i + run < total && run < 127) {
                if (i + run + 1 < total && !memcmp(flat + (i + run) * ps, flat + (i + run + 1) * ps, ps)) break;
                run++;
            }
            out[q++] = (uint8_t)run;
            memcpy(out + q, flat + i * ps, run * ps); q += run * ps;
            i += run;
        }
    }
    *out_size = q;
    return out;
}

static void to_argb(const uint8_t *rgba, uint8_t *argb, size_t px) {
    size_t i;
    for (i = 0; i < px; i++) {
        argb[i * 4 + 0] = rgba[i * 4 + 3];
        argb[i * 4 + 1] = rgba[i * 4 + 0];
        argb[i * 4 + 2] = rgba[i * 4 + 1];
        argb[i * 4 + 3] = rgba[i * 4 + 2];
    }
}

static void from_argb(const uint8_t *argb, uint8_t *rgba, size_t px) {
    size_t i;
    for (i = 0; i < px; i++) {
        rgba[i * 4 + 0] = argb[i * 4 + 1];
        rgba[i * 4 + 1] = argb[i * 4 + 2];
        rgba[i * 4 + 2] = argb[i * 4 + 3];
        rgba[i * 4 + 3] = argb[i * 4 + 0];
    }
}

static uint8_t *pb6_decode(const uint8_t *d, size_t n, uint32_t *W, uint32_t *H, int *bpp_out) {
    uint32_t w = d[18] | d[19] << 8, h = d[22] | d[23] << 8;
    int bpp = d[28] | d[29] << 8;
    size_t px = (size_t)w * h, i, y, x;
    uint8_t *rgba = xmalloc(px * 4);
    if (!memcmp(d, "BM8", 3)) {
        uint8_t *argb = xmalloc(px * 4);
        memcpy(argb, d + 54, px * 4);
        from_argb(argb, rgba, px);
        free(argb);
    } else if (bpp == 8) {
        for (i = 0; i < px; i++) {
            const uint8_t *e = d + 54 + d[1078 + i] * 4;
            rgba[i * 4 + 0] = e[0]; rgba[i * 4 + 1] = e[1]; rgba[i * 4 + 2] = e[2];
            rgba[i * 4 + 3] = (!e[0] && !e[1] && !e[2]) ? 0 : 255;
        }
    } else if (bpp == 24) {
        uint8_t *flat = rle_decode(d, n, px, 3);
        for (i = 0; i < px; i++) {
            rgba[i * 4 + 0] = flat[i * 3]; rgba[i * 4 + 1] = flat[i * 3 + 1];
            rgba[i * 4 + 2] = flat[i * 3 + 2]; rgba[i * 4 + 3] = 255;
        }
        free(flat);
    } else if (bpp == 32) {
        uint8_t *flat = rle_decode(d, n, px, 4);
        from_argb(flat, rgba, px);
        free(flat);
    } else {
        fail("unsupported bpp");
    }
    for (y = 0; y < h / 2; y++)
        for (x = 0; x < w; x++) {
            uint8_t *a = rgba + ((size_t)y * w + x) * 4;
            uint8_t *b = rgba + ((size_t)(h - 1 - y) * w + x) * 4;
            uint8_t t[4];
            memcpy(t, a, 4); memcpy(a, b, 4); memcpy(b, t, 4);
        }
    *W = w; *H = h; *bpp_out = bpp;
    return rgba;
}

static void put16(uint8_t *p, uint16_t v) { p[0] = v; p[1] = v >> 8; }

static void put32(uint8_t *p, uint32_t v) { p[0] = v; p[1] = v >> 8; p[2] = v >> 16; p[3] = v >> 24; }

static uint8_t *pb6_encode(const uint8_t *rgba, uint32_t w, uint32_t h, int bpp, int raw, size_t *out_size) {
    size_t px = (size_t)w * h, i, y, x, ps;
    uint8_t *flip = xmalloc(px * 4);
    uint8_t *out;
    size_t q = 0;
    for (y = 0; y < h; y++)
        memcpy(flip + (size_t)y * w * 4, rgba + (size_t)(h - 1 - y) * w * 4, (size_t)w * 4);
    if (raw) {
        out = xmalloc(54 + px * 4);
        to_argb(flip, out + 54, px);
        q = 54 + px * 4;
        memcpy(out, "BM8\x80", 4);
        put32(out + 4, (uint32_t)(54 + px * 4));
        put32(out + 10, 54);
        put32(out + 14, 40); put32(out + 18, w); put32(out + 22, h);
        put16(out + 26, 1); put16(out + 28, 32);
        *out_size = q;
        free(flip);
        return out;
    }
    ps = bpp == 32 ? 4 : 3;
    if (bpp == 8) {
        uint8_t pal[1024], *idx = xmalloc(px);
        int count = 0, quantized = 0;
        memset(pal, 0, sizeof(pal));
        for (i = 0; i < px; i++) {
            int found = find_color(pal, count, flip + i * 4);
            if (found < 0) {
                if (count < 256) { memcpy(pal + count * 4, flip + i * 4, 4); found = count++; }
                else { quantized = 1; break; }
            }
            idx[i] = (uint8_t)found;
        }
        if (quantized) {
            if (!quantize_liq(flip, w, h, idx, pal)) {
                memset(pal, 0, sizeof(pal));
                count = 0;
                for (i = 0; i < px; i++) {
                    int found = find_color(pal, count, flip + i * 4);
                    if (found < 0) {
                        if (count < 256) { memcpy(pal + count * 4, flip + i * 4, 4); found = count++; }
                        else found = nearest_color(pal, count, flip + i * 4);
                    }
                    idx[i] = (uint8_t)found;
                }
            }
            fprintf(stderr, "%ux%u quantized\n", w, h);
        }
        out = xmalloc(1078 + px);
        out[0] = 'P'; out[1] = 'B'; out[2] = '6'; out[3] = 0x04;
        put32(out + 4, (uint32_t)(1078 + px));
        put32(out + 10, 1078);
        put32(out + 14, 40); put32(out + 18, w); put32(out + 22, h);
        put16(out + 26, 1); put16(out + 28, 8);
        memcpy(out + 54, pal, 1024);
        for (y = 0; y < h; y++) memcpy(out + 1078 + y * w, idx + y * w, w);
        *out_size = 1078 + px;
        free(idx);
        free(flip);
        return out;
    }
    {
        uint8_t *flat = xmalloc(px * ps);
        uint8_t *body;
        size_t body_size;
        if (bpp == 32) to_argb(flip, flat, px);
        else for (i = 0; i < px; i++) memcpy(flat + i * 3, flip + i * 4, 3);
        body = rle_encode(flat, px, ps, &body_size);
        out = xmalloc(54 + body_size);
        out[0] = 'P'; out[1] = 'B'; out[2] = '6'; out[3] = bpp == 24 ? 0x40 : 0x00;
        put32(out + 4, (uint32_t)(px * ps * 10 + 54));
        put32(out + 10, 54);
        put32(out + 14, 40); put32(out + 18, w); put32(out + 22, h);
        put16(out + 26, 1); put16(out + 28, (uint16_t)bpp);
        memcpy(out + 54, body, body_size);
        *out_size = 54 + body_size;
        free(body);
        free(flat);
        free(flip);
        return out;
    }
}

static void path_join(char *out, const char *dir, const char *name) {
    sprintf(out, "%s\\%s", dir, name);
}

static int entry_cmp(const void *a, const void *b) {
    return strcmp(((const Entry *)a)->name, ((const Entry *)b)->name);
}

static DWORD WINAPI worker_d(void *arg) {
    Ctx *ctx = arg;
    ensure_gdip();
    for (;;) {
        LONG i = InterlockedIncrement(&ctx->next) - 1;
        char name[260], ppath[1024];
        uint8_t *d, *rgba;
        size_t n;
        uint32_t w, h;
        int bpp, raw;
        if ((size_t)i >= ctx->count) break;
        _splitpath(ctx->paths[i], NULL, NULL, name, NULL);
        d = read_file(ctx->paths[i], &n);
        raw = !memcmp(d, "BM8", 3);
        fprintf(stderr, "A %s\n", name);
        rgba = pb6_decode(d, n, &w, &h, &bpp);
        free(d);
        fprintf(stderr, "B %s\n", name);
        sprintf(ppath, "%s\\%s.png", ctx->dst, name);
        save_png(ppath, rgba, w, h);
        free(rgba);
        fprintf(stderr, "C %s\n", name);
        EnterCriticalSection(&ctx->log_lock);
        printf("%s\n", name);
        LeaveCriticalSection(&ctx->log_lock);
        EnterCriticalSection(&ctx->lock);
        {
            FILE *f = fopen("pb6._tmp", "a");
            fprintf(f, "%s %d %d\n", name, bpp, raw);
            fclose(f);
        }
        LeaveCriticalSection(&ctx->lock);
    }
    return 0;
}

static const char *attr(const char *line, const char *key, char *buf, size_t cap) {
    char pat[64];
    const char *p, *q;
    size_t n;
    sprintf(pat, "%s=\"", key);
    p = strstr(line, pat);
    if (!p) return NULL;
    p += strlen(pat);
    q = strchr(p, '"');
    if (!q) return NULL;
    n = (size_t)(q - p);
    if (n >= cap) n = cap - 1;
    memcpy(buf, p, n);
    buf[n] = 0;
    return buf;
}

int main(int argc, char **argv) {
    WIN32_FIND_DATAA fd;
    HANDLE h;
    Ctx ctx;
    HANDLE *threads;
    DWORD n, k;
    char pat[1024];
    if (argc != 4 || (strcmp(argv[1], "d") && strcmp(argv[1], "e"))) {
        fprintf(stderr, "pb6 d src_dir dst_dir\npb6 e src_dir dst_dir\n");
        return 1;
    }
    CreateDirectoryA(argv[3], NULL);
    memset(&ctx, 0, sizeof(ctx));
    ctx.src = argv[2];
    ctx.dst = argv[3];
    InitializeCriticalSection(&ctx.lock);
    InitializeCriticalSection(&ctx.log_lock);
    ensure_gdip();
    if (argv[1][0] == 'd') {
        FILE *xf;
        Entry *list;
        size_t count = 0, cap = 256, i;
        path_join(pat, argv[2], "*.bmp");
        ctx.paths = xmalloc(cap * sizeof(*ctx.paths));
        h = FindFirstFileA(pat, &fd);
        if (h == INVALID_HANDLE_VALUE) fail("no bmp files found");
        do {
            uint8_t magic[3];
            char ppath[1024];
            FILE *f;
            if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) continue;
            path_join(ppath, argv[2], fd.cFileName);
            f = fopen(ppath, "rb");
            if (!f || fread(magic, 1, 3, f) != 3) { if (f) fclose(f); continue; }
            fclose(f);
            if (memcmp(magic, "PB6", 3) && memcmp(magic, "BM8", 3)) continue;
            if (count == cap) { cap *= 2; ctx.paths = realloc(ctx.paths, cap * sizeof(*ctx.paths)); }
            strcpy(ctx.paths[count++], ppath);
        } while (FindNextFileA(h, &fd));
        FindClose(h);
        ctx.count = count;
        DeleteFileA("pb6._tmp");
        n = count < 16 ? (DWORD)(count ? count : 1) : 16;
        threads = xmalloc(n * sizeof(HANDLE));
        for (k = 0; k < n; k++) threads[k] = CreateThread(NULL, 0, worker_d, &ctx, 0, NULL);
        WaitForMultipleObjects(n, threads, TRUE, INFINITE);
        for (k = 0; k < n; k++) CloseHandle(threads[k]);
        free(threads);
        xf = fopen("pb6._tmp", "r");
        if (!xf) fail("no results");
        list = xmalloc(count * sizeof(Entry));
        i = 0;
        while (i < count && fscanf(xf, "%255s %d %d", list[i].name, &list[i].bpp, &list[i].raw) == 3) i++;
        fclose(xf);
        qsort(list, i, sizeof(Entry), entry_cmp);
        path_join(pat, argv[3], "pb6.xml");
        xf = fopen(pat, "w");
        fprintf(xf, "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n<pb6>\n");
        for (i = 0; i < count; i++)
            fprintf(xf, "  <image name=\"%s\" bpp=\"%d\"%s />\n", list[i].name, list[i].bpp, list[i].raw ? " raw=\"1\"" : "");
        fprintf(xf, "</pb6>\n");
        fclose(xf);
        DeleteFileA("pb6._tmp");
        free(list);
    } else {
        char xmlpath[1024], line[2048];
        FILE *xf;
        Entry *list;
        size_t count = 0, cap = 256;
        path_join(xmlpath, argv[2], "pb6.xml");
        xf = fopen(xmlpath, "r");
        if (!xf) fail("pb6.xml not found");
        list = xmalloc(cap * sizeof(Entry));
        while (fgets(line, sizeof(line), xf)) {
            char name[260], buf[64];
            if (!strstr(line, "<image ")) continue;
            if (!attr(line, "name", name, sizeof(name))) continue;
            if (count == cap) { cap *= 2; list = realloc(list, cap * sizeof(Entry)); }
            strcpy(list[count].name, name);
            list[count].bpp = attr(line, "bpp", buf, sizeof(buf)) ? atoi(buf) : 0;
            list[count].raw = attr(line, "raw", buf, sizeof(buf)) ? atoi(buf) : 0;
            count++;
        }
        fclose(xf);
        for (k = 0; k < count; k++) {
            char ppath[1024], opath[1024];
            uint8_t *rgba;
            uint32_t w, hh;
            size_t n2;
            uint8_t *out;
            sprintf(ppath, "%s\\%s.png", argv[2], list[k].name);
            if (GetFileAttributesA(ppath) == INVALID_FILE_ATTRIBUTES) continue;
            rgba = load_png(ppath, &w, &hh);
            out = pb6_encode(rgba, w, hh, list[k].bpp, list[k].raw, &n2);
            sprintf(opath, "%s\\%s.bmp", argv[3], list[k].name);
            write_file(opath, out, n2);
            free(out);
            free(rgba);
            printf("%s\n", list[k].name);
        }
        path_join(pat, argv[2], "*.png");
        h = FindFirstFileA(pat, &fd);
        if (h != INVALID_HANDLE_VALUE) {
            do {
                char stem[260];
                size_t j;
                int found = 0;
                _splitpath(fd.cFileName, NULL, NULL, stem, NULL);
                for (j = 0; j < count; j++)
                    if (!strcmp(list[j].name, stem)) { found = 1; break; }
                if (!found) fprintf(stderr, "%s: not in pb6.xml\n", fd.cFileName);
            } while (FindNextFileA(h, &fd));
            FindClose(h);
        }
        free(list);
    }
    DeleteCriticalSection(&ctx.lock);
    DeleteCriticalSection(&ctx.log_lock);
    return 0;
}
