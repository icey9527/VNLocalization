/*
 * util.c -- helpers: file IO, little-endian ints, magic sniffing, dir listing.
 */
#include "cdi.h"

#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <direct.h>
#include <windows.h>

void die(const char *msg, const char *arg)
{
    if (arg) fprintf(stderr, "error: %s (%s)\n", msg, arg);
    else     fprintf(stderr, "error: %s\n", msg);
    exit(1);
}

FILE *xfopen(const char *path, const char *mode)
{
    FILE *f = fopen(path, mode);
    if (!f) die(strerror(errno), path);
    return f;
}

void seekf(FILE *f, uint64_t off)
{
    if (_fseeki64(f, (long long)off, SEEK_SET) != 0) die("seek failed", NULL);
}

uint64_t fsize(FILE *f)
{
    _fseeki64(f, 0, SEEK_END);
    return (uint64_t)_ftelli64(f);
}

uint32_t rd32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}
uint16_t rd16(const uint8_t *p) { return (uint16_t)(p[0] | (p[1] << 8)); }
void wr32(uint8_t *p, uint32_t v)
{
    p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8);
    p[2] = (uint8_t)(v >> 16); p[3] = (uint8_t)(v >> 24);
}
void wr16(uint8_t *p, uint16_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); }

uint64_t align_up(uint64_t n, uint64_t a) { return (n + a - 1) / a * a; }

int mkpath(const char *path)
{
    char tmp[PATHSZ];
    size_t len = strlen(path);
    if (len == 0 || len >= sizeof tmp) return -1;
    memcpy(tmp, path, len + 1);
    for (char *p = tmp + 1; *p; p++) {
        if (*p == '\\' || *p == '/') {
            char c = *p;
            *p = 0;
            _mkdir(tmp);
            *p = c;
        }
    }
    if (_mkdir(tmp) == 0) return 0;
    return (errno == EEXIST) ? 0 : -1;
}

/* ------------------------------------------------------------- 魔数嗅探 */

typedef struct { const char *sig; int len; uint32_t off; const char *ext; } Magic;

static const Magic MAGICS[] = {
    { "OggS",             4, 0x000, ".ogg"  },
    { "ZVOC",             4, 0x000, ".zvoc" },
    { "SCR\0",            4, 0x000, ".scr"  },
    { "PGM\0",            4, 0x000, ".pgm"  },
    { "SFO\0",            4, 0x000, ".sfo"  },
    { "NPSF",             4, 0x000, ".npsf" },
    { "PHDp",             4, 0x000, ".phdp" },
    { "ZEF\0",            4, 0x000, ".zef"  },
    { "TIM2",             4, 0x000, ".tm2"  },
    { "RIFF",             4, 0x000, ".wav"  },
    { "\x89" "PNG",       4, 0x000, ".png"  },
    { "\xFF\xD8\xFF",     3, 0x000, ".jpg"  },
    { "\x00\x00\x01\xB3", 4, 0x810, ".m2v"  },   /* movimage: MPEG-2 序列头 */
    { "\x00\x00\x01\xBA", 4, 0x810, ".pss"  },
};

const char *sniff_ext(const uint8_t *d, uint64_t len, char *namepart, size_t npsz)
{
    if (namepart && npsz) namepart[0] = 0;
    for (size_t i = 0; i < sizeof MAGICS / sizeof MAGICS[0]; i++) {
        const Magic *m = &MAGICS[i];
        if ((uint64_t)m->off + m->len > len) continue;
        if (memcmp(d + m->off, m->sig, (size_t)m->len) != 0) continue;
        if (memcmp(m->sig, "NPSF", 4) == 0 && namepart && npsz > 8 && len > 0x40) {
            uint64_t k = 0x34;
            char nb[64];
            size_t j = 0;
            while (k < len && d[k] >= 0x20 && d[k] < 0x7F && j + 1 < sizeof nb) nb[j++] = (char)d[k++];
            nb[j] = 0;
            if (j >= 5) {
                char *dot = strrchr(nb, '.');
                if (dot) *dot = 0;
                snprintf(namepart, npsz, "_%s", nb);
            }
        }
        return m->ext;
    }
    return ".bin";
}

/* ------------------------------------------------------------- 读写整文件 */

uint8_t *read_all(const char *path, uint64_t *len)
{
    FILE *f = xfopen(path, "rb");
    uint8_t *b;
    *len = fsize(f);
    b = malloc((size_t)*len + 1);
    if (!b) die("out of memory", NULL);
    seekf(f, 0);
    if (*len && fread(b, 1, (size_t)*len, f) != (size_t)*len) die("read failed", path);
    fclose(f);
    return b;
}

void write_all(const char *path, const uint8_t *d, uint64_t len)
{
    FILE *f = xfopen(path, "wb");
    if (len && fwrite(d, 1, (size_t)len, f) != (size_t)len) die("write failed", path);
    fclose(f);
}

/* ------------------------------------------------------------- 目录列举 */

Ent *list_dir(const char *dir, int *count)
{
    char pat[PATHSZ];
    WIN32_FIND_DATAA fd;
    HANDLE h;
    int cap = 64, n = 0;
    Ent *v;

    snprintf(pat, sizeof pat, "%s\\*", dir);
    h = FindFirstFileA(pat, &fd);
    if (h == INVALID_HANDLE_VALUE) die("cannot list directory", dir);
    v = malloc(sizeof(Ent) * cap);
    if (!v) die("out of memory", NULL);
    do {
        if (!strcmp(fd.cFileName, ".") || !strcmp(fd.cFileName, "..")) continue;
        if (n == cap) {
            cap *= 2;
            v = realloc(v, sizeof(Ent) * cap);
            if (!v) die("out of memory", NULL);
        }
        snprintf(v[n].name, sizeof v[n].name, "%s", fd.cFileName);
        v[n].size = ((uint64_t)fd.nFileSizeHigh << 32) | fd.nFileSizeLow;
        v[n].isdir = (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) ? 1 : 0;
        n++;
    } while (FindNextFileA(h, &fd));
    FindClose(h);
    *count = n;
    return v;
}

void stem_of(const char *name, char *out, size_t n)
{
    size_t i, l = strlen(name);
    for (i = 0; i < l && i + 1 < n; i++) out[i] = name[i];
    out[i] = 0;
}

static int hexval(int c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

int parse_id(const char *name, uint32_t *out)
{
    uint64_t v = 0;
    int n = 0, d;
    const char *p = name;
    for (;; p++) {
        d = hexval((unsigned char)*p);
        if (d < 0) break;
        v = v * 16 + (uint64_t)d;
        if (++n > 8 || v > 0xFFFFFFFFull) return -1;
    }
    if (!n) return -1;
    /* id 之后可跟 '.'（扩展名）或 '_'（内嵌原名，如 02D8_bgm005.npsf） */
    if (*p != 0 && *p != '.' && *p != '_') return -1;
    *out = (uint32_t)v;
    return 0;
}
