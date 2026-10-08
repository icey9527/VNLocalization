#include "saf_internal.h"
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <windows.h>
#include <io.h>
#include <errno.h>
#include <ctype.h>

/* XML contains only fields that cannot be reconstructed from file sizes. */
static char *convert_name(const char *name, UINT from, UINT to)
{
    int chars = MultiByteToWideChar(from, from == CP_UTF8 ? MB_ERR_INVALID_CHARS : 0, name, -1, NULL, 0);
    if (!chars) return NULL;
    wchar_t *wide = malloc((size_t)chars * sizeof *wide);
    if (!wide) return NULL;
    if (!MultiByteToWideChar(from, from == CP_UTF8 ? MB_ERR_INVALID_CHARS : 0, name, -1, wide, chars)) { free(wide); return NULL; }
    BOOL substituted = FALSE;
    int bytes = WideCharToMultiByte(to, to == 932 ? WC_NO_BEST_FIT_CHARS : 0, wide, chars, NULL, 0, NULL, to == 932 ? &substituted : NULL);
    char *result = bytes ? malloc(bytes) : NULL;
    if (result && (!WideCharToMultiByte(to, to == 932 ? WC_NO_BEST_FIT_CHARS : 0, wide, chars, result, bytes, NULL, to == 932 ? &substituted : NULL) || substituted)) {
        free(result); result = NULL;
    }
    free(wide);
    return result;
}

static void xml_escape(FILE *fp, const char *value)
{
    while (*value) {
        switch (*value) {
            case '&': fputs("&amp;", fp); break;
            case '<': fputs("&lt;", fp); break;
            case '>': fputs("&gt;", fp); break;
            case '"': fputs("&quot;", fp); break;
            case '\'': fputs("&apos;", fp); break;
            default: fputc((unsigned char)*value, fp);
        }
        value++;
    }
}

static FILE *manifest_output;
static char *manifest_text;
static char manifest_root[1024];

static const char *relative_folder(const char *folder)
{
    size_t length = strlen(manifest_root);
    const char *p = folder + length;
    while (*p == '/' || *p == '\\') p++;
    return p;
}

int xml_start_write(const char *folder)
{
    char path[1024];
    if (snprintf(manifest_root, sizeof manifest_root, "%s", folder) >= (int)sizeof manifest_root) return 1;
    size_t length = strlen(manifest_root);
    while (length && (manifest_root[length-1] == '/' || manifest_root[length-1] == '\\')) manifest_root[--length] = 0;
    make_dir(folder);
    if (snprintf(path, sizeof path, "%s/%s", folder, MANIFEST) >= (int)sizeof path) return 1;
    manifest_output = fopen(path, "wb");
    if (!manifest_output) return 1;
    fputs("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<resources>\n", manifest_output);
    return 0;
}

int xml_end_write(void)
{
    if (!manifest_output) return 1;
    fputs("</resources>\n", manifest_output);
    int failed = ferror(manifest_output);
    if (fclose(manifest_output)) failed = 1;
    manifest_output = NULL;
    return failed;
}

int xml_start_read(const char *folder)
{
    char path[1024]; size_t size;
    if (snprintf(manifest_root, sizeof manifest_root, "%s", folder) >= (int)sizeof manifest_root) return 1;
    size_t length = strlen(manifest_root);
    while (length && (manifest_root[length-1] == '/' || manifest_root[length-1] == '\\')) manifest_root[--length] = 0;
    if (snprintf(path, sizeof path, "%s/%s", folder, MANIFEST) >= (int)sizeof path) return 1;
    manifest_text = (char *)read_file(path, &size);
    if (!manifest_text) { printf("Error: missing root index: %s\n", path); return 1; }
    manifest_text[size] = 0;
    if (memchr(manifest_text, 0, size) || !strstr(manifest_text, "<resources>") || !strstr(manifest_text, "</resources>")) {
        free(manifest_text); manifest_text = NULL; return 1;
    }
    return 0;
}

void xml_end_read(void)
{
    free(manifest_text); manifest_text = NULL;
}

