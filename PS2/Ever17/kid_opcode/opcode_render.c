#include "opcode_render.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int append_formatted(TextBuffer *buffer, const char *text) {
    return text_buffer_append_copy(buffer, text);
}

static int insn_list_reserve(ScriptInsnList *list, size_t needed) {
    ScriptInsn *new_items;
    size_t new_capacity;

    if (list->capacity >= needed) {
        return 1;
    }

    new_capacity = list->capacity ? list->capacity * 2 : 64;
    while (new_capacity < needed) {
        new_capacity *= 2;
    }

    new_items = (ScriptInsn *)realloc(list->items, new_capacity * sizeof(ScriptInsn));
    if (!new_items) {
        return 0;
    }

    list->items = new_items;
    list->capacity = new_capacity;
    return 1;
}

static int append_raw_bytes_text(char *out, size_t out_size, const uint8_t *data, size_t count) {
    size_t i;
    size_t cursor = 0;
    for (i = 0; i < count; ++i) {
        int written = snprintf(out + cursor, out_size - cursor, "%s%02X", i ? " " : "", data[i]);
        if (written < 0 || (size_t)written >= out_size - cursor) {
            return 0;
        }
        cursor += (size_t)written;
    }
    return 1;
}

void script_output_init(ScriptOutput *out) {
    text_buffer_init(&out->asm_lines);
    text_buffer_init(&out->txt_lines);
}

void script_output_free(ScriptOutput *out) {
    text_buffer_free(&out->asm_lines);
    text_buffer_free(&out->txt_lines);
}

void script_insn_list_init(ScriptInsnList *list) {
    list->items = NULL;
    list->count = 0;
    list->capacity = 0;
}

void script_insn_list_free(ScriptInsnList *list) {
    free(list->items);
    list->items = NULL;
    list->count = 0;
    list->capacity = 0;
}

int script_insn_list_append(ScriptInsnList *list, const DecodedInsn *insn) {
    if (!insn_list_reserve(list, list->count + 1)) {
        return 0;
    }
    list->items[list->count].decoded = *insn;
    list->count += 1;
    return 1;
}

int render_decoded_instruction(ScriptOutput *out, const DecodedInsn *insn) {
    char line[8192];
    if (insn->has_text) {
        char refs[8192];
        char comments[4096];
        size_t i;

        refs[0] = '\0';
        comments[0] = '\0';
        for (i = 0; i < insn->text_count; ++i) {
            int txt_index = (int)out->txt_lines.count + 1;
            char ref_part[32];
            if (!text_buffer_append_copy(&out->txt_lines, insn->texts[i])) {
                return 0;
            }
            snprintf(ref_part, sizeof(ref_part), "%s@%d", i ? " " : "", txt_index);
            if (strlen(refs) + strlen(ref_part) + 1 >= sizeof(refs)) {
                return 0;
            }
            strcat(refs, ref_part);
            if (i == 0) {
                snprintf(comments, sizeof(comments), "%s", insn->texts[i]);
            } else if (insn->text_count <= 16) {
                if (strlen(comments) + strlen(insn->texts[i]) + 4 >= sizeof(comments)) {
                    return 0;
                }
                strcat(comments, " | ");
                strcat(comments, insn->texts[i]);
            }
        }
        if (insn->args[0]) {
            snprintf(line, sizeof(line), "%06X %s %s %s %s ;%s", insn->address, insn->raw_bytes, insn->opcode_name, insn->args, refs, comments);
        } else {
            snprintf(line, sizeof(line), "%06X %s %s %s ;%s", insn->address, insn->raw_bytes, insn->opcode_name, refs, comments);
        }
    } else {
        if (insn->args[0]) {
            snprintf(line, sizeof(line), "%06X %s %s %s", insn->address, insn->raw_bytes, insn->opcode_name, insn->args);
        } else {
            snprintf(line, sizeof(line), "%06X %s %s", insn->address, insn->raw_bytes, insn->opcode_name);
        }
    }
    return append_formatted(&out->asm_lines, line);
}

int render_raw_data_line(ScriptOutput *out, uint32_t address, const uint8_t *data, size_t size) {
    char raw[8192];
    char line[16384];
    if (!append_raw_bytes_text(raw, sizeof(raw), data, size)) {
        return 0;
    }
    snprintf(line, sizeof(line), "%06X %s raw", address, raw);
    return append_formatted(&out->asm_lines, line);
}

int render_u16_table_line(ScriptOutput *out, uint32_t address, const uint8_t *data, size_t size) {
    char line[8192];
    size_t cursor = 0;
    size_t i;

    if ((size & 1U) != 0) {
        return render_raw_data_line(out, address, data, size);
    }

    cursor += (size_t)snprintf(line + cursor, sizeof(line) - cursor, "%06X table_u16", address);
    for (i = 0; i + 1 < size; i += 2) {
        uint16_t value = (uint16_t)(data[i] | (data[i + 1] << 8));
        int written = snprintf(line + cursor, sizeof(line) - cursor, " 0x%04X", (unsigned)value);
        if (written < 0 || (size_t)written >= sizeof(line) - cursor) {
            return 0;
        }
        cursor += (size_t)written;
    }
    return append_formatted(&out->asm_lines, line);
}
