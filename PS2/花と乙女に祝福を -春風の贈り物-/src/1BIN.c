#define _CRT_SECURE_NO_WARNINGS
#include <windows.h>
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "1BIN.h"

typedef struct {
    unsigned char *v;
    size_t n;
    size_t cap;
} Buf;

typedef struct {
    unsigned *v;
    size_t n;
    size_t cap;
} U32Vec;

typedef struct {
    unsigned short *v;
    size_t n;
    size_t cap;
} U16Vec;

typedef struct {
    char **v;
    size_t n;
    size_t cap;
} StrVec;

typedef struct {
    unsigned id;
    char *file;
    U32Vec refs;
} EntryMap;

typedef struct {
    EntryMap *v;
    size_t n;
    size_t cap;
} EntryVec;

static void die(const char *msg) {
    fprintf(stderr, "%s\n", msg);
    exit(1);
}

static void *xmalloc(size_t n) {
    void *p = malloc(n ? n : 1);
    if (!p) die("out of memory");
    return p;
}

static void *xrealloc(void *p, size_t n) {
    void *q = realloc(p, n ? n : 1);
    if (!q) die("out of memory");
    return q;
}

static char *xstrdup(const char *s) {
    size_t n = strlen(s);
    char *p = (char *)xmalloc(n + 1);
    memcpy(p, s, n + 1);
    return p;
}

static wchar_t *wjoin2(const wchar_t *a, const wchar_t *b) {
    size_t na = wcslen(a), nb = wcslen(b);
    int slash = na && a[na - 1] != L'\\' && a[na - 1] != L'/';
    wchar_t *p = (wchar_t *)xmalloc((na + slash + nb + 1) * sizeof(wchar_t));
    memcpy(p, a, na * sizeof(wchar_t));
    if (slash) p[na++] = L'\\';
    memcpy(p + na, b, (nb + 1) * sizeof(wchar_t));
    return p;
}

static void buf_reserve(Buf *b, size_t add) {
    size_t need = b->n + add;
    if (need <= b->cap) return;
    size_t cap = b->cap ? b->cap : 256;
    while (cap < need) cap <<= 1;
    b->v = (unsigned char *)xrealloc(b->v, cap);
    b->cap = cap;
}

static void buf_push(Buf *b, unsigned char x) {
    buf_reserve(b, 1);
    b->v[b->n++] = x;
}

static void buf_write(Buf *b, const void *src, size_t n) {
    buf_reserve(b, n);
    memcpy(b->v + b->n, src, n);
    b->n += n;
}

static void buf_u16(Buf *b, unsigned short x) {
    buf_push(b, (unsigned char)(x & 0xFF));
    buf_push(b, (unsigned char)(x >> 8));
}

static void u32_push(U32Vec *v, unsigned x) {
    if (v->n == v->cap) {
        v->cap = v->cap ? v->cap * 2 : 16;
        v->v = (unsigned *)xrealloc(v->v, v->cap * sizeof(*v->v));
    }
    v->v[v->n++] = x;
}

static void u16_push(U16Vec *v, unsigned short x) {
    if (v->n == v->cap) {
        v->cap = v->cap ? v->cap * 2 : 16;
        v->v = (unsigned short *)xrealloc(v->v, v->cap * sizeof(*v->v));
    }
    v->v[v->n++] = x;
}

static void str_push(StrVec *v, char *s) {
    if (v->n == v->cap) {
        v->cap = v->cap ? v->cap * 2 : 8;
        v->v = (char **)xrealloc(v->v, v->cap * sizeof(*v->v));
    }
    v->v[v->n++] = s;
}

static void entry_push(EntryVec *v, EntryMap e) {
    if (v->n == v->cap) {
        v->cap = v->cap ? v->cap * 2 : 32;
        v->v = (EntryMap *)xrealloc(v->v, v->cap * sizeof(*v->v));
    }
    v->v[v->n++] = e;
}

static unsigned short rd16(const unsigned char *p, size_t off) {
    return (unsigned short)(p[off] | (p[off + 1] << 8));
}

static unsigned rd32(const unsigned char *p, size_t off) {
    return (unsigned)(p[off] | (p[off + 1] << 8) | (p[off + 2] << 16) | (p[off + 3] << 24));
}

