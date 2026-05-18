#include "bip_build.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static size_t utf8_char_length_local(unsigned char lead) {
    if ((lead & 0x80) == 0x00) {
        return 1;
    }
    if ((lead & 0xE0) == 0xC0) {
        return 2;
    }
    if ((lead & 0xF0) == 0xE0) {
        return 3;
    }
    if ((lead & 0xF8) == 0xF0) {
        return 4;
    }
    return 1;
}

static int text_buffer_contains_line_local(const TextBuffer *buffer, const char *line) {
    size_t i;
    for (i = 0; i < buffer->count; ++i) {
        if (strcmp(buffer->lines[i], line) == 0) {
            return 1;
        }
    }
    return 0;
}

static int append_unencodable_chars_local(TextBuffer *failed, const char *text) {
    const unsigned char *cursor = (const unsigned char *)text;
    while (*cursor) {
        size_t char_len = utf8_char_length_local(*cursor);
        char one_char[8];
        uint8_t *encoded = NULL;
        size_t encoded_size = 0;
        if (char_len >= sizeof(one_char)) {
            char_len = 1;
        }
        memcpy(one_char, cursor, char_len);
        one_char[char_len] = '\0';
        if (!utf8_to_cp932_bytes(one_char, &encoded, &encoded_size)) {
            if (!text_buffer_contains_line_local(failed, one_char)) {
                if (!text_buffer_append_copy(failed, one_char)) {
                    free(encoded);
                    return 0;
                }
            }
        }
        free(encoded);
        cursor += char_len;
    }
    return 1;
}

static int split_text_file_lines_local(const char *path, char ***out_lines, size_t *out_count) {
    FILE *fp;
    char **lines = NULL;
    size_t count = 0;
    size_t capacity = 0;
    char line[65536];

    *out_lines = NULL;
    *out_count = 0;

    fp = fopen(path, "rb");
    if (!fp) {
        return 0;
    }
    while (fgets(line, sizeof(line), fp)) {
        size_t len = strlen(line);
        char *copy;
        if (len && line[len - 1] == '\n') {
            line[--len] = '\0';
        }
        if (len && line[len - 1] == '\r') {
            line[--len] = '\0';
        }
        copy = (char *)malloc(len + 1);
        if (!copy) {
            fclose(fp);
            return 0;
        }
        memcpy(copy, line, len + 1);
        if (count == capacity) {
            size_t new_capacity = capacity ? capacity * 2 : 64;
            char **new_lines = (char **)realloc(lines, new_capacity * sizeof(char *));
            if (!new_lines) {
                free(copy);
                fclose(fp);
                return 0;
            }
            lines = new_lines;
            capacity = new_capacity;
        }
        lines[count++] = copy;
    }
    fclose(fp);
    *out_lines = lines;
    *out_count = count;
    return 1;
}

static void free_text_lines(char **lines, size_t count) {
    size_t i;
    if (!lines) {
        return;
    }
    for (i = 0; i < count; ++i) {
        free(lines[i]);
    }
    free(lines);
}

void bip_text_pool_init(BipTextPool *pool) {
    memset(pool, 0, sizeof(*pool));
}

void bip_text_pool_free(BipTextPool *pool) {
    size_t i;
    free_text_lines(pool->lines, pool->count);
    if (pool->encoded_lines) {
        for (i = 0; i < pool->encoded_count; ++i) {
            free(pool->encoded_lines[i]);
        }
    }
    free(pool->encoded_lines);
    free(pool->encoded_sizes);
    free(pool->offsets);
    memset(pool, 0, sizeof(*pool));
}

int bip_text_pool_load_optional(const char *txt_path, BipTextPool *pool) {
    FILE *fp = fopen(txt_path, "rb");
    if (!fp) {
        pool->lines = NULL;
        pool->count = 0;
        return 1;
    }
    fclose(fp);
    return split_text_file_lines_local(txt_path, &pool->lines, &pool->count);
}

uint32_t bip_align16_u32(uint32_t value) {
    return (value + 15U) & ~15U;
}

int bip_text_pool_encode(BipTextPool *pool, const char *badchar_path) {
    TextBuffer failed;
    size_t i;
    uint32_t cursor = 0;

    text_buffer_init(&failed);
    pool->encoded_count = pool->count;
    pool->encoded_lines = (uint8_t **)calloc(pool->count ? pool->count : 1, sizeof(uint8_t *));
    pool->encoded_sizes = (size_t *)calloc(pool->count ? pool->count : 1, sizeof(size_t));
    pool->offsets = (uint32_t *)calloc(pool->count ? pool->count : 1, sizeof(uint32_t));
    if (!pool->encoded_lines || !pool->encoded_sizes || !pool->offsets) {
        text_buffer_free(&failed);
        return 0;
    }

    for (i = 0; i < pool->count; ++i) {
        if (!utf8_to_cp932_bytes(pool->lines[i], &pool->encoded_lines[i], &pool->encoded_sizes[i])) {
            if (!append_unencodable_chars_local(&failed, pool->lines[i])) {
                text_buffer_free(&failed);
                return 0;
            }
        }
    }
    if (failed.count != 0) {
        text_buffer_write_utf8(badchar_path, &failed);
        text_buffer_free(&failed);
        return 0;
    }
    text_buffer_free(&failed);

    for (i = 0; i < pool->count; ++i) {
        pool->offsets[i] = cursor;
        cursor += (uint32_t)pool->encoded_sizes[i] + 1U;
    }
    pool->total_size = (size_t)cursor;
    return 1;
}
