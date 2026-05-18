#ifndef E17_REPORT_H
#define E17_REPORT_H

#include "cp932.h"

#include <stdint.h>

typedef struct ReportState {
    TextBuffer lines;
    char current_script[128];
} ReportState;

void report_state_init(ReportState *state);
void report_state_free(ReportState *state);
void report_set_script(ReportState *state, const char *script_name);
int report_note_unknown_opcode(ReportState *state, uint32_t address, uint8_t opcode);
int report_write(const char *path, const ReportState *state);
int report_has_entries(const ReportState *state);

#endif
