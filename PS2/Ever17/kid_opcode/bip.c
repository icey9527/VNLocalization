#include "bip.h"

#include "opcode_decode.h"
#include "opcode_render.h"
#include "bip_build.h"

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int write_script_output_files(const char *output_dir, const char *name, const ScriptOutput *out) {
    char asm_name[260];
    char txt_name[260];
    char asm_path[512];
    char txt_path[512];

    if (snprintf(asm_name, sizeof(asm_name), "%s.asm", name) <= 0) {
        return 0;
    }
    if (snprintf(txt_name, sizeof(txt_name), "%s.txt", name) <= 0) {
        return 0;
    }
    if (!join_path(asm_path, sizeof(asm_path), output_dir, asm_name)) {
        return 0;
    }
    if (!join_path(txt_path, sizeof(txt_path), output_dir, txt_name)) {
        return 0;
    }
    if (!text_buffer_write_utf8(asm_path, &out->asm_lines)) {
        return 0;
    }
    if (out->txt_lines.count == 0) {
        remove(txt_path);
        return 1;
    }
    return text_buffer_write_utf8(txt_path, &out->txt_lines);
}

static int should_skip_table_like_script(const char *name) {
    return strcmp(name, "SHORTCUT01") == 0 || strcmp(name, "SHORTCUT02") == 0;
}

