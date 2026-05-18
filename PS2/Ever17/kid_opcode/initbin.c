#include "initbin.h"

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct TableSpec {
    uint32_t header_index;
    const char *label;
    int is_string_table;
    int is_script_name_table;
    int is_u16_pointer_table;
    int uses_txt_refs;
} TableSpec;

typedef struct BlockSpec {
    uint32_t header_index;
    const char *label;
} BlockSpec;

static const TableSpec k_table_specs[] = {
    {2, "str_tbl_02", 1, 0, 0, 1},
    {3, "str_tbl_03", 1, 0, 0, 1},
    {4, "str_tbl_04", 1, 0, 0, 1},
    {5, "str_tbl_05", 1, 0, 0, 1},
    {6, "str_tbl_06", 1, 0, 0, 1},
    {7, "str_tbl_07", 1, 0, 0, 1},
    {8, "script_tbl", 1, 1, 0, 0},
    {9, "bg_tbl", 1, 0, 0, 0},
    {10, "ev_tbl", 1, 0, 0, 0},
    {11, "chr_tbl", 1, 0, 0, 0},
    {12, "bgm_tbl", 1, 0, 0, 0},
    {13, "se_tbl", 1, 0, 0, 0},
    {14, "empty_tbl", 1, 0, 0, 0},
    {15, "str_tbl_15", 1, 0, 0, 0},
    {19, "u16_tbl_19", 0, 0, 1, 0}
};

static const BlockSpec k_block_specs[] = {
    {16, "block_16_u16_values"},
    {17, "block_17_raw"},
    {18, "block_18_raw"},
    {20, "block_20_byte_classes"},
    {21, "block_21_u16_pairs"}
};

static uint32_t read_u32le(const uint8_t *data, size_t offset) {
    return (uint32_t)data[offset]
        | ((uint32_t)data[offset + 1] << 8)
        | ((uint32_t)data[offset + 2] << 16)
        | ((uint32_t)data[offset + 3] << 24);
}

static uint16_t read_u16le(const uint8_t *data, size_t offset) {
    return (uint16_t)(data[offset] | (data[offset + 1] << 8));
}

static int write_plain_hex_lines(TextBuffer *tbl, const uint8_t *data, uint32_t size, uint32_t row_size);
static int write_u16_lines(TextBuffer *tbl, const uint8_t *data, uint32_t size);

static int append_format(TextBuffer *buffer, const char *fmt, ...) {
    char stack[1024];
    char *heap;
    int written;
    va_list args;

    va_start(args, fmt);
    written = vsnprintf(stack, sizeof(stack), fmt, args);
    va_end(args);
    if (written < 0) {
        return 0;
    }
    if ((size_t)written < sizeof(stack)) {
        return text_buffer_append_copy(buffer, stack);
    }

    heap = (char *)malloc((size_t)written + 1);
    if (!heap) {
        return 0;
    }
    va_start(args, fmt);
    vsnprintf(heap, (size_t)written + 1, fmt, args);
    va_end(args);
    return text_buffer_append_owned(buffer, heap);
}

static int append_string_ref(InitBin *init, uint32_t table_index, uint32_t item_index, uint32_t offset, const char *text) {
    InitStringRef *new_refs;
    char *copy;
    size_t length;

    if (init->string_count == init->string_capacity) {
        size_t new_capacity = init->string_capacity ? init->string_capacity * 2 : 128;
        new_refs = (InitStringRef *)realloc(init->strings, new_capacity * sizeof(InitStringRef));
        if (!new_refs) {
            return 0;
        }
        init->strings = new_refs;
        init->string_capacity = new_capacity;
    }

    length = strlen(text);
    copy = (char *)malloc(length + 1);
    if (!copy) {
        return 0;
    }
    memcpy(copy, text, length + 1);

    init->strings[init->string_count].table_index = table_index;
    init->strings[init->string_count].item_index = item_index;
    init->strings[init->string_count].string_offset = offset;
    init->strings[init->string_count].text = copy;
    init->strings[init->string_count].text_line_index = 0;
    init->string_count += 1;
    return 1;
}

static int decode_cp932_string(const uint8_t *data, size_t size, uint32_t offset, char **out_text) {
    size_t end = offset;

    if (offset >= size) {
        return 0;
    }
    while (end < size && data[end] != 0) {
        ++end;
    }
    if (end >= size) {
        return 0;
    }
    return cp932_bytes_to_utf8(data + offset, end - offset, out_text);
}

static int table_uses_txt_refs(uint32_t header_index) {
    return (header_index >= 2 && header_index <= 7) || header_index == 15;
}

