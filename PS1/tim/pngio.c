#include "pngio.h"

#include <stdlib.h>
#include <string.h>

#include <gdiplus.h>

#include "util.h"

static ULONG_PTR g_gdiplus_token;
static int g_gdiplus_ready;

static CLSID png_encoder_clsid(void) {
    UINT count = 0, bytes = 0;
    CLSID clsid;
    ImageCodecInfo *info;
    memset(&clsid, 0, sizeof(clsid));
    if (GdipGetImageEncodersSize(&count, &bytes) != Ok || !bytes) return clsid;
    info = (ImageCodecInfo *)malloc(bytes);
    if (!info) return clsid;
    if (GdipGetImageEncoders(count, bytes, info) == Ok) {
        for (UINT i = 0; i < count; ++i) {
            if (info[i].MimeType && wcscmp(info[i].MimeType, L"image/png") == 0) {
                clsid = info[i].Clsid;
                break;
            }
        }
    }
    free(info);
    return clsid;
}

int png_runtime_init(void) {
    if (!g_gdiplus_ready) {
        GdiplusStartupInput input;
        memset(&input, 0, sizeof(input));
        input.GdiplusVersion = 1;
        if (GdiplusStartup(&g_gdiplus_token, &input, NULL) != Ok) return -1;
        g_gdiplus_ready = 1;
    }
    return 0;
}

void png_runtime_shutdown(void) {
    if (g_gdiplus_ready) {
        GdiplusShutdown(g_gdiplus_token);
        g_gdiplus_ready = 0;
    }
}

int png_read_rgba_file_w(const wchar_t *path, uint8_t **rgba_out, int *w_out, int *h_out) {
    GpBitmap *bmp = NULL;
    BitmapData bd;
    Rect rect;
    uint8_t *rgba;
    int w, h;
    if (png_runtime_init() != 0) return -1;
    if (GdipLoadImageFromFile(path, (GpImage **)&bmp) != Ok) return -1;
    if (GdipGetImageWidth((GpImage *)bmp, (UINT *)&w) != Ok || GdipGetImageHeight((GpImage *)bmp, (UINT *)&h) != Ok) {
        GdipDisposeImage((GpImage *)bmp);
        return -1;
    }
    rect.X = 0;
    rect.Y = 0;
    rect.Width = w;
    rect.Height = h;
    if (GdipBitmapLockBits(bmp, &rect, ImageLockModeRead, PixelFormat32bppARGB, &bd) != Ok) {
        GdipDisposeImage((GpImage *)bmp);
        return -1;
    }
    rgba = (uint8_t *)malloc((size_t)w * (size_t)h * 4);
    if (!rgba) {
        GdipBitmapUnlockBits(bmp, &bd);
        GdipDisposeImage((GpImage *)bmp);
        return -1;
    }
    for (int y = 0; y < h; ++y) {
        const uint8_t *row = (const uint8_t *)bd.Scan0 + (size_t)y * bd.Stride;
        for (int x = 0; x < w; ++x) {
            const uint8_t *p = row + x * 4;
            size_t i = ((size_t)y * (size_t)w + (size_t)x) * 4;
            rgba[i + 0] = p[2];
            rgba[i + 1] = p[1];
            rgba[i + 2] = p[0];
            rgba[i + 3] = p[3];
        }
    }
    GdipBitmapUnlockBits(bmp, &bd);
    GdipDisposeImage((GpImage *)bmp);
    *rgba_out = rgba;
    if (w_out) *w_out = w;
    if (h_out) *h_out = h;
    return 0;
}

int png_write_rgba_file_w(const wchar_t *path, const uint8_t *rgba, int width, int height) {
    CLSID clsid;
    GpBitmap *bmp;
    uint8_t *argb;
    int i;
    if (png_runtime_init() != 0) return -1;
    clsid = png_encoder_clsid();
    if (!clsid.Data1 && !clsid.Data2 && !clsid.Data3 && !clsid.Data4[0]) return -1;
    argb = (uint8_t *)malloc((size_t)width * (size_t)height * 4);
    if (!argb) return -1;
    for (i = 0; i < width * height; ++i) {
        argb[i * 4 + 0] = rgba[i * 4 + 2];
        argb[i * 4 + 1] = rgba[i * 4 + 1];
        argb[i * 4 + 2] = rgba[i * 4 + 0];
        argb[i * 4 + 3] = rgba[i * 4 + 3];
    }
    if (GdipCreateBitmapFromScan0(width, height, width * 4, PixelFormat32bppARGB, argb, &bmp) != Ok) {
        free(argb);
        return -1;
    }
    if (GdipSaveImageToFile((GpImage *)bmp, path, &clsid, NULL) != Ok) {
        GdipDisposeImage((GpImage *)bmp);
        free(argb);
        return -1;
    }
    GdipDisposeImage((GpImage *)bmp);
    free(argb);
    return 0;
}
