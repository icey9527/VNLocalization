#ifndef E17_BIP_H
#define E17_BIP_H

#include "initbin.h"
#include "io.h"
#include "opcode.h"
#include "report.h"

int disasm_bip_batch(
    const char *input_dir,
    const char *output_dir,
    const InitBin *init,
    const FileNameSet *mac_files,
    const OpcodeTable *opcode_table,
    ReportState *report_state);
int rebuild_bip_batch(
    const char *input_dir,
    const char *output_dir,
    const InitBin *init,
    const FileNameSet *mac_files);
int rebuild_bip_file_with_entry(
    const char *asm_path,
    const char *txt_path,
    const char *out_path,
    const InitScriptEntry *entry);

#endif