static unsigned be32(const unsigned char *p, size_t off) {
    return (unsigned)((p[off] << 24) | (p[off + 1] << 16) | (p[off + 2] << 8) | p[off + 3]);
}

static unsigned achr_size(const unsigned char *data, size_t pc) {
    unsigned sub = rd16(data, pc + 2);
    if (sub == 0) return 6;
    if (sub == 1 || sub == 2 || sub == 6) return 12;
    if (sub == 103 || sub == 110 || sub == 113 || sub == 114 || sub == 119 || sub == 128 || sub == 129) return 14;
    return 6;
}

static unsigned char *read_file_w(const wchar_t *path, size_t *size) {
    FILE *fp = _wfopen(path, L"rb");
    unsigned char *buf;
    size_t n;
    if (!fp) die("open failed");
    fseek(fp, 0, SEEK_END);
    n = (size_t)ftell(fp);
    fseek(fp, 0, SEEK_SET);
    buf = (unsigned char *)xmalloc(n ? n : 1);
    if (n && fread(buf, 1, n, fp) != n) die("read failed");
    fclose(fp);
    *size = n;
    return buf;
}

static char *read_text_w(const wchar_t *path) {
    size_t n;
    unsigned char *raw = read_file_w(path, &n);
    char *txt = (char *)xmalloc(n + 1);
    memcpy(txt, raw, n);
    txt[n] = 0;
    free(raw);
    return txt;
}

static void write_file_w(const wchar_t *path, const void *data, size_t size) {
    FILE *fp = _wfopen(path, L"wb");
    if (!fp) die("write failed");
    if (size && fwrite(data, 1, size, fp) != size) die("write failed");
    fclose(fp);
}

static void ensure_dir_w(const wchar_t *path) {
    CreateDirectoryW(path, NULL);
}

static unsigned char *decompress_1bin(const unsigned char *src, size_t src_size, size_t *out_size) {
    Buf out = {0};
    size_t pos = 8;
    unsigned want;
    if (src_size < 8 || memcmp(src, "1BIN", 4) != 0) die("not a 1BIN file");
    want = be32(src, 4);
    while (pos < src_size) {
        unsigned ctl = src[pos++];
        if (ctl & 0x80) {
            int count, back, cur, i;
            if (pos >= src_size) break;
            back = src[pos++];
            count = 2 - ((int)ctl - 256);
            cur = (int)out.n - back - 1;
            if (cur < 0) die("bad backref");
            for (i = 0; i < count; i++) {
                buf_push(&out, out.v[cur++]);
            }
        } else {
            if (ctl == 0 || pos + ctl > src_size) break;
            buf_write(&out, src + pos, ctl);
            pos += ctl;
        }
    }
    if (out.n != want) die("decompress size mismatch");
    *out_size = out.n;
    return out.v;
}

static int hash_at(const unsigned char *src, size_t len, int pos) {
    if ((unsigned)(pos + 1) >= len) return -1;
    return (src[pos] << 8) | src[pos + 1];
}

