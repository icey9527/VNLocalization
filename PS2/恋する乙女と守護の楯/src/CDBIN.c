#define _CRT_SECURE_NO_WARNINGS
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <wchar.h>
#include "1TEX.h"
#include "1BIN.h"

#define WSPRINTF _snwprintf

typedef struct {
    uint32_t table_va;
    uint32_t segment_va;
    uint32_t segment_file_offset;
    uint32_t sector_size;
} Config;

typedef struct {
    uint32_t sector;
    uint32_t size;
    uint32_t offset;
} Entry;

typedef struct {
    Entry *v;
    size_t n;
    size_t cap;
} EntryVec;

typedef struct {
    char *text;
    size_t size;
} TextBuf;

typedef struct {
    uint32_t offset;
    uint32_t size;
    char id8[16];
    char *xml;
    size_t xml_size;
} TexMemJob;

typedef struct {
    const wchar_t *cd_path;
    const wchar_t *out_dir;
    TexMemJob *jobs;
    size_t job_count;
    volatile LONG next;
} TexExtractCtx;

static Config cfg = {0x34B550, 0x100000, 0x80, 0x800};
static TextBuf g_tex_xml = {0};

static void fail(const char *msg) {
    fprintf(stderr, "%s\n", msg);
    exit(1);
}

static void load_config(void) {
    wchar_t path[MAX_PATH];
    wchar_t buf[64];
    GetModuleFileNameW(NULL, path, MAX_PATH);
    {
        wchar_t *p = wcsrchr(path, L'\\');
        if (p)
            p[1] = 0;
        else
            path[0] = 0;
    }
    wcscat(path, L"cd.ini");
    if (GetPrivateProfileStringW(L"cd", L"table_va", L"", buf, 64, path))
        cfg.table_va = (uint32_t)wcstoul(buf, NULL, 0);
    if (GetPrivateProfileStringW(L"cd", L"segment_va", L"", buf, 64, path))
        cfg.segment_va = (uint32_t)wcstoul(buf, NULL, 0);
    if (GetPrivateProfileStringW(L"cd", L"segment_file_offset", L"", buf, 64, path))
        cfg.segment_file_offset = (uint32_t)wcstoul(buf, NULL, 0);
    if (GetPrivateProfileStringW(L"cd", L"sector_size", L"", buf, 64, path))
        cfg.sector_size = (uint32_t)wcstoul(buf, NULL, 0);
}

static void *xmalloc(size_t n) {
    void *p = malloc(n ? n : 1);
    if (!p)
        fail("out of memory");
    return p;
}

static void *xrealloc(void *p, size_t n) {
    void *q = realloc(p, n ? n : 1);
    if (!q)
        fail("out of memory");
    return q;
}

static DWORD thread_count(void) {
    SYSTEM_INFO si;
    GetSystemInfo(&si);
    if (!si.dwNumberOfProcessors)
        return 1;
    if (si.dwNumberOfProcessors > 16)
        return 16;
    return si.dwNumberOfProcessors;
}

static void ensure_dir(const wchar_t *path) {
    CreateDirectoryW(path, NULL);
}

static void ensure_dir_tree(const wchar_t *path) {
    wchar_t tmp[1024];
    size_t n = wcslen(path);
    if (!n || n >= sizeof(tmp) / sizeof(tmp[0]))
        return;
    wcscpy(tmp, path);
    for (size_t i = 0; tmp[i]; i++) {
        if (tmp[i] != L'\\' && tmp[i] != L'/')
            continue;
        if (i == 0)
            continue;
        if (i == 2 && tmp[1] == L':')
            continue;
        {
            wchar_t ch = tmp[i];
            tmp[i] = 0;
            CreateDirectoryW(tmp, NULL);
            tmp[i] = ch;
        }
    }
    CreateDirectoryW(tmp, NULL);
}

static void ensure_parent_dir(const wchar_t *path) {
    wchar_t tmp[1024];
    wchar_t *p;
    if (wcslen(path) >= sizeof(tmp) / sizeof(tmp[0]))
        return;
    wcscpy(tmp, path);
    p = wcsrchr(tmp, L'\\');
    if (!p)
        p = wcsrchr(tmp, L'/');
    if (!p)
        return;
    *p = 0;
    if (!tmp[0])
        return;
    ensure_dir_tree(tmp);
}

static void join_path(wchar_t *out, size_t cap, const wchar_t *a, const wchar_t *b) {
    (void)cap;
    swprintf(out, L"%ls\\%ls", a, b);
}

