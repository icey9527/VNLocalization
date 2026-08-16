#ifndef ONE_TEX_H
#define ONE_TEX_H

#include <wchar.h>
#include <stddef.h>
#include <stdint.h>

void onetex_extract_dir(const wchar_t *src_dir, const wchar_t *out_dir);
void onetex_pack_dir(const wchar_t *src_dir, const wchar_t *out_dir);
char *onetex_extract_one_mem(const uint8_t *src, size_t src_size, const wchar_t *out_dir, const char *tex_id, size_t *xml_size);
uint8_t *onetex_pack_one_mem(const wchar_t *src_dir, const char *xml_text, size_t xml_size, const char *tex_id, size_t *out_size);

#endif
