#ifndef E17_OPCODE_DECODE_H
#define E17_OPCODE_DECODE_H

#include "opcode_table.h"
#include "report.h"

#include <stddef.h>
#include <stdint.h>

typedef struct DecodeContext {
    const uint8_t *data;
    size_t size;
    size_t cursor;
    const OpcodeTable *table;
    ReportState *report;
} DecodeContext;

typedef struct DecodedInsn {
    uint32_t address;
    uint8_t opcode;
    uint32_t next_address;
    uint32_t data_end_address;
    char opcode_name[32];
    char raw_bytes[8192];
    char args[256];
    size_t consumed;
    int has_text;
    size_t text_count;
    char texts[256][512];
    int known;
} DecodedInsn;

int decode_instruction(DecodeContext *ctx, DecodedInsn *out);

#endif
