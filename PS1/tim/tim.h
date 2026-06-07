#ifndef TIM_H
#define TIM_H

#include <stddef.h>
#include <stdint.h>

typedef enum TimMode {
    TIM_MODE_4BPP = 4,
    TIM_MODE_8BPP = 8,
    TIM_MODE_16BPP = 16,
    TIM_MODE_24BPP = 24
} TimMode;

typedef struct TimImage {
    TimMode mode;
    int has_clut;
    int image_x;
    int image_y;
    int clut_x;
    int clut_y;
    int clut_w;
    int clut_h;
    int width;
    int height;
    int palette_count;
    uint16_t palette[256];
    uint8_t *data;
    size_t data_size;
} TimImage;

void tim_image_init(TimImage *img);
void tim_image_free(TimImage *img);
int tim_read_file_w(const wchar_t *path, TimImage *out);
int tim_write_file_w(const wchar_t *path, const TimImage *img);
int tim_to_rgba(const TimImage *img, uint8_t **rgba_out, int *w_out, int *h_out);
int tim_from_rgba(const uint8_t *rgba, int width, int height, TimMode mode, int image_x, int image_y, int clut_x, int clut_y, const uint16_t *palette, int palette_count, const uint8_t *indices, TimImage *out);
void tim_print_info(const TimImage *img, const wchar_t *path);

#endif
