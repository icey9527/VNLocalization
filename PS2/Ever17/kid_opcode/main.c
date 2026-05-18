#include "bip.h"
#include "initbin.h"
#include "io.h"
#include "opcode.h"
#include "report.h"

#include <stdio.h>
#include <string.h>

static void print_usage(void) {
    fprintf(stderr, "usage: tool.exe d <input_dir> <output_dir>\n");
    fprintf(stderr, "       tool.exe e <input_dir> <output_dir>\n");
    fprintf(stderr, "\n");
    fprintf(stderr, "input layout:\n");
    fprintf(stderr, "  input_dir/\n");
    fprintf(stderr, "  |- init.bin        (for d)\n");
    fprintf(stderr, "  |- init.tbl        (for e)\n");
    fprintf(stderr, "  |- init.txt        (for e)\n");
    fprintf(stderr, "  `- mac/\n");
    fprintf(stderr, "     |- *.BIP        (for d)\n");
    fprintf(stderr, "     |- *.asm        (for e)\n");
    fprintf(stderr, "     `- *.txt        (for e, optional if script has no text)\n");
    fprintf(stderr, "\n");
    fprintf(stderr, "output layout:\n");
    fprintf(stderr, "  output_dir/\n");
    fprintf(stderr, "  |- init.bin / init.tbl / init.txt\n");
    fprintf(stderr, "  `- mac/\n");
    fprintf(stderr, "     |- *.BIP\n");
    fprintf(stderr, "     |- *.asm\n");
    fprintf(stderr, "     `- *.txt\n");
}

static int run_decode(const char *input_dir, const char *output_dir) {
    char init_path[512];
    char mac_path[512];
    BinaryBlob init_blob;
    FileNameSet mac_files;
    InitBin init;
    OpcodeTable opcode_table;
    ReportState report_state;

    opcode_table_init(&opcode_table);
    report_state_init(&report_state);

    if (!join_path(init_path, sizeof(init_path), input_dir, "init.bin")) {
        fprintf(stderr, "input init.bin path too long\n");
        report_state_free(&report_state);
        return 0;
    }
    if (!join_path(mac_path, sizeof(mac_path), input_dir, "mac")) {
        fprintf(stderr, "input mac path too long\n");
        report_state_free(&report_state);
        return 0;
    }
    if (!ensure_directory_chain(output_dir)) {
        fprintf(stderr, "failed to create output directory: %s\n", output_dir);
        report_state_free(&report_state);
        return 0;
    }

    file_name_set_init(&mac_files);
    if (!list_bip_stems(mac_path, &mac_files)) {
        fprintf(stderr, "failed to list BIP files from: %s\n", mac_path);
        file_name_set_free(&mac_files);
        report_state_free(&report_state);
        return 0;
    }
    if (!read_binary_file(init_path, &init_blob)) {
        fprintf(stderr, "failed to read init.bin: %s\n", init_path);
        file_name_set_free(&mac_files);
        report_state_free(&report_state);
        return 0;
    }
    if (!parse_initbin(init_blob.data, init_blob.size, &mac_files, &init)) {
        fprintf(stderr, "failed to parse init.bin\n");
        binary_blob_free(&init_blob);
        file_name_set_free(&mac_files);
        report_state_free(&report_state);
        return 0;
    }
    if (!opcode_table_load("opcode_table.txt", &opcode_table)) {
        fprintf(stderr, "failed to load opcode_table.txt\n");
        initbin_free(&init);
        binary_blob_free(&init_blob);
        file_name_set_free(&mac_files);
        report_state_free(&report_state);
        return 0;
    }
    if (!write_init_outputs(output_dir, &init)) {
        fprintf(stderr, "failed to write init outputs\n");
        opcode_table_free(&opcode_table);
        initbin_free(&init);
        binary_blob_free(&init_blob);
        file_name_set_free(&mac_files);
        report_state_free(&report_state);
        return 0;
    }

    fprintf(stdout, "parsed init.bin\n");
    fprintf(stdout, "wrote init.tbl and init.txt\n");

    if (!disasm_bip_batch(input_dir, output_dir, &init, &mac_files, &opcode_table, &report_state)) {
        fprintf(stderr, "failed to generate script outputs\n");
        opcode_table_free(&opcode_table);
        initbin_free(&init);
        binary_blob_free(&init_blob);
        file_name_set_free(&mac_files);
        report_state_free(&report_state);
        return 0;
    }

    report_state_free(&report_state);
    opcode_table_free(&opcode_table);
    initbin_free(&init);
    binary_blob_free(&init_blob);
    file_name_set_free(&mac_files);
    return 1;
}

