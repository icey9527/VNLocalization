#include "io.h"
#include <stdlib.h>
#include <string.h>
#include <direct.h>

 uint32_t rd32(const uint8_t *p)
{
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}

 void wr32(uint8_t *p, uint32_t v)
{
    p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); p[2] = (uint8_t)(v >> 16); p[3] = (uint8_t)(v >> 24);
}

 void make_dir(const char *path)
{
    char buf[1024];
    snprintf(buf, sizeof buf, "%s", path);
    for (size_t i = 1; buf[i]; i++) {
        if (buf[i] == '/' || buf[i] == '\\') {
            char save = buf[i];
            buf[i] = 0;
            _mkdir(buf);
            buf[i] = save;
        }
    }
    _mkdir(buf);
}

 uint8_t *read_file(const char *path, size_t *out_size)
{
    FILE *fp = fopen(path, "rb");
    if (!fp) return NULL;
    fseek(fp, 0, SEEK_END);
    long sz = ftell(fp);
    fseek(fp, 0, SEEK_SET);
    if (sz < 0) { fclose(fp); return NULL; }
    uint8_t *buf = malloc((size_t)sz + 1);
    if (buf && sz && fread(buf, 1, (size_t)sz, fp) != (size_t)sz) {
        free(buf); buf = NULL;
    }
    fclose(fp);
    *out_size = (size_t)sz;
    return buf;
}

/* Names are archive keys, not inferred file extensions. */
 int safe_name(const char *s)
{
    return *s && strcmp(s, ".") && strcmp(s, "..") &&
           !strpbrk(s, "/\\:");
}

