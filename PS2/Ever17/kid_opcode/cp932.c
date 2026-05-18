#include "cp932.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>

static int text_buffer_reserve(TextBuffer *buffer, size_t needed) {
    char **new_lines;
    size_t new_capacity;

    if (buffer->capacity >= needed) {
        return 1;
    }

    new_capacity = buffer->capacity ? buffer->capacity * 2 : 32;
    while (new_capacity < needed) {
        new_capacity *= 2;
    }

    new_lines = (char **)realloc(buffer->lines, new_capacity * sizeof(char *));
    if (!new_lines) {
        return 0;
    }

    buffer->lines = new_lines;
    buffer->capacity = new_capacity;
    return 1;
}

void text_buffer_init(TextBuffer *buffer) {
    buffer->lines = NULL;
    buffer->count = 0;
    buffer->capacity = 0;
}

void text_buffer_free(TextBuffer *buffer) {
    size_t i;

    for (i = 0; i < buffer->count; ++i) {
        free(buffer->lines[i]);
    }
    free(buffer->lines);
    buffer->lines = NULL;
    buffer->count = 0;
    buffer->capacity = 0;
}

int text_buffer_append_owned(TextBuffer *buffer, char *line) {
    if (!text_buffer_reserve(buffer, buffer->count + 1)) {
        return 0;
    }
    buffer->lines[buffer->count++] = line;
    return 1;
}

int text_buffer_append_copy(TextBuffer *buffer, const char *line) {
    size_t length;
    char *copy;

    length = strlen(line);
    copy = (char *)malloc(length + 1);
    if (!copy) {
        return 0;
    }
    memcpy(copy, line, length + 1);
    return text_buffer_append_owned(buffer, copy);
}

int text_buffer_write_utf8(const char *path, const TextBuffer *buffer) {
    FILE *fp;
    size_t i;

    fp = fopen(path, "wb");
    if (!fp) {
        return 0;
    }

    for (i = 0; i < buffer->count; ++i) {
        if (fwrite(buffer->lines[i], 1, strlen(buffer->lines[i]), fp) != strlen(buffer->lines[i])) {
            fclose(fp);
            return 0;
        }
        if (fwrite("\r\n", 1, 2, fp) != 2) {
            fclose(fp);
            return 0;
        }
    }

    fclose(fp);
    return 1;
}

int cp932_bytes_to_utf8(const uint8_t *data, size_t size, char **out_text) {
    int wide_len;
    int utf8_len;
    wchar_t *wide_text;
    char *utf8_text;

    *out_text = NULL;
    wide_len = MultiByteToWideChar(932, MB_ERR_INVALID_CHARS, (const char *)data, (int)size, NULL, 0);
    if (wide_len <= 0) {
        return 0;
    }

    wide_text = (wchar_t *)malloc((size_t)(wide_len + 1) * sizeof(wchar_t));
    if (!wide_text) {
        return 0;
    }
    if (MultiByteToWideChar(932, MB_ERR_INVALID_CHARS, (const char *)data, (int)size, wide_text, wide_len) != wide_len) {
        free(wide_text);
        return 0;
    }
    wide_text[wide_len] = L'\0';

    utf8_len = WideCharToMultiByte(CP_UTF8, 0, wide_text, wide_len, NULL, 0, NULL, NULL);
    if (utf8_len <= 0) {
        free(wide_text);
        return 0;
    }

    utf8_text = (char *)malloc((size_t)utf8_len + 1);
    if (!utf8_text) {
        free(wide_text);
        return 0;
    }
    if (WideCharToMultiByte(CP_UTF8, 0, wide_text, wide_len, utf8_text, utf8_len, NULL, NULL) != utf8_len) {
        free(utf8_text);
        free(wide_text);
        return 0;
    }
    utf8_text[utf8_len] = '\0';
    free(wide_text);
    *out_text = utf8_text;
    return 1;
}

int utf8_to_cp932_bytes(const char *text, uint8_t **out_data, size_t *out_size) {
    int wide_len;
    int cp932_len;
    wchar_t *wide_text;
    char *cp932_text;
    BOOL used_default = FALSE;

    *out_data = NULL;
    *out_size = 0;

    wide_len = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, text, -1, NULL, 0);
    if (wide_len <= 0) {
        return 0;
    }

    wide_text = (wchar_t *)malloc((size_t)wide_len * sizeof(wchar_t));
    if (!wide_text) {
        return 0;
    }
    if (MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, text, -1, wide_text, wide_len) != wide_len) {
        free(wide_text);
        return 0;
    }

    cp932_len = WideCharToMultiByte(932, WC_NO_BEST_FIT_CHARS, wide_text, -1, NULL, 0, NULL, &used_default);
    if (cp932_len <= 0 || used_default) {
        free(wide_text);
        return 0;
    }

    cp932_text = (char *)malloc((size_t)cp932_len);
    if (!cp932_text) {
        free(wide_text);
        return 0;
    }
    used_default = FALSE;
    if (WideCharToMultiByte(932, WC_NO_BEST_FIT_CHARS, wide_text, -1, cp932_text, cp932_len, NULL, &used_default) != cp932_len || used_default) {
        free(cp932_text);
        free(wide_text);
        return 0;
    }

    free(wide_text);
    *out_data = (uint8_t *)cp932_text;
    *out_size = (size_t)(cp932_len - 1);
    return 1;
}
