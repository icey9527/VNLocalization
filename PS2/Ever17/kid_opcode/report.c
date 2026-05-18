#include "report.h"

#include <stdio.h>
#include <string.h>

void report_state_init(ReportState *state) {
    text_buffer_init(&state->lines);
    state->current_script[0] = '\0';
}

void report_state_free(ReportState *state) {
    text_buffer_free(&state->lines);
    state->current_script[0] = '\0';
}

void report_set_script(ReportState *state, const char *script_name) {
    snprintf(state->current_script, sizeof(state->current_script), "%s", script_name ? script_name : "");
}

int report_note_unknown_opcode(ReportState *state, uint32_t address, uint8_t opcode) {
    char line[256];
    snprintf(
        line,
        sizeof(line),
        "[%s] %06X unknown opcode %02X",
        state->current_script[0] ? state->current_script : "<no-script>",
        (unsigned)address,
        (unsigned)opcode);
    return text_buffer_append_copy(&state->lines, line);
}

int report_write(const char *path, const ReportState *state) {
    return text_buffer_write_utf8(path, &state->lines);
}

int report_has_entries(const ReportState *state) {
    return state->lines.count != 0;
}
