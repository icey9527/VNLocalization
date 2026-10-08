#ifndef SWEET_IO_H
#define SWEET_IO_H
#include <stdint.h>
#include <stdio.h>
uint32_t rd32(const uint8_t *p);
void wr32(uint8_t *p, uint32_t v);
void make_dir(const char *path);
uint8_t *read_file(const char *path, size_t *size);
int safe_name(const char *name);
#endif
