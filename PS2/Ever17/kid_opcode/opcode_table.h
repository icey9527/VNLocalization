#ifndef E17_OPCODE_TABLE_H
#define E17_OPCODE_TABLE_H

#include <stddef.h>
#include <stdint.h>

typedef struct OpcodeTableEntry {
    uint8_t opcode;
    uint32_t handler_addr;
    char name[32];
} OpcodeTableEntry;

typedef struct OpcodeTable {
    OpcodeTableEntry *items;
    size_t count;
} OpcodeTable;

void opcode_table_init(OpcodeTable *table);
void opcode_table_free(OpcodeTable *table);
int opcode_table_load(const char *path, OpcodeTable *out);
const OpcodeTableEntry *opcode_table_find(const OpcodeTable *table, uint8_t opcode);

#endif