static int run_encode(const char *input_dir, const char *output_dir) {
    char tbl_path[512];
    char txt_path[512];
    char out_init_path[512];
    char out_mac_dir[512];
    BinaryBlob rebuilt_blob;
    FileNameSet mac_files;
    InitBin rebuilt_init;

    rebuilt_blob.data = NULL;
    rebuilt_blob.size = 0;

    if (!join_path(tbl_path, sizeof(tbl_path), input_dir, "init.tbl")) {
        fprintf(stderr, "input init.tbl path too long\n");
        return 0;
    }
    if (!join_path(txt_path, sizeof(txt_path), input_dir, "init.txt")) {
        fprintf(stderr, "input init.txt path too long\n");
        return 0;
    }
    if (!join_path(out_init_path, sizeof(out_init_path), output_dir, "init.bin")) {
        fprintf(stderr, "output init.bin path too long\n");
        return 0;
    }
    if (!join_path(out_mac_dir, sizeof(out_mac_dir), output_dir, "mac")) {
        fprintf(stderr, "output mac path too long\n");
        return 0;
    }
    if (!ensure_directory_chain(output_dir)) {
        fprintf(stderr, "failed to create output directory: %s\n", output_dir);
        return 0;
    }

    if (!rebuild_initbin_from_text(tbl_path, txt_path, out_init_path)) {
        fprintf(stderr, "failed to rebuild init.bin from tbl/txt\n");
        return 0;
    }
    if (!read_binary_file(out_init_path, &rebuilt_blob)) {
        fprintf(stderr, "failed to read rebuilt init.bin\n");
        return 0;
    }

    file_name_set_init(&mac_files);
    if (!parse_initbin(rebuilt_blob.data, rebuilt_blob.size, &mac_files, &rebuilt_init)) {
        fprintf(stderr, "failed to parse rebuilt init.bin\n");
        binary_blob_free(&rebuilt_blob);
        file_name_set_free(&mac_files);
        return 0;
    }
    if (!ensure_directory_chain(out_mac_dir)) {
        fprintf(stderr, "failed to create output mac directory\n");
        initbin_free(&rebuilt_init);
        binary_blob_free(&rebuilt_blob);
        file_name_set_free(&mac_files);
        return 0;
    }
    if (!rebuild_bip_batch(input_dir, out_mac_dir, &rebuilt_init, &mac_files)) {
        fprintf(stderr, "failed to rebuild bip batch\n");
        initbin_free(&rebuilt_init);
        binary_blob_free(&rebuilt_blob);
        file_name_set_free(&mac_files);
        return 0;
    }

    fprintf(stdout, "rebuilt init.bin from tbl/txt\n");
    fprintf(stdout, "rebuilt BIP files from asm/txt\n");

    initbin_free(&rebuilt_init);
    binary_blob_free(&rebuilt_blob);
    file_name_set_free(&mac_files);
    return 1;
}

int main(int argc, char **argv) {
    remove("badchar.txt");
    remove("badchars.txt");
    remove("report.txt");
    if (argc != 4) {
        print_usage();
        return 1;
    }
    if (strcmp(argv[1], "d") == 0) {
        return run_decode(argv[2], argv[3]) ? 0 : 1;
    }
    if (strcmp(argv[1], "e") == 0) {
        return run_encode(argv[2], argv[3]) ? 0 : 1;
    }
    print_usage();
    return 1;
}
