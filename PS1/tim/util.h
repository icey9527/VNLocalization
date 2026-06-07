#ifndef UTIL_H
#define UTIL_H

#include <stddef.h>
#include <stdint.h>
#include <wchar.h>
#include <windows.h>

char *utf8_from_wide(const wchar_t *w);
wchar_t *wide_from_utf8(const char *s);
int path_join_w(wchar_t *out, size_t cap, const wchar_t *dir, const wchar_t *name);
int path_change_ext_w(wchar_t *out, size_t cap, const wchar_t *path, const wchar_t *ext);
int path_stem_w(wchar_t *out, size_t cap, const wchar_t *path);
int path_make_relative_no_ext_w(wchar_t *out, size_t cap, const wchar_t *base_dir, const wchar_t *full_path);
int path_join_stem_ext_w(wchar_t *out, size_t cap, const wchar_t *base_dir, const wchar_t *stem, const wchar_t *ext);
int ensure_parent_dir_w(const wchar_t *path);
int ensure_dir_w(const wchar_t *path);
int read_file_w(const wchar_t *path, uint8_t **data, size_t *size);
int write_file_w(const wchar_t *path, const uint8_t *data, size_t size);

#endif
