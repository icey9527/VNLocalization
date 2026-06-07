#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>
#include <shellapi.h>

#include "tim.h"
#include "pngio.h"
#include "quant.h"
#include "xml.h"
#include "util.h"

typedef struct FileList {
    wchar_t **items;
    size_t count;
} FileList;

static void filelist_free(FileList *list) {
    for (size_t i = 0; i < list->count; ++i) free(list->items[i]);
    free(list->items);
    memset(list, 0, sizeof(*list));
}

static int filelist_push(FileList *list, const wchar_t *path) {
    wchar_t **tmp = (wchar_t **)realloc(list->items, (list->count + 1) * sizeof(wchar_t *));
    if (!tmp) return -1;
    list->items = tmp;
    list->items[list->count] = _wcsdup(path);
    if (!list->items[list->count]) return -1;
    list->count++;
    return 0;
}

static int has_ext_w(const wchar_t *name, const wchar_t *ext) {
    size_t n = wcslen(name), e = wcslen(ext);
    if (n < e) return 0;
    return _wcsicmp(name + n - e, ext) == 0;
}

static int scan_recursive(const wchar_t *dir, const wchar_t *ext, FileList *out) {
    wchar_t pattern[MAX_PATH * 4];
    WIN32_FIND_DATAW fd;
    HANDLE h;
    if (swprintf(pattern, L"%ls\\*.*", dir) < 0) return -1;
    h = FindFirstFileW(pattern, &fd);
    if (h == INVALID_HANDLE_VALUE) return 0;
    do {
        if (wcscmp(fd.cFileName, L".") == 0 || wcscmp(fd.cFileName, L"..") == 0) continue;
        {
            wchar_t path[MAX_PATH * 4];
            path_join_w(path, MAX_PATH * 4, dir, fd.cFileName);
            if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
                scan_recursive(path, ext, out);
            } else if (has_ext_w(fd.cFileName, ext)) {
                filelist_push(out, path);
            }
        }
    } while (FindNextFileW(h, &fd));
    FindClose(h);
    return 0;
}

static int inspect_tim(const wchar_t *path) {
    TimImage img;
    int rc = tim_read_file_w(path, &img);
    if (rc) return rc;
    tim_print_info(&img, path);
    tim_image_free(&img);
    return 0;
}

static int convert_tim_to_png(const wchar_t *tim_path, const wchar_t *png_path) {
    TimImage img;
    uint8_t *rgba = NULL;
    int rc = tim_read_file_w(tim_path, &img);
    if (rc) return rc;
    wprintf(L"%ls -> %ls\n", tim_path, png_path);
    rc = tim_to_rgba(&img, &rgba, NULL, NULL);
    if (!rc) rc = png_write_rgba_file_w(png_path, rgba, img.width, img.height);
    free(rgba);
    tim_image_free(&img);
    return rc;
}

static uint8_t tim5_to_8(uint8_t v) {
    return (uint8_t)((v << 3) | (v >> 2));
}

static uint8_t fixed_palette_index(const uint8_t *rgba, const uint16_t *palette, int palette_count) {
    int best = 0;
    unsigned long best_dist = ~0UL;
    int want_opaque = rgba[3] >= 128;
    for (int i = 0; i < palette_count; ++i) {
        uint16_t c = palette[i];
        int is_opaque = (c & 0x8000) != 0;
        if (want_opaque != is_opaque) continue;
        {
            int pr = tim5_to_8((uint8_t)(c & 0x1F));
            int pg = tim5_to_8((uint8_t)((c >> 5) & 0x1F));
            int pb = tim5_to_8((uint8_t)((c >> 10) & 0x1F));
            long dr = (long)rgba[0] - pr;
            long dg = (long)rgba[1] - pg;
            long db = (long)rgba[2] - pb;
            unsigned long dist = (unsigned long)(dr * dr * 3L + dg * dg * 6L + db * db * 2L);
            if (dist < best_dist) {
                best_dist = dist;
                best = i;
            }
        }
    }
    if (best_dist != ~0UL) return (uint8_t)best;
    for (int i = 0; i < palette_count; ++i) {
        uint16_t c = palette[i];
        int pr = tim5_to_8((uint8_t)(c & 0x1F));
        int pg = tim5_to_8((uint8_t)((c >> 5) & 0x1F));
        int pb = tim5_to_8((uint8_t)((c >> 10) & 0x1F));
        long dr = (long)rgba[0] - pr;
        long dg = (long)rgba[1] - pg;
        long db = (long)rgba[2] - pb;
        unsigned long dist = (unsigned long)(dr * dr * 3L + dg * dg * 6L + db * db * 2L);
        if (dist < best_dist) {
            best_dist = dist;
            best = i;
        }
    }
    return (uint8_t)best;
}

