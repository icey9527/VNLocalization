#include "opcode_table.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int reserve_entries(OpcodeTable *table, size_t needed) {
    OpcodeTableEntry *items;
    size_t capacity;

    if (table->count >= needed) {
        return 1;
    }

    capacity = table->count ? table->count * 2 : 128;
    while (capacity < needed) {
        capacity *= 2;
    }

    items = (OpcodeTableEntry *)realloc(table->items, capacity * sizeof(OpcodeTableEntry));
    if (!items) {
        return 0;
    }
    table->items = items;
    return 1;
}

void opcode_table_init(OpcodeTable *table) {
    table->items = NULL;
    table->count = 0;
}

void opcode_table_free(OpcodeTable *table) {
    free(table->items);
    table->items = NULL;
    table->count = 0;
}

const OpcodeTableEntry *opcode_table_find(const OpcodeTable *table, uint8_t opcode) {
    size_t i;
    for (i = 0; i < table->count; ++i) {
        if (table->items[i].opcode == opcode) {
            return &table->items[i];
        }
    }
    return NULL;
}

int opcode_table_load(const char *path, OpcodeTable *out) {
    FILE *fp;
    char line[256];

    opcode_table_init(out);
    fp = fopen(path, "rb");
    if (!fp) {
        return 0;
    }

    while (fgets(line, sizeof(line), fp)) {
        unsigned int opcode;
        unsigned int addr;
        char name[32];
        if (sscanf(line, "%x %x %31s", &opcode, &addr, name) != 3) {
            continue;
        }
        if (!reserve_entries(out, out->count + 1)) {
            fclose(fp);
            opcode_table_free(out);
            return 0;
        }
        out->items[out->count].opcode = (uint8_t)opcode;
        out->items[out->count].handler_addr = (uint32_t)addr;
        snprintf(out->items[out->count].name, sizeof(out->items[out->count].name), "%s", name);
        out->count += 1;
    }

    fclose(fp);
    return 1;
}
