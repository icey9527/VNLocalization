#ifndef PNGIO_H
#define PNGIO_H

#include "tim.h"

int png_runtime_init(void);
void png_runtime_shutdown(void);
int png_read_rgba_file_w(const wchar_t *path, uint8_t **rgba_out, int *w_out, int *h_out);
int png_write_rgba_file_w(const wchar_t *path, const uint8_t *rgba, int width, int height);

#endif
