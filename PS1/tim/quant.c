#include "quant.h"

#include <stdlib.h>
#include <string.h>

typedef struct QEntry {
    uint16_t color;
    uint8_t r, g, b;
    unsigned count;
} QEntry;

typedef struct QBox {
    int first;
    int count;
    uint8_t rmin, rmax, gmin, gmax, bmin, bmax;
    unsigned long weight;
    unsigned long sum_r;
    unsigned long sum_g;
    unsigned long sum_b;
} QBox;

static uint8_t to5(uint8_t v) {
    return (uint8_t)((v * 31u + 127u) / 255u);
}

static void tim16_to_rgb5(uint16_t c, uint8_t *rgb) {
    rgb[0] = (uint8_t)(c & 0x1F);
    rgb[1] = (uint8_t)((c >> 5) & 0x1F);
    rgb[2] = (uint8_t)((c >> 10) & 0x1F);
}

static unsigned long dist2_rgb5(const uint8_t *p, const QEntry *c) {
    long dr = (long)p[0] - (long)c->r;
    long dg = (long)p[1] - (long)c->g;
    long db = (long)p[2] - (long)c->b;
    return (unsigned long)(dr * dr * 3L + dg * dg * 6L + db * db * 2L);
}

static void box_update(QBox *box, const QEntry *entries) {
    int i;
    uint8_t rmin = 31, gmin = 31, bmin = 31, rmax = 0, gmax = 0, bmax = 0;
    unsigned long weight = 0, sum_r = 0, sum_g = 0, sum_b = 0;
    for (i = 0; i < box->count; ++i) {
        const QEntry *c = &entries[box->first + i];
        if (c->r < rmin) rmin = c->r;
        if (c->g < gmin) gmin = c->g;
        if (c->b < bmin) bmin = c->b;
        if (c->r > rmax) rmax = c->r;
        if (c->g > gmax) gmax = c->g;
        if (c->b > bmax) bmax = c->b;
        weight += c->count;
        sum_r += (unsigned long)c->r * c->count;
        sum_g += (unsigned long)c->g * c->count;
        sum_b += (unsigned long)c->b * c->count;
    }
    box->rmin = rmin;
    box->rmax = rmax;
    box->gmin = gmin;
    box->gmax = gmax;
    box->bmin = bmin;
    box->bmax = bmax;
    box->weight = weight;
    box->sum_r = sum_r;
    box->sum_g = sum_g;
    box->sum_b = sum_b;
}

static unsigned long box_variance(const QBox *box, const QEntry *entries) {
    unsigned long mean_r, mean_g, mean_b;
    unsigned long var_r = 0, var_g = 0, var_b = 0;
    int i;
    if (!box->weight) return 0;
    mean_r = box->sum_r / box->weight;
    mean_g = box->sum_g / box->weight;
    mean_b = box->sum_b / box->weight;
    for (i = 0; i < box->count; ++i) {
        const QEntry *c = &entries[box->first + i];
        long dr = (long)c->r - (long)mean_r;
        long dg = (long)c->g - (long)mean_g;
        long db = (long)c->b - (long)mean_b;
        var_r += (unsigned long)(dr * dr) * c->count;
        var_g += (unsigned long)(dg * dg) * c->count;
        var_b += (unsigned long)(db * db) * c->count;
    }
    if (var_r >= var_g && var_r >= var_b) return var_r;
    if (var_g >= var_r && var_g >= var_b) return var_g;
    return var_b;
}

static int box_axis(const QBox *box) {
    int rr = (int)box->rmax - (int)box->rmin;
    int rg = (int)box->gmax - (int)box->gmin;
    int rb = (int)box->bmax - (int)box->bmin;
    if (rr >= rg && rr >= rb) return 0;
    if (rg >= rr && rg >= rb) return 1;
    return 2;
}

static int color_cmp_r(const void *a, const void *b) {
    const QEntry *x = (const QEntry *)a, *y = (const QEntry *)b;
    if (x->r != y->r) return (int)x->r - (int)y->r;
    if (x->g != y->g) return (int)x->g - (int)y->g;
    return (int)x->b - (int)y->b;
}

