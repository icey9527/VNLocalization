#ifndef E17_CP932_H
#define E17_CP932_H

#include <stddef.h>
#include <stdint.h>

typedef struct TextBuffer {
    char **lines;
    size_t count;
    size_t capacity;
} TextBuffer;

void text_buffer_init(TextBuffer *buffer);
void text_buffer_free(TextBuffer *buffer);
int text_buffer_append_owned(TextBuffer *buffer, char *line);
int text_buffer_append_copy(TextBuffer *buffer, const char *line);
int text_buffer_write_utf8(const char *path, const TextBuffer *buffer);

int cp932_bytes_to_utf8(const uint8_t *data, size_t size, char **out_text);
int utf8_to_cp932_bytes(const char *text, uint8_t **out_data, size_t *out_size);

#endif
