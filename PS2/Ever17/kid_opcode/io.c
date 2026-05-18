#include "io.h"

#include <direct.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>

static int name_set_reserve(FileNameSet *set, size_t needed) {
    char **new_items;
    size_t new_capacity;

    if (set->capacity >= needed) {
        return 1;
    }

    new_capacity = set->capacity ? set->capacity * 2 : 32;
    while (new_capacity < needed) {
        new_capacity *= 2;
    }

    new_items = (char **)realloc(set->items, new_capacity * sizeof(char *));
    if (!new_items) {
        return 0;
    }

    set->items = new_items;
    set->capacity = new_capacity;
    return 1;
}

static int has_bip_extension(const char *name) {
    const char *dot = strrchr(name, '.');
    if (!dot) {
        return 0;
    }
    return _stricmp(dot, ".BIP") == 0;
}

void binary_blob_free(BinaryBlob *blob) {
    free(blob->data);
    blob->data = NULL;
    blob->size = 0;
}

int read_binary_file(const char *path, BinaryBlob *blob) {
    FILE *fp;
    long size;
    uint8_t *data;

    blob->data = NULL;
    blob->size = 0;

    fp = fopen(path, "rb");
    if (!fp) {
        return 0;
    }
    if (fseek(fp, 0, SEEK_END) != 0) {
        fclose(fp);
        return 0;
    }
    size = ftell(fp);
    if (size < 0) {
        fclose(fp);
        return 0;
    }
    if (fseek(fp, 0, SEEK_SET) != 0) {
        fclose(fp);
        return 0;
    }

    data = (uint8_t *)malloc((size_t)size);
    if (!data) {
        fclose(fp);
        return 0;
    }
    if (size > 0 && fread(data, 1, (size_t)size, fp) != (size_t)size) {
        free(data);
        fclose(fp);
        return 0;
    }

    fclose(fp);
    blob->data = data;
    blob->size = (size_t)size;
    return 1;
}

int write_binary_file(const char *path, const void *data, size_t size) {
    FILE *fp = fopen(path, "wb");
    if (!fp) {
        return 0;
    }
    if (size > 0 && fwrite(data, 1, size, fp) != size) {
        fclose(fp);
        return 0;
    }
    fclose(fp);
    return 1;
}

int compare_binary_files(const char *left_path, const char *right_path) {
    BinaryBlob left;
    BinaryBlob right;
    int same;

    if (!read_binary_file(left_path, &left)) {
        return 0;
    }
    if (!read_binary_file(right_path, &right)) {
        binary_blob_free(&left);
        return 0;
    }

    same = left.size == right.size && memcmp(left.data, right.data, left.size) == 0;
    binary_blob_free(&left);
    binary_blob_free(&right);
    return same;
}

void file_name_set_init(FileNameSet *set) {
    set->items = NULL;
    set->count = 0;
    set->capacity = 0;
}

void file_name_set_free(FileNameSet *set) {
    size_t i;

    for (i = 0; i < set->count; ++i) {
        free(set->items[i]);
    }
    free(set->items);
    set->items = NULL;
    set->count = 0;
    set->capacity = 0;
}

int file_name_set_append(FileNameSet *set, const char *name) {
    size_t length;
    char *copy;

    if (!name_set_reserve(set, set->count + 1)) {
        return 0;
    }

    length = strlen(name);
    copy = (char *)malloc(length + 1);
    if (!copy) {
        return 0;
    }
    memcpy(copy, name, length + 1);
    set->items[set->count++] = copy;
    return 1;
}

int file_name_set_contains(const FileNameSet *set, const char *name) {
    size_t i;
    for (i = 0; i < set->count; ++i) {
        if (_stricmp(set->items[i], name) == 0) {
            return 1;
        }
    }
    return 0;
}

int ensure_directory_exists(const char *path) {
    if (_mkdir(path) == 0) {
        return 1;
    }
    return errno == EEXIST;
}

int ensure_directory_chain(const char *path) {
    char temp[MAX_PATH];
    size_t i;
    size_t length;

    length = strlen(path);
    if (length >= sizeof(temp)) {
        return 0;
    }
    memcpy(temp, path, length + 1);

    for (i = 0; i < length; ++i) {
        if (temp[i] == '\\' || temp[i] == '/') {
            char saved = temp[i];
            if (i > 0 && temp[i - 1] != ':') {
                temp[i] = '\0';
                if (!ensure_directory_exists(temp)) {
                    return 0;
                }
                temp[i] = saved;
            }
        }
    }

    return ensure_directory_exists(temp);
}

int join_path(char *buffer, size_t buffer_size, const char *left, const char *right) {
    int written;
    written = snprintf(buffer, buffer_size, "%s\\%s", left, right);
    return written > 0 && (size_t)written < buffer_size;
}

int list_bip_stems(const char *mac_dir, FileNameSet *set) {
    char pattern[MAX_PATH];
    WIN32_FIND_DATAA find_data;
    HANDLE handle;

    if (!join_path(pattern, sizeof(pattern), mac_dir, "*.BIP")) {
        return 0;
    }

    handle = FindFirstFileA(pattern, &find_data);
    if (handle == INVALID_HANDLE_VALUE) {
        return 0;
    }

    do {
        char stem[MAX_PATH];
        const char *dot;
        size_t length;

        if (find_data.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
            continue;
        }
        if (!has_bip_extension(find_data.cFileName)) {
            continue;
        }

        dot = strrchr(find_data.cFileName, '.');
        length = dot ? (size_t)(dot - find_data.cFileName) : strlen(find_data.cFileName);
        if (length >= sizeof(stem)) {
            FindClose(handle);
            return 0;
        }
        memcpy(stem, find_data.cFileName, length);
        stem[length] = '\0';

        if (!file_name_set_append(set, stem)) {
            FindClose(handle);
            return 0;
        }
    } while (FindNextFileA(handle, &find_data));

    FindClose(handle);
    return 1;
}