static void compress_1bin_body(const unsigned char *src, size_t len, Buf *body) {
    int *head = (int *)xmalloc(0x10000 * sizeof(int));
    int *chain = (int *)xmalloc((len ? len : 1) * sizeof(int));
    size_t sp = 0;
    size_t i;
    for (i = 0; i < 0x10000; i++) head[i] = -1;
    for (i = 0; i < len; i++) chain[i] = -1;
    while (sp < len) {
        int best_len = 0, best_dist = 0;
        if (sp + 1 < len) {
            int hash = hash_at(src, len, (int)sp);
            int prev;
            int max_len = (int)((len - sp) < 130 ? (len - sp) : 130);
            for (prev = head[hash]; prev >= 0; prev = chain[prev]) {
                int dist = (int)sp - prev;
                int m = 0;
                if (dist <= 0) continue;
                if (dist > 0x100) break;
                while (m < max_len && src[prev + m] == src[sp + m]) m++;
                if (m >= 3 && m > best_len) {
                    best_len = m;
                    best_dist = dist;
                    if (m == max_len) break;
                }
            }
        }
        if (best_dist == 1 && best_len >= 3 && sp + (size_t)best_len == len) best_len--;
        if (best_len >= 3) {
            int d = best_dist - 1;
            int k;
            buf_push(body, (unsigned char)(258 - best_len));
            buf_push(body, (unsigned char)(d & 0xFF));
            for (k = 0; k < best_len; k++) {
                int pos = (int)sp + k;
                int hash = hash_at(src, len, pos);
                if (hash >= 0) {
                    chain[pos] = head[hash];
                    head[hash] = pos;
                }
            }
            sp += (size_t)best_len;
        } else {
            int lit = 1;
            int pos = (int)sp;
            int hash = hash_at(src, len, pos);
            if (hash >= 0) {
                chain[pos] = head[hash];
                head[hash] = pos;
            }
            while (sp + (size_t)lit < len && lit < 0x7F) {
                int probe_len = 0, probe_dist = 0;
                size_t at = sp + (size_t)lit;
                if (at + 1 < len) {
                    int h = hash_at(src, len, (int)at);
                    int prev;
                    int max_len = (int)((len - at) < 130 ? (len - at) : 130);
                    for (prev = head[h]; prev >= 0; prev = chain[prev]) {
                        int dist = (int)at - prev;
                        int m = 0;
                        if (dist <= 0) continue;
                        if (dist > 0x100) break;
                        while (m < max_len && src[prev + m] == src[at + m]) m++;
                        if (m >= 3 && m > probe_len) {
                            probe_len = m;
                            probe_dist = dist;
                            if (m == max_len) break;
                        }
                    }
                }
                if (probe_len >= 3 && probe_dist > 0) break;
                hash = hash_at(src, len, (int)at);
                if (hash >= 0) {
                    chain[at] = head[hash];
                    head[hash] = (int)at;
                }
                lit++;
            }
            buf_push(body, (unsigned char)lit);
            buf_write(body, src + sp, (size_t)lit);
            sp += (size_t)lit;
        }
    }
    buf_push(body, 0);
    while ((8 + body->n) & 3) buf_push(body, 0);
    free(head);
    free(chain);
}

static unsigned char *compress_1bin(const unsigned char *src, size_t len, size_t *out_size) {
    Buf body = {0};
    Buf out = {0};
    compress_1bin_body(src, len, &body);
    buf_write(&out, "1BIN", 4);
    buf_push(&out, (unsigned char)((len >> 24) & 0xFF));
    buf_push(&out, (unsigned char)((len >> 16) & 0xFF));
    buf_push(&out, (unsigned char)((len >> 8) & 0xFF));
    buf_push(&out, (unsigned char)(len & 0xFF));
    buf_write(&out, body.v, body.n);
    free(body.v);
    *out_size = out.n;
    return out.v;
}

static char *cp932_to_utf8(const unsigned char *src, size_t len) {
    int wlen = MultiByteToWideChar(932, 0, (const char *)src, (int)len, NULL, 0);
    wchar_t *wbuf;
    int u8len;
    char *out;
    if (wlen < 0) die("cp932 decode failed");
    wbuf = (wchar_t *)xmalloc((wlen + 1) * sizeof(wchar_t));
    MultiByteToWideChar(932, 0, (const char *)src, (int)len, wbuf, wlen);
    wbuf[wlen] = 0;
    u8len = WideCharToMultiByte(CP_UTF8, 0, wbuf, wlen, NULL, 0, NULL, NULL);
    out = (char *)xmalloc(u8len + 1);
    WideCharToMultiByte(CP_UTF8, 0, wbuf, wlen, out, u8len, NULL, NULL);
    out[u8len] = 0;
    free(wbuf);
    return out;
}

static unsigned char *utf8_to_cp932(const char *src, size_t *out_len) {
    int wlen = MultiByteToWideChar(CP_UTF8, 0, src, -1, NULL, 0);
    wchar_t *wbuf;
    int clen;
    unsigned char *out;
    if (wlen <= 0) die("utf8 decode failed");
    wbuf = (wchar_t *)xmalloc((size_t)wlen * sizeof(wchar_t));
    MultiByteToWideChar(CP_UTF8, 0, src, -1, wbuf, wlen);
    clen = WideCharToMultiByte(932, 0, wbuf, -1, NULL, 0, NULL, NULL);
    if (clen <= 0) die("cp932 encode failed");
    out = (unsigned char *)xmalloc((size_t)clen - 1);
    WideCharToMultiByte(932, 0, wbuf, -1, (char *)out, clen, NULL, NULL);
    free(wbuf);
    *out_len = (size_t)clen - 1;
    return out;
}

