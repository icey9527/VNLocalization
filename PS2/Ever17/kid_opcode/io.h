#ifndef E17_IO_H
#define E17_IO_H

#include <stddef.h>
#include <stdint.h>

typedef struct BinaryBlob {
    uint8_t *data;
    size_t size;
} BinaryBlob;

typedef struct FileNameSet {
    char **items;
    size_t count;
    size_t capacity;
} FileNameSet;

void binary_blob_free(BinaryBlob *blob);
int read_binary_file(const char *path, BinaryBlob *blob);
int write_binary_file(const char *path, const void *data, size_t size);
int compare_binary_files(const char *left_path, const char *right_path);

void file_name_set_init(FileNameSet *set);
void file_name_set_free(FileNameSet *set);
int file_name_set_append(FileNameSet *set, const char *name);
int file_name_set_contains(const FileNameSet *set, const char *name);

int ensure_directory_exists(const char *path);
int ensure_directory_chain(const char *path);
int join_path(char *buffer, size_t buffer_size, const char *left, const char *right);
int list_bip_stems(const char *mac_dir, FileNameSet *set);

#endif
