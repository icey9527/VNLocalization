#include "opcode_decode.h"

#include "opcode_handlers_core.h"
#include "opcode_handlers_text.h"
#include "opcode_table.h"

#include <stdio.h>
#include <string.h>

static int append_raw_bytes(char *out, size_t out_size, const uint8_t *data, size_t count) {
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

int decode_instruction(DecodeContext *ctx, DecodedInsn *out) {
    const OpcodeTableEntry *entry;
    size_t raw_count;

    memset(out, 0, sizeof(*out));
    if (ctx->cursor >= ctx->size) {
        return 0;
    }

    out->address = (uint32_t)ctx->cursor;
    out->opcode = ctx->data[ctx->cursor];
    out->next_address = 0;
    out->data_end_address = 0;
    out->known = 0;
    out->has_text = 0;
    out->text_count = 0;

    if (!decode_text_opcode(ctx, out) && !decode_core_opcode(ctx, out)) {
        entry = opcode_table_find(ctx->table, out->opcode);
        snprintf(out->opcode_name, sizeof(out->opcode_name), "op_%02X", out->opcode);
        if (entry) {
            snprintf(out->opcode_name, sizeof(out->opcode_name), "%s", entry->name);
        }
        out->consumed = (ctx->size - ctx->cursor) >= 2 ? 2 : (ctx->size - ctx->cursor);
        out->args[0] = '\0';
        if (ctx->report && !report_note_unknown_opcode(ctx->report, out->address, out->opcode)) {
            return 0;
        }
    }

    raw_count = out->consumed;
    if (!append_raw_bytes(out->raw_bytes, sizeof(out->raw_bytes), ctx->data + ctx->cursor, raw_count)) {
        return 0;
    }
    return 1;
}