static char *quote_bytes(const unsigned char *src, size_t len) {
    Buf out = {0};
    size_t i = 0;
    while (i < len && src[i]) {
        if (src[i] == 'c' && i + 1 < len && src[i + 1] == 'r') {
            buf_write(&out, "<cr>", 4);
            i += 2;
            continue;
        }
        if (src[i] == '\\' || src[i] == '"') {
            buf_push(&out, '\\');
            buf_push(&out, src[i++]);
            continue;
        }
        if (src[i] >= 0x20 && src[i] < 0x80) {
            buf_push(&out, src[i++]);
            continue;
        }
        if (src[i] >= 0xA1 && src[i] <= 0xDF) {
            char *u8 = cp932_to_utf8(src + i, 1);
            buf_write(&out, u8, strlen(u8));
            free(u8);
            i++;
            continue;
        }
        if (i + 1 < len) {
            char *u8 = cp932_to_utf8(src + i, 2);
            buf_write(&out, u8, strlen(u8));
            free(u8);
            i += 2;
            continue;
        }
        i++;
    }
    buf_push(&out, 0);
    return (char *)out.v;
}

static void line_write(Buf *b, const char *s) {
    buf_write(b, s, strlen(s));
}

static void line_num(Buf *b, unsigned x) {
    char tmp[32];
    sprintf(tmp, "%u", x);
    line_write(b, tmp);
}

static void line_hex4(Buf *b, unsigned x) {
    char tmp[16];
    sprintf(tmp, "0x%04X", x & 0xFFFF);
    line_write(b, tmp);
}

static void line_q(Buf *b, const unsigned char *src, size_t len) {
    char *u8 = quote_bytes(src, len);
    buf_push(b, '"');
    line_write(b, u8);
    buf_push(b, '"');
    free(u8);
}

static unsigned next_end(const unsigned *entries, unsigned count, unsigned idx, unsigned size) {
    unsigned start = entries[idx];
    unsigned i;
    for (i = idx + 1; i < count; i++) if (entries[i] > start) return entries[i];
    return size;
}

static void disasm_one(Buf *out, const unsigned char *data, unsigned size, const unsigned *entries, unsigned count, unsigned idx) {
    unsigned pc = entries[idx];
    unsigned end = next_end(entries, count, idx, size);
    while (pc < end) {
        unsigned op = rd16(data, pc);
        if (op >= NAME_COUNT) break;
        if (op == 0x10) {
            line_write(out, "ScrIf(");
            line_num(out, rd16(data, pc + 2));
            line_write(out, ", ");
            line_hex4(out, rd16(data, pc + 4));
            line_write(out, ", ");
            line_num(out, rd16(data, pc + 6));
            line_write(out, ", ");
            line_num(out, rd16(data, pc + 8));
            line_write(out, ", ");
            line_num(out, rd16(data, pc + 10));
            line_write(out, ")\r\n");
            pc += 12;
        } else if (op == 0x11 || op == 0x12) {
            line_write(out, NAMES[op]);
            line_write(out, "(");
            line_hex4(out, rd16(data, pc + 2));
            line_write(out, ")\r\n");
            pc += 4;
            if (op == 0x11) break;
        } else if (op == 0x13) {
            line_write(out, "ScrReturn()\r\n");
            pc += 2;
            break;
        } else if (op == 0x14) {
            unsigned a = data[pc + 4], b = data[pc + 6], cur = pc + 8, i;
            line_write(out, "ScrSelect(");
            line_num(out, rd16(data, pc + 2));
            line_write(out, ", ");
            line_num(out, a);
            line_write(out, ", ");
            line_num(out, b);
            for (i = 0; i < a + b; i++) {
                unsigned n = rd16(data, cur);
                line_write(out, ", ");
                line_q(out, data + cur + 2, 2 * (n - 1));
                cur += 2 * n;
            }
            line_write(out, ")\r\n");
            pc = cur;
        } else if (op == 0x19) {
            unsigned n = rd16(data, pc + 2);
            unsigned i;
            line_write(out, "ScrWinRubi(");
            for (i = 0; i < n; i++) {
                if (i) line_write(out, ", ");
                line_num(out, rd16(data, pc + 2 + i * 2));
            }
            line_write(out, ")\r\n");
            pc += 2 * (n + 1);
        } else if (op == 0x2A) {
            unsigned first = rd16(data, pc + 6);
            unsigned mid = pc + 2 * (first + 3);
            unsigned second = rd16(data, mid);
            line_write(out, "ScrMess(");
            line_num(out, rd16(data, pc + 2));
            line_write(out, ", ");
            line_num(out, rd16(data, pc + 4));
            line_write(out, ", ");
            line_q(out, data + pc + 8, 2 * (first - 1));
            line_write(out, ", ");
            line_q(out, data + mid + 2, 2 * (second - 1));
            line_write(out, ")\r\n");
            pc = mid + 2 * second;
        } else if (op == 0x2B) {
            unsigned size2 = achr_size(data, pc), n = size2 / 2 - 1, i;
            line_write(out, "ScrAchr(");
            for (i = 0; i < n; i++) {
                if (i) line_write(out, ", ");
                line_num(out, rd16(data, pc + 2 + i * 2));
            }
            line_write(out, ")\r\n");
            pc += size2;
        } else {
            unsigned n = WORDS[op] - 1, i;
            line_write(out, NAMES[op]);
            line_write(out, "(");
            for (i = 0; i < n; i++) {
                if (i) line_write(out, ", ");
                line_num(out, rd16(data, pc + 2 + i * 2));
            }
            line_write(out, ")\r\n");
            pc += WORDS[op] * 2;
        }
    }
}

