#ifndef SWEET_T2_H
#define SWEET_T2_H
#include <stdint.h>
#include <stddef.h>
int t2_export(const uint8_t *data, size_t size, const char *png_path, int *x, int *y);
uint8_t *t2_import(const char *png_path, int x, int y, size_t *size);
#endif
