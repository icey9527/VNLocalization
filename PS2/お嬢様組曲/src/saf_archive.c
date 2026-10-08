#include "saf_internal.h"
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include "saf_archive.h"
#include "t2.h"

/* Outer archive is read from disk; child archives are views into decoded RAM. */
typedef struct { FILE *file; const uint8_t *data; size_t size, pos; } Input;
static int input_seek(Input *in, size_t pos)
{
    if (pos > in->size) return 1;
    in->pos = pos;
    return in->file ? fseek(in->file, (long)pos, SEEK_SET) != 0 : 0;
}
static size_t input_read(Input *in, void *out, size_t size)
{
    if (size > in->size-in->pos) return 0;
    if (in->file) { if (fread(out, 1, size, in->file) != size) return 0; }
    else memcpy(out, in->data+in->pos, size);
    in->pos += size;
    return size;
}
static int load_table(Input *fp, uint32_t *ver, uint32_t *count, int *esz, ENTRY **tab)
{
    uint8_t h[16];
    size_t length = fp->size;
    if (input_seek(fp, 0)) goto fail;
    if (input_read(fp, h, 16) != 16 || memcmp(h, "SAF0", 4)) goto fail;
    *ver = rd32(h + 4); *count = rd32(h + 12);
    if (*ver != 1 && *ver != 2) goto fail;
    *esz = *ver == 1 ? 32 : 48;
    if (length < 16 || (uint64_t)16 + (uint64_t)*count * *esz > (uint64_t)length) goto fail;
    if (rd32(h + 8) != (uint32_t)length) goto fail;
    ENTRY *t = calloc(*count ? *count : 1, sizeof *t);
    if (!t) goto fail;
    input_seek(fp, 16);
    for (uint32_t i = 0; i < *count; i++) {
        uint8_t e[48];
        if (input_read(fp, e, *esz) != (size_t)*esz) { free(t); goto fail; }
        t[i].flags = rd32(e); t[i].off = rd32(e + 4);
        t[i].csize = rd32(e + 8); t[i].rsize = rd32(e + 12);
        memcpy(t[i].name, e + 16, *esz - 16);
        if (!safe_name(t[i].name) || !_stricmp(t[i].name, MANIFEST) ||
            (uint64_t)t[i].off + t[i].csize > (uint64_t)length ||
            (!(t[i].flags & FLAG_ZLIB) && t[i].csize != t[i].rsize)) {
            free(t); goto fail;
        }
        for (uint32_t j = 0; j < i; j++) {
            if (!_stricmp(t[i].name, t[j].name)) { free(t); goto fail; }
        }
    }
    *tab = t;
    return 0;
fail:
    printf("Error: invalid/truncated SAF0 archive or unsafe/duplicate name\n");
    return 1;
}

static uint8_t *entry_data(Input *fp, const ENTRY *e)
{
    uint8_t *src = malloc(e->csize ? e->csize : 1), *dst = NULL;
    if (!src) return NULL;
    if (input_seek(fp, e->off) || input_read(fp, src, e->csize) != e->csize) {
        free(src); return NULL;
    }
    if (!(e->flags & FLAG_ZLIB)) return src;
    uLongf size = e->rsize;
    dst = malloc(e->rsize ? e->rsize : 1);
    int error = !dst || uncompress(dst, &size, src, e->csize);
    free(src);
    if (error || size != e->rsize) { free(dst); return NULL; }
    return dst;
}

static int unpack_stream(Input *fp, const char *out_dir, unsigned depth)
{
    uint32_t ver, count; int esz; ENTRY *tab = NULL;
    if (depth > 16 || load_table(fp, &ver, &count, &esz, &tab)) return 1;
    make_dir(out_dir);
    int failed = 0;
    for (uint32_t i = 0; i < count; i++) {
        ENTRY *e = &tab[i];
        uint8_t *data = entry_data(fp, e);
        char path[1024];
        if (!data || snprintf(path, sizeof path, "%s/%s", out_dir, e->name) >= (int)sizeof path) {
            free(data); failed = 1; break;
        }
        struct stat st;
        int nested = e->rsize >= 4 && !memcmp(data, "SAF0", 4);
        e->t2 = e->rsize >= 2 && !memcmp(data, "T2", 2);
        if (e->t2) {
            for (uint32_t j = 0; j < count; j++) {
                char name[64]; snprintf(name, sizeof name, "%s.png", e->name);
                if (!_stricmp(name, tab[j].name)) { printf("Error: PNG name conflict: %s\n", name); free(data); free(tab); return 1; }
            }
            if (snprintf(path, sizeof path, "%s/%s.png", out_dir, e->name) >= (int)sizeof path) { free(data); failed = 1; break; }
        }
        if (!stat(path, &st) && ((st.st_mode & S_IFDIR) != 0) != nested) {
            printf("Error: file/directory conflict: %s (use a fresh output directory)\n", path);
            free(data); failed = 1; break;
        }
        printf("%*s[%04u] %s%s\n", (int)depth * 2, "", i, e->name, nested ? "/ (nested SAF0)" : "");
        if (nested) {
            Input child = {NULL, data, e->rsize, 0};
            failed = unpack_stream(&child, path, depth + 1);
        } else if (e->t2) {
            failed = t2_export(data, e->rsize, path, &e->x, &e->y);
        } else {
            FILE *out = fopen(path, "wb");
            if (!out) failed = 1;
            else {
                failed = fwrite(data, 1, e->rsize, out) != e->rsize;
                if (fclose(out)) failed = 1;
            }
        }
        free(data);
        if (failed) { printf("Error: extracting %s\n", path); break; }
    }
    if (!failed) failed = write_xml(out_dir, ver, count, tab);
    free(tab);
    return failed;
}