static unsigned find_op(const char *name) {
    unsigned i;
    for (i = 0; i < NAME_COUNT; i++) if (!strcmp(name, NAMES[i])) return i;
    return 0xFFFF;
}

static void skip_ws(char **p) {
    while (**p && (unsigned char)**p <= ' ') (*p)++;
}

static char *parse_ident(char **p) {
    char *s = *p, *e;
    while (**p && (isalnum((unsigned char)**p) || **p == '_')) (*p)++;
    e = *p;
    {
        char hold = *e;
        char *r;
        *e = 0;
        r = xstrdup(s);
        *e = hold;
        return r;
    }
}

static unsigned parse_num(char **p) {
    unsigned x;
    x = (unsigned)strtoul(*p, p, 0);
    return x;
}

static char *parse_qstr(char **p) {
    Buf out = {0};
    if (**p != '"') die("expected quote");
    (*p)++;
    while (**p && **p != '"') {
        if (**p == '\\') {
            (*p)++;
            if (**p) buf_push(&out, (unsigned char)*(*p)++);
            continue;
        }
        if (!strncmp(*p, "<cr>", 4)) {
            buf_push(&out, 'c');
            buf_push(&out, 'r');
            *p += 4;
            continue;
        }
        {
            unsigned char tmp[8];
            int adv = 1;
            if ((unsigned char)(*p)[0] >= 0x80) {
                if (((unsigned char)(*p)[0] & 0xE0) == 0xC0) adv = 2;
                else if (((unsigned char)(*p)[0] & 0xF0) == 0xE0) adv = 3;
                else if (((unsigned char)(*p)[0] & 0xF8) == 0xF0) adv = 4;
            }
            memcpy(tmp, *p, adv);
            tmp[adv] = 0;
            {
                size_t cp_len;
                unsigned char *cp = utf8_to_cp932((char *)tmp, &cp_len);
                buf_write(&out, cp, cp_len);
                free(cp);
            }
            *p += adv;
        }
    }
    if (**p != '"') die("unterminated string");
    (*p)++;
    buf_push(&out, 0);
    if (out.n & 1) buf_push(&out, 0);
    return (char *)out.v;
}

static void expect(char **p, char ch) {
    skip_ws(p);
    if (**p != ch) die("syntax error");
    (*p)++;
}