static int color_cmp_g(const void *a, const void *b) {
    const QEntry *x = (const QEntry *)a, *y = (const QEntry *)b;
    if (x->g != y->g) return (int)x->g - (int)y->g;
    if (x->r != y->r) return (int)x->r - (int)y->r;
    return (int)x->b - (int)y->b;
}

static int color_cmp_b(const void *a, const void *b) {
    const QEntry *x = (const QEntry *)a, *y = (const QEntry *)b;
    if (x->b != y->b) return (int)x->b - (int)y->b;
    if (x->g != y->g) return (int)x->g - (int)y->g;
    return (int)x->r - (int)y->r;
}

static int build_histogram(const uint8_t *rgba, int width, int height, unsigned long *hist, int *has_transparent) {
    size_t pixels = (size_t)width * (size_t)height;
    size_t i;
    *has_transparent = 0;
    for (i = 0; i < pixels; ++i) {
        const uint8_t *p = rgba + i * 4;
        if (p[3] < 128) {
            *has_transparent = 1;
            continue;
        }
        hist[(to5(p[2]) << 10) | (to5(p[1]) << 5) | to5(p[0])]++;
    }
    return 0;
}

static int build_entries(const unsigned long *hist, QEntry *entries, int max_entries) {
    int count = 0;
    for (int c = 0; c < 32768; ++c) {
        if (!hist[c]) continue;
        if (count >= max_entries) return -1;
        entries[count].color = (uint16_t)c;
        tim16_to_rgb5((uint16_t)c, &entries[count].r);
        entries[count].count = (unsigned)hist[c];
        count++;
    }
    return count;
}

