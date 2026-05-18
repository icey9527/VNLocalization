#ifndef E17_OPCODE_RENDER_H
#define E17_OPCODE_RENDER_H

#include "cp932.h"
#include "opcode_decode.h"

typedef struct ScriptOutput {
    TextBuffer asm_lines;
    TextBuffer txt_lines;
} ScriptOutput;

typedef struct ScriptInsn {
    DecodedInsn decoded;
} ScriptInsn;

typedef struct ScriptInsnList {
    ScriptInsn *items;
    size_t count;
    size_t capacity;
} ScriptInsnList;

void script_output_init(ScriptOutput *out);
void script_output_free(ScriptOutput *out);
void script_insn_list_init(ScriptInsnList *list);
void script_insn_list_free(ScriptInsnList *list);
int script_insn_list_append(ScriptInsnList *list, const DecodedInsn *insn);
int render_decoded_instruction(ScriptOutput *out, const DecodedInsn *insn);
int render_raw_data_line(ScriptOutput *out, uint32_t address, const uint8_t *data, size_t size);
int render_u16_table_line(ScriptOutput *out, uint32_t address, const uint8_t *data, size_t size);

#endif