static U16Vec parse_args_nums(char **p, StrVec *strs) {
    U16Vec nums = {0};
    skip_ws(p);
    if (**p == ')') return nums;
    for (;;) {
        skip_ws(p);
        if (**p == '"') str_push(strs, parse_qstr(p));
        else u16_push(&nums, (unsigned short)parse_num(p));
        skip_ws(p);
        if (**p == ')') break;
        if (**p != ',') die("expected comma");
        (*p)++;
    }
    return nums;
}

static void build_record(Buf *b, const char *s) {
    size_t len = strlen(s) + 1;
    unsigned short words;
    Buf tmp = {0};
    buf_write(&tmp, s, len);
    if (tmp.n & 1) buf_push(&tmp, 0);
    words = (unsigned short)(tmp.n / 2 + 1);
    buf_u16(b, words);
    buf_write(b, tmp.v, tmp.n);
    free(tmp.v);
}

static void assemble_line(Buf *out, const char *line) {
    char *copy = xstrdup(line);
    char *p = copy;
    char *name;
    StrVec strs = {0};
    U16Vec nums;
    unsigned op;
    skip_ws(&p);
    if (!*p) {
        free(copy);
        return;
    }
    name = parse_ident(&p);
    expect(&p, '(');
    nums = parse_args_nums(&p, &strs);
    expect(&p, ')');
    op = find_op(name);
    if (op == 0xFFFF) die("unknown opcode");
    buf_u16(out, (unsigned short)op);
    if (op == 0x10) {
        unsigned i;
        if (nums.n != 5) die("ScrIf arg count");
        for (i = 0; i < 5; i++) buf_u16(out, nums.v[i]);
    } else if (op == 0x11 || op == 0x12) {
        if (nums.n != 1) die("jump arg count");
        buf_u16(out, nums.v[0]);
    } else if (op == 0x13) {
    } else if (op == 0x14) {
        unsigned i;
        if (nums.n != 3 || strs.n != (size_t)(nums.v[1] + nums.v[2])) die("ScrSelect arg count");
        buf_u16(out, nums.v[0]);
        buf_push(out, (unsigned char)nums.v[1]);
        buf_push(out, 0);
        buf_push(out, (unsigned char)nums.v[2]);
        buf_push(out, 0);
        for (i = 0; i < strs.n; i++) build_record(out, strs.v[i]);
    } else if (op == 0x19) {
        unsigned i;
        if (!nums.n) die("ScrWinRubi arg count");
        for (i = 0; i < nums.n; i++) buf_u16(out, nums.v[i]);
    } else if (op == 0x2A) {
        if (nums.n != 2 || strs.n != 2) die("ScrMess arg count");
        buf_u16(out, nums.v[0]);
        buf_u16(out, nums.v[1]);
        build_record(out, strs.v[0]);
        build_record(out, strs.v[1]);
    } else if (op == 0x2B) {
        unsigned need = achr_size((unsigned char[]){0,0,(unsigned char)(nums.n?nums.v[0]&0xFF:0),(unsigned char)(nums.n?nums.v[0]>>8:0)}, 0) / 2 - 1;
        unsigned i;
        if (nums.n != need) die("ScrAchr arg count");
        for (i = 0; i < nums.n; i++) buf_u16(out, nums.v[i]);
    } else {
        unsigned need = WORDS[op] - 1, i;
        if (nums.n != need || strs.n) die("generic arg count");
        for (i = 0; i < nums.n; i++) buf_u16(out, nums.v[i]);
    }
    {
        size_t i;
        for (i = 0; i < strs.n; i++) free(strs.v[i]);
        free(strs.v);
        free(nums.v);
        free(name);
        free(copy);
    }
}

static void parse_list_xml(const wchar_t *path, EntryVec *entries, unsigned *max_id) {
    char *txt = read_text_w(path);
    char *p = txt;
    *max_id = 0;
    while ((p = strstr(p, "<entry ")) != NULL) {
        EntryMap e;
        char id[16] = {0}, file[260] = {0}, aliases[512] = {0};
        char *q = strchr(p, '>');
        if (!q) break;
        memset(&e, 0, sizeof(e));
        sscanf(p, "<entry id=\"%15[^\"]\" file=\"%259[^\"]\" aliases=\"%511[^\"]\"", id, file, aliases);
        if (!id[0]) sscanf(p, "<entry id=\"%15[^\"]\" file=\"%259[^\"]\"", id, file);
        e.id = (unsigned)strtoul(id, NULL, 16);
        e.file = xstrdup(file);
        u32_push(&e.refs, e.id);
        if (aliases[0]) {
            char *a = aliases, *tok;
            while ((tok = strtok(a, ",")) != NULL) {
                unsigned v = (unsigned)strtoul(tok, NULL, 16);
                u32_push(&e.refs, v);
                if (v > *max_id) *max_id = v;
                a = NULL;
            }
        }
        if (e.id > *max_id) *max_id = e.id;
        entry_push(entries, e);
        p = q + 1;
    }
    free(txt);
}