static size_t utf8_char_length(unsigned char lead) {
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

static int append_bad_chars(TextBuffer *failed_lines, const char *text) {
    const unsigned char *cursor = (const unsigned char *)text;
    while (*cursor) {
        size_t char_len = utf8_char_length(*cursor);
        char one_char[8];
        uint8_t *encoded = NULL;
        size_t encoded_size = 0;
        if (char_len >= sizeof(one_char)) {
            return 0;
        }
        memcpy(one_char, cursor, char_len);
        one_char[char_len] = '\0';
        if (!utf8_to_cp932_bytes(one_char, &encoded, &encoded_size)) {
            if (!text_buffer_append_copy(failed_lines, one_char)) {
                return 0;
            }
        }
        free(encoded);
        cursor += char_len;
    }
    return 1;
}

static int parse_offset_table(const uint8_t *data, size_t size, const TableSpec *spec, InitOffsetTable *table) {
    uint32_t off = read_u32le(data, spec->header_index * 4);
    uint32_t count = 0;
    uint32_t pos = off;
    uint32_t *items = NULL;

    if (off >= size) {
        return 0;
    }

    while (pos + 4 <= size) {
        uint32_t value = read_u32le(data, pos);
        if (value == 0) {
            break;
        }
        pos += 4;
        count += 1;
    }

    if (count > 0) {
        uint32_t i;
        items = (uint32_t *)malloc(count * sizeof(uint32_t));
        if (!items) {
            return 0;
        }
        for (i = 0; i < count; ++i) {
            items[i] = read_u32le(data, off + i * 4);
        }
    }

    table->header_index = spec->header_index;
    table->file_offset = off;
    table->count = count;
    table->items = items;
    table->label = spec->label;
    table->is_string_table = spec->is_string_table;
    table->is_script_name_table = spec->is_script_name_table;
    table->is_u16_pointer_table = spec->is_u16_pointer_table;
    (void)spec->uses_txt_refs;
    return 1;
}

static int detect_block_size(const InitBin *init, uint32_t header_index, uint32_t *out_size) {
    size_t i;
    uint32_t start = init->header[header_index];
    uint32_t next = (uint32_t)init->size;

    for (i = 0; i < INIT_HEADER_COUNT; ++i) {
        uint32_t candidate = init->header[i];
        if (candidate > start && candidate < next) {
            next = candidate;
        }
    }

    if (next < start || next > init->size) {
        return 0;
    }
    *out_size = next - start;
    return 1;
}

void initbin_init(InitBin *init) {
    memset(init, 0, sizeof(*init));
}

void initbin_free(InitBin *init) {
    size_t i;

    for (i = 0; i < init->table_count; ++i) {
        free(init->tables[i].items);
    }
    free(init->tables);
    for (i = 0; i < init->string_count; ++i) {
        free(init->strings[i].text);
    }
    free(init->strings);
    memset(init, 0, sizeof(*init));
}

int parse_initbin(const uint8_t *data, size_t size, const FileNameSet *mac_files, InitBin *out) {
    (void)mac_files;
    size_t i;

    if (size < INIT_HEADER_COUNT * 4) {
        return 0;
    }

    initbin_init(out);
    out->data = data;
    out->size = size;

    for (i = 0; i < INIT_HEADER_COUNT; ++i) {
        out->header[i] = read_u32le(data, i * 4);
    }

    out->table_count = sizeof(k_table_specs) / sizeof(k_table_specs[0]);
    out->tables = (InitOffsetTable *)calloc(out->table_count, sizeof(InitOffsetTable));
    if (!out->tables) {
        return 0;
    }

    for (i = 0; i < out->table_count; ++i) {
        uint32_t j;
        if (!parse_offset_table(data, size, &k_table_specs[i], &out->tables[i])) {
            return 0;
        }
        if (!out->tables[i].is_string_table) {
            continue;
        }
        for (j = 0; j < out->tables[i].count; ++j) {
            char *text = NULL;
            if (!decode_cp932_string(data, size, out->tables[i].items[j], &text)) {
                return 0;
            }
            if (!append_string_ref(out, out->tables[i].header_index, j, out->tables[i].items[j], text)) {
                free(text);
                return 0;
            }
            free(text);
        }
    }

    out->block_count = sizeof(k_block_specs) / sizeof(k_block_specs[0]);
    for (i = 0; i < out->block_count; ++i) {
        out->blocks[i].header_index = k_block_specs[i].header_index;
        out->blocks[i].file_offset = out->header[k_block_specs[i].header_index];
        out->blocks[i].label = k_block_specs[i].label;
        if (!detect_block_size(out, k_block_specs[i].header_index, &out->blocks[i].size)) {
            return 0;
        }
    }

    return 1;
}

static int write_header_dump(TextBuffer *tbl, const InitBin *init) {
    size_t i;
    if (!append_format(tbl, "[header]")) {
        return 0;
    }
    for (i = 0; i < INIT_HEADER_COUNT; ++i) {
        if (!append_format(tbl, "[%02u] %06X", (unsigned)i, init->header[i])) {
            return 0;
        }
    }
    return append_format(tbl, "");
}

static int write_table_00_dump(TextBuffer *tbl, const InitBin *init) {
    uint32_t start = init->header[0];
    uint32_t size;
    uint32_t count;

    if (!detect_block_size(init, 0, &size)) {
        return 0;
    }
    count = size / 2;
    if (!append_format(tbl, "[0]%u", count)) {
        return 0;
    }
    if (!write_u16_lines(tbl, init->data + start, size)) {
        return 0;
    }
    return append_format(tbl, "");
}

static int write_table_01_dump(TextBuffer *tbl, const InitBin *init) {
    uint32_t start = init->header[1];
    uint32_t size;
    uint32_t pos;
    uint32_t count;
    uint32_t effective_size;

    if (!detect_block_size(init, 1, &size)) {
        return 0;
    }
    effective_size = size;
    count = effective_size / 12;
    if (!append_format(tbl, "[1]%u", count)) {
        return 0;
    }
    for (pos = 0; pos + 12 <= effective_size; pos += 12) {
        if (!append_format(tbl, "%06X %06X %06X",
            read_u32le(init->data, start + pos),
            read_u32le(init->data, start + pos + 4),
            read_u32le(init->data, start + pos + 8))) {
            return 0;
        }
    }
    return append_format(tbl, "");
}

static int write_table_dump(TextBuffer *tbl, TextBuffer *txt, const InitBin *init, const InitOffsetTable *table) {
    uint32_t i;

    if (!append_format(tbl, "[%u]%u",
        table->header_index,
        table->count)) {
        return 0;
    }

    for (i = 0; i < table->count; ++i) {
        uint32_t item = table->items[i];
        if (table->is_string_table) {
            size_t k;
            for (k = 0; k < init->string_count; ++k) {
                const InitStringRef *ref = &init->strings[k];
                if (ref->table_index == table->header_index && ref->item_index == i) {
                    if (table_uses_txt_refs(table->header_index)) {
                        if (!text_buffer_append_copy(txt, ref->text)) {
                            return 0;
                        }
                        if (!append_format(tbl, "@%u ; %s",
                            (unsigned)txt->count,
                            ref->text)) {
                            return 0;
                        }
                    } else {
                        if (!append_format(tbl, "%s", ref->text)) {
                            return 0;
                        }
                    }
                    break;
                }
            }
        } else if (table->is_u16_pointer_table) {
            uint32_t pos = item;
            char line[512];
            size_t cursor = 0;
            (void)i;
            while (pos + 2 <= init->size) {
                uint16_t value = read_u16le(init->data, pos);
                cursor += (size_t)snprintf(line + cursor, sizeof(line) - cursor, "%s%04X", cursor ? " " : "", value);
                pos += 2;
                if (value == 0xFFFF || cursor + 8 >= sizeof(line)) {
                    break;
                }
            }
            if (!text_buffer_append_copy(tbl, line)) {
                return 0;
            }
        } else {
            if (!append_format(tbl, "[%03u] %06X",
                        i,
                        item)) {
                return 0;
            }
        }
    }

    return append_format(tbl, "");
}

static int write_plain_hex_lines(TextBuffer *tbl, const uint8_t *data, uint32_t size, uint32_t row_size) {
    uint32_t i;
    for (i = 0; i < size; i += row_size) {
        char bytes[256];
        size_t j;
        size_t cursor = 0;
        uint32_t this_row = size - i > row_size ? row_size : size - i;
        for (j = 0; j < this_row; ++j) {
            cursor += (size_t)snprintf(bytes + cursor, sizeof(bytes) - cursor, "%s%02X", j ? " " : "", data[i + j]);
        }
        if (!append_format(tbl, "%s", bytes)) {
            return 0;
        }
    }
    return 1;
}

static int write_u16_lines(TextBuffer *tbl, const uint8_t *data, uint32_t size) {
    uint32_t i;
    for (i = 0; i + 1 < size; i += 2) {
        if (!append_format(tbl, "%04X", read_u16le(data, i))) {
            return 0;
        }
    }
    if (size & 1) {
        if (!append_format(tbl, "%02X", data[size - 1])) {
            return 0;
        }
    }
    return 1;
}

static int write_block_dump(TextBuffer *tbl, const InitBin *init, const InitBlock *block) {
    if (block->header_index == 16) {
        uint32_t count = block->size / 2;
        if (!append_format(tbl, "[%u]%u", block->header_index, count)) {
            return 0;
        }
        if (!write_u16_lines(tbl, init->data + block->file_offset, block->size)) {
            return 0;
        }
        return append_format(tbl, "");
    }
    if (block->header_index == 17 || block->header_index == 18 || block->header_index == 20) {
        if (!append_format(tbl, "[%u]%u", block->header_index, block->size)) {
            return 0;
        }
        if (!write_plain_hex_lines(tbl, init->data + block->file_offset, block->size, 16)) {
            return 0;
        }
        return append_format(tbl, "");
    }
    if (block->header_index == 21) {
        uint32_t count = block->size / 2;
        if (!append_format(tbl, "[%u]%u", block->header_index, count)) {
            return 0;
        }
        if (!write_u16_lines(tbl, init->data + block->file_offset, block->size)) {
            return 0;
        }
        return append_format(tbl, "");
    }
    return append_format(tbl, "");
}

int write_init_outputs(const char *output_dir, const InitBin *init) {
    char tbl_path[512];
    char txt_path[512];
    TextBuffer tbl;
    TextBuffer txt;
    size_t i;

    text_buffer_init(&tbl);
    text_buffer_init(&txt);

    if (!join_path(tbl_path, sizeof(tbl_path), output_dir, "init.tbl")) {
        goto fail;
    }
    if (!join_path(txt_path, sizeof(txt_path), output_dir, "init.txt")) {
        goto fail;
    }

    if (!write_header_dump(&tbl, init)) {
        goto fail;
    }
    if (!write_table_00_dump(&tbl, init)) {
        goto fail;
    }
    if (!write_table_01_dump(&tbl, init)) {
        goto fail;
    }
    for (i = 0; i < init->table_count; ++i) {
        if (init->tables[i].header_index >= 16) {
            continue;
        }
        if (!write_table_dump(&tbl, &txt, init, &init->tables[i])) {
            goto fail;
        }
    }
    for (i = 0; i < init->table_count; ++i) {
        if (init->tables[i].header_index != 19) {
            continue;
        }
        if (!write_table_dump(&tbl, &txt, init, &init->tables[i])) {
            goto fail;
        }
    }
    for (i = 0; i < init->block_count; ++i) {
        if (!write_block_dump(&tbl, init, &init->blocks[i])) {
            goto fail;
        }
    }
    for (i = 0; i < init->table_count; ++i) {
        if (init->tables[i].header_index < 16 || init->tables[i].header_index == 19) {
            continue;
        }
        if (!write_table_dump(&tbl, &txt, init, &init->tables[i])) {
            goto fail;
        }
    }

    if (!text_buffer_write_utf8(tbl_path, &tbl)) {
        goto fail;
    }
    if (!text_buffer_write_utf8(txt_path, &txt)) {
        goto fail;
    }

    text_buffer_free(&tbl);
    text_buffer_free(&txt);
    return 1;

fail:
    text_buffer_free(&tbl);
    text_buffer_free(&txt);
    return 0;
}

int write_initbin_binary(const char *path, const InitBin *init) {
    uint8_t *buffer;
    size_t i;

    buffer = (uint8_t *)malloc(init->size);
    if (!buffer) {
        return 0;
    }
    memcpy(buffer, init->data, init->size);

    for (i = 0; i < INIT_HEADER_COUNT; ++i) {
        uint32_t value = init->header[i];
        size_t off = i * 4;
        buffer[off] = (uint8_t)(value & 0xFF);
        buffer[off + 1] = (uint8_t)((value >> 8) & 0xFF);
        buffer[off + 2] = (uint8_t)((value >> 16) & 0xFF);
        buffer[off + 3] = (uint8_t)((value >> 24) & 0xFF);
    }

    if (!write_binary_file(path, buffer, init->size)) {
        free(buffer);
        return 0;
    }

    free(buffer);
    return 1;
}

typedef struct RebuildStringTable {
    uint32_t count;
    uint32_t *line_refs;
} RebuildStringTable;

typedef struct RebuildU16List {
    uint16_t *values;
    uint32_t count;
} RebuildU16List;

typedef struct RebuildModel {
    uint32_t header[INIT_HEADER_COUNT];
    uint16_t table0_values[64];
    uint32_t table0_count;
    uint32_t *table1_values;
    uint32_t table1_count;
    RebuildStringTable string_tables[16];
    RebuildU16List table19_lists[256];
    uint32_t table19_count;
    uint16_t block16_values[256];
    uint32_t block16_count;
    uint8_t *block17_bytes;
    uint32_t block17_count;
    uint8_t *block18_bytes;
    uint32_t block18_count;
    uint8_t *block20_bytes;
    uint32_t block20_count;
    uint16_t block21_values[512];
    uint32_t block21_count;
    char **txt_lines;
    uint32_t txt_count;
} RebuildModel;

static void rebuild_model_init(RebuildModel *model) {
    memset(model, 0, sizeof(*model));
}

static void rebuild_model_free(RebuildModel *model) {
    size_t i;
    free(model->table1_values);
    for (i = 0; i < 16; ++i) {
        free(model->string_tables[i].line_refs);
    }
    for (i = 0; i < 256; ++i) {
        free(model->table19_lists[i].values);
    }
    free(model->block17_bytes);
    free(model->block18_bytes);
    free(model->block20_bytes);
    if (model->txt_lines) {
        for (i = 0; i < model->txt_count; ++i) {
            free(model->txt_lines[i]);
        }
        free(model->txt_lines);
    }
    memset(model, 0, sizeof(*model));
}

static int split_text_file_lines(const char *path, char ***out_lines, uint32_t *out_count) {
    BinaryBlob blob;
    char **lines = NULL;
    uint32_t count = 0;
    uint32_t capacity = 0;
    size_t start = 0;
    size_t i;

    if (!read_binary_file(path, &blob)) {
        return 0;
    }

    for (i = 0; i <= blob.size; ++i) {
        int at_end = i == blob.size;
        int at_break = !at_end && (blob.data[i] == '\n' || blob.data[i] == '\r');
        if (!at_end && !at_break) {
            continue;
        }
        if (count == capacity) {
            uint32_t new_capacity = capacity ? capacity * 2 : 256;
            char **new_lines = (char **)realloc(lines, new_capacity * sizeof(char *));
            if (!new_lines) {
                binary_blob_free(&blob);
                return 0;
            }
            lines = new_lines;
            capacity = new_capacity;
        }
        {
            size_t end = i;
            size_t len = end - start;
            char *line = (char *)malloc(len + 1);
            if (!line) {
                binary_blob_free(&blob);
                return 0;
            }
            memcpy(line, blob.data + start, len);
            line[len] = '\0';
            lines[count++] = line;
        }
        if (!at_end && blob.data[i] == '\r' && i + 1 < blob.size && blob.data[i + 1] == '\n') {
            ++i;
        }
        start = i + 1;
    }

    binary_blob_free(&blob);
    *out_lines = lines;
    *out_count = count;
    return 1;
}

static int parse_hex_u32(const char *text, uint32_t *out_value) {
    unsigned int value;
    if (sscanf(text, "%x", &value) != 1) {
        return 0;
    }
    *out_value = (uint32_t)value;
    return 1;
}

static int parse_hex_u16(const char *text, uint16_t *out_value) {
    unsigned int value;
    if (sscanf(text, "%x", &value) != 1 || value > 0xFFFFU) {
        return 0;
    }
    *out_value = (uint16_t)value;
    return 1;
}

static int parse_hex_u8(const char *text, uint8_t *out_value) {
    unsigned int value;
    if (sscanf(text, "%x", &value) != 1 || value > 0xFFU) {
        return 0;
    }
    *out_value = (uint8_t)value;
    return 1;
}

static int parse_tbl_header_line(const char *line, uint32_t *index, uint32_t *value) {
    unsigned int idx;
    unsigned int val;
    if (sscanf(line, "[%u] %x", &idx, &val) != 2) {
        return 0;
    }
    *index = (uint32_t)idx;
    *value = (uint32_t)val;
    return 1;
}

static int parse_tbl_section_line(const char *line, uint32_t *index, uint32_t *count) {
    unsigned int idx;
    unsigned int val;
    if (sscanf(line, "[%u]%u", &idx, &val) != 2) {
        return 0;
    }
    *index = (uint32_t)idx;
    *count = (uint32_t)val;
    return 1;
}

static int is_string_table_index(uint32_t index) {
    return (index >= 2 && index <= 15 && index != 19);
}

static int append_u8(uint8_t **data, uint32_t *count, uint8_t value) {
    uint8_t *new_data = (uint8_t *)realloc(*data, (size_t)(*count + 1));
    if (!new_data) {
        return 0;
    }
    new_data[*count] = value;
    *data = new_data;
    *count += 1;
    return 1;
}

static int parse_init_tbl_and_txt(const char *tbl_path, const char *txt_path, RebuildModel *model) {
    char **tbl_lines = NULL;
    uint32_t tbl_count = 0;
    uint32_t i = 0;
    int current_section = -1;
    uint32_t remaining = 0;

    if (!split_text_file_lines(txt_path, &model->txt_lines, &model->txt_count)) {
        return 0;
    }
    if (!split_text_file_lines(tbl_path, &tbl_lines, &tbl_count)) {
        return 0;
    }

    if (tbl_count == 0 || strcmp(tbl_lines[0], "[header]") != 0) {
        goto fail;
    }
    for (i = 1; i <= INIT_HEADER_COUNT; ++i) {
        uint32_t idx;
        uint32_t value;
        if (i >= tbl_count || !parse_tbl_header_line(tbl_lines[i], &idx, &value) || idx >= INIT_HEADER_COUNT) {
            goto fail;
        }
        model->header[idx] = value;
    }

    for (i = INIT_HEADER_COUNT + 1; i < tbl_count; ++i) {
        char *line = tbl_lines[i];
        if (!line[0]) {
            current_section = -1;
            remaining = 0;
            continue;
        }
        if (line[0] == '[') {
            uint32_t idx;
            uint32_t count;
            if (!parse_tbl_section_line(line, &idx, &count)) {
                goto fail;
            }
            current_section = (int)idx;
            remaining = count;
            if (idx == 1) {
                model->table1_count = count;
                model->table1_values = (uint32_t *)calloc((size_t)count * 3, sizeof(uint32_t));
                if (!model->table1_values) {
                    goto fail;
                }
            } else if (idx == 19) {
                model->table19_count = count;
            } else if (is_string_table_index(idx)) {
                model->string_tables[idx].count = count;
                model->string_tables[idx].line_refs = (uint32_t *)calloc(count ? count : 1, sizeof(uint32_t));
                if (count && !model->string_tables[idx].line_refs) {
                    goto fail;
                }
            } else if (idx == 17 || idx == 18 || idx == 20) {
                if (idx == 17) {
                    model->block17_count = 0;
                } else if (idx == 18) {
                    model->block18_count = 0;
                } else {
                    model->block20_count = 0;
                }
            } else if (idx == 0) {
                model->table0_count = count;
            } else if (idx == 16) {
                model->block16_count = count;
            } else if (idx == 21) {
                model->block21_count = count;
            }
            continue;
        }

        if (current_section == 0) {
            if (model->table0_count == 0) {
                continue;
            }
            if (!parse_hex_u16(line, &model->table0_values[model->table0_count - remaining])) {
                goto fail;
            }
            --remaining;
        } else if (current_section == 1) {
            unsigned int a, b, c;
            size_t base = (size_t)(model->table1_count - remaining) * 3;
            if (sscanf(line, "%x %x %x", &a, &b, &c) != 3) {
                goto fail;
            }
            model->table1_values[base] = (uint32_t)a;
            model->table1_values[base + 1] = (uint32_t)b;
            model->table1_values[base + 2] = (uint32_t)c;
            --remaining;
        } else if (is_string_table_index((uint32_t)current_section)) {
            uint32_t slot = model->string_tables[current_section].count - remaining;
            if (table_uses_txt_refs((uint32_t)current_section)) {
                unsigned int ref_index;
                if (sscanf(line, "@%u", &ref_index) != 1 || ref_index == 0 || ref_index > model->txt_count) {
                    goto fail;
                }
                model->string_tables[current_section].line_refs[slot] = ref_index - 1;
            } else {
                size_t len = strlen(line);
                char *copy = (char *)malloc(len + 1);
                if (!copy) {
                    goto fail;
                }
                memcpy(copy, line, len + 1);
                {
                    char **new_lines = (char **)realloc(model->txt_lines, (size_t)(model->txt_count + 1) * sizeof(char *));
                    if (!new_lines) {
                        free(copy);
                        goto fail;
                    }
                    model->txt_lines = new_lines;
                    model->txt_lines[model->txt_count] = copy;
                    model->string_tables[current_section].line_refs[slot] = model->txt_count;
                    model->txt_count += 1;
                }
            }
            --remaining;
        } else if (current_section == 16) {
            if (!parse_hex_u16(line, &model->block16_values[model->block16_count - remaining])) {
                goto fail;
            }
            --remaining;
        } else if (current_section == 17 || current_section == 18 || current_section == 20) {
            char *cursor = line;
            while (*cursor) {
                char token[16];
                uint8_t value;
                int len = 0;
                while (*cursor == ' ') {
                    ++cursor;
                }
                while (cursor[len] && cursor[len] != ' ') {
                    token[len] = cursor[len];
                    ++len;
                }
                token[len] = '\0';
                if (len == 0) {
                    break;
                }
                if (!parse_hex_u8(token, &value)) {
                    goto fail;
                }
                if (current_section == 17) {
                    if (!append_u8(&model->block17_bytes, &model->block17_count, value)) {
                        goto fail;
                    }
                } else if (current_section == 18) {
                    if (!append_u8(&model->block18_bytes, &model->block18_count, value)) {
                        goto fail;
                    }
                } else {
                    if (!append_u8(&model->block20_bytes, &model->block20_count, value)) {
                        goto fail;
                    }
                }
                cursor += len;
            }
        } else if (current_section == 19) {
            RebuildU16List *list = &model->table19_lists[model->table19_count - remaining];
            char *cursor = line;
            while (*cursor) {
                char token[16];
                uint16_t value;
                int len = 0;
                uint16_t *new_values;
                while (*cursor == ' ') {
                    ++cursor;
                }
                while (cursor[len] && cursor[len] != ' ') {
                    token[len] = cursor[len];
                    ++len;
                }
                token[len] = '\0';
                if (len == 0) {
                    break;
                }
                if (!parse_hex_u16(token, &value)) {
                    goto fail;
                }
                new_values = (uint16_t *)realloc(list->values, (size_t)(list->count + 1) * sizeof(uint16_t));
                if (!new_values) {
                    goto fail;
                }
                list->values = new_values;
                list->values[list->count++] = value;
                cursor += len;
            }
            --remaining;
        } else if (current_section == 21) {
            if (!parse_hex_u16(line, &model->block21_values[model->block21_count - remaining])) {
                goto fail;
            }
            --remaining;
        }
    }

    for (i = 0; i < tbl_count; ++i) {
        free(tbl_lines[i]);
    }
    free(tbl_lines);
    return 1;

fail:
    if (tbl_lines) {
        for (i = 0; i < tbl_count; ++i) {
            free(tbl_lines[i]);
        }
        free(tbl_lines);
    }
    return 0;
}

static void write_u16le_value(uint8_t *buffer, uint32_t offset, uint16_t value) {
    buffer[offset] = (uint8_t)(value & 0xFF);
    buffer[offset + 1] = (uint8_t)((value >> 8) & 0xFF);
}

static void write_u32le_value(uint8_t *buffer, uint32_t offset, uint32_t value) {
    buffer[offset] = (uint8_t)(value & 0xFF);
    buffer[offset + 1] = (uint8_t)((value >> 8) & 0xFF);
    buffer[offset + 2] = (uint8_t)((value >> 16) & 0xFF);
    buffer[offset + 3] = (uint8_t)((value >> 24) & 0xFF);
}

int rebuild_initbin_from_text(const char *tbl_path, const char *txt_path, const char *out_path) {
    RebuildModel model;
    uint8_t *buffer = NULL;
    uint8_t **encoded_lines = NULL;
    size_t *encoded_sizes = NULL;
    TextBuffer failed_lines;
    const char *failed_path = "badchars.txt";
    uint32_t text_cursor;
    uint32_t table19_cursor;
    uint32_t final_size;
    uint32_t max_end;
    uint32_t i;

    rebuild_model_init(&model);
    text_buffer_init(&failed_lines);
    if (!parse_init_tbl_and_txt(tbl_path, txt_path, &model)) {
        text_buffer_free(&failed_lines);
        rebuild_model_free(&model);
        return 0;
    }

    encoded_lines = (uint8_t **)calloc(model.txt_count ? model.txt_count : 1, sizeof(uint8_t *));
    encoded_sizes = (size_t *)calloc(model.txt_count ? model.txt_count : 1, sizeof(size_t));
    if (!encoded_lines || !encoded_sizes) {
        free(encoded_lines);
        free(encoded_sizes);
        text_buffer_free(&failed_lines);
        rebuild_model_free(&model);
        return 0;
    }

    for (i = 0; i < model.txt_count; ++i) {
        if (!utf8_to_cp932_bytes(model.txt_lines[i], &encoded_lines[i], &encoded_sizes[i])) {
            if (!append_bad_chars(&failed_lines, model.txt_lines[i])) {
                goto fail;
            }
        }
    }
    if (failed_lines.count > 0) {
        if (!text_buffer_write_utf8(failed_path, &failed_lines)) {
            goto fail;
        }
        goto fail;
    }

    text_cursor = model.header[22];
    table19_cursor = model.header[19] + model.table19_count * 4 + 4;
    final_size = model.header[22];

    for (i = 0; i < 16; ++i) {
        uint32_t j;
        if (!is_string_table_index(i)) {
            continue;
        }
        for (j = 0; j < model.string_tables[i].count; ++j) {
            uint32_t ref = model.string_tables[i].line_refs[j];
            final_size += (uint32_t)encoded_sizes[ref] + 1;
        }
    }
    for (i = 0; i < model.table19_count; ++i) {
        final_size += model.table19_lists[i].count * 2;
    }
    buffer = (uint8_t *)calloc(final_size ? final_size : 1, 1);
    if (!buffer) {
        rebuild_model_free(&model);
        return 0;
    }

    for (i = 0; i < INIT_HEADER_COUNT; ++i) {
        write_u32le_value(buffer, i * 4, model.header[i]);
    }

    for (i = 0; i < model.table0_count; ++i) {
        write_u16le_value(buffer, model.header[0] + i * 2, model.table0_values[i]);
    }

    for (i = 0; i < model.table1_count; ++i) {
        write_u32le_value(buffer, model.header[1] + i * 12, model.table1_values[i * 3]);
        write_u32le_value(buffer, model.header[1] + i * 12 + 4, model.table1_values[i * 3 + 1]);
        write_u32le_value(buffer, model.header[1] + i * 12 + 8, model.table1_values[i * 3 + 2]);
    }
    if (model.header[3] >= model.header[1] + model.table1_count * 12 + 4) {
        write_u32le_value(buffer, model.header[1] + model.table1_count * 12, 0xFFFFFFFFU);
    }

    for (i = 2; i <= 15; ++i) {
        uint32_t j;
        uint32_t table_off;
        if (!is_string_table_index(i)) {
            continue;
        }
        table_off = model.header[i];
        for (j = 0; j < model.string_tables[i].count; ++j) {
            uint32_t ref = model.string_tables[i].line_refs[j];
            size_t len = encoded_sizes[ref];
            write_u32le_value(buffer, table_off + j * 4, text_cursor);
            memcpy(buffer + text_cursor, encoded_lines[ref], len);
            buffer[text_cursor + len] = 0;
            text_cursor += (uint32_t)len + 1;
        }
        write_u32le_value(buffer, table_off + model.string_tables[i].count * 4, 0);
    }

    for (i = 0; i < model.table19_count; ++i) {
        uint32_t j;
        RebuildU16List *list = &model.table19_lists[i];
        write_u32le_value(buffer, model.header[19] + i * 4, table19_cursor);
        for (j = 0; j < list->count; ++j) {
            write_u16le_value(buffer, table19_cursor + j * 2, list->values[j]);
        }
        table19_cursor += list->count * 2;
    }
    write_u32le_value(buffer, model.header[19] + model.table19_count * 4, 0);

    for (i = 0; i < model.block16_count; ++i) {
        write_u16le_value(buffer, model.header[16] + i * 2, model.block16_values[i]);
    }
    if (model.block17_count) {
        memcpy(buffer + model.header[17], model.block17_bytes, model.block17_count);
    }
    if (model.block18_count) {
        memcpy(buffer + model.header[18], model.block18_bytes, model.block18_count);
    }
    if (model.block20_count) {
        memcpy(buffer + model.header[20], model.block20_bytes, model.block20_count);
    }
    for (i = 0; i < model.block21_count; ++i) {
        write_u16le_value(buffer, model.header[21] + i * 2, model.block21_values[i]);
    }

    max_end = model.header[22];
    if (text_cursor > max_end) {
        max_end = text_cursor;
    }
    if (table19_cursor > max_end) {
        max_end = table19_cursor;
    }
    if (model.header[16] + model.block16_count * 2 > max_end) {
        max_end = model.header[16] + model.block16_count * 2;
    }
    if (model.header[17] + model.block17_count > max_end) {
        max_end = model.header[17] + model.block17_count;
    }
    if (model.header[18] + model.block18_count > max_end) {
        max_end = model.header[18] + model.block18_count;
    }
    if (model.header[20] + model.block20_count > max_end) {
        max_end = model.header[20] + model.block20_count;
    }
    if (model.header[21] + model.block21_count * 2 > max_end) {
        max_end = model.header[21] + model.block21_count * 2;
    }

    if (!write_binary_file(out_path, buffer, max_end)) {
        goto fail;
    }

    free(buffer);
    if (encoded_lines) {
        for (i = 0; i < model.txt_count; ++i) {
            free(encoded_lines[i]);
        }
    }
    free(encoded_lines);
    free(encoded_sizes);
    text_buffer_free(&failed_lines);
    rebuild_model_free(&model);
    return 1;

fail:
    free(buffer);
    if (encoded_lines) {
        for (i = 0; i < model.txt_count; ++i) {
            free(encoded_lines[i]);
        }
    }
    free(encoded_lines);
    free(encoded_sizes);
    text_buffer_free(&failed_lines);
    rebuild_model_free(&model);
    return 0;
}

size_t initbin_get_script_entry_count(const InitBin *init) {
    uint32_t size = 0;
    size_t table1_count = 0;
    size_t table8_count = 0;
    size_t i;

    if (detect_block_size(init, 1, &size)) {
        table1_count = size / 12;
    }

    for (i = 0; i < init->table_count; ++i) {
        if (init->tables[i].header_index == 8) {
            table8_count = init->tables[i].count;
        }
    }

    return table1_count < table8_count ? table1_count : table8_count;
}

int initbin_get_script_entry(const InitBin *init, size_t index, InitScriptEntry *out) {
    const InitOffsetTable *table8 = NULL;
    uint32_t start;
    uint32_t size;
    size_t count;
    size_t i;

    if (!out) {
        return 0;
    }

    count = initbin_get_script_entry_count(init);
    if (index >= count) {
        return 0;
    }

    for (i = 0; i < init->table_count; ++i) {
        if (init->tables[i].header_index == 8) {
            table8 = &init->tables[i];
            break;
        }
    }
    if (!table8) {
        return 0;
    }

    start = init->header[1];
    if (!detect_block_size(init, 1, &size)) {
        return 0;
    }
    if (index * 12 + 12 > size) {
        return 0;
    }

    out->dialog_offset = read_u32le(init->data, start + (uint32_t)index * 12);
    out->choice_offset = read_u32le(init->data, start + (uint32_t)index * 12 + 4);
    out->padding_value = read_u32le(init->data, start + (uint32_t)index * 12 + 8);
    out->name = NULL;
    out->table1_index = index;
    out->table8_index = index;

    for (i = 0; i < init->string_count; ++i) {
        const InitStringRef *ref = &init->strings[i];
        if (ref->table_index == table8->header_index && ref->item_index == index) {
            out->name = ref->text;
            break;
        }
    }

    return out->name != NULL;
}
