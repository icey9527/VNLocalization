#ifndef SWEET_PNG_H
#define SWEET_PNG_H
#include <stddef.h>
#include <stdint.h>
typedef struct {
    unsigned w, h;
    uint8_t *pixels;
    uint8_t palette[1024], original_alpha[256];
    int indexed, has_original_alpha;
} PngImage;
int png_write(const char *path, const PngImage *image);
int png_read(const char *path, PngImage *image);
#endif
