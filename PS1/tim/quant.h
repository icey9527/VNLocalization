#ifndef QUANT_H
#define QUANT_H

#include "tim.h"

int quantize_rgba_to_palette(const uint8_t *rgba, int width, int height, int max_colors, uint16_t *palette_out, uint8_t *indices_out, int *palette_count_out);

#endif
