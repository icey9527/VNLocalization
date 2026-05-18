#ifndef E17_BIP_BUILD_H
#define E17_BIP_BUILD_H

#include "cp932.h"

#include <stddef.h>
#include <stdint.h>

typedef struct BipTextRef {
    uint32_t line_index;
    uint32_t string_offset;
} BipTextRef;

typedef struct BipTextPool {
    char **lines;
    size_t count;
    uint8_t **encoded_lines;
    size_t *encoded_sizes;
    uint32_t *offsets;
    size_t encoded_count;
    size_t total_size;
} BipTextPool;

void bip_text_pool_init(BipTextPool *pool);
void bip_text_pool_free(BipTextPool *pool);
int bip_text_pool_load_optional(const char *txt_path, BipTextPool *pool);
int bip_text_pool_encode(BipTextPool *pool, const char *badchar_path);
uint32_t bip_align16_u32(uint32_t value);

#endif
