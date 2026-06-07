#include "xml.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "util.h"

static void append_utf8(char **buf, size_t *size, size_t *cap, const char *s) {
    size_t n = strlen(s);
    if (*size + n + 1 > *cap) {
        size_t nc = *cap ? *cap : 256;
        while (nc < *size + n + 1) nc *= 2;
        *buf = (char *)realloc(*buf, nc);
        *cap = nc;
    }
    memcpy(*buf + *size, s, n);
    *size += n;
    (*buf)[*size] = 0;
}

static const char *find_attr(const char *tag, const char *name) {
    static char pattern[64];
    snprintf(pattern, sizeof(pattern), "%s=\"", name);
    return strstr(tag, pattern);
}

static char *dup_attr(const char *tag, const char *name) {
    const char *p = find_attr(tag, name);
    const char *e;
    char *out;
    size_t n;
    if (!p) return NULL;
    p += strlen(name) + 2;
    e = strchr(p, '"');
    if (!e) return NULL;
    n = (size_t)(e - p);
    out = (char *)malloc(n + 1);
    if (!out) return NULL;
    memcpy(out, p, n);
    out[n] = 0;
    return out;
}

static void append_palette_attr(char *out, size_t cap, const TimMeta *item) {
    size_t len;
    int i;
    if (item->palette_count <= 0) return;
    len = strlen(out);
    if (len + 12 >= cap) return;
    strncat(out, " palette=\"", cap - strlen(out) - 1);
    for (i = 0; i < item->palette_count; ++i) {
        char tmp[8];
        _snprintf(tmp, sizeof(tmp), "%04X", item->palette[i]);
        if (strlen(out) + strlen(tmp) + 2 >= cap) break;
        strncat(out, tmp, cap - strlen(out) - 1);
        if (i + 1 < item->palette_count) strncat(out, ",", cap - strlen(out) - 1);
    }
    strncat(out, "\"", cap - strlen(out) - 1);
}

static int parse_mode(const char *s) {
    if (!strcmp(s, "4bpp")) return TIM_MODE_4BPP;
    if (!strcmp(s, "8bpp")) return TIM_MODE_8BPP;
    if (!strcmp(s, "16bpp")) return TIM_MODE_16BPP;
    if (!strcmp(s, "24bpp")) return TIM_MODE_24BPP;
    return 0;
}

void tim_meta_free(TimMetaList *list) {
    for (size_t i = 0; i < list->count; ++i) free(list->items[i].stem);
    free(list->items);
    memset(list, 0, sizeof(*list));
}

int tim_meta_save_w(const wchar_t *path, const TimMetaList *list) {
    char *buf = NULL;
    size_t size = 0, cap = 0;
    append_utf8(&buf, &size, &cap, "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n<timlist>\n");
    for (size_t i = 0; i < list->count; ++i) {
        char *stem = utf8_from_wide(list->items[i].stem);
        char line[4096];
        line[0] = 0;
        snprintf(line, sizeof(line),
                 "  <image stem=\"%s\" mode=\"%s\" image_x=\"%d\" image_y=\"%d\" clut_x=\"%d\" clut_y=\"%d\" clut_w=\"%d\" clut_h=\"%d\"",
                 stem ? stem : "",
                 list->items[i].mode == TIM_MODE_4BPP ? "4bpp" :
                 list->items[i].mode == TIM_MODE_8BPP ? "8bpp" :
                 list->items[i].mode == TIM_MODE_16BPP ? "16bpp" : "24bpp",
                 list->items[i].image_x, list->items[i].image_y,
                 list->items[i].clut_x, list->items[i].clut_y,
                 list->items[i].clut_w, list->items[i].clut_h);
        append_palette_attr(line, sizeof(line), &list->items[i]);
        strncat(line, " />\n", sizeof(line) - strlen(line) - 1);
        append_utf8(&buf, &size, &cap, line);
        free(stem);
    }
    append_utf8(&buf, &size, &cap, "</timlist>\n");
    if (write_file_w(path, (const uint8_t *)buf, size) != 0) {
        free(buf);
        return -1;
    }
    free(buf);
    return 0;
}

int tim_meta_load_w(const wchar_t *path, TimMetaList *list) {
    uint8_t *buf = NULL;
    size_t size = 0;
    char *text, *p;
    if (read_file_w(path, &buf, &size) != 0) return -1;
    text = (char *)malloc(size + 1);
    if (!text) {
        free(buf);
        return -1;
    }
    memcpy(text, buf, size);
    text[size] = 0;
    free(buf);
    memset(list, 0, sizeof(*list));
    p = text;
    while ((p = strstr(p, "<image")) != NULL) {
        char *end = strchr(p, '>');
        char *stem_s = dup_attr(p, "stem");
        char *mode_s = dup_attr(p, "mode");
        char *ix_s = dup_attr(p, "image_x");
        char *iy_s = dup_attr(p, "image_y");
        char *cx_s = dup_attr(p, "clut_x");
        char *cy_s = dup_attr(p, "clut_y");
        char *cw_s = dup_attr(p, "clut_w");
        char *ch_s = dup_attr(p, "clut_h");
        char *pal_s = dup_attr(p, "palette");
        if (stem_s && mode_s && end) {
            TimMeta item;
            memset(&item, 0, sizeof(item));
            item.stem = wide_from_utf8(stem_s);
            item.mode = parse_mode(mode_s);
            item.image_x = ix_s ? atoi(ix_s) : 0;
            item.image_y = iy_s ? atoi(iy_s) : 0;
            item.clut_x = cx_s ? atoi(cx_s) : 0;
            item.clut_y = cy_s ? atoi(cy_s) : 0;
            item.clut_w = cw_s ? atoi(cw_s) : 0;
            item.clut_h = ch_s ? atoi(ch_s) : 0;
            if (pal_s) {
                char *tok = pal_s;
                while (*tok && item.palette_count < 256) {
                    char *next = strchr(tok, ',');
                    if (next) *next = 0;
                    item.palette[item.palette_count++] = (uint16_t)strtoul(tok, NULL, 16);
                    if (!next) break;
                    tok = next + 1;
                }
            }
            list->items = (TimMeta *)realloc(list->items, (list->count + 1) * sizeof(TimMeta));
            list->items[list->count++] = item;
        }
        free(stem_s);
        free(mode_s);
        free(ix_s);
        free(iy_s);
        free(cx_s);
        free(cy_s);
        free(cw_s);
        free(ch_s);
        free(pal_s);
        p = end ? end + 1 : p + 6;
    }
    free(text);
    return 0;
}