static const unsigned *ENTRY_SORT_BASE;

static int cmp_entry_offset(const void *a, const void *b) {
    const EntryMap *x = (const EntryMap *)a, *y = (const EntryMap *)b;
    unsigned xo = ENTRY_SORT_BASE[x->id];
    unsigned yo = ENTRY_SORT_BASE[y->id];
    if (xo < yo) return -1;
    if (xo > yo) return 1;
    return 0;
}

void onebin_extract_mem(const unsigned char *raw, size_t raw_size, const wchar_t *out_dir) {
    size_t data_size;
    unsigned char *data = decompress_1bin(raw, raw_size, &data_size);
    unsigned count = rd32(data, 0) / 4;
    unsigned *entries = (unsigned *)xmalloc(count * sizeof(unsigned));
    unsigned i, j;
    EntryVec unique = {0};
    Buf xml = {0};
    for (i = 0; i < count; i++) entries[i] = rd32(data, i * 4);
    for (i = 0; i < count; i++) {
        for (j = 0; j < unique.n; j++) {
            if (entries[unique.v[j].id] == entries[i]) {
                u32_push(&unique.v[j].refs, i);
                break;
            }
        }
        if (j == unique.n) {
            EntryMap e;
            memset(&e, 0, sizeof(e));
            e.id = i;
            {
                char name[16];
                sprintf(name, "%04X.asm", i);
                e.file = xstrdup(name);
            }
            u32_push(&e.refs, i);
            entry_push(&unique, e);
        }
    }
    ensure_dir_w(out_dir);
    {
        wchar_t *mask = wjoin2(out_dir, L"*.asm");
        WIN32_FIND_DATAW fd;
        HANDLE h;
        h = FindFirstFileW(mask, &fd);
        free(mask);
        if (h != INVALID_HANDLE_VALUE) {
            do {
                wchar_t *p = wjoin2(out_dir, fd.cFileName);
                DeleteFileW(p);
                free(p);
            } while (FindNextFileW(h, &fd));
            FindClose(h);
        }
        {
            wchar_t *p = wjoin2(out_dir, L"list.xml");
            DeleteFileW(p);
            free(p);
        }
    }
    ENTRY_SORT_BASE = entries;
    qsort(unique.v, unique.n, sizeof(unique.v[0]), cmp_entry_offset);
    for (i = 0; i < unique.n; i++) {
        Buf txt = {0};
        wchar_t wfile[32];
        wchar_t *path;
        MultiByteToWideChar(CP_ACP, 0, unique.v[i].file, -1, wfile, 32);
        path = wjoin2(out_dir, wfile);
        disasm_one(&txt, data, (unsigned)data_size, entries, count, unique.v[i].id);
        write_file_w(path, txt.v, txt.n);
        free(path);
        free(txt.v);
    }
    line_write(&xml, "<?xml version='1.0' encoding='utf-8'?>\r\n<entries>\r\n");
    for (i = 0; i < unique.n; i++) {
        char tmp[1024];
        size_t k;
        sprintf(tmp, "  <entry id=\"%04X\" file=\"%s\"", unique.v[i].id, unique.v[i].file);
        line_write(&xml, tmp);
        if (unique.v[i].refs.n > 1) {
            line_write(&xml, " aliases=\"");
            for (k = 1; k < unique.v[i].refs.n; k++) {
                if (k > 1) line_write(&xml, ",");
                sprintf(tmp, "%04X", unique.v[i].refs.v[k]);
                line_write(&xml, tmp);
            }
            line_write(&xml, "\"");
        }
        line_write(&xml, " />\r\n");
    }
    line_write(&xml, "</entries>\r\n");
    {
        wchar_t *path = wjoin2(out_dir, L"list.xml");
        write_file_w(path, xml.v, xml.n);
        free(path);
    }
    free(xml.v);
    for (i = 0; i < unique.n; i++) {
        free(unique.v[i].file);
        free(unique.v[i].refs.v);
    }
    free(unique.v);
    free(entries);
    free(data);
}

