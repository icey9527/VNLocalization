#ifndef E17_INITBIN_H
#define E17_INITBIN_H

#include "cp932.h"
#include "io.h"

#include <stddef.h>
#include <stdint.h>

#define INIT_HEADER_COUNT 24

typedef struct InitStringRef {
    uint32_t table_index;
    uint32_t item_index;
    uint32_t string_offset;
    char *text;
    size_t text_line_index;
} InitStringRef;

typedef struct InitOffsetTable {
    uint32_t header_index;
    uint32_t file_offset;
    uint32_t count;
    uint32_t *items;
    const char *label;
    int is_string_table;
    int is_script_name_table;
    int is_u16_pointer_table;
} InitOffsetTable;

typedef struct InitBlock {
    uint32_t header_index;
    uint32_t file_offset;
    uint32_t size;
    const char *label;
} InitBlock;

typedef struct InitScriptEntry {
    const char *name;
    uint32_t dialog_offset;
    uint32_t choice_offset;
    uint32_t padding_value;
    size_t table1_index;
    size_t table8_index;
} InitScriptEntry;

typedef struct InitBin {
    const uint8_t *data;
    size_t size;
    uint32_t header[INIT_HEADER_COUNT];
    InitOffsetTable *tables;
    size_t table_count;
    InitBlock blocks[7];
    size_t block_count;
    InitStringRef *strings;
    size_t string_count;
    size_t string_capacity;
} InitBin;

void initbin_init(InitBin *init);
void initbin_free(InitBin *init);

int parse_initbin(const uint8_t *data, size_t size, const FileNameSet *mac_files, InitBin *out);
int write_init_outputs(const char *output_dir, const InitBin *init);
int write_initbin_binary(const char *path, const InitBin *init);
int rebuild_initbin_from_text(const char *tbl_path, const char *txt_path, const char *out_path);
size_t initbin_get_script_entry_count(const InitBin *init);
int initbin_get_script_entry(const InitBin *init, size_t index, InitScriptEntry *out);

#endif