static int map_rgba_to_palette(const uint8_t *rgba, int width, int height, const uint16_t *palette, int palette_count, uint8_t *indices) {
    size_t pixels = (size_t)width * (size_t)height;
    if (palette_count <= 0 || palette_count > 256) return -1;
    for (size_t i = 0; i < pixels; ++i) {
        indices[i] = fixed_palette_index(rgba + i * 4, palette, palette_count);
    }
    return 0;
}

static void report_fail(const wchar_t *src, const wchar_t *dst, const wchar_t *stage, int rc) {
    fwprintf(stderr, L"%ls -> %ls failed at %ls (%d)\n", src, dst, stage, rc);
}

static int convert_png_to_tim(const wchar_t *png_path, const wchar_t *tim_path, const TimMeta *meta, int use_ref_palette) {
    uint8_t *rgba = NULL;
    TimImage img;
    int w = 0, h = 0;
    int rc = png_read_rgba_file_w(png_path, &rgba, &w, &h);
    tim_image_init(&img);
    if (rc) return rc;
    if (meta && meta->mode == TIM_MODE_4BPP) {
        uint16_t pal[256];
        uint8_t *idx = (uint8_t *)malloc((size_t)w * (size_t)h);
        int pal_count = 0;
        int map_count = 0;
        if (!idx) {
            free(rgba);
            return -1;
        }
        if (use_ref_palette && meta->palette_count > 0) {
            pal_count = meta->palette_count;
            memcpy(pal, meta->palette, (size_t)pal_count * sizeof(uint16_t));
            map_count = pal_count > 16 ? 16 : pal_count;
            rc = map_rgba_to_palette(rgba, w, h, pal, map_count, idx);
        } else {
            rc = quantize_rgba_to_palette(rgba, w, h, 16, pal, idx, &pal_count);
        }
        if (!rc) {
            rc = tim_from_rgba(rgba, w, h, TIM_MODE_4BPP, meta->image_x, meta->image_y, meta->clut_x, meta->clut_y, pal, pal_count, idx, &img);
            if (!rc) {
                img.clut_w = meta->clut_w;
                img.clut_h = meta->clut_h;
                if (use_ref_palette && meta->palette_count > 0) img.palette_count = meta->palette_count;
            }
        }
        free(idx);
    } else if (meta && meta->mode == TIM_MODE_8BPP) {
        uint16_t pal[256];
        uint8_t *idx = (uint8_t *)malloc((size_t)w * (size_t)h);
        int pal_count = 0;
        if (!idx) {
            free(rgba);
            return -1;
        }
        if (use_ref_palette && meta->palette_count > 0) {
            pal_count = meta->palette_count;
            memcpy(pal, meta->palette, (size_t)pal_count * sizeof(uint16_t));
            rc = map_rgba_to_palette(rgba, w, h, pal, pal_count, idx);
        } else {
            rc = quantize_rgba_to_palette(rgba, w, h, 256, pal, idx, &pal_count);
        }
        if (!rc) {
            rc = tim_from_rgba(rgba, w, h, TIM_MODE_8BPP, meta->image_x, meta->image_y, meta->clut_x, meta->clut_y, pal, pal_count, idx, &img);
            if (!rc) {
                img.clut_w = meta->clut_w;
                img.clut_h = meta->clut_h;
                if (use_ref_palette && meta->palette_count > 0) img.palette_count = meta->palette_count;
            }
        }
        free(idx);
    } else {
        rc = tim_from_rgba(rgba, w, h, TIM_MODE_16BPP, meta ? meta->image_x : 0, meta ? meta->image_y : 0, 0, 0, NULL, 0, NULL, &img);
    }
    if (!rc) {
        wprintf(L"%ls -> %ls\n", png_path, tim_path);
        rc = tim_write_file_w(tim_path, &img);
    }
    tim_image_free(&img);
    free(rgba);
    return rc;
}

