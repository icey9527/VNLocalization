#include "quantize.h"
#include <windows.h>
#include <stdio.h>
#include <string.h>

typedef struct liq_attr liq_attr;
typedef struct liq_image liq_image;
typedef struct liq_result liq_result;
typedef struct { uint8_t r, g, b, a; } liq_color;
typedef struct { unsigned count; liq_color entries[256]; } liq_palette;
typedef struct {
    HMODULE dll;
    liq_attr *(__cdecl *attr_create)(void);
    void (__cdecl *attr_destroy)(liq_attr *);
    int (__cdecl *set_max_colors)(liq_attr *, int);
    liq_image *(__cdecl *image_create_rgba)(liq_attr *, const void *, int, int, double);
    void (__cdecl *image_destroy)(liq_image *);
    /* Supplied DLL uses the older two-argument ABI and returns a result pointer. */
    liq_result *(__cdecl *quantize_image)(liq_attr *, liq_image *);
    const liq_palette *(__cdecl *get_palette)(liq_result *);
    int (__cdecl *set_dithering_level)(liq_result *, float);
    int (__cdecl *write_remapped_image)(liq_result *, liq_image *, void *, size_t);
    void (__cdecl *result_destroy)(liq_result *);
} LiqApi;
static LiqApi liq;

static int load_liq(void)
{
    if (liq.dll) return 0;
    wchar_t path[1024];
    DWORD n = GetModuleFileNameW(NULL, path, 1024);
    if (!n || n >= 1024) return 1;
    wchar_t *name = wcsrchr(path, L'\\');
    if (!name || (size_t)(name-path)+19 >= 1024) return 1;
    wcscpy(name+1, L"libimagequant.dll");
    liq.dll = LoadLibraryW(path);
    if (!liq.dll) { printf("Error: cannot load libimagequant.dll next to saf.exe (Win32 error %lu)\n", GetLastError()); return 1; }
#define PROC(field, symbol) do { *(FARPROC *)&liq.field = GetProcAddress(liq.dll, symbol); if (!liq.field) goto fail; } while (0)
    PROC(attr_create, "liq_attr_create"); PROC(attr_destroy, "liq_attr_destroy");
    PROC(set_max_colors, "liq_set_max_colors"); PROC(image_create_rgba, "liq_image_create_rgba");
    PROC(image_destroy, "liq_image_destroy"); PROC(quantize_image, "liq_quantize_image");
    PROC(get_palette, "liq_get_palette"); PROC(set_dithering_level, "liq_set_dithering_level");
    PROC(write_remapped_image, "liq_write_remapped_image"); PROC(result_destroy, "liq_result_destroy");
#undef PROC
    return 0;
fail:
    printf("Error: libimagequant.dll is missing a required function\n");
    FreeLibrary(liq.dll); memset(&liq, 0, sizeof liq); return 1;
}

int image_palette(const uint8_t *rgba, unsigned w, unsigned h, uint8_t *indices, uint8_t *palette)
{
    unsigned count = 0;
    /* Fixed 512-slot lookup: at most 256 colors, no per-pixel allocation. */
    unsigned short slots[512] = {0};
    size_t n = (size_t)w*h, i;
    memset(palette, 0, 1024);
    for (i = 0; i < n; i++) {
        uint32_t key;
        memcpy(&key, rgba+4*i, 4);
        unsigned slot = ((key ^ (key >> 16))*2654435761u) >> 23;
        while (slots[slot] && memcmp(palette+4*(slots[slot]-1), rgba+4*i, 4)) slot = (slot+1)&511;
        unsigned j;
        if (!slots[slot]) {
            if (count == 256) break;
            j = count++;
            memcpy(palette+4*j, rgba+4*i, 4);
            slots[slot] = j+1;
        } else j = slots[slot]-1;
        indices[i] = j;
    }
    if (i == n) return 0;
    if (load_liq()) return 1;
    liq_attr *attr = liq.attr_create();
    liq_image *image = NULL;
    liq_result *result = NULL;
    int failed = !attr;
    int code = 0;
    const char *stage = "attribute allocation";
    if (!failed) { stage = "set_max_colors"; code = liq.set_max_colors(attr, 256); failed = code != 0; }
    if (!failed) image = liq.image_create_rgba(attr, rgba, w, h, 0.0);
    if (!image && !failed) { stage = "image allocation"; failed = 1; }
    if (!failed) { stage = "quantize_image"; result = liq.quantize_image(attr, image); failed = !result; }
    if (!failed) { stage = "set_dithering_level"; code = liq.set_dithering_level(result, 0.0f); failed = code != 0; }
    if (!failed) { stage = "write_remapped_image"; code = liq.write_remapped_image(result, image, indices, n); failed = code != 0; }
    if (!failed) {
        const liq_palette *pal = liq.get_palette(result);
        if (!pal || !pal->count || pal->count > 256) { stage = "palette"; failed = 1; }
        else { memset(palette, 0, 1024); memcpy(palette, pal->entries, pal->count*4); }
    }
    if (result) liq.result_destroy(result);
    if (image) liq.image_destroy(image);
    if (attr) liq.attr_destroy(attr);
    if (!failed) printf("  Quantized to <=256 RGBA colors (libimagequant.dll, no dithering)\n");
    else printf("Error: libimagequant %s failed (code %d)\n", stage, code);
    return failed;
}