static uint8_t *read_file(const wchar_t *path, size_t *size) {
    FILE *fp = _wfopen(path, L"rb");
    uint8_t *buf;
    long len;
    if (!fp)
        fail("open failed");
    fseek(fp, 0, SEEK_END);
    len = ftell(fp);
    fseek(fp, 0, SEEK_SET);
    if (len < 0)
        fail("bad file length");
    buf = xmalloc((size_t)len);
    if (len && fread(buf, 1, (size_t)len, fp) != (size_t)len)
        fail("read failed");
    fclose(fp);
    *size = (size_t)len;
    return buf;
}

static void write_file(const wchar_t *path, const void *data, size_t size) {
    ensure_parent_dir(path);
    FILE *fp = _wfopen(path, L"wb");
    if (!fp)
        fail("write failed");
    if (size && fwrite(data, 1, size, fp) != size)
        fail("write failed");
    fclose(fp);
}

static char *read_text8(const wchar_t *path, size_t *size) {
    size_t n;
    uint8_t *raw = read_file(path, &n);
    char *txt = (char *)xmalloc(n + 1);
    memcpy(txt, raw, n);
    txt[n] = 0;
    free(raw);
    if (size)
        *size = n;
    return txt;
}

static void write_text8(const wchar_t *path, const char *text) {
    write_file(path, text, strlen(text));
}