int write_xml(const char *folder, uint32_t ver, uint32_t count, const ENTRY *tab)
{
    if (!manifest_output) return 1;
    FILE *fp = manifest_output;
    char *relative = convert_name(relative_folder(folder), 932, CP_UTF8);
    if (!relative) return 1;
    fputs("  <archive", fp);
    if (*relative) { fputs(" path=\"", fp); xml_escape(fp, relative); fputc('"', fp); }
    fprintf(fp, " version=\"%u\">\n", ver);
    free(relative);
    for (uint32_t i = 0; i < count; i++) {
        char *name = convert_name(tab[i].name, 932, CP_UTF8);
        if (!name) return 1;
        fputs("    <entry name=\"", fp); xml_escape(fp, name);
        fprintf(fp, "\" flags=\"0x%08X\"", tab[i].flags);
        if (tab[i].t2) {
            fputs(" type=\"T2\"", fp);
            if (tab[i].x) fprintf(fp, " x=\"%d\"", tab[i].x);
            if (tab[i].y) fprintf(fp, " y=\"%d\"", tab[i].y);
        }
        fputs(" />\n", fp);
        free(name);
    }
    fputs("  </archive>\n", fp);
    return ferror(fp) != 0;
}

/* Small, strict parser for our flat saf/entry schema (not a general XML parser). */
static int attribute(const char *tag, const char *key, char *out, size_t cap)
{
    const char *p = tag;
    while (*p && !isspace((unsigned char)*p)) p++;
    int found = 0;
    while (*p) {
        while (isspace((unsigned char)*p)) p++;
        if (!*p || *p == '/') break;
        const char *start = p;
        while (isalnum((unsigned char)*p) || *p == '_') p++;
        if (p == start) return 1;
        size_t len = (size_t)(p - start);
        while (isspace((unsigned char)*p)) p++;
        if (*p++ != '=') return 1;
        while (isspace((unsigned char)*p)) p++;
        char quote = *p++;
        if (quote != '"' && quote != '\'') return 1;
        const char *value = p;
        while (*p && *p != quote) p++;
        if (!*p) return 1;
        if (len == strlen(key) && !memcmp(start, key, len)) {
            if (found++) return 1;
            size_t n = 0;
            while (value < p) {
                char ch = *value++;
                if (ch == '&') {
                    const char *entities[] = {"amp;", "lt;", "gt;", "quot;", "apos;"};
                    const char chars[] = "&<>\"'";
                    unsigned i;
                    for (i = 0; i < 5; i++) {
                        size_t size = strlen(entities[i]);
                        if ((size_t)(p - value) >= size && !memcmp(value, entities[i], size)) { ch = chars[i]; value += size; break; }
                    }
                    if (i == 5) return 1;
                }
                if (n + 1 >= cap) return 1;
                out[n++] = ch;
            }
            out[n] = 0;
        }
        p++;
    }
    return found ? 0 : 2;
}

static int xml_uint(const char *text, uint32_t *value)
{
    char *end;
    if (!*text || *text == '-' || *text == '+') return 1;
    errno = 0;
    unsigned long v = strtoul(text, &end, 0);
    if (errno || *end || v > UINT32_MAX) return 1;
    *value = (uint32_t)v;
    return 0;
}

static int optional_position(const char *tag, const char *key, int *value)
{
    char text[256], *end;
    *value = 0;
    int status = attribute(tag, key, text, sizeof text);
    if (status == 2) return 0;
    if (status) return 1;
    errno = 0;
    long n = strtol(text, &end, 10);
    if (errno || !*text || *end || n < -32768 || n > 32767) return 1;
    *value = (int)n;
    return 0;
}

