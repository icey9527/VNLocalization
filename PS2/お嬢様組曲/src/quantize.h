#ifndef SWEET_QUANTIZE_H
#define SWEET_QUANTIZE_H
#include <stdint.h>
int image_palette(const uint8_t *rgba, unsigned w, unsigned h, uint8_t *indices, uint8_t *palette);
#endif