static uint32_t rd32(const uint8_t *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static void wr32(uint8_t *p, uint32_t x) {
    p[0] = (uint8_t)x;
    p[1] = (uint8_t)(x >> 8);
    p[2] = (uint8_t)(x >> 16);
    p[3] = (uint8_t)(x >> 24);
}

static void entry_push(EntryVec *v, Entry e) {
    if (v->n == v->cap) {
        v->cap = v->cap ? v->cap * 2 : 256;
        v->v = xrealloc(v->v, v->cap * sizeof(*v->v));
    }
    v->v[v->n++] = e;
}

static void tex_job_push(TexMemJob **jobs, size_t *count, size_t *cap, TexMemJob job) {
    if (*count == *cap) {
        *cap = *cap ? *cap * 2 : 64;
        *jobs = xrealloc(*jobs, *cap * sizeof(**jobs));
    }
    (*jobs)[(*count)++] = job;
}

static void hex4(wchar_t *out, size_t cap, size_t index) {
    WSPRINTF(out, cap, L"%04X", (unsigned)index);
}

static const wchar_t *suffix_from_head(const uint8_t *data, size_t size) {
    if (!size)
        return L".empty";
    if (size >= 4 && !memcmp(data, "\x00\x00\x01\xBA", 4))
        return L".mpg";
    if (size >= 4 && !memcmp(data, "1tex", 4))
        return L".1tex";
    if (size >= 4 && !memcmp(data, "1BIN", 4))
        return L".1BIN";
    return L".bin";
}

static EntryVec read_table(const wchar_t *elf, size_t cd_size) {
    EntryVec out = {0};
    size_t size;
    uint8_t *data = read_file(elf, &size);
    size_t pos = cfg.table_va - cfg.segment_va + cfg.segment_file_offset;
    while (pos + 8 <= size) {
        Entry e;
        e.sector = rd32(data + pos);
        e.size = rd32(data + pos + 4);
        e.offset = e.sector << 11;
        if (out.n && e.sector == 0)
            break;
        if (e.offset > cd_size || e.offset + e.size > cd_size)
            break;
        entry_push(&out, e);
        pos += 8;
    }
    free(data);
    return out;
}

static const char *tex_xml_find_block(const char *txt, const char *id, size_t *out_len) {
    char pat[64];
    char *a, *b;
    sprintf(pat, "<tex id=\"%s\">", id);
    a = strstr((char *)txt, pat);
    if (!a)
        return NULL;
    b = strstr(a, "</tex>");
    if (!b)
        return NULL;
    b += 6;
    *out_len = (size_t)(b - a);
    return a;
}

static void tex_xml_load_global(const wchar_t *in_dir) {
    wchar_t path[1024];
    if (g_tex_xml.text)
        return;
    join_path(path, 1024, in_dir, L"1tex.xml");
    g_tex_xml.text = read_text8(path, &g_tex_xml.size);
}

static void tex_xml_append_text(const wchar_t *out_dir, const char *txt, size_t size) {
    wchar_t path[1024];
    char *tmp = (char *)xmalloc(size + 1);
    char *a, *b;
    FILE *fp;
    memcpy(tmp, txt, size);
    tmp[size] = 0;
    a = strstr(tmp, "<tex ");
    b = a ? strstr(a, "</tex>") : NULL;
    if (!a || !b) {
        free(tmp);
        fail("bad 1tex xml text");
    }
    b += 6;
    join_path(path, 1024, out_dir, L"1tex.xml");
    ensure_parent_dir(path);
    fp = _wfopen(path, L"ab");
    if (!fp)
        fail("write failed");
    fwrite("  ", 1, 2, fp);
    fwrite(a, 1, (size_t)(b - a), fp);
    fwrite("\n", 1, 1, fp);
    fclose(fp);
    free(tmp);
}

static void tex_xml_begin(const wchar_t *out_dir) {
    wchar_t path[1024];
    join_path(path, 1024, out_dir, L"1tex.xml");
    write_text8(path, "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n<texs>\n");
}

static void tex_xml_end(const wchar_t *out_dir) {
    wchar_t path[1024];
    FILE *fp;
    join_path(path, 1024, out_dir, L"1tex.xml");
    ensure_parent_dir(path);
    fp = _wfopen(path, L"ab");
    if (!fp)
        fail("write failed");
    fwrite("</texs>\n", 1, 8, fp);
    fclose(fp);
}

static DWORD WINAPI tex_extract_worker(void *arg) {
    TexExtractCtx *ctx = (TexExtractCtx *)arg;
    FILE *fp = _wfopen(ctx->cd_path, L"rb");
    if (!fp)
        fail("open failed");
    for (;;) {
        LONG i = InterlockedIncrement(&ctx->next) - 1;
        uint8_t *buf;
        if ((size_t)i >= ctx->job_count)
            break;
        buf = xmalloc(ctx->jobs[i].size);
        if (fseeko64(fp, (long long)ctx->jobs[i].offset, SEEK_SET))
            fail("seek failed");
        if (ctx->jobs[i].size && fread(buf, 1, ctx->jobs[i].size, fp) != ctx->jobs[i].size)
            fail("read failed");
        ctx->jobs[i].xml = onetex_extract_one_mem(buf, ctx->jobs[i].size, ctx->out_dir, ctx->jobs[i].id8, &ctx->jobs[i].xml_size);
        free(buf);
    }
    fclose(fp);
    return 0;
}

static void auto_extract_one(const wchar_t *out_dir, size_t index, const uint8_t *data, size_t size) {
    wchar_t id[16], name[64], path[1024];
    const wchar_t *suf = suffix_from_head(data, size);
    hex4(id, 16, index);
    WSPRINTF(name, 64, L"%ls%ls", id, suf);
    if (!wcscmp(suf, L".1tex")) {
        char id8[16];
        char *xml;
        size_t xml_size;
        WideCharToMultiByte(CP_ACP, 0, id, -1, id8, 16, NULL, NULL);
        xml = onetex_extract_one_mem(data, size, out_dir, id8, &xml_size);
        tex_xml_append_text(out_dir, xml, xml_size);
        free(xml);
    } else if (!wcscmp(suf, L".1BIN")) {
        wchar_t subdir[1024], tmp[1024];
        join_path(subdir, 1024, out_dir, name);
        ensure_dir(subdir);
        join_path(tmp, 1024, subdir, name);
        onebin_extract_mem(data, size, subdir);
    } else {
        join_path(path, 1024, out_dir, name);
        write_file(path, data, size);
    }
}

static void command_extract(const wchar_t *elf, const wchar_t *cd, const wchar_t *out_dir) {
    EntryVec table;
    FILE *fp;
    size_t cd_size;
    TexMemJob *jobs = NULL;
    size_t job_count = 0, job_cap = 0;
    ensure_dir_tree(out_dir);
    {
        WIN32_FILE_ATTRIBUTE_DATA fad;
        if (!GetFileAttributesExW(cd, GetFileExInfoStandard, &fad))
            fail("cannot stat cd.bin");
        {
            ULARGE_INTEGER u;
            u.LowPart = fad.nFileSizeLow;
            u.HighPart = fad.nFileSizeHigh;
            cd_size = (size_t)u.QuadPart;
        }
    }
    table = read_table(elf, cd_size);
    fp = _wfopen(cd, L"rb");
    if (!fp)
        fail("open failed");
    for (size_t i = 0; i < table.n; i++) {
        uint8_t head[4] = {0};
        const wchar_t *suf;
        wchar_t id[16], name[64];
        if (fseeko64(fp, (long long)table.v[i].offset, SEEK_SET))
            fail("seek failed");
        if (table.v[i].size && fread(head, 1, table.v[i].size < 4 ? table.v[i].size : 4, fp) != (table.v[i].size < 4 ? table.v[i].size : 4))
            fail("read failed");
        suf = suffix_from_head(head, table.v[i].size < 4 ? table.v[i].size : 4);
        hex4(id, 16, i);
        WSPRINTF(name, 64, L"%ls%ls", id, suf);
        wprintf(L"%ls\n", name);
        if (!wcscmp(suf, L".1tex")) {
            TexMemJob job;
            memset(&job, 0, sizeof(job));
            job.offset = table.v[i].offset;
            job.size = table.v[i].size;
            WideCharToMultiByte(CP_ACP, 0, id, -1, job.id8, 16, NULL, NULL);
            tex_job_push(&jobs, &job_count, &job_cap, job);
            continue;
        }
        {
            uint8_t *buf = xmalloc(table.v[i].size);
            if (fseeko64(fp, (long long)table.v[i].offset, SEEK_SET))
                fail("seek failed");
            if (table.v[i].size && fread(buf, 1, table.v[i].size, fp) != table.v[i].size)
                fail("read failed");
            auto_extract_one(out_dir, i, buf, table.v[i].size);
            free(buf);
        }
    }
    fclose(fp);
    tex_xml_begin(out_dir);
    if (job_count) {
        TexExtractCtx ctx;
        HANDLE *threads;
        DWORD n;
        memset(&ctx, 0, sizeof(ctx));
        ctx.cd_path = cd;
        ctx.out_dir = out_dir;
        ctx.jobs = jobs;
        ctx.job_count = job_count;
        n = thread_count();
        if ((size_t)n > job_count)
            n = (DWORD)job_count;
        if (!n)
            n = 1;
        threads = xmalloc((size_t)n * sizeof(HANDLE));
        for (DWORD i = 0; i < n; i++)
            threads[i] = CreateThread(NULL, 0, tex_extract_worker, &ctx, 0, NULL);
        WaitForMultipleObjects(n, threads, TRUE, INFINITE);
        for (DWORD i = 0; i < n; i++)
            CloseHandle(threads[i]);
        free(threads);
        for (size_t i = 0; i < job_count; i++) {
            tex_xml_append_text(out_dir, jobs[i].xml, jobs[i].xml_size);
            free(jobs[i].xml);
        }
    }
    tex_xml_end(out_dir);
    free(jobs);
    free(table.v);
}

static int try_find_path(wchar_t *out, size_t cap, const wchar_t *dir, size_t index, const wchar_t *suffix, int dir_only) {
    wchar_t id[16], name[64], path[1024];
    DWORD attr;
    hex4(id, 16, index);
    WSPRINTF(name, 64, L"%ls%ls", id, suffix);
    join_path(path, 1024, dir, name);
    attr = GetFileAttributesW(path);
    if (attr == INVALID_FILE_ATTRIBUTES)
        return 0;
    if (dir_only && !(attr & FILE_ATTRIBUTE_DIRECTORY))
        return 0;
    if (!dir_only && (attr & FILE_ATTRIBUTE_DIRECTORY))
        return 0;
    wcsncpy(out, path, cap);
    out[cap - 1] = 0;
    return 1;
}

static uint8_t *build_one_entry(const wchar_t *in_dir, size_t index, size_t *out_size) {
    wchar_t path[1024], tmp[1024], id[16];
    hex4(id, 16, index);
    tex_xml_load_global(in_dir);
    {
        const char *xml_head = "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n<texs>\n";
        const char *xml_tail = "\n</texs>\n";
        char id8[16];
        const char *block;
        size_t block_len;
        char *xml_text;
        size_t head_len = strlen(xml_head);
        size_t tail_len = strlen(xml_tail);
        WideCharToMultiByte(CP_ACP, 0, id, -1, id8, 16, NULL, NULL);
        block = tex_xml_find_block(g_tex_xml.text, id8, &block_len);
        if (block) {
            xml_text = (char *)xmalloc(head_len + block_len + tail_len + 1);
            memcpy(xml_text, xml_head, head_len);
            memcpy(xml_text + head_len, block, block_len);
            memcpy(xml_text + head_len + block_len, xml_tail, tail_len);
            xml_text[head_len + block_len + tail_len] = 0;
            WSPRINTF(path, 1024, L"%ls.1tex", id);
            wprintf(L"%ls\n", path);
            {
                uint8_t *data = onetex_pack_one_mem(in_dir, xml_text, head_len + block_len + tail_len, id8, out_size);
                free(xml_text);
                return data;
            }
        }
    }
    if (try_find_path(path, 1024, in_dir, index, L".1BIN", 1)) {
        hex4(tmp, 1024, index);
        wcscat(tmp, L".1BIN");
        wprintf(L"%ls\n", tmp);
        return onebin_pack_mem(path, out_size);
    }
    if (try_find_path(path, 1024, in_dir, index, L".mpg", 0) ||
        try_find_path(path, 1024, in_dir, index, L".bin", 0) ||
        try_find_path(path, 1024, in_dir, index, L".empty", 0) ||
        try_find_path(path, 1024, in_dir, index, L".1tex", 0) ||
        try_find_path(path, 1024, in_dir, index, L".1BIN", 0)) {
        wchar_t *name = wcsrchr(path, L'\\');
        wprintf(L"%ls\n", name ? name + 1 : path);
        return read_file(path, out_size);
    }
    fprintf(stderr, "WARNING: entry missing in input dir: %ls\n", id);
    *out_size = 0;
    return NULL;
}

static void command_pack(const wchar_t *src_elf, const wchar_t *in_dir, const wchar_t *out_elf, const wchar_t *out_cd) {
    EntryVec table = read_table(src_elf, 0xFFFFFFFFu);
    size_t elf_size;
    uint8_t *elf = read_file(src_elf, &elf_size);
    ensure_parent_dir(out_cd);
    ensure_parent_dir(out_elf);
    FILE *fp = _wfopen(out_cd, L"wb");
    size_t table_pos = cfg.table_va - cfg.segment_va + cfg.segment_file_offset;
    if (!fp)
        fail("write failed");
    for (size_t i = 0; i < table.n; i++) {
        size_t size, pad;
        uint8_t *data = build_one_entry(in_dir, i, &size);
        if (!data)
            continue;
        long long cur = ftello64(fp);
        uint32_t sector;
        if (cur < 0)
            fail("ftell failed");
        pad = ((size_t)cur + cfg.sector_size - 1) & ~(cfg.sector_size - 1);
        while ((size_t)cur < pad) {
            fputc(0, fp);
            cur++;
        }
        sector = (uint32_t)((size_t)cur / cfg.sector_size);
        if (size && fwrite(data, 1, size, fp) != size)
            fail("write failed");
        wr32(elf + table_pos + i * 8, sector);
        wr32(elf + table_pos + i * 8 + 4, (uint32_t)size);
        free(data);
    }
    fclose(fp);
    write_file(out_elf, elf, elf_size);
    free(elf);
    free(table.v);
}

static wchar_t *argw(const char *s) {
    int n = MultiByteToWideChar(CP_ACP, 0, s, -1, NULL, 0);
    wchar_t *w = xmalloc((size_t)n * sizeof(wchar_t));
    MultiByteToWideChar(CP_ACP, 0, s, -1, w, n);
    return w;
}

int main(int argc, char **argv8) {
    wchar_t **argv = xmalloc((size_t)argc * sizeof(wchar_t *));
    DWORD attr;
    load_config();
    for (int i = 0; i < argc; i++)
        argv[i] = argw(argv8[i]);
    if (argc == 4) {
        attr = GetFileAttributesW(argv[2]);
        if (attr != INVALID_FILE_ATTRIBUTES && !(attr & FILE_ATTRIBUTE_DIRECTORY)) {
            command_extract(argv[1], argv[2], argv[3]);
            goto done_ok;
        }
    }
    if (argc == 5) {
        attr = GetFileAttributesW(argv[2]);
        if (attr != INVALID_FILE_ATTRIBUTES && (attr & FILE_ATTRIBUTE_DIRECTORY)) {
            command_pack(argv[1], argv[2], argv[3], argv[4]);
            goto done_ok;
        }
    }
    fwprintf(stderr, L"usage:\n  CDBIN elf cd.bin out_dir\n  CDBIN elf input_dir out.elf out_cd.bin\n");
    for (int i = 0; i < argc; i++)
        free(argv[i]);
    free(argv);
    return 1;
done_ok:
    for (int i = 0; i < argc; i++)
        free(argv[i]);
    free(argv);
    return 0;
}