int quantize_rgba_to_palette(const uint8_t *rgba, int width, int height, int max_colors, uint16_t *palette_out, uint8_t *indices_out, int *palette_count_out) {
    unsigned long *hist = NULL;
    QEntry *entries = NULL;
    QBox *boxes = NULL;
    QEntry *palette_entries = NULL;
    int has_transparent = 0;
    int opaque_limit;
    int entry_count;
    int box_count = 0;
    size_t pixels = (size_t)width * (size_t)height;
    size_t i;
    if (max_colors <= 0 || max_colors > 256) return -1;
    hist = (unsigned long *)calloc(32768, sizeof(unsigned long));
    if (!hist) return -1;
    build_histogram(rgba, width, height, hist, &has_transparent);

    opaque_limit = max_colors - (has_transparent ? 1 : 0);

    entries = (QEntry *)malloc((size_t)32768 * sizeof(QEntry));
    if (!entries) {
        free(hist);
        return -1;
    }
    entry_count = build_entries(hist, entries, 32768);
    if (entry_count < 0) {
        free(entries);
        free(hist);
        return -1;
    }
    if (opaque_limit <= 0 && entry_count > 0) {
        free(entries);
        free(hist);
        return -1;
    }

    if (entry_count <= opaque_limit) {
        int out_count = 0;
        unsigned char map[32768];
        memset(map, 0xFF, sizeof(map));
        if (has_transparent) {
            palette_out[out_count++] = 0x0000;
        }
        for (i = 0; i < (size_t)entry_count; ++i) {
            uint16_t c = entries[i].color;
            unsigned char idx = (unsigned char)(has_transparent ? (1 + (int)i) : (int)i);
            palette_out[out_count] = (uint16_t)(0x8000 | c);
            map[c] = idx;
            out_count++;
        }
        *palette_count_out = out_count;
        for (i = 0; i < pixels; ++i) {
            const uint8_t *p = rgba + i * 4;
            if (p[3] < 128) {
                indices_out[i] = 0;
            } else {
                uint16_t c = (uint16_t)((to5(p[2]) << 10) | (to5(p[1]) << 5) | to5(p[0]));
                unsigned char idx = map[c];
                if (idx == 0xFF) idx = has_transparent ? 1 : 0;
                indices_out[i] = idx;
            }
        }
        free(entries);
        free(hist);
        return 0;
    }

    palette_entries = (QEntry *)malloc((size_t)entry_count * sizeof(QEntry));
    boxes = (QBox *)calloc((size_t)opaque_limit, sizeof(QBox));
    if (!palette_entries || !boxes) {
        free(palette_entries);
        free(boxes);
        free(entries);
        free(hist);
        return -1;
    }
    memcpy(palette_entries, entries, (size_t)entry_count * sizeof(QEntry));
    box_count = 1;
    boxes[0].first = 0;
    boxes[0].count = entry_count;
    box_update(&boxes[0], palette_entries);

    while (box_count < opaque_limit) {
        int best_i = -1;
        int best_axis = -1;
        unsigned long best_score = 0;
        for (int i2 = 0; i2 < box_count; ++i2) {
            unsigned long score;
            if (boxes[i2].count <= 1) continue;
            score = box_variance(&boxes[i2], palette_entries);
            if (score > best_score) {
                best_score = score;
                best_i = i2;
                best_axis = box_axis(&boxes[i2]);
            }
        }
        if (best_i < 0) break;
        if (best_axis == 0) qsort(palette_entries + boxes[best_i].first, (size_t)boxes[best_i].count, sizeof(QEntry), color_cmp_r);
        else if (best_axis == 1) qsort(palette_entries + boxes[best_i].first, (size_t)boxes[best_i].count, sizeof(QEntry), color_cmp_g);
        else qsort(palette_entries + boxes[best_i].first, (size_t)boxes[best_i].count, sizeof(QEntry), color_cmp_b);
        {
            int half = boxes[best_i].count / 2;
            QBox nb;
            if (half <= 0 || half >= boxes[best_i].count) break;
            nb.first = boxes[best_i].first + half;
            nb.count = boxes[best_i].count - half;
            boxes[best_i].count = half;
            box_update(&boxes[best_i], palette_entries);
            box_update(&nb, palette_entries);
            boxes[box_count++] = nb;
        }
    }

    {
        int out_count = 0;
        if (has_transparent) palette_out[out_count++] = 0x0000;
        for (int bi = 0; bi < box_count; ++bi) {
            unsigned long sum_r = 0, sum_g = 0, sum_b = 0, weight = 0;
            int j;
            for (j = 0; j < boxes[bi].count; ++j) {
                const QEntry *c = &palette_entries[boxes[bi].first + j];
                weight += c->count;
                sum_r += (unsigned long)c->r * c->count;
                sum_g += (unsigned long)c->g * c->count;
                sum_b += (unsigned long)c->b * c->count;
            }
            if (!weight) {
                palette_out[out_count++] = 0x8000;
            } else {
                uint8_t r = (uint8_t)((sum_r + (weight / 2)) / weight);
                uint8_t g = (uint8_t)((sum_g + (weight / 2)) / weight);
                uint8_t b = (uint8_t)((sum_b + (weight / 2)) / weight);
                palette_out[out_count++] = (uint16_t)(0x8000 | (b << 10) | (g << 5) | r);
            }
        }
        *palette_count_out = out_count;
    }

    for (i = 0; i < pixels; ++i) {
        const uint8_t *p = rgba + i * 4;
        if (p[3] < 128 && has_transparent) {
            indices_out[i] = 0;
        } else {
            uint8_t c[3] = {to5(p[2]), to5(p[1]), to5(p[0])};
            int best = has_transparent ? 1 : 0;
            unsigned long best_dist = ~0UL;
            for (int bi = 0; bi < box_count; ++bi) {
                QEntry pe;
                uint8_t pal_rgb[3];
                uint16_t pal = palette_out[has_transparent ? (bi + 1) : bi];
                tim16_to_rgb5(pal, pal_rgb);
                pe.r = pal_rgb[0];
                pe.g = pal_rgb[1];
                pe.b = pal_rgb[2];
                {
                    unsigned long d = dist2_rgb5(c, &pe);
                    if (d < best_dist) {
                        best_dist = d;
                        best = has_transparent ? (bi + 1) : bi;
                    }
                }
            }
            indices_out[i] = (uint8_t)best;
        }
    }

    free(palette_entries);
    free(boxes);
    free(entries);
    free(hist);
    return 0;
}