/* Rebuild each child archive in memory; no temporary SAF/T2 files. */
typedef struct { uint8_t *data; size_t size, capacity; } Buffer;
static int append(Buffer *out, const void *data, size_t size)
{
    if (size > UINT32_MAX-out->size) return 1;
    size_t need = out->size+size;
    if (need > out->capacity) {
        size_t cap = need < UINT32_MAX/2 ? need*2 : need;
        uint8_t *p = realloc(out->data, cap ? cap : 1);
        if (!p) return 1;
        out->data = p; out->capacity = cap;
    }
    memcpy(out->data+out->size, data, size); out->size = need;
    return 0;
}
static int pack_stream(const char *in_dir, Buffer *out, unsigned depth)
{
    uint32_t ver = 0, count = 0; int esz = 0; ENTRY *tab = NULL;
    if (depth > 16 || read_xml(in_dir, &ver, &count, &esz, &tab)) return 1;
    uint64_t header_size = (uint64_t)16 + (uint64_t)count * esz;
    if (header_size > UINT32_MAX - 63) { free(tab); return 1; }
    uint32_t cur = ALIGN((uint32_t)header_size);
    uint8_t *table = calloc(1, cur);
    if (!table) { free(tab); return 1; }
    memcpy(table, "SAF0", 4); wr32(table + 4, ver); wr32(table + 12, count);
    int failed = append(out, table, cur);
    for (uint32_t i = 0; i < count && !failed; i++) {
        ENTRY *e = &tab[i];
        uint8_t *data = NULL, *store = NULL;
        size_t size = 0; uint32_t stored = 0;
        char path[1024]; struct stat st;
        if (snprintf(path, sizeof path, "%s/%s%s", in_dir, e->name, e->t2 ? ".png" : "") >= (int)sizeof path) { failed = 1; break; }
        if (stat(path, &st)) {
            printf("Error: XML entry missing from folder: %s\n", path); failed = 1; break;
        }
        if (e->t2) {
            data = t2_import(path, e->x, e->y, &size);
        } else if (st.st_mode & S_IFDIR) {
            Buffer child = {0};
            failed = pack_stream(path, &child, depth + 1);
            data = child.data; size = child.size;
        } else data = read_file(path, &size);
        if (failed || !data || size > UINT32_MAX) { free(data); failed = 1; break; }
        store = data; stored = (uint32_t)size;
        if (e->flags & FLAG_ZLIB) {
            uLongf length = compressBound((uLong)size);
            uint8_t *compressed = length ? malloc(length) : NULL;
            if (!compressed || compress2(compressed, &length, data, (uLong)size, 9)) {
                printf("Error: compression failed: %s\n", path);
                free(compressed); free(data); failed = 1; break;
            }
            store = compressed; stored = (uint32_t)length;
        }
        if ((uint64_t)cur + stored + 63 > UINT32_MAX) failed = 1;
        uint8_t *rec = table + 16 + (size_t)i * esz;
        wr32(rec, e->flags); wr32(rec + 4, cur); wr32(rec + 8, stored); wr32(rec + 12, (uint32_t)size);
        memcpy(rec + 16, e->name, esz - 16);
        if (!failed) {
            static const uint8_t zeros[64] = {0};
            uint32_t pad = ALIGN(stored) - stored;
            failed = append(out, store, stored) || append(out, zeros, pad);
            cur += ALIGN(stored);
        }
        if (store != data) free(store);
        free(data);
        printf("%*s[%04u] packed %s\n", (int)depth * 2, "", i, e->name);
    }
    if (!failed) {
        wr32(table + 8, cur);
        memcpy(out->data, table, (size_t)header_size);
    }
    free(table); free(tab);
    return failed;
}

int saf_unpack(const char *input, const char *folder)
{
    FILE *fp = fopen(input, "rb");
    if (!fp) { printf("Error: cannot open %s\n", input); return 1; }
    if (xml_start_write(folder)) { fclose(fp); return 1; }
    int failed = fseek(fp, 0, SEEK_END) != 0;
    long length = failed ? -1 : ftell(fp);
    Input stream = {fp, NULL, length < 0 ? 0 : (size_t)length, 0};
    if (length < 0) failed = 1;
    if (!failed) failed = unpack_stream(&stream, folder, 0);
    if (xml_end_write()) failed = 1;
    fclose(fp);
    return failed;
}

int saf_pack(const char *folder, const char *output)
{
    char a[1024], b[1024];
    if (!_fullpath(a, folder, sizeof a) || !_fullpath(b, output, sizeof b)) return 1;
    size_t len = strlen(a);
    while (len && (a[len-1] == '\\' || a[len-1] == '/')) a[--len] = 0;
    if (!_strnicmp(a, b, len) && (!b[len] || b[len] == '\\' || b[len] == '/')) {
        printf("Error: output archive must be outside input folder\n"); return 1;
    }
    struct stat st;
    if (stat(folder, &st) || !(st.st_mode & S_IFDIR)) {
        printf("Error: input folder does not exist\n"); return 1;
    }
    if (xml_start_read(folder)) return 1;
    Buffer rebuilt = {0};
    int failed = pack_stream(folder, &rebuilt, 0);
    xml_end_read();
    if (!failed) {
        char *parent = strrchr(b, '\\');
        if (parent) { *parent = 0; make_dir(b); }
        FILE *out = fopen(output, "wb");
        if (!out) failed = 1;
        else {
            failed = fwrite(rebuilt.data, 1, rebuilt.size, out) != rebuilt.size;
            if (fclose(out)) failed = 1;
        }
    }
    free(rebuilt.data);
    printf("%s: %s\n", failed ? "Error" : "Done", output);
    return failed;
}

