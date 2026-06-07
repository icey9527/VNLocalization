#ifndef XML_H
#define XML_H

#include "tim.h"

typedef struct TimMeta {
    wchar_t *stem;
    TimMode mode;
    int image_x;
    int image_y;
    int clut_x;
    int clut_y;
    int clut_w;
    int clut_h;
    int palette_count;
    uint16_t palette[256];
} TimMeta;

typedef struct TimMetaList {
    TimMeta *items;
    size_t count;
} TimMetaList;

void tim_meta_free(TimMetaList *list);
int tim_meta_save_w(const wchar_t *path, const TimMetaList *list);
int tim_meta_load_w(const wchar_t *path, TimMetaList *list);

#endif