static int write_report_file(const ReportState *report_state) {
    remove("report.txt");
    if (!report_has_entries(report_state)) {
        return 1;
    }
    return report_write("report.txt", report_state);
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

static void free_text_file_lines_local(char **lines, size_t count) {
    size_t i;
    if (!lines) {
        return;
    }
    for (i = 0; i < count; ++i) {
        free(lines[i]);
    }
    free(lines);
}

static int parse_hex_byte_token(const char *text, uint8_t *out_value) {
    unsigned int value;
    if (sscanf(text, "%2x", &value) != 1 || value > 0xFFU) {
        return 0;
    }
    *out_value = (uint8_t)value;
    return 1;
}

static int parse_hex_u16_token(const char *text, uint16_t *out_value) {
    unsigned int value;
    if (sscanf(text, "0x%4x", &value) != 1 || value > 0xFFFFU) {
        return 0;
    }
    *out_value = (uint16_t)value;
    return 1;
}

static int append_ref_index(uint32_t **refs, size_t *count, size_t *capacity, uint32_t value) {
    if (*count == *capacity) {
        size_t new_capacity = *capacity ? (*capacity * 2) : 8;
        uint32_t *new_refs = (uint32_t *)realloc(*refs, new_capacity * sizeof(uint32_t));
        if (!new_refs) {
            return 0;
        }
        *refs = new_refs;
        *capacity = new_capacity;
    }
    (*refs)[(*count)++] = value;
    return 1;
}

static int collect_line_refs(const char *line, uint32_t **out_refs, size_t *out_count) {
    const char *cursor = line;
    uint32_t *refs = NULL;
    size_t count = 0;
    size_t capacity = 0;

    *out_refs = NULL;
    *out_count = 0;
    while ((cursor = strchr(cursor, '@')) != NULL) {
        unsigned int ref_value;
        if (sscanf(cursor + 1, "%u", &ref_value) == 1 && ref_value != 0) {
            if (!append_ref_index(&refs, &count, &capacity, (uint32_t)(ref_value - 1))) {
                free(refs);
                return 0;
            }
        }
        ++cursor;
    }
    *out_refs = refs;
    *out_count = count;
    return 1;
}

static void write_u16le(uint8_t *data, size_t off, uint16_t value) {
    data[off] = (uint8_t)(value & 0xFFU);
    data[off + 1] = (uint8_t)((value >> 8) & 0xFFU);
}

static uint16_t read_u16le_local(const uint8_t *data, size_t off) {
    return (uint16_t)(data[off] | (data[off + 1] << 8));
}

static int ensure_buffer_size(uint8_t **buffer, size_t *buffer_size, size_t needed_size) {
    if (needed_size <= *buffer_size) {
        return 1;
    }
    {
        uint8_t *new_buffer = (uint8_t *)realloc(*buffer, needed_size);
        if (!new_buffer) {
            return 0;
        }
        memset(new_buffer + *buffer_size, 0, needed_size - *buffer_size);
        *buffer = new_buffer;
        *buffer_size = needed_size;
    }
    return 1;
}

static int patch_text_offsets_from_asm(
    char **lines,
    size_t line_count,
    uint8_t **buffer,
    size_t *buffer_size,
    const BipTextPool *pool) {
    size_t i;
    uint32_t text_base = 0xFFFFFFFFU;

    if (pool->count == 0) {
        return 1;
    }

    for (i = 0; i < line_count; ++i) {
        char *line = lines[i];
        unsigned int addr;
        int consumed;
        uint8_t opcode;
        uint32_t *refs = NULL;
        size_t ref_count = 0;
        size_t j;

        if (!line[0]) {
            continue;
        }
        if (sscanf(line, "%x%n", &addr, &consumed) != 1) {
            continue;
        }
        if ((size_t)addr >= *buffer_size) {
            continue;
        }
        opcode = (*buffer)[addr];
        if (!collect_line_refs(line, &refs, &ref_count)) {
            return 0;
        }
        if (ref_count == 0) {
            free(refs);
            continue;
        }

        switch (opcode) {
            case 0x1F:
            case 0x7A:
                if ((size_t)addr + 3 < *buffer_size) {
                    uint16_t old_off = read_u16le_local(*buffer, (size_t)addr + 2);
                    if (old_off < text_base) text_base = old_off;
                }
                break;
            case 0x74:
                if ((size_t)addr + 5 < *buffer_size) {
                    uint16_t old_off = read_u16le_local(*buffer, (size_t)addr + 4);
                    if (old_off < text_base) text_base = old_off;
                }
                break;
            case 0x25:
                for (j = 0; j < ref_count; ++j) {
                    size_t off = (size_t)addr + 4 + j * 8;
                    if (off + 1 < *buffer_size) {
                        uint16_t old_off = read_u16le_local(*buffer, off);
                        if (old_off < text_base) text_base = old_off;
                    }
                }
                break;
            case 0x75:
                for (j = 0; j < ref_count; ++j) {
                    size_t off = (size_t)addr + 6 + j * 8;
                    if (off + 1 < *buffer_size) {
                        uint16_t old_off = read_u16le_local(*buffer, off);
                        if (old_off < text_base) text_base = old_off;
                    }
                }
                break;
            case 0x5C:
            case 0x5D:
            case 0x5E:
            case 0x70:
            case 0x7D:
            case 0x7E:
            case 0x7F:
                if ((size_t)addr + 3 < *buffer_size) {
                    uint16_t old_off = read_u16le_local(*buffer, (size_t)addr + 2);
                    if (old_off < text_base) text_base = old_off;
                }
                break;
            default:
                break;
        }
        free(refs);
    }

    if (text_base == 0xFFFFFFFFU) {
        return 1;
    }

    if (!ensure_buffer_size(buffer, buffer_size, (size_t)text_base + pool->total_size)) {
        return 0;
    }
    memset(*buffer + text_base, 0, pool->total_size);
    for (i = 0; i < pool->count; ++i) {
        memcpy(*buffer + text_base + pool->offsets[i], pool->encoded_lines[i], pool->encoded_sizes[i]);
        (*buffer)[text_base + pool->offsets[i] + pool->encoded_sizes[i]] = 0;
    }

    for (i = 0; i < line_count; ++i) {
        char *line = lines[i];
        unsigned int addr;
        int consumed;
        uint8_t opcode;
        uint32_t *refs = NULL;
        size_t ref_count = 0;
        size_t j;

        if (!line[0]) {
            continue;
        }
        if (sscanf(line, "%x%n", &addr, &consumed) != 1) {
            continue;
        }
        if ((size_t)addr >= *buffer_size) {
            continue;
        }
        opcode = (*buffer)[addr];
        if (!collect_line_refs(line, &refs, &ref_count)) {
            return 0;
        }
        if (ref_count == 0) {
            free(refs);
            continue;
        }

        switch (opcode) {
            case 0x1F:
            case 0x7A:
                if (refs[0] < pool->count) {
                    write_u16le(*buffer, (size_t)addr + 2, (uint16_t)(text_base + pool->offsets[refs[0]]));
                }
                break;
            case 0x74:
                if (refs[0] < pool->count) {
                    write_u16le(*buffer, (size_t)addr + 4, (uint16_t)(text_base + pool->offsets[refs[0]]));
                }
                break;
            case 0x25:
                for (j = 0; j < ref_count; ++j) {
                    if (refs[j] < pool->count) {
                        write_u16le(*buffer, (size_t)addr + 4 + j * 8, (uint16_t)(text_base + pool->offsets[refs[j]]));
                    }
                }
                break;
            case 0x75:
                for (j = 0; j < ref_count; ++j) {
                    if (refs[j] < pool->count) {
                        write_u16le(*buffer, (size_t)addr + 6 + j * 8, (uint16_t)(text_base + pool->offsets[refs[j]]));
                    }
                }
                break;
            case 0x5C:
            case 0x5D:
            case 0x5E:
            case 0x70:
            case 0x7D:
            case 0x7E:
            case 0x7F:
                if (refs[0] < pool->count) {
                    write_u16le(*buffer, (size_t)addr + 2, (uint16_t)(text_base + pool->offsets[refs[0]]));
                }
                break;
            default:
                break;
        }
        free(refs);
    }

    return 1;
}

int rebuild_bip_file_with_entry(
    const char *asm_path,
    const char *txt_path,
    const char *out_path,
    const InitScriptEntry *entry) {
    char **lines = NULL;
    size_t line_count = 0;
    uint8_t *buffer = NULL;
    size_t buffer_size = 0;
    BipTextPool pool;
    size_t i;

    bip_text_pool_init(&pool);
    if (!split_text_file_lines_local(asm_path, &lines, &line_count)) {
        return 0;
    }
    if (!bip_text_pool_load_optional(txt_path, &pool)) {
        free_text_file_lines_local(lines, line_count);
        return 0;
    }

    for (i = 0; i < line_count; ++i) {
        char *line = lines[i];
        char *cursor = line;
        unsigned int addr;
        int consumed;
        size_t offset;
        char opcode_name[64];
        if (!line[0]) {
            continue;
        }
        if (sscanf(cursor, "%x%n", &addr, &consumed) != 1) {
            fprintf(stderr, "rebuild parse failed: %s line %u\n", asm_path, (unsigned)(i + 1));
            free_text_file_lines_local(lines, line_count);
            free(buffer);
            return 0;
        }
        offset = (size_t)addr;
        cursor += consumed;
        while (*cursor == ' ') {
            ++cursor;
        }
        while (isxdigit((unsigned char)cursor[0]) && isxdigit((unsigned char)cursor[1])) {
            uint8_t value;
            if (!parse_hex_byte_token(cursor, &value)) {
                break;
            }
            if (offset >= buffer_size) {
                size_t new_size = offset + 1;
                uint8_t *new_buffer = (uint8_t *)realloc(buffer, new_size);
                if (!new_buffer) {
                    fprintf(stderr, "rebuild alloc failed: %s line %u\n", asm_path, (unsigned)(i + 1));
                    free_text_file_lines_local(lines, line_count);
                    free(buffer);
                    return 0;
                }
                memset(new_buffer + buffer_size, 0, new_size - buffer_size);
                buffer = new_buffer;
                buffer_size = new_size;
            }
            buffer[offset++] = value;
            cursor += 2;
            while (*cursor == ' ') {
                ++cursor;
            }
        }

        if (sscanf(cursor, "%63s", opcode_name) == 1 && strcmp(opcode_name, "table_u16") == 0) {
            char *value_cursor = cursor;
            while (*value_cursor && *value_cursor != ' ') {
                ++value_cursor;
            }
            while (*value_cursor == ' ') {
                ++value_cursor;
            }
            while (*value_cursor) {
                uint16_t value;
                char token[16];
                size_t token_len = 0;

                while (value_cursor[token_len] && value_cursor[token_len] != ' ') {
                    ++token_len;
                }
                if (token_len == 0 || token_len >= sizeof(token)) {
                    break;
                }
                memcpy(token, value_cursor, token_len);
                token[token_len] = '\0';

                if (!parse_hex_u16_token(token, &value)) {
                    break;
                }
                if (offset + 1 >= buffer_size) {
                    size_t new_size = offset + 2;
                    uint8_t *new_buffer = (uint8_t *)realloc(buffer, new_size);
                    if (!new_buffer) {
                        fprintf(stderr, "rebuild alloc failed: %s line %u\n", asm_path, (unsigned)(i + 1));
                        free_text_file_lines_local(lines, line_count);
                        free(buffer);
                        return 0;
                    }
                    memset(new_buffer + buffer_size, 0, new_size - buffer_size);
                    buffer = new_buffer;
                    buffer_size = new_size;
                }
                write_u16le(buffer, offset, value);
                offset += 2;

                value_cursor += token_len;
                while (*value_cursor == ' ') {
                    ++value_cursor;
                }
            }
        }
    }

    if (pool.count != 0) {
        if (!bip_text_pool_encode(&pool, "badchars.txt")) {
            free_text_file_lines_local(lines, line_count);
            free(buffer);
            bip_text_pool_free(&pool);
            return 0;
        }
        if (!patch_text_offsets_from_asm(lines, line_count, &buffer, &buffer_size, &pool)) {
            free_text_file_lines_local(lines, line_count);
            free(buffer);
            bip_text_pool_free(&pool);
            return 0;
        }
    }

    free_text_file_lines_local(lines, line_count);
    if (entry) {
        size_t tail_off = buffer_size;
        if (!ensure_buffer_size(&buffer, &buffer_size, tail_off + 12)) {
            free_text_file_lines_local(lines, line_count);
            free(buffer);
            bip_text_pool_free(&pool);
            return 0;
        }
        buffer[tail_off + 0] = (uint8_t)(entry->dialog_offset & 0xFFU);
        buffer[tail_off + 1] = (uint8_t)((entry->dialog_offset >> 8) & 0xFFU);
        buffer[tail_off + 2] = (uint8_t)((entry->dialog_offset >> 16) & 0xFFU);
        buffer[tail_off + 3] = (uint8_t)((entry->dialog_offset >> 24) & 0xFFU);
        buffer[tail_off + 4] = (uint8_t)(entry->choice_offset & 0xFFU);
        buffer[tail_off + 5] = (uint8_t)((entry->choice_offset >> 8) & 0xFFU);
        buffer[tail_off + 6] = (uint8_t)((entry->choice_offset >> 16) & 0xFFU);
        buffer[tail_off + 7] = (uint8_t)((entry->choice_offset >> 24) & 0xFFU);
        buffer[tail_off + 8] = (uint8_t)(entry->padding_value & 0xFFU);
        buffer[tail_off + 9] = (uint8_t)((entry->padding_value >> 8) & 0xFFU);
        buffer[tail_off + 10] = (uint8_t)((entry->padding_value >> 16) & 0xFFU);
        buffer[tail_off + 11] = (uint8_t)((entry->padding_value >> 24) & 0xFFU);
        buffer_size = tail_off + 12;
    }

    if (!write_binary_file(out_path, buffer, buffer_size)) {
        fprintf(stderr, "rebuild write failed: %s\n", out_path);
        free(buffer);
        bip_text_pool_free(&pool);
        return 0;
    }
    free(buffer);
    bip_text_pool_free(&pool);
    return 1;
}

static int disasm_bip_file(const uint8_t *data, size_t size, const OpcodeTable *opcode_table, ScriptOutput *out, ReportState *report_state) {
    DecodeContext ctx;

    ctx.data = data;
    ctx.size = size;
    ctx.cursor = 0;
    ctx.table = opcode_table;
    ctx.report = report_state;

    while (ctx.cursor < ctx.size) {
        DecodedInsn insn;
        if (!decode_instruction(&ctx, &insn)) {
            return 0;
        }
        if (insn.opcode == 0x00) {
            break;
        }
        if (!render_decoded_instruction(out, &insn)) {
            return 0;
        }
        if (insn.consumed == 0) {
            return 0;
        }
        if (insn.next_address != 0) {
            size_t tail_start = ctx.cursor + insn.consumed;
            size_t data_end = insn.data_end_address ? (size_t)insn.data_end_address : (size_t)insn.next_address;
            if (data_end > tail_start && data_end <= ctx.size) {
                if (insn.opcode == 0x09 && ctx.data[ctx.cursor + 1] == 0x0F) {
                    if (!render_u16_table_line(out, (uint32_t)tail_start, ctx.data + tail_start, data_end - tail_start)) {
                        return 0;
                    }
                } else {
                    if (!render_raw_data_line(out, (uint32_t)tail_start, ctx.data + tail_start, data_end - tail_start)) {
                        return 0;
                    }
                }
            }
            ctx.cursor = insn.next_address;
        } else {
            ctx.cursor += insn.consumed;
        }
    }
    return 1;
}

int disasm_bip_batch(
    const char *input_dir,
    const char *output_dir,
    const InitBin *init,
    const FileNameSet *mac_files,
    const OpcodeTable *opcode_table,
    ReportState *report_state) {
    size_t count;
    size_t i;
    size_t generated = 0;
    char mac_dir[512];
    char out_mac_dir[512];

    if (!join_path(mac_dir, sizeof(mac_dir), input_dir, "mac")) {
        return 0;
    }
    if (!join_path(out_mac_dir, sizeof(out_mac_dir), output_dir, "mac")) {
        return 0;
    }
    if (!ensure_directory_chain(out_mac_dir)) {
        return 0;
    }

    count = initbin_get_script_entry_count(init);
    for (i = 0; i < count; ++i) {
        InitScriptEntry entry;
        char file_name[260];
        char bip_path[512];
        BinaryBlob blob;
        ScriptOutput out;

        if (!initbin_get_script_entry(init, i, &entry)) {
            continue;
        }
        if (entry.dialog_offset == 0) {
            continue;
        }
        if (!file_name_set_contains(mac_files, entry.name)) {
            continue;
        }
        if (should_skip_table_like_script(entry.name)) {
            continue;
        }
        if (snprintf(file_name, sizeof(file_name), "%s.BIP", entry.name) <= 0) {
            return 0;
        }
        if (!join_path(bip_path, sizeof(bip_path), mac_dir, file_name)) {
            return 0;
        }
        if (!read_binary_file(bip_path, &blob)) {
            fprintf(stderr, "failed to read BIP: %s\n", bip_path);
            return 0;
        }

        report_set_script(report_state, entry.name);
        script_output_init(&out);
        if (!disasm_bip_file(blob.data, blob.size, opcode_table, &out, report_state)) {
            script_output_free(&out);
            binary_blob_free(&blob);
            fprintf(stderr, "failed to disasm BIP: %s\n", entry.name);
            return 0;
        }
        if (!write_script_output_files(out_mac_dir, entry.name, &out)) {
            script_output_free(&out);
            binary_blob_free(&blob);
            fprintf(stderr, "failed to write script outputs: %s\n", entry.name);
            return 0;
        }

        script_output_free(&out);
        binary_blob_free(&blob);
        generated += 1;
    }

    if (!write_report_file(report_state)) {
        fprintf(stderr, "failed to write report.txt\n");
        return 0;
    }
    fprintf(stdout, "generated %u script outputs\n", (unsigned)generated);
    return 1;
}

int rebuild_bip_batch(
    const char *input_dir,
    const char *output_dir,
    const InitBin *init,
    const FileNameSet *mac_files) {
    size_t count;
    size_t i;
    size_t generated = 0;

    (void)mac_files;

    count = initbin_get_script_entry_count(init);
    for (i = 0; i < count; ++i) {
        InitScriptEntry entry;
        char asm_name[260];
        char txt_name[260];
        char bip_name[260];
        char asm_path[512];
        char txt_path[512];
        char bip_path[512];

        if (!initbin_get_script_entry(init, i, &entry)) {
            continue;
        }
        if (entry.dialog_offset == 0) {
            continue;
        }
        if (should_skip_table_like_script(entry.name)) {
            continue;
        }
        if (snprintf(asm_name, sizeof(asm_name), "%s.asm", entry.name) <= 0) {
            return 0;
        }
        if (snprintf(txt_name, sizeof(txt_name), "%s.txt", entry.name) <= 0) {
            return 0;
        }
        if (snprintf(bip_name, sizeof(bip_name), "%s.BIP", entry.name) <= 0) {
            return 0;
        }
        if (!join_path(asm_path, sizeof(asm_path), input_dir, "mac")) {
            return 0;
        }
        if (!join_path(asm_path, sizeof(asm_path), asm_path, asm_name)) {
            return 0;
        }
        if (!join_path(txt_path, sizeof(txt_path), input_dir, "mac")) {
            return 0;
        }
        if (!join_path(txt_path, sizeof(txt_path), txt_path, txt_name)) {
            return 0;
        }
        if (!join_path(bip_path, sizeof(bip_path), output_dir, bip_name)) {
            return 0;
        }
        if (!rebuild_bip_file_with_entry(asm_path, txt_path, bip_path, &entry)) {
            fprintf(stderr, "failed to rebuild BIP: %s\n", entry.name);
            return 0;
        }
        generated += 1;
    }

    fprintf(stdout, "rebuilt %u script binaries\n", (unsigned)generated);
    return 1;
}