static void append_meta(TimMetaList *list, const wchar_t *stem, const TimImage *img) {
    TimMeta *tmp = (TimMeta *)realloc(list->items, (list->count + 1) * sizeof(TimMeta));
    if (!tmp) return;
    list->items = tmp;
    memset(&list->items[list->count], 0, sizeof(TimMeta));
    list->items[list->count].stem = _wcsdup(stem);
    list->items[list->count].mode = img->mode;
    list->items[list->count].image_x = img->image_x;
    list->items[list->count].image_y = img->image_y;
    list->items[list->count].clut_x = img->clut_x;
    list->items[list->count].clut_y = img->clut_y;
    list->items[list->count].clut_w = img->clut_w;
    list->items[list->count].clut_h = img->clut_h;
    list->items[list->count].palette_count = img->palette_count;
    if (img->palette_count > 0 && img->palette_count <= 256) {
        memcpy(list->items[list->count].palette, img->palette, (size_t)img->palette_count * sizeof(uint16_t));
    }
    list->count++;
}

int main(int argc, char **argv) {
    int wargc = 0;
    wchar_t **wargv = CommandLineToArgvW(GetCommandLineW(), &wargc);
    TimMetaList meta_list;
    FileList files = {0};
    int rc = 0;
    int argi = 1;
    int use_ref_palette = 0;
    (void)argc;
    (void)argv;
    if (!wargv) return 1;
    if (png_runtime_init() != 0) {
        LocalFree(wargv);
        return 1;
    }
    memset(&meta_list, 0, sizeof(meta_list));

    if (argi < wargc && !_wcsicmp(wargv[argi], L"-r")) {
        use_ref_palette = 1;
        argi++;
    }

    if (wargc - argi < 2) {
        wprintf(L"Usage:\n  tim i <tim-file>\n  tim d <tim-folder> <png-folder>\n  tim e <png-folder> <tim-folder>\n  tim -r e <png-folder> <tim-folder>\n  tim e -r <png-folder> <tim-folder>\n");
        goto done;
    }

    if (!_wcsicmp(wargv[argi], L"i")) {
        rc = inspect_tim(wargv[argi + 1]);
        goto done;
    }

    if (wargc - argi < 3) {
        rc = 1;
        goto done;
    }

    if (!_wcsicmp(wargv[argi], L"d")) {
        wchar_t xml_path[MAX_PATH * 4];
        ensure_dir_w(wargv[argi + 2]);
        scan_recursive(wargv[argi + 1], L".tim", &files);
        for (size_t i = 0; i < files.count; ++i) {
            TimImage img;
            wchar_t rel[MAX_PATH * 4], out_rel[MAX_PATH * 4], out_path[MAX_PATH * 4];
            if (tim_read_file_w(files.items[i], &img) != 0) continue;
            path_make_relative_no_ext_w(rel, MAX_PATH * 4, wargv[argi + 1], files.items[i]);
            path_change_ext_w(out_rel, MAX_PATH * 4, rel, L".png");
            path_join_w(out_path, MAX_PATH * 4, wargv[argi + 2], out_rel);
            ensure_parent_dir_w(out_path);
            rc = convert_tim_to_png(files.items[i], out_path);
            if (rc) report_fail(files.items[i], out_path, L"decode", rc);
            append_meta(&meta_list, rel, &img);
            tim_image_free(&img);
        }
        path_join_w(xml_path, MAX_PATH * 4, wargv[argi + 2], L"list.xml");
        tim_meta_save_w(xml_path, &meta_list);
    } else if (!_wcsicmp(wargv[argi], L"e")) {
        wchar_t xml_path[MAX_PATH * 4];
        int path_off = 0;
        if (argi + 1 < wargc && !_wcsicmp(wargv[argi + 1], L"-r")) {
            use_ref_palette = 1;
            path_off = 1;
        }
        ensure_dir_w(wargv[argi + 2 + path_off]);
        path_join_w(xml_path, MAX_PATH * 4, wargv[argi + 1 + path_off], L"list.xml");
        tim_meta_load_w(xml_path, &meta_list);
        for (size_t i = 0; i < meta_list.count; ++i) {
            wchar_t png_path[MAX_PATH * 4], tim_path[MAX_PATH * 4];
            const TimMeta *meta = &meta_list.items[i];
            path_join_stem_ext_w(png_path, MAX_PATH * 4, wargv[argi + 1 + path_off], meta->stem, L".png");
            path_join_stem_ext_w(tim_path, MAX_PATH * 4, wargv[argi + 2 + path_off], meta->stem, L".tim");
            ensure_parent_dir_w(tim_path);
            rc = convert_png_to_tim(png_path, tim_path, meta, use_ref_palette);
            if (rc) report_fail(png_path, tim_path, L"encode", rc);
        }
    } else {
        rc = 1;
    }

done:
    filelist_free(&files);
    tim_meta_free(&meta_list);
    LocalFree(wargv);
    png_runtime_shutdown();
    return rc ? 1 : 0;
}