void onebin_extract_dir(const wchar_t *src_path, const wchar_t *out_dir) {
    size_t raw_size;
    unsigned char *raw = read_file_w(src_path, &raw_size);
    onebin_extract_mem(raw, raw_size, out_dir);
    free(raw);
}

unsigned char *onebin_pack_mem(const wchar_t *in_dir, size_t *out_size) {
    EntryVec map = {0};
    unsigned max_id, count, i, j;
    unsigned *entries;
    Buf scripts = {0};
    unsigned char *packed;
    {
        wchar_t *xml = wjoin2(in_dir, L"list.xml");
        parse_list_xml(xml, &map, &max_id);
        free(xml);
    }
    if (!map.n) die("empty list.xml");
    count = max_id + 1;
    entries = (unsigned *)xmalloc(count * sizeof(unsigned));
    for (i = 0; i < count; i++) entries[i] = 0;
    buf_reserve(&scripts, count * 4);
    for (i = 0; i < count * 4; i++) buf_push(&scripts, 0);
    for (i = 0; i < map.n; i++) {
        wchar_t wfile[32];
        wchar_t *path;
        MultiByteToWideChar(CP_ACP, 0, map.v[i].file, -1, wfile, 32);
        path = wjoin2(in_dir, wfile);
        char *txt = read_text_w(path);
        char *line = strtok(txt, "\r\n");
        unsigned offset = (unsigned)scripts.n;
        while (line) {
            assemble_line(&scripts, line);
            line = strtok(NULL, "\r\n");
        }
        for (j = 0; j < map.v[i].refs.n; j++) entries[map.v[i].refs.v[j]] = offset;
        free(txt);
        free(path);
    }
    for (i = 0; i < count; i++) {
        scripts.v[i * 4 + 0] = (unsigned char)(entries[i] & 0xFF);
        scripts.v[i * 4 + 1] = (unsigned char)((entries[i] >> 8) & 0xFF);
        scripts.v[i * 4 + 2] = (unsigned char)((entries[i] >> 16) & 0xFF);
        scripts.v[i * 4 + 3] = (unsigned char)((entries[i] >> 24) & 0xFF);
    }
    packed = compress_1bin(scripts.v, scripts.n, out_size);
    free(entries);
    free(scripts.v);
    for (i = 0; i < map.n; i++) {
        free(map.v[i].file);
        free(map.v[i].refs.v);
    }
    free(map.v);
    return packed;
}

void onebin_pack_dir(const wchar_t *in_dir, const wchar_t *out_path) {
    size_t out_size;
    unsigned char *packed = onebin_pack_mem(in_dir, &out_size);
    write_file_w(out_path, packed, out_size);
    free(packed);
}

#ifndef ONEBIN_NO_MAIN
int main(int argc, char **argv) {
    if (argc != 4) {
        fprintf(stderr, "usage: %s d input.1BIN output_dir\n       %s e input_dir output.1BIN\n", argv[0], argv[0]);
        return 1;
    }
    {
        int n2 = MultiByteToWideChar(CP_ACP, 0, argv[2], -1, NULL, 0);
        int n3 = MultiByteToWideChar(CP_ACP, 0, argv[3], -1, NULL, 0);
        wchar_t *a = (wchar_t *)xmalloc((size_t)n2 * sizeof(wchar_t));
        wchar_t *b = (wchar_t *)xmalloc((size_t)n3 * sizeof(wchar_t));
        MultiByteToWideChar(CP_ACP, 0, argv[2], -1, a, n2);
        MultiByteToWideChar(CP_ACP, 0, argv[3], -1, b, n3);
        if (!strcmp(argv[1], "d")) onebin_extract_dir(a, b);
        else if (!strcmp(argv[1], "e")) onebin_pack_dir(a, b);
        else die("unknown command");
        free(a);
        free(b);
    }
    return 0;
}
#endif