int read_xml(const char *folder, uint32_t *ver, uint32_t *count, int *esz, ENTRY **tab)
{
    char path[1024];
    snprintf(path, sizeof path, "%s/%s", manifest_root, MANIFEST);
    if (!manifest_text) return 1;
    const char *wanted = relative_folder(folder);
    const char *scan = manifest_text;
    char *xml = NULL;
    while ((scan = strstr(scan, "<archive "))) {
        const char *end = strstr(scan, "</archive>");
        const char *header_end = strchr(scan, '>');
        if (!end || !header_end || header_end > end) { free(xml); return 1; }
        size_t header_length = (size_t)(header_end - scan - 1);
        char *tag = malloc(header_length + 1);
        if (!tag) { free(xml); return 1; }
        memcpy(tag, scan+1, header_length); tag[header_length] = 0;
        char attr[1024];
        int failed = attribute(tag, "path", attr, sizeof attr);
        if (failed == 2) { attr[0] = 0; failed = 0; }
        else if (!failed && !*attr) failed = 1;
        free(tag);
        char *relative = failed ? NULL : convert_name(attr, CP_UTF8, 932);
        if (!relative) { free(xml); return 1; }
        if (!_stricmp(relative, wanted)) {
            if (xml) { free(relative); free(xml); printf("Error: duplicate archive path\n"); return 1; }
            size_t length = (size_t)(end + strlen("</archive>") - scan);
            xml = malloc(length+1);
            if (xml) { memcpy(xml, scan, length); xml[length] = 0; }
            else { free(relative); return 1; }
        }
        free(relative);
        scan = end + strlen("</archive>");
    }
    if (!xml) { printf("Error: archive path absent from root list.xml: %s\n", folder); return 1; }
    char *p = xml;
    ENTRY *entries = NULL;
    size_t capacity = 0;
    *count = 0;
    int root = 0, closed = 0, failed = 0;
    while (*p && !failed) {
        while (isspace((unsigned char)*p)) p++;
        if (!*p) break;
        if (!strncmp(p, "<!--", 4)) {
            char *end = strstr(p+4, "-->");
            if (!end) { failed = 1; break; }
            p = end + 3; continue;
        }
        if (!strncmp(p, "<?xml", 5) && !root) {
            char *end = strstr(p+5, "?>");
            if (!end) { failed = 1; break; }
            p = end + 2; continue;
        }
        if (*p != '<') { failed = 1; break; }
        char *tag = ++p, quote = 0;
        while (*p) {
            if (quote) { if (*p == quote) quote = 0; }
            else if (*p == '"' || *p == '\'') quote = *p;
            else if (*p == '>') break;
            p++;
        }
        if (!*p) { failed = 1; break; }
        *p++ = 0;
        char attr[256];
        if (!strncmp(tag, "archive", 7) && isspace((unsigned char)tag[7]) && !root) {
            failed = attribute(tag, "version", attr, sizeof attr) || xml_uint(attr, ver) || (*ver != 1 && *ver != 2);
            root = 1; *esz = *ver == 1 ? 32 : 48;
        } else if (!strncmp(tag, "entry", 5) && isspace((unsigned char)tag[5]) && root && !closed) {
            size_t length = strlen(tag);
            while (length && isspace((unsigned char)tag[length-1])) length--;
            if (!length || tag[length-1] != '/' || attribute(tag, "name", attr, sizeof attr)) { failed = 1; break; }
            char *name = convert_name(attr, CP_UTF8, 932);
            if (!name || !safe_name(name) || strlen(name) > (size_t)*esz-16 || !_stricmp(name, MANIFEST)) {
                free(name); failed = 1; break;
            }
            ENTRY entry = {0};
            strcpy(entry.name, name); free(name);
            failed = attribute(tag, "flags", attr, sizeof attr) || xml_uint(attr, &entry.flags);
            int type_status = attribute(tag, "type", attr, sizeof attr);
            if (type_status == 1 || (!type_status && strcmp(attr, "T2"))) failed = 1;
            entry.t2 = type_status == 0;
            if (optional_position(tag, "x", &entry.x) || optional_position(tag, "y", &entry.y) ||
                (!entry.t2 && (entry.x || entry.y))) failed = 1;
            for (uint32_t i = 0; i < *count; i++) if (!_stricmp(entries[i].name, entry.name)) failed = 1;
            if (failed || *count == UINT32_MAX) { failed = 1; break; }
            if (*count == capacity) {
                size_t next = capacity ? capacity*2 : 32;
                if (next < capacity || next > SIZE_MAX/sizeof *entries) { failed = 1; break; }
                ENTRY *grown = realloc(entries, next*sizeof *entries);
                if (!grown) { failed = 1; break; }
                entries = grown; capacity = next;
            }
            entries[(*count)++] = entry;
        } else if (!strcmp(tag, "/archive") && root && !closed) closed = 1;
        else failed = 1;
    }
    free(xml);
    if (failed || !closed) { free(entries); printf("Error: invalid SAF XML: %s\n", path); return 1; }
    /* No silent omissions: every file/directory must appear in XML. */
    snprintf(path, sizeof path, "%s/*", folder);
    struct _finddata_t found;
    intptr_t handle = _findfirst(path, &found);
    if (handle == -1) { free(entries); return 1; }
    do {
        if (!strcmp(found.name, ".") || !strcmp(found.name, "..") || !_stricmp(found.name, MANIFEST)) continue;
        int listed = 0;
        for (uint32_t i = 0; i < *count; i++) {
            char expected[64];
            snprintf(expected, sizeof expected, "%s%s", entries[i].name, entries[i].t2 ? ".png" : "");
            if (!_stricmp(found.name, expected)) listed = 1;
        }
        if (!listed) { printf("Error: file not listed in XML: %s/%s\n", folder, found.name); failed = 1; }
    } while (!_findnext(handle, &found));
    _findclose(handle);
    if (failed) { free(entries); return 1; }
    *tab = entries;
    return 0;
}

